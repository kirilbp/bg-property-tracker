"""
Diagnostic-only, round 2: round 1 found the real nationwide mechanism
(?locationId=0 drops the city filter entirely - confirmed live,
offersCount jumped from 12,351 Sofia-only to 44,111, first result a real
non-Sofia city). Still open: "ApartmentSell" stays in searchCriteria even
with ?locationId=0, meaning results are still apartment-only - need the
real property-type selector mechanism before rewriting scraper_homes.py
for all 6 categories, not just flats.

Searches the raw homepage HTML (not just the parsed state) for the site's
own type-selector markup - dropdown <option> values, data- attributes, or
JS-visible route definitions - to find what "HouseSell"/"LandSell"-style
alternates to "ApartmentSell" actually look like as real URL/param values,
rather than guessing blindly.

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


# --- Part 1: scan the raw homepage HTML for type-selector hints ------------
print("=== scanning raw homepage HTML for type-selector hints ===")
html = fetch(BASE_URL + "/")

# Look for any of the known Bulgarian property-type words near an href,
# option value, or data attribute - captures ~80 chars of context each.
TYPE_WORDS = ["апартамент", "къща", "парцел", "офис", "магазин", "гараж", "склад"]
for word in TYPE_WORDS:
    for m in re.finditer(re.escape(word), html, re.IGNORECASE):
        start = max(0, m.start() - 60)
        end = min(len(html), m.end() + 20)
        snippet = html[start:end].replace("\n", " ")
        if "href" in snippet or "value=" in snippet or "data-" in snippet or "/" in snippet:
            print(f"  [{word}] ...{snippet}...")
            break  # one example per word is enough

# Look for any script-embedded route/type map (e.g. a JS object listing
# every "Sell"-suffixed key alongside a URL segment or numeric id).
for m in re.finditer(r'"[A-Za-z]+Sell"\s*:\s*"[^"]*"', html):
    print("  Sell-key match:", m.group(0))

# --- Part 2: try candidate type-scoped URL segments -------------------------
print("\n=== candidate type-scoped URLs (with ?locationId=0 for nationwide) ===")
CANDIDATES = [
    "kashti", "kushti", "houses", "parceli", "zemya", "ofisi", "office",
    "magazini", "garaji", "skladove", "imoti",
]
for slug in CANDIDATES:
    url = f"{BASE_URL}/{slug}/?locationId=0"
    try:
        text = fetch(url)
    except requests.RequestException as e:
        print(f"  /{slug}/?locationId=0 -> FAILED: {e}")
        continue
    m = STATE_RE.search(text)
    if not m:
        print(f"  /{slug}/?locationId=0 -> no state found")
        continue
    state = json.loads(m.group(1))
    offers = state.get("data", {}).get("offers", {})
    print(f"  /{slug}/?locationId=0 -> searchCriteria={offers.get('searchCriteria')} offersCount={offers.get('offersCount')}")
