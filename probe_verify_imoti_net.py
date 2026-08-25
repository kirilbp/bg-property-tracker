"""
Diagnostic-only: bounded live verification of the new nationwide, per-city
fetch_listings() in scraper.py, before it goes into the real scrape-large.yml
rotation (a full run visits every tracked listing's own page too, so it's a
genuinely multi-hour job - not something to run unbounded here first).

Runs the real scraper module's own functions (fetch_listings_page,
extract_area, fetch_listing_dates) against a handful of real cities -
Plovdiv/Varna/Burgas specifically (the three the user asked to verify),
plus one small city (Silistra) as a cheap sanity check - fetching only
page 1 of each (not full pagination) and only running the detail-page
date/coords/category fetch on a small sample, to keep this fast while
still exercising the exact same code path the real scrape will run.

Checks: real listings appear for all three target cities, "city" field is
correctly tagged per query (not defaulting to Sofia), "area" is a real
neighborhood name (not the whole title), and detail-page enrichment
(category/coords/date) works on a sample.

Read-only for scraper purposes (writes nothing to data/ - doesn't call
load_history/save_history/main()). No commit step in the workflow.
Deleted once this verification passes.
"""

import time

import scraper as sc

TEST_CITIES = [
    ("plovdiv", "Пловдив"),
    ("varna", "Варна"),
    ("burgas", "Бургас"),
    ("silistra", "Силистра"),
]

seen = {}
for city_slug, city_name in TEST_CITIES:
    url = f"{sc.BASE_URL}/{city_slug}"
    before = len(seen)
    link_count = sc.fetch_listings_page(url, seen, city_slug, city_name)
    print(f"{city_name}: page 1 link_count={link_count}, new listings={len(seen) - before}")
    time.sleep(1)

print(f"\n=== {len(seen)} total listings collected across {len(TEST_CITIES)} cities (page 1 only) ===")

by_city = {}
for l in seen.values():
    by_city.setdefault(l["city"], []).append(l)
for city, listings in by_city.items():
    print(f"\n{city}: {len(listings)} listings")
    for l in listings[:3]:
        print(f"  price={l['price_eur']} sqm={l['sqm']} area={l['area']!r} title={l['title'][:60]!r}")

bad = [l for l in seen.values() if not l.get("area") or not l.get("city") or l.get("price_eur") is None]
print(f"\nlistings with missing core fields: {len(bad)}")

print("\n=== detail-page enrichment sample (first 8 listings) ===")
sample = dict(list(seen.items())[:8])
sc.fetch_listing_dates(sample)
for lid, l in sample.items():
    print(f"  {lid}: category={l.get('category')} lat={l.get('lat')} site_posted_at={l.get('site_posted_at')}")

print("\ndone")
