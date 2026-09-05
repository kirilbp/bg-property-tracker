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
    already scoped to an apartments-only search URL."""
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


# alo.bg's real free-text description sits in a <div class="obqva-block">,
# but always prefixed with a fixed boilerplate paragraph (contact
# instructions + reference number + responsible broker, when the listing
# has one) ahead of the actual text - confirmed live via probe_descriptions.py
# against a real listing. Each regex strips one known-fixed segment, only
# if present, so a private-seller listing (no boilerplate at all) passes
# through unchanged.
_ALO_DESC_PREFIX_RES = [
    re.compile(r"^Допълнителна информация\s*"),
    re.compile(r"^За повече информация.*?в alo\.bg\.\s*"),
    re.compile(r"^Референтен номер:\s*\S+(?:\s+\S+)?\s*"),
    re.compile(r"^Отговорен брокер:\s*\S+(?:\s+\S+){0,1}\s*"),
]


def extract_description_alo(html):
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find("div", class_="obqva-block")
    if not node:
        return None
    text = node.get_text(" ", strip=True)
    for pat in _ALO_DESC_PREFIX_RES:
        text = pat.sub("", text)
    text = text.strip()
    return text or None


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
