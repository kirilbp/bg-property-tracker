"""
Diagnostic-only: bounded live verification of the new price-band-bisection
fetch_listings() in scraper_homes.py, before it goes into the real
scrape.yml rotation. Runs the real scraper module's own functions
end-to-end (bisect_price_slices + scrape_slice + parse_offer) but scoped to
just LandAgro - the smallest of the 4 real homes.bg types (~2,115-2,122
known live total) - so this finishes in a couple minutes instead of the
full run's much longer time, while exercising the exact same code path
(same bisection, same per-slice pagination, same parsing/geocoding) the
real scrape.yml step will run.

Checks: total listing count vs. the known live total, no crashes, sane
field values (price/sqm/area/category) on a sample, and how many price
slices bisection produced.

Read-only for geocoding purposes (cache-only lookups, no network calls,
same as production) - the only write is geo_utils' own cache save (a repo
data file), same as a real run would do. No commit step in the workflow.
Deleted once this verification passes.
"""

import time

import requests

import scraper_homes as sh
from geo_utils import Geocoder

session = requests.Session()
geocoder = Geocoder()
type_id, category = "LandAgro", "land"

start = time.monotonic()
slices = sh.bisect_price_slices(session, type_id, 0, sh.MAX_SLICE_PRICE)
tail_count = sh.get_offers_count(session, type_id, sh.MAX_SLICE_PRICE, None)
slices.append((sh.MAX_SLICE_PRICE, None))
print(f"{type_id}: {len(slices)} price slices (tail count {tail_count}), bisection took {time.monotonic() - start:.0f}s")

seen = {}
for lo, hi in slices:
    sh.scrape_slice(session, geocoder, type_id, category, lo, hi, seen, start)

geocoder.save()

listings = list(seen.values())
print(f"\n=== {type_id}: {len(listings)} total listings (known live total ~2,115-2,122) ===")
print(f"total time: {time.monotonic() - start:.0f}s")

bad = [l for l in listings if l["price_eur"] is None or not l["title"] or l["category"] != category]
print(f"listings with missing/wrong core fields: {len(bad)}")

with_coords = sum(1 for l in listings if l["lat"] is not None)
print(f"listings with cached coords already resolved: {with_coords}/{len(listings)}")

print("\nsample of 5:")
for l in listings[:5]:
    print(f"  {l['id']} | {l['price_eur']} EUR | {l['sqm']} sqm | area={l['area']!r} | cat={l['category']}/{l['category_confidence']}")

print("\ndone")
