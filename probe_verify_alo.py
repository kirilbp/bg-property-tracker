"""
Diagnostic-only: bounded live verification of the nationwide-converted
scraper_alo.py + backfill_detail_alo.py, before either goes into the real
scrape-large.yml / backfill-detail-alo.yml rotation.

Runs the real module's fetch_listings_page() against a few real nationwide
pages (not the full 2800-page crawl - that's a real multi-hour job) to
check area/city extraction is correct for non-Sofia listings (the whole
point of today's fix), then runs the real fetch_update_dates() detail-
enrichment function against a small sample to confirm the backfill script's
core logic works end-to-end.

Read-only for scraper purposes (writes nothing to data/) - doesn't call
load_history/save_history/main(). No commit step in the workflow. Deleted
once this verification passes.
"""

import time

import scraper_alo as sa

seen = {}
for page in [1, 100, 800, 2000]:
    url = sa.SEARCH_URL if page == 1 else f"{sa.SEARCH_URL}&page={page}"
    before = len(seen)
    link_count = sa.fetch_listings_page(url, seen)
    print(f"page {page}: link_count={link_count}, new listings={len(seen) - before}")
    time.sleep(1)

print(f"\n=== {len(seen)} total listings collected (bounded sample) ===")

by_city = {}
for l in seen.values():
    by_city.setdefault(l.get("city"), []).append(l)
for city, listings in sorted(by_city.items(), key=lambda kv: -len(kv[1])):
    print(f"\n{city!r}: {len(listings)} listings")
    for l in listings[:3]:
        print(f"  price={l['price_eur']} sqm={l['sqm']} area={l['area']!r} title={l['title'][:70]!r}")

bad = [l for l in seen.values() if l.get("area") is None or l.get("price_eur") is None]
print(f"\nlistings with missing core fields: {len(bad)}")
no_city = sum(1 for l in seen.values() if l.get("city") is None)
print(f"listings with no city match at all: {no_city}/{len(seen)}")

print("\n=== detail-enrichment sample (first 5 listings) ===")
sample = dict(list(seen.items())[:5])
to_enrich = {lid: l for lid, l in sample.items()}
sa.fetch_update_dates(to_enrich)
for lid, l in sample.items():
    print(f"  {lid}: category={l.get('category')} lat={l.get('lat')} site_updated_at={l.get('site_updated_at')}")

print("\ndone")
