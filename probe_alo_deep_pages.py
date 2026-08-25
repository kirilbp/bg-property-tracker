"""
Diagnostic-only: round 2 for alo.bg nationwide. Round 1 found dropping the
location filter (region_id/location_ids) jumps the site's own stated total
from ~10,009 (Sofia) to ~80,424 (nationwide apartments), with no HTTP-level
block through page 330 - but that's still far short of the ~2,681 pages
80,424 listings would need at 30/page, and round 1's listing-link count was
broken (raw-text regex, not per-<a href> matching, so always read 0).

This fixes the count (matches each real <a href> like the actual scraper
does) and pages deeper - up to ~2700 - watching for either a hard block
(403/etc) or real content quietly drying up short of where the site's own
80,424 claim would predict, the same way homes.bg's per-page-49 cap and
imoti.net's per-page-200 cap were both found by paging past where a flat
MAX_PAGES assumption would have stopped looking.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/"
LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")


def check(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = [a for a in soup.find_all("a", href=True) if LISTING_LINK_RE.search(a["href"])]
        return resp.status_code, len(links), len(resp.text)
    except requests.RequestException as e:
        return f"ERROR: {e}", 0, 0


print("=== corrected listing counts, page 1 (Sofia vs nationwide) ===")
for label, url in [
    ("sofia", f"{BASE}?region_id=22&location_ids=4342"),
    ("nationwide", BASE),
]:
    status, n, length = check(url)
    print(f"  {label}: status={status} real_listing_links={n} len={length}")
    time.sleep(1)

print("\n=== deep pagination on nationwide, corrected count ===")
for page in [1, 100, 300, 500, 800, 1200, 1600, 2000, 2400, 2600, 2700, 2750, 2800]:
    url = BASE if page == 1 else f"{BASE}?page={page}"
    status, n, length = check(url)
    print(f"  page {page}: status={status} real_listing_links={n} len={length}")
    time.sleep(0.8)

print("\ndone")
