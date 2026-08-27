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

    def geocode(self, query):
        query = _clean_query(query or "")
        if not query:
            return None
        if query in self.cache:
            return self.cache[query]
        time.sleep(NOMINATIM_DELAY_SECONDS)
        result = None
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": GEOCODE_USER_AGENT},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            if data:
                result = {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        except Exception as e:
            print(f"DEBUG: geocode failed for {query!r}: {e}")
        self.cache[query] = result
        self._dirty = True
        return result

    def save(self):
        if self._dirty:
            CACHE_FILE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
            self._dirty = False
