"""
Regression/proof tests for the bazar.bg detail-page extraction functions
added 2026-09-24: geo_utils.extract_specs_bazar() and geo_utils.
extract_contact_bazar() - the same real-content gap already closed for
alo.bg (see tests/test_alo_detail_extraction.py), now closed for bazar.bg.

This sandbox's network egress to bazar.bg is blocked (same restriction
already documented for alo.bg - see extract_coords_bazar()'s neighboring
comment in geo_utils.py), so none of this could be tested against a live
page. Instead, these fixtures are synthetic HTML modeled closely on real
user-supplied screenshots of a live bazar.bg detail page (bazar_55691101,
https://bazar.bg/obiava-55691101/prodava-2-staen-gr-sofiia-lyulin-1) -
same label/value pairs, same section text, a plausible (not confirmed) tag
shape. Since the real DOM structure is unverified, every extractor is
deliberately built to key off fixed Bulgarian LABEL TEXT rather than any
specific CSS class/tag name (see each function's own comment in
geo_utils.py) - these tests exercise that text-based strategy against more
than one plausible markup shape for the same content, and prove a
non-matching page degrades to None/partial results instead of crashing or
extracting garbage.

geo_utils.extract_description_ldjson()/extract_photos_ldjson()/
extract_coords_bazar() are NOT re-tested here - they're pre-existing,
already live-verified (see their own module comments: "confirmed live via
probe_descriptions.py"/"probe_photos.py") and already wired into
backfill_detail_bazar.py; this file covers only the two functions that are
new as of 2026-09-24.

Run with: python3 -m unittest tests.test_bazar_detail_extraction -v
(no pytest / other test framework is installed in this repo.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geo_utils import extract_contact_bazar, extract_specs_bazar


# A realistic full detail page, modeled on the real screenshots: a spec
# table (as <tr>/<td> pairs) with the exact label/value pairs from the
# ground-truth listing, a free-text description directly below it (not
# exercised by these tests - that's extract_description_ldjson()'s job,
# already covered elsewhere), and an agency contact box with a plain-text
# name, an "Още оферти на <url>" link, and a masked phone number behind a
# "покажи" reveal button.
REALISTIC_DETAIL_PAGE_TABLE_SHAPE = """
<html><body>
<h1>Продава 2-СТАЕН, гр. София, Люлин 1</h1>
<table>
<tr><td>Тип сделка</td><td>Продава Апартамент в гр. София</td></tr>
<tr><td>Тип апартамент</td><td>2-стаен</td></tr>
<tr><td>Квадратура</td><td>50 кв. м.</td></tr>
<tr><td>Цена на кв.м.</td><td>2240 €/кв. м.</td></tr>
<tr><td>Вид строителство</td><td>ЕПК</td></tr>
<tr><td>Етаж</td><td>4</td></tr>
</table>
<p>ПРОДАВАМЕ МАЛОМЕРН 2 ст.ЕПК ,НА 4 ТИ ЕТАЖ,С 2 РАБОТЕЩИ АСАНСЬОРА.
Апартаментът се състои от дневна с кухненски бокс, спалня, баня с тоалетна
и балкон.</p>

<div class="contact-box">
  <strong>АГЕНЦИЯ СНТ - ИНТЕРНЕШЪНЪЛ ООД</strong>
  <p>Още оферти на <a href="https://sntbg.imot.bg">https://sntbg.imot.bg</a></p>
  <div class="phone-mask">08XX XXX XXX <button>(покажи)</button></div>
</div>
</body></html>
"""

# Same content, deliberately different DOM shape (divs instead of a table,
# a bare URL rendered as visible text instead of a real <a href>) - proves
# the extractors key off label TEXT, not a specific tag/class, since real
# bazar.bg markup could plausibly be either shape (or something else) and
# was never directly observed.
REALISTIC_DETAIL_PAGE_DIV_SHAPE = """
<html><body>
<div class="spec-row"><span class="label">Тип апартамент</span><span class="value">Тристаен</span></div>
<div class="spec-row"><span class="label">Квадратура</span><span class="value">85.5 кв. м.</span></div>
<div class="spec-row"><span class="label">Вид строителство</span><span class="value">Тухла</span></div>
<div class="spec-row"><span class="label">Етаж</span><span class="value">7</span></div>

<div class="contact-box">
  <div class="poster-name">Иван Петров Имоти</div>
  <div>Още оферти на sivanov-imoti.bg</div>
  <div class="phone-mask">089 XXX XXXX (покажи)</div>
