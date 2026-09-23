"""
Regression tests for docs/backlog.md item 30 / commit 3e1aadb ("Fix
olx.bg's masked grid-crawl timeout with a checkpointed, rotating oblast
loop").

scraper_olx.py's grid crawl (fetch_listings()) used to have no time budget
and no resume state at all. scrape.yml's olx.bg step has timeout-minutes:
60 and continue-on-error: true, and the 6 most recent scheduled runs all
got hard-killed mid-page at that 60-minute cap (confirmed via real job
logs, ~4min/oblast average) - continue-on-error masked every one of those
kills as a successful workflow run. Because OBLAST_SLUGS is a fixed,
never-randomized list order and the old loop always restarted at index 0,
the SAME first ~15 of its 26 oblasts got covered every single run and the
same ~10 tail oblasts (including Lovech) were chronically starved, not
just occasionally missed.

The fix (scraper_olx.py) added two genuinely new, load-bearing pieces of
logic, neither of which shipped with a committed automated test (Missy's
review of 3e1aadb, approved with this gap flagged - only uncommitted
offline harnesses existed):

  1. fetch_listings() now takes deadline/on_checkpoint and persists which
     OBLAST_SLUGS index to resume from next run in GRID_STATE_FILE
     (data/olx_grid_state.json), so a bounded run's leftover oblasts
     rotate to the FRONT of the next run instead of the loop always
     restarting at index 0 and starving the same tail forever.
  2. main()'s record_new()/checkpoint closure dedups by listing id
     (recorded_ids) so the incremental per-oblast checkpoints - each one
     carrying fetch_listings()'s FULL accumulated seen.values(), not just
     that oblast's own delta (see fetch_listings()'s own
     "on_checkpoint(list(seen.values()), geocoder)" call) - don't
     double/triple-append a history snapshot for a listing that shows up
     in more than one checkpoint within the same run.

This file reconstructs the two verification scripts Missy wrote and ran
during review (rotation/wraparound, and checkpoint dedup) as real,
committed tests against the actual scraper_olx.py functions, stubbing
only Playwright/network and simulating the real ~4min/oblast pace
observed in the 6 killed production runs.

Run with: python3 -m unittest tests.test_olx_grid_crawl_timeout_fix -v
(no pytest / other test framework is installed in this repo - see
tests/test_update_history.py's own note.)
"""

import contextlib
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper_olx


@contextlib.contextmanager
def _patched(module, **attrs):
    """Sets module attributes for the duration of the block and restores
    their original values afterward - a plain, dependency-free stand-in
    for unittest.mock.patch.object, consistent with this repo's existing
    tests (see test_update_history.py's own manual try/finally attribute
    swap for the same purpose)."""
    original = {name: getattr(module, name) for name in attrs}
    for name, value in attrs.items():
        setattr(module, name, value)
    try:
        yield
    finally:
        for name, value in original.items():
            setattr(module, name, value)


class _FakeGeocoder:
    """Stands in for geo_utils.Geocoder inside fetch_listings() - no disk
    cache, no network, just enough surface (geocode_cached_only/save) for
    fetch_listings_page()/fetch_listings() to call without erroring."""

    def geocode_cached_only(self, query):
        return None

    def save(self):
        pass


class _FakePage:
    pass


class _FakeContext:
    def new_page(self):
        return _FakePage()


class _FakeBrowser:
    def new_context(self, **kwargs):
        return _FakeContext()

    def close(self):
        pass


class _FakeChromium:
    def launch(self, **kwargs):
        return _FakeBrowser()


class _FakePlaywright:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    chromium = _FakeChromium()


def _fake_sync_playwright():
    return _FakePlaywright()


