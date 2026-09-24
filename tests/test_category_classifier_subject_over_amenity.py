"""
Regression tests for Ready's second assignment (docs/decisions.md
2026-09-23 "Ready's second assignment" entry) - the double-counting
scoring bug flagged (but deliberately NOT fixed) as a residual gap in
Ready's first assignment: the garage-tiebreak fix
(_resolve_garage_tie/_title_match_positions) only fires when two
categories' raw scores land on an EXACT tie. The same real-world shape
("гараж"/"паркомясто"/"склад"/etc. mentioned as an attached amenity of a
listing whose real subject is something else) also produces an outright,
non-tied win for the wrong category whenever the SAME amenity word appears
in both the title and the url - e.g. a url that's a portal-generated
transliteration of the title (confirmed live for olx.bg: a house listing's
own url spells "къща" as "kascha", a spelling CATEGORY_KEYWORDS["house"]
didn't have, so only "гараж"/"garazh" - present in both title and url -
contributed to any score, giving garage 5 (title 3 + url 2) outright
against house's 3 (title only), no tie, "high" confidence).

_resolve_subject_over_amenity() generalizes the exact same "Bulgarian
titles are subject-first, amenities-appended" position reasoning the
garage-tie fix already established, checked regardless of whether the raw
scores happen to land on a tie: an amenity-class winner (garage/shop/
business) is overridden by the title's own leftmost SUBJECT-class match
(flat/house/land) whenever that subject match precedes the winner's own
title match - and left alone (same "apples-to-apples only" discipline as
the original tie fix) whenever the winner has no match inside the title at
all, since there's then no title position to compare against.

This file proves:
  1. The real, live-sampled olx.bg regression case (house mislabeled
     garage via title+url double-counting, non-tied, "high" confidence)
     now classifies as "house" - and that it genuinely discriminates the
     bug (fails without the fix, passes with it).
  2. The originally-disclosed alo.bg case from Ready's first assignment
     ("Четиристаен в Свети Влас + паркомясто + склад") now classifies as
     "flat" instead of losing outright to garage/business.
  3. This is NOT scoped to "garage" only, unlike the first fix - a "shop"
     or "business" outright win over a leftmost title subject is corrected
     the same way, since none of the real-data evidence behind this fix
     was garage-specific.
  4. Non-regression: an amenity-class category that IS the title's own
     leftmost/real subject (a genuine garage/shop/business-for-sale
     listing) is never overridden, even when a subject-class word appears
     later in the same title.
  5. Non-regression: when the amenity-class winner has NO match inside the
     title at all (its whole score came from url/description), the
     existing tie/CATEGORY_ORDER fallback is left alone - unchanged from
     before this fix, matching the already-shipped
     test_tie_missing_title_evidence_for_one_side_falls_back_unchanged
     case in test_category_classifier_garage_tiebreak.py.

Run with: python3 -m pytest tests/test_category_classifier_subject_over_amenity.py -v
"""

import unittest

from category_classifier import classify_listing, CATEGORY_ORDER


def _pre_fix_classify(title=None, description=None, url=None):
    """Reimplements classify_listing() exactly as it was before THIS fix
    (i.e. including the already-shipped garage-tie fix, but without
    _resolve_subject_over_amenity) - so tests can prove a case genuinely
    discriminates THIS bug specifically."""
    from category_classifier import _score_signal, _resolve_garage_tie

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
        if "garage" in winners:
            resolved = _resolve_garage_tie(winners, title)
            if resolved is not None:
                return resolved, "low", "tied_categories_by_title_position:" + ",".join(winners)
        return winner, "low", "tied_categories:" + ",".join(winners)

    if len(matched_signals[winner]) < 2:
        return winner, "low", "single_signal_only"

    return winner, "high", None


