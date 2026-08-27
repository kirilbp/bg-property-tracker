"""
One-shot live diagnostic: why does imoti.bg only yield ~800 listings
nationwide when imoti.net (a differently-named, comparably-sized portal)
yields ~25,000? Checks whether our SEARCH_URL/pagination genuinely reaches
the site's real end of results, or stops early due to a misread signal -
same look-at-the-real-page-before-guessing discipline used throughout this
project's nationwide rollout.
"""
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://imoti.bg"
SEARCH_URL = "https://imoti.bg/продажби/cu:BGN"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}
LISTING_LINK_RE = re.compile(r"/продажби/([^/]+)/([^/]+)/([^/]+)-(\d{5,})\.htm")

print("=== Checking page 1 for a results-count indicator ===")
r = requests.get(SEARCH_URL, headers=HEADERS, timeout=20)
print("status:", r.status_code, "len:", len(r.text))
soup = BeautifulSoup(r.text, "html.parser")
text = soup.get_text(" ", strip=True)
for m in re.finditer(r"(\d[\d\s]{2,9})\s*(обяви|резултат)", text, re.IGNORECASE):
    print("count-like match:", repr(m.group(0)))

links_p1 = set(a["href"] for a in soup.find_all("a", href=True) if LISTING_LINK_RE.search(a["href"]))
print("unique listing links on page 1:", len(links_p1))

print()
print("=== Walking pages until 2 consecutive empty/short pages ===")
seen = set()
empty_streak = 0
for page in range(1, 60):
    url = SEARCH_URL if page == 1 else f"{SEARCH_URL}/page:{page}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    s = BeautifulSoup(resp.text, "html.parser")
    links = set(a["href"] for a in s.find_all("a", href=True) if LISTING_LINK_RE.search(a["href"]))
    new_ids = set()
    for href in links:
        m = LISTING_LINK_RE.search(href)
        new_ids.add(m.group(4))
    before = len(seen)
    seen |= new_ids
    print(f"page {page}: status={resp.status_code} raw_links={len(links)} new_ids={len(seen)-before} cum_total={len(seen)}")
    if len(links) == 0:
        empty_streak += 1
        if empty_streak >= 2:
            print(f"--> stopped: 2 consecutive empty pages at page {page}")
            break
    else:
        empty_streak = 0

print()
print("FINAL unique listing ids found across walked pages:", len(seen))

print()
print("=== Sanity: try a known high-volume city-specific URL variant ===")
for slug in ("softия", "софия"):
    pass  # placeholder, real check below

test_urls = [
    "https://imoti.bg/продажби",
    "https://imoti.bg/продажби/апартамент",
]
for u in test_urls:
    try:
        rr = requests.get(u, headers=HEADERS, timeout=20)
        ss = BeautifulSoup(rr.text, "html.parser")
        ll = set(a["href"] for a in ss.find_all("a", href=True) if LISTING_LINK_RE.search(a["href"]))
        print(u, "-> status", rr.status_code, "links", len(ll))
    except Exception as e:
        print(u, "-> ERROR", e)
