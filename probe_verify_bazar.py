"""
Bounded live verification for scraper_bazar.py's nationwide rewrite,
before merging - per the project's standing "verify against real listing
counts for Plovdiv/Varna/Burgas" requirement. Runs the real module's own
fetch/parse functions (not a reimplementation) against Sofia (existing
baseline), Plovdiv, Varna and Burgas, each capped to 3 pages, and reports:
real city tagging, area extraction, and per-city listing counts.

Read-only, no commit step - deleted once the question is answered.
"""

from collections import Counter

import scraper_bazar as sb

VERIFY_CITIES = [c for c in sb.CITY_SLUGS if c[0] in ("София", "Пловдив", "Варна", "Бургас")]
PAGES_PER_CITY = 3

all_listings = {}

for city_display, slug in VERIFY_CITIES:
    search_url = f"{sb.SEARCH_BASE}/{slug}"
    before = len(all_listings)
    prev_ids = None
    for page_num in range(1, PAGES_PER_CITY + 1):
        url = search_url if page_num == 1 else f"{search_url}?page={page_num}"
        page_listings = sb.fetch_listings_page(url, city_display)
        if page_listings is None:
            print(f"  {city_display} page {page_num}: navigation failed")
            break
        page_ids = frozenset(page_listings.keys())
        print(f"  {city_display} page {page_num}: {len(page_listings)} listing links")
        if not page_listings or page_ids == prev_ids:
            break
        all_listings.update(page_listings)
        prev_ids = page_ids
    print(f"{city_display}: {len(all_listings) - before} new listings collected\n")

print("=== summary ===")
by_city = Counter(l["city"] for l in all_listings.values())
print(f"total listings: {len(all_listings)}")
print(f"by city: {dict(by_city)}")

print("\n=== sample listings per city (area, price, category) ===")
by_city_samples = {}
for l in all_listings.values():
    by_city_samples.setdefault(l["city"], []).append(l)
for city, listings in by_city_samples.items():
    print(f"--- {city} ({len(listings)}) ---")
    for l in listings[:4]:
        print(f"  area={l['area']!r} price={l['price_eur']} category={l['category']}")

print("\ndone")
