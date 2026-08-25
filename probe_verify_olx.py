"""
Bounded live verification for scraper_olx.py's nationwide rewrite, before
merging - per the project's standing "verify against real listing counts
for Plovdiv/Varna/Burgas" requirement. Runs the real module's own
fetch/parse functions (not a reimplementation) against Sofia (existing
baseline), Plovdiv, Varna and Burgas oblasts, each capped to 3 pages, and
reports: real city/area tagging (both the "гр." and "с." branches),
per-oblast listing counts, and no city bleeding between oblasts.

Read-only except for geo_utils' on-disk cache (cache-only lookups here,
no live geocoding) - no commit step, deleted once the question is
answered.
"""

from collections import Counter

from playwright.sync_api import sync_playwright

import scraper_olx as so
from geo_utils import Geocoder

VERIFY_OBLASTS = [o for o in so.OBLAST_SLUGS if o[0] in ("София", "Пловдив", "Варна", "Бургас")]
PAGES_PER_OBLAST = 3

seen = {}
geocoder = Geocoder()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=so.USER_AGENT, locale="bg-BG")
    page = context.new_page()

    for oblast_display, slug in VERIFY_OBLASTS:
        search_url = f"{so.SEARCH_BASE}/{slug}/"
        before = len(seen)
        for page_num in range(1, PAGES_PER_OBLAST + 1):
            url = search_url if page_num == 1 else f"{search_url}?page={page_num}"
            link_count = so.fetch_listings_page(page, url, seen, geocoder, oblast_display)
            print(f"  {oblast_display} page {page_num}: {link_count} listing links")
            if link_count is None or link_count <= 1:
                break
        print(f"{oblast_display}: {len(seen) - before} new listings collected\n")

    browser.close()

print("=== summary ===")
by_oblast = Counter(l["city"] for l in seen.values())
print(f"total listings: {len(seen)}")
print(f"by city tag: {dict(by_oblast)}")

print("\n=== sample listings per oblast (city, area, price, sqm) ===")
by_oblast_samples = {}
for l in seen.values():
    by_oblast_samples.setdefault(l.get("city"), []).append(l)
for city, listings in by_oblast_samples.items():
    print(f"--- tagged city={city!r} ({len(listings)}) ---")
    for l in listings[:4]:
        print(f"  area={l['area']!r} city={l['city']!r} price={l['price_eur']} sqm={l['sqm']} category={l['category']}")

print("\ndone")
