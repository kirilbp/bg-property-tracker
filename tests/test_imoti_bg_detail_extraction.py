"""
Regression/proof tests for the imoti.bg detail-page spec/contact extraction
functions added 2026-09-24: geo_utils.extract_specs_imoti_bg() and
geo_utils.extract_contact_imoti_bg().

CORRECTED 2026-09-25: this docstring previously claimed imoti.bg's
detail-page description extraction (scraper_imoti_bg.fetch_listing_detail())
"is ALREADY proven, live-confirmed working code: it successfully parses a
real <script type="application/ld+json"> block off imoti.bg's own detail
pages today." A production audit found that claim doesn't actually hold:
fetch_listing_detail() reads description from a <meta name="description">
tag FIRST and only falls back to ld+json when that's missing, so its 94%+
hit rate is explained by the meta tag alone and proves nothing about
whether ld+json parsing itself ever succeeds on a real page. Root cause
and full reasoning in geo_utils.py's own comment above
_imoti_bg_ld_json_candidates(). What's genuinely unverified here remains
the same as before (whether real imoti.bg ld+json, if it exists at all,
carries floorSize/amenityFeature/seller-provider-author/Accommodation
subtype @type) - this sandbox's network egress to imoti.bg is blocked
(confirmed again 2026-09-25), so these fixtures stay synthetic ld+json
blocks built from real, documented schema.org vocabulary (not a guess
about imoti.bg's specific CSS/tag names), modeled on the two shapes a
RealEstateListing's structured data commonly takes: the Accommodation
nested under "about", or a single flat object carrying everything itself.
A third set of fixtures added 2026-09-25 covers a second, independently
plausible cause of the same 0% symptom: a common real-world JSON-LD quirk
(a raw, unescaped control character inside a string value) that trips
strict json.loads() regardless of the page's actual schema - a generic
parser-hardening concern, not a site-specific guess.

Run with: python3 -m unittest tests.test_imoti_bg_detail_extraction -v
(no pytest / other test framework is installed in this repo.)
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geo_utils import (
    extract_contact_imoti_bg,
    extract_specs_imoti_bg,
    imoti_bg_ld_json_diagnostic,
)


def _page_with_ld_json(*blocks):
    scripts = "\n".join(
        f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>'
        for b in blocks
    )
    return f"<html><head>{scripts}</head><body><h1>Listing</h1></body></html>"


# Shape 1: RealEstateListing wrapping an Accommodation under "about" -
# the canonical schema.org nesting for "this listing is FOR this
# accommodation, whose own facts (size, amenities, type) live on it, not
# on the listing wrapper itself".
NESTED_ABOUT_SHAPE = _page_with_ld_json({
    "@context": "https://schema.org",
    "@type": "RealEstateListing",
    "description": "Просторен тристаен апартамент в отлично състояние.",
    "offers": {
        "@type": "Offer",
        "price": "95000",
        "priceCurrency": "EUR",
        "seller": {"@type": "Organization", "name": "Империал Имоти", "url": "https://imperial-imoti.bg"},
    },
    "about": {
        "@type": "Apartment",
        "floorSize": {"@type": "QuantitativeValue", "value": "75.5", "unitCode": "MTK"},
        "amenityFeature": [
            {"@type": "LocationFeatureSpecification", "name": "Асансьор", "value": True},
            {"@type": "LocationFeatureSpecification", "name": "Обзаведен", "value": True},
            {"@type": "LocationFeatureSpecification", "name": "ТЕЦ", "value": True},
            {"@type": "LocationFeatureSpecification", "name": "Гараж", "value": False},
        ],
    },
})

# Shape 2: everything flat on one object, no "about" nesting, author
# instead of seller, plain numeric floorSize (no QuantitativeValue
# wrapper), "Необзаведен" (unfurnished) instead of furnished, and an
# internal imoti.bg link that must NOT be treated as the agency's website.
FLAT_SHAPE_UNFURNISHED = _page_with_ld_json({
    "@context": "https://schema.org",
    "@type": "House",
    "description": "Продавам къща в отлично състояние, готова за нанасяне.",
    "floorSize": 120,
    "amenityFeature": [
        {"name": "Необзаведен", "value": "true"},
    ],
    "author": {"@type": "Person", "name": "Иван Петров", "url": "https://imoti.bg/profile/ivan-petrov"},
})

# A page with real ld+json (proves the description path still works) but
# none of the extra fields these two functions look for - must degrade to
# None, not fabricate anything.
LD_JSON_WITH_NO_EXTRA_FIELDS = _page_with_ld_json({
    "@context": "https://schema.org",
    "@type": "Product",
    "description": "Продавам парцел в добра локация, готов за строеж.",
})

# offers.seller present alongside a different top-level "author" - proves
# offers.seller wins (the more specific "who's actually selling this
# offer" signal), not whichever happens to be scanned first.
OFFERS_SELLER_PRIORITY_SHAPE = _page_with_ld_json({
    "@type": "RealEstateListing",
    "offers": {"@type": "Offer", "seller": {"@type": "Organization", "name": "Real Agency", "url": "https://real-agency.bg"}},
    "author": {"@type": "Organization", "name": "Wrong Name", "url": "https://wrong.bg"},
})

# No ld+json block at all - the genuinely-no-structured-data case (should
# never happen on a real imoti.bg detail page per fetch_listing_detail()'s
# own docstring, but must still degrade cleanly rather than crash).
NO_LD_JSON_PAGE = "<html><body><h1>404 - обявата е изтрита</h1></body></html>"


class ExtractSpecsImotiBgTest(unittest.TestCase):
    def test_extracts_full_specs_nested_about_shape(self):
        specs = extract_specs_imoti_bg(NESTED_ABOUT_SHAPE)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["sqm"], 76)  # round(75.5)
        self.assertEqual(specs["property_type_raw"], "Apartment")
        self.assertEqual(specs["features"], ["Асансьор", "Обзаведен", "ТЕЦ"])
        # The unchecked "Гараж" (value: False) must never appear.
        self.assertNotIn("Гараж", specs["features"])
        self.assertTrue(specs["has_elevator"])
        self.assertTrue(specs["furnished"])
        self.assertTrue(specs["has_central_heating"])
        # Fields with no real schema.org evidence must never be fabricated.
        self.assertNotIn("construction_type", specs)
        self.assertNotIn("built_year", specs)
        self.assertNotIn("completion_status", specs)
        self.assertNotIn("floor_number", specs)
        self.assertNotIn("floor_qualifier", specs)

    def test_extracts_partial_specs_flat_shape_and_unfurnished(self):
        specs = extract_specs_imoti_bg(FLAT_SHAPE_UNFURNISHED)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["sqm"], 120)
        self.assertEqual(specs["property_type_raw"], "House")
        self.assertEqual(specs["features"], ["Необзаведен"])
        self.assertFalse(specs["furnished"])
        self.assertNotIn("has_elevator", specs)
        self.assertNotIn("has_central_heating", specs)

    def test_returns_none_when_ld_json_has_no_extra_fields(self):
        self.assertIsNone(extract_specs_imoti_bg(LD_JSON_WITH_NO_EXTRA_FIELDS))

    def test_returns_none_when_no_ld_json_at_all(self):
        self.assertIsNone(extract_specs_imoti_bg(NO_LD_JSON_PAGE))

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_specs_imoti_bg("<<<not even html"))
        self.assertIsNone(extract_specs_imoti_bg(""))

    def test_generic_type_is_not_treated_as_property_type(self):
        # "Product"/"RealEstateListing"/"Offer" are not Accommodation
        # subtypes - must never be stored as property_type_raw.
        specs = extract_specs_imoti_bg(LD_JSON_WITH_NO_EXTRA_FIELDS)
        self.assertIsNone(specs)


class ExtractContactImotiBgTest(unittest.TestCase):
    def test_extracts_name_and_website_nested_about_shape(self):
        contact = extract_contact_imoti_bg(NESTED_ABOUT_SHAPE)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "Империал Имоти")
        self.assertEqual(contact["agency_website"], "https://imperial-imoti.bg")

    def test_internal_imoti_bg_link_is_never_used_as_agency_website(self):
        contact = extract_contact_imoti_bg(FLAT_SHAPE_UNFURNISHED)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "Иван Петров")
        self.assertNotIn("agency_website", contact)

    def test_offers_seller_takes_priority_over_author(self):
        contact = extract_contact_imoti_bg(OFFERS_SELLER_PRIORITY_SHAPE)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "Real Agency")
        self.assertEqual(contact["agency_website"], "https://real-agency.bg")

    def test_returns_none_when_ld_json_has_no_org_fields(self):
        self.assertIsNone(extract_contact_imoti_bg(LD_JSON_WITH_NO_EXTRA_FIELDS))

    def test_returns_none_when_no_ld_json_at_all(self):
        self.assertIsNone(extract_contact_imoti_bg(NO_LD_JSON_PAGE))

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_contact_imoti_bg("<<<not even html"))
        self.assertIsNone(extract_contact_imoti_bg(""))

    def test_never_extracts_a_phone_number(self):
        # No phone field is ever read by this function at all - not even
        # if one happens to be present in the ld+json - mirroring
        # extract_contact_alo()'s own deliberate restraint.
        page = _page_with_ld_json({
            "@type": "RealEstateListing",
            "offers": {"@type": "Offer", "seller": {
                "@type": "Organization", "name": "Agency With Phone",
                "url": "https://agency-with-phone.bg", "telephone": "+359888123456",
            }},
        })
        contact = extract_contact_imoti_bg(page)
        self.assertIsNotNone(contact)
        self.assertNotIn("phone", contact)
        self.assertNotIn("telephone", contact)
        self.assertNotIn("+359888123456", str(contact.values()))


# A raw, unescaped control character (a literal newline) inside a JSON
# string value - deliberately NOT built via json.dumps (which would escape
# it correctly), since the whole point is to reproduce a block that fails
# strict json.loads() the way a real site's own template might generate one
# from an unescaped multi-line source string. This is a documented, common
# real-world JSON-LD quirk (see geo_utils.py's own comment above
# _imoti_bg_ld_json_candidates()), not a guess about imoti.bg's markup.
RAW_CONTROL_CHAR_LD_JSON_PAGE = (
    '<html><head><script type="application/ld+json">'
    '{"@context": "https://schema.org", "@type": "Apartment", '
    '"description": "Real listing text with a raw\nunescaped newline right '
    'in the middle of it.", '
    '"floorSize": {"@type": "QuantitativeValue", "value": "60"}, '
    '"amenityFeature": [{"name": "Асансьор", "value": true}], '
    '"offers": {"@type": "Offer", "seller": {"@type": "Organization", '
    '"name": "Raw Newline Agency", "url": "https://raw-newline-agency.bg"}}}'
    "</script></head><body></body></html>"
)

# Same control-character quirk, but genuinely unparseable even with the
# strict=False retry (truncated JSON) - must degrade to None/0 like any
# other unparseable block, never raise.
TRULY_BROKEN_LD_JSON_PAGE = (
    '<html><head><script type="application/ld+json">'
    '{"@type": "Apartment", "floorSize": {"value": "60"'
    "</script></head><body></body></html>"
)


class MalformedLdJsonControlCharacterTest(unittest.TestCase):
    """A real-world JSON-LD quirk (see this module's own docstring): a raw
    control character inside a string value trips Python's default strict
    json.loads() regardless of whether the surrounding schema is otherwise
    exactly the shape these extractors expect. Both extractors must still
    recover the real data via the strict=False retry, not silently return
    None just because one block had this quirk."""

    def test_specs_recovered_despite_raw_control_character(self):
        specs = extract_specs_imoti_bg(RAW_CONTROL_CHAR_LD_JSON_PAGE)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["sqm"], 60)
        self.assertEqual(specs["property_type_raw"], "Apartment")
        self.assertTrue(specs["has_elevator"])

    def test_contact_recovered_despite_raw_control_character(self):
        contact = extract_contact_imoti_bg(RAW_CONTROL_CHAR_LD_JSON_PAGE)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "Raw Newline Agency")
        self.assertEqual(contact["agency_website"], "https://raw-newline-agency.bg")

    def test_truly_unparseable_block_still_degrades_to_none(self):
        self.assertIsNone(extract_specs_imoti_bg(TRULY_BROKEN_LD_JSON_PAGE))
        self.assertIsNone(extract_contact_imoti_bg(TRULY_BROKEN_LD_JSON_PAGE))


class ImotiBgLdJsonDiagnosticTest(unittest.TestCase):
    """imoti_bg_ld_json_diagnostic() - the zero-cost visibility helper
    scraper_imoti_bg.py logs when specs/contact both come up empty, meant to
    tell "no ld+json on the page" apart from "ld+json is there but not the
    assumed shape" apart from "ld+json is there but fails to parse" the next
    time this scraper actually runs against production."""

    def test_no_script_tags_at_all(self):
        diag = imoti_bg_ld_json_diagnostic(NO_LD_JSON_PAGE)
        self.assertEqual(diag["script_tags"], 0)
        self.assertEqual(diag["parsed"], 0)
        self.assertEqual(diag["failed_to_parse"], 0)
        self.assertEqual(diag["types_seen"], [])

    def test_script_tags_present_but_unrecognized_shape(self):
        diag = imoti_bg_ld_json_diagnostic(LD_JSON_WITH_NO_EXTRA_FIELDS)
        self.assertEqual(diag["script_tags"], 1)
        self.assertEqual(diag["parsed"], 1)
        self.assertEqual(diag["failed_to_parse"], 0)
        self.assertEqual(diag["types_seen"], ["Product"])

    def test_recovered_via_strict_false_retry_still_counts_as_parsed(self):
        diag = imoti_bg_ld_json_diagnostic(RAW_CONTROL_CHAR_LD_JSON_PAGE)
        self.assertEqual(diag["script_tags"], 1)
        self.assertEqual(diag["parsed"], 1)
        self.assertEqual(diag["failed_to_parse"], 0)
        self.assertEqual(diag["types_seen"], ["Apartment"])

    def test_truly_broken_block_counted_as_failed_not_parsed(self):
        diag = imoti_bg_ld_json_diagnostic(TRULY_BROKEN_LD_JSON_PAGE)
        self.assertEqual(diag["script_tags"], 1)
        self.assertEqual(diag["parsed"], 0)
        self.assertEqual(diag["failed_to_parse"], 1)
        self.assertEqual(diag["types_seen"], [])

    def test_never_raises_on_garbage_html(self):
        diag = imoti_bg_ld_json_diagnostic("<<<not even html")
        self.assertEqual(diag["script_tags"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
