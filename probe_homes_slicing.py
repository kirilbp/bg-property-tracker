"""
Diagnostic-only, round 3: rounds 1-2 confirmed locationId is a real
settlement id, priceFrom/priceTo are real working filter params, and -
crucially - a slice with offersCount under the ~1000 depth cap paginates
cleanly to its true end (631-result and 391-result test slices both
stopped on a real partial last page with hasMoreItems=False, not an
artificial page-49 cutoff). Round 2 also mapped the real nationwide
ApartmentSell price distribution: it's heavily skewed, several 20-50k-wide
bands (e.g. 100000-130000 EUR alone) already exceed 7,000 listings - a
flat band scheme isn't nearly fine-grained enough in the dense middle of
the market.

This round recursively bisects the price range for each of the 4 real
homes.bg types: start from the full [0, 1000000] range (round 2 showed
the 1000000+ tail is already small - 108 listings - so no bisection
needed above that), keep splitting any slice whose offersCount exceeds
the safety threshold until every leaf slice is under it, then sum every
leaf's offersCount to get the real total retrievable via full slicing -
compared directly against each type's already-known unsliced total.

Read-only, no commit step - deleted once the question is answered.
"""

import json
import re
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.homes.bg"
STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)

THRESHOLD = 900  # safety margin under the ~1000 depth cap
MAX_PRICE = 1_000_000  # round 2: 1000000+ tail is already small (108) for ApartmentSell
MAX_DEPTH = 12
REQUEST_COUNT = 0


def fetch(url):
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def get_state(html):
    m = STATE_RE.search(html)
    return json.loads(m.group(1)) if m else None


def offers_count(type_id, lo, hi):
    if hi is None:
        url = f"{BASE_URL}/?locationId=0&typeId={type_id}&priceFrom={lo}"
    else:
        url = f"{BASE_URL}/?locationId=0&typeId={type_id}&priceFrom={lo}&priceTo={hi}"
    st = get_state(fetch(url))
    if not st:
        return 0
    return st.get("data", {}).get("offers", {}).get("offersCount", 0) or 0


def bisect(type_id, lo, hi, depth=0):
    """Returns a list of (lo, hi, count) leaf slices, each under THRESHOLD."""
    count = offers_count(type_id, lo, hi)
    if count <= THRESHOLD or depth >= MAX_DEPTH or hi - lo < 500:
        return [(lo, hi, count)]
    mid = lo + (hi - lo) // 2
    return bisect(type_id, lo, mid, depth + 1) + bisect(type_id, mid, hi, depth + 1)


for type_id, unsliced_known_total in [
    ("ApartmentSell", 44111),
    ("HouseSell", 9625),
    ("LandParcel", 13406),
    ("LandAgro", 2115),
]:
    print(f"\n=== {type_id} ===")
    tail_count = offers_count(type_id, MAX_PRICE, None)
    print(f"  {MAX_PRICE}+ tail: {tail_count} (already under threshold: {tail_count <= THRESHOLD})")

    leaves = bisect(type_id, 0, MAX_PRICE)
    over_threshold = [l for l in leaves if l[2] > THRESHOLD]
    total = sum(l[2] for l in leaves) + tail_count
    print(f"  leaf slices: {len(leaves)} (+ 1 tail slice)")
    print(f"  leaf slices still over threshold after max depth: {len(over_threshold)} {over_threshold[:5]}")
    print(f"  SUM of all leaf offersCounts = {total}  (vs unsliced type total ~{unsliced_known_total})")
    print(f"  requests used so far (cumulative): {REQUEST_COUNT}")
    time.sleep(0.3)

print(f"\n=== total requests used by this probe: {REQUEST_COUNT} ===")
