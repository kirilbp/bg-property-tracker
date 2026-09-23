"""
One-off remediation for the garage/parking-amenity tiebreak bug fixed in
category_classifier.py (docs/decisions.md 2026-09-23 "Ready" entry,
.claude/agents/ready.md): CATEGORY_ORDER = ["garage", "shop", "business",
"land", "house", "flat"] was used as an unconditional tiebreak whenever two
categories scored exactly equal, so "garage" won every tie by list position
alone - including the dominant real case, confirmed by sampling the
low-confidence garage pool, where a parking space or garage is mentioned as
an attached AMENITY inside a real flat/house/shop/business listing's own
title ("Тристаен апартамент ... с ПАРКОМЯСТО", "Етаж от къща с гараж и
паркомясто"). classify_listing() now resolves a garage/X tie by which tied
category's own keyword appears leftmost in the title (see
category_classifier.py's module comment above CATEGORY_ORDER for the full
reasoning and why it doesn't just flip the order globally).

This is the one-off cleanup for the records already stored with the old,
buggy classification before that fix landed - unlike
backfill_category_imoti_net.py (which reclassified every imoti.net record,
migrating between two entirely different classifiers), this only touches
records whose CURRENT latest.category is "garage" AND
latest.category_confidence is "low" - the exact, provably-affected target
set (a "high"-confidence garage record never came from a tie, so the fix
can't have changed it; confirmed by running the full 118k-record population
actually classified by category_classifier.classify_listing() through the
fixed code and diffing against what's stored - zero changes for any record
whose old category wasn't "garage", see docs/decisions.md).

Covers the three portals whose scrapers actually call
category_classifier.classify_listing() (confirmed by reading each
scraper's own classify_listing() call site - the other portals either
hardcode confidence, like homes.bg, or use the separate, older
geo_utils.classify_category() 4-bucket classifier, like bazar.bg/bcpea/
imot.bg/olx.bg, which this fix doesn't touch at all):
  - imoti.net  (scraper.py,          data/history.json,          title+url)
  - alo.bg     (scraper_alo.py,      data/history_alo.json,      title+url)
  - imoti.bg   (scraper_imoti_bg.py, data/history_imoti_bg.json, title+description+url)

Recomputes each target record's category the same way each scraper's own
fetch loop does, from that record's own already-stored fields - no live
fetch needed (same reasoning as backfill_apartment_category_regression.py:
both are already scraped/stored before any network call). One caveat for
imoti.bg specifically: scraper_imoti_bg.py's own call appends a transient
"_category_slug" string to the url signal that is popped off and never
persisted to history, so it can't be reproduced from stored data alone;
this backfill uses title+description+url (without that slug) instead - the
best-effort signal actually available from what's on disk. Checked live:
this reproduces the stored category/confidence exactly (zero mismatches)
for all 6 of imoti.bg's currently-affected records, so the missing slug
doesn't appear to change the outcome for this portal's actual affected set,
but it's called out here in case a future, larger imoti.bg-affected pool
ever behaves differently.

Updates ONLY latest.category/latest.category_confidence in place - never
snapshots, first_seen, price, description, or any other field. Regenerates
each portal's own leads*.json via that portal's own compute_leads() (not a
hand-rolled reimplementation), the same reasoning as
backfill_apartment_category_regression.py: leads.json's cross-listing
aggregates (e.g. area_avg_price_per_sqm) were themselves computed over the
wrong category bucket for every affected listing, not just its own record.

Run with: python3 backfill_garage_tiebreak_regression.py
"""

import json

import category_classifier as cc


# Each entry: (portal label, scraper module import name, whether that
# scraper's own classify_listing() call includes description).
PORTALS = [
    ("imoti.net", "scraper", False),
    ("alo.bg", "scraper_alo", False),
    ("imoti.bg", "scraper_imoti_bg", True),
]


def backfill_portal(portal_label, module_name, uses_description):
    module = __import__(module_name)

    history = module.load_history()

    before_garage_low = 0
    changed = 0
    after_counts = {}
    changed_examples = []

    for lid, rec in history.items():
        latest = rec.get("latest")
        if not latest:
            continue
        if latest.get("category") != "garage" or latest.get("category_confidence") != "low":
            continue

        before_garage_low += 1
        description = latest.get("description") if uses_description else None
        category, confidence, _ = cc.classify_listing(
            title=latest.get("title"), description=description, url=latest.get("url")
        )
        if category == latest.get("category") and confidence == latest.get("category_confidence"):
            continue

        latest["category"] = category
        latest["category_confidence"] = confidence
        changed += 1
        after_counts[category] = after_counts.get(category, 0) + 1
        if len(changed_examples) < 8:
            changed_examples.append((lid, latest.get("title"), category, confidence))

    # Full post-fix category distribution for this portal, not just the
    # changed subset, for a real before/after.
    full_counts_after = {}
    portal_total = 0
    for rec in history.values():
        latest = rec.get("latest") or {}
        portal_total += 1
        full_counts_after[latest.get("category")] = full_counts_after.get(latest.get("category"), 0) + 1

    print(f"=== {portal_label} ({module_name}) ===")
    print(f"DEBUG: records with latest.category=='garage' AND latest.category_confidence=='low' before this run: {before_garage_low}")
    print(f"DEBUG: reclassified: {changed}")
    print(f"DEBUG: new categories assigned (from the {changed} corrected records): {after_counts}")
    print(f"DEBUG: {portal_label} full category distribution after fix ({portal_total} total): {full_counts_after}")
    print(f"DEBUG: sample of corrected records (id, title, new category, new confidence):")
    for lid, title, category, confidence in changed_examples:
        print(f"  {lid}: {title!r} -> {category} ({confidence})")

    if changed:
        module.save_history(history)
        leads = module.compute_leads(history)
        module.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"DEBUG: wrote {len(leads)} leads to {module.LEADS_FILE}")
    else:
        print("DEBUG: nothing changed - history/leads left untouched")
    print()

    return before_garage_low, changed


def main():
    total_before = 0
    total_changed = 0
    for portal_label, module_name, uses_description in PORTALS:
        before, changed = backfill_portal(portal_label, module_name, uses_description)
        total_before += before
        total_changed += changed

    print("=== TOTAL ACROSS ALL 3 PORTALS ===")
    print(f"DEBUG: total garage/low-confidence records checked: {total_before}")
    print(f"DEBUG: total reclassified: {total_changed}")
    print(f"DEBUG: total left as garage (genuinely low-confidence garage, e.g. single_signal_only, or a garage/X tie where garage's own keyword IS the title's leftmost subject): {total_before - total_changed}")


if __name__ == "__main__":
    main()
