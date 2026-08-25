"""
Diagnostic-only: before converting scraper_olx.py to nationwide, checks
olx.bg's real nationwide URL mechanism. Current URL is
/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/ (a region-scoped path
segment). Tests whether dropping the region segment entirely gives a real
nationwide result (the homes.bg/alo.bg pattern), or whether each region
needs its own explicit slug (the imoti.net/imot.bg pattern).

Also checks whether deep pagination on whatever the real nationwide/
largest-scope URL turns out to be hits any kind of depth cap - a real
concern given homes.bg, imoti.net, and imot.bg all turned out to have one
once investigated.

Uses the same Playwright setup as the real scraper (bot-blocked for plain
requests, confirmed in scraper_olx.py's own docstring).

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

    print("=== Part 1: nationwide URL candidates (page 1 each) ===")
    candidates = [
        ("sofia (current)", f"{BASE}/oblast-sofiya-grad/"),
        ("no region segment", f"{BASE}/"),
        ("plovdiv guess", f"{BASE}/oblast-plovdiv/"),
        ("varna guess", f"{BASE}/oblast-varna/"),
    ]
    for label, url in candidates:
        status, n, length = check(page, url)
        print(f"  {label}: {url} -> status={status} listing_links={n} len={length}")
        time.sleep(1)

    print("\n=== Part 2: deep pagination on Sofia (known scope) ===")
    for pnum in [1, 10, 20, 30, 40, 60, 90]:
        url = f"{BASE}/oblast-sofiya-grad/" if pnum == 1 else f"{BASE}/oblast-sofiya-grad/?page={pnum}"
        status, n, length = check(page, url)
        print(f"  page {pnum}: status={status} listing_links={n} len={length}")
        time.sleep(1)

    browser.close()

print("\ndone")
