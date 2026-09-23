"""
Shared helpers for the radius-average feature: property-category
classification and OpenStreetMap Nominatim geocoding.

Category classification is a Bulgarian-keyword match against a listing's
title. Most portals already scope their search URL to apartments only
(alo.bg, homes.bg, imoti.bg), but imot.bg and olx.bg search "all real
estate for sale" and genuinely mix in houses/land/commercial - so every
portal runs the same classifier for consistency, rather than trusting
"apartments-only" portals to never contain a mislabeled listing.

Geocoding covers the 4 portals with no coordinates anywhere in their own
pages (static or JS-rendered) - homes.bg, olx.bg, imot.bg, imoti.bg,
confirmed by direct investigation (static HTML regex scan + a real headless
browser with cookie handling, WebGL enabled, and navigator.webdriver
patched, still found no map DOM node, no live google.maps.Map object, and
no maps iframe on either imot.bg or imoti.bg). Each of those 4 portals'
search is scoped to Sofia, and every listing carries a real neighborhood
name (the existing "area" field) - not a per-listing address, but real and
geocodable at neighborhood precision via OpenStreetMap's free Nominatim
API. Nominatim's usage policy caps free use at ~1 request/second and
expects heavy users to cache rather than re-request - and since Sofia has
only a few hundred distinct neighborhood names total (reused across
thousands of listings), caching by the query string itself (not per
listing) turns this into a one-time fixed cost rather than one geocode
call per listing: after the first run populates data/geocode_cache.json,
essentially every later call is a cache hit and costs nothing.

imoti.net, alo.bg, and bazar.bg need no geocoding at all - each embeds
real, listing-exact coordinates directly in its own listing page's HTML
(confirmed live): imoti.net as literal "latitude"/"longitude" JSON keys,
alo.bg as a plain <a href="https://maps.google.com/?q=LAT,LNG"> share
link, and bazar.bg as data-lat/data-long attributes on its #see_on_map
element - all present in the plain server-rendered HTML with no
JavaScript execution required, so a normal requests.get() picks them up.
"""

import json
import math
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CACHE_FILE = Path(__file__).parent / "data" / "geocode_cache.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a real identifying User-Agent (not a
# generic browser string) for the free public endpoint - see
# https://operations.osmfoundation.org/policies/nominatim/
GEOCODE_USER_AGENT = "bg-property-tracker/1.0 (personal deal-tracking tool, non-commercial)"
NOMINATIM_DELAY_SECONDS = 1.1

CATEGORY_KEYWORDS = {
    # Checked before "apartment" so e.g. "къща с 3 апартамента" (a house
    # subdivided into apartments) reads as a house, not an apartment.
    "land": ["парцел", "земеделска земя", "заведение за земя", "упи ", "имот за строеж", "терен"],
    "house": ["къща", "вила", "етаж от къща", "таунхаус"],
    "commercial": ["офис", "магазин", "склад", "хале", "заведение", "бизнес имот", "хотел", "ателие"],
    "apartment": [
        "апартамент", "едностаен", "двустаен", "тристаен", "четиристаен",
        "многостаен", "мезонет", "гарсониера", "стаен",
    ],
}


def classify_category(title):
    """Best-effort category from a Bulgarian listing title. Defaults to
    'apartment' when nothing matches, which is correct for every portal
    already scoped to an apartments-only search URL.

    KNOWN-BAD when called on a portal that ISN'T apartments-only: confirmed
    live for sales.bcpea.org (scraper_bcpea.py), whose auctions cover every
    property type - garages, farmland, production buildings, etc. - and
    whose own Bulgarian type words for those (e.g. "Гараж", "Земеделска
    земя") aren't all in CATEGORY_KEYWORDS below, so a majority of its own
    non-apartment listings silently default to "apartment" here. Never read
    a bcpea listing's raw "category" field expecting it to be accurate -
    type_filter_bucket() in sync_to_supabase.py (and typeFilterBucket() in
    index.html) already know this and use bcpea_type_match() against the
    title's own precise controlled vocabulary instead for that one portal;
    everything else in the app already goes through one of those two
    functions rather than raw category, so this is a dead-field trap for
    future code, not a live bug."""
    text = (title or "").lower()
    for category in ("land", "house", "commercial", "apartment"):
        if any(kw in text for kw in CATEGORY_KEYWORDS[category]):
            return category
    return "apartment"


# imoti.net embeds the listing's coordinates as plain JSON keys in the
# server-rendered detail page, e.g. "latitude":"42.72206626" - confirmed
# live via a plain (non-JS) HTTP fetch.
_IMOTI_NET_LAT_RE = re.compile(r'"latitude"\s*:\s*"?(-?\d{1,3}\.\d{3,10})"?')
_IMOTI_NET_LNG_RE = re.compile(r'"longitude"\s*:\s*"?(-?\d{1,3}\.\d{3,10})"?')


