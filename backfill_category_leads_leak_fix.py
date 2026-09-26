"""
Category-only patch: re-runs the SAME classify_listing() logic
backfill_category_review3_fixes.py uses (the PR's own final, all-4-review-
round authoritative script, per docs/decisions.md's matching entry), but
applies the resulting category/category_confidence changes as a targeted
in-place patch over CURRENT origin/main's data/leads_*.json and
data/history_*.json content, instead of regenerating leads_*.json via
compute_leads(). This is the fix for Missy's finding on PR #264's second
rebase pass (0d28605): compute_leads() recomputes wall-clock-dependent
days_on_market/score/pct_vs_area_avg fresh, silently drifting ~12,000
records' worth of those fields beyond the PR's declared category-only
scope.

Precondition: data/leads_*.json and data/history_*.json for all 6 governed
portals must already be checked out to origin/main's exact current content
before this script runs (done separately via `git checkout origin/main --
data/...`).

For each portal:
  1. Load history (main's current content).
  2. For every record, run classify_listing() exactly as
     backfill_category_review3_fixes.py does (same uses_description flag
     per portal).
  3. Where category or category_confidence differs from main's current
     value, update ONLY those two keys - in history[lid]["latest"] AND in
     the matching leads.json list entry (found by id) - leaving every
     other field (including days_on_market/score/pct_vs_area_avg/
     price_history/anything else) exactly as main already has it.
  4. Write history via save_history() (prune_snapshots() is a pure,
     idempotent price-dedup pass - no wall-clock dependency - so this is
     safe against already-pruned main content) and write leads.json
     directly (list order preserved, only the two fields touched).

Run with: python3 backfill_category_leads_leak_fix.py
"""

import category_classifier as cc
from geo_utils import load_json_any, save_json_any


PORTALS = [
    ("imoti.net", "scraper", False),
    ("alo.bg", "scraper_alo", False),
    ("imoti.bg", "scraper_imoti_bg", True),
    ("bazar.bg", "scraper_bazar", True),
    ("imot.bg", "scraper_imot", True),
    ("olx.bg", "scraper_olx", True),
]


def patch_portal(portal_label, module_name, uses_description):
    module = __import__(module_name)
    history = module.load_history()

    leads = load_json_any(module.LEADS_FILE)
    leads_by_id = {rec["id"]: rec for rec in leads}

    total = 0
    changed = 0
    was_high_now_changed = 0
    transitions = {}
    changed_ids = []

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
        changed_ids.append(lid)

        # In-place, category-only patch: history's `latest` sub-object.
        latest["category"] = category
        latest["category_confidence"] = confidence

        # Same in-place, category-only patch: the matching leads.json
        # entry, WITHOUT touching days_on_market/score/pct_vs_area_avg/
        # anything else - this is the actual fix, replacing
        # backfill_category_review3_fixes.py's compute_leads() call.
        lead_rec = leads_by_id.get(lid)
        if lead_rec is not None:
            lead_rec["category"] = category
            lead_rec["category_confidence"] = confidence

    print(f"=== {portal_label} ({module_name}) ===")
    print(f"DEBUG: total records: {total}")
    print(f"DEBUG: changed (category or confidence): {changed}")
    print(f"DEBUG: of those, previously 'high' confidence (confidently WRONG before this fix): {was_high_now_changed}")
    print("DEBUG: transitions (old_category -> new_category):")
    for pair, count in sorted(transitions.items(), key=lambda kv: -kv[1]):
        print(f"   {pair}: {count}")

    if changed:
        module.save_history(history)
        save_json_any(module.LEADS_FILE, leads)
        print(f"DEBUG: wrote category-only patch for {changed} records to {module.HISTORY_FILE} and {module.LEADS_FILE}")
    else:
        print("DEBUG: nothing changed - history/leads left untouched")
    print()

    return total, changed, was_high_now_changed, changed_ids


def main():
    total_all = 0
    changed_all = 0
    high_all = 0
    all_changed_ids = {}
    for portal_label, module_name, uses_description in PORTALS:
        total, changed, was_high, changed_ids = patch_portal(portal_label, module_name, uses_description)
        total_all += total
        changed_all += changed
        high_all += was_high
        all_changed_ids[portal_label] = changed_ids

    print("=== TOTAL ACROSS ALL 6 PORTALS ===")
    print(f"DEBUG: total records checked: {total_all}")
    print(f"DEBUG: total changed: {changed_all}")
    print(f"DEBUG: of those, previously 'high' confidence (confidently wrong before): {high_all}")

    return all_changed_ids


if __name__ == "__main__":
    main()
