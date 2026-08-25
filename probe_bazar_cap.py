"""
Diagnostic-only: round 2 for bazar.bg nationwide. Round 1 found:
- Both a bare nationwide URL (dropping the city segment) and per-city
  slugs (plovdiv/varna/burgas all resolved) work as real, distinct
  queries.
- Pages 1/10/20 return real, slightly different content (different
  lengths), but pages 30/50/80/120 all return byte-length-identical
  content (500093) - suggesting the site clamps out-of-range page numbers
  to its real last page instead of ever showing an empty page. If true,
  the existing scraper's "stop on empty page" logic would never fire and
  it would silently loop through every remaining page re-fetching the
  same last page.

This pins the exact boundary (pages 15-30) where content stops changing,
and confirms the clamp-to-last-page hypothesis by comparing the actual
listing ID sets on two "identical length" pages (30 vs 50) - if the ID
sets match exactly, it's a real clamp, not coincidentally-same-length
different content. Also checks whether querying a different city (Plovdiv)
after Sofia has already hit its plateau, in the same session, gets fresh
content (same "does slicing reset the cap" check every other portal
needed).

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests

BASE = "https://bazar.bg/obiavi/prodazhba-apartamenti"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}
LISTING_LINK_RE = re.compile(r"obiava-(\d+)")


def fetch_ids(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        ids = sorted(set(LISTING_LINK_RE.findall(r.text)))
        return r.status_code, ids, len(r.text)
    except Exception as e:
        return f"ERROR: {e}", [], 0


print("=== Part 1: pin down exact plateau boundary on Sofia (pages 15-30) ===")
prev_ids = None
plateau_page = None
for pnum in range(15, 31):
    url = f"{BASE}/sofia" if pnum == 1 else f"{BASE}/sofia?page={pnum}"
    status, ids, length = fetch_ids(url)
    same_as_prev = (ids == prev_ids)
    print(f"  page {pnum}: status={status} n_ids={len(ids)} len={length} same_as_prev_page={same_as_prev}")
    if same_as_prev and plateau_page is None:
        plateau_page = pnum
    prev_ids = ids
    time.sleep(1)
print(f"\nPlateau (identical listing set to previous page) starts around page {plateau_page}")

print("\n=== Part 2: are page 30 and page 50 the exact same listing set? ===")
_, ids30, _ = fetch_ids(f"{BASE}/sofia?page=30")
time.sleep(1)
_, ids50, _ = fetch_ids(f"{BASE}/sofia?page=50")
print(f"  page 30 ids == page 50 ids: {ids30 == ids50} (n={len(ids30)} vs {len(ids50)})")

print("\n=== Part 3: does a different city query (Plovdiv) get fresh content in the same session? ===")
for pnum in [1, 15, 25]:
    url = f"{BASE}/plovdiv" if pnum == 1 else f"{BASE}/plovdiv?page={pnum}"
    status, ids, length = fetch_ids(url)
    print(f"  Plovdiv page {pnum}: status={status} n_ids={len(ids)} len={length}")
    time.sleep(1)

print("\ndone")
