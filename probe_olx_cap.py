"""
Diagnostic-only: round 2 for olx.bg nationwide. Round 1 found:
- Dropping the region segment entirely (/nedvizhimi-imoti/prodazhbi/) IS a
  real nationwide switch (same page size/listing count as Sofia's own page
  1) - unlike imot.bg/imoti.net, no per-region slug is strictly required.
- But per-query pagination on Sofia collapses somewhere between page 20
  (41 real links) and page 30 (1 link, page length nearly halved) - a real
  depth cap, the same pattern every other portal turned out to have.
- oblast-plovdiv and oblast-varna guessed region slugs both resolved to
  real distinct pages, so per-region slicing IS available as a fallback if
  the bare nationwide URL's own cap turns out too shallow to cover
  Bulgaria's real total inventory.

This pins the exact cap boundary (pages 21-29) on Sofia, and checks
whether it resets per-query the same way it did for every other portal -
by paging Plovdiv (a different oblast-scoped query) past where Sofia
capped, in the same browser session - and separately checks how deep the
bare nationwide URL itself goes before hitting its own cap.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

from playwright.sync_api import sync_playwright

BASE = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/d/ad/[^\"'#]*-ID(\w+)\.html")


def check(page, url):
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        html = page.content()
        n = len(set(LISTING_LINK_RE.findall(html)))
        status = resp.status if resp else "?"
        return status, n, len(html)
    except Exception as e:
        return f"ERROR: {e}", 0, 0


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()

    print("=== Part 1: pin down exact cap boundary on Sofia (pages 21-29) ===")
    cap_page = None
    for pnum in range(21, 30):
        url = f"{BASE}/oblast-sofiya-grad/?page={pnum}"
        status, n, length = check(page, url)
        print(f"  page {pnum}: status={status} listing_links={n} len={length}")
        if n <= 1 and cap_page is None:
            cap_page = pnum
        time.sleep(1)
    print(f"\nCap appears to kick in around page {cap_page}")

    print("\n=== Part 2: does a different oblast query (Plovdiv) reset the cap? ===")
    for pnum in [1, 15, 25, 28]:
        url = f"{BASE}/oblast-plovdiv/" if pnum == 1 else f"{BASE}/oblast-plovdiv/?page={pnum}"
        status, n, length = check(page, url)
        print(f"  Plovdiv page {pnum}: status={status} listing_links={n} len={length}")
        time.sleep(1)

    print("\n=== Part 3: how deep does the bare nationwide URL itself go? ===")
    for pnum in [1, 15, 25, 28, 35]:
        url = f"{BASE}/" if pnum == 1 else f"{BASE}/?page={pnum}"
        status, n, length = check(page, url)
        print(f"  nationwide page {pnum}: status={status} listing_links={n} len={length}")
        time.sleep(1)

    browser.close()

print("\ndone")
