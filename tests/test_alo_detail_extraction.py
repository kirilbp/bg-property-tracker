"""
Regression/proof tests for the alo.bg detail-page extraction functions added
2026-09-24: geo_utils.extract_description_alo() (real implementation,
replacing the "always return None" stub from backlog #9), geo_utils.
extract_specs_alo() (new), and geo_utils.extract_contact_alo() (new).

This sandbox's network egress to alo.bg is blocked (see the NOTE above
extract_description_alo() in geo_utils.py), so none of this could be tested
against a live page. Instead, these fixtures are synthetic HTML modeled
closely on real user-supplied screenshots of a live alo.bg detail page
(listing alo_11319466, https://www.alo.bg/prodavam-atelie-v-zona-b-19-11319466)
- same values, same section labels, a plausible (not confirmed) tag shape.
Since the real DOM structure is unverified, every extractor is deliberately
built to key off fixed Bulgarian LABEL TEXT rather than any specific CSS
class/tag name (see each function's own comment in geo_utils.py) - these
tests exercise that text-based strategy against more than one plausible
markup shape for the same content, and prove a non-matching page degrades
to None/partial results instead of crashing or extracting garbage.

Run with: python3 -m unittest tests.test_alo_detail_extraction -v
(no pytest / other test framework is installed in this repo.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geo_utils import extract_contact_alo, extract_description_alo, extract_specs_alo


# A realistic full detail page, modeled on the real screenshots: a spec
# table (as <tr>/<td> pairs - one plausible shape among several this
# extractor is designed to survive, see the class' second fixture below for
# a different shape), a "Допълнителна информация" free-text section, and a
# "Контакт с подателя на обявата" box with an agency name, an alo.bg-hosted
# storefront link, a masked phone number with no real href, and a real
# external agency website link.
REALISTIC_DETAIL_PAGE_TABLE_SHAPE = """
<html><body>
<h1>Продавам ателие в зона Б-19</h1>
<table>
<tr><td>Местоположение</td><td>Зона Б19, град София, област София,
  <a href="/map">(Виж Зона Б19 на картата)</a></td></tr>
<tr><td>Вид на имота</td><td><strong>Ателие/Студио</strong></td></tr>
<tr><td>Квадратура</td><td><strong>57 кв.м</strong></td></tr>
<tr><td>Вид на строителство</td><td><strong>ЕПК/ПК</strong></td></tr>
<tr><td>Година на строителство</td><td><strong>1980 г.</strong>
  <span class="hint">(годината може да е ориентировъчна)</span></td></tr>
<tr><td>Степен на завършеност</td><td><strong>Готов (завършен)</strong></td></tr>
<tr><td>Номер на етажа</td><td><strong>12 етаж</strong></td></tr>
<tr><td>Етаж</td><td><strong>Непоследен</strong></td></tr>
<tr><td>Особености</td><td>
  <span class="feat">Асансьор</span>
  <span class="feat">Необзаведен</span>
  <span class="feat">ТЕЦ</span>
</td></tr>
</table>
<p>Актуализирана вчера. Валидна още 51 дни.</p>

<div class="obqva-block">
  <h3>Допълнителна информация</h3>
  <p>Продавам имот с площ от 57 кв.м, разположен на 12-и етаж в 24-етажна
  ЕПК сграда в столичния квартал Зона Б-19. Жилището е напълно освободено
  от мебели и лични вещи и е готово за цялостно обновяване според вкуса и
  нуждите на новия собственик.</p>
  <a href="#comment">Напиши първи коментар</a>
</div>

<div class="similar">
  <h3>Подобни обяви</h3>
  <a href="/s1">zona b19</a>
</div>

<div class="contact-box">
  <h3>Контакт с подателя на обявата</h3>
  <strong>ENDREVA HAUSES</strong>
  <a href="https://endrevahouses.alo.bg">endrevahouses.alo.bg</a>
  <button>Изпрати съобщение</button>
  <div class="phone-mask">08X XXX XXXX <button>Виж</button></div>
  <a href="https://endreva-houses.com">https://endreva-houses.com</a>
  <span>област Пловдив, Пловдив, беломорски</span>
