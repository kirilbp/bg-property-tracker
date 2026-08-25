"""
Diagnostic-only, round 2: round 1 confirmed locationId is a real settlement
id (1=Sofia offersCount=12351, 2=Plovdiv=7897, 3=Varna=8800, 4=Burgas=1879,
5=Ruse=220 - even most single big cities are still over the ~1000 depth
cap on their own) and that priceFrom/priceTo are real, working filter
params (searchCriteria echoed 'priceRanges' back, offersCount changed) -
unlike the other three param-name guesses, which were silently ignored.

This round:
  1. Confirms the depth cap is really about PAGE COUNT, not some other
     mechanism - paginates a slice with offersCount between 1000-2000
     (Sofia priced 0-100000, expected roughly ~2x the cap) and checks
     whether it still stops around page 50, and separately paginates a
     genuinely small slice (offersCount well under 1000) to confirm full
     pagination actually reaches the true end instead of being truncated.
  2. Probes the real nationwide ApartmentSell price distribution with a
     handful of band edges, to see how many bands (and how narrow) would
     be needed to keep every band under ~950 offers for full coverage.

Read-only, no commit step - deleted once the question is answered.
"""

import json
import re
import time

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


def offers_for(url):
    text = fetch(url)
    st = get_state(text)
    if not st:
        return None
    return st.get("data", {}).get("offers", {})


print("=== Part 1: does a narrow (well under 1000) slice paginate past page 50? ===")
# A random narrow nationwide price band, from round 1's own priceFrom/priceTo
# test pattern (already confirmed working).
url = f"{BASE_URL}/?locationId=0&typeId=ApartmentSell&priceFrom=95000&priceTo=97000"
offers = offers_for(url)
print(f"  slice offersCount = {offers.get('offersCount') if offers else 'N/A'}")

last_page_with_results = 0
for page in range(1, 80):
    params_url = f"{BASE_URL}/?locationId=0&typeId=ApartmentSell&priceFrom=95000&priceTo=97000&page={page}"
    text = fetch(params_url)
    st = get_state(text)
    if not st:
        print(f"  page {page}: no state")
        break
    offers = st.get("data", {}).get("offers", {})
    results = offers.get("result", [])
    print(f"  page {page}: {len(results)} results, hasMoreItems={offers.get('hasMoreItems')}")
    if results:
        last_page_with_results = page
    if not results or not offers.get("hasMoreItems"):
        break
    time.sleep(0.2)
print(f"  -> last page with real results: {last_page_with_results}")

print("\n=== Part 2: does a slice with offersCount ~1000-2000 still cap around page 50? ===")
url = f"{BASE_URL}/?locationId=1&typeId=ApartmentSell&priceFrom=0&priceTo=100000"
offers = offers_for(url)
print(f"  Sofia 0-100000 EUR offersCount = {offers.get('offersCount') if offers else 'N/A'}")
last_page = 0
for page in range(1, 60):
    params_url = f"{BASE_URL}/?locationId=1&typeId=ApartmentSell&priceFrom=0&priceTo=100000&page={page}"
    text = fetch(params_url)
    st = get_state(text)
    if not st:
        break
    offers = st.get("data", {}).get("offers", {})
    results = offers.get("result", [])
    if results:
        last_page = page
    if not results or not offers.get("hasMoreItems"):
        print(f"  stopped at page {page}: {len(results)} results, hasMoreItems={offers.get('hasMoreItems')}")
        break
    time.sleep(0.2)
print(f"  -> last page with real results: {last_page}")

print("\n=== Part 3: nationwide ApartmentSell price distribution (band edges) ===")
BANDS = [0, 20000, 40000, 60000, 80000, 100000, 130000, 160000, 200000, 250000,
         300000, 400000, 500000, 700000, 1000000, None]
for i in range(len(BANDS) - 1):
    lo, hi = BANDS[i], BANDS[i + 1]
    if hi is None:
        url = f"{BASE_URL}/?locationId=0&typeId=ApartmentSell&priceFrom={lo}"
        label = f"{lo}+"
    else:
        url = f"{BASE_URL}/?locationId=0&typeId=ApartmentSell&priceFrom={lo}&priceTo={hi}"
        label = f"{lo}-{hi}"
    offers = offers_for(url)
    print(f"  {label} EUR -> offersCount={offers.get('offersCount') if offers else 'N/A'}")
    time.sleep(0.2)
