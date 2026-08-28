"""
Fills in lat/lng and description for bazar.bg listings that
scraper_bazar.py's nationwide grid crawl left unenriched.

scraper_bazar.py's nationwide conversion deliberately stopped visiting
every listing's own detail page during the main scrape (see its module
docstring) - nationwide scale (29 cities vs. the old Sofia-only) made that
no longer affordable in a single run. It now only does the fast grid
crawl; category is still set immediately there (a pure title-keyword
classifier, no network needed), but lat/lng - which live only on each
listing's own detail page as data-lat/data-long attributes - are left
unset, as is description.

This script is the other half: a separate, resumable pass that visits
each listing's own page (the same plain, non-JS HTTP fetch + Focus-backend
#see_on_map parsing the old inline code used) for whatever hasn't been
checked yet, prioritized newest-first (by first_seen) so freshly
discovered listings get real coordinates/description before older ones
queue behind them - same pattern backfill_detail_alo.py already
established. description is extracted from the page's own ld+json block
(geo_utils.extract_description_ldjson()) - live-verified to carry the
real agent/seller-written text, not just an auto-generated summary.

A listing is marked "coords_checked" once its detail page has actually
been visited, regardless of whether that page turned up real coordinates
or a description - some bazar.bg listings genuinely have neither on their
own page, and without an explicit marker those would get needlessly
re-visited by every future run instead of being treated as done.

Scheduled hourly (see backfill-detail-bazar.yml) - previously
workflow_dispatch-only since it only filled in map coordinates, a
lower-priority field; now that it also fills in description (real
listing content, not just a map pin), it needs to actually keep running
rather than wait to be re-dispatched by hand.
"""

import json
import time

import scraper_bazar as sb
from geo_utils import extract_coords_bazar, extract_description_ldjson

REQUEST_DELAY_SECONDS = 1.0
# Caps a single run's detail-page-visit count so this can't itself balloon
# into an unbounded, multi-hour job at nationwide scale - meant to be
# re-run repeatedly (by hand, or on a schedule) until the backlog clears.
# 1500 (the original value, from back when this ran via workflow_dispatch
# with no explicit timeout) doesn't reliably fit inside the 45-minute
# timeout added when this was converted to run hourly: at ~1.5-2.5s/listing
# (1.0s delay + real fetch time), 1500 listings is 37.5-62.5 minutes - a
# real run timed out and got killed partway through. 1000 comfortably fits
# with margin (25-42 minutes).
MAX_LOOKUPS_PER_RUN = 1000


def main():
    history = sb.load_history()

    missing = [
        (lid, rec) for lid, rec in history.items()
        if not rec.get("latest", {}).get("coords_checked")
    ]
    missing.sort(key=lambda item: item[1].get("first_seen", ""), reverse=True)
    print(f"DEBUG: {len(missing)} / {len(history)} listings not yet detail-checked")

    batch = missing[:MAX_LOOKUPS_PER_RUN]
    filled = 0
    for i, (lid, rec) in enumerate(batch, 1):
        latest = rec["latest"]
        time.sleep(REQUEST_DELAY_SECONDS)
        html = sb.fetch_html(latest["url"])
        latest["coords_checked"] = True
        if html is not None:
            coords = extract_coords_bazar(html)
            if coords:
                latest["lat"] = coords["lat"]
                latest["lng"] = coords["lng"]
                filled += 1
            description = extract_description_ldjson(html)
            if description:
                latest["description"] = description
        if i % 200 == 0:
            print(f"DEBUG: checked {i}/{len(batch)} listings")

    sb.save_history(history)

    leads = sb.compute_leads(history)
    sb.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    processed = len(batch)
    print(f"DEBUG: filled coords for {filled} / {processed} checked this run "
          f"({len(missing) - processed} still queued for a future run)")


if __name__ == "__main__":
    main()
