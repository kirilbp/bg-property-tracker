"""
Diagnostic-only, round 4: round 3 found each listing in
data.offers.result[] carries its own short internal type code
("type": "as" for every Sofia-apartment result seen so far - likely
"a"=apartment/"s"=sell). Nav <a href> and <select> weren't present in the
raw HTML at all (homepage is client-rendered post-hydration for those),
so the type selector isn't discoverable that way. This round:

  1. Dumps the full top-level shape of __PRELOADED_STATE__.data (one and
     two levels deep) to find any criteria/menu/location option list that
     enumerates the other type codes ("hs", "ls", "os", "ms", "gs", ...?).
  2. Greps the whole raw HTML for the other known "*Sell" business names
     (HouseSell, PlotSell/LandSell, OfficeSell, ShopSell, GarageSell,
     WarehouseSell) as literal substrings, in case they appear outside the
     single searchCriteria dict already found (e.g. in an inline i18n
     dictionary).
  3. Tries the two-letter code straight as a query param against the
     already-confirmed-working nationwide URL (?locationId=0), guessing
     the param name is "type" since that's the key name found on each
     result object: /?locationId=0&type=hs (and the other 5 plausible
     codes), reading back offersCount + searchCriteria each time.

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


html = fetch(BASE_URL + "/?locationId=0")
state = get_state(html)

print("=== top-level state.data keys ===")
if state:
    data = state.get("data", {})
    print(" ", sorted(data.keys()))
    print("\n=== two levels deep (dict/list keys only) ===")
    for k, v in data.items():
        if isinstance(v, dict):
            print(f"  data.{k} (dict) keys = {sorted(v.keys())}")
        elif isinstance(v, list):
            print(f"  data.{k} (list) len={len(v)} first_item_type={type(v[0]).__name__ if v else None}")
            if v and isinstance(v[0], dict):
                print(f"    first item keys = {sorted(v[0].keys())}")
else:
    print("  no state found")

print("\n=== literal search for other *Sell business names in raw HTML ===")
for name in ["HouseSell", "PlotSell", "LandSell", "OfficeSell", "ShopSell", "GarageSell", "WarehouseSell", "CommercialSell"]:
    count = html.count(name)
    print(f"  {name}: {count} occurrence(s)")

print("\n=== trying type= query param with guessed short codes (nationwide) ===")
for code in ["hs", "ls", "os", "ms", "gs", "ws", "cs", "h", "l", "o", "m", "g"]:
    url = f"{BASE_URL}/?locationId=0&type={code}"
    try:
        text = fetch(url)
    except requests.RequestException as e:
        print(f"  type={code} -> FAILED: {e}")
        continue
    st = get_state(text)
    if not st:
        print(f"  type={code} -> no state found")
        continue
    offers = st.get("data", {}).get("offers", {})
    print(f"  type={code} -> searchCriteria={offers.get('searchCriteria')} offersCount={offers.get('offersCount')}")
