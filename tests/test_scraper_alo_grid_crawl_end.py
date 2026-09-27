"""
Regression tests for scraper_alo.py's fetch_listings() grid-crawl stop
condition (2026-09-27, investigating backlog item 60's alo.bg-vs-Sofia
finding).

Real production job logs (workflow run 35973606926, 2026-09-24, and
workflow run 36113518576, 2026-09-25 - both scraper_alo.py steps, read in
full, page-by-page) show alo.bg returns a genuine HTTP 404 for the first
page past its real last page, rather than a page that loads with zero
listings (the "stop on empty page" signal every sibling scraper's crawl
loop relies on). Before this fix, fetch_listings_page() caught that 404
itself (PermanentlyGone) and returned a plain None - identical to what a
genuinely transient failure (a timeout or 5xx) also returns - so
fetch_listings()'s own loop could not tell "reached the confirmed real
end of the site" apart from "an actual outage is happening". Both real
runs cost 4 extra wasted page requests (5 consecutive "failures" required
before stopping) to reach a stop they should have made immediately, and -
the real risk this test guards against - a genuine mid-crawl outage would
have printed the exact same "looks like a real outage" message as an
ordinary, harmless end-of-day completion, making the two impossible to
tell apart from a run's own logs alone.

This sandbox has no network egress to alo.bg, so fetch_with_retries() is
mocked throughout - no live dispatch, per this repo's CLAUDE.md.

Run with: python3 -m pytest tests/test_scraper_alo_grid_crawl_end.py -v
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper_alo


class GridCrawlStopsCleanlyOnRealPastEndTests(unittest.TestCase):
    """A 404 (PermanentlyGone) on the grid crawl stops immediately, without
    consuming any of the MAX_CONSECUTIVE_PAGE_FAILURES budget - the same
    trust a single empty page (`if not link_count: break`) already gets."""

    def test_single_404_stops_the_crawl_immediately(self):
        # Page 1 succeeds with real listings; page 2 is a genuine 404 (the
        # real end of pagination) - matches both real runs' own shape.
        page_1_html = _card_html(["1000001", "1000002"])

        def fake_fetch(url):
            if "page=2" not in url and url == scraper_alo.SEARCH_URL:
                return page_1_html
            raise scraper_alo.PermanentlyGone(url)

        with mock.patch("scraper_alo.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper_alo.time.sleep"):
            listings = scraper_alo.fetch_listings()

        # Real listings from the one real page are kept.
        self.assertEqual({l["id"] for l in listings}, {"alo_1000001", "alo_1000002"})

    def test_404_is_not_counted_toward_consecutive_page_failures(self):
        # A single 404 must not print the "N/5 consecutive" failure framing
        # nor the "looks like a real outage" message - those are reserved
        # for actual transient failures (fetch_with_retries returning None
        # after exhausting retries, not raising PermanentlyGone).
        def fake_fetch(url):
            if url == scraper_alo.SEARCH_URL:
                return _card_html(["2000001"])
            raise scraper_alo.PermanentlyGone(url)

        with mock.patch("scraper_alo.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper_alo.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            scraper_alo.fetch_listings()

        printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertNotIn("consecutive", printed)
        self.assertNotIn("looks like a real outage", printed)
        self.assertIn("reached the real end of pagination", printed)

    def test_genuine_transient_failures_still_require_five_in_a_row(self):
        # A real transient failure (fetch_with_retries exhausts retries and
        # returns None, no PermanentlyGone raised) must still go through
        # the existing MAX_CONSECUTIVE_PAGE_FAILURES accounting, completely
        # unaffected by this fix - this is the "actual outage" case the
        # message is meant for.
        call_count = {"n": 0}

        def fake_fetch(url):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _card_html(["3000001"])
            return None  # every page after the first is a transient failure

        with mock.patch("scraper_alo.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper_alo.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            scraper_alo.fetch_listings()

        printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertIn(
            f"{scraper_alo.MAX_CONSECUTIVE_PAGE_FAILURES} consecutive page failures",
            printed,
        )
        self.assertIn("looks like a real outage", printed)
        # Exactly MAX_CONSECUTIVE_PAGE_FAILURES transient-failure pages were
        # attempted after the first real one, matching the pre-existing
        # (unchanged) threshold.
        self.assertEqual(call_count["n"], 1 + scraper_alo.MAX_CONSECUTIVE_PAGE_FAILURES)

    def test_transient_failure_then_404_stops_via_the_404_not_the_threshold(self):
        # A real transient blip (below the consecutive-failure threshold)
        # followed by a genuine 404 must still stop cleanly on the 404,
        # not require the 404 itself to also accumulate toward the
        # transient-failure counter.
        calls = {"n": 0}

        def fake_fetch(url):
            calls["n"] += 1
            if calls["n"] == 1:
                return _card_html(["4000001"])
            if calls["n"] in (2, 3):
                return None  # two transient blips, below the threshold of 5
            raise scraper_alo.PermanentlyGone(url)

        with mock.patch("scraper_alo.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper_alo.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            listings = scraper_alo.fetch_listings()

        printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertIn("reached the real end of pagination", printed)
        self.assertNotIn("looks like a real outage", printed)
        self.assertEqual({l["id"] for l in listings}, {"alo_4000001"})


def _card_html(listing_ids):
    """A minimal real-shaped alo.bg listing-grid page: one card per id,
    matching what fetch_listings_page()'s own LISTING_LINK_RE/PRICE_RE
    expect (see scraper_alo.py's own module docstring for the real card
    shape this mirrors)."""
    cards = "".join(
        f'<div><a href="/some-flat-{lid}">Some flat {lid}</a>'
        f'<span>Слънчев бряг, Бургас Цена : 50 000 €</span></div>'
        for lid in listing_ids
    )
    return f"<html><body>{cards}</body></html>"


if __name__ == "__main__":
    unittest.main()