def extract_coords_imoti_net(html):
    lat_m = _IMOTI_NET_LAT_RE.search(html)
    lng_m = _IMOTI_NET_LNG_RE.search(html)
    if lat_m and lng_m:
        return {"lat": float(lat_m.group(1)), "lng": float(lng_m.group(1))}
    return None


# alo.bg embeds a plain "share this location" Google Maps link on the
# detail page, e.g. href="https://maps.google.com/?q=42.664,23.289&ll=...".
_ALO_MAPS_HREF_RE = re.compile(r"maps\.google\.com/\?q=(-?\d{1,3}\.\d{3,15}),(-?\d{1,3}\.\d{3,15})")


def extract_coords_alo(html):
    m = _ALO_MAPS_HREF_RE.search(html)
    if m:
        return {"lat": float(m.group(1)), "lng": float(m.group(2))}
    return None


# bazar.bg embeds the coordinates as data-lat/data-long attributes on its
# #see_on_map anchor, e.g. data-lat="42.698..." data-long="27.710...".
# Extracted as: find the whole tag, then find each attribute independently
# within it - not tied to a fixed attribute order or exact whitespace
# between them, since a first version requiring data-long to immediately
# follow data-lat undercounted real matches (~23% of a spot-checked sample
# vs. other portals' 88-100%) despite both attributes genuinely being
# present on the page.
_SEE_ON_MAP_TAG_RE = re.compile(r'<a\b[^>]*\bid="see_on_map"[^>]*>')
_DATA_LAT_RE = re.compile(r'data-lat="(-?\d{1,3}\.\d{3,15})"')
_DATA_LONG_RE = re.compile(r'data-long="(-?\d{1,3}\.\d{3,15})"')


def extract_coords_bazar(html):
    tag_match = _SEE_ON_MAP_TAG_RE.search(html)
    if not tag_match:
        return None
    tag = tag_match.group(0)
    lat_m = _DATA_LAT_RE.search(tag)
    lng_m = _DATA_LONG_RE.search(tag)
    if lat_m and lng_m:
        return {"lat": float(lat_m.group(1)), "lng": float(lng_m.group(1))}
    return None


# NOTE (backlog #9, 2026-09-23): `.obqva-block` was previously believed to
# hold alo.bg's real free-text description, but a later investigation
# sampling 200 real non-empty descriptions from data/leads_alo.json found
# 165/200 (82.5%) are literal substrings of that same listing's own `title`
# field - e.g. title "...Двустаен апартамент в к-с Суит хоум 2 Слънчев
# бряг, област Бургас" -> stored description "Двустаен апартамент в к-с
# Суит хоум 2". Re-sampling 300 records independently while fixing this
# reproduced the same shape at an even higher rate (265/300 = 88.3% exact
# substrings; nearly all of the remainder are still obvious near-duplicate
# title fragments, e.g. differing only by a trailing "!" or an emoji the
# title-truncation display cut off), never real seller-written prose. This
# is the same bug class as the already-fixed homes.bg case just above
# `extract_description_ldjson()`'s definition (see scraper_homes.py): a
# field that looks like a real description but is actually an echo of the
# title/heading blurb next to it.
#
# `.obqva-block` is therefore very likely the wrong element - probably a
# heading/summary blurb rendered near the title, not alo.bg's actual ad
# body - but this could not be confirmed live: alo.bg is blocked from this
# sandbox's network egress (both a plain HTTPS request and the WebFetch
# tool return a hard EGRESS_BLOCKED/403 for www.alo.bg), so a real probe of
# a live detail page to find the correct selector (if alo.bg even has a
# separate free-text ad-body element at all) is **deferred pending live
# access**, exactly like the still-open homes.bg description gap documented
# in scraper_homes.py.
#
# Until then, this returns None unconditionally rather than the
# `.obqva-block` text: a title-echo is actively misleading (it looks like a
# real description, so a caller/reader trusts it as one), so showing "no
# description available" is strictly better than showing a fake one - same
# reasoning as the homes.bg fix. This only stops *new* writes; it does not
# retroactively clear already-stored title-echo descriptions in
# data/leads_alo.json / data/history_alo.json (same scope as the homes.bg
# fix, which also only stopped writing the wrong value going forward).
_ALO_DESC_PREFIX_RES = [
    re.compile(r"^Допълнителна информация\s*"),
    re.compile(r"^За повече информация.*?в alo\.bg\.\s*"),
    re.compile(r"^Референтен номер:\s*\S+(?:\s+\S+)?\s*"),
    re.compile(r"^Отговорен брокер:\s*\S+(?:\s+\S+){0,1}\s*"),
]


def extract_description_alo(html):
    # Deliberately always returns None - see the NOTE above this function.
    # `_ALO_DESC_PREFIX_RES` is unused for now but kept in place (not
    # deleted): the boilerplate-stripping logic it encodes was confirmed
    # live against a real listing and is still expected to be needed once a
    # correct selector is found; a bare "not implemented" stub would lose
    # that already-verified logic.
    return None


