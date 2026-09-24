"""
Tests for backfill_detail_alo.py's select_batch() - the three-tier,
dual-floor selection/budgeting logic added 2026-09-24 alongside the
"_gallery_specs_rechecked" flag (see scraper_alo.py's fetch_update_dates()
and backfill_detail_alo.py's own module-level comments for the full
reasoning: extract_photos_alo() was found to have a 0.0% production hit
rate, root-caused to an HTML-attribute-order bug, and fixed the same day -
this is the "already _photos_checked: True listings won't automatically
get revisited under the fix" half of that change, applying the exact same
"_detail_fetched -> _photos_checked" precedent one level deeper).

Run with: python3 -m unittest tests.test_backfill_detail_alo_tiers -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backfill_detail_alo as bda


def _rec(first_seen, **latest_fields):
    return {"first_seen": first_seen, "snapshots": [], "latest": latest_fields}


class SelectBatchTierMembershipTest(unittest.TestCase):
    def test_three_tiers_are_mutually_exclusive_and_exhaustive(self):
        history = {
            "never_fetched_1": _rec("2026-09-20T00:00:00+00:00"),
            "photos_recheck_1": _rec("2026-09-20T00:00:00+00:00", _detail_fetched=True),
            "gallery_specs_recheck_1": _rec(
                "2026-09-20T00:00:00+00:00", _detail_fetched=True, _photos_checked=True,
            ),
            "fully_done_1": _rec(
                "2026-09-20T00:00:00+00:00", _detail_fetched=True, _photos_checked=True,
                _gallery_specs_rechecked=True,
            ),
        }
        # Force every tier's whole (tiny) backlog through by raising the
        # floors/cap well above what this fixture could ever need.
        with _patched(bda, MAX_LOOKUPS_PER_RUN=100, PHOTOS_RECHECK_FLOOR=100,
                       GALLERY_SPECS_RECHECK_FLOOR=100):
            missing = bda.select_batch(history)
        ids = [lid for lid, _ in missing]
        self.assertIn("never_fetched_1", ids)
        self.assertIn("photos_recheck_1", ids)
        self.assertIn("gallery_specs_recheck_1", ids)
        # Already fully processed under the fixed extractors - must not be
        # picked up again (the whole point of this flag).
        self.assertNotIn("fully_done_1", ids)
        # No id appears in more than one tier / twice in the result.
        self.assertEqual(len(ids), len(set(ids)))

    def test_gallery_specs_recheck_excludes_never_photos_checked(self):
        # A listing that's _detail_fetched but never even _photos_checked
        # belongs ONLY to the (older, still-shrinking) photos_recheck tier,
        # not also to gallery_specs_recheck - these must stay disjoint or a
        # listing could be double-counted/double-visited in the same run.
        history = {
            "old_pre_photos_visit": _rec("2026-09-20T00:00:00+00:00", _detail_fetched=True),
        }
        with _patched(bda, MAX_LOOKUPS_PER_RUN=100, PHOTOS_RECHECK_FLOOR=100,
                       GALLERY_SPECS_RECHECK_FLOOR=100):
            missing = bda.select_batch(history)
        self.assertEqual([lid for lid, _ in missing], ["old_pre_photos_visit"])


class SelectBatchFloorAndStarvationTest(unittest.TestCase):
    def test_recheck_floors_are_not_starved_by_a_huge_never_fetched_backlog(self):
        # Reproduces the exact bug PHOTOS_RECHECK_FLOOR/
        # GALLERY_SPECS_RECHECK_FLOOR exist to prevent (see their own
        # comments): a never_fetched backlog far larger than
        # MAX_LOOKUPS_PER_RUN must not crowd BOTH recheck tiers out of a
        # run entirely.
        history = {}
        for i in range(5000):
            history[f"never_{i}"] = _rec(f"2026-09-{(i % 28) + 1:02d}T00:00:00+00:00")
        history["photos_recheck_1"] = _rec("2026-09-20T00:00:00+00:00", _detail_fetched=True)
        history["gallery_specs_recheck_1"] = _rec(
            "2026-09-20T00:00:00+00:00", _detail_fetched=True, _photos_checked=True,
        )
        with _patched(bda, MAX_LOOKUPS_PER_RUN=1000, PHOTOS_RECHECK_FLOOR=250,
                       GALLERY_SPECS_RECHECK_FLOOR=400):
            missing = bda.select_batch(history)
        ids = [lid for lid, _ in missing]
        self.assertIn("photos_recheck_1", ids)
        self.assertIn("gallery_specs_recheck_1", ids)
        self.assertEqual(len(missing), 1000)  # the full MAX_LOOKUPS_PER_RUN budget used

    def test_floors_sized_so_never_fetched_still_gets_a_real_share(self):
        # PHOTOS_RECHECK_FLOOR + GALLERY_SPECS_RECHECK_FLOOR must leave a
        # real, positive amount of this run's budget for never_fetched when
        # both recheck backlogs are at or above their own floors - the
        # opposite failure mode (recheck tiers alone consuming the ENTIRE
        # budget) would silently stop new listings from ever being visited.
        self.assertGreater(bda.MAX_LOOKUPS_PER_RUN, bda.PHOTOS_RECHECK_FLOOR + bda.GALLERY_SPECS_RECHECK_FLOOR)

    def test_leftover_budget_goes_to_recheck_when_never_fetched_is_small(self):
        history = {
            "never_1": _rec("2026-09-20T00:00:00+00:00"),
        }
        for i in range(10):
            history[f"gallery_specs_recheck_{i}"] = _rec(
                f"2026-09-{i + 1:02d}T00:00:00+00:00", _detail_fetched=True, _photos_checked=True,
            )
        with _patched(bda, MAX_LOOKUPS_PER_RUN=5, PHOTOS_RECHECK_FLOOR=0, GALLERY_SPECS_RECHECK_FLOOR=1):
            missing = bda.select_batch(history)
        # never_1 (1) + guaranteed floor (1) + leftover cap spent on more
        # gallery_specs_recheck (3) = the full budget of 5, not left unused.
        self.assertEqual(len(missing), 5)

    def test_newest_first_within_each_tier(self):
        history = {
            "gsr_old": _rec("2026-09-01T00:00:00+00:00", _detail_fetched=True, _photos_checked=True),
            "gsr_new": _rec("2026-09-20T00:00:00+00:00", _detail_fetched=True, _photos_checked=True),
        }
        with _patched(bda, MAX_LOOKUPS_PER_RUN=100, PHOTOS_RECHECK_FLOOR=100,
                       GALLERY_SPECS_RECHECK_FLOOR=100):
            missing = bda.select_batch(history)
        ids = [lid for lid, _ in missing]
        self.assertLess(ids.index("gsr_new"), ids.index("gsr_old"))


class _patched:
    """Minimal context manager to temporarily override module-level
    constants (MAX_LOOKUPS_PER_RUN/PHOTOS_RECHECK_FLOOR/
    GALLERY_SPECS_RECHECK_FLOOR) for one test, restoring the real values
    afterward - avoids every test needing production-sized fixtures just to
    exercise the selection logic."""

    def __init__(self, module, **overrides):
        self.module = module
        self.overrides = overrides
        self.originals = {}

    def __enter__(self):
        for name, value in self.overrides.items():
            self.originals[name] = getattr(self.module, name)
            setattr(self.module, name, value)
        return self

    def __exit__(self, *exc_info):
        for name, value in self.originals.items():
            setattr(self.module, name, value)
        return False


if __name__ == "__main__":
    unittest.main(verbosity=2)
