"""
Diagnose why scraper_alo.py's smallest_container_with_price() fails for the
vast majority of alo.bg listings (only ~1-4 out of ~30 unique listings per
page succeed, per DEBUG output from the live pagination test). For each of
the first several failing listing links, print the price-mention count and
text length at each ancestor level up to 10 levels, to see whether it's a
too-low max_levels, a regex mismatch, or something else.
"""

import re
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}

LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
PRICE_RE = re.compile(r"Цена:\s*([\d\s]+)\s?€")
MAX_CARD_TEXT_LENGTH = 1500


def main():
    resp = requests.get(SEARCH_URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
    print("total matching links:", len(matching_links))

    seen_ids = set()
    diagnosed = 0
    for a in matching_links:
        listing_id = LISTING_LINK_RE.search(a["href"]).group(1)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)

        node = a
        print(f"\n=== listing {listing_id} (href={a['href']!r}) ===")
        for level in range(1, 11):
            if node.parent is None:
                print(f"  level {level}: no parent, stopping")
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            matches = PRICE_RE.findall(text)
            print(f"  level {level}: tag={node.name} price_matches={len(matches)} text_len={len(text)} "
                  f"ok={1 <= len(matches) <= 1 and len(text) <= MAX_CARD_TEXT_LENGTH}")
            if len(matches) >= 1:
                print(f"    matched price(s): {matches}")

        diagnosed += 1
        if diagnosed >= 4:
            break


if __name__ == "__main__":
    main()
