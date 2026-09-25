"""
Regression tests for scraper_bcpea.py's _log_photo_miss() - the zero-cost
diagnostic tripwire added 2026-09-25 alongside extract_photos_bcpea()'s own
correction (see its docstring in scraper_bcpea.py and
tests/test_bcpea_detail_extraction.py's module docstring for the full
story: a production audit found "photos" at a flat 0% (0/2,246), and this
diagnostic exists to capture real <img> markup evidence - which class
attributes exist inside vs. outside `.item__expanded` - the next time this
scraper actually runs against production, since this sandbox has no live
network access to find out directly).

Mirrors scraper_bcpea.py's own _seen_unrecognized_labels cap/dedupe pattern
(and the analogous imoti.bg tripwire in
tests/test_imoti_bg_ld_json_diagnostic_logging.py): logged for at most a
handful of listings per run, not spammed across the whole nationwide
backlog for what's very possibly the same root cause every time.

Run with: python3 -m unittest tests.test_scraper_bcpea_photo_miss_tripwire -v
(no pytest / other test framework is installed in this repo.)
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup

import scraper_bcpea


def _soup_and_expanded(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup, soup.find(class_="item__expanded")


HEAD_OUTSIDE_EXPANDED_HTML = """
<div class="item">
  <div class="head"><img src="/upload/1/1/real.jpg"></div>
  <div class="item__expanded">
    <div class="label__group"><span class="label">Район</span><span class="info">Център</span></div>
  </div>
</div>
"""

NO_IMAGES_AT_ALL_HTML = '<div class="item__expanded"><p>No images here.</p></div>'


class LogPhotoMissTest(unittest.TestCase):
    def setUp(self):
        # Reset the module-level counter so each test starts from a clean
        # cap - same reset _log_ld_json_miss's own tests need for the
        # analogous imoti.bg tripwire.
        scraper_bcpea._photo_miss_logged = 0

    def test_logs_diagnostic_with_url(self):
        soup, expanded = _soup_and_expanded(HEAD_OUTSIDE_EXPANDED_HTML)
        buf = io.StringIO()
        with redirect_stdout(buf):
            scraper_bcpea._log_photo_miss("https://sales.bcpea.org/properties/1", soup, expanded)
        output = buf.getvalue()
        self.assertIn("extract_photos_bcpea() empty", output)
        self.assertIn("https://sales.bcpea.org/properties/1", output)
        self.assertIn("outside_expanded", output)
        self.assertIn("'inside_expanded': []", output)

    def test_logs_when_no_images_anywhere(self):
        soup, expanded = _soup_and_expanded(NO_IMAGES_AT_ALL_HTML)
        buf = io.StringIO()
        with redirect_stdout(buf):
            scraper_bcpea._log_photo_miss("https://sales.bcpea.org/properties/2", soup, expanded)
        self.assertIn("'inside_expanded': []", buf.getvalue())
        self.assertIn("'outside_expanded': []", buf.getvalue())

    def test_stops_logging_past_the_cap(self):
        soup, expanded = _soup_and_expanded(NO_IMAGES_AT_ALL_HTML)
        buf = io.StringIO()
        with redirect_stdout(buf):
            for i in range(scraper_bcpea._PHOTO_MISS_LOG_CAP + 3):
                scraper_bcpea._log_photo_miss(f"https://sales.bcpea.org/properties/{i}", soup, expanded)
        output = buf.getvalue()
        self.assertEqual(output.count("DEBUG: extract_photos_bcpea() empty"),
                          scraper_bcpea._PHOTO_MISS_LOG_CAP)


if __name__ == "__main__":
    unittest.main(verbosity=2)
