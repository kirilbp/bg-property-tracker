"""
Diagnostic-only: before converting scraper_bazar.py to nationwide, checks
bazar.bg's real nationwide URL mechanism. Current URL is
/obiavi/prodazhba-apartamenti/sofia (a city-scoped path segment). Tests
whether dropping the city segment entirely gives a real nationwide result
(the homes.bg/alo.bg/olx.bg pattern), or whether each city needs its own
slug (the imoti.net/imot.bg pattern).

Also checks whether deep pagination on whatever the real nationwide/
largest-scope URL turns out to be hits any kind of depth cap - a real
concern given every other portal in this project turned out to have one
once investigated.

bazar.bg has no bot-blocking (confirmed in scraper_bazar.py's own
docstring) - uses plain requests, same as the real scraper.

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


def check(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        n = len(set(LISTING_LINK_RE.findall(r.text)))
        return r.status_code, n, len(r.text)
    except Exception as e:
        return f"ERROR: {e}", 0, 0


print("=== Part 1: nationwide URL candidates (page 1 each) ===")
candidates = [
    ("sofia (current)", f"{BASE}/sofia"),
    ("no city segment", BASE),
    ("plovdiv guess", f"{BASE}/plovdiv"),
    ("varna guess", f"{BASE}/varna"),
    ("burgas guess", f"{BASE}/burgas"),
]
for label, url in candidates:
    status, n, length = check(url)
    print(f"  {label}: {url} -> status={status} listing_links={n} len={length}")
    time.sleep(1)

print("\n=== Part 2: deep pagination on Sofia (known scope) ===")
for pnum in [1, 10, 20, 30, 50, 80, 120]:
    url = f"{BASE}/sofia" if pnum == 1 else f"{BASE}/sofia?page={pnum}"
    status, n, length = check(url)
    print(f"  page {pnum}: status={status} listing_links={n} len={length}")
    time.sleep(1)

print("\ndone")
