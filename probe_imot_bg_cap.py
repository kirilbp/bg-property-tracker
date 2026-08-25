"""
Diagnostic-only: round 2 for imot.bg nationwide. Round 1 found a real,
previously-undiscovered depth cap on Sofia-scoped pagination somewhere
between page 20 (real content, 40 links) and page 30 (0 links, page
length halved) - this predates today's nationwide work entirely; even
the existing Sofia-only scraper (MAX_PAGES=30) was already brushing
against it. Round 1 also found the nationwide URL is simply dropping the
city segment entirely (/obiavi/prodazhbi with no /grad-X suffix, same
listing count as Sofia's own page 1) - no per-city slug needed, unlike
imoti.net/alo.bg.

This pins down the exact cap boundary (pages 21-29) and checks whether it
resets per-query the same way homes.bg's and imoti.net's caps did - by
paging Plovdiv (a different city-scoped query) past where Sofia capped,
in the same browser context/session.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

from playwright.sync_api import sync_playwright

BASE = "https://www.imot.bg/obiavi/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/obiava-(\d[a-z]\d{10,})-")


def check(page, url):
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1200)
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
        url = f"{BASE}/grad-sofiya/p-{pnum}"
        status, n, length = check(page, url)
        print(f"  page {pnum}: status={status} listing_links={n} len={length}")
        if n == 0 and cap_page is None:
            cap_page = pnum
        time.sleep(1)

    print(f"\nCap appears to kick in around page {cap_page}")

    print("\n=== Part 2: does a different city query (Plovdiv) reset the cap? ===")
    print("Paging Plovdiv past where Sofia capped, in the SAME session...")
    for pnum in [1, 15, 25, 28]:
        url = f"{BASE}/grad-plovdiv" if pnum == 1 else f"{BASE}/grad-plovdiv/p-{pnum}"
        status, n, length = check(page, url)
        print(f"  Plovdiv page {pnum}: status={status} listing_links={n} len={length}")
        time.sleep(1)

    print("\n=== Part 3: does nationwide (no city segment) itself hit the same wall? ===")
    for pnum in [1, 15, 25, 28, 35]:
        url = BASE if pnum == 1 else f"{BASE}/p-{pnum}"
        status, n, length = check(page, url)
        print(f"  nationwide page {pnum}: status={status} listing_links={n} len={length}")
        time.sleep(1)

    browser.close()

print("\ndone")
