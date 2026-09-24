"""
Regression/proof tests for the olx.bg detail-page spec-field extension
added 2026-09-24 (docs/backlog.md - "extend fetch_listing_detail() to
capture spec fields/coordinates/agency contact, reusing the same ld+json
blob extract_description_ldjson()/extract_photos_ldjson() already read"):
geo_utils.extract_sqm_ldjson() (new), and scraper_olx.fetch_listing_detail()
wiring it in as a gap-filler.

This sandbox's network egress to olx.bg is blocked (confirmed again live via
WebFetch while doing this work - same as every other olx.bg detail-page
extractor in this codebase), and no raw olx.bg detail-page HTML is saved
anywhere in this repo to test against instead. These fixtures are therefore
synthetic <script type="application/ld+json"> blocks built from the
standard Schema.org "floorSize" (QuantitativeValue) shape - the one field
this extension actually adds, see geo_utils.extract_sqm_ldjson()'s own
comment for why every other requested field (property_type_raw,
construction_type, built_year, completion_status, floor_number,
floor_qualifier, features, has_elevator, furnished, has_central_heating,
agency_name, agency_website, lat/lng) was investigated and deliberately NOT
added.

Run with: python3 -m unittest tests.test_olx_detail_extraction -v
(no pytest / other test framework is installed in this repo.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geo_utils import extract_sqm_ldjson
import scraper_olx


# Realistic shape: same single ld+json blob already proven to carry
# "description" and "image" (see extract_description_ldjson()/
# extract_photos_ldjson()'s own docstrings), extended with a standard
# Schema.org "floorSize" QuantitativeValue - exactly the shape this
# extension is designed to read.
LDJSON_WITH_FLOOR_SIZE = """
<html><body>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Product",
 "description": "Просторен тристаен апартамент в отлично състояние.",
 "image": ["https://img.olx.bg/1.jpg", "https://img.olx.bg/2.jpg"],
 "floorSize": {"@type": "QuantitativeValue", "value": "85.5", "unitCode": "MTK"}}
</script>
</body></html>
"""

LDJSON_NO_FLOOR_SIZE = """
<html><body>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Product",
 "description": "Двустаен апартамент.",
 "image": ["https://img.olx.bg/1.jpg"]}
</script>
</body></html>
"""

# A page whose ld+json is a top-level LIST of blobs (same shape
# extract_description_ldjson()/extract_photos_ldjson() already handle via
# their own "data if isinstance(data, list) else [data]" branch) - the real
# spec value sits in the second blob, not the first.
LDJSON_LIST_SHAPE = """
<html><body>
<script type="application/ld+json">
[{"@context": "https://schema.org", "@type": "Organization", "name": "OLX.bg"},
 {"@context": "https://schema.org", "@type": "Product",
  "description": "Тристаен апартамент.",
  "floorSize": {"@type": "QuantitativeValue", "value": 102}}]
