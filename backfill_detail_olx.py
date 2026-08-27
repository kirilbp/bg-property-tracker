"""
Fills in description for olx.bg listings that scraper_olx.py's grid crawl
never visits the detail page for.

olx.bg's own search-result cards carry no free-text description at all
(only price/area/sqm/update-date) - the real, seller-written description
sits on each listing's own detail page, as the "description" key of a
<script type="application/ld+json"> block. Confirmed live via
probe_descriptions.py: a plain requests.get() gets blocked outright
(403, same Akamai-style edge check scraper_olx.py's own grid crawl
already works around with Playwright), but a normal Playwright/Chromium
visit - no stealth tricks needed - gets through and returns the real,
full description.

This script is a new, separate, resumable pass - olx.bg's grid crawl has
never visited individual detail pages at all - visiting each listing's own
page (scraper_olx.py's fetch_listing_detail(), a lighter-weight sibling of
the grid crawl's own fetch_html() that skips the lazy-load scroll loop,
which only matters on a search-results page) for whatever hasn't been
checked yet, prioritized newest-first (by first_seen) so freshly
discovered listings get a real description before older ones queue behind
them - same pattern backfill_detail_alo.py/backfill_detail_bazar.py/
backfill_detail_bcpea.py/backfill_detail_imot.py already established.

A listing is marked "detail_checked" once its detail page has actually
been visited, regardless of whether that page turned up a real
description - without an explicit marker those would get needlessly
re-visited by every future run instead of being treated as done.

Scheduled hourly (see backfill-detail-olx.yml) - a fresh full backlog
clears over a few days at this run's cap, after which each run only has
to keep up with that day's newly-discovered listings, a much smaller
number.
"""

import json

import scraper_olx as so

# One shared Playwright page reused across the whole batch (see
# fetch_listing_details()'s own comment) keeps the per-listing cost close
# to a plain page navigation.
MAX_LOOKUPS_PER_RUN = 500


def main():
    history = so.load_history()

    missing = [
        (lid, rec) for lid, rec in history.items()
        if not rec.get("latest", {}).get("detail_checked")
    ]
    missing.sort(key=lambda item: item[1].get("first_seen", ""), reverse=True)
    print(f"DEBUG: {len(missing)} / {len(history)} listings not yet detail-checked")

    batch = missing[:MAX_LOOKUPS_PER_RUN]
    to_check = [rec["latest"] for _, rec in batch]
    so.fetch_listing_details(to_check)

    so.save_history(history)

    leads = so.compute_leads(history)
    so.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    processed = len(batch)
    print(f"DEBUG: detail-checked {processed} listings this run "
          f"({len(missing) - processed} still queued for a future run)")


if __name__ == "__main__":
    main()
