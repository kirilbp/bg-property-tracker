"""
One-off remediation for Ready's second assignment (docs/decisions.md
2026-09-23 "Ready's second assignment" entry) - migrates bazar.bg, imot.bg,
and olx.bg's already-committed listings from the old geo_utils.
classify_category() 4-bucket scorer (land/house/commercial/apartment,
apartment-default on no match) to the shared, 6-bucket category_classifier.
classify_listing() every other nationwide scraper already uses (imoti.net,
alo.bg, imoti.bg) - the same migration backfill_category_imoti_net.py did
for imoti.net alone (docs/backlog.md item 5), extended to the 3 portals
that hadn't been migrated yet (sync_to_supabase.py's own CATEGORY_TO_BUCKET
comment already anticipated this: "'apartment'/'commercial' are
classify_category()'s old 4-value output..., still produced by portals not
yet migrated to the nationwide expansion's category_classifier.py").

Root cause this fixes (full detail in docs/decisions.md): geo_utils.
classify_category() has no "garage" or "shop" concept at all (its
CATEGORY_KEYWORDS only has land/house/commercial/apartment) and silently
defaults every unmatched title to "apartment" - already flagged as
KNOWN-BAD for sales.bcpea.org in that function's own docstring, but never
checked for bazar.bg/imot.bg/olx.bg, which use the exact same function for
their real, live-facing category. Confirmed real and quantified by
sampling (docs/decisions.md): imot.bg alone had 342 titles literally
opening "Продава ГАРАЖ, ..."/"Продава ПАРКОМЯСТО, ..." filed under
"apartment" for want of any garage category to file them under at all;
olx.bg had a comparable pattern at larger scale; bazar.bg (apartments-only
scope by design, so its listings are ALL genuinely apartments) had ~183
genuine apartment listings wrongly pulled to "commercial" by an
attached-amenity or place-name word ("АТЕЛИЕ" - a real Bulgarian synonym
for a studio-type apartment already correctly in category_classifier's OWN
"flat" keyword list, but miscategorized as "commercial" in geo_utils' own
older, narrower keyword list; "Бизнес хотел" - a real Varna apartment-
complex NAME, not a hotel-for-sale).

This migration was validated (NOT run blind) against a pre-migration
regression this same investigation found and fixed FIRST, before ever
running this script: classify_listing()'s own
"double-counting via url-slug echoing the title" bug (Ready's first
assignment's own disclosed, not-yet-fixed residual gap) and a "упи" keyword
word-boundary gap (CATEGORY_KEYWORDS["land"]'s old " упи " padding never
matched a title that OPENS with "УПИ", the single most common real
phrasing) - both root-caused and fixed in category_classifier.py itself
(see its own module comments for _resolve_subject_over_amenity and
_UPI_RE) BEFORE this migration ran, specifically because dry-running this
migration against the unfixed classifier surfaced them (e.g. a real olx.bg
house listing "Продавам двуетажна къща ... с гараж" was reclassifying to
"garage" outright, "high" confidence, before that fix).

Purely local, no live fetch: title/url/description for every record are
already stored in data/history_bazar.json / data/history_imot.json /
data/history_olx.json - description is used where present (title+url
otherwise), same "best-effort from what's actually on disk" reasoning
backfill_garage_tiebreak_regression.py used for imoti.bg's own similar
case. One caveat, disclosed rather than silently accepted: going forward,
scraper_imot.py/scraper_olx.py deliberately classify a FRESH scrape from
the raw first card line alone (NOT the fuller stored `title` field, which
has ", <area>" appended) - to avoid a new false-positive class an
area/district name could introduce (e.g. "Промишлена зона"/"Бизнес хотел"
are real place names, not category words) - but this backfill only has
the already-`", <area>"`-appended `title` field stored on disk to work
with, the same "best-effort from what's on disk" limitation
backfill_garage_tiebreak_regression.py already accepted for imoti.bg's own
transient-slug case. In practice this rarely changes the outcome here,
since area is always appended AFTER a listing's own real subject in that
stored title, and _resolve_subject_over_amenity's whole point is
preferring whichever category leads the text - confirmed by sampling
(see docs/decisions.md) that this exact "Бизнес хотел" area-name pattern
resolves correctly either way. A future natural re-scrape may still
occasionally reclassify a record differently once it picks up the
narrower, area-free title - flagged here rather than treated as a
same-script inconsistency to silently paper over.

Updates ONLY latest.category/latest.category_confidence in place - never
snapshots, first_seen, price, description, or any other field. Regenerates
each portal's own leads*.json via that portal's own compute_leads(), same
reasoning as every other backfill in this project: leads.json's cross-
listing aggregates (e.g. area_avg_price_per_sqm) were themselves computed
over the wrong category bucket for every affected listing, not just its
own record.

Run with: python3 backfill_category_bazar_imot_olx_migration.py
"""

import json

import category_classifier as cc


PORTALS = [
    ("bazar.bg", "scraper_bazar"),
    ("imot.bg", "scraper_imot"),
    ("olx.bg", "scraper_olx"),
]


def backfill_portal(portal_label, module_name):
    module = __import__(module_name)
    history = module.load_history()

    total = 0
    changed = 0
    before_cat = {}
    after_cat = {}
    before_conf = {}
    after_conf = {}
    transitions = {}
    changed_examples = []

    for lid, rec in history.items():
        latest = rec.get("latest")
        if not latest:
            continue
        total += 1
        before = latest.get("category")
        before_conf_v = latest.get("category_confidence")
        before_cat[before] = before_cat.get(before, 0) + 1
        before_conf[before_conf_v] = before_conf.get(before_conf_v, 0) + 1

        category, confidence, reason = cc.classify_listing(
            title=latest.get("title"), description=latest.get("description"), url=latest.get("url")
        )
        after_cat[category] = after_cat.get(category, 0) + 1
        after_conf[confidence] = after_conf.get(confidence, 0) + 1

        if category != before or confidence != before_conf_v:
            changed += 1
            transitions[(before, category)] = transitions.get((before, category), 0) + 1
            if len(changed_examples) < 12:
                changed_examples.append((lid, before, category, confidence, reason, latest.get("title")))

        latest["category"] = category
        latest["category_confidence"] = confidence

    print(f"=== {portal_label} ({module_name}) ===")
    print(f"DEBUG: total records: {total}")
    print(f"DEBUG: category counts BEFORE: {before_cat}")
    print(f"DEBUG: category counts AFTER:  {after_cat}")
    print(f"DEBUG: confidence counts BEFORE: {before_conf}")
    print(f"DEBUG: confidence counts AFTER:  {after_conf}")
    print(f"DEBUG: total changed (category or confidence): {changed}")
    print("DEBUG: top transitions (old_category -> new_category):")
    for pair, count in sorted(transitions.items(), key=lambda kv: -kv[1])[:20]:
        print(f"   {pair}: {count}")
    print("DEBUG: sample of changed records (id, old, new, confidence, reason, title):")
    for ex in changed_examples:
        print(f"  {ex}")

    module.save_history(history)
    leads = module.compute_leads(history)
    module.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DEBUG: wrote {len(leads)} leads to {module.LEADS_FILE}")
    print()

    return total, changed


def main():
    total_all = 0
    changed_all = 0
    for portal_label, module_name in PORTALS:
        total, changed = backfill_portal(portal_label, module_name)
        total_all += total
        changed_all += changed

    print("=== TOTAL ACROSS bazar.bg + imot.bg + olx.bg ===")
    print(f"DEBUG: total records checked: {total_all}")
    print(f"DEBUG: total changed (category or confidence): {changed_all}")


if __name__ == "__main__":
    main()
