"""
Investigate bazar.bg's pagination completeness for the Sofia
apartments-for-sale category (scraper_bazar.py). MAX_PAGES is currently
hard-capped at 3 with a "stop on empty page" fallback - check whether real
listings continue past page 3, and any stated total count.
"""

import re
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}
LISTING_LINK_RE = re.compile(r"obiava-(\d+)")


def check_page(page_num):
    url = SEARCH_URL if page_num == 1 else f"{SEARCH_URL}?page={page_num}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = [a for a in soup.find_all("a", href=True) if LISTING_LINK_RE.search(a["href"])]
    ids = {LISTING_LINK_RE.search(a["href"]).group(1) for a in links}
    print(f"page {page_num}: status={resp.status_code} raw_links={len(links)} unique_ids={len(ids)}")

    if page_num == 1:
        body_text = soup.get_text(" ", strip=True)
        for m in re.finditer(r"[\d][\d\s,]{1,8}\s?(обяви|резултат[а-я]*)", body_text, re.IGNORECASE):
            print("COUNT CANDIDATE:", repr(body_text[max(0, m.start()-40):m.end()+10]))
        pag_links = set()
        for a in soup.find_all("a", href=True):
            if re.search(r"page=\d", a["href"]):
                pag_links.add(a["href"])
        print("pagination links found:", sorted(pag_links))

    return len(ids)


def main():
    for page_num in range(1, 8):
        count = check_page(page_num)
        if count == 0:
            print(f"page {page_num} empty, stopping")
            break


if __name__ == "__main__":
    main()
