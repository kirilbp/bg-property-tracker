"""
Round 3: print the raw text of alo.bg's "listvip-item" card (the template
used on paginated pages, page 2+) to find out what price format it actually
uses, since it doesn't match the "Цена: X €" pattern that page 1's
"listtop-item" cards use.
"""

import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342&page=5"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}

LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")


def main():
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")

    vip_items = soup.select(".listvip-item")
    print("listvip-item count:", len(vip_items))

    for item in vip_items[:3]:
        print("\n=== raw text of one listvip-item ===")
        print(repr(item.get_text(" ", strip=True))[:800])
        print("\n--- outer HTML (first 1500 chars) ---")
        print(str(item)[:1500])
        print("\n")


if __name__ == "__main__":
    main()
