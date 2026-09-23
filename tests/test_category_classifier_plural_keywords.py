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


if __name__ == "__main__":
    unittest.main()
