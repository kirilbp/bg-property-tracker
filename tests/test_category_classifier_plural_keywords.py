"""
Regression test for Ready's second assignment (docs/decisions.md
2026-09-23 "Ready's second assignment" entry) - CATEGORY_KEYWORDS["house"]
had "къща"/"вила" (singular) but not "къщи"/"вили" (plural). Most Bulgarian
plurals in this list are formed by SUFFIXING the singular (e.g.
"апартамент"->"апартаменти", "офис"->"офиси", "склад"->"складове"), so the
singular substring already matches the plural for free - but "къща"/"вила"
are feminine nouns that pluralize by replacing the final "-а" with "-и"
("къща"->"къщи", "вила"->"вили"), so the singular substring never matches
the plural form at all. Confirmed live (data/leads_olx.json,
data/leads_alo.json, 2026-09-23): 191 olx.bg + 14 alo.bg real house
listings ("Две къщи с голям двор за продажба", "продавам 2 къщи в
Катуница") were missing "house" as a candidate category entirely because
of this, most defaulting to "flat" (the no-match fallback).

Extended for Missy's PR #264 review (2026-09-23, BLOCKING) - the original
"къщи"/"вили" fix above was itself found to have two real, live bugs once
verified against the FULL affected population (not just the small alo.bg
subset originally sampled): a substring-collision bug ("вили" matching
inside "павилион") and a land-vs-house context bug ("къщи"/"вили" mentioned
as neighboring/planned-development CONTEXT in a genuine land-plot listing,
not the listing's own subject). See category_classifier.py's own
_KASHTI_RE/_VILI_RE and _demote_context_only_house_signals comments for the
full root-cause detail these new tests cover.
"""

import unittest

from category_classifier import classify_listing


class HousePluralKeywordTest(unittest.TestCase):
    def test_plural_kashti_matches_house(self):
        # Real, live-sampled olx.bg title (2026-09-23) - previously
        # defaulted to "flat" (no_keyword_match).
        category, confidence, reason = classify_listing(title="Две къщи с голям двор за продажба гр. Борово, обл. Русе")
        self.assertEqual(category, "house")

    def test_plural_vili_matches_house(self):
        category, confidence, reason = classify_listing(title="Продавам два имота - вили в к.к. Пампорово")
        self.assertEqual(category, "house")

    def test_singular_kashta_still_matches(self):
        # Non-regression: the existing singular form must still work.
        category, _, _ = classify_listing(title="Продавам къща в село Х")
        self.assertEqual(category, "house")


class ViliPavilionSubstringCollisionTest(unittest.TestCase):
    """Missy's PR #264 review, bug class 1: "вили" (4 letters, no
    word-boundary guard) was a plain substring of "павилион" ("pavilion" -
    a small commercial kiosk, unrelated to houses) and several other real,
    live-confirmed unrelated words. 9 of 13 real "павилион" listings across
    portals were reclassified "house" over this, 4 at "high" confidence
    (olx_a4QA4, olx_a3C7D, olx_9C5tm, olx_9ZUa0)."""

    def test_pavilion_kiosk_not_classified_as_house(self):
        # Real, live-sampled olx.bg title (olx_a4QA4, 2026-09-23).
        category, _, _ = classify_listing(title="Модулен павилион, Бургас")
        self.assertNotEqual(category, "house")

    def test_working_business_pavilion_not_classified_as_house(self):
        # Real, live-sampled olx.bg title (olx_a3C7D, 2026-09-23).
        category, _, _ = classify_listing(title="Работещ бизнес - павилион за бързо хранене, Борово")
        self.assertNotEqual(category, "house")

    def test_pavilion_shop_not_classified_as_house(self):
        # Real, live-sampled olx.bg title (olx_9VKGa, 2026-09-23) - should
        # land on "shop" via its own "магазин" keyword, never "house".
        category, _, _ = classify_listing(title="Павилион магазин, Запад")
        self.assertNotEqual(category, "house")

    def test_branded_complex_name_with_vili_substring_not_classified_as_house(self):
        # "Привилидж"/"Сън Вилидж" are real apartment-complex BRAND names
        # (e.g. "Sun Village", "Privilege") containing "-вили-"/"-вилидж-"
        # as a mid-word substring, not the word "вили" itself - real,
        # live-sampled alo.bg titles (alo_11398759, alo_9761373).
        category, _, _ = classify_listing(
            title="Двустаен апартамент на първа линия в Привилидж Форт Бийч, Свети Влас"
        )
        self.assertNotEqual(category, "house")

    def test_past_tense_verb_suffix_not_classified_as_house(self):
        # A very common Bulgarian past-tense plural verb suffix
        # ("напра-вили", "предостави-ли") ends in the same 4 letters as
        # "вили" - must not be mistaken for the house-plural keyword.
        category, _, _ = classify_listing(
            title="Собствениците направили основен ремонт преди продажбата"
        )
        self.assertNotEqual(category, "house")

    def test_standalone_vili_word_still_matches_house(self):
        # Non-regression: the real, standalone plural word must still work
        # (this is the whole point of the original plural-keyword fix).
        category, _, _ = classify_listing(title="Продавам два имота - вили в к.к. Пампорово")
        self.assertEqual(category, "house")


