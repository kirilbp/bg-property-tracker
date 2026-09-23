"""
One-off remediation for issue #243 / docs/missy-findings/2026-09-23.md:
PR #199 (merged 2026-09-22T16:15:40Z) fixed imoti.net's "100%-apartment"
classifier bug by correcting `latest.category` in place on `main` for
every imoti.net listing, with no new snapshot appended (a deliberate
data-only correction - see backfill_category_imoti_net.py, the script
that did that original fix, and merge_history_conflict.py's module
docstring for the full incident). Four hours later, commit `d76d607`
("Update listings (large sites)") silently reintroduced it for 17,680 of
imoti.net's 27,251 listings: a scrape-large.yml run that had checked out
`main` BEFORE PR #199 merged (so was still running the old, buggy
classifier) hit its `git pull --rebase` conflict AFTER PR #199 had
already landed, and the OLD version of merge_history_conflict.py's
per-record "latest" merge picked that run's whole `latest` dict because
its own snapshot was chronologically newer - reintroducing its stale
`category: "apartment"` and silently discarding PR #199's fix.

merge_history_conflict.py itself is now fixed (see its own module
docstring's "'latest' is now a per-field merge" section) so this can't
happen silently again going forward. This script is the one-off cleanup
for the ~17,680 records already corrupted on disk before that fix landed.

Deliberately narrow, unlike backfill_category_imoti_net.py (which
reclassified every imoti.net record - the right call for that PR, which
was migrating the classifier itself): this only touches imoti.net records
whose CURRENT `latest.category` is literally `"apartment"` - a value
category_classifier.classify_listing() can never produce (it only ever
returns garage/shop/business/land/house/flat - confirmed by reading its
source), so every one of these is provably wrong, not just suspected, and
touching only this exact, unambiguous target set means every other
already-correctly-classified imoti.net record (and every other portal's
data) is left byte-for-byte alone. Recomputes each target record's
category the same way scraper.py's own fetch_listings_page() does -
`classify_listing(title=..., url=...)` from that record's own already-
stored title/url, no live fetch needed (see backfill_category_imoti_net.py
for why that's safe - both are already scraped/stored before any network
call, and this project's egress proxy blocks imoti.net live anyway).
Updates ONLY `latest.category`/`latest.category_confidence` in place -
never snapshots, first_seen, price, or any other field.

data/leads.json IS regenerated (via scraper.py's own compute_leads(), not
a hand-rolled reimplementation) rather than left to "self-heal on the next
scrape run" - unlike merge_history_conflict.py's deliberate choice not to
write a leads*.json merger (a real, argued design decision for THAT
script, which only ever has two conflicting in-memory sides to merge and
no live classifier available to it in the same call shape), here the full,
now-corrected history.json is already on disk and compute_leads() is a
pure, cheap, already-trusted function of it - regenerating leads.json now
is the same step backfill_category_imoti_net.py already took for the
original fix, not new machinery, and it matters because compute_leads()
also derives cross-listing aggregates (e.g. area_avg_price_per_sqm) that
were themselves polluted by the corrupted category on every OTHER
imoti.net listing's bucket, not just the 17,680 corrected records - a
partial, per-record leads.json patch would leave those aggregates wrong.
"""

import json

import scraper as si
from category_classifier import classify_listing


def main():
    history = si.load_history()

    before_apartment = 0
    changed = 0
    after_counts = {}
    changed_examples = []

    for lid, rec in history.items():
        latest = rec.get("latest")
        if not latest or latest.get("portal") != "imoti.net":
            continue
        if latest.get("category") != "apartment":
            continue

        before_apartment += 1
        category, confidence, _ = classify_listing(title=latest.get("title"), url=latest.get("url"))
        latest["category"] = category
        latest["category_confidence"] = confidence
        after_counts[category] = after_counts.get(category, 0) + 1
        changed += 1
        if len(changed_examples) < 5:
            changed_examples.append((lid, latest.get("title"), latest.get("url"), category))

    # Recount imoti.net's full category distribution after the fix, to
    # report a real before/after rather than just the changed subset.
    after_full_counts = {}
    imoti_net_total = 0
    for rec in history.values():
        latest = rec.get("latest") or {}
        if latest.get("portal") != "imoti.net":
            continue
        imoti_net_total += 1
        after_full_counts[latest.get("category")] = after_full_counts.get(latest.get("category"), 0) + 1

    print(f"DEBUG: imoti.net records with latest.category == 'apartment' before this run: {before_apartment}")
    print(f"DEBUG: reclassified {changed} records")
    print(f"DEBUG: new categories assigned (from the {changed} corrected records): {after_counts}")
    print(f"DEBUG: imoti.net full category distribution after fix ({imoti_net_total} total): {after_full_counts}")
    print("DEBUG: sample of corrected records (id, title, url, new category):")
    for lid, title, url, category in changed_examples:
        print(f"  {lid}: {title!r} {url!r} -> {category}")

    si.save_history(history)
    leads = si.compute_leads(history)
    si.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DEBUG: wrote {len(leads)} leads to {si.LEADS_FILE}")


if __name__ == "__main__":
    main()
