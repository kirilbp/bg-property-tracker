"""
Regression tests for Ready's first assignment (.claude/agents/ready.md,
docs/decisions.md 2026-09-23 "Ready" entry) - category_classifier.py's
CATEGORY_ORDER = ["garage", "shop", "business", "land", "house", "flat"] was
used ONLY as a tiebreak when two categories scored exactly equal, but with
"garage" listed first, it won every tie unconditionally - including the
dominant real-world case, confirmed by sampling 2,516 low-confidence
garage-tagged listings on 2026-09-23: a listing's title mentions a parking
space or garage ("паркомясто", "гараж") as an attached AMENITY of a flat,
house, shop or business listing ("Тристаен апартамент ... с ПАРКОМЯСТО",
"Етаж от къща с гараж и паркомясто"), which ties "garage" against the
listing's real category and garage won by list position alone, regardless
of which category actually described the property for sale.

The fix (_resolve_garage_tie / _title_match_positions in
category_classifier.py) resolves a garage/X tie by which tied category's
own keyword appears LEFTMOST in the title - real garage-for-sale titles are
templated to open with the word itself ("Garage, 14 м2 Sofia, ..."), so
garage stays leftmost (and keeps winning) in that genuine case, while an
amenity mention is always appended after the listing's real subject noun.
It only overrides the tie when every tied category actually has its own
match inside the title itself (the strongest, purpose-written signal); it
never touches non-garage ties or non-tied classifications at all.

This file proves:
  1. The exact reported bug case (the real, sampled title from
     .claude/agents/ready.md) now classifies as "flat", not "garage" - and
     that this specific assertion genuinely fails against the pre-fix
     tiebreak (CATEGORY_ORDER alone, no position check), not just that the
     fixed code happens to pass some assertion.
  2. The same amenity pattern for "house" (a house floor listing that
     mentions an attached garage) and money for other categories is
     resolved the same way.
  3. The explicit non-regression case this fix must NOT flip: a genuine
     garage-for-sale listing whose title also happens to mention nearby
     apartments/houses (garage's own keyword still leftmost) stays garage.
  4. A real garage-for-sale listing with no competing category mention at
     all (the imoti.net "Garage, NN м2 City, District" template) is
     unaffected - still garage, same confidence/reason as before.
  5. A tie that does NOT include "garage" at all is untouched - the fix is
     scoped to garage ties specifically, not a general tiebreak rewrite.

Run with: python3 -m pytest tests/test_category_classifier_garage_tiebreak.py -v
(or: python3 -m unittest tests.test_category_classifier_garage_tiebreak -v)
"""

import unittest

from category_classifier import classify_listing, CATEGORY_ORDER


def _pre_fix_classify(title=None, description=None, url=None):
    """Reimplements classify_listing() exactly as it was before this fix -
    CATEGORY_ORDER-only tiebreak, no title-position check - so tests can
    prove a case genuinely discriminates the bug (fails here, passes with
    the real, fixed classify_listing()) rather than just asserting the
    fixed behavior in isolation."""
    from category_classifier import _score_signal

    scores = {}
    matched_signals = {}
    _score_signal("title", title, scores, matched_signals)
    _score_signal("url", url, scores, matched_signals)
    _score_signal("description", description, scores, matched_signals)

    if not scores:
        return "flat", "low", "no_keyword_match"

    best_score = max(scores.values())
    winners = [cat for cat in CATEGORY_ORDER if scores.get(cat) == best_score]
    winner = winners[0]

    if len(winners) > 1:
        return winner, "low", "tied_categories:" + ",".join(winners)

    if len(matched_signals[winner]) < 2:
        return winner, "low", "single_signal_only"

    return winner, "high", None


