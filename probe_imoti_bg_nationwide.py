"""
Diagnostic-only: bounded first pass of the newly nationwide-ized
scraper_imoti_bg.py against the real live site, before trusting it enough
to run unbounded in the real pipeline. Caps pagination low (a fraction of
the real MAX_PAGES) specifically to keep this run fast and cheap while
still exercising every part of the real, unmodified scraper code path -
imports and calls the actual functions rather than reimplementing
anything, so this validates the exact code that will ship.

Checks the things the nationwide expansion actually promised: listings
from more than one city (proving the Sofia filter is really gone), more
than one of the 6 categories (proving all-types search plus the new
classifier are both working, not just apartments), real descriptions
being captured (not just the old card-only fields), and the classifier's
confidence-flag distribution on real data.

Read-only, no commit step - deleted once the question is answered.
"""

import scraper_imoti_bg as scraper

scraper.MAX_PAGES = 15

listings = scraper.fetch_listings()

print(f"\n=== total listings found (capped at {scraper.MAX_PAGES} pages): {len(listings)} ===")

cities = set()
categories = {}
confidences = {}
with_description = 0
with_photo = 0
with_posted_date = 0

for l in listings:
    cities.add(l["area"])
    categories[l["category"]] = categories.get(l["category"], 0) + 1
    confidences[l["category_confidence"]] = confidences.get(l["category_confidence"], 0) + 1
    if l.get("description"):
        with_description += 1
    if l.get("photo"):
        with_photo += 1
    if l.get("site_posted_at"):
        with_posted_date += 1

print(f"distinct areas seen: {len(cities)}")
print(f"  sample areas: {sorted(cities)[:20]}")
print(f"category distribution: {categories}")
print(f"confidence distribution: {confidences}")
print(f"listings with a real description: {with_description}/{len(listings)}")
print(f"listings with a photo: {with_photo}/{len(listings)}")
print(f"listings with a posted date: {with_posted_date}/{len(listings)}")

print("\n=== sample listings (up to 8) ===")
for l in listings[:8]:
    print(f"\n  id={l['id']} category={l['category']} ({l['category_confidence']})")
    print(f"  title={l['title']!r}")
    print(f"  area={l['area']!r} price={l['price_eur']} sqm={l['sqm']}")
    print(f"  url={l['url']}")
    print(f"  photo={l['photo']}")
    desc = l.get("description")
    print(f"  description={(desc[:150] + '...') if desc and len(desc) > 150 else desc!r}")
    print(f"  site_posted_at={l.get('site_posted_at')}")
    print(f"  lat/lng={l.get('lat')},{l.get('lng')}")