class GridCrawlRotationTest(unittest.TestCase):
    """Reconstruction of Missy's rotation/wraparound harness: a fake clock
    simulating the real ~4min/oblast pace (derived from the 6 real
    production runs, all killed at 60m12s-60m13s) drives two simulated
    bounded fetch_listings() runs back-to-back through the real function -
    only Playwright/network and fetch_listings_page() are stubbed."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.grid_state_file = Path(self._tmpdir.name) / "olx_grid_state.json"

        # TIME_BUDGET_SECONDS is the real 50*60 = 3000s budget main() passes
        # as fetch_listings()'s deadline. 250s/oblast (~4.17min) matches the
        # module's own "~4min/oblast average" from the real killed-run logs,
        # and divides the budget evenly into exactly 12 oblasts/run so the
        # simulated deadline is hit exactly at the same point both runs.
        self.per_oblast_seconds = scraper_olx.TIME_BUDGET_SECONDS / 12
        self.clock = {"t": 0.0}

    def _run_bounded_crawl(self):
        visited = []

        def fake_fetch_listings_page(page, url, seen, geocoder, oblast_display):
            visited.append(oblast_display)
            self.clock["t"] += self.per_oblast_seconds
            # <= 1 ends this oblast's page loop after a single page, same
            # as a real "reached the end of results" page.
            return 0

        with _patched(scraper_olx, GRID_STATE_FILE=self.grid_state_file,
                       Geocoder=_FakeGeocoder, sync_playwright=_fake_sync_playwright,
                       fetch_listings_page=fake_fetch_listings_page), \
             _patched(scraper_olx.time, monotonic=lambda: self.clock["t"]):
            deadline = scraper_olx.TIME_BUDGET_SECONDS
            scraper_olx.fetch_listings(deadline=deadline, on_checkpoint=None)

        return visited

    def _read_grid_state(self):
        # Read the persisted state file directly, rather than via
        # scraper_olx.load_grid_state(), since that function looks up the
        # GRID_STATE_FILE global at call time and the patch above is only
        # in effect inside _run_bounded_crawl()'s own "with" block.
        return json.loads(self.grid_state_file.read_text(encoding="utf-8"))

    def test_run1_covers_first_12_of_26_and_persists_resume_index(self):
        visited = self._run_bounded_crawl()

        expected = [name for name, _slug in scraper_olx.OBLAST_SLUGS[:12]]
        self.assertEqual(visited, expected)

        state = self._read_grid_state()
        self.assertEqual(state.get("next_start_index"), 12)

    def test_run2_resumes_from_persisted_index_and_covers_next_12_including_lovech(self):
        run1_visited = self._run_bounded_crawl()

        # Simulate a fresh run: reset the clock, keep the persisted grid
        # state file exactly as run 1 left it (that's the whole point -
        # run 2 must read it back and resume from there).
        self.clock["t"] = 0.0
        run2_visited = self._run_bounded_crawl()

        expected = [name for name, _slug in scraper_olx.OBLAST_SLUGS[12:24]]
        self.assertEqual(run2_visited, expected)
        self.assertIn("Ловеч", run2_visited)  # the oblast the original bug chronically starved

        state = self._read_grid_state()
        self.assertEqual(state.get("next_start_index"), 24)

        # Union of both runs covers 24/26 oblasts - NOT 25 (Missy caught
        # and corrected this exact number in the fix's own commit message;
        # the last 2, Разград/Смолян at indices 24-25, are left for a 3rd
        # run).
        union = set(run1_visited) | set(run2_visited)
        self.assertEqual(len(union), 24)
        self.assertNotEqual(len(union), 25)
        self.assertEqual(len(run1_visited), 12)
        self.assertEqual(len(run2_visited), 12)


def _make_listing(lid, price_eur):
    return {
        "id": lid,
        "url": f"https://www.olx.bg/d/ad/{lid}.html",
        "photo": None,
        "price_eur": price_eur,
        "sqm": None,
        "area": "Център",
        "city": "София",
        "title": f"Апартамент {lid}, Център",
        "portal": "olx.bg",
        "site_updated_at": None,
        "lat": None,
        "lng": None,
        "category": "apartment",
    }


# Three overlapping checkpoint snapshots the way fetch_listings()'s
# on_checkpoint callback actually calls it: each one is the FULL
# accumulated seen.values() so far (see fetch_listings(): "on_checkpoint
# (list(seen.values()), geocoder)"), not an incremental delta - so A and B
# appear in all three, C in the last two, D only in the last one.
_LISTING_A = _make_listing("olx_A", 100000)
_LISTING_B = _make_listing("olx_B", 80000)
_LISTING_C = _make_listing("olx_C", 60000)
_LISTING_D = _make_listing("olx_D", 40000)

_CHECKPOINT_BATCHES = [
    [_LISTING_A, _LISTING_B],
    [_LISTING_A, _LISTING_B, _LISTING_C],
    [_LISTING_A, _LISTING_B, _LISTING_C, _LISTING_D],
]


class CheckpointDedupTest(unittest.TestCase):
    """Reconstruction of Missy's checkpoint-dedup harness: drives the REAL
    main() (its actual record_new()/checkpoint closure, not a
    reimplementation) with a fake fetch_listings() that calls the
    on_checkpoint it's handed three times with overlapping, fully-
    accumulated snapshots - exactly the shape the real fetch_listings()
    produces - and asserts every listing ends up with exactly one history
    snapshot despite the overlap."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.history_file = Path(self._tmpdir.name) / "history_olx.json"
        self.leads_file = Path(self._tmpdir.name) / "leads_olx.json"

    def _fake_fetch_listings(self, deadline=None, on_checkpoint=None):
        # Old (pre-fix) main() calls "fetch_listings()" with no arguments
        # at all - on_checkpoint never gets wired up. Raising here (rather
        # than silently skipping the checkpoint calls) is what makes this
        # test fail loudly against that shape instead of passing
        # vacuously.
        if on_checkpoint is None:
            raise TypeError(
                "fetch_listings() was called without on_checkpoint - the real "
                "fix's main() always passes its checkpoint closure"
            )
        fake_geocoder = _FakeGeocoder()
        for batch in _CHECKPOINT_BATCHES:
            on_checkpoint([copy.deepcopy(l) for l in batch], fake_geocoder)
        return [copy.deepcopy(l) for l in _CHECKPOINT_BATCHES[-1]]

    def test_overlapping_checkpoints_each_listing_gets_exactly_one_snapshot(self):
        with _patched(scraper_olx, HISTORY_FILE=self.history_file, LEADS_FILE=self.leads_file,
                      fetch_listings=self._fake_fetch_listings):
            scraper_olx.main()

        history = json.loads(self.history_file.read_text(encoding="utf-8"))
        self.assertEqual(set(history.keys()), {"olx_A", "olx_B", "olx_C", "olx_D"})
        for lid in ("olx_A", "olx_B", "olx_C", "olx_D"):
            snapshots = history[lid]["snapshots"]
            self.assertEqual(
                len(snapshots), 1,
                f"{lid} ended up with {len(snapshots)} history snapshots "
                f"(expected exactly 1) after 3 overlapping checkpoint calls",
            )

        # The fix is a dedup, not a data loss - the final recorded prices
        # must still be each listing's real price, and D (only ever seen
        # in the LAST checkpoint) must still have made it in at all.
        self.assertEqual(history["olx_A"]["snapshots"][0]["price_eur"], 100000)
        self.assertEqual(history["olx_D"]["snapshots"][0]["price_eur"], 40000)


