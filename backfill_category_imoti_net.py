"""
One-off remediation for docs/backlog.md item 5: reclassifies every already-
committed imoti.net listing's "category" using category_classifier.
classify_listing() instead of the old geo_utils.classify_category() bug
that left 100% of them "apartment" (see scraper.py's fetch_listings_page()
comment for the full root-cause story, and docs/decisions.md's 2026-09-22
entry for the investigation).

Purely local: title and url are already stored in data/history.json for
every listing (both are used at scrape time, before any network call), so
this needs no live fetch to imoti.net at all - it re-derives "category"/
"category_confidence" for every record already on disk and regenerates
data/leads.json from the corrected history, the same compute_leads() pass
scraper.py's own main() already uses. Going forward, scraper.py's own fix
means every future scrape already classifies correctly at scrape time -
this script is only needed once, to fix what's already committed instead
of waiting for every listing to naturally get re-crawled (some listings
currently "removed" never will be, since fetch_listings() only updates
records still found in a live grid crawl).
"""

import json

import scraper as si
from category_classifier import classify_listing


def main():
    history = si.load_history()

    changed = 0
    unchanged = 0
    before_counts = {}
    after_counts = {}
    for rec in history.values():
        latest = rec.get("latest")
        if not latest or latest.get("portal") != "imoti.net":
            continue
        before = latest.get("category")
        before_counts[before] = before_counts.get(before, 0) + 1

        category, confidence, _ = classify_listing(title=latest.get("title"), url=latest.get("url"))
        latest["category"] = category
        latest["category_confidence"] = confidence
        after_counts[category] = after_counts.get(category, 0) + 1

        if category != before:
            changed += 1
        else:
            unchanged += 1

    print(f"DEBUG: reclassified {changed} listings, {unchanged} already matched (no-op)")
    print(f"DEBUG: category counts before: {before_counts}")
    print(f"DEBUG: category counts after: {after_counts}")

    si.save_history(history)
    leads = si.compute_leads(history)
    si.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DEBUG: wrote {len(leads)} leads to {si.LEADS_FILE}")


if __name__ == "__main__":
    main()
