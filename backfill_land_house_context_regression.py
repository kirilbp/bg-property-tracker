"""
One-off remediation for Missy's PR #264 review (2026-09-23, BLOCKING) of
Ready's exhaustive category-allocation audit - persists the effect of
category_classifier.py's fix for the two real bug classes her review found
already live in already-committed data:

1. "вили" substring-collision bug: "вили" (added as a plain substring, no
   word-boundary guard) is itself a literal substring of "павилион"
   ("pavilion" - a small commercial kiosk, unrelated to houses) and several
   other real, unrelated words ("привилидж"/"цивилизация", any past-tense
   verb ending in "-вили"). "къщи" (this fix's sibling keyword) had the
   same latent risk ("автокъщи" - car dealerships, "вкъщи" - "at home").
   Fixed with _KASHTI_RE/_VILI_RE, proper \\b word-boundary regexes, the
   same way _UPI_RE already fixed this exact class of bug for "упи".

2. Land-vs-house context bug: a genuine LAND-plot listing routinely
   mentions neighboring or future-planned houses as location CONTEXT, not
   as the property actually being sold ("Поземлен имот... на 20 метра от
   къщи", "Парцел... до вили", "проект за шест къщи"). Fixed with
   _demote_context_only_house_signals - see that function's own module
   comment in category_classifier.py for the full position-based design
   (and the two real regressions its title/description asymmetry exists
   to avoid - a naive first cut wrongly flipped genuine multi-house
   listings like "Две къщи с общ парцел" to "land").

Also adds two small land-keyword vocabulary gaps found necessary to
actually resolve the real cases above (without them, "land" never had any
competing evidence at all for several of Missy's own examples): "поземлен
имот" (a generic, very common land-listing phrase, distinct from the
already-present "земеделски имот" which is specifically AGRICULTURAL
land) and "ниви" (plural of "нива" - the exact same feminine noun -а/-и
pluralization gap "къщи"/"вили" needed fixing on the house side, just
never previously found on the land side).

Covers ALL SIX portals category_classifier.classify_listing() governs
(confirmed by reading each scraper's own call site) - the same population
Ready's original PR #264 touched, per Missy's explicit instruction to
re-sample the ACTUAL full affected population, not just the small alo.bg
subset the original PR's own verification scoped to:
  - imoti.net (scraper.py,          data/history.json,          title+url)
  - alo.bg    (scraper_alo.py,      data/history_alo.json,      title+url)
  - imoti.bg  (scraper_imoti_bg.py, data/history_imoti_bg.json, title+description+url)
  - bazar.bg  (scraper_bazar.py,    data/history_bazar.json,    title+description+url)
  - imot.bg   (scraper_imot.py,     data/history_imot.json,     title+description+url)
  - olx.bg    (scraper_olx.py,      data/history_olx.json,      title+description+url)

Full recompute (not scoped to a category=="X" AND confidence=="low"
pre-filter) - deliberately, because Missy's own review's most concerning
finding was NOT limited to already-low-confidence records (53 of the
olx.bg records were "high" confidence and CONFIDENTLY WRONG). Same pattern
backfill_subject_over_amenity_regression.py and
backfill_category_bazar_imot_olx_migration.py already established.

Purely local: title/description/url are already stored in each portal's
own data/history_*.json. Updates ONLY latest.category/
latest.category_confidence in place - never any other field. Regenerates
each portal's own leads*.json via that portal's own compute_leads().

Run with: python3 backfill_land_house_context_regression.py
"""

import json

import category_classifier as cc


# Each entry: (portal label, scraper module import name, whether that
# scraper's own classify_listing() call includes description) - same
# mapping the prior two backfills in this same investigation established.
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
