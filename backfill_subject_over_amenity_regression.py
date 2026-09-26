"""
One-off remediation for Ready's second assignment (docs/decisions.md
2026-09-23 "Ready's second assignment" entry) - persists the effect of
category_classifier.py's two new fixes (_resolve_subject_over_amenity's
title/url double-counting fix, and the _UPI_RE word-boundary fix) onto the
3 portals that already called classify_listing() BEFORE this pass
(imoti.net, alo.bg, imoti.bg) - the same "recompute every already-committed
record with the now-fixed classifier, diff, report" pattern
backfill_category_imoti_net.py and backfill_garage_tiebreak_regression.py
both already established, needed here because a classifier bug fix alone
never touches already-stored data on its own.

Full recompute (not scoped to a category=="X" AND confidence=="low"
pre-filter like backfill_garage_tiebreak_regression.py) because this fix's
own real effect is NOT limited to already-low-confidence records - the
most concerning finding from this pass was 87 alo.bg records that were
"high" confidence and CONFIDENTLY WRONG (both title and url agreed on the
wrong, amenity-driven category, e.g. "2-стаен, тухлен, Паркомясто,
обзаведен" filed as "garage" with "high" confidence) - a
category=="garage" AND confidence=="low" pre-filter would have missed
every one of those, the same way it would have missed them before this
fix existed. See docs/decisions.md for the full, sampled evidence this is
based on.

Purely local: title/description/url are already stored in each portal's
own data/history*.json. Updates ONLY latest.category/
latest.category_confidence in place - never any other field. Regenerates
each portal's own leads*.json via that portal's own compute_leads().

Run with: python3 backfill_subject_over_amenity_regression.py
"""

import category_classifier as cc
from geo_utils import save_json_any


# Each entry: (portal label, scraper module import name, whether that
# scraper's own classify_listing() call includes description) - same
# mapping backfill_garage_tiebreak_regression.py already established.
PORTALS = [
    ("imoti.net", "scraper", False),
    ("alo.bg", "scraper_alo", False),
    ("imoti.bg", "scraper_imoti_bg", True),
]


def backfill_portal(portal_label, module_name, uses_description):
    module = __import__(module_name)
    history = module.load_history()

    total = 0
    changed = 0
    was_high_now_changed = 0
    transitions = {}
    changed_examples = []

    for lid, rec in history.items():
        latest = rec.get("latest")
        if not latest:
            continue
        total += 1
        before_cat = latest.get("category")
        before_conf = latest.get("category_confidence")

        description = latest.get("description") if uses_description else None
        category, confidence, reason = cc.classify_listing(
            title=latest.get("title"), description=description, url=latest.get("url")
        )
        if category == before_cat and confidence == before_conf:
            continue

        changed += 1
        transitions[(before_cat, category)] = transitions.get((before_cat, category), 0) + 1
        if before_conf == "high":
            was_high_now_changed += 1
        if len(changed_examples) < 15:
            changed_examples.append((lid, before_cat, before_conf, category, confidence, reason, latest.get("title")))

        latest["category"] = category
        latest["category_confidence"] = confidence

    print(f"=== {portal_label} ({module_name}) ===")
    print(f"DEBUG: total records: {total}")
    print(f"DEBUG: changed (category or confidence): {changed}")
    print(f"DEBUG: of those, previously 'high' confidence (confidently WRONG before this fix): {was_high_now_changed}")
    print("DEBUG: transitions (old_category -> new_category):")
    for pair, count in sorted(transitions.items(), key=lambda kv: -kv[1]):
        print(f"   {pair}: {count}")
    print("DEBUG: sample of changed records:")
    for ex in changed_examples:
        print(f"  {ex}")

    if changed:
        module.save_history(history)
        leads = module.compute_leads(history)
        save_json_any(module.LEADS_FILE, leads)
        print(f"DEBUG: wrote {len(leads)} leads to {module.LEADS_FILE}")
    else:
        print("DEBUG: nothing changed - history/leads left untouched")
    print()

    return total, changed, was_high_now_changed


def main():
    total_all = 0
    changed_all = 0
    high_all = 0
    for portal_label, module_name, uses_description in PORTALS:
        total, changed, was_high = backfill_portal(portal_label, module_name, uses_description)
        total_all += total
        changed_all += changed
        high_all += was_high

    print("=== TOTAL ACROSS imoti.net + alo.bg + imoti.bg ===")
    print(f"DEBUG: total records checked: {total_all}")
    print(f"DEBUG: total changed: {changed_all}")
    print(f"DEBUG: of those, previously 'high' confidence (confidently wrong before): {high_all}")


if __name__ == "__main__":
    main()