# bazar.bg and olx.bg both embed the listing's real, agent/seller-written
# description as the "description" key of a <script type="application/
# ld+json"> block on the detail page (confirmed live via
# probe_descriptions.py) - takes the first non-empty one found, since a
# page can carry more than one ld+json block (e.g. bazar.bg also has an
# Organization block with no description at all).
def extract_description_ldjson(html):
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        blobs = data if isinstance(data, list) else [data]
        for blob in blobs:
            if isinstance(blob, dict) and blob.get("description"):
                return blob["description"].strip()
    return None


# imot.bg's real free-text description sits in a <div class="moreInfo">,
# prefixed with the fixed Bulgarian label "Описание на имота:" ("Property
# description:") - confirmed live via probe_descriptions.py (a Playwright
# fetch; imot.bg blocks plain requests-based fetching, same as its grid
# pages - see scraper_imot.py's module docstring).
_IMOT_BG_DESC_PREFIX_RE = re.compile(r"^Описание на имота:\s*")


def extract_description_imot(html):
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find("div", class_="moreInfo")
    if not node:
        return None
    text = _IMOT_BG_DESC_PREFIX_RE.sub("", node.get_text(" ", strip=True)).strip()
    return text or None


# imot.bg's detail page embeds every gallery photo twice - once under
# ".../<dir>//big1/..." (double slash) and once under ".../<dir>/big1/..."
# (single slash), both resolving to the same image - confirmed live via
# probe_photos.py. Normalizing the double slash before deduping is what
# turns that raw list into the real, distinct photo set.
_IMOT_PHOTO_RE = re.compile(r'https://cdn3\.focus\.bg/imot/photosimotbg/[^\s"\'<>]+?\.jpg', re.IGNORECASE)


def extract_photos_imot(html):
    seen = []
    for url in _IMOT_PHOTO_RE.findall(html):
        normalized = url.replace("//big1/", "/big1/")
        if normalized not in seen:
            seen.append(normalized)
    return seen


# bazar.bg and olx.bg both embed the listing's full photo gallery as the
# "image" key of the same <script type="application/ld+json"> block
# extract_description_ldjson() already reads "description" from -
# confirmed live via probe_photos.py for bazar.bg (17 photos in one
# listing's "image" array); olx.bg couldn't be directly probed (blocked
# by the same edge check its own scraper already routes around via
# Playwright - see backfill_detail_olx.py) but shares the same ld+json
# "description" shape, so worth trying the same key there too - returns
# an empty list harmlessly if olx.bg's own blob has no "image" key.
def extract_photos_ldjson(html):
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        blobs = data if isinstance(data, list) else [data]
        for blob in blobs:
            if not isinstance(blob, dict) or not blob.get("image"):
                continue
            image = blob["image"]
            return image if isinstance(image, list) else [image]
    return []


# imoti.net's detail page embeds the gallery as separate numbered files -
# "main_image/thumb_<size>_wm_main_image_<id>_1.jpg" for the cover photo,
# then "images/thumb_<size>_wm_images_<id>_<n>.jpg" for the rest - each at
# more than one size variant. Confirmed live via probe_photos.py (7 total
# URLs across 2 size variants for a 5-photo gallery + cover). Keeps only
# the 1200x630 variant (present for every photo, unlike the smaller
# 620x349 one which was only seen for the cover) and dedupes by photo
# number so each real photo appears once.
_IMOTI_NET_PHOTO_RE = re.compile(
    r'https://www\.imoti\.net/web/files/obiavi/\d+/(main_image|images)/'
    r'thumb_1200x630_wm_(?:main_image|images)_(\d+)_(\d+)\.jpg'
)


def extract_photos_imoti_net(html):
    by_index = {}
    for kind, listing_id, n in _IMOTI_NET_PHOTO_RE.findall(html):
        key = (0, int(n)) if kind == "main_image" else (1, int(n))
        by_index[key] = (
            f"https://www.imoti.net/web/files/obiavi/{listing_id}/{kind}/"
            f"thumb_1200x630_wm_{kind}_{listing_id}_{n}.jpg"
        )
    return [by_index[key] for key in sorted(by_index)]


# alo.bg's detail page lists every gallery photo as an <a class="fancyimages"
# data-type="image" href="user_files/.../<n>_big.jpg"> - a relative URL, and
# the reason a plain URL-regex scan missed them all (confirmed live via
# probe_photos_round2.py: 14 such anchors on one listing, none of them an
# absolute https:// URL). One extra non-photo anchor with data-type="ajax"
# (a "more on Google" panel) is excluded by requiring data-type="image".
_ALO_GALLERY_ANCHOR_RE = re.compile(
    r'<a\b[^>]*\bclass="[^"]*fancyimages[^"]*"[^>]*\bdata-type="image"[^>]*\bhref="([^"]+)"',
    re.IGNORECASE,
)


def extract_photos_alo(html):
    seen = []
    for href in _ALO_GALLERY_ANCHOR_RE.findall(html):
        url = href if href.startswith("http") else f"https://www.alo.bg/{href}"
        if url not in seen:
            seen.append(url)
    return seen