</div>
</body></html>
"""

# Same content, deliberately different DOM shape (divs instead of a table,
# a heading tag instead of a bold-text-then-paragraph pairing for the
# description) - proves the extractors key off label TEXT, not a specific
# tag/class, since real alo.bg markup could plausibly be either shape (or
# something else) and was never directly observed.
REALISTIC_DETAIL_PAGE_DIV_SHAPE = """
<html><body>
<div class="spec-row"><span class="label">Вид на имота</span><span class="value">Тристаен апартамент</span></div>
<div class="spec-row"><span class="label">Квадратура</span><span class="value">85.5 кв.м</span></div>
<div class="spec-row"><span class="label">Степен на завършеност</span><span class="value">Груб стоеж</span></div>
<div class="spec-row"><span class="label">Номер на етажа</span><span class="value">3 етаж</span></div>
<div class="spec-row"><span class="label">Особености</span><span class="value">Асансьор</span></div>

<section>
  <span class="section-title">Допълнителна информация</span>
  <div class="body-text">Просторен тристаен апартамент в отлично състояние, с две тераси и паркомясто.</div>
</section>

<section>
  <span class="section-title">Контакт с подателя на обявата</span>
  <div class="poster-name">Иван Петров</div>
  <a href="mailto:someone@example.com">someone@example.com</a>
  <a href="https://www.some-agency.bg">www.some-agency.bg</a>
</section>
</body></html>
"""

# A page with none of the known section labels at all - a real listing on a
# genuinely different template, or a page this extraction never anticipated.
UNRELATED_PAGE = """
<html><body>
<h1>404 - Обявата е премахната</h1>
<p>Съжаляваме, но тази обява вече не е налична.</p>
</body></html>
"""

# Reproduces the ORIGINAL title-echo bug's shape: a `.obqva-block`-classed
# element exists on the page, but it holds a short title echo, not the real
# "Допълнителна информация" section (which is simply absent here) - proves
# the fix doesn't fall back to that class under any circumstance.
TITLE_ECHO_BLOCK_NO_REAL_DESCRIPTION = """
<html><body>
<div class="obqva-block">
  <strong>Двустаен апартамент в к-с Суит хоум 2</strong>
