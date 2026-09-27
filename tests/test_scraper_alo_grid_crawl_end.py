"""
Regression tests for scraper_alo.py's fetch_listings() grid-crawl stop
condition (2026-09-27, investigating backlog item 61's alo.bg-vs-Sofia
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
end of the site" apart from "an actual outage is happening".

Correction (Missy's review): the first version of this fix stopped the
crawl on the very first PermanentlyGone, no retry required - a real
functional-regression risk, since a WAF/anti-bot layer serving a single
spurious 404 instead of a 429/503 mid-crawl (a known technique) would
have silently truncated that day's crawl while printing the *most*
confident, least-suspicious log message available. Fixed to require 2
consecutive PermanentlyGone responses before treating it as the real end
- still far faster than MAX_CONSECUTIVE_PAGE_FAILURES (5) wasted requests,
but no longer trusting a single occurrence blindly. Both real runs this
fix was built from showed several consecutive 404s in a row at the true
end, not one flaky one among successes, so requiring 2 does not risk
missing the real end.

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
    """Two consecutive 404s (PermanentlyGone) on the grid crawl stop it
    promptly, without consuming the MAX_CONSECUTIVE_PAGE_FAILURES budget -
    but a single, spurious 404 does NOT stop the crawl on its own."""

    def test_two_consecutive_404s_stop_the_crawl(self):
        # Page 1 succeeds with real listings; pages 2 and 3 are genuine
        # 404s (the real end of pagination) - matches both real runs' own
        # shape of several consecutive 404s in a row at the true end.
        page_1_html = _card_html(["1000001", "1000002"])

        def fake_fetch(url):
            if url == scraper_alo.SEARCH_URL:
                return page_1_html
            raise scraper_alo.PermanentlyGone(url)

        with mock.patch("scraper_alo.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper_alo.time.sleep"):
            listings = scraper_alo.fetch_listings()

        # Real listings from the one real page are kept.
        self.assertEqual({l["id"] for l in listings}, {"alo_1000001", "alo_1000002"})

    def test_single_spurious_404_does_not_stop_the_crawl(self):
        # Page 2 is a lone 404 (e.g. a WAF/anti-bot blip), but page 3
        # succeeds again with real listings - the crawl must NOT have
        # stopped after the single 404, and must pick page 3's listings
        # up. This is the exact regression the 2-consecutive threshold
        # guards against.
        def fake_fetch(url):
            if url == scraper_alo.SEARCH_URL:
                return _card_html(["5000001"])
            if "page=2" in url:
                raise scraper_alo.PermanentlyGone(url)
            if "page=3" in url:
                return _card_html(["5000002"])
            raise scraper_alo.PermanentlyGone(url)

        with mock.patch("scraper_alo.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper_alo.time.sleep"):
            listings = scraper_alo.fetch_listings()

        # Both the pre- and post-blip real pages' listings were kept - the
        # single spurious 404 on page 2 did not truncate the crawl there.
        self.assertEqual({l["id"] for l in listings}, {"alo_5000001", "alo_5000002"})

    def test_404_is_not_counted_toward_consecutive_page_failures(self):
        # Two consecutive 404s must not print the "N/5 consecutive"
        # transient-failure framing nor the "looks like a real outage"
        # message - those are reserved for actual transient failures
        # (fetch_with_retries returning None after exhausting retries, not
        # raising PermanentlyGone).
        def fake_fetch(url):
            if url == scraper_alo.SEARCH_URL:
                return _card_html(["2000001"])
            raise scraper_alo.PermanentlyGone(url)

        with mock.patch("scraper_alo.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper_alo.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            scraper_alo.fetch_listings()

        printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertNotIn("consecutive page failures", printed)
        self.assertNotIn("looks like a real outage", printed)
        self.assertIn("reached the real end of pagination", printed)
        # The first 404 is logged as 1/2, the second as 2/2, before the
        # crawl actually stops.
        self.assertIn("1/2 consecutive", printed)
        self.assertIn("2/2 consecutive", printed)

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

    def test_transient_failure_then_404s_stop_via_the_404s_not_the_threshold(self):
        # A real transient blip (below the consecutive-failure threshold)
        # followed by two genuine consecutive 404s must still stop
        # cleanly on the 404s, not require them to also accumulate toward
        # the transient-failure counter.
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

    def test_success_between_two_404s_resets_the_gone_counter(self):
        # A lone 404 followed by a real success page must not carry over
        # toward a later, genuinely-consecutive pair - the counter resets
        # on any successful page, same as consecutive_failures does.
        calls = {"n": 0}

        def fake_fetch(url):
            calls["n"] += 1
            if calls["n"] == 1:
                return _card_html(["6000001"])
            if calls["n"] == 2:
                raise scraper_alo.PermanentlyGone(url)  # one lone 404
            if calls["n"] == 3:
                return _card_html(["6000002"])  # real page resets the counter
            raise scraper_alo.PermanentlyGone(url)  # real end starts here

        with mock.patch("scraper_alo.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper_alo.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            listings = scraper_alo.fetch_listings()

        printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
        # If the counter hadn't reset, the crawl would have stopped one
        # page earlier (on call 4, the first 404 after the reset) instead
        # of call 5 - so both real pages must be present.
        self.assertEqual(
            {l["id"] for l in listings}, {"alo_6000001", "alo_6000002"}
        )
        self.assertIn("reached the real end of pagination", printed)


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
