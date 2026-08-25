"""
Diagnostic-only: homes.bg's homepage embeds window.__PRELOADED_STATE__ with
an explicit searchCriteria object ({"ApartmentSell": "...", "locationId":
"София"}) even when the URL itself carries no query params - confirmed in
an earlier round of diagnostics. Before rewriting scraper_homes.py for the
nationwide expansion, need to find the real mechanism for "all of Bulgaria,
all property types" - guessing at URL params risks silently still scraping
Sofia-apartments-only under a different-looking URL.

Tries several candidate approaches: common query param names guessed from
the searchCriteria keys themselves (locationId, type), a plain "clear all
filters" style empty-criteria URL, and inspecting the state object's own
shape for a hint of what a "no filter" criteria value looks like (None?
0? empty string?) by checking if any field in the state describes
available location/type options.

Read-only, no commit step - deleted once the question is answered.
"""

import json
import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.homes.bg"
STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)


def dump_state(url, label):
    print(f"\n=== {label}: {url} ===")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  FAILED: {e}")
        return None
    m = STATE_RE.search(resp.text)
    if not m:
        print("  no __PRELOADED_STATE__ found")
        return None
    state = json.loads(m.group(1))
    offers = state.get("data", {}).get("offers", {})
    print(f"  searchCriteria: {json.dumps(offers.get('searchCriteria'), ensure_ascii=False)}")
    print(f"  offersCount: {offers.get('offersCount')}")
    print(f"  result length: {len(offers.get('result', []))}")
    if offers.get("result"):
        first = offers["result"][0]
        print(f"  first result location: {first.get('location')!r} title: {first.get('title')!r}")
    # Dump top-level state keys and any "filters"/"criteria"/"location" - ish
    # keys anywhere in data, to find the real filter-options shape.
    data = state.get("data", {})
    print(f"  top-level data keys: {list(data.keys())}")
    for k in data.keys():
        if any(w in k.lower() for w in ("filter", "criteria", "location", "type", "category")):
            v = data[k]
            snippet = json.dumps(v, ensure_ascii=False)[:300] if not isinstance(v, str) else v[:300]
            print(f"  data[{k!r}] = {snippet}")
    return state


# Candidate URLs: common query param names guessed from the searchCriteria
# object's own keys, plus a couple of plausible "all Bulgaria"/"all types"
# path conventions seen on other BG portals.
CANDIDATES = [
    ("bare homepage (known default: Sofia apartments)", BASE_URL + "/"),
    ("?locationId=0", BASE_URL + "/?locationId=0"),
    ("?location=0", BASE_URL + "/?location=0"),
    ("?locationId=", BASE_URL + "/?locationId="),
    ("/api/offers (guess)", BASE_URL + "/api/offers"),
    ("/en/ (English homepage, may differ)", BASE_URL + "/en/"),
    ("/prodazhbi/ (guess)", BASE_URL + "/prodazhbi/"),
    ("?type=0", BASE_URL + "/?type=0"),
]

for label, url in CANDIDATES:
    dump_state(url, label)
