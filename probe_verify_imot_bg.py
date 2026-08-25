"""
Bounded live verification for scraper_imot.py's nationwide rewrite, before
merging - per the project's standing "verify against real listing counts
for Plovdiv/Varna/Burgas" requirement. Runs the real module's own
fetch/parse functions (not a reimplementation) against Sofia (existing
baseline), Plovdiv, Varna and Burgas, each capped to 3 pages, and reports:
real city tagging correctness, area extraction correctness (spot check
against the module docstring's known-good samples), and per-city listing
counts to confirm no city returns 0 despite a real listings page.

Read-only except for geo_utils' on-disk cache (cache-only lookups here,
no live geocoding) - no commit step, deleted once the question is
answered.
"""

from collections import Counter

from playwright.sync_api import sync_playwright

import scraper_imot as si
from geo_utils import Geocoder

VERIFY_CITIES = [c for c in si.CITY_SLUGS if c[0] in ("София", "Пловдив", "Варна", "Бургас")]
PAGES_PER_CITY = 3

seen = {}
geocoder = Geocoder()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=si.USER_AGENT, locale="bg-BG")
    page = context.new_page()

    for city_display, slug in VERIFY_CITIES:
        search_url = f"{si.SEARCH_BASE}/{slug}"
        before = len(seen)
        for page_num in range(1, PAGES_PER_CITY + 1):
            url = search_url if page_num == 1 else f"{search_url}/p-{page_num}"
            html = si.goto_with_retries(page, url)
            if html is None:
                print(f"  {city_display} page {page_num}: navigation failed")
                break
            link_count = si.parse_listings_page(html, seen, geocoder, city_display)
            print(f"  {city_display} page {page_num}: {link_count} listing links")
            if link_count == 0:
                break
        print(f"{city_display}: {len(seen) - before} new listings collected\n")

    browser.close()

print("=== summary ===")
by_city = Counter(l["city"] for l in seen.values())
print(f"total listings: {len(seen)}")
print(f"by city: {dict(by_city)}")

print("\n=== sample listings per city (area, price, sqm) ===")
by_city_samples = {}
for l in seen.values():
    by_city_samples.setdefault(l["city"], []).append(l)
for city, listings in by_city_samples.items():
    print(f"--- {city} ({len(listings)}) ---")
    for l in listings[:3]:
        print(f"  area={l['area']!r} price={l['price_eur']} sqm={l['sqm']} category={l['category']}")

print("\ndone")
