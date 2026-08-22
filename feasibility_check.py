"""
Round 2: compare alo.bg's page 1 (default, no &page= param) vs a later
&page=N page's DOM structure for the same listing-card extraction logic,
to see whether they differ - page 1 succeeded at level 2 in round 1, but
the real scraper's paginated runs (page 2+) showed massive container-fail
rates.
"""

import re
import requests
from bs4 import BeautifulSoup

BASE_SEARCH_URL = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}

LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
PRICE_RE = re.compile(r"Цена:\s*([\d\s]+)\s?€")
MAX_CARD_TEXT_LENGTH = 1500


def diagnose(url, label):
    print(f"\n\n##### {label}: {url} #####")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    print("status:", resp.status_code, "html length:", len(resp.text))
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
        for level in range(1, 8):
            if node.parent is None:
                print(f"  level {level}: no parent, stopping")
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            matches = PRICE_RE.findall(text)
            ok = 1 <= len(matches) <= 1 and len(text) <= MAX_CARD_TEXT_LENGTH
            print(f"  level {level}: tag={node.name} class={node.get('class')} price_matches={len(matches)} text_len={len(text)} ok={ok}")
            if ok:
                break

        diagnosed += 1
        if diagnosed >= 3:
            break


def main():
    diagnose(BASE_SEARCH_URL, "page 1 (no param)")
    diagnose(f"{BASE_SEARCH_URL}&page=5", "page 5 (paginated)")


if __name__ == "__main__":
    main()
