"""
Regression tests for issue #243 / docs/missy-findings/2026-09-23.md -
merge_history_conflict.py's merge_record() used to pick which side's
whole "latest" dict wins a rebase conflict purely by comparing
freshest_seen_at() (which side's LAST snapshot is chronologically newer).
That conflates "which side scraped this listing most recently" (a real
signal for fields that genuinely change over time, like price_eur/sqm)
with "which side's code produced correct classifier/parser output" (which
the script has no visibility into from timestamps alone) - confirmed live
as the exact mechanism that reintroduced imoti.net's "100%-apartment" bug
for ~17,680 listings four hours after PR #199 had already fixed it: a
long-running scrape-large.yml run that checked out `main` BEFORE PR #199
merged (so was still running the old, buggy classifier) hit its rebase
conflict AFTER PR #199 had landed, and its genuinely-newer snapshot made
the old code pick its stale, wrong "category" over PR #199's already-
merged, data-only correction.

This file proves:
  1. The exact regression scenario (PR #199-shaped: an older side with a
     data-only correctness fix vs. a newer side with a fresh snapshot but
     stale/wrong classifier output) is now resolved correctly, for both
     of the "recomputable" portals (imoti.net, alo.bg).
  2. The classifier-recompute-agrees case (both sides' own title/url
     recompute to the same answer via today's classifier, regardless of
     what was actually stored) picks that shared fresh answer.
  3. The "can't verify" fallback (non-recomputable portal, e.g. bazar.bg)
     still doesn't let a fresher-but-wrong side win via recency alone -
     it conservatively prefers main.
  4. The existing, legitimate, ALREADY-WORKING case this script exists
     for is NOT regressed: a genuinely newer re-scrape's price_eur/status-
     shaped fields (and a "latest" field unique to one side) still merge
     exactly as the module docstring documents.
  5. first_seen (earliest wins) and snapshots (deduped union) - the two
     other pieces of merge_record()'s documented behavior - are unchanged.

Run with: python3 -m unittest tests.test_merge_history_conflict -v
(no pytest / other test framework is installed in this repo - see
tests/test_update_history.py's own note.)
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import merge_history_conflict as m


# Real imoti.net example from Missy's 2026-09-23 finding (issue #243):
# id 6005389, url ".../parcel/6005389/", title "Development land, 500 м2
# Sofia, Gotse Delchev" - category_classifier.classify_listing() on this
# exact (title, url) pair produces "land"/"high" (a parcel slug + a title
# that says "Development land" agree on two independent signals).
LAND_TITLE = "Development land, 500 kv.m Sofia, Gotse Delchev"
LAND_URL = "https://www.imoti.net/en/obiavi/prodazhba/parcel/6005389/"


def _imoti_net_latest(category, category_confidence, extra=None):
    latest = {
        "id": "6005389",
        "url": LAND_URL,
        "title": LAND_TITLE,
        "portal": "imoti.net",
        "price_eur": 50000,
        "sqm": 500,
        "category": category,
        "category_confidence": category_confidence,
    }
    if extra:
        latest.update(extra)
    return latest


class TestIssue243Regression(unittest.TestCase):
    def test_confirmed_classifier_recomputes_land_not_apartment(self):
        # Sanity check the fixture itself actually reproduces the real
        # bug shape before trusting the scenario tests below.
        category, confidence, _ = m.classify_listing(title=LAND_TITLE, url=LAND_URL)
        self.assertEqual(category, "land")

    def test_pr199_scenario_stale_fresher_snapshot_does_not_win_imoti_net(self):
        """main: PR #199's data-only fix already landed (correct
        "land", no new snapshot). local: a scrape-large.yml run that
        started before PR #199 merged, still has the pre-fix "apartment"
        category, but genuinely re-scraped (a real, chronologically newer
        snapshot). The old code picked local's "apartment" because its
        snapshot was newer - the fix must pick main's "land" instead,
        because local's own stored category no longer matches what
        today's classifier produces from local's own title/url."""
        main_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T10:42:15+00:00", "price_eur": 50000}],
            "latest": _imoti_net_latest("land", "high"),
        }
        local_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T17:27:37+00:00", "price_eur": 50000}],
            "latest": _imoti_net_latest("apartment", "high"),
        }
        merged = m.merge_record(main_rec, local_rec)
        self.assertEqual(merged["latest"]["category"], "land")
        self.assertEqual(merged["latest"]["category_confidence"], "high")
        # The newer snapshot itself is still kept (never discarded) - only
        # the classifier-derived fields are protected from following it.
        self.assertEqual(
            [s["seen_at"] for s in merged["snapshots"]],
            ["2026-09-22T10:42:15+00:00", "2026-09-22T17:27:37+00:00"],
        )

    def test_pr199_scenario_reversed_sides_still_picks_correct_category(self):
        """Same scenario with main/local swapped (main is the stale run,
        local already has the fix) - proves the fix isn't secretly just
        "always prefer main," it's actually verifying via recompute."""
        main_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T17:27:37+00:00", "price_eur": 50000}],
            "latest": _imoti_net_latest("apartment", "high"),
        }
        local_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T10:42:15+00:00", "price_eur": 50000}],
            "latest": _imoti_net_latest("land", "high"),
        }
        merged = m.merge_record(main_rec, local_rec)
        self.assertEqual(merged["latest"]["category"], "land")

    def test_alo_bg_same_scenario(self):
        """The same regression shape on alo.bg (the other
        RECOMPUTABLE_CLASSIFIER_PORTALS entry) - a garage listing stuck at
        a stale "apartment" category on the fresher side."""
        title = "Garage, 34 kv.m Sofia, Vitosha"
        url = "https://www.alo.bg/obiavi/imoti/garazhi-parkomesta/34-kv-m-sofia-vitosha/1234567"
        category, _, _ = m.classify_listing(title=title, url=url)
        self.assertEqual(category, "garage")

        def latest(cat):
            return {
                "id": "alo_1234567", "url": url, "title": title, "portal": "alo.bg",
                "price_eur": 12000, "category": cat, "category_confidence": "high",
            }

        main_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T10:00:00+00:00", "price_eur": 12000}],
            "latest": latest("garage"),
        }
        local_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T20:00:00+00:00", "price_eur": 12000}],
            "latest": latest("apartment"),
        }
        merged = m.merge_record(main_rec, local_rec)
        self.assertEqual(merged["latest"]["category"], "garage")

    def test_both_sides_stale_disagreeing_recompute_agrees_uses_fresh_answer(self):
        """Both sides' stored category is stale relative to today's
        classifier (e.g. a keyword-list improvement landed after both
        these runs happened) AND they disagree with each other (main
        says "apartment", local says "business" - a real conflict to
        resolve) - but recomputing each side's own (title, url) through
        today's classifier agrees on "land" for both. The fix should
        trust that shared fresh answer over either side's stale stored
        value, rather than picking whichever of the two wrong answers
        happens to be on the fresher/main side."""
        main_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T10:00:00+00:00", "price_eur": 50000}],
            "latest": _imoti_net_latest("apartment", "low"),
        }
        local_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T20:00:00+00:00", "price_eur": 50000}],
            "latest": _imoti_net_latest("business", "low"),
        }
        merged = m.merge_record(main_rec, local_rec)
        self.assertEqual(merged["latest"]["category"], "land")
        self.assertEqual(merged["latest"]["category_confidence"], "high")

    def test_non_recomputable_portal_falls_back_to_preferring_main(self):
        """bazar.bg uses geo_utils.classify_category(), not
        category_classifier.classify_listing() - not in
        RECOMPUTABLE_CLASSIFIER_PORTALS, so no recompute is attempted.
        The fix must still not let the fresher-snapshot side win via
        recency alone for a STABLE_LATEST_FIELDS key - it falls back to
        preferring main (see module docstring's "main can never be older-
        code than local" reasoning)."""
        main_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T10:00:00+00:00", "price_eur": 80000}],
            "latest": {
                "id": "bazar_1", "url": "https://bazar.bg/x", "title": "Kashta, Plovdiv",
                "portal": "bazar.bg", "price_eur": 80000, "category": "house",
            },
        }
        local_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T20:00:00+00:00", "price_eur": 80000}],
            "latest": {
                "id": "bazar_1", "url": "https://bazar.bg/x", "title": "Kashta, Plovdiv",
                "portal": "bazar.bg", "price_eur": 80000, "category": "apartment",
            },
        }
        merged = m.merge_record(main_rec, local_rec)
        self.assertEqual(merged["latest"]["category"], "house")

    def test_classify_listing_unimportable_degrades_to_prefer_main(self):
        """If category_classifier ever becomes unimportable,
        _recompute_category() must return None (never raise), and the
        merge must still resolve via the prefer-main fallback rather than
        crashing the whole conflict resolution."""
        original = m.classify_listing
        m.classify_listing = None
        try:
            main_rec = {
                "first_seen": "2026-09-01T00:00:00+00:00",
                "snapshots": [{"seen_at": "2026-09-22T10:00:00+00:00", "price_eur": 50000}],
                "latest": _imoti_net_latest("land", "high"),
            }
            local_rec = {
                "first_seen": "2026-09-01T00:00:00+00:00",
                "snapshots": [{"seen_at": "2026-09-22T20:00:00+00:00", "price_eur": 50000}],
                "latest": _imoti_net_latest("apartment", "high"),
            }
            merged = m.merge_record(main_rec, local_rec)
            self.assertEqual(merged["latest"]["category"], "land")
        finally:
            m.classify_listing = original