class CheckpointDedupSanityCheck(unittest.TestCase):
    """Sanity check that CheckpointDedupTest actually discriminates the
    bug class it guards against, the same way test_update_history.py's own
    BuggyUpdateHistoryReallyDoesLoseData class does for its bug: reproduces
    main()'s record_new() shape WITHOUT its recorded_ids dedup filter (i.e.
    naively calling the real update_history() on the full accumulated
    checkpoint every time, instead of only on the delta) against the same
    three overlapping checkpoint batches, and confirms that DOES produce
    more than one snapshot for the listings that appear in more than one
    checkpoint."""

    def test_naive_checkpointing_without_id_dedup_double_appends(self):
        history = {}

        def buggy_record_new(listings_so_far):
            # The bug shape: no recorded_ids filter at all - every
            # checkpoint calls update_history() on its own full
            # accumulated snapshot.
            nonlocal history
            history = scraper_olx.update_history(history, listings_so_far)

        for batch in _CHECKPOINT_BATCHES:
            buggy_record_new([copy.deepcopy(l) for l in batch])

        # A and B are in all 3 checkpoint batches -> 3 snapshots each.
        self.assertEqual(len(history["olx_A"]["snapshots"]), 3)
        self.assertEqual(len(history["olx_B"]["snapshots"]), 3)
        # C is in the last 2 batches -> 2 snapshots.
        self.assertEqual(len(history["olx_C"]["snapshots"]), 2)
        # D is only in the last batch -> 1 snapshot (nothing to dedup yet).
        self.assertEqual(len(history["olx_D"]["snapshots"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