</div>
</body></html>
"""

# A page with none of the known section labels at all.
UNRELATED_PAGE = """
<html><body>
<h1>404 - Обявата е премахната</h1>
<p>Съжаляваме, но тази обява вече не е налична.</p>
</body></html>
"""


class ExtractSpecsBazarTest(unittest.TestCase):
    def test_extracts_full_specs_table_shape(self):
        specs = extract_specs_bazar(REALISTIC_DETAIL_PAGE_TABLE_SHAPE)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["property_type_raw"], "2-стаен")
        self.assertEqual(specs["sqm"], 50)
        self.assertEqual(specs["construction_type"], "ЕПК")
        self.assertEqual(specs["floor_number"], 4)
        # "Тип сделка" and "Цена на кв.м." are deliberately never stored -
        # see extract_specs_bazar()'s own comment.
        self.assertNotIn("transaction_type", specs)
        self.assertNotIn("price_per_sqm", specs)

    def test_extracts_partial_specs_div_shape_and_decimal_sqm(self):
        specs = extract_specs_bazar(REALISTIC_DETAIL_PAGE_DIV_SHAPE)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["property_type_raw"], "Тристаен")
        self.assertEqual(specs["sqm"], 86)  # round(85.5)
        self.assertEqual(specs["construction_type"], "Тухла")
        self.assertEqual(specs["floor_number"], 7)

    def test_returns_none_when_no_known_label_present(self):
        self.assertIsNone(extract_specs_bazar(UNRELATED_PAGE))

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_specs_bazar("<<<not even html"))
        self.assertIsNone(extract_specs_bazar(""))

    def test_floor_number_stays_correct_when_no_row_follows_it(self):
        # "Етаж" is the LAST known row on a real bazar.bg listing, with no
        # confirmed heading/stop-text right after it - the free-text
        # description paragraph sits directly below instead. Proves the
        # digit-only regex extraction stays correct (picks the real "4",
        # not some later number from the description) even when the value
        # collector's line cap pulls in a bit of that following text.
        html = """
        <table><tr><td>Етаж</td><td>4</td></tr></table>
        <p>Продавам апартамент на 12-и етаж в панелна сграда с 2 асансьора.</p>
        """
        specs = extract_specs_bazar(html)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["floor_number"], 4)

    def test_sqm_row_does_not_bleed_into_price_per_sqm_row(self):
        # "Цена на кв.м." immediately follows "Квадратура" on a real
        # listing - must correctly stop sqm's value collection there
        # rather than swallowing the price-per-sqm row's own value too.
        html = """
        <table>
        <tr><td>Квадратура</td><td>50 кв. м.</td></tr>
        <tr><td>Цена на кв.м.</td><td>2240 €/кв. м.</td></tr>
        </table>
        """
        specs = extract_specs_bazar(html)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["sqm"], 50)


class ExtractContactBazarTest(unittest.TestCase):
    def test_extracts_name_and_website_table_shape(self):
        contact = extract_contact_bazar(REALISTIC_DETAIL_PAGE_TABLE_SHAPE)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "АГЕНЦИЯ СНТ - ИНТЕРНЕШЪНЪЛ ООД")
        self.assertEqual(contact["agency_website"], "https://sntbg.imot.bg")
        # The masked phone number must never be extracted as a real value.
        self.assertNotIn("phone", contact)
        self.assertNotIn("08XX XXX XXX", str(contact.values()))

    def test_extracts_name_and_bare_url_website_div_shape(self):
        contact = extract_contact_bazar(REALISTIC_DETAIL_PAGE_DIV_SHAPE)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "Иван Петров Имоти")
        # A bare domain rendered as plain text (no real <a href>) must
        # still be picked up via the text-fallback path.
        self.assertEqual(contact["agency_website"], "https://sivanov-imoti.bg")
        self.assertNotIn("phone", contact)

    def test_returns_none_when_offers_phrase_absent(self):
        self.assertIsNone(extract_contact_bazar(UNRELATED_PAGE))

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_contact_bazar("<<<not even html"))
        self.assertIsNone(extract_contact_bazar(""))

    def test_never_extracts_masked_phone_as_agency_name(self):
        # A page where the phone-mask line would be the first line after
        # the offers phrase if the "покажи" filter didn't work - proves it
        # never becomes the agency_name by mistake.
        html = """
        <div>
          <p>Още оферти на https://example-agency.bg</p>
          <div>0888 123 456 (покажи)</div>
          <div>РЕАЛНА АГЕНЦИЯ ООД</div>
        </div>
        """
        contact = extract_contact_bazar(html)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "РЕАЛНА АГЕНЦИЯ ООД")
        self.assertEqual(contact["agency_website"], "https://example-agency.bg")


if __name__ == "__main__":
    unittest.main(verbosity=2)
