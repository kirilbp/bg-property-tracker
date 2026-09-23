"""
Regression test for Ready's second assignment (docs/decisions.md
2026-09-23 "Ready's second assignment" entry) - CATEGORY_KEYWORDS["land"]'s
own "упи" entry was a plain substring padded with a leading+trailing space
(" упи ") to avoid a false match inside an unrelated longer word (e.g.
"групи", "принцип") - but that padding requires a character to exist
BEFORE "упи" too, which a title that OPENS with "УПИ" (confirmed live to be
an extremely common real phrasing for a land-plot listing, e.g. olx.bg's
"УПИ до къщи в Първенец", "УПИ в село Мезек") never has, since it's the
very first word of the string. That silently made the single most common
real-world "упи" phrasing never match "land" at all - discovered while
migrating olx.bg to this classifier (154 of olx.bg's real land listings hit
this exact gap, sampled and confirmed genuinely all real land/plot
listings).

_UPI_RE (a proper \\b word-boundary regex) fixes this while still correctly
rejecting the same false-substring-match case the padding originally
guarded against.
"""

import unittest

from category_classifier import classify_listing


class UpiKeywordBoundaryTest(unittest.TestCase):
    def test_title_opening_with_upi_matches_land(self):
        # Real, live-sampled olx.bg title (data/history_olx.json,
        # 2026-09-23) - previously "no_keyword_match" -> defaulted to flat.
        category, confidence, reason = classify_listing(title="УПИ до къщи в Първенец, Първенец")
        self.assertEqual(category, "land")

    def test_title_opening_with_upi_lowercase_matches_land(self):
        category, confidence, reason = classify_listing(title="упи в село Мезек – перлата на Родопските подножия")
        self.assertEqual(category, "land")

    def test_upi_followed_by_comma_still_matches(self):
        category, _, _ = classify_listing(title="Продавам упи, готов за строеж")
        self.assertEqual(category, "land")

    def test_upi_mid_sentence_still_matches(self):
        category, _, _ = classify_listing(title="Инвестиционен имот - парцел с УПИ за жилищно строителство")
        self.assertEqual(category, "land")

    def test_false_substring_still_correctly_rejected(self):
        # The exact false-positive case the original " упи " padding was
        # meant to guard against - "групи"/"принцип" contain "упи" as a bare
        # substring but not as a real word; \b must still reject these.
        category, confidence, reason = classify_listing(
            title="Групи домове за възрастни хора - продава се комплекс"
        )
        self.assertNotEqual(category, "land")


if __name__ == "__main__":
    unittest.main()
