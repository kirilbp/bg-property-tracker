"""
Diagnostic-only, round 7 (likely final): round 6 found the full type
catalog hardcoded in the client bundle:
  n = {APARTMENT_SALE:"ApartmentSell", APARTMENT_RENT:"ApartmentRent",
       HOUSE_SALE:"HouseSell", HOUSE_RENT:"HouseRent",
       LAND_PARCEL:"LandParcel", LAND_AGRO:"LandAgro",
       PREFIX_APARTMENT_SALE:"as", ..., PREFIX_HOUSE_SALE:"hs", ...}
  o = {ApartmentSell:"as", ApartmentRent:"ar", HouseSell:"hs",
       HouseRent:"hr", LandParcel:"lp", LandAgro:"la"}

homes.bg has ONLY 4 real-estate types total (apartment/house/land-parcel/
land-agro, each sale or rent) - no office/shop/garage/warehouse exist on
this portal at all, unlike imoti.bg. For-sale scope needs: ApartmentSell
(already scraped), HouseSell, LandParcel, LandAgro.

Round 4's blind "type=<2-letter-code>" query param guess was a no-op
(always fell back to ApartmentSell) - but round 4 guessed made-up 2-letter
codes (hs/ls/os/...) for categories that don't exist. Now that the real
business names and their real short prefixes are confirmed, this round
tries the actual candidates directly against the nationwide URL
(?locationId=0): both the full PascalCase name and the real 2-letter
prefix, as both "type=" and "typeId=" (typeId is the real attributeName
seen in the form-config dump), to find which (param name, value format)
pair actually changes searchCriteria away from ApartmentSell.

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


CANDIDATES = ["HouseSell", "LandParcel", "LandAgro", "hs", "lp", "la"]
PARAM_NAMES = ["type", "typeId"]

for param in PARAM_NAMES:
    print(f"\n=== param name: {param} ===")
    for val in CANDIDATES:
        url = f"{BASE_URL}/?locationId=0&{param}={val}"
        try:
            text = fetch(url)
        except requests.RequestException as e:
            print(f"  {param}={val} -> FAILED: {e}")
            continue
        st = get_state(text)
        if not st:
            print(f"  {param}={val} -> no state found")
            continue
        offers = st.get("data", {}).get("offers", {})
        print(f"  {param}={val} -> searchCriteria={offers.get('searchCriteria')} offersCount={offers.get('offersCount')}")

# Also: does homes.bg have a dedicated path per type, built from the
# PascalCase business name rather than a slug guess (e.g. /HouseSell/ or
# a lowercase/dasherized variant)?
print("\n=== path-based guesses using the real business names ===")
PATH_CANDIDATES = ["HouseSell", "housesell", "house-sell", "LandParcel", "land-parcel", "LandAgro", "land-agro"]
for slug in PATH_CANDIDATES:
    url = f"{BASE_URL}/{slug}/?locationId=0"
    try:
        text = fetch(url)
    except requests.RequestException as e:
        print(f"  /{slug}/ -> FAILED: {e}")
        continue
    st = get_state(text)
    if not st:
        print(f"  /{slug}/ -> no state found")
        continue
    offers = st.get("data", {}).get("offers", {})
    print(f"  /{slug}/ -> searchCriteria={offers.get('searchCriteria')} offersCount={offers.get('offersCount')}")
