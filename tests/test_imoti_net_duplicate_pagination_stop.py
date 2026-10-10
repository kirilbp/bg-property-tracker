"""
Regression tests for docs/backlog.md item 57's 2026-10-10 addendum:
scraper.py's fetch_listings() now stops a city's pagination early once a
long, unbroken run of still-FULL pages has added zero new listings,
instead of grinding on toward MAX_PAGES/the known page-200 403 block.

Why this exists (see scraper.py's own DUPLICATE_STOP_WINDOW comment for
the full writeup): item 57's original 2026-09-26 hypothesis - a site-side
card-markup change breaking smallest_container_with_price()/BGN_RE -
is DISPROVEN. Real production job logs (run 37915439804, 2026-10-09)
show no_container/no_bgn_match near zero even during the active-ratio
collapse; the dominant, overwhelming skip reason is `duplicate`. Burgas
that day paged 199 full pages (60 raw links/page) all the way to the
known page-200 block, but only 1,019/11,940 raw link encounters (8.5%)
were ever genuinely new - once ~34 pages' worth of real content had been
seen, every further page was re-serving already-collected listings.
Compare a healthy small city that never needs to page this deep (that
same run's Стара Загора: 410/826, 49.6% yield, duplicate=410 - exactly
the ~50% split expected from each card's own thumbnail + title anchor
both matching LISTING_LINK_RE).

Honesty check on what this sandbox can and cannot prove (no live
imoti.net access - see docs/backlog.md item 57's addendum): these tests
confirm the STOPPING LOGIC behaves correctly against synthetic HTML
shaped to match the real evidence above (a clean fresh-then-duplicate
split, a healthy even city, and a deliberately awkward trickle-of-real-
content-among-duplicates case to check the conservative threshold does
NOT cut real content off). They cannot confirm WHY imoti.net serves
heavily duplicated content past a certain page depth (sort-order drift
vs. caching vs. a deliberate anti-scraping tarpit all remain genuinely
unconfirmed) - only that, given that observed shape, this scraper now
spends far less time/requests paging through it.

This sandbox has no network egress to imoti.net, so fetch_with_retries()
is mocked throughout - no live dispatch, per this repo's CLAUDE.md.

Run with: python3 -m pytest tests/test_imoti_net_duplicate_pagination_stop.py -v
"""

import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper

PAGE_RE = re.compile(r"page=(\d+)")


def _page_num(url):
    m = PAGE_RE.search(url)
    return int(m.group(1)) if m else 1


def _card_html(listing_ids):
    """One page of real-shaped imoti.net cards: each listing gets TWO
    matching <a> tags (thumbnail + title) sharing one price-bearing
    container, mirroring the real site's own ~50% duplicate split (two
    anchors per real card) confirmed against a healthy city's own real
    yield stats (see module docstring) - not scraper.py's original
    single-anchor test fixture in test_imoti_net_yield_diagnostics.py,
    which was sufficient for that file's per-card extraction checks but
    doesn't reproduce the real duplicate-ratio shape this fix is about.
    """
    cards = []
    for lid in listing_ids:
        href = f"/en/obiava/prodava-apartment-sofia-{lid}/{lid}/"
        cards.append(
            f'<div class="card">'
            f'<a href="{href}"><img src="/img/{lid}.jpg"/></a>'
            f'<div class="body">for sale Two-bedroom apartment, Center 75 '
            f'м2 51000 € 100000 BGN</div>'
            f'<a href="{href}">Two-bedroom apartment</a>'
            f'</div>'
        )
    return f"<html><body>{''.join(cards)}</body></html>"