class KashtiAvtokashtaSubstringCollisionTest(unittest.TestCase):
    """The same substring-collision class Missy's review found for "вили"
    also applied to "къщи" (the sibling plural keyword added by the same
    fix): "автокъща"/"автокъщи" (a real, common Bulgarian term for a CAR
    DEALERSHIP, "auto-house") and "вкъщи" ("at home", an adverb) both
    contain "къщи" as a bare substring - confirmed live in this project's
    own stored description text, 2026-09-23."""

    def test_car_dealerships_plural_not_classified_as_house(self):
        # "автокъщи" (plural of "автокъща" - "car dealerships") contains
        # "къщи" as a bare substring the same way "павилион" contains
        # "вили" - confirmed live in this project's own stored description
        # text, 2026-09-23. (The singular "автокъща" doesn't exercise this
        # specific bug at all - "къщи" is spelled with a trailing "и" that
        # only the PLURAL car-dealership form happens to share.)
        category, _, _ = classify_listing(
            title="Автокъщи, сервизи, складове, офиси, производства - продава се имотен комплекс"
        )
        self.assertNotEqual(category, "house")

    def test_at_home_adverb_does_not_trigger_house(self):
        category, _, _ = classify_listing(title="Апартамент, обзаведен като вкъщи, тих квартал")
        self.assertEqual(category, "flat")

    def test_standalone_kashti_word_still_matches_house(self):
        # Non-regression.
        category, _, _ = classify_listing(title="Две къщи с голям двор за продажба гр. Борово, обл. Русе")
        self.assertEqual(category, "house")

    def test_digit_glued_kashti_matches_house(self):
        # Missy's PR #264 third review, non-blocking finding (2026-09-23):
        # Python's \b doesn't separate a digit from a following Cyrillic
        # letter (both are \w), so a plain \b-bounded regex silently missed
        # this real, live-sampled olx.bg title (olx_9ECK4) - was wrongly
        # "flat"/"low" (no_keyword_match) before this fix.
        category, _, _ = classify_listing(
            title="Продава 2къщи в с.Соволяно общ.Кюстендил, Промишлена зона"
        )
        self.assertEqual(category, "house")