# "жк."/"ж.к." (жилищен комплекс - "residential complex") is a common
# Bulgarian prefix on neighborhood names (e.g. "жк. Лозенец") that, left
# in the query, made Nominatim return zero results ~95% of the time
# (56/59 in a spot-check of the real geocode cache) - while the exact same
# neighborhood names with the "кв." prefix or no prefix at all succeeded
# ~95-100% of the time. Stripped here, at the one call site every scraper
# shares, rather than in each scraper individually.
_ZHK_PREFIX_RE = re.compile(r"^ж\.?\s*к\.?\s+", re.IGNORECASE)


def _clean_query(query):
    return _ZHK_PREFIX_RE.sub("", query.strip())


def _haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


class Geocoder:
    """Caches by the exact query string on disk (data/geocode_cache.json,
    shared across all scrapers and committed to the repo like the other
    data files), so the same neighborhood name reused across thousands of
    listings - and across scraper runs - triggers one real Nominatim
    request total, not one per listing per run."""

    def __init__(self):
        self.cache = _load_cache()
        self._dirty = False

    def geocode_cached_only(self, query):
        """Cache lookup with no network call, for callers that can't afford
        to block on a live Nominatim round-trip (or its up-to-8s timeout)
        per listing - e.g. a scraper covering thousands of distinct
        nationwide locations for the first time, where the existing cache
        barely helps yet. Returns None on any cache miss instead of
        fetching; a separate backfill pass (see backfill_geocode_homes.py)
        does the live lookups on its own schedule."""
        query = _clean_query(query or "")
        return self.cache.get(query)

    def _geocode_raw(self, query, limit=1):
        """One real Nominatim lookup, no caching - callers manage the cache
        themselves so a single query() call can make more than one raw
        lookup (see geocode()'s cross-check) without double-charging the
        rate limit delay per cache write. limit>1 (used only by the
        confidence check below) doesn't cost an extra request - Nominatim
        returns up to `limit` ranked results in the one response."""
        time.sleep(NOMINATIM_DELAY_SECONDS)
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": limit},
                headers={"User-Agent": GEOCODE_USER_AGENT},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            points = [{"lat": float(d["lat"]), "lng": float(d["lon"])} for d in data]
        except Exception as e:
            print(f"DEBUG: geocode failed for {query!r}: {e}")
            points = []
        return points[0] if (points and limit == 1) else points

    def _bare_name_is_confident(self, query):
        """A bare settlement name is only trustworthy as independent ground
        truth when Nominatim itself is confident about it - i.e. its top
        few ranked results agree on roughly one place, not scattered
        across the country. A GENUINE distinct settlement name (like
        "Червен бряг") resolves this way. A generic word reused as a
        district name in many unrelated towns (Център/"Center", Дружба/
        "Friendship", Изток/"East"...) does not - its top results are
        each a real place, just different, unrelated ones - so trusting
        the single top hit as "the" answer for those would be wrong.
        This replaces an earlier attempt at this that tried to hand-list
        which cities/words are "safe" to skip - that approach doesn't
        scale (an early version only excluded Bulgaria's 4 biggest
        cities, and still wrongly overrode dozens of ordinary districts
        in smaller cities like Ruse and Haskovo, corrupting real data
        before being caught and reverted). Checking the bare name's own
        result spread works for any settlement name, known in advance or
        not, without needing a list of exceptions at all."""
        top = self._geocode_raw(query, limit=3)
        if len(top) < 2:
            return len(top) == 1
        ref = top[0]
        return all(_haversine_km(ref["lat"], ref["lng"], p["lat"], p["lng"]) <= 30 for p in top[1:])

    def geocode(self, query):
        query = _clean_query(query or "")
        if not query:
            return None
        if query in self.cache:
            return self.cache[query]

        result = self._geocode_raw(query)

        # Independent verification, not blind trust: a query like "<area>,
        # <city>, България" only ever resolves correctly if <city> is
        # really that area's own city/region - and for a city/oblast-
        # sliced scraper, <city> is often just whichever search page a
        # listing happened to turn up on, not a fact about the listing
        # itself (confirmed live: an imot.bg "Lovech" city search
        # returned a real Cherven Bryag listing, an entirely different
        # town in a different oblast - geocoding "Червен бряг, Ловеч,
        # България" resolved ~62km from the real town, propagating a
        # wrong coordinate to every listing that shared the query).
        # The bare settlement name is only trusted as the independent
        # answer when it's ALSO independently confident on its own (see
        # _bare_name_is_confident) - a generic district name disagreeing
        # with its qualifier is not evidence the qualifier is wrong, it's
        # just an ambiguous word; only override when the bare name is
        # both different from the qualified result AND unambiguous by
        # itself.
        parts = [p.strip() for p in query.split(",")]
        if result and len(parts) >= 3 and parts[0]:
            bare_query = _clean_query(f"{parts[0]}, България")
            if bare_query != query:
                bare_result = self.cache.get(bare_query)
                if bare_query not in self.cache:
                    bare_result = self._geocode_raw(bare_query)
                    self.cache[bare_query] = bare_result
                    self._dirty = True
                if bare_result:
                    dist_km = _haversine_km(result["lat"], result["lng"], bare_result["lat"], bare_result["lng"])
                    if dist_km > 30 and self._bare_name_is_confident(bare_query):
                        print(f"DEBUG: geocode mismatch for {query!r} vs {bare_query!r} "
                              f"({dist_km:.0f}km apart, bare name confident) - trusting the bare settlement name")
                        result = bare_result
                    elif dist_km > 30:
                        print(f"DEBUG: geocode mismatch for {query!r} vs {bare_query!r} "
                              f"({dist_km:.0f}km apart, bare name AMBIGUOUS) - keeping the qualified result")

        self.cache[query] = result
        self._dirty = True
        return result

    def save(self):
        if self._dirty:
            CACHE_FILE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
            self._dirty = False


