"""
Diagnostic-only: before converting scraper.py (imoti.net) to nationwide,
this checks two things live:

1. The real nationwide search URL - the current scraper is hardcoded to
   /en/obiavi/r/prodava/sofia; removing/changing that path segment should
   reveal the real "all Bulgaria" mechanism (same kind of undocumented-URL
   problem homes.bg had).

2. Whether the confirmed page-200 HTTP 403 block (see scraper.py's own
   docstring) is a per-QUERY depth cap (like homes.bg's, where a narrower
   query resets the counter and price-band slicing would fix it) or a
   per-SESSION/IP cap that doesn't reset no matter how the query is
   sliced (in which case slicing wouldn't help at all, and going further
   nationwide would need a different approach). Tested by, in ONE
   requests.Session (same cookies/connection reuse as the real scraper),
   paging one query up to and past page 200 to trigger the block, then
   immediately trying page 1 of a completely different query in the same
   session - if that also 403s, the block is session-wide, not per-query.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE = "https://www.imoti.net/en/obiavi/r/prodava"
LISTING_LINK_RE = re.compile(r'^/en/obiava/prodava[^"\'#]*?/(\d+)/')


def check(session, url):
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        n = len(set(LISTING_LINK_RE.findall(resp.text)))
        return resp.status_code, n, len(resp.text)
    except requests.RequestException as e:
        return f"ERROR: {e}", 0, 0


print("=== Part 1: nationwide URL candidates (fresh session, page 1 each) ===")
session1 = requests.Session()
candidates = [
    ("sofia (current)", f"{BASE}/sofia"),
    ("no city segment", BASE),
    ("bulgaria", f"{BASE}/bulgaria"),
    ("no city, ?page=1 only", f"{BASE}?page=1"),
]
for label, url in candidates:
    status, n, length = check(session1, url)
    print(f"  {label}: {url} -> status={status} listing_links={n} len={length}")
    time.sleep(1)

print("\n=== Part 2: is the page-200 block per-query or per-session? ===")
session2 = requests.Session()
query_a = f"{BASE}/sofia"
query_b = f"{BASE}/plovdiv"  # guessed city slug, just needs to be a different URL

print(f"Paging query A ({query_a}) from page 195 to 205 to trigger the known block...")
blocked_at = None
for page in range(195, 206):
    url = f"{query_a}?page={page}"
    status, n, length = check(session2, url)
    print(f"  A page {page}: status={status} listing_links={n}")
    if status == 403 and blocked_at is None:
        blocked_at = page
    time.sleep(1)

print(f"\nBlock triggered at page {blocked_at}. Now trying query B ({query_b}) page 1 in the SAME session...")
status, n, length = check(session2, query_b)
print(f"  B page 1: status={status} listing_links={n} len={length}")
if status == 403:
    print("  -> Block is SESSION-WIDE: a different query in the same session is also blocked.")
else:
    print("  -> Block is PER-QUERY: a different query in the same session works fine, slicing should help.")

print("\n=== Part 3: does a brand new session (same process) also work fine immediately? ===")
session3 = requests.Session()
status, n, length = check(session3, query_a)
print(f"  fresh session, query A page 1: status={status} listing_links={n}")

print("\ndone")