class LandVsHouseContextTest(unittest.TestCase):
    """Missy's PR #264 review, bug class 2: a genuine LAND-plot listing
    routinely mentions neighboring or future-planned houses as location
    CONTEXT, not as the property actually being sold - e.g. "20m FROM
    houses", "a plot WITH an approved project for six houses". 190 olx.bg +
    7 alo.bg + 1 imoti.bg real records were affected, 53 of the olx.bg ones
    at "high" confidence. See category_classifier.py's
    _demote_context_only_house_signals for the full root-cause detail."""

    def test_land_plot_near_neighboring_houses_classified_as_land(self):
        # Real, live-sampled olx.bg title+description (olx_9GeXh,
        # 2026-09-23) - was "house"/"high" before this fix.
        category, confidence, reason = classify_listing(
            title="код 62942. Поземлен имот 3800м2 на 20 метра от къщи, ток и вода., Строево",
            description=(
                "код 62942. Поземлен имот 3800м2 на 20 метра от обитаеми къщи, "
                "ток и вода. Идеален за парцелиране и жилищно застрояване."
            ),
        )
        self.assertEqual(category, "land")

    def test_land_plot_near_villas_classified_as_land(self):
        # Real, live-sampled olx.bg title (olx_9n4Jk, 2026-09-23) - was
        # "house"/"high" before this fix.
        category, _, _ = classify_listing(title="Парцел 430м2 до вили, ток и вода - за жилищно, Пловдив")
        self.assertEqual(category, "land")

    def test_land_plot_with_planned_house_project_classified_as_land(self):
        # Real, live-sampled olx.bg title (olx_a3vCU, 2026-09-23) - an
        # approved-but-unbuilt development plan for six houses is still
        # land, not house, until built. Was "house"/"high" before this fix.
        category, _, _ = classify_listing(
            title="Голям поземлен имот за продажба, с ПУП и проект за шест къщи, в с. Здр, Здравец"
        )
        self.assertEqual(category, "land")

    def test_land_plot_only_evidence_in_description_classified_as_land(self):
        # Real, live-sampled olx.bg title+description (olx_9RCOH,
        # 2026-09-23) - the trickiest of Missy's examples: the title alone
        # ("Имот 630м2... от последните къщи") never spells out "Поземлен",
        # only the description does, so this specifically exercises the
        # cross-signal corroboration path (Part B), not just same-signal
        # position (Part A). Was "house"/"high" before this fix.
        category, confidence, reason = classify_listing(
            title="код 63103. Имот 630м2  на 100 метра от последните къщи, до ток и вода, Цалапица",
            description=(
                "код 63103. Поземлен имот 630м2 на 100 метра от последните къщи, "
                "до ток и вода и на 150 м от асфалт с пряк достъп по мек път. "
                "Подходящ за жилищно застрояване след промяна на НТП."
            ),
        )
        self.assertEqual(category, "land")

    def test_genuine_multi_house_listing_with_shared_parcel_not_reclassified_to_land(self):
        # Non-regression - the first cut of this fix (specificity-only,
        # no position) WRONGLY flipped this real, live-sampled olx.bg
        # listing (olx_9PjA5) to "land": two actual houses, each with a
        # full room-by-room description, "in a shared parcel" trailing as
        # an attached-land AMENITY, not the listing's own subject. "къщи"
        # leads the title/description, "парцел"/"дворно място" trails -
        # must stay "house".
        category, confidence, reason = classify_listing(
            title="Две къщи с АКТ 14  в общ парцел в село Велика, Царево., Велика",
            description=(
                "Ем Джи Естейт продава две самостоятелни еднофамилни къщи в общ двор "
                "в село Велика. Всяка къща е на един етаж с РЗП от 102 кв. м. "
                "Дворното място е с площ 1000 кв.м."
            ),
        )
        self.assertEqual(category, "house")

    def test_genuine_multi_house_development_with_early_parcel_mention_stays_high_confidence(self):
        # Non-regression - a second, distinct false positive the first
        # cut's naive same-signal POSITION check introduced: a real,
        # live-sampled olx.bg house-development listing (olx_9ZyJH) whose
        # long description happens to OPEN by mentioning its underlying
        # "10 парцела" before describing the "4-ри редови къщи" (and each
        # one, by name, in singular - "Всяка къща...") actually being sold.
        # Must stay "house" at "high" confidence (title+description still
        # genuinely agree) - not merely avoid flipping to "land", but also
        # not lose confidence over an unrelated early mention.
        category, confidence, reason = classify_listing(
            title="Къща град Плевен Топ локация, Сторгозия",
            description=(
                "Капитол предлага в бутиков жилищен комплекс от затворен тип "
                "състоящ се от 10 парцела за хора с високи изисквания. "
                "Проектирани са 4-ри редови къщи. Всяка къща се продава като "
                "самостоятелна сграда. Къща 1 - 161 721 хил евро."
            ),
        )
        self.assertEqual(category, "house")
        self.assertEqual(confidence, "high")

    def test_house_listing_with_no_land_mention_at_all_unaffected(self):
        # Non-regression - the demotion logic must never even trigger when
        # there's no competing land evidence anywhere.
        category, confidence, reason = classify_listing(
            title="Къща в Плевен, област-с.Горталово площ 45 цена 53000, Горталово",
            description="Продава се едноетажна тухлена къща с двор, готова за нанасяне.",
        )
        self.assertEqual(category, "house")