def prune_snapshots(history):
    # Every scraper appends one {seen_at, price_eur} snapshot per listing
    # per run regardless of whether the price changed - the real driver of
    # history_*.json's size at nationwide scale (a listing scraped every 6h
    # for 8 months with 2 real price changes stores ~970 raw snapshots
    # before this, 3 after). Shrinks each listing's snapshot list to its
    # first snapshot, every point where the price actually changed, and
    # the single most recent snapshot - kept unconditionally, even when
    # its price repeats the one before it, so last-seen/removed_at/
    # days_on_market (all read off the last snapshot's timestamp) stay
    # exactly as accurate as before this ran. Never drops a listing or a
    # real price change, only redundant same-price snapshots in between.
    for rec in history.values():
        snapshots = rec.get("snapshots") or []
        if not snapshots:
            continue
        pruned = [snapshots[0]]
        for s in snapshots[1:]:
            if s.get("price_eur") != pruned[-1].get("price_eur"):
                pruned.append(s)
        if pruned[-1] is not snapshots[-1]:
            pruned.append(snapshots[-1])
        rec["snapshots"] = pruned
    return history


# --- City-key derivation - shared by every scraper's own compute_leads()
# (for area averages) and sync_to_supabase.py's cross-portal merge/city
# filter. Used to live only in sync_to_supabase.py; moved here so a
# scraper doesn't need its own separate copy (import sync_to_supabase.py
# from a scraper would be backwards - this module already flows the other
# way) and so there is exactly one implementation to keep correct, not two
# that can quietly drift apart.
#
# sales.bcpea.org's own listing-type lookup lives here too, since
# listing_city_key() needs it for that portal's settlement-from-title
# extraction (bcpea has no separate "city" field - the settlement name IS
# the title, once the type prefix is stripped).
BCPEA_RAW_TYPES = [
    ("flat", ["Едностаен апартамент", "Двустаен апартамент", "Тристаен апартамент",
              "Многостаен апартамент", "Мезонет", "Ателие, Таван", "Стая"]),
    ("house", ["Вила", "Етаж от къща", "Къща", "Жилищна сграда", "Къща с парцел"]),
    ("land", ["Парцел", "Земеделска земя", "Земеделски имот", "Парцел с къща"]),
    ("garage", ["Гараж", "Паркомясто"]),
    ("shop", ["Магазин", "Заведение"]),
    ("business", ["Офис", "Склад", "Фабрика", "Хотел", "Търговски имот",
                  "Производствен имот", "Бензиностанция", "Газстанция", "Автомивка"]),
]
# Longest raw type first, so a type string that's a prefix of another (e.g.
# "Къща" vs "Къща с парцел") always resolves to the more specific one.
BCPEA_TYPE_LOOKUP = sorted(
    ((raw_type, key) for key, raw_types in BCPEA_RAW_TYPES for raw_type in raw_types),
    key=lambda pair: -len(pair[0]),
)


def bcpea_type_match(title):
    if not title:
        return None
    for raw_type, key in BCPEA_TYPE_LOOKUP:
        if title.startswith(raw_type):
            return raw_type, key
    return None


def bcpea_settlement_from_title(title):
    match = bcpea_type_match(title)
    if match:
        raw_type, _ = match
        rest = title[len(raw_type):]
        return re.sub(r"^,\s*", "", rest).strip() or None
    # "Други" ("Other") is a real bcpea.org category label outside
    # BCPEA_RAW_TYPES' controlled vocabulary - deliberately NOT added there,
    # since bcpea_type_match() returning None for it is exactly what makes
    # type_filter_bucket() correctly bucket these listings "other" (backlog
    # item 21). But the settlement name still follows the same
    # "<category label>, <settlement>" shape every other bcpea title uses
    # (e.g. "Други, Брезово"), so settlement extraction alone needs its own
    # narrow handling of this one label to not lose the location signal.
    if title and title.startswith("Други"):
        rest = title[len("Други"):]
        return re.sub(r"^,\s*", "", rest).strip() or None
    return None


