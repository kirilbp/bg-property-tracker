"""
Diagnostic-only: the production imoti.bg scraper (nationwide, all categories,
no MAX_PAGES cap - stop condition is a genuinely empty page) currently
returns 801 total listings, far fewer than the other nationwide-eligible
portals even though it should now cover all of Bulgaria. Its own docstring
notes it was picked first *because* it was the smallest portal (71 Sofia
listings pre-conversion), so 801 nationwide might be a real, small total -
or pagination might be stopping early for some other reason (a site-side
depth cap like homes.bg's, or request failures being silently treated as
"no more listings", the same failure mode already fixed elsewhere).

This checks: (1) whether the site's own search-results page displays a
total-count figure anywhere, to compare against 801, and (2) fetches deep
page numbers directly (not sequential) past where the real scraper would
have stopped, to see whether they come back genuinely empty (confirming
801 is real) or whether something else is going on (blocked / wrong
content / a differently-shaped page).

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}
SEARCH_URL = "https://imoti.bg/продажби/cu:BGN"
LISTING_LINK_RE = re.compile(r"/продажби/([^/]+)/([^/]+)/([^/]+)-(\d{5,})\.htm")


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    return resp


print("=== page 1: looking for a site-reported total count ===")
resp = fetch(SEARCH_URL)
print(f"status={resp.status_code} len={len(resp.text)}")
soup = BeautifulSoup(resp.text, "html.parser")
text = soup.get_text(" ", strip=True)
for m in re.finditer(r"([\d\s]{2,7})\s*(обяви|резултат|имот[аи]?)", text, re.IGNORECASE):
    print(f"  candidate total-count text: {m.group(0)!r}")
links_p1 = {m.group(4) for a in soup.find_all("a", href=True) for m in [LISTING_LINK_RE.search(a["href"])] if m}
print(f"  distinct listing ids on page 1: {len(links_p1)}")

print("\n=== deep page probe ===")
for page in [20, 27, 30, 35, 40, 50, 80, 120]:
    url = f"{SEARCH_URL}/page:{page}"
    try:
        resp = fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        ids = {m.group(4) for a in soup.find_all("a", href=True) for m in [LISTING_LINK_RE.search(a["href"])] if m}
        print(f"  page {page}: status={resp.status_code} len={len(resp.text)} distinct listing ids={len(ids)}")
    except requests.RequestException as e:
        print(f"  page {page}: REQUEST FAILED: {e}")
    time.sleep(1)

print("\ndone")