</div>
<p>Актуализирана днес.</p>
</body></html>
"""


class ExtractDescriptionAloTest(unittest.TestCase):
    def test_extracts_real_description_table_shape(self):
        desc = extract_description_alo(REALISTIC_DETAIL_PAGE_TABLE_SHAPE)
        self.assertIsNotNone(desc)
        self.assertIn("Продавам имот с площ от 57 кв.м", desc)
        self.assertIn("новия собственик", desc)
        # The heading label itself must not leak into the extracted text.
        self.assertNotIn("Допълнителна информация", desc)
        # Trailing boilerplate from the same card must be stripped.
        self.assertNotIn("Напиши", desc)
        self.assertNotIn("Подобни обяви", desc)

    def test_extracts_real_description_div_shape(self):
        desc = extract_description_alo(REALISTIC_DETAIL_PAGE_DIV_SHAPE)
        self.assertIsNotNone(desc)
        self.assertIn("Просторен тристаен апартамент", desc)
        self.assertNotIn("Допълнителна информация", desc)

    def test_returns_none_when_heading_absent(self):
        self.assertIsNone(extract_description_alo(UNRELATED_PAGE))

    def test_never_falls_back_to_obqva_block_title_echo(self):
        # The exact bug this fix replaces: an .obqva-block with a title
        # echo, no real "Допълнителна информация" heading anywhere. Must
        # return None, never the title-echo text.
        self.assertIsNone(extract_description_alo(TITLE_ECHO_BLOCK_NO_REAL_DESCRIPTION))

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_description_alo("<<<not even html"))
        self.assertIsNone(extract_description_alo(""))


class ExtractSpecsAloTest(unittest.TestCase):
    def test_extracts_full_specs_table_shape(self):
        specs = extract_specs_alo(REALISTIC_DETAIL_PAGE_TABLE_SHAPE)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["property_type_raw"], "Ателие/Студио")
        self.assertEqual(specs["sqm"], 57)
        self.assertEqual(specs["construction_type"], "ЕПК/ПК")
        self.assertEqual(specs["built_year"], 1980)
        self.assertEqual(specs["completion_status"], "Готов (завършен)")
        self.assertEqual(specs["floor_number"], 12)
        self.assertEqual(specs["floor_qualifier"], "Непоследен")
        self.assertEqual(specs["features"], ["Асансьор", "Необзаведен", "ТЕЦ"])
        self.assertTrue(specs["has_elevator"])
        self.assertFalse(specs["furnished"])
        self.assertTrue(specs["has_central_heating"])

    def test_extracts_partial_specs_div_shape_and_decimal_sqm(self):
        specs = extract_specs_alo(REALISTIC_DETAIL_PAGE_DIV_SHAPE)
        self.assertIsNotNone(specs)
        self.assertEqual(specs["property_type_raw"], "Тристаен апартамент")
        self.assertEqual(specs["sqm"], 86)  # round(85.5)
        self.assertEqual(specs["completion_status"], "Груб стоеж")
        self.assertEqual(specs["floor_number"], 3)
        self.assertEqual(specs["features"], ["Асансьор"])
        self.assertTrue(specs["has_elevator"])
        # construction_type/built_year/floor_qualifier genuinely absent
        # from this fixture's rows - must be left out, not guessed.
        self.assertNotIn("construction_type", specs)
        self.assertNotIn("built_year", specs)
        self.assertNotIn("floor_qualifier", specs)
        # Only one feature present - no unfurnished/heating claim to make.
        self.assertNotIn("furnished", specs)
        self.assertNotIn("has_central_heating", specs)

    def test_returns_none_when_no_known_label_present(self):
        self.assertIsNone(extract_specs_alo(UNRELATED_PAGE))

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_specs_alo("<<<not even html"))
        self.assertIsNone(extract_specs_alo(""))

    def test_built_year_out_of_plausible_range_is_dropped(self):
        html = """<table>
        <tr><td>Година на строителство</td><td><strong>90210</strong></td></tr>
        </table>"""
        specs = extract_specs_alo(html)
        # A single implausible "year" is the only thing on the page - no
        # other spec label matches, so the whole function should find
        # nothing usable rather than store a bogus year.
        self.assertIsNone(specs)


class ExtractContactAloTest(unittest.TestCase):
    def test_extracts_name_and_real_external_website_table_shape(self):
        contact = extract_contact_alo(REALISTIC_DETAIL_PAGE_TABLE_SHAPE)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "ENDREVA HAUSES")
        self.assertEqual(contact["agency_website"], "https://endreva-houses.com")
        # The masked phone number must never be extracted as a real value.
        self.assertNotIn("phone", contact)
        self.assertNotIn("08X XXX XXXX", str(contact.values()))

    def test_extracts_individual_seller_div_shape_skips_mailto(self):
        contact = extract_contact_alo(REALISTIC_DETAIL_PAGE_DIV_SHAPE)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "Иван Петров")
        # mailto: link must be skipped in favor of the real http(s) site.
        self.assertEqual(contact["agency_website"], "https://www.some-agency.bg")

    def test_returns_none_when_heading_absent(self):
        self.assertIsNone(extract_contact_alo(UNRELATED_PAGE))

    def test_returns_none_when_heading_present_but_no_links_at_all(self):
        html = """<div><h3>Контакт с подателя на обявата</h3><p>Иван Иванов</p></div>"""
        self.assertIsNone(extract_contact_alo(html))

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_contact_alo("<<<not even html"))
        self.assertIsNone(extract_contact_alo(""))

    def test_alo_hosted_storefront_link_alone_yields_no_website(self):
        # Only an endrevahouses.alo.bg-style link present, no real external
        # site - agency_name should still come through, agency_website
        # should not be set to the internal alo.bg profile link.
        html = """
        <div>
          <h3>Контакт с подателя на обявата</h3>
          <strong>SOLO AGENCY</strong>
          <a href="https://soloagency.alo.bg">soloagency.alo.bg</a>
        </div>
        """
        contact = extract_contact_alo(html)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["agency_name"], "SOLO AGENCY")
        self.assertNotIn("agency_website", contact)


if __name__ == "__main__":
    unittest.main(verbosity=2)
