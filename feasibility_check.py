"""
Investigate alo.bg's pagination structure for the Sofia apartments-for-sale
search (scraper_alo.py), and find the site's own stated total listing count.
scraper_alo.py currently only fetches SEARCH_URL once with no pagination
loop at all.
"""

import re
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}


def main():
    resp = requests.get(SEARCH_URL, headers=HEADERS, timeout=20)
    print("status:", resp.status_code)
    html = resp.text
    print("html length:", len(html))
    soup = BeautifulSoup(html, "html.parser")

    body_text = soup.get_text(" ", strip=True)
    for m in re.finditer(r"[\d][\d\s,]{1,8}\s?(резултат[а-я]*|обяви|resultat[a-z]*)", body_text, re.IGNORECASE):
        print("COUNT CANDIDATE:", repr(body_text[max(0, m.start()-40):m.end()+10]))

    print("\n--- pagination-related links ---")
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if re.search(r"page|str=|/p/\d|p=\d", href, re.IGNORECASE) or re.fullmatch(r"\d{1,4}", text):
            if href not in seen:
                seen.add(href)
                print(repr(href), "|", repr(text[:40]))

    print("\n--- elements with class/id containing 'pag' ---")
    for el in soup.select("[class*=pag], [id*=pag]")[:6]:
        print(str(el)[:400])
        print("---")

    listing_link_re = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
    listing_links = [a for a in soup.find_all("a", href=True) if listing_link_re.search(a["href"])]
    ids = set()
    for a in listing_links:
        m = listing_link_re.search(a["href"])
        ids.add(m.group(1))
    print("\nunique listing IDs on page 1:", len(ids))


if __name__ == "__main__":
    main()