class TestLegitimateVolatileFieldBehaviorNotRegressed(unittest.TestCase):
    """The case this script was already built and shipped for: a
    genuinely newer re-scrape's price/status-shaped fields SHOULD win
    over a stale side, and a "latest" field unique to one side must
    survive. STABLE_LATEST_FIELDS must not interfere with any of this."""

    def test_newer_side_price_and_unique_field_still_win(self):
        main_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-20T00:00:00+00:00", "price_eur": 90000}],
            "latest": {
                "id": "alo_9", "url": "https://www.alo.bg/x", "title": "Kashta, Varna",
                "portal": "alo.bg", "price_eur": 90000, "category": "house",
                "category_confidence": "high",
                "site_updated_at": "2026-09-10T00:00:00+00:00",  # backfill-only enrichment field
            },
        }
        local_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-22T00:00:00+00:00", "price_eur": 85000}],
            "latest": {
                "id": "alo_9", "url": "https://www.alo.bg/x", "title": "Kashta, Varna",
                "portal": "alo.bg", "price_eur": 85000, "category": "house",
                "category_confidence": "high",
                # local's own plain grid-crawl "latest" never carries this
                # backfill-only field (see module docstring).
            },
        }
        merged = m.merge_record(main_rec, local_rec)
        # Newer side's own price wins (real, legitimate price-change signal).
        self.assertEqual(merged["latest"]["price_eur"], 85000)
        # Category agrees on both sides here, so nothing to resolve -
        # simply carried through.
        self.assertEqual(merged["latest"]["category"], "house")
        # A field unique to the older side still survives the union.
        self.assertEqual(merged["latest"]["site_updated_at"], "2026-09-10T00:00:00+00:00")

    def test_first_seen_takes_earlier_and_snapshots_are_deduped_union(self):
        main_rec = {
            "first_seen": "2026-09-05T00:00:00+00:00",
            "snapshots": [
                {"seen_at": "2026-09-05T00:00:00+00:00", "price_eur": 100000},
                {"seen_at": "2026-09-10T00:00:00+00:00", "price_eur": 95000},
            ],
            "latest": {"id": "x", "portal": "alo.bg", "price_eur": 95000, "category": "flat"},
        }
        local_rec = {
            "first_seen": "2026-09-01T00:00:00+00:00",  # earlier - should win
            "snapshots": [
                {"seen_at": "2026-09-05T00:00:00+00:00", "price_eur": 100000},  # exact dupe of main's
                {"seen_at": "2026-09-12T00:00:00+00:00", "price_eur": 93000},
            ],
            "latest": {"id": "x", "portal": "alo.bg", "price_eur": 93000, "category": "flat"},
        }
        merged = m.merge_record(main_rec, local_rec)
        self.assertEqual(merged["first_seen"], "2026-09-01T00:00:00+00:00")
        self.assertEqual(
            [s["seen_at"] for s in merged["snapshots"]],
            ["2026-09-05T00:00:00+00:00", "2026-09-10T00:00:00+00:00", "2026-09-12T00:00:00+00:00"],
        )
        self.assertEqual(merged["latest"]["price_eur"], 93000)

    def test_record_only_on_one_side_passes_through_unchanged(self):
        local_only = {
            "first_seen": "2026-09-01T00:00:00+00:00",
            "snapshots": [{"seen_at": "2026-09-01T00:00:00+00:00", "price_eur": 1000}],
            "latest": {"id": "z", "portal": "alo.bg", "category": "flat"},
        }
        self.assertEqual(m.merge_record(None, local_only), local_only)
        self.assertEqual(m.merge_record(local_only, None), local_only)


