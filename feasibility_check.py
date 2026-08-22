"""
Investigate imoti.net's pagination structure for the Sofia sale-listings
search (scraper.py), and find the site's own stated total listing count so
we can verify a pagination fix against it. scraper.py currently only
fetches SEARCH_URL once with no pagination loop at all.
"""

import re
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.imoti.net/en/obiavi/r/prodava/sofia"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}


def main():
    resp = requests.get(SEARCH_URL, headers=HEADERS, timeout=20)
    print("status:", resp.status_code)
    html = resp.text
    print("html length:", len(html))
    soup = BeautifulSoup(html, "html.parser")

    body_text = soup.get_text(" ", strip=True)
    for m in re.finditer(r"[\d][\d\s,]{1,8}\s?(results|listings|obiavi|offers|imots?|properties)", body_text, re.IGNORECASE):
        print("COUNT CANDIDATE:", repr(body_text[max(0, m.start()-40):m.end()+10]))

    print("\n--- pagination-related links ---")
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if re.search(r"page|/r/prodava/sofia/\d|str=", href, re.IGNORECASE) or re.fullmatch(r"\d{1,4}", text):
            if href not in seen:
                seen.add(href)
                print(repr(href), "|", repr(text[:40]))

    print("\n--- elements with class/id containing 'pag' ---")
    for el in soup.select("[class*=pag], [id*=pag]")[:5]:
        print(str(el)[:400])
        print("---")

    listing_link_re = re.compile(r"^/en/obiava/prodava[^\"'#]*?/(\d+)/")
    listing_links = [a for a in soup.find_all("a", href=True) if listing_link_re.search(a["href"])]
    ids = set()
    for a in listing_links:
        m = listing_link_re.search(a["href"])
        ids.add(m.group(1))
    print("\nunique listing IDs on page 1:", len(ids))


if __name__ == "__main__":
    main()
