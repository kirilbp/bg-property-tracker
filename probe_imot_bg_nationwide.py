"""
Diagnostic-only: before converting scraper_imot.py to nationwide, checks
imot.bg's real nationwide URL mechanism. Current URL is
/obiavi/prodazhbi/grad-sofiya (a city-scoped path segment, like imoti.net's
/en/obiavi/r/prodava/<city> - not a query-param toggle like homes.bg's
?locationId=0). Tests whether there's a single "all cities" URL, or
whether (like imoti.net) each city needs its own slug.

Also checks whether deep pagination on whatever the real nationwide/
largest-scope URL turns out to be hits any kind of depth cap (a real
concern given both other Playwright/requests-blocked-by-bot-check hurdles
this portal already has - and both imoti.net and homes.bg turned out to
have real depth caps once investigated).

Uses the same Playwright setup as the real scraper (bot-blocked for plain
requests, confirmed in scraper_imot.py's own docstring).

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

    print("=== Part 1: nationwide URL candidates (page 1 each) ===")
    candidates = [
        ("sofia (current)", f"{BASE}/grad-sofiya"),
        ("no city segment", BASE),
        ("bulgaria", f"{BASE}/bulgaria"),
        ("plovdiv guess", f"{BASE}/grad-plovdiv"),
        ("varna guess", f"{BASE}/grad-varna"),
    ]
    for label, url in candidates:
        status, n, length = check(page, url)
        print(f"  {label}: {url} -> status={status} listing_links={n} len={length}")
        time.sleep(1)

    print("\n=== Part 2: deep pagination on Sofia (known scope) ===")
    for pnum in [1, 10, 20, 30, 50, 80, 120, 200]:
        url = f"{BASE}/grad-sofiya" if pnum == 1 else f"{BASE}/grad-sofiya/p-{pnum}"
        status, n, length = check(page, url)
        print(f"  page {pnum}: status={status} listing_links={n} len={length}")
        time.sleep(1)

    browser.close()

print("\ndone")