class SubjectOverAmenityDiscriminatesBugTest(unittest.TestCase):
    def test_real_olx_house_with_garage_url_echo_discriminates(self):
        # Real, live-sampled title/url from data/history_olx.json
        # (2026-09-23) - a real house listing that mentions an attached
        # garage; olx.bg's own url is a transliteration of the title that
        # happens to spell "къща" as "kascha" (not a spelling
        # CATEGORY_KEYWORDS["house"] has), so only the garage amenity word
        # doubled up across title+url, letting garage win outright.
        title = "Продавам двуетажна къща 206РЗП и двор 525кв.м. с гараж в с.Тополово, Тополово"
        url = (
            "https://www.olx.bg/d/ad/prodavam-dvuetazhna-kascha-206rzp-i-dvor-"
            "525kv-m-s-garazh-v-s-topolovo-CID368-ID9N4BR.html"
        )

        pre_fix_category, pre_fix_confidence, _ = _pre_fix_classify(title=title, url=url)
        self.assertEqual((pre_fix_category, pre_fix_confidence), ("garage", "high"))

        category, confidence, reason = classify_listing(title=title, url=url)
        self.assertEqual(category, "house")
        self.assertEqual(confidence, "low")
        self.assertTrue(reason.startswith("title_subject_override:garage->house"))

    def test_disclosed_alo_double_counting_case_discriminates(self):
        # The exact case flagged as a NOT-yet-fixed residual gap in Ready's
        # first assignment (docs/decisions.md 2026-09-23 "Ready's first
        # assignment" entry) - real alo.bg listing alo_11375674, a genuine
        # 4-room flat that loses to garage/business on raw score before the
        # tiebreak logic even runs.
        title = "Четиристаен в Свети Влас + паркомясто + склад"
        url = "https://www.alo.bg/obiava/chetiristaen-svети-vlas-parkomyasto-sklad-12345"

        pre_fix_category, pre_fix_confidence, _ = _pre_fix_classify(title=title, url=url)
        self.assertIn(pre_fix_category, ("garage", "business"))

        category, confidence, reason = classify_listing(title=title, url=url)
        self.assertEqual(category, "flat")
        self.assertEqual(confidence, "low")
        self.assertTrue(reason.startswith("title_subject_override:"))

    def test_not_scoped_to_garage_shop_over_land_title_echo_discriminates(self):
        # Same double-counting shape, but the amenity-class winner is
        # "shop" (not "garage") - proves this fix isn't garage-specific,
        # unlike the first one. A land/parcel listing whose title mentions
        # an attached small shop unit later, with the shop word echoed in
        # the url too.
        title = "Парцел за застрояване в кв. Дружба с малък магазин на входа"
        url = "https://example.bg/obiava/partsel-druzhba-magazin-99999"

        pre_fix_category, pre_fix_confidence, _ = _pre_fix_classify(title=title, url=url)
        self.assertEqual(pre_fix_category, "shop")
        self.assertEqual(pre_fix_confidence, "high")

        category, confidence, reason = classify_listing(title=title, url=url)
        self.assertEqual(category, "land")
        self.assertEqual(confidence, "low")


class SubjectOverAmenityDoesNotOverGeneralizeTest(unittest.TestCase):
    def test_genuine_garage_listing_with_later_subject_word_unaffected(self):
        # Already covered by the garage-tie test file for the tied case;
        # confirming the SAME non-regression holds for an outright
        # (non-tied) genuine garage win too - garage is the title's own
        # leftmost/real subject, so it must not be overridden just because
        # "апартаменти" is mentioned later.
        title = "Гараж на 50м от нов комплекс с апартаменти, паркинг място включено"
        category, confidence, reason = classify_listing(title=title)
        pre_fix_category, pre_fix_confidence, pre_fix_reason = _pre_fix_classify(title=title)
        self.assertEqual((category, confidence, reason), (pre_fix_category, pre_fix_confidence, pre_fix_reason))
        self.assertEqual(category, "garage")

    def test_amenity_winner_with_zero_title_evidence_falls_back_unchanged(self):
        # The amenity winner's whole score comes from url/description, not
        # the title at all - no apples-to-apples title position to compare
        # a subject match against, so this must fall back to whatever the
        # existing tie/CATEGORY_ORDER logic already does (matches
        # test_tie_missing_title_evidence_for_one_side_falls_back_unchanged
        # in test_category_classifier_garage_tiebreak.py).
        title = "Апартамент"
        url = "https://example.bg/garazh-12345"
        description = "близо до паркомясто"
        category, confidence, reason = classify_listing(title=title, description=description, url=url)
        pre_fix_category, pre_fix_confidence, pre_fix_reason = _pre_fix_classify(
            title=title, description=description, url=url
        )
        self.assertEqual((category, confidence, reason), (pre_fix_category, pre_fix_confidence, pre_fix_reason))
        self.assertEqual(category, "garage")

    def test_genuine_shop_listing_unaffected(self):
        title = "Продава МАГАЗИН, Кършияка"
        category, confidence, reason = classify_listing(title=title)
        pre_fix_category, pre_fix_confidence, pre_fix_reason = _pre_fix_classify(title=title)
        self.assertEqual((category, confidence, reason), (pre_fix_category, pre_fix_confidence, pre_fix_reason))
        self.assertEqual(category, "shop")


if __name__ == "__main__":
    unittest.main()
