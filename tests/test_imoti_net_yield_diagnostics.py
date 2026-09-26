"""
Regression coverage for docs/backlog.md item 57 (imoti.net active-ratio
collapse investigation, 2026-09-26).

scraper.py's fetch_listings_page() used to silently `continue` past a raw
<a>-tag match that didn't turn into a saved listing, with no logging at
all - confirmed, from real production job logs, that this hid a real
~83% collapse in per-page extraction yield (~30/page on 2026-09-22 down
to ~5/page on every run since 2026-09-24, with the raw per-page <a>-tag
count completely unchanged) for 3+ days before it was noticed only
because the aggregate active-ratio freshness check happened to also trip.

This does NOT fix that regression - the real cause needs live imoti.net
HTML this sandbox's egress proxy blocks (confirmed via both `curl` and
`WebFetch` - see docs/decisions.md's 2026-09-26 entry). It only adds an
optional `skip_stats` counter to fetch_listings_page()/fetch_listings()
so the NEXT time this happens, the very next run's own log tells a human
(or agent) exactly which check is rejecting most of a page's real
listings - no_container, no_bgn_match, price_under_1000, no_title_match,
or duplicate - instead of requiring the multi-hour GitHub Actions log
archaeology this investigation needed.

Verified here against synthetic HTML fixtures (this sandbox has no way
to fetch real, current imoti.net HTML to test against - see above), and
by confirming this is purely additive: every extraction outcome (which
listings get added to `seen`, with what fields) is byte-for-byte
identical whether or not skip_stats is passed.
"""

import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper


def _card_html(listing_id, price_bgn, price_eur, sqm=75, desc="Two-bedroom apartment, Center",
                extra_bgn_mentions=0):
    """A single synthetic imoti.net-shaped listing card: one <a> tag
    whose href matches LISTING_LINK_RE, wrapped in a container whose text
    matches BGN_RE/SQM_RE/DESC_RE the same way a real card's text does
    (confirmed against the real regexes in scraper.py, not guessed).
    `extra_bgn_mentions` lets a test push the BGN-mention count in this
    card's own container past MAX_PRICE_MENTIONS (2), simulating a card
    whose price is now shown in more places than before - one concrete,
    plausible shape the real regression could take (see the module
    docstring), without claiming this IS the real cause.
    """
    extra = " ".join(f"{100 + i} BGN" for i in range(extra_bgn_mentions))
    return (
        f'<div class="card">'
        f'<a href="/en/obiava/prodava-apartment-sofia/{listing_id}/">'
        f'<img src="/img/{listing_id}.jpg"/></a>'
        f'<div class="body">for sale {desc} {sqm} м2 {price_eur} € '
        f'{price_bgn} BGN {extra}</div>'
        f'</div>'
    )