BG_CITIES = [
    ("sofia", "София"), ("plovdiv", "Пловдив"), ("varna", "Варна"), ("burgas", "Бургас"),
    ("ruse", "Русе"), ("stara_zagora", "Стара Загора"), ("pleven", "Плевен"), ("sliven", "Сливен"),
    ("dobrich", "Добрич"), ("shumen", "Шумен"), ("pernik", "Перник"), ("haskovo", "Хасково"),
    ("yambol", "Ямбол"), ("pazardzhik", "Пазарджик"), ("blagoevgrad", "Благоевград"),
    ("veliko_tarnovo", "Велико Търново"), ("vratsa", "Враца"), ("gabrovo", "Габрово"),
    ("vidin", "Видин"), ("asenovgrad", "Асеновград"), ("kazanlak", "Казанлък"),
    ("kyustendil", "Кюстендил"), ("kardzhali", "Кърджали"), ("montana", "Монтана"),
    ("dimitrovgrad", "Димитровград"), ("targovishte", "Търговище"), ("lovech", "Ловеч"),
    ("silistra", "Силистра"), ("dupnitsa", "Дупница"), ("svishtov", "Свищов"),
]
BG_CITY_BY_NAME = {name: key for key, name in BG_CITIES}


def city_key_from_name(name):
    if not name:
        return None
    # Sofia is the one BG_CITIES name where this "strip a trailing 'област'"
    # normalization below is actively wrong, not just a no-op: "София
    # област" (Sofia Province/Софийска област) is a REAL, DIFFERENT oblast
    # from Sofia city itself (city_key "sofia" -> oblast "sofia_grad";
    # Sofia Province is oblast "sofia" - see BG_OBLASTS/CITY_KEY_TO_OBLAST's
    # own comments for the same sofia/sofia_grad split). Every other
    # BG_CITIES name's own oblast happens to share that city's exact name
    # (e.g. Plovdiv city sits in an oblast that's also just called
    # "Пловдив"), so stripping "област" there is harmless - only Sofia has
    # two differently-named oblasts where blindly stripping "област" turns
    # a real reference to the SURROUNDING region into a false match for the
    # CAPITAL city. Confirmed live: 67 imoti.bg listings literally tagged
    # city="София област" (backlog item 20-22-adjacent audit) were all
    # resolving to sofia_grad instead of the correct "sofia" (province)
    # oblast before this fix.
    stripped = name.strip()
    if re.match(r"^софия\s*област$", stripped, flags=re.IGNORECASE):
        return None
    # Strips a trailing settlement-type suffix a portal's own title text can
    # tack on after the real city name - "област" (region), or homes.bg's
    # own "<City> - град"/"- село" (town/village) convention, live-sampled
    # from real currently-active homes.bg titles like "София, София - град"
    # (the second "София" is the last comma segment the title fallback
    # reads, but " - град" made it fail to match "София" exactly).
    normalized = re.sub(r"\s*(?:област|-\s*град|-\s*село)$", "", stripped, flags=re.IGNORECASE).strip()
    return BG_CITY_BY_NAME.get(normalized)


# alo.bg's title has "<area>, <city>" but sometimes runs the price straight
# into the city with no separating comma - "...Дианабад, София Цена : 480
# 000 €" - so the last comma segment is "София Цена : 480 000 €", not
# "София" alone, and the exact match above fails even though the city name
# is right there. Live-sampled: every currently-active alo.bg listing with
# a null city_key that still had a comma in its title matched this shape.
# Longest names first so "Стара Загора" doesn't prefix-match as "Стара"
# alone (not a real entry, but keeps the general principle safe).
BG_CITY_PREFIX_RE = re.compile(
    r"^(" + "|".join(re.escape(name) for _, name in sorted(BG_CITIES, key=lambda c: -len(c[1]))) + r")\b"
)


def city_key_from_name_prefix(name):
    if not name:
        return None
    stripped = name.strip()
    # Same Sofia-specific guard as city_key_from_name() above - a name
    # starting with "София област" must not prefix-match "София" the city.
    if re.match(r"^софия\s*област\b", stripped, flags=re.IGNORECASE):
        return None
    normalized = re.sub(r"\s*(?:област|-\s*град|-\s*село)$", "", stripped, flags=re.IGNORECASE).strip()
    match = BG_CITY_PREFIX_RE.match(normalized)
    return BG_CITY_BY_NAME.get(match.group(1)) if match else None


