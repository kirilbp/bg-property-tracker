"""
Diagnostic-only: bounded verification of the nationwide scraper_homes.py
rewrite before running it unbounded. Per the staged-rollout requirement
(prove one portal end to end before moving to the next, and prove each
portal's own rewrite before letting it run unbounded), this monkeypatches
MAX_PAGES down to a small number so the run finishes in seconds instead of
however long the full ~69k-listing nationwide crawl would take, then
checks the same things the imoti.bg bounded probe checked: real listings
come back, they're spread across cities (not just Sofia), and every
listing lands in the category matching the search it came from.

Read-only (writes nothing to history/leads files or Supabase), no commit
step - deleted once verification passes.
"""

import scraper_homes as sh

# Earlier attempts at MAX_PAGES=1-2 ran 10-20+ minutes without finishing -
# scraper_homes.py was blocking on a live Nominatim geocode call per
# nationwide cache miss, and nationwide locations meant almost every one
# was a miss. Fixed by decoupling geocoding from the scrape entirely
# (fetch_listings() now does a cache-only lookup - see scraper_homes.py's
# module docstring and backfill_geocode_homes.py), so this should now run
# in seconds - back to a real sample size to verify the rewrite properly.
sh.MAX_PAGES = 3

listings = sh.fetch_listings()

print(f"\n=== bounded fetch summary: {len(listings)} listings ===")

by_category = {}
for l in listings:
    by_category.setdefault(l["category"], []).append(l)

print("\n=== per-category counts ===")
for cat, items in sorted(by_category.items()):
    confidences = {i["category_confidence"] for i in items}
    print(f"  {cat}: {len(items)} (confidence values seen: {confidences})")

print("\n=== sample listings per category (city/area, price, sqm) ===")
for cat, items in sorted(by_category.items()):
    print(f"  --- {cat} ---")
    for l in items[:5]:
        print(f"    area={l['area']!r} price_eur={l['price_eur']} sqm={l['sqm']} lat={l['lat']} lng={l['lng']}")
        print(f"      title={l['title']!r}")
        print(f"      url={l['url']!r}")

non_sofia = [l for l in listings if "софия" not in l["area"].lower() and "sofia" not in l["area"].lower()]
print(f"\n=== non-Sofia listings: {len(non_sofia)} / {len(listings)} ===")
for l in non_sofia[:10]:
    print(f"  area={l['area']!r} category={l['category']!r}")

missing_desc = sum(1 for l in listings if not l.get("description"))
missing_photo = sum(1 for l in listings if not l.get("photo"))
missing_coords = sum(1 for l in listings if l.get("lat") is None)
print(f"\n=== field completeness ===")
print(f"  missing description: {missing_desc}/{len(listings)}")
print(f"  missing photo: {missing_photo}/{len(listings)}")
print(f"  missing coords: {missing_coords}/{len(listings)}")
