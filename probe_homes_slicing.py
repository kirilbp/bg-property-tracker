"""
Diagnostic-only: the real nationwide run (see git history for the earlier
homes.bg rounds) found every property type's pagination stops at exactly
page 49 (980-1000 results, always a full 20-item page right up to the
cutoff) regardless of the much larger offersCount each type reports
(44,111 for ApartmentSell alone) - a site-side pagination depth cap, not
a scraper bug or a natural end-of-results. This probes whether slicing
each type's query into narrower pieces (by city/region, then by price
band) gets under that ~1,000 cap per slice, so full pagination inside
each slice reaches the real end of results instead of being truncated -
and if so, what the real total retrievable count looks like versus the
~4,000 the unsliced run got.

Three parts:
  1. Find real locationId values for specific cities/regions (not just
     the already-confirmed 0=nationwide) - reads the client JS bundle for
     any embedded location list, and separately tries the homepage's own
     default (no query params = Sofia) to see what id that resolves to.
  2. For a couple of candidate locationId values (if found) plus the
     already-confirmed nationwide (0), check whether adding a price-range
     query works at all (tries common param name guesses) and whether it
     changes offersCount - if so, price-band slicing is viable even
     without solving location slicing.
  3. Report offersCount for each tested slice, so the real "would narrower
     slicing help" question has real numbers behind it.

Read-only, no commit step - deleted once the question is answered.
"""

import json
import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.homes.bg"
STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def get_state(html):
    m = STATE_RE.search(html)
    return json.loads(m.group(1)) if m else None


print("=== Part 1: default (Sofia) homepage - what locationId does it use? ===")
html = fetch(BASE_URL + "/")
st = get_state(html)
if st:
    offers = st.get("data", {}).get("offers", {})
    print(f"  default searchCriteria={offers.get('searchCriteria')} offersCount={offers.get('offersCount')}")
# Look for any location-related id near the criteria in the raw HTML/state dump
loc_matches = re.findall(r'"locationId"\s*:\s*"?(\w+)"?', html)
print(f"  raw locationId occurrences in HTML: {set(loc_matches)}")

print("\n=== Part 1b: scan client bundle for a location/city/region list ===")
scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
LOC_WORD_RE = re.compile(r'"(софия|пловдив|варна|бургас|русе|стара загора|плевен)"', re.IGNORECASE)
for s in scripts:
    url = s if s.startswith("http") else (BASE_URL + s if s.startswith("/") else f"{BASE_URL}/{s}")
    try:
        js = fetch(url)
    except requests.RequestException as e:
        print(f"  FAILED to fetch {url}: {e}")
        continue
    hits = LOC_WORD_RE.findall(js)
    if hits:
        print(f"  {url}: city-name hits = {set(hits)}")
        # print ~150 chars of context around the first hit of each unique city name
        seen = set()
        for m in LOC_WORD_RE.finditer(js):
            city = m.group(1).lower()
            if city in seen:
                continue
            seen.add(city)
            start = max(0, m.start() - 100)
            end = min(len(js), m.end() + 60)
            print(f"    [{city}] ...{js[start:end]}...")

print("\n=== Part 2: try candidate locationId values directly (guessing small ints) ===")
for loc_id in ["1", "2", "3", "4", "5", "39", "41"]:
    url = f"{BASE_URL}/?locationId={loc_id}&typeId=ApartmentSell"
    try:
        text = fetch(url)
    except requests.RequestException as e:
        print(f"  locationId={loc_id} -> FAILED: {e}")
        continue
    st = get_state(text)
    if not st:
        print(f"  locationId={loc_id} -> no state found")
        continue
    offers = st.get("data", {}).get("offers", {})
    print(f"  locationId={loc_id} -> searchCriteria={offers.get('searchCriteria')} offersCount={offers.get('offersCount')}")

print("\n=== Part 3: try price-range query param guesses (nationwide apartments) ===")
PRICE_PARAM_GUESSES = [
    {"priceFrom": "50000", "priceTo": "100000"},
    {"price_from": "50000", "price_to": "100000"},
    {"minPrice": "50000", "maxPrice": "100000"},
    {"priceMin": "50000", "priceMax": "100000"},
]
for params in PRICE_PARAM_GUESSES:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/?locationId=0&typeId=ApartmentSell&{qs}"
    try:
        text = fetch(url)
    except requests.RequestException as e:
        print(f"  {qs} -> FAILED: {e}")
        continue
    st = get_state(text)
    if not st:
        print(f"  {qs} -> no state found")
        continue
    offers = st.get("data", {}).get("offers", {})
    print(f"  {qs} -> searchCriteria={offers.get('searchCriteria')} offersCount={offers.get('offersCount')}")