class FetchListingsPageSkipStatsTest(unittest.TestCase):
    def _run(self, html, seen=None, skip_stats=None):
        seen = {} if seen is None else seen
        import bs4
        real_soup = bs4.BeautifulSoup
        # fetch_with_retries() does the real HTTP GET - stub it so this
        # test runs on synthetic HTML with no network access, matching
        # this project's existing pattern for scraper unit tests.
        orig = scraper.fetch_with_retries
        scraper.fetch_with_retries = lambda url: html
        try:
            link_count = scraper.fetch_listings_page(
                "https://www.imoti.net/en/obiavi/r/prodava/sofia", seen, "София",
                skip_stats=skip_stats,
            )
        finally:
            scraper.fetch_with_retries = orig
        return link_count, seen

    def test_normal_card_is_added_and_counted(self):
        html = _card_html("111", price_bgn=146770, price_eur=75000)
        stats = Counter()
        link_count, seen = self._run(html, skip_stats=stats)
        self.assertEqual(link_count, 1)
        self.assertIn("111", seen)
        # price_eur is derived by the real code from price_bgn (not from
        # the price_eur text embedded in the fixture, which only exists
        # to satisfy DESC_RE's own "<title> <digits> €" shape) - round(
        # 146770 / 1.95583).
        self.assertEqual(seen["111"]["price_eur"], round(146770 / scraper.BGN_TO_EUR))
        self.assertEqual(stats["added"], 1)
        self.assertEqual(stats["no_container"], 0)
        self.assertEqual(stats["no_title_match"], 0)
        self.assertEqual(stats["price_under_1000"], 0)
        self.assertEqual(stats["duplicate"], 0)

    def test_too_many_price_mentions_counted_as_no_container(self):
        # 1 (own price) + 3 extra = 4 BGN mentions in the innermost
        # container, past MAX_PRICE_MENTIONS (2) at every level up to
        # max_levels - smallest_container_with_price() returns None,
        # exactly the shape a "price now shown in more places on the
        # card" site-side change would produce.
        html = _card_html("222", price_bgn=100000, price_eur=51000, extra_bgn_mentions=3)
        stats = Counter()
        link_count, seen = self._run(html, skip_stats=stats)
        self.assertEqual(link_count, 1)
        self.assertNotIn("222", seen)
        self.assertEqual(stats["no_container"], 1)
        self.assertEqual(stats["added"], 0)

    def test_no_title_match_counted(self):
        # DESC_RE requires "for sale <text> <digits> €" - breaking that
        # shape (no "for sale" prefix) reproduces a real card whose title
        # can't be extracted, without touching the price/sqm fields.
        html = (
            '<div class="card">'
            '<a href="/en/obiava/prodava-apartment-sofia/333/">'
            '<img src="/img/333.jpg"/></a>'
            '<div class="body">Two-bedroom apartment, Center 75 м2 '
            '75000 € 146770 BGN</div>'
            '</div>'
        )
        stats = Counter()
        link_count, seen = self._run(html, skip_stats=stats)
        self.assertEqual(link_count, 1)
        self.assertNotIn("333", seen)
        self.assertEqual(stats["no_title_match"], 1)
        self.assertEqual(stats["added"], 0)

    def test_price_under_floor_counted(self):
        html = _card_html("444", price_bgn=500, price_eur=250)
        stats = Counter()
        link_count, seen = self._run(html, skip_stats=stats)
        self.assertEqual(link_count, 1)
        self.assertNotIn("444", seen)
        self.assertEqual(stats["price_under_1000"], 1)
        self.assertEqual(stats["added"], 0)

    def test_duplicate_id_counted(self):
        html = _card_html("555", price_bgn=146770, price_eur=75000)
        stats = Counter()
        seen = {"555": {"id": "555"}}
        link_count, _ = self._run(html, seen=seen, skip_stats=stats)
        self.assertEqual(link_count, 1)
        self.assertEqual(stats["duplicate"], 1)
        self.assertEqual(stats["added"], 0)

    def test_multi_card_page_yield_breakdown_matches_real_outcomes(self):
        # A realistic mixed page: 2 good cards, 1 over-price-mentions,
        # 1 no-title, 1 under the price floor - confirms the per-page
        # counters used by fetch_listings()'s own yield summary line
        # match reality exactly, card for card.
        html = "".join([
            _card_html("601", price_bgn=100000, price_eur=51000),
            _card_html("602", price_bgn=200000, price_eur=102000),
            _card_html("603", price_bgn=100000, price_eur=51000, extra_bgn_mentions=3),
            (
                '<div class="card"><a href="/en/obiava/prodava-apartment-sofia/604/">'
                '<img src="/img/604.jpg"/></a><div class="body">Studio, Center 40 м2 '
                '30000 € 58500 BGN</div></div>'
            ),
            _card_html("605", price_bgn=999, price_eur=500),
        ])
        stats = Counter()
        link_count, seen = self._run(html, skip_stats=stats)
        self.assertEqual(link_count, 5)
        self.assertEqual(set(seen.keys()), {"601", "602"})
        self.assertEqual(stats["added"], 2)
        self.assertEqual(stats["no_container"], 1)
        self.assertEqual(stats["no_title_match"], 1)
        self.assertEqual(stats["price_under_1000"], 1)

    def test_skip_stats_is_purely_additive_extraction_unchanged(self):
        # Same page, run once with skip_stats and once without - the set
        # of added listings and their fields must be byte-for-byte
        # identical either way (this instrumentation must never change
        # what gets scraped, only report on it).
        html = "".join([
            _card_html("701", price_bgn=100000, price_eur=51000),
            _card_html("702", price_bgn=999, price_eur=500),
            _card_html("703", price_bgn=200000, price_eur=102000, extra_bgn_mentions=3),
        ])
        _, seen_with_stats = self._run(html, skip_stats=Counter())
        _, seen_without_stats = self._run(html, skip_stats=None)
        self.assertEqual(seen_with_stats, seen_without_stats)
        self.assertEqual(set(seen_without_stats.keys()), {"701"})

    def test_skip_stats_none_does_not_crash(self):
        # fetch_listings_page() must still work with no skip_stats passed
        # at all (e.g. any external caller that doesn't know about this
        # parameter) - default is None, every increment is guarded.
        html = _card_html("801", price_bgn=146770, price_eur=75000)
        link_count, seen = self._run(html, skip_stats=None)
        self.assertEqual(link_count, 1)
        self.assertIn("801", seen)


if __name__ == "__main__":
    unittest.main(verbosity=2)
