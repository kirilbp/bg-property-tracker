"""
One-off remediation for Missy's PR #264 THIRD review (2026-09-23) of
Ready's exhaustive category-allocation audit - persists the effect of
category_classifier.py's three round-3 fixes:

1. _ZEMYA_IMOT_RE cadastral-registry-boilerplate guard: the round-2 fix's
   own new "поземлен имот" keyword matched standard Bulgarian cadastral-
   registry boilerplate ("...построена в поземлен имот с идентификатор №
   67338.516.1...") describing the land parcel UNDERNEATH an unrelated
   building, not the property being sold - confirmed live, imotibg_515292
   ("Търговско помещение, Република", a 460m² commercial food-service
   space) was wrongly flipped flat->land over this. Fixed with a negative
   lookahead that excludes only the "поземлен имот" + "с идентификатор"
   boilerplate shape, re-verified against all 15 sitewide records matching
   that phrase (12 genuine land + 2 genuine business unaffected, this one
   now correctly flat again).

2. _demote_context_only_house_signals Part B title-borrowing guard: Part B
   let a signal with no land competitor of its own (like a title whose
   only house evidence is the ambiguous "къщи"/"вили" plural) borrow the
   "land wins" verdict from ANY directly-demoted sibling signal, including
   the TITLE, even when the title's own plural mention was genuinely the
   ad's real subject ("Продавам две къщи в село Раковски" - reproduced by
   Missy, not found live in the current population). Fixed by requiring
   the title's own plural mention to be accompanied by a locational/
   distance marker ("от", "до", "близо до", "граничещ...", "съседен...",
   "покрай") before it's eligible for Part B borrowing at all -
   _HOUSE_PROXIMITY_MARKER_RE / _has_house_proximity_context.

3. Digit-glued word-boundary fix: Python's \\b doesn't separate an ASCII
   digit from a following Cyrillic letter (both are \\w), so \\b-bounded
   "къщи"/"вили"/"упи"/"ниви" regexes silently missed a real, live
   Bulgarian shorthand ("Продава 2къщи в с.Соволяно..." - olx_9ECK4,
   wrongly flat/low). Fixed with a shared _letter_bounded() helper bounding
   against letters specifically rather than \\w's broader digit-inclusive
   class.

Covers ALL SIX portals category_classifier.classify_listing() governs, same
population every prior backfill in this investigation covered. Full
recompute (not scoped to a category/confidence pre-filter) for the same
reason those backfills established - a classifier fix can change "high"
confidence verdicts too, not just "low" ones.

Purely local: title/description/url are already stored in each portal's
own data/history_*.json. Updates ONLY latest.category/
latest.category_confidence in place - never any other field. Regenerates
each portal's own leads*.json via that portal's own compute_leads().

Run with: python3 backfill_category_review3_fixes.py
"""

import json

import category_classifier as cc


PORTALS = [
    ("imoti.net", "scraper", False),
    ("alo.bg", "scraper_alo", False),
    ("imoti.bg", "scraper_imoti_bg", True),
    ("bazar.bg", "scraper_bazar", True),
    ("imot.bg", "scraper_imot", True),
    ("olx.bg", "scraper_olx", True),
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
    print("DEBUG: all changed records:")
    for ex in changed_examples:
        print(f"  {ex}")

    if changed:
        module.save_history(history)
        leads = module.compute_leads(history)
        module.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
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

    print("=== TOTAL ACROSS ALL 6 PORTALS ===")
    print(f"DEBUG: total records checked: {total_all}")
    print(f"DEBUG: total changed: {changed_all}")
    print(f"DEBUG: of those, previously 'high' confidence (confidently wrong before): {high_all}")


if __name__ == "__main__":
    main()