class TitleBorrowingThirdFailureModeTest(unittest.TestCase):
    """Missy's PR #264 THIRD review (2026-09-23, BLOCKING finding B):
    _demote_context_only_house_signals' Part B let a signal with no land
    competitor of its own (like a title whose only house evidence is the
    ambiguous "къщи"/"вили" plural) borrow the "land wins" verdict from ANY
    other directly-demoted sibling signal - including the TITLE, even when
    the title's own plural mention was genuinely the ad's real, unambiguous
    subject. See category_classifier.py's _HOUSE_PROXIMITY_MARKER_RE /
    _has_house_proximity_context and Part B's own comment for the fix."""

    def test_title_naming_two_houses_as_direct_object_stays_house(self):
        # Missy's exact reproduction case (2026-09-23) - title alone
        # correctly classifies "house"; adding a description that mentions
        # bordering agricultural land used to wrongly flip the whole
        # listing to "land" via Part B's title-borrowing, even though
        # nothing about the title itself was ever ambiguous.
        title = "Продавам две къщи в село Раковски"
        description = (
            "Продавам голям недвижим имот. Земеделска земя в местността, "
            "граничеща с двете къщи, е включена в сделката. Всяка от "
            "къщите е тухлена, полумасивна конструкция, с отделен двор."
        )
        category, _, _ = classify_listing(title=title)
        self.assertEqual(category, "house")
        category, _, _ = classify_listing(title=title, description=description)
        self.assertEqual(category, "house")

    def test_land_plot_only_evidence_in_description_still_classified_as_land(self):
        # Non-regression - Part B must still correctly resolve the case it
        # was originally built for: a title with NO land competitor of its
        # own, but whose "къщи" mention reads as a locational/distance
        # reference ("...от последните къщи..." - "from the last houses"),
        # corroborated by the description's own directly-demoted verdict.
        # Real, live-sampled olx.bg listing (olx_9RCOH, 2026-09-23).
        category, confidence, reason = classify_listing(
            title="код 63103. Имот 630м2  на 100 метра от последните къщи, до ток и вода, Цалапица",
            description=(
                "код 63103. Поземлен имот 630м2 на 100 метра от последните къщи, "
                "до ток и вода и на 150 м от асфалт с пряк достъп по мек път. "
                "Подходящ за жилищно застрояване след промяна на НТП."
            ),
        )
        self.assertEqual(category, "land")

    def test_title_naming_villas_near_preposition_still_borrows_land_verdict(self):
        # A title whose plural house mention IS accompanied by a proximity
        # marker ("до вили" - "near villas"), with no land competitor of
        # its own in the title itself (so Part A can't settle it directly),
        # should still be eligible for Part B borrowing when the
        # description independently demotes.
        category, _, _ = classify_listing(
            title="Имот 1200м2 до вили, ток и вода",
            description="Поземлен имот 1200м2 до вили, ток и вода. Земеделска земя за продажба.",
        )
        self.assertEqual(category, "land")


if __name__ == "__main__":
    unittest.main()
