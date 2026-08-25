"""
Fills in site_posted_at/lat,lng for imoti.net listings that scraper.py's
nationwide grid crawl left unenriched.

scraper.py's fetch_listings() deliberately stopped visiting every
listing's own page during the main scrape (see its module docstring) -
nationwide scale (~21,700 listings vs. the old Sofia-only estimate this
was originally sized for) made that no longer affordable in a single run:
a real production run timed out at the workflow's 300-minute step limit
with the detail pass only 3,600/21,719 listings in, discarding that
entire run's freshly-scraped grid data too, since nothing gets saved
until after both steps finish. It now only does the fast grid crawl
(category is already set there - a pure title-keyword classifier, no
network needed) and leaves site_posted_at/lat,lng unset.

This script is the other half: a separate, resumable pass that visits
each listing's own page (scraper.py's own fetch_listing_dates(), reused
unchanged) for whatever hasn't been checked yet, prioritized newest-first
(by first_seen) so freshly discovered listings get real dates/coordinates
before older ones queue behind them - same pattern backfill_detail_alo.py
already established.

A listing is marked "detail_checked" once its detail page has actually
been visited, regardless of whether that page turned up a real date or
coordinates - some listings genuinely have neither on their own page, and
without an explicit marker those would get needlessly re-visited by every
future run instead of being treated as done.

Not scheduled automatically - re-run it by hand (or on a cron, later)
until the "not yet checked" count reaches zero, same as any other
backfill.
"""

import json

import scraper as si

# Matches homes.bg's/imot.bg's/olx.bg's own geocode-backfill cap - bounds a
# single run's detail-page-visit count so this can't itself balloon into
# an unbounded, multi-hour job at nationwide scale.
MAX_LOOKUPS_PER_RUN = 1500


def main():
    history = si.load_history()

    missing = [
        (lid, rec) for lid, rec in history.items()
        if not rec.get("latest", {}).get("detail_checked")
    ]
    missing.sort(key=lambda item: item[1].get("first_seen", ""), reverse=True)
    print(f"DEBUG: {len(missing)} / {len(history)} listings not yet detail-checked")

    batch = dict(missing[:MAX_LOOKUPS_PER_RUN])
    to_check = {lid: rec["latest"] for lid, rec in batch.items()}
    si.fetch_listing_dates(to_check)

    si.save_history(history)

    leads = si.compute_leads(history)
    si.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    processed = len(batch)
    print(f"DEBUG: detail-checked {processed} listings this run "
          f"({len(missing) - processed} still queued for a future run)")


if __name__ == "__main__":
    main()