class GarageTiebreakDiscriminatesBugTest(unittest.TestCase):
    """Proves each case actually discriminates the bug: fails under the
    old, pre-fix tiebreak, and passes under the real, fixed classifier."""

    def test_reported_bug_case_discriminates(self):
        title = "Тристаен апартамент в кв. Прослав с ПАРКОМЯСТО"

        pre_fix_category, pre_fix_confidence, pre_fix_reason = _pre_fix_classify(title=title)
        self.assertEqual(
            (pre_fix_category, pre_fix_confidence, pre_fix_reason),
            ("garage", "low", "tied_categories:garage,flat"),
            "pre-fix reproduction drifted from the originally-reported bug shape",
        )

        category, confidence, reason = classify_listing(title=title)
        self.assertEqual(category, "flat")
        self.assertEqual(confidence, "low")
        self.assertTrue(reason.startswith("tied_categories_by_title_position:"))

    def test_house_with_garage_amenity_discriminates(self):
        title = "Етаж от къща с гараж и паркомясто"

        pre_fix_category, _, _ = _pre_fix_classify(title=title)
        self.assertEqual(pre_fix_category, "garage")

        category, confidence, reason = classify_listing(title=title)
        self.assertEqual(category, "house")
        self.assertEqual(confidence, "low")

    def test_real_sampled_alo_titles_reclassify_to_flat(self):
        # Real, currently-live listing titles pulled from the low-confidence
        # garage pool on 2026-09-23 (data/history_alo.json) - every one of
        # these is a real apartment listing (room-count word + "апартамент"/
        # "мезонет"/"студио" as the title's lead subject) with a parking
        # space mentioned afterward as an amenity.
        real_titles = [
            "Кондор Недвижими Имоти преди 30+ дни Тристаен нов апартамент / "
            "Паркомясто/ Кършияка, Пловдив",
            "движими Имоти преди 4 дни Двустаен нов апартамент /Паркомясто/ - "
            "Широк Център-Изток, Център, Пловдив",
            "SUPRIMMO преди 30+ дни Студио с паркомясто в сграда ново "
            "строителство в кв. „Витоша“, Витоша, София",
            "реди 30+ дни 10-Продава се обзаведен мезонет с паркомясто в кв. "
            "„Освобождение“, Освобождение, Разград",
        ]
        for title in real_titles:
            with self.subTest(title=title):
                pre_fix_category, _, _ = _pre_fix_classify(title=title)
                self.assertEqual(pre_fix_category, "garage")

                category, _, _ = classify_listing(title=title)
                self.assertEqual(category, "flat")


class GarageTiebreakDoesNotOverGeneralizeTest(unittest.TestCase):
    """The explicit constraint from the task: garage/shop/business/land are
    also legitimately supposed to win a tie sometimes - this must not
    become a blanket "flat/house always wins" rule."""

    def test_garage_leftmost_of_its_own_tie_stays_garage(self):
        # A real garage-for-sale listing whose title happens to ALSO
        # mention nearby apartments - garage's own keyword is still the
        # title's lead subject (leftmost), so it must not flip to flat.
        title = "Гараж на 50м от нов комплекс с апартаменти"
        category, confidence, reason = classify_listing(title=title)
        self.assertEqual(category, "garage")
        self.assertEqual(confidence, "low")
        self.assertEqual(reason, "tied_categories:garage,flat")

    def test_genuine_garage_listing_no_competing_category_unaffected(self):
        # The imoti.net template for a real garage-for-sale listing - no
        # other category's keyword appears anywhere, so there's no tie at
        # all; this must classify exactly as it did before the fix.
        title = "Garage, 14 м 2 Sofia, Krastova Vada"
        url = (
            "https://www.imoti.net/en/obiava/prodava--v-stroej/sofia/"
            "krystova-vada/garaj/6274325/?sid=icNBCK&page=10"
        )
        category, confidence, reason = classify_listing(title=title, url=url)
        pre_fix_category, pre_fix_confidence, pre_fix_reason = _pre_fix_classify(title=title, url=url)
        self.assertEqual((category, confidence, reason), (pre_fix_category, pre_fix_confidence, pre_fix_reason))
        self.assertEqual(category, "garage")

    def test_non_garage_tie_is_untouched(self):
        # A tie that never involves "garage" at all must resolve exactly
        # as CATEGORY_ORDER always did - this fix is scoped to garage ties.
        title = "магазин терен"  # shop vs land, weight-3 each, no garage
        category, confidence, reason = classify_listing(title=title)
        pre_fix_category, pre_fix_confidence, pre_fix_reason = _pre_fix_classify(title=title)
        self.assertEqual((category, confidence, reason), (pre_fix_category, pre_fix_confidence, pre_fix_reason))
        self.assertEqual(category, "shop")  # shop precedes land in CATEGORY_ORDER

    def test_tie_missing_title_evidence_for_one_side_falls_back_unchanged(self):
        # flat scores 3 (title only: "Апартамент"). garage scores 3 too,
        # but entirely from url(2)+description(1) - "гараж"/"паркомясто"
        # never appear in the title at all. Since garage has no match
        # inside the title itself, there's no apples-to-apples position to
        # compare it against flat's, so this must fall back to the
        # original CATEGORY_ORDER behavior (garage listed first) unchanged.
        title = "Апартамент"
        url = "https://example.bg/garazh-12345"
        description = "близо до паркомясто"
        category, confidence, reason = classify_listing(title=title, description=description, url=url)
        pre_fix_category, pre_fix_confidence, pre_fix_reason = _pre_fix_classify(
            title=title, description=description, url=url
        )
        self.assertEqual((category, confidence, reason), (pre_fix_category, pre_fix_confidence, pre_fix_reason))
        self.assertEqual(category, "garage")


if __name__ == "__main__":
    unittest.main()
