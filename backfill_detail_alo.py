"""
Fills in site_updated_at/lat,lng/category for alo.bg listings that
scraper_alo.py's nationwide grid crawl left unenriched.

scraper_alo.py's nationwide conversion deliberately stopped visiting every
listing's own page during the main scrape (see its module docstring) -
nationwide scale (~156,000 listings vs. the old ~10,000 Sofia-only) made
that no longer affordable in a single run. It now only does the fast grid
crawl and leaves detail fields unset.

This script is the other half: a separate, resumable pass that visits
listing pages (scraper_alo.py's own fetch_update_dates(), unchanged) for
whatever's still unenriched, prioritized newest-first (by first_seen) so
freshly discovered listings get their real posted date and coordinates
before older ones queue behind them - same "don't let unbounded
outside-network work block or crash the actual scrape" pattern
backfill_geocode_homes.py already established for homes.bg's geocoding.

Scheduled hourly (see backfill-detail-alo.yml) rather than left to manual
dispatch like the geocode backfills - at ~1,000 listings/run (see
MAX_LOOKUPS_PER_RUN below) and 24 runs/day, a fresh ~156,000-listing
backlog takes roughly a week to fully clear; after that, each run only
has to keep up with newly-discovered listings from that day's scrapes,
which is a much smaller number.
"""

import json

import scraper_alo as sa

# ~1,000 listings/run at ~1.0-1.5s each (REQUEST_DELAY_SECONDS plus network
# round-trip) is roughly 17-25 minutes - comfortably inside the hourly
# cadence this runs on, with real margin before the next run would start.
MAX_LOOKUPS_PER_RUN = 1000


def main():
    history = sa.load_history()

    # "category" is always set once a listing's detail page has actually
    # been visited (classify_category() never returns None) - unlike
    # site_updated_at/lat,lng, which can genuinely stay None even after a
    # real visit (the site doesn't always show them), so category is the
    # one reliable "not yet enriched" signal.
    missing = [
        (lid, rec) for lid, rec in history.items()
        if "category" not in rec.get("latest", {})
    ]
    # Newest-discovered first, so freshly scraped listings get real
    # dates/coordinates before older ones still waiting in the backlog.
    missing.sort(key=lambda item: item[1].get("first_seen", ""), reverse=True)
    print(f"DEBUG: {len(missing)} / {len(history)} listings not yet detail-enriched")

    batch = dict(missing[:MAX_LOOKUPS_PER_RUN])
    to_enrich = {lid: rec["latest"] for lid, rec in batch.items()}
    sa.fetch_update_dates(to_enrich)

    sa.save_history(history)

    leads = sa.compute_leads(history)
    sa.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    processed = len(batch)
    print(f"DEBUG: detail-enriched {processed} listings this run "
          f"({len(missing) - processed} still queued for a future run)")


if __name__ == "__main__":
    main()
