"""
Regression tests for docs/backlog.md item 31 ("bazar.bg: extend CITY_SLUGS
coverage and give its grid crawl the same checkpointed/rotating loop item
30 shipped for scraper_olx.py").

scraper_bazar.py's grid crawl (fetch_listings()) used to be an unbounded,
non-resumable loop over CITY_SLUGS with no deadline and no persisted
rotation state - the exact shape docs/backlog.md item 30 already found and
fixed for scraper_olx.py's own oblast loop. Growing CITY_SLUGS from 29 to
37 entries (see scraper_bazar.py's own module docstring for the new
entries and why no genuine oblast-level query was used instead) makes a
bounded run genuinely more likely on a real network, so this file ports
item 30's two load-bearing pieces of logic straight into scraper_bazar.py
before shipping the larger list, not after:

  1. fetch_listings() now takes deadline/on_checkpoint and persists which
     CITY_SLUGS index to resume from next run in GRID_STATE_FILE
     (data/bazar_grid_state.json), so a bounded run's leftover entries
     rotate to the FRONT of the next run instead of the loop always
     restarting at index 0 and starving the same tail (which, after this
     change, is exactly where all 8 of the new item-31 settlements live)
     forever.
  2. main()'s record_new()/checkpoint closure dedups by listing id
     (recorded_ids) so the incremental per-entry checkpoints - each one
     carrying fetch_listings()'s FULL accumulated all_listings.values(),
     not just that entry's own delta (see fetch_listings()'s own
     "on_checkpoint(list(all_listings.values()))" call) - don't
     double/triple-append a history snapshot for a listing that shows up
     in more than one checkpoint within the same run.

This file exercises the real scraper_bazar.py functions (not a
reimplementation), stubbing only the network (fetch_listings_page) and the
wall clock (time.monotonic), the same discipline
tests/test_olx_grid_crawl_timeout_fix.py already established for the
mechanism this ports from.

Run with: python3 -m unittest tests.test_bazar_grid_crawl_checkpoint -v
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

import scraper_bazar


@contextlib.contextmanager
def _patched(module, **attrs):
    """Sets module attributes for the duration of the block and restores
    their original values afterward - a plain, dependency-free stand-in
    for unittest.mock.patch.object, consistent with this repo's existing
    tests (see test_update_history.py's own manual try/finally attribute
    swap, and test_olx_grid_crawl_timeout_fix.py's identical helper, for
    the same purpose)."""
    original = {name: getattr(module, name) for name in attrs}
    for name, value in attrs.items():
        setattr(module, name, value)
    try:
        yield
    finally:
        for name, value in original.items():
            setattr(module, name, value)


# The 8 docs/backlog.md item 31 additions - see scraper_bazar.py's own
# CITY_SLUGS comment. All sit at the tail of the list (indices 29-36 of
# 37), which is exactly the range the old unbounded-from-index-0 loop
# would have starved on every single bounded run.
_NEW_SETTLEMENTS = {"Разград", "Смолян", "Петрич", "Троян", "Банско", "Свети Влас", "Обзор", "Велинград"}


class GridCrawlRotationTest(unittest.TestCase):
    """A fake clock drives two simulated bounded fetch_listings() runs
    back-to-back through the real function - only the network
    (fetch_listings_page) is stubbed - and confirms the rotation state
    persisted in GRID_STATE_FILE is what lets run 2 pick up where run 1
    left off, reaching the new item-31 settlements that a naive
    always-restart-at-0 loop could never get to inside one bounded run."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.grid_state_file = Path(self._tmpdir.name) / "bazar_grid_state.json"

        self.num_entries = len(scraper_bazar.CITY_SLUGS)
        self.assertEqual(self.num_entries, 37)  # 29 original + 8 item-31 additions
        # TIME_BUDGET_SECONDS / 20 divides the real 75*60 = 4500s budget
        # main() passes as fetch_listings()'s deadline into exactly 20
        # entries/run (225s each) - chosen so a 2nd run's first chunk
        # (order[20:37] + order[0:3], 20 entries) reaches every one of the
        # 8 new item-31 settlements (indices 29-36) inside that same run,
        # the same way test_olx_grid_crawl_timeout_fix.py's own per-oblast
        # pacing was chosen to land on a specific, checkable boundary.
        self.per_entry_seconds = scraper_bazar.TIME_BUDGET_SECONDS / 20
        self.clock = {"t": 0.0}

    def _run_bounded_crawl(self):
        visited = []

        def fake_fetch_listings_page(url, city_display):
            visited.append(city_display)
            self.clock["t"] += self.per_entry_seconds
            # An empty dict ends this entry's page loop after a single
            # page, same as a real "reached the end of results" page
            # (fetch_listings()'s own "not page_listings" check).
            return {}

        with _patched(scraper_bazar, GRID_STATE_FILE=self.grid_state_file,
                       fetch_listings_page=fake_fetch_listings_page), \
             _patched(scraper_bazar.time, monotonic=lambda: self.clock["t"]):
            deadline = scraper_bazar.TIME_BUDGET_SECONDS
            scraper_bazar.fetch_listings(deadline=deadline, on_checkpoint=None)

        return visited

    def _read_grid_state(self):
        # Read the persisted state file directly, rather than via
        # scraper_bazar.load_grid_state(), since that function looks up
        # the GRID_STATE_FILE global at call time and the patch above is
        # only in effect inside _run_bounded_crawl()'s own "with" block.
        return json.loads(self.grid_state_file.read_text(encoding="utf-8"))

    def test_run1_covers_first_20_of_37_and_persists_resume_index(self):
        visited = self._run_bounded_crawl()

        expected = [name for name, _slug in scraper_bazar.CITY_SLUGS[:20]]
        self.assertEqual(visited, expected)
        self.assertTrue(_NEW_SETTLEMENTS.isdisjoint(visited))  # none of run 1's 20 are item-31 additions

        state = self._read_grid_state()
        self.assertEqual(state.get("next_start_index"), 20)

    def test_run2_resumes_from_persisted_index_and_reaches_every_new_settlement(self):
        run1_visited = self._run_bounded_crawl()

        # Simulate a fresh run: reset the clock, keep the persisted grid
        # state file exactly as run 1 left it - that's the whole point,
        # run 2 must read it back and resume from there instead of
        # restarting at CITY_SLUGS[0].
        self.clock["t"] = 0.0
        run2_visited = self._run_bounded_crawl()

        expected_tail = [name for name, _slug in scraper_bazar.CITY_SLUGS[20:]]  # 17 entries, indices 20-36
        expected_wrap = [name for name, _slug in scraper_bazar.CITY_SLUGS[:3]]   # wraps to indices 0-2
        self.assertEqual(run2_visited, expected_tail + expected_wrap)
        self.assertEqual(len(run2_visited), 20)

        # The entire point of this fix: every one of the 8 item-31
        # additions is a real oblast capital or small/mid town this
        # session confirmed exists on bazar.bg but the old code could
        # never reach inside a single bounded run.
        self.assertTrue(_NEW_SETTLEMENTS.issubset(set(run2_visited)))

        state = self._read_grid_state()
        self.assertEqual(state.get("next_start_index"), (20 + 20) % 37)

        # Two runs' union covers every one of the 37 entries at least
        # once - full coverage within 2 runs, not just partial.
        union = set(run1_visited) | set(run2_visited)
        self.assertEqual(len(union), 37)


