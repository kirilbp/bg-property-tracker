"""
Fills in site_updated_at/lat,lng/category for alo.bg listings that
scraper_alo.py's nationwide grid crawl left unenriched.

scraper_alo.py's nationwide conversion deliberately stopped visiting every
listing's own page during the main scrape (see its module docstring) -
nationwide scale (~156,000 listings vs. the old ~10,000 Sofia-only) made
that no longer affordable in a single run. It now only does the fast grid
crawl and leaves detail fields unset.

This script is the other half: a separate, resumable pass that visits
listing pages (scraper_alo.py's own fetch_update_dates()) for whatever's
still unenriched, prioritized newest-first (by first_seen) so freshly
discovered listings get their real posted date and coordinates before
older ones queue behind them - same "don't let unbounded outside-network
work block or crash the actual scrape" pattern backfill_geocode_homes.py
already established for homes.bg's geocoding.

Scheduled hourly (see backfill-detail-alo.yml) rather than left to manual
dispatch like the geocode backfills - at ~1,000 listings/run (see
MAX_LOOKUPS_PER_RUN below) and 24 runs/day, a fresh ~156,000-listing
backlog takes roughly a week to fully clear; after that, each run only
has to keep up with newly-discovered listings from that day's scrapes,
which is a much smaller number.

fetch_update_dates() now takes a deadline and on_checkpoint, and stops
early after several consecutive per-listing failures - added after a
live production run hit a burst of 429 Too Many Requests across many
different listings in a row (the site actively throttling this run, not
any one listing being bad) and, with nothing saved until the very end,
ground through the rest of its ~1,000-listing batch retrying doomed
requests until the workflow's 45-minute timeout hard-killed it, reporting
a failed run with zero progress kept - every single hourly run, for
hours. Same fix as backfill_detail_imoti_net.py's own timeout problem
(see that script's docstring), adapted for a throttling burst here
instead of a run of permanently-gone (404/410) listings there.
"""

import json
import time

import scraper_alo as sa

# ~1,000 listings/run at ~1.0-1.5s each (REQUEST_DELAY_SECONDS plus network
# round-trip) is roughly 17-25 minutes - comfortably inside the hourly
# cadence this runs on, with real margin before the next run would start.
# Kept generous since the internal time budget below (not this count) is
# what actually decides when a run stops.
MAX_LOOKUPS_PER_RUN = 1000

# Stop visiting new listings once a run has spent this much of the
# workflow's 45-minute timeout - real headroom for whatever page is in
# flight, the final checkpoint, computing leads, and the commit/push step,
# so a run that needs every second of its time budget still exits on its
# own instead of getting hard-killed.
TIME_BUDGET_SECONDS = 35 * 60

CHECKPOINT_EVERY = 150


def main():
    history = sa.load_history()

    # "_detail_fetched" is set unconditionally once a listing's detail page
    # has actually been visited (scraper_alo.py's fetch_update_dates()) -
    # unlike site_updated_at/lat,lng/category, which can genuinely stay
    # unset even after a real visit (the site doesn't always show them, and
    # category is now classified at grid-crawl time from title/url alone,
    # with no detail-page dependency at all - see fetch_listings_page()),
    # so this explicit marker is the only reliable "not yet enriched"
    # signal; a bare field-presence check would stop finding any work once
    # every field it could check is populated some other way.
    missing = [
        (lid, rec) for lid, rec in history.items()
        if not rec.get("latest", {}).get("_detail_fetched")
    ]
    # Newest-discovered first, so freshly scraped listings get real
    # dates/coordinates before older ones still waiting in the backlog.
    missing.sort(key=lambda item: item[1].get("first_seen", ""), reverse=True)
    print(f"DEBUG: {len(missing)} / {len(history)} listings not yet detail-enriched")

    batch = dict(missing[:MAX_LOOKUPS_PER_RUN])
    to_enrich = {lid: rec["latest"] for lid, rec in batch.items()}

    def checkpoint():
        sa.save_history(history)
        leads = sa.compute_leads(history)
        sa.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    deadline = time.monotonic() + TIME_BUDGET_SECONDS
    sa.fetch_update_dates(to_enrich, on_checkpoint=checkpoint, checkpoint_every=CHECKPOINT_EVERY, deadline=deadline)

    checkpoint()

    processed = sum(1 for l in to_enrich.values() if l.get("_detail_fetched"))
    print(f"DEBUG: detail-enriched {processed} listings this run "
          f"({len(missing) - processed} still queued for a future run)")


if __name__ == "__main__":
    main()
