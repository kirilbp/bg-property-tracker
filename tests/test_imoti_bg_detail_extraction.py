"""
Regression/proof tests for the imoti.bg detail-page spec/contact extraction
functions added 2026-09-24: geo_utils.extract_specs_imoti_bg() and
geo_utils.extract_contact_imoti_bg().

Unlike alo.bg's own detail-page extractors (built from screenshots, since
alo.bg's real markup was never directly observed), imoti.bg's detail-page
description extraction (scraper_imoti_bg.fetch_listing_detail()) is
ALREADY proven, live-confirmed working code: it successfully parses a real
<script type="application/ld+json"> block off imoti.bg's own detail pages
today. What's genuinely unverified here is only whether that same ld+json
data ALSO carries the extra schema.org fields these two functions look for
(floorSize, amenityFeature, seller/provider/author, and Accommodation
subtype names as @type) - this sandbox's network egress to imoti.bg is
blocked (same caveat as alo.bg), so these fixtures are synthetic ld+json
blocks built from real, documented schema.org vocabulary (not a guess
about imoti.bg's specific CSS/tag names), modeled on the two shapes a
RealEstateListing's structured data commonly takes: the Accommodation
nested under "about", or a single flat object carrying everything itself.

Run with: python3 -m unittest tests.test_imoti_bg_detail_extraction -v
(no pytest / other test framework is installed in this repo.)
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geo_utils import extract_contact_imoti_bg, extract_specs_imoti_bg


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