class RotationSanityCheck(unittest.TestCase):
    """Proves GridCrawlRotationTest actually discriminates the bug class
    it guards against, the same way test_olx_grid_crawl_timeout_fix.py's
    own CheckpointDedupSanityCheck does for its bug: reruns the exact same
    two bounded crawls WITHOUT ever persisting/reading GRID_STATE_FILE
    (the pre-fix shape - a bounded loop that always restarts at
    CITY_SLUGS[0]) and confirms that shape never reaches a single one of
    the 8 new item-31 settlements, across any number of runs, since they
    all sit past index 20 and every run covers only indices 0-19."""

    def setUp(self):
        self.num_entries = len(scraper_bazar.CITY_SLUGS)
        self.per_entry_seconds = scraper_bazar.TIME_BUDGET_SECONDS / 20
        self.clock = {"t": 0.0}

    def _run_naive_bounded_crawl_always_from_zero(self):
        # Reconstructs fetch_listings()'s own page/entry loop shape but
        # deliberately WITHOUT the GRID_STATE_FILE-backed start_index
        # rotation - the bug class item 30 (and now item 31) fixed.
        visited = []
        deadline = scraper_bazar.TIME_BUDGET_SECONDS
        for city_display, _slug in scraper_bazar.CITY_SLUGS:
            if self.clock["t"] >= deadline:
                break
            visited.append(city_display)
            self.clock["t"] += self.per_entry_seconds
        return visited

    def test_naive_always_from_zero_never_reaches_new_settlements(self):
        run1 = self._run_naive_bounded_crawl_always_from_zero()
        self.clock["t"] = 0.0
        run2 = self._run_naive_bounded_crawl_always_from_zero()

        self.assertEqual(run1, run2)  # the bug: identical every run, no rotation at all
        self.assertEqual(len(run1), 20)
        self.assertTrue(_NEW_SETTLEMENTS.isdisjoint(run1))
        self.assertTrue(_NEW_SETTLEMENTS.isdisjoint(run2))


