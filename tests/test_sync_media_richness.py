"""
Regression tests for the merged_listings photo/photos/description-richness
fix (backlog: site owner reported "every single listing needs to have
multiple photos when opened... priority for our listing the one with
multiple photos and full description").

Root cause (sync_to_supabase.py's build_rows(), confirmed by reading the
code, not re-derived): for a cross-posted group, EVERY MERGED_FIELDS value
- including photo/photos/description - came from `best`, the group's
single highest-compute_motivation_score() source. That score is price-
drop/days-on-market/price-vs-area-average - unrelated to how many photos a
source has or whether it has a real description - so a merged listing
could always end up with a 1-photo, no-description source's media even
when a different cross-posted source for the exact same real property had
many photos and a full description right there in the same group.

The fix adds select_media_best(), used only for photo/photos/description,
while every other MERGED_FIELDS value still comes from `best` unchanged.
These tests exercise select_media_best() and _photo_count()/
_has_real_description() directly against synthetic fixtures (real-data
verification - concrete before/after examples from the actual committed
leads_*.json(.gz) files and the overall %% of merged listings affected -
was done separately and is written up in docs/decisions.md, not repeated
here as a unit test since it needs the real, large, gitignored-in-CI-sense
data files).

Run with: python3 -m unittest tests.test_sync_media_richness -v
(no pytest / other test framework is installed in this repo - matches
every other tests/test_*.py file's own header.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_to_supabase import (
    MEDIA_FIELDS,
    _has_real_description,
    _photo_count,
    build_rows,
    select_media_best,
)


def source(portal, score, photo=None, photos=None, description=None, **extra):
    """A minimal listing_sources-shaped dict - just the fields these tests
    care about, plus whatever build_rows()'s wider pipeline needs to not
    crash (sqm/area/price_eur/id/title/city) when exercised end to end."""
    s = {
        "id": f"{portal}_1",
        "portal": portal,
        "score": score,
        "photo": photo,
        "photos": photos,
        "description": description,
        "title": extra.pop("title", "Двустаен апартамент, Люлин 4, София"),
        "sqm": extra.pop("sqm", 65),
        "area": extra.pop("area", "Люлин 4"),
        "city": extra.pop("city", "София"),
        "price_eur": extra.pop("price_eur", 140000),
    }
    s.update(extra)
    return s


class PhotoCountTests(unittest.TestCase):
    def test_uses_photos_list_length_when_present(self):
        s = source("homes.bg", 10, photo="p.jpg", photos=["a.jpg", "b.jpg", "c.jpg"])
        self.assertEqual(_photo_count(s), 3)

    def test_single_photo_field_with_no_photos_list_counts_as_one(self):
        # The literal "original listing with only one photo" case from the
        # bug report - imoti.bg (and most portals, most of the time) never
        # populate "photos" (plural) at all, only "photo" (singular).
        s = source("imoti.bg", 10, photo="only.jpg", photos=None)
        self.assertEqual(_photo_count(s), 1)

    def test_no_photo_at_all_counts_as_zero(self):
        s = source("bcpea", 10, photo=None, photos=None)
        self.assertEqual(_photo_count(s), 0)

    def test_empty_photos_list_falls_back_to_photo_field(self):
        s = source("olx.bg", 10, photo="only.jpg", photos=[])
        self.assertEqual(_photo_count(s), 1)


class HasRealDescriptionTests(unittest.TestCase):
    def test_empty_description_is_not_real(self):
        s = source("imot.bg", 10, description=None)
        self.assertFalse(_has_real_description(s))
        s2 = source("imot.bg", 10, description="   ")
        self.assertFalse(_has_real_description(s2))

    def test_title_echo_is_not_a_real_description(self):
        # Mirrors the confirmed alo.bg bug shape (geo_utils.py's own
        # _looks_like_title_echo(), reused here rather than duplicated):
        # a "description" that's just a substring of the title.
        s = source(
            "alo.bg", 10,
            title="Двустаен апартамент в к-с Суит хоум 2 Слънчев бряг, област Бургас",
            description="Двустаен апартамент в к-с Суит хоум 2",
        )
        self.assertFalse(_has_real_description(s))

    def test_real_free_text_description_is_real(self):
        s = source(
            "bazar.bg", 10,
            title="Двустаен апартамент, Люлин 4",
            description="Продавам светъл и функционален двустаен апартамент, "
                         "разположен на комуникативно място, 8-ми етаж от 8.",
        )
        self.assertTrue(_has_real_description(s))


class SelectMediaBestTests(unittest.TestCase):
    def test_single_source_group_is_a_complete_no_op(self):
        # The ~majority of listings aren't cross-posted at all - group size
        # 1 - and this fix must not touch that case.
        only = source("imoti.net", 42, photo="p.jpg", photos=["p.jpg"],
                       description="Real description here, plenty of text.")
        self.assertIs(select_media_best([only]), only)

    def test_prefers_source_with_most_photos_over_highest_score(self):
        best_by_score = source("imoti.net", 38, photo="one.jpg", photos=None,
                                description=None)
        richer = source("homes.bg", 36, photo="a.jpg",
                         photos=["a.jpg", "b.jpg", "c.jpg", "d.jpg"],
                         description="Истинско, пълно описание на имота тук.")
        sorted_sources = sorted([best_by_score, richer],
                                 key=lambda s: s["score"], reverse=True)
        self.assertIs(sorted_sources[0], best_by_score)  # sanity: best-by-score really is first
        self.assertIs(select_media_best(sorted_sources), richer)

    def test_photo_count_tie_broken_by_real_description(self):
        no_desc = source("imoti.net", 27, photo="a.jpg",
                          photos=["a.jpg", "b.jpg", "c.jpg"], description=None)
        with_desc = source("homes.bg", 10, photo="x.jpg",
                            photos=["x.jpg", "y.jpg", "z.jpg"],
                            description="Реално описание с достатъчно текст.")
        sorted_sources = sorted([no_desc, with_desc],
                                 key=lambda s: s["score"], reverse=True)
        # Same photo count (3 == 3); the lower-scoring source has the only
        # real description among the tied-max-photo candidates, so it wins
        # despite scoring far lower - proves the description tiebreak
        # actually overrides plain motivation-score order, not just agrees
        # with it by coincidence.
        self.assertIs(select_media_best(sorted_sources), with_desc)

    def test_full_tie_falls_back_to_motivation_score_order(self):
        a = source("imoti.net", 50, photo="a.jpg", photos=["a.jpg", "b.jpg"],
                    description=None)
        b = source("homes.bg", 20, photo="c.jpg", photos=["c.jpg", "d.jpg"],
                    description=None)
        sorted_sources = sorted([a, b], key=lambda s: s["score"], reverse=True)
        # Tied on photo count, neither has a real description - falls back
        # to sorted_sources' existing motivation-score order, i.e. `a`.
        self.assertIs(select_media_best(sorted_sources), a)

    def test_no_source_with_more_than_one_photo_falls_back_to_best(self):
        best = source("imoti.net", 50, photo="a.jpg", photos=None, description=None)
        other = source("olx.bg", 10, photo="b.jpg", photos=None,
                        description="Дори с реално описание тук, но само 1 снимка.")
        sorted_sources = sorted([best, other], key=lambda s: s["score"], reverse=True)
        # Nobody has >1 photo - nothing richer to prefer on the photo axis,
        # so this must not surprise-pick `other` just because it has a
        # description; falls back to `best` (today's behavior) entirely.
        self.assertIs(select_media_best(sorted_sources), sorted_sources[0])
        self.assertIs(select_media_best(sorted_sources), best)

    def test_zero_photos_everywhere_falls_back_to_best(self):
        best = source("imoti.net", 50, photo=None, photos=None, description=None)
        other = source("olx.bg", 10, photo=None, photos=None, description=None)
        sorted_sources = sorted([best, other], key=lambda s: s["score"], reverse=True)
        self.assertIs(select_media_best(sorted_sources), best)


class BuildRowsIntegrationTests(unittest.TestCase):
    """Exercises the actual build_rows() wiring (not just select_media_best()
    in isolation) against a small synthetic cross-posted group, proving the
    merged row really does pick up media_best's photo/photos/description
    while every other MERGED_FIELDS value still comes from `best`."""

    def test_merged_row_uses_media_best_for_media_only(self):
        best = source(
            "imoti.net", 38, photo="one.jpg", photos=None, description=None,
            url="https://imoti.net/best", price_per_sqm=2154,
        )
        richer = source(
            "homes.bg", 20, photo="a.jpg",
            photos=["a.jpg", "b.jpg", "c.jpg", "d.jpg"],
            description="Пълно, истинско описание с достатъчно текст тук.",
            url="https://homes.bg/richer", price_per_sqm=2200,
        )
        listing_source_rows, merged_rows = build_rows([best, richer])

        self.assertEqual(len(merged_rows), 1)
        merged = merged_rows[0]

        # Media fields come from `richer` (media_best), not `best`.
        self.assertEqual(merged["photos"], richer["photos"])
        self.assertEqual(merged["photo"], richer["photo"])
        self.assertEqual(merged["description"], richer["description"])

        # Every other MERGED_FIELDS value is unchanged from today's
        # behavior - still `best` (highest motivation score), never
        # media_best. url/price_per_sqm stand in for "everything else".
        self.assertEqual(merged["url"], best["url"])
        self.assertEqual(merged["price_per_sqm"], best["price_per_sqm"])
        self.assertEqual(merged["portal"], best["portal"])

        # listing_sources rows (the per-portal rows, not the merged row)
        # are completely untouched by this fix - each still carries its
        # own real photo/photos/description, not media_best's.
        by_portal = {r["portal"]: r for r in listing_source_rows}
        self.assertEqual(by_portal["imoti.net"]["photos"], best["photos"])
        self.assertEqual(by_portal["homes.bg"]["photos"], richer["photos"])

    def test_single_portal_listing_build_rows_is_unaffected(self):
        only = source("imoti.net", 10, photo="p.jpg", photos=["p.jpg"],
                       description="Real description, plenty of text here.")
        listing_source_rows, merged_rows = build_rows([only])
        self.assertEqual(len(merged_rows), 1)
        merged = merged_rows[0]
        for f in MEDIA_FIELDS:
            self.assertEqual(merged[f], only[f])


if __name__ == "__main__":
    unittest.main()
