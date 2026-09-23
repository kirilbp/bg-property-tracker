"""
Regression tests for docs/backlog.md item 31 ("imot.bg: nationwide coverage
is structurally limited to a fixed ~25-city allowlist") on scraper_imot.py.

scraper_imot.py's CITY_SLUGS (25 cities) achieved "nationwide" coverage by
querying only a fixed, manually-curated list of Bulgaria's largest cities -
Bulgaria's ~230 other towns and ~5,000 villages were structurally never
queried at all, and every listing's `city` field was tagged directly from
which CITY_SLUGS entry produced it (not re-parsed from the listing's own
card text). The fix (this module's own commit) added three genuinely new,
load-bearing pieces of logic:

  1. OBLAST_SLUGS (27 oblasts) - a second, oblast-level query phase added
     on top of the existing CITY_SLUGS phase, reusing scraper_olx.py's own
     checkpointed/rotating-index mechanism (fetch_listings()'s
     deadline/on_checkpoint, GRID_STATE_FILE persisting which OBLAST_SLUGS
     index to resume the OBLAST phase from next run) - the CITY_SLUGS phase
     itself stays unbounded/un-rotated, since it already reliably finishes
     within the workflow's own timeout on its own.
  2. parse_listings_page() now derives a listing's `city` AND `area` from
     its own card text (CITY_AREA_LINE_RE/CITY_ONLY_LINE_RE/VILLAGE_LINE_RE)
     instead of trusting the city/oblast display name that was queried -
     required because a single oblast query returns listings from many real
     settlements, not just its own namesake.
  3. main()'s record_new()/checkpoint closure dedups by listing id
     (recorded_ids) so the incremental per-city/per-oblast checkpoints -
     each one carrying fetch_listings()'s FULL accumulated seen.values(),
     not just that query's own delta - don't double/triple-append a history
     snapshot for a listing that shows up in more than one checkpoint
     within the same run (same risk scraper_olx.py's own item 30 fix
     already guards against, reused here rather than reinvented).

This file exercises the REAL scraper_imot.py functions throughout (never a
reimplementation of the logic under test), stubbing only Playwright/network
at the same granularity tests/test_olx_grid_crawl_timeout_fix.py stubs
scraper_olx.py's analogous fetch_listings_page() - here that's
scraper_imot.py's own per-query helper, _crawl_one_query() - except for
CityAreaFromCardTextTest, which calls the real parse_listings_page()
directly against synthetic card HTML with no stubbing at all.

Run with: python3 -m unittest tests.test_imot_oblast_grid_crawl -v
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

import scraper_imot


@contextlib.contextmanager
def _patched(module, **attrs):
    """Sets module attributes for the duration of the block and restores
    their original values afterward - a plain, dependency-free stand-in
    for unittest.mock.patch.object, consistent with this repo's existing
    tests (see test_olx_grid_crawl_timeout_fix.py/test_update_history.py's
    own manual try/finally attribute swap for the same purpose)."""
    original = {name: getattr(module, name) for name in attrs}
    for name, value in attrs.items():
        setattr(module, name, value)
    try:
        yield
    finally:
        for name, value in original.items():
            setattr(module, name, value)


class _FakeGeocoder:
    """Stands in for geo_utils.Geocoder - no disk cache, no network, just
    enough surface (geocode_cached_only/save) for parse_listings_page()/
    fetch_listings() to call without erroring."""

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


def _make_card_html(obiava_id, lines):
    # obiava_id must match LISTING_LINK_RE (r"/obiava-(\d[a-z]\d{10,})-") -
    # digit, one lowercase letter, then 10+ digits.
    body = "\n".join(f"<div>{l}</div>" for l in lines)
    return f'<html><body><div class="card"><a href="/obiava-{obiava_id}-nqk">{body}</a></div></body></html>'


class CityAreaFromCardTextTest(unittest.TestCase):
    """Exercises the real parse_listings_page() directly (no Playwright
    stubbing needed - it takes already-fetched HTML) against synthetic
    cards shaped like the module docstring's documented per-line layout,
    proving city/area now come from the card's own text rather than the
    query's display name (docs/backlog.md item 31, point 3)."""

    def setUp(self):
        self.geocoder = _FakeGeocoder()

    def _parse_one(self, obiava_id, lines, query_display):
        seen = {}
        n = scraper_imot.parse_listings_page(_make_card_html(obiava_id, lines), seen, self.geocoder, query_display)
        self.assertEqual(n, 1)
        self.assertEqual(len(seen), 1)
        return next(iter(seen.values()))

    def test_city_with_area_parsed_from_card_not_query(self):
        # The query display name is deliberately wrong ("Ловеч" - as an
        # oblast-level "oblast-lovech" query would pass) while the card's
        # own text plainly says Plovdiv - proving the real city comes from
        # the card, not the query.
        l = self._parse_one("9a12345678901", ["Продава 2-СТАЕН", "град Пловдив, Тракия", "85000 €", "65 кв.м, ет.3"],
                             query_display="Ловеч")
        self.assertEqual(l["city"], "Пловдив")
        self.assertEqual(l["area"], "Тракия")

    def test_village_listing_city_equals_area(self):
        l = self._parse_one("9a12345678902", ["Продава КЪЩА", "с. Велчево", "45000 €", "120 кв.м, двор"],
                             query_display="Ловеч")
        self.assertEqual(l["city"], "Велчево")
        self.assertEqual(l["area"], "Велчево")

    def test_city_with_no_comma_still_recovers_real_town_name(self):
        # A smaller town's card may have no separate named area at all -
        # CITY_ONLY_LINE_RE's fallback tier. Real-world motivating case
        # (docs/decisions.md 2026-09-23 location-allocation entry): imot.bg
        # groups Cherven Bryag listings under a "grad-lovech"/
        # "oblast-lovech" query even though the town is really in Pleven
        # oblast - if the card's own text says the real town name, this
        # must recover it instead of inheriting the query's wrong claim.
        l = self._parse_one("9a12345678904", ["Продава КЪЩА", "град Червен бряг", "30000 €", "90 кв.м"],
                             query_display="Ловеч")
        self.assertEqual(l["city"], "Червен бряг")
        self.assertEqual(l["area"], "Червен бряг")

    def test_fallback_to_query_display_only_when_no_line_matches(self):
        l = self._parse_one("9a12345678903", ["Продава ОФИС", "85000 €", "65 кв.м"], query_display="Пловдив")
        self.assertEqual(l["city"], "Пловдив")
        self.assertEqual(l["area"], "Пловдив")

    def test_not_vacuous_old_query_trusting_behavior_would_get_it_wrong(self):
        # Reconstructs the OLD (pre-fix) tagging rule this module's own
        # docstring described: "Each listing's city is tagged directly from
        # which CITY_SLUGS entry produced it... not re-parsed from text."
        # That old rule is exactly "city = query_display, unconditionally" -
        # proving this test class discriminates the real fix, not just
        # checking a tautology, by showing the old rule gets the Plovdiv
        # card wrong when queried as an oblast-level "Ловеч" page.
        old_rule_city = "Ловеч"  # what CITY_SLUGS/OBLAST_SLUGS-trusting tagging would have produced
        real = self._parse_one("9a12345678905", ["Продава 2-СТАЕН", "град Пловдив, Тракия", "85000 €", "65 кв.м"],
                                query_display="Ловеч")
        self.assertNotEqual(real["city"], old_rule_city)
        self.assertEqual(real["city"], "Пловдив")


