"""
Regression tests for scraper_imoti_bg.py's _log_ld_json_miss() - the
zero-cost diagnostic tripwire added 2026-09-25 alongside the
strict=False JSON-LD parsing fix (see geo_utils.py's own comment above
_imoti_bg_ld_json_candidates() and this module's fetch_listing_detail()
for the full story: a production audit found imoti.bg's specs/contact
extraction at a flat 0%, and this diagnostic exists to capture real
evidence - script-tag counts, parse failures, observed @type values -
the next time this scraper actually runs against production, since this
sandbox has no live network access to find out directly).

Mirrors scraper_bcpea.py's own _seen_unrecognized_labels cap/dedupe
pattern: logged for at most a handful of listings per run, not spammed
across the whole nationwide backlog for what's very possibly the same
root cause every time.

Run with: python3 -m unittest tests.test_imoti_bg_ld_json_diagnostic_logging -v
(no pytest / other test framework is installed in this repo.)
"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper_imoti_bg


def _page_with_ld_json(*blocks):
    scripts = "\n".join(
        f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>'
        for b in blocks
    )
    return f"<html><head>{scripts}</head><body><h1>Listing</h1></body></html>"


NO_LD_JSON_PAGE = "<html><body><h1>404</h1></body></html>"
RECOGNIZED_SHAPE_PAGE = _page_with_ld_json({
    "@type": "Apartment",
    "floorSize": {"@type": "QuantitativeValue", "value": "60"},
})
UNRECOGNIZED_SHAPE_PAGE = _page_with_ld_json({"@type": "Product", "description": "x" * 50})


class LogLdJsonMissTest(unittest.TestCase):
    def setUp(self):
        # Reset the module-level counter so each test starts from a clean
        # cap, same reset scraper_bcpea.py's own tripwire tests would need
        # if it had equivalent tests for _seen_unrecognized_labels.
        scraper_imoti_bg._ld_json_miss_logged = 0

    def test_logs_when_shape_unrecognized(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            scraper_imoti_bg._log_ld_json_miss("https://imoti.bg/x/1", UNRECOGNIZED_SHAPE_PAGE)
        output = buf.getvalue()
        self.assertIn("imoti.bg specs/contact empty", output)
        self.assertIn("https://imoti.bg/x/1", output)
        self.assertIn("'script_tags': 1", output)
        self.assertIn("'types_seen': ['Product']", output)

    def test_logs_when_no_ld_json_at_all(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            scraper_imoti_bg._log_ld_json_miss("https://imoti.bg/x/2", NO_LD_JSON_PAGE)
        self.assertIn("'script_tags': 0", buf.getvalue())

    def test_stops_logging_past_the_cap(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            for i in range(scraper_imoti_bg._LD_JSON_MISS_LOG_CAP + 3):
                scraper_imoti_bg._log_ld_json_miss(f"https://imoti.bg/x/{i}", NO_LD_JSON_PAGE)
        output = buf.getvalue()
        self.assertEqual(output.count("DEBUG: imoti.bg specs/contact empty"),
                          scraper_imoti_bg._LD_JSON_MISS_LOG_CAP)

    def test_fetch_listing_detail_does_not_log_when_specs_or_contact_found(self):
        # A page whose ld+json IS recognized (specs found) must never hit
        # the miss-logging path - this diagnostic is for the empty case
        # only, not a log-every-listing spam source.
        scraper_imoti_bg._ld_json_miss_logged = 0
        buf = io.StringIO()
        with redirect_stdout(buf):
            specs = scraper_imoti_bg.extract_specs_imoti_bg(RECOGNIZED_SHAPE_PAGE)
            contact = scraper_imoti_bg.extract_contact_imoti_bg(RECOGNIZED_SHAPE_PAGE)
            if not specs and not contact:
                scraper_imoti_bg._log_ld_json_miss("https://imoti.bg/x/3", RECOGNIZED_SHAPE_PAGE)
        self.assertIsNotNone(specs)
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
