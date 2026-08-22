"""
Investigate homes.bg's pagination completeness. scraper_homes.py already
paginates via ?page=N and respects the API's own hasMoreItems flag, but
caps at PAGES_TO_FETCH=2 regardless. Check hasMoreItems/totalItems across
several pages to see whether real results continue past page 2.
"""

import json
import re
import requests

BASE_URL = "https://www.homes.bg"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)


def check_page(page):
    url = BASE_URL + ("/" if page == 1 else f"/?page={page}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    match = STATE_RE.search(resp.text)
    if not match:
        print(f"page {page}: no __PRELOADED_STATE__ found, status={resp.status_code}")
        return None
    state = json.loads(match.group(1))
    offers = state.get("data", {}).get("offers", {})
    results = offers.get("result", [])
    has_more = offers.get("hasMoreItems")
    total = offers.get("totalItems") or offers.get("total") or offers.get("count")
    print(f"page {page}: results={len(results)} hasMoreItems={has_more} totalItems={total} "
          f"other_offer_keys={list(offers.keys())}")
    return has_more


def main():
    for page in range(1, 8):
        has_more = check_page(page)
        if has_more is False:
            print(f"stopped at page {page}: hasMoreItems is False")
            break


if __name__ == "__main__":
    main()