def _fake_crawl_factory(clock, per_query_seconds, visited_log):
    """Builds a fake _crawl_one_query() - records which query_display was
    visited, advances the shared fake clock by per_query_seconds, and
    reports "done after one page" (mirrors
    test_olx_grid_crawl_timeout_fix.py's own fake_fetch_listings_page()
    returning 0 to end a query's pagination immediately)."""

    def fake_crawl_one_query(page, query_display, search_url, seen, geocoder, deadline):
        visited_log.append(query_display)
        clock["t"] += per_query_seconds
        return 0, False  # (new_count, interrupted) - not interrupted, 0 new

    return fake_crawl_one_query


class GridCrawlPhaseTest(unittest.TestCase):
    """Reconstruction-style harness (same shape as
    tests/test_olx_grid_crawl_timeout_fix.py's GridCrawlRotationTest) for
    scraper_imot.py's two-phase fetch_listings(): a fake clock drives two
    simulated bounded runs back-to-back through the REAL fetch_listings(),
    with only _crawl_one_query() (the network-touching leaf, analogous to
    scraper_olx.py's own fetch_listings_page()) and Playwright stubbed."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.grid_state_file = Path(self._tmpdir.name) / "imot_grid_state.json"
        self.clock = {"t": 0.0}
        # City-level phase is unbounded by design (see module docstring) -
        # zero simulated cost per city so it never competes with the
        # deadline, matching real behavior (it reliably finishes fast).
        self.per_city_seconds = 0.0
        # 27 oblasts, budget chosen to cover exactly 13 per bounded run
        # (13 * 10 = 130) - leaves 14 for a following run, so two runs
        # together do NOT cover every oblast (mirrors the olx test's own
        # "26 of 26, not all" style assertion - here 26 of 27).
        self.per_oblast_seconds = 10.0
        self.deadline_budget = 130.0

    def _run_bounded_crawl(self):
        city_visited = []
        oblast_visited = []

        def fake_crawl(page, query_display, search_url, seen, geocoder, deadline):
            names = {n for n, _ in scraper_imot.CITY_SLUGS}
            if query_display in names and len(city_visited) < len(scraper_imot.CITY_SLUGS) \
                    and query_display not in city_visited:
                # City-level phase call (visited in CITY_SLUGS order, once
                # each, before any oblast call - see the assertion below).
                city_visited.append(query_display)
                self.clock["t"] += self.per_city_seconds
                return 0, False
            oblast_visited.append(query_display)
            self.clock["t"] += self.per_oblast_seconds
            return 0, False

        with _patched(scraper_imot, GRID_STATE_FILE=self.grid_state_file,
                       Geocoder=_FakeGeocoder, sync_playwright=_fake_sync_playwright,
                       _crawl_one_query=fake_crawl), \
             _patched(scraper_imot.time, monotonic=lambda: self.clock["t"]):
            scraper_imot.fetch_listings(deadline=self.deadline_budget, on_checkpoint=None)

        return city_visited, oblast_visited

    def _read_grid_state(self):
        return json.loads(self.grid_state_file.read_text(encoding="utf-8"))

    def test_city_phase_always_covers_all_cities_unrotated(self):
        city_visited, _oblast_visited = self._run_bounded_crawl()
        expected = [name for name, _slug in scraper_imot.CITY_SLUGS]
        self.assertEqual(city_visited, expected)

    def test_run1_covers_first_13_of_27_oblasts_and_persists_resume_index(self):
        _city_visited, oblast_visited = self._run_bounded_crawl()

        expected = [name for name, _slug in scraper_imot.OBLAST_SLUGS[:13]]
        self.assertEqual(oblast_visited, expected)

        state = self._read_grid_state()
        self.assertEqual(state.get("next_start_index"), 13)

    def test_run2_resumes_oblast_rotation_while_city_phase_repeats_in_full(self):
        city1, oblast1 = self._run_bounded_crawl()

        self.clock["t"] = 0.0
        city2, oblast2 = self._run_bounded_crawl()

        # City-level phase: identical full coverage both runs (unrotated).
        self.assertEqual(city1, city2)
        self.assertEqual(len(city1), len(scraper_imot.CITY_SLUGS))

        # Oblast-level phase: run 2 picks up exactly where run 1 left off.
        expected2 = [name for name, _slug in scraper_imot.OBLAST_SLUGS[13:26]]
        self.assertEqual(oblast2, expected2)
        self.assertIn("Ловеч", oblast2)  # the oblast the CITY_SLUGS-only gap chronically missed real villages in

        state = self._read_grid_state()
        self.assertEqual(state.get("next_start_index"), 26)

        union = set(oblast1) | set(oblast2)
        self.assertEqual(len(union), 26)
        self.assertNotEqual(len(union), 27)
        self.assertEqual(len(oblast1), 13)
        self.assertEqual(len(oblast2), 13)

    def test_not_vacuous_naive_unrotated_loop_would_starve_the_same_tail(self):
        # Reconstructs the pre-fix shape: OBLAST_SLUGS always restarted at
        # index 0 with no persisted state, the exact bug docs/backlog.md
        # item 30 already found and fixed once for scraper_olx.py. Proves
        # this test class actually discriminates real rotation logic,
        # not just something dict/list order gives it for free.
        def naive_bounded_run(clock):
            visited = []
            for name, _slug in scraper_imot.OBLAST_SLUGS:
                if clock["t"] >= self.deadline_budget:
                    break
                visited.append(name)
                clock["t"] += self.per_oblast_seconds
            return visited

        clock = {"t": 0.0}
        naive_run1 = naive_bounded_run(clock)
        clock["t"] = 0.0
        naive_run2 = naive_bounded_run(clock)

        # Without rotation, run 2 covers the SAME first 13 oblasts as run 1
        # instead of the next 13 - unlike the real fetch_listings() above.
        self.assertEqual(naive_run1, naive_run2)
        self.assertNotIn("Ловеч", naive_run2)  # index 22 - past the naive 13-oblast cutoff every single run


def _make_listing(lid, price_eur, city="София", area="Център"):
    return {
        "id": lid,
        "url": f"https://www.imot.bg/obiava-{lid}.html",
        "photo": None,
        "price_eur": price_eur,
        "sqm": None,
        "area": area,
        "city": city,
        "title": f"Апартамент {lid}, {area}",
        "portal": "imot.bg",
        "lat": None,
        "lng": None,
        "category": "apartment",
    }


# Simulates fetch_listings()'s real checkpoint shape: on_checkpoint fires
# once per completed city AND once per completed oblast, each call carrying
# the FULL accumulated seen.values() so far (see fetch_listings(): "
# on_checkpoint(list(seen.values()), geocoder)" in both phases) - not an
# incremental per-query delta. "imot_SOFIA" appears in every checkpoint here
# on purpose: it's the listing docs/backlog.md item 31 point 4 flags as the
# realistic overlap case (a Sofia listing returned by both the city-level
# "grad-sofiya" query AND the oblast-level "oblast-sofiya" query, each its
# own completed-query checkpoint).
_LISTING_SOFIA = _make_listing("imot_SOFIA", 150000)
_LISTING_B = _make_listing("imot_B", 80000)
_LISTING_C = _make_listing("imot_C", 60000)

_CHECKPOINT_BATCHES = [
    [_LISTING_SOFIA],                              # after e.g. "grad-sofiya" (city phase)
    [_LISTING_SOFIA, _LISTING_B],                   # after e.g. "grad-plovdiv" (city phase)
    [_LISTING_SOFIA, _LISTING_B],                   # after e.g. "oblast-sofiya" (oblast phase) - SOFIA again
    [_LISTING_SOFIA, _LISTING_B, _LISTING_C],       # after e.g. "oblast-lovech" (oblast phase)
]


class CheckpointDedupTest(unittest.TestCase):
    """Reconstruction of the same checkpoint-dedup harness
    tests/test_olx_grid_crawl_timeout_fix.py already ships for
    scraper_olx.py, adapted to scraper_imot.py's two-phase (city + oblast)
    checkpointing: drives the REAL main() (its actual
    record_new()/checkpoint closure, not a reimplementation) with a fake
    fetch_listings() that calls the on_checkpoint it's handed four times
    with overlapping, fully-accumulated snapshots - including
    "imot_SOFIA" appearing in checkpoints from BOTH a simulated city-phase
    query and a simulated oblast-phase query - asserting every listing
    still ends up with exactly one history snapshot despite the overlap."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.history_file = Path(self._tmpdir.name) / "history_imot.json"
        self.leads_file = Path(self._tmpdir.name) / "leads_imot.json"

    def _fake_fetch_listings(self, deadline=None, on_checkpoint=None):
        # Old (pre-fix) main() called "fetch_listings()" with no arguments
        # at all - on_checkpoint never got wired up. Raising here (rather
        # than silently skipping the checkpoint calls) is what makes this
        # test fail loudly against that shape instead of passing vacuously.
        if on_checkpoint is None:
            raise TypeError(
                "fetch_listings() was called without on_checkpoint - the real "
                "fix's main() always passes its checkpoint closure"
            )
        fake_geocoder = _FakeGeocoder()
        for batch in _CHECKPOINT_BATCHES:
            on_checkpoint([copy.deepcopy(l) for l in batch], fake_geocoder)
        return [copy.deepcopy(l) for l in _CHECKPOINT_BATCHES[-1]]

    def test_overlapping_city_and_oblast_checkpoints_each_listing_gets_exactly_one_snapshot(self):
        with _patched(scraper_imot, HISTORY_FILE=self.history_file, LEADS_FILE=self.leads_file,
                      fetch_listings=self._fake_fetch_listings):
            scraper_imot.main()

        history = json.loads(self.history_file.read_text(encoding="utf-8"))
        self.assertEqual(set(history.keys()), {"imot_SOFIA", "imot_B", "imot_C"})
        for lid in ("imot_SOFIA", "imot_B", "imot_C"):
            snapshots = history[lid]["snapshots"]
            self.assertEqual(
                len(snapshots), 1,
                f"{lid} ended up with {len(snapshots)} history snapshots "
                f"(expected exactly 1) after 4 overlapping city+oblast checkpoint calls",
            )

        # A dedup, not a data loss: real prices preserved, and C (only ever
        # seen in the LAST checkpoint) still made it in.
        self.assertEqual(history["imot_SOFIA"]["snapshots"][0]["price_eur"], 150000)
        self.assertEqual(history["imot_C"]["snapshots"][0]["price_eur"], 60000)

    def test_not_vacuous_naive_checkpointing_without_id_dedup_double_appends(self):
        # Reproduces main()'s record_new() shape WITHOUT its recorded_ids
        # dedup filter (i.e. naively calling the real update_history() on
        # the full accumulated checkpoint every time) against the same
        # four overlapping batches, confirming that DOES produce more than
        # one snapshot for imot_SOFIA/imot_B - proving CheckpointDedupTest
        # above actually discriminates the fix, not a vacuous pass.
        history = {}

        def buggy_record_new(listings_so_far):
            nonlocal history
            history = scraper_imot.update_history(history, listings_so_far)

        for batch in _CHECKPOINT_BATCHES:
            buggy_record_new([copy.deepcopy(l) for l in batch])

        # imot_SOFIA is in all 4 batches -> 4 snapshots.
        self.assertEqual(len(history["imot_SOFIA"]["snapshots"]), 4)
        # imot_B is in the last 3 batches -> 3 snapshots.
        self.assertEqual(len(history["imot_B"]["snapshots"]), 3)
        # imot_C is only in the last batch -> 1 snapshot (nothing to dedup yet).
        self.assertEqual(len(history["imot_C"]["snapshots"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