class DuplicateSaturationStopsPaginationEarlyTests(unittest.TestCase):
    """The Burgas-shaped case: a real run of fresh pages, then an
    unbroken run of pages that are purely re-serving already-collected
    listings - must stop once DUPLICATE_STOP_WINDOW consecutive full
    pages have added zero new listings, not grind on to MAX_PAGES."""

    def test_stops_after_window_of_zero_new_pages(self):
        fresh_pages = 15  # > DUPLICATE_STOP_WINDOW, matching item 57's
        # addendum evidence that real content ran out well before the
        # page-200 block (Burgas: ~34 pages' worth of real content).
        calls = {"n": 0}

        def fake_fetch(url):
            calls["n"] += 1
            page_num = _page_num(url)
            if page_num <= fresh_pages:
                start = (page_num - 1) * 30 + 1
                return _card_html(range(start, start + 30))
            # Every page past the fresh run re-serves page 1's listings -
            # already in `seen`, so this contributes zero NEW listings,
            # exactly the Burgas shape (duplicate=10,919 of 11,940).
            return _card_html(range(1, 31))

        with mock.patch("scraper.CITY_SLUGS", [("testcity", "Тестград")]), \
             mock.patch("scraper.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            listings = scraper.fetch_listings()

        # Stopped right at fresh_pages + DUPLICATE_STOP_WINDOW - not at
        # MAX_PAGES (420), not at some other count - the exact boundary
        # the window logic should hit.
        self.assertEqual(calls["n"], fresh_pages + scraper.DUPLICATE_STOP_WINDOW)
        self.assertEqual(len(listings), fresh_pages * 30)
        self.assertEqual({l["id"] for l in listings}, {str(i) for i in range(1, fresh_pages * 30 + 1)})

        printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        self.assertIn("stopping early", printed)
        self.assertIn("duplicate-saturated", printed)
        # This is a deliberate, intentional stop, not a truncation - the
        # misleading "may be truncated" warning (reserved for a real
        # fetch failure or hitting MAX_PAGES still full) must NOT appear.
        self.assertNotIn("may be truncated", printed)

    def test_healthy_small_city_is_never_mistaken_for_duplicate_saturated(self):
        # A healthy city's own ~50% duplicate split (two anchors per
        # distinct real card) never drops added-per-page anywhere near
        # zero - 12 full fresh pages (more than DUPLICATE_STOP_WINDOW),
        # each contributing 30 genuinely new listings, then a natural
        # empty page at the real end. Must page all the way to the real
        # end, completely unaffected by the new stop logic.
        total_fresh_pages = 12
        calls = {"n": 0}

        def fake_fetch(url):
            calls["n"] += 1
            page_num = _page_num(url)
            if page_num <= total_fresh_pages:
                start = (page_num - 1) * 30 + 1
                return _card_html(range(start, start + 30))
            return "<html><body></body></html>"  # natural end

        with mock.patch("scraper.CITY_SLUGS", [("testcity", "Тестград")]), \
             mock.patch("scraper.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            listings = scraper.fetch_listings()

        self.assertEqual(calls["n"], total_fresh_pages + 1)  # +1 for the empty page
        self.assertEqual(len(listings), total_fresh_pages * 30)

        printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        self.assertNotIn("stopping early", printed)
        self.assertNotIn("duplicate-saturated", printed)
        self.assertNotIn("may be truncated", printed)

    def test_trickle_of_new_listings_among_duplicates_is_not_cut_off(self):
        # Conservative-risk check: a sparse but real new listing appearing
        # once inside an otherwise-duplicate-heavy window must NOT trigger
        # an early stop (sum over that window is 1, not <=0) - the trickle
        # keeps the city paging, and its real content is still collected.
        # Only once a FULLY zero window follows does pagination actually
        # stop. This is the scenario the task's own brief calls out as
        # the real risk of getting this wrong - the fix must be
        # conservative enough not to drop it.
        calls = {"n": 0}

        def fake_fetch(url):
            calls["n"] += 1
            page_num = _page_num(url)
            if page_num == 1:
                return _card_html(range(1, 31))  # 30 fresh
            if page_num == 6:
                # 29 duplicates of page 1's ids + exactly 1 genuinely new
                # listing (id 9001) - a real trickle amid duplication.
                return _card_html(list(range(1, 30)) + [9001])
            if 2 <= page_num <= 15:
                return _card_html(range(1, 31))  # pure duplicates
            return _card_html(range(1, 31))  # keeps re-serving past that

        with mock.patch("scraper.CITY_SLUGS", [("testcity", "Тестград")]), \
             mock.patch("scraper.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            listings = scraper.fetch_listings()

        ids = {l["id"] for l in listings}
        # The trickled-in real listing (added on page 6) was collected -
        # every 10-page window containing it sums to >=1, not <=0, so no
        # stop fired while it was still inside the window; pagination
        # continued well past page 11 (where a naive "sum of last 10 is
        # small" check might have fired).
        self.assertIn("9001", ids)
        self.assertGreater(calls["n"], 11)
        # It does eventually stop once a truly clean zero-new window no
        # longer contains page 6's trickle - the first such window is
        # pages 7-16, so it stops right at page 16.
        self.assertEqual(calls["n"], 16)

        printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        self.assertIn("duplicate-saturated", printed)


class StopReasonLoggingIsDistinguishedTests(unittest.TestCase):
    """fetch_listings() must not conflate an intentional duplicate-
    saturation stop with a real fetch failure or hitting MAX_PAGES still
    full - those two genuinely may have left real content uncollected
    (the pre-existing "may be truncated" warning is correct for them);
    the new stop reason is confident enough about why it stopped that
    printing that same warning there would be actively misleading."""

    def test_fetch_failure_still_warns_about_possible_truncation(self):
        def fake_fetch(url):
            page_num = _page_num(url)
            if page_num == 1:
                return _card_html(range(1, 31))
            return None  # simulates the real page-200 403 block

        with mock.patch("scraper.CITY_SLUGS", [("testcity", "Тестград")]), \
             mock.patch("scraper.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            listings = scraper.fetch_listings()

        self.assertEqual(len(listings), 30)
        printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        self.assertIn("may be truncated", printed)
        self.assertNotIn("duplicate-saturated", printed)

    def test_max_pages_reached_still_full_still_warns(self):
        def fake_fetch(url):
            page_num = _page_num(url)
            start = (page_num - 1) * 30 + 1
            return _card_html(range(start, start + 30))  # always fresh, never ends

        with mock.patch("scraper.CITY_SLUGS", [("testcity", "Тестград")]), \
             mock.patch("scraper.MAX_PAGES", 5), \
             mock.patch("scraper.fetch_with_retries", side_effect=fake_fetch), \
             mock.patch("scraper.time.sleep"), \
             mock.patch("builtins.print") as mock_print:
            listings = scraper.fetch_listings()

        self.assertEqual(len(listings), 5 * 30)
        printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        self.assertIn("may be truncated", printed)
        self.assertNotIn("duplicate-saturated", printed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