# imoti.net's own titles render the city in English/Latin script ("... Sofia,
# Lyulin Center" - the city is the SECOND-to-last comma segment there, not
# the last, so the generic last-comma fallback above can never recover it).
# This bit imoti.net hardest: a live sample of currently-active,
# freshly-scraped imoti.net listings with no "city" field found ~5,800 of
# them (28% of all active merged listings, and the single largest unmatched
# bucket of any portal) were genuinely Sofia listings whose title plainly
# says so in Latin script - e.g. "Shop, 44 m2 Sofia, Lyulin Center". Reuses
# the same slugs scraper.py's own CITY_SLUGS already live-verified against
# imoti.net's real city pages, just keyed by the natural-language spelling
# (space, not the URL slug's hyphen) since this searches free-form title
# text, not a URL.
LATIN_CITY_TO_KEY = {
    "sofia": "sofia", "plovdiv": "plovdiv", "varna": "varna", "burgas": "burgas", "bourgas": "burgas",
    "ruse": "ruse", "stara zagora": "stara_zagora", "pleven": "pleven", "sliven": "sliven",
    "dobrich": "dobrich", "shumen": "shumen", "pernik": "pernik", "haskovo": "haskovo",
    "yambol": "yambol", "pazardzhik": "pazardzhik", "blagoevgrad": "blagoevgrad",
    "veliko tarnovo": "veliko_tarnovo", "vratsa": "vratsa", "gabrovo": "gabrovo", "vidin": "vidin",
    "kardzhali": "kardzhali", "montana": "montana", "targovishte": "targovishte", "lovech": "lovech",
    "silistra": "silistra",
}
LATIN_CITY_RE = re.compile(
    r"\b(" + "|".join(sorted((k.replace(" ", r"\s+") for k in LATIN_CITY_TO_KEY), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def latin_city_key_from_text(text):
    if not text:
        return None
    match = LATIN_CITY_RE.search(text)
    if not match:
        return None
    normalized = re.sub(r"\s+", " ", match.group(1).lower())
    return LATIN_CITY_TO_KEY.get(normalized)


# bazar.bg's own title format has the same "city buried mid-string, not in
# the last comma segment" problem as imoti.net, just in Cyrillic: "Продава
# 3-СТАЕН, гр. София, Левски Г" - the city is the "гр. <City>" segment in
# the middle, area (last segment) is the neighborhood. A live sample of
# currently-active bazar.bg listings with no "city" field (stale rows
# scraped before bazar.bg's nationwide city-tagging merged today) confirmed
# this "гр. <City>," shape holds consistently, matching bazar.bg's own
# AREA_LINE_RE ("^гр\.\s*\S.*?,\s*(.+)$") which already relies on the same
# "гр. " prefix convention to find the area line at all.
CYR_CITY_TITLE_RE = re.compile(
    r"гр\.?\s*(" + "|".join(re.escape(name) for _, name in BG_CITIES) + r")"
)


def cyr_city_key_from_text(text):
    if not text:
        return None
    match = CYR_CITY_TITLE_RE.search(text)
    if not match:
        return None
    return BG_CITY_BY_NAME.get(match.group(1))


def _title_derived_city_key(title):
    # The title-only half of listing_city_key()'s resolution, kept separate
    # so listing_city_key() can compute it independently of the "city"
    # field and compare the two - see that function's own comment for why.
    if not title:
        return None
    if "," in title:
        last_segment = title.rsplit(",", 1)[1].strip()
        key = city_key_from_name(last_segment)
        if key:
            return key
        key = city_key_from_name_prefix(last_segment)
        if key:
            return key
    key = latin_city_key_from_text(title)
    if key:
        return key
    return cyr_city_key_from_text(title)


def listing_city_key(l):
    # Ported 1:1 from index.html's listingCityKey() - see that function's
    # comment for the full story (this used to unconditionally return
    # "sofia" for every non-bcpea portal, silently miscounting every real
    # non-Sofia listing from homes.bg/imoti.bg as Sofia).
    if l.get("portal") == "sales.bcpea.org":
        settlement = bcpea_settlement_from_title(l.get("title"))
        return city_key_from_name(settlement) if settlement else None

    title = l.get("title")
    title_key = _title_derived_city_key(title)

    city = l.get("city")
    field_key = None
    if city:
        field_key = city_key_from_name(city)
        if not field_key:
            field_key = city_key_from_name_prefix(city)

    # A live report found a listing whose "city" field disagreed with its
    # own title (a stale/wrong scrape-time field vs. a title that plainly,
    # unambiguously names a different real city) - trusting the field
    # unconditionally let two listings that don't actually share a city
    # slip through a downstream cross-portal match on area+price alone
    # (see group_listings()'s own comment). The title is the thing a human
    # reader would trust in that situation, so when both resolve and
    # disagree, the title wins.
    if field_key and title_key and field_key != title_key:
        return title_key
    return field_key or title_key


# --- Motivation score (backlog item, reworked after relisting detection was
# built) ------------------------------------------------------------------
#
# A single shared implementation, unlike most of this project's per-scraper
# compute_leads() logic (deliberately duplicated there - see e.g.
# scraper.py's own comments - because those tweaks are a few inline lines
# woven into each scraper's own loop). This is different: a self-contained
# function with plain inputs and no scraper-specific state, exactly the
# kind of logic this module already centralizes for the same reason
# listing_city_key() lives here instead of copy-pasted 8 times - one
# implementation that can't drift, not eight that could.
#
# Original formula (still what every scraper computes today, before this
# rework ships) was two inputs only: min(drop_pct,0..20)/20*50 +
# min(days_on_market,0..180)/180*50. Reworked per direct user request once
# relisting detection existed to feed it: five inputs, weighted and capped
# from real distributions measured against the live committed dataset
# (all 8 portals, deduped through the same merge sync_to_supabase.py's
# group_listings() does) - not guessed. See each cap's own comment for the
# specific percentile that justified it.
#
# Matches index.html's own UNVERIFIED_PCT_THRESHOLD (computeUnverified()) -
# a price/m² this far from its area average is flagged there as a likely
# data error rather than a real bargain, and the same judgment applies
# here: an "unverified" pct_vs_area_avg must not earn motivation-score
# points, or a parsing error could outscore a genuine below-market deal.
UNVERIFIED_PCT_THRESHOLD = 60

# Below this many points, the caller couldn't compute a real distinct-
# reduction/drop-size/days-on-market picture at all (see the docstring on
# compute_motivation_score for when that happens) - not currently used to
# gate anything here, kept only as a named constant so the 85/100 rescale
# factor below has a name instead of a bare magic number.
_RESCALE_WITHOUT_AREA_AVG = 85


def _relisting_score_component(price_history):
    """Up to 25 points: 10 base for having been delisted and relisted at
    all (a real, behavioral "this deal stalled and the ad restarted"
    event - the strongest single signal this formula has, per the user's
    own framing), plus up to 15 more scaled to how much cheaper it came
    back. Real data: of 112 relistings where both the old and new price
    are known, 74% came back lower, median cut 3.9%, 90th percentile
    17.5% - capped at a 15% price cut for full marks on the bonus, so it's
    reachable by genuinely large capitulations without needing an extreme
    outlier to max out. A relisting at the same or a higher price still
    earns the 10-point base (something changed enough for the ad to be
    pulled and restarted) but no bonus.

    price_history is chronological (see every compute_leads()'s own
    price_history construction) - a listing relisted more than once uses
    its LAST (most recent) tagged event, the freshest signal, rather than
    whichever event happened to produce the highest score.
    """
    before = after = None
    for entry in price_history:
        if not isinstance(entry, dict) or entry.get("source") != "relisted_from":
            continue
        before = entry.get("price_eur")
        after = entry.get("came_back_price")
    if before is None:
        return 0
    points = 10
    if before and after and after < before:
        drop_on_relist = (before - after) / before * 100
        points += min(drop_on_relist, 15) / 15 * 15
    return points


def compute_motivation_score(drop_pct, price_drop_count, days_on_market, pct_vs_area_avg, price_history):
    """The five components, each capped, summed, and rescaled to 0-100.

    Every component except the area-average one is always computable - a
    listing that was never reduced or never relisted legitimately scores 0
    there, which isn't missing data, it's a real answer. pct_vs_area_avg is
    the one genuine gap: None when the listing (or too few of its area
    peers) has no sqm/price_per_sqm to compare, and treated as unusable
    (not just missing, actively excluded) when it's flagged unverified -
    see UNVERIFIED_PCT_THRESHOLD above. When that component isn't usable,
    the other four are rescaled from their 0-85 raw sum up to 0-100 rather
    than leaving every affected listing capped below the real top end -
    the deliberate "rescale" choice over "cap at 85", made because the gap
    is a data-collection artifact (alo.bg in particular has sparse sqm
    coverage) rather than a real signal about the listing, and capping
    would systematically punish whichever portals/areas happen to have
    thinner coverage rather than reflecting anything about the property
    itself.
    """
    relist_pts = _relisting_score_component(price_history)
    drop_count_pts = min(price_drop_count or 0, 3) / 3 * 20  # real p90=1, p95=2, p99=3 among ever-reduced listings - a cap of 4+ would be unreachable
    drop_pct_pts = min(max(drop_pct or 0, 0), 20) / 20 * 20  # unchanged cap from the original formula - real data confirms it still sits near the ~96th percentile of reduced listings
    days_pts = min(days_on_market or 0, 180) / 180 * 20  # unchanged cap - kept for when tracking history matures rather than fitted to today's artificially compressed (~23-28 day) distribution

    area_available = pct_vs_area_avg is not None and abs(pct_vs_area_avg) < UNVERIFIED_PCT_THRESHOLD
    area_pts = 0
    if area_available and pct_vs_area_avg < 0:
        area_pts = min(abs(pct_vs_area_avg), 40) / 40 * 15  # real data (verified listings only): cap sits near the 90th percentile of below-average listings

    raw_total = relist_pts + drop_count_pts + drop_pct_pts + days_pts + (area_pts if area_available else 0)
    denom = 100 if area_available else _RESCALE_WITHOUT_AREA_AVG
    return round(raw_total * 100 / denom)