def _make_listing(lid, price_eur, city="Разград"):
    return {
        "id": lid,
        "url": f"https://bazar.bg/obiava-{lid}",
        "photo": None,
        "price_eur": price_eur,
        "sqm": None,
        "area": city,
        "city": city,
        "title": f"Продава 2-СТАЕН, гр. {city}, Център",
        "portal": "bazar.bg",
        "lat": None,
        "lng": None,
        "category": "apartment",
    }


# Three overlapping checkpoint snapshots the way fetch_listings()'s
# on_checkpoint callback actually calls it: each one is the FULL
# accumulated all_listings.values() so far (see fetch_listings(): "on_
# checkpoint(list(all_listings.values()))"), not an incremental delta -
# so A and B appear in all three, C in the last two, D only in the last
# one - identical shape to test_olx_grid_crawl_timeout_fix.py's own
# _CHECKPOINT_BATCHES.
_LISTING_A = _make_listing("bazar_A", 100000)
_LISTING_B = _make_listing("bazar_B", 80000)
_LISTING_C = _make_listing("bazar_C", 60000)
_LISTING_D = _make_listing("bazar_D", 40000)

_CHECKPOINT_BATCHES = [
    [_LISTING_A, _LISTING_B],
    [_LISTING_A, _LISTING_B, _LISTING_C],
    [_LISTING_A, _LISTING_B, _LISTING_C, _LISTING_D],
]


