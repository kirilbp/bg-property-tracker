"""
Diagnostic-only: before converting scraper_alo.py to nationwide, checks
whether alo.bg's location filter (?region_id=22&location_ids=4342, Sofia)
can simply be dropped for nationwide results, same mechanism as homes.bg's
?locationId=0, or whether it needs a different real nationwide value.

Also spot-checks whether the confirmed alo.bg listing count (~9995
apartment listings, ~333 pages) changes meaningfully when the location
filter is dropped/altered, and whether pagination survives deep into the
result set without a homes.bg/imoti.net-style block (not yet checked for
this portal).

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/"
LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")


def check(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        n = len(set(LISTING_LINK_RE.findall(resp.text)))
        # alo.bg's own results header usually states a total count somewhere
        # in the page text near "обяви" (listings) - grab any nearby number
        # for a rough real-total signal.
        total_hint = re.findall(r"([\d\s]{2,7})\s*обяви", resp.text)
        return resp.status_code, n, len(resp.text), total_hint[:3]
    except requests.RequestException as e:
        return f"ERROR: {e}", 0, 0, []


print("=== Part 1: location filter candidates (page 1 each) ===")
candidates = [
    ("sofia (current)", f"{BASE}?region_id=22&location_ids=4342"),
    ("no location params", BASE),
    ("region_id=0", f"{BASE}?region_id=0"),
    ("no trailing slash, no params", "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai"),
]
for label, url in candidates:
    status, n, length, hint = check(url)
    print(f"  {label}: {url} -> status={status} listing_links={n} len={length} total_hint={hint}")
    time.sleep(1)

print("\n=== Part 2: deep pagination check on the 'no location params' candidate ===")
for page in [1, 50, 100, 150, 200, 250, 300, 330]:
    url = BASE if page == 1 else f"{BASE}?page={page}"
    status, n, length, hint = check(url)
    print(f"  page {page}: status={status} listing_links={n} len={length}")
    time.sleep(1)

print("\ndone")
