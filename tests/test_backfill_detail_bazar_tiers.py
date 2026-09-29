"""
Tests for backfill_detail_bazar.py's select_batch() - the two-tier,
floor-protected selection/budgeting logic added 2026-09-29 alongside the
new "specs_checked" flag (mirrors backfill_detail_alo.py's own
select_batch()/"_photos_checked" precedent - see
tests/test_backfill_detail_alo_tiers.py).

Real motivation (see backfill_detail_bazar.py's own module docstring):
extract_specs_bazar()/extract_contact_bazar() were added 2026-09-24, but
every listing already marked "coords_checked": True before that date was
visited under the OLD script, which never called them - live-measured
against data/history_bazar.json.gz on 2026-09-29, 43,185 such listings
exist and only 21.5% of them have any specs at all (vs. 99.2% for
listings first checked on/after 2026-09-24), and 91.7% of the no-specs
ones already have a real description - proof the page WAS fetched
successfully and the gap is this stale-flag bug, not the portal "not
publishing" the field.

Run with: python3 -m unittest tests.test_backfill_detail_bazar_tiers -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backfill_detail_bazar as bdb


def _rec(first_seen, **latest_fields):
    return {"first_seen": first_seen, "snapshots": [], "latest": latest_fields}


_ALL_FLOORS = dict(MAX_LOOKUPS_PER_RUN=100, SPECS_RECHECK_FLOOR=100)


class SelectBatchTierMembershipTest(unittest.TestCase):
    def test_two_tiers_are_mutually_exclusive_and_exhaustive(self):
        history = {
            "never_checked_1": _rec("2026-09-20T00:00:00+00:00"),
            "specs_recheck_1": _rec("2026-09-20T00:00:00+00:00", coords_checked=True),
            "fully_done_1": _rec(
                "2026-09-20T00:00:00+00:00", coords_checked=True, specs_checked=True,
            ),
        }
        with _patched(bdb, **_ALL_FLOORS):
            missing = bdb.select_batch(history)
        ids = [lid for lid, _ in missing]
        self.assertIn("never_checked_1", ids)
        self.assertIn("specs_recheck_1", ids)
        # Already checked under the current specs/contact extractors - must
        # not be picked up again (the whole point of this flag).
        self.assertNotIn("fully_done_1", ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_specs_recheck_excludes_never_checked(self):
        # A listing that was never even coords_checked belongs ONLY to the
        # never_checked tier, not also specs_recheck - these must stay
        # disjoint or a listing could be double-counted/double-visited in
        # the same run.
        history = {"never_checked_1": _rec("2026-09-20T00:00:00+00:00")}
        with _patched(bdb, **_ALL_FLOORS):
            missing = bdb.select_batch(history)
        self.assertEqual([lid for lid, _ in missing], ["never_checked_1"])


class SelectBatchFloorAndStarvationTest(unittest.TestCase):
    def test_recheck_floor_is_not_starved_by_a_huge_never_checked_backlog(self):
        # Reproduces the exact bug SPECS_RECHECK_FLOOR exists to prevent: a
        # never_checked backlog far larger than MAX_LOOKUPS_PER_RUN must not
        # crowd the recheck tier out of a run entirely.
        history = {}
        for i in range(5000):
            history[f"never_{i}"] = _rec(f"2026-09-{(i % 28) + 1:02d}T00:00:00+00:00")
        history["specs_recheck_1"] = _rec("2026-09-20T00:00:00+00:00", coords_checked=True)
        with _patched(bdb, MAX_LOOKUPS_PER_RUN=1000, SPECS_RECHECK_FLOOR=400):
            missing = bdb.select_batch(history)
        ids = [lid for lid, _ in missing]
        self.assertIn("specs_recheck_1", ids)
        self.assertEqual(len(missing), 1000)  # the full MAX_LOOKUPS_PER_RUN budget used

    def test_floor_sized_so_never_checked_still_gets_a_real_share(self):
        self.assertGreater(bdb.MAX_LOOKUPS_PER_RUN, bdb.SPECS_RECHECK_FLOOR)

    def test_leftover_budget_goes_to_recheck_when_never_checked_is_small(self):
        history = {"never_1": _rec("2026-09-20T00:00:00+00:00")}
        for i in range(10):
            history[f"specs_recheck_{i}"] = _rec(
                f"2026-09-{i + 1:02d}T00:00:00+00:00", coords_checked=True,
            )
        with _patched(bdb, MAX_LOOKUPS_PER_RUN=5, SPECS_RECHECK_FLOOR=1):
            missing = bdb.select_batch(history)
        # never_1 (1) + guaranteed floor (1) + leftover cap spent on more
        # specs_recheck (3) = the full budget of 5, not left unused.
        self.assertEqual(len(missing), 5)

    def test_newest_first_within_each_tier(self):
        history = {
            "sr_old": _rec("2026-09-01T00:00:00+00:00", coords_checked=True),
            "sr_new": _rec("2026-09-20T00:00:00+00:00", coords_checked=True),
        }
        with _patched(bdb, **_ALL_FLOORS):
            missing = bdb.select_batch(history)
        ids = [lid for lid, _ in missing]
        self.assertLess(ids.index("sr_new"), ids.index("sr_old"))

    def test_recheck_slice_comes_before_never_checked_slice(self):
        # The recheck floor's slice is meant to claim first place in
        # processing order (see select_batch()'s own comment) so it gets
        # first shot at this run's time budget too, not just a slot
        # somewhere in the candidate list.
        history = {
            "never_1": _rec("2026-09-25T00:00:00+00:00"),
            "specs_recheck_1": _rec("2026-09-01T00:00:00+00:00", coords_checked=True),
        }
        with _patched(bdb, **_ALL_FLOORS):
            missing = bdb.select_batch(history)
        ids = [lid for lid, _ in missing]
        self.assertEqual(ids[0], "specs_recheck_1")


class _patched:
    """Minimal context manager to temporarily override module-level
    constants (MAX_LOOKUPS_PER_RUN/SPECS_RECHECK_FLOOR) for one test,
    restoring the real values afterward."""

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