class CheckpointDedupTest(unittest.TestCase):
    """Drives the REAL main() (its actual record_new()/checkpoint
    closure, not a reimplementation) with a fake fetch_listings() that
    calls the on_checkpoint it's handed three times with overlapping,
    fully-accumulated snapshots - exactly the shape the real
    fetch_listings() produces - and asserts every listing ends up with
    exactly one history snapshot despite the overlap."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.history_file = Path(self._tmpdir.name) / "history_bazar.json"
        self.leads_file = Path(self._tmpdir.name) / "leads_bazar.json"

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
        for batch in _CHECKPOINT_BATCHES:
            on_checkpoint([copy.deepcopy(l) for l in batch])
        return [copy.deepcopy(l) for l in _CHECKPOINT_BATCHES[-1]]

    def test_overlapping_checkpoints_each_listing_gets_exactly_one_snapshot(self):
        with _patched(scraper_bazar, HISTORY_FILE=self.history_file, LEADS_FILE=self.leads_file,
                      fetch_listings=self._fake_fetch_listings):
            scraper_bazar.main()

        history = json.loads(self.history_file.read_text(encoding="utf-8"))
        self.assertEqual(set(history.keys()), {"bazar_A", "bazar_B", "bazar_C", "bazar_D"})
        for lid in ("bazar_A", "bazar_B", "bazar_C", "bazar_D"):
            snapshots = history[lid]["snapshots"]
            self.assertEqual(
                len(snapshots), 1,
                f"{lid} ended up with {len(snapshots)} history snapshots "
                f"(expected exactly 1) after 3 overlapping checkpoint calls",
            )

        # The fix is a dedup, not a data loss - the final recorded prices
        # must still be each listing's real price, and D (only ever seen
        # in the LAST checkpoint) must still have made it in at all.
        self.assertEqual(history["bazar_A"]["snapshots"][0]["price_eur"], 100000)
        self.assertEqual(history["bazar_D"]["snapshots"][0]["price_eur"], 40000)


class CheckpointDedupSanityCheck(unittest.TestCase):
    """Sanity check that CheckpointDedupTest actually discriminates the
    bug class it guards against: reproduces main()'s record_new() shape
    WITHOUT its recorded_ids dedup filter (i.e. naively calling the real
    update_history() on the full accumulated checkpoint every time,
    instead of only on the delta) against the same three overlapping
    checkpoint batches, and confirms that DOES produce more than one
    snapshot for the listings that appear in more than one checkpoint."""

    def test_naive_checkpointing_without_id_dedup_double_appends(self):
        history = {}

        def buggy_record_new(listings_so_far):
            # The bug shape: no recorded_ids filter at all - every
            # checkpoint calls update_history() on its own full
            # accumulated snapshot.
            nonlocal history
            history = scraper_bazar.update_history(history, listings_so_far)

        for batch in _CHECKPOINT_BATCHES:
            buggy_record_new([copy.deepcopy(l) for l in batch])

        # A and B are in all 3 checkpoint batches -> 3 snapshots each.
        self.assertEqual(len(history["bazar_A"]["snapshots"]), 3)
        self.assertEqual(len(history["bazar_B"]["snapshots"]), 3)
        # C is in the last 2 batches -> 2 snapshots.
        self.assertEqual(len(history["bazar_C"]["snapshots"]), 2)
        # D is only in the last batch -> 1 snapshot (nothing to dedup yet).
        self.assertEqual(len(history["bazar_D"]["snapshots"]), 1)


class CityAreaParsedFromTextTest(unittest.TestCase):
    """docs/backlog.md item 31: a listing's city/area must come from its
    own card text (CITY_AREA_LINE_RE / VILLAGE_LINE_RE), not be trusted
    from the CITY_SLUGS query slug - see scraper_bazar.py's module
    docstring. Exercises the real fetch_listings_page() against a
    synthetic HTML fixture shaped like a real bazar.bg results page
    (same card structure fetch_listings_page() already parses: a link
    matching LISTING_LINK_RE, climbable to an ancestor whose text has
    exactly one "<price> €" mention)."""

    def setUp(self):
        self._orig_fetch_html = scraper_bazar.fetch_html

    def tearDown(self):
        scraper_bazar.fetch_html = self._orig_fetch_html

    def _page_html(self, card_lines):
        # Mirrors the real card shape fetch_listings_page() parses: a
        # title line, the price split across two lines ("<digits>" then a
        # bare "€"), and the location line - all inside one container
        # that also holds the listing link, same "climb from the link"
        # shape smallest_container_with_price() looks for.
        lines_html = "".join(f"<div>{line}</div>" for line in card_lines)
        return f'<html><body><div>{lines_html}<a href="/obiava-999888">link</a></div></body></html>'

    def test_city_leaking_from_a_neighboring_town_is_tagged_from_its_own_text(self):
        # The exact "incidental leakage" scenario the module docstring
        # flags: a query for one CITY_SLUGS entry ("Ловеч") returns a card
        # whose own text names a different real settlement ("Червен
        # бряг") - city/area must reflect the card's own text, not the
        # query's display name.
        html = self._page_html([
            "Продава 2-СТАЕН", "120000", "€", "гр. Червен бряг, Център",
        ])
        scraper_bazar.fetch_html = lambda url: html

        listings = scraper_bazar.fetch_listings_page("https://bazar.bg/obiavi/prodazhba-apartamenti/lovech", "Ловеч")

        self.assertEqual(len(listings), 1)
        listing = next(iter(listings.values()))
        self.assertEqual(listing["city"], "Червен бряг")
        self.assertEqual(listing["area"], "Център")

    def test_card_matching_neither_line_format_falls_back_to_query_display_name(self):
        html = self._page_html(["Продава 2-СТАЕН", "95000", "€", "some unparseable location text"])
        scraper_bazar.fetch_html = lambda url: html

        listings = scraper_bazar.fetch_listings_page("https://bazar.bg/obiavi/prodazhba-apartamenti/petrich", "Петрич")

        self.assertEqual(len(listings), 1)
        listing = next(iter(listings.values()))
        self.assertEqual(listing["city"], "Петрич")
        self.assertEqual(listing["area"], "Петрич")


if __name__ == "__main__":
    unittest.main(verbosity=2)
