"""
Regression test for Missy's PR #264 THIRD review (2026-09-23, BLOCKING
finding A) - CATEGORY_KEYWORDS["land"]'s "поземлен имот" keyword (added for
the round-2 fix) matched standard Bulgarian cadastral-registry boilerplate
that appears inside almost any building's own listing text ("...построена в
поземлен имот с идентификатор № 67338.516.1..." - describing the LAND
PARCEL UNDERNEATH a building, never the property being sold), not just
genuine land-for-sale listings that happen to use the same phrase to name
their own subject.

Confirmed live: imotibg_515292 ("Търговско помещение, Република" - a 460m²
commercial food-service space) was wrongly flipped flat->land purely
because its description contains this boilerplate shape. Missy searched all
6 non-bcpea portals for "поземлен имот с идентификатор" and found 15 total
records: 11 genuinely land, 2 genuinely business, 1 (imotibg_515292) wrong
(the fix target, flat), and 1 (olx_9Sr6A, an admin building with garage
cells) correctly `garage` via CATEGORY_ORDER's static tiebreak against
land/business/flat - unaffected by _ZEMYA_IMOT_RE either way, listed here
only so the count adds up to the full 15 (corrected from an earlier
"12 land" miscount, PR #264 fourth review, 2026-09-23: olx_9Sr6A was
wrongly folded into the "land" bucket the first time this was counted).
See category_classifier.py's _ZEMYA_IMOT_RE for the fix - a negative
lookahead that excludes only the "поземлен имот" + "с идентификатор"
boilerplate shape, while still matching every other real phrasing
(including genuine land listings that cite their own parcel's identifier
using a different construction, e.g. no "с").
"""

import unittest

from category_classifier import classify_listing


class ZemyaImotCadastralBoilerplateTest(unittest.TestCase):
    def test_commercial_space_with_cadastral_boilerplate_not_classified_as_land(self):
        # Real, live-sampled imoti.bg listing (imotibg_515292, 2026-09-23) -
        # was wrongly "land"/"low" before this fix. No other land/shop/
        # business keyword in this text, so it correctly falls back to the
        # no-match "flat" default, same as the classifier's own behavior
        # before "поземлен имот" was ever added as a keyword.
        category, confidence, reason = classify_listing(
            title="Търговско помещение, Република",
            description=(
                "Самостоятелен обект в сграда с идентификатор 67338.516.1.1.2, "
                "с преназначение – за обществено хранене, с площ 460 кв.м., "
                "разположен в четириетажна сграда с идентификатор "
                "67338.516.1.1, с преназначение административна, делова "
                "сграда, със застроена площ 786 кв.м., построена в поземлен "
                "имот с идентификатор № 67338.516.1- публична държавна "
                "собственост,  находящ се в гр. Сливен, ул."
            ),
        )
        self.assertNotEqual(category, "land")
        self.assertEqual((category, confidence, reason), ("flat", "low", "no_keyword_match"))

    def test_bordering_boilerplate_variant_with_comma_not_classified_as_land(self):
        # Same boilerplate shape, comma-separated variant ("поземлен имот,
        # с идентификатор") - confirmed live phrasing variant exists in
        # this project's own stored text.
        category, _, _ = classify_listing(
            description="Обектът е построен в поземлен имот, с идентификатор 12345.67.89, целият с площ 500 кв.м."
        )
        self.assertNotEqual(category, "land")

    def test_genuine_land_listing_citing_own_identifier_still_classified_as_land(self):
        # Non-regression - a genuine land-for-sale listing that names its
        # own parcel's cadastral identifier as the actual subject must
        # still classify as land. Real, live-sampled olx.bg listing
        # (olx_a4Xck, 2026-09-23) - its OWN title already says "Парцел"
        # (a different, unguarded land keyword), so it isn't solely
        # dependent on the "поземлен имот с идентификатор" phrase - the
        # same reason this record stays correct after the guard (it has
        # its own independent land evidence, unlike imotibg_515292).
        category, _, _ = classify_listing(
            title="ТОП ИНВЕСТИЦИЯ! Парцел в с. Кичево, Кичево",
            description=(
                "Парцел в с. Кичево – За Складово/Бизнес или Жилищно "
                "строителство. Продава се атрактивен поземлен имот с "
                "идентификатор 37099.61.45, находящ се в землището на "
                "с. Кичево."
            ),
        )
        self.assertEqual(category, "land")

    def test_genuine_land_listing_identifier_without_s_still_classified_as_land(self):
        # Non-regression - real, live-sampled olx.bg listing (olx_9Mx3k,
        # 2026-09-23): a genuine 5.7-decare agricultural land sale that
        # cites its own identifier without the word "с" - must not be
        # caught by the boilerplate guard, which only excludes the "с
        # идентификатор" shape specifically.
        category, _, _ = classify_listing(
            description=(
                "Земеделска земя, 5,733 декара, кат.9, местност Карчана, "
                "поземлен имот идентификатор 70247.76.41 цена 800 евро за 1 декар."
            )
        )
        self.assertEqual(category, "land")

    def test_genuine_land_listing_title_without_identifier_suffix_still_classified_as_land(self):
        # Non-regression - the overwhelming majority of real land listings
        # using "поземлен имот" as their own title/subject never mention
        # "идентификатор" at all.
        category, _, _ = classify_listing(
            title="Поземлен имот 3800м2 на 20 метра от къщи, ток и вода, Строево"
        )
        self.assertEqual(category, "land")


if __name__ == "__main__":
    unittest.main()