</script>
</body></html>
"""

# floorSize present but malformed - not a dict, or a dict with a
# non-numeric value - must degrade to None, never raise or return garbage.
LDJSON_FLOOR_SIZE_NOT_A_DICT = """
<html><body>
<script type="application/ld+json">
{"description": "x", "floorSize": "85 кв.м"}
</script>
</body></html>
"""

LDJSON_FLOOR_SIZE_NON_NUMERIC_VALUE = """
<html><body>
<script type="application/ld+json">
{"description": "x", "floorSize": {"value": "не е известно"}}
</script>
</body></html>
"""

# One broken ld+json block (invalid JSON) followed by a real, valid one -
# proves a single malformed <script> tag doesn't abort the whole scan, same
# defensive shape extract_description_ldjson()/extract_photos_ldjson()
# already have (their own "except (json.JSONDecodeError, TypeError):
# continue").
LDJSON_ONE_BROKEN_ONE_VALID = """
<html><body>
<script type="application/ld+json">{not valid json,,,</script>
<script type="application/ld+json">
{"description": "y", "floorSize": {"value": 60}}
</script>
</body></html>
"""

NO_LDJSON_AT_ALL = "<html><body><h1>404</h1></body></html>"


class ExtractSqmLdjsonTest(unittest.TestCase):
    def test_extracts_and_rounds_floor_size_value(self):
        self.assertEqual(extract_sqm_ldjson(LDJSON_WITH_FLOOR_SIZE), 86)  # round(85.5)

    def test_returns_none_when_floor_size_key_absent(self):
        self.assertIsNone(extract_sqm_ldjson(LDJSON_NO_FLOOR_SIZE))

    def test_finds_floor_size_in_second_blob_of_a_list_shaped_ldjson(self):
        self.assertEqual(extract_sqm_ldjson(LDJSON_LIST_SHAPE), 102)

    def test_returns_none_when_floor_size_is_not_a_dict(self):
        self.assertIsNone(extract_sqm_ldjson(LDJSON_FLOOR_SIZE_NOT_A_DICT))

    def test_returns_none_when_floor_size_value_is_non_numeric(self):
        self.assertIsNone(extract_sqm_ldjson(LDJSON_FLOOR_SIZE_NON_NUMERIC_VALUE))

    def test_skips_one_broken_ldjson_block_and_still_finds_a_later_valid_one(self):
        self.assertEqual(extract_sqm_ldjson(LDJSON_ONE_BROKEN_ONE_VALID), 60)

    def test_returns_none_when_no_ldjson_present(self):
        self.assertIsNone(extract_sqm_ldjson(NO_LDJSON_AT_ALL))

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_sqm_ldjson("<<<not even html"))
        self.assertIsNone(extract_sqm_ldjson(""))


class _FakeDetailPage:
    """Stands in for a Playwright Page inside fetch_listing_detail() -
    goto_with_retries() only ever calls .goto()/.wait_for_timeout()/
    .content() on it, same minimal surface test_olx_grid_crawl_timeout_fix.
    py's _FakePage already stubs for the grid-crawl path."""

    def __init__(self, html):
        self._html = html

    def goto(self, url, wait_until=None, timeout=None):
        pass

    def wait_for_timeout(self, ms):
        pass

    def content(self):
        return self._html


class FetchListingDetailSqmGapFillerTest(unittest.TestCase):
    def test_fills_sqm_from_ldjson_when_grid_crawl_found_none(self):
        listing = {"url": "https://www.olx.bg/d/ad/x-ID1.html", "sqm": None}
        ok = scraper_olx.fetch_listing_detail(_FakeDetailPage(LDJSON_WITH_FLOOR_SIZE), listing)
        self.assertTrue(ok)
        self.assertEqual(listing["sqm"], 86)
        # description/photos extraction (already-working, unrelated to this
        # change) must still both fire off the same fetch.
        self.assertIn("Просторен тристаен апартамент", listing["description"])
        self.assertEqual(listing["photos"], ["https://img.olx.bg/1.jpg", "https://img.olx.bg/2.jpg"])

    def test_never_overwrites_a_real_grid_crawl_sqm(self):
        listing = {"url": "https://www.olx.bg/d/ad/x-ID1.html", "sqm": 70}
        ok = scraper_olx.fetch_listing_detail(_FakeDetailPage(LDJSON_WITH_FLOOR_SIZE), listing)
        self.assertTrue(ok)
        # ld+json says 86 (from floorSize 85.5) but the grid already found a
        # real 70 - the detail pass must never clobber it.
        self.assertEqual(listing["sqm"], 70)

    def test_leaves_sqm_unset_when_ldjson_has_no_floor_size_either(self):
        listing = {"url": "https://www.olx.bg/d/ad/x-ID1.html", "sqm": None}
        ok = scraper_olx.fetch_listing_detail(_FakeDetailPage(LDJSON_NO_FLOOR_SIZE), listing)
        self.assertTrue(ok)
        self.assertIsNone(listing.get("sqm"))

    def test_detail_only_fields_tuple_includes_sqm(self):
        # update_history()'s merge-not-replace protection (see
        # scraper_olx.py's own _DETAIL_ONLY_FIELDS comment) only applies to
        # fields listed here - a future grid-only re-touch must not be able
        # to silently wipe a detail-filled sqm.
        self.assertIn("sqm", scraper_olx._DETAIL_ONLY_FIELDS)
        self.assertIn("description", scraper_olx._DETAIL_ONLY_FIELDS)
        self.assertIn("photos", scraper_olx._DETAIL_ONLY_FIELDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
