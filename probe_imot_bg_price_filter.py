"""
Diagnostic-only: round 3 for imot.bg nationwide. Rounds 1-2 confirmed the
real depth cap (~27 real pages, ~1,080 listings at 40/page) hits
independently per query - Sofia, Plovdiv, and nationwide (no city
segment) all cap at the same ~page 27-28 boundary. Since imot.bg's own
site UI already states 1000+ Sofia listings alone, Sofia (and likely a
few other big cities) will still exceed the cap even sliced down to a
single city - this checks whether imot.bg's search URL supports a price
filter param, so an over-cap city can be sliced further by price band,
the same combined technique already proven for homes.bg (price bands)
and imoti.net (city slicing) - here potentially needing both layered
together.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

from playwright.sync_api import sync_playwright

BASE = "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/obiava-(\d[a-z]\d{10,})-")
PRICE_TEXT_RE = re.compile(r"([\d\s]{3,10})\s?€")


def check(page, url):
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1200)
        html = page.content()
        n = len(set(LISTING_LINK_RE.findall(html)))
        status = resp.status if resp else "?"
        return status, n, len(html), html
    except Exception as e:
        return f"ERROR: {e}", 0, 0, ""


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()

    print("=== Part 1: look for a price-filter form/link on the search page ===")
    status, n, length, html = check(page, BASE)
    print(f"baseline: status={status} listing_links={n} len={length}")
    # Look for any form inputs or query-param hints related to price
    price_hints = re.findall(r'name="([^"]*price[^"]*)"', html, re.IGNORECASE)
    price_hints2 = re.findall(r'name="([^"]*cena[^"]*)"', html, re.IGNORECASE)
    print(f"form fields with 'price' in name: {set(price_hints)}")
    print(f"form fields with 'cena' in name: {set(price_hints2)}")

    print("\n=== Part 2: try common price param guesses on Sofia ===")
    candidates = [
        ("price_from/to", f"{BASE}?price_from=0&price_to=100000"),
        ("priceFrom/To", f"{BASE}?priceFrom=0&priceTo=100000"),
        ("cena_ot/do", f"{BASE}?cena_ot=0&cena_do=100000"),
        ("pf/pt", f"{BASE}?pf=0&pt=100000"),
    ]
    for label, url in candidates:
        status, n, length, _ = check(page, url)
        print(f"  {label}: status={status} listing_links={n} len={length}")
        time.sleep(1)

    print("\n=== Part 3: check for a real price filter link in nav/sidebar HTML ===")
    # Look for any href containing digits that could be a price range link
    price_links = re.findall(r'href="([^"]*(?:cena|price)[^"]*)"', html, re.IGNORECASE)
    print(f"links mentioning price/cena: {price_links[:10]}")

    browser.close()

print("\ndone")