class TestMergeHistoryFileLevel(unittest.TestCase):
    """merge_history() is what resolve() actually calls with each side's
    whole-file JSON text - covers the file-level "one side doesn't have
    this listing/portal yet" and "one side's JSON is missing entirely"
    shapes that merge_record()'s own tests above only exercise as
    pre-built dicts, not as something merge_history() itself has to
    discover via set(main_data) | set(local_data)."""

    def _payload(self, lid, seen_at, price):
        return {
            lid: {
                "first_seen": seen_at,
                "snapshots": [{"seen_at": seen_at, "price_eur": price}],
                "latest": {"id": lid, "portal": "homes.bg", "price_eur": price},
            }
        }

    def test_new_listing_on_only_one_side_is_kept_not_dropped(self):
        # "portal-not-yet-existing entry": local scraped a genuinely new
        # listing main has never seen (a brand-new id key, not a value
        # conflict on a shared key) - the union over both sides' key sets
        # must still include it.
        main_json = json.dumps(self._payload("homes_1", "2026-09-20T00:00:00+00:00", 100000))
        local_json = json.dumps({
            **self._payload("homes_1", "2026-09-20T00:00:00+00:00", 100000),
            **self._payload("homes_2", "2026-09-25T00:00:00+00:00", 50000),
        })
        merged = m.merge_history(main_json, local_json)
        self.assertEqual(set(merged), {"homes_1", "homes_2"})
        self.assertEqual(merged["homes_2"]["latest"]["price_eur"], 50000)

    def test_main_side_json_missing_entirely_keeps_local_data(self):
        # git_show() returns None when a stage doesn't exist at all (e.g.
        # a brand-new file only this run's commit added) - resolve()
        # passes that straight through as main_json=None. merge_history()
        # must treat it as "no data on that side," not crash on
        # json.loads(None).
        local_json = json.dumps(self._payload("homes_3", "2026-09-25T00:00:00+00:00", 70000))
        merged = m.merge_history(None, local_json)
        self.assertEqual(set(merged), {"homes_3"})

    def test_local_side_json_missing_entirely_keeps_main_data(self):
        main_json = json.dumps(self._payload("homes_4", "2026-09-20T00:00:00+00:00", 80000))
        merged = m.merge_history(main_json, None)
        self.assertEqual(set(merged), {"homes_4"})

    def test_both_sides_missing_yields_empty_merge(self):
        self.assertEqual(m.merge_history(None, None), {})


if __name__ == "__main__":
    unittest.main()
