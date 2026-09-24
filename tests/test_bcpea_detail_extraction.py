"""
Regression/proof tests for scraper_bcpea.py's detail-page gallery/spec
investigation added 2026-09-24: extract_photos_bcpea() (new - a full photo
set, not just the single `.head` image already captured) and
unrecognized_labels() (new - a zero-cost tripwire for a genuine new
property-spec label, should sales.bcpea.org ever start rendering one).

Unlike tests/test_alo_detail_extraction.py's fixtures (built from real
user-supplied screenshots, since alo.bg's exact DOM shape was never
directly confirmed), these fixtures use the CONFIRMED real markup this
scraper already parses successfully in production: `.item__expanded`,
`.head`, `.label__group`/`.label`/`.info` (see scraper_bcpea.py's own
module docstring and fetch_listing_detail()). What's genuinely unverified
this session (network egress to sales.bcpea.org is blocked here, same as
every other scraper's own egress-block note, and no second real saved
page with extra photos/labels was available to check) is only WHETHER a
real page ever puts more than one real <img> in `.item__expanded` or more
than the two already-known .label__group labels ("Район"/"Описание") on
it - not the markup shape itself. These tests exercise both the confirmed
single-photo/two-label shape (the only shape ever actually seen) and a
hypothetical richer shape, to prove the extractors handle either without
guessing or crashing.

Run with: python3 -m unittest tests.test_bcpea_detail_extraction -v
(no pytest / other test framework is installed in this repo.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup

from scraper_bcpea import extract_photos_bcpea, unrecognized_labels, label_info, BASE_URL


# The only shape ever actually confirmed against a real saved page: one
# photo in `.head`, exactly the two known labels ("Район"/"Описание").
REAL_SHAPE_SINGLE_PHOTO_TWO_LABELS = """
<div class="item__expanded">
  <div class="head"><img src="/upload/91569/457032/IMG_20260722_112419.jpg?w=270&h=270"></div>
  <div class="label__group"><span class="label">Район</span><span class="info">Лозенец</span></div>
  <div class="label__group"><span class="label">Описание</span><span class="info">
    Легален текст с кадастрален идентификатор 68134.4082.31, площ 57 кв.м.
  </span></div>
</div>
"""

# A page whose card image was the shared placeholder graphic (see
# fetch_listings_page()'s own "photo-placeholder.png" -> photo=None
# handling) reused inside .head on the detail page too - must not be
# captured as a real photo.
PLACEHOLDER_ONLY_SHAPE = """
<div class="item__expanded">
  <div class="head"><img src="/img/photo-placeholder.png"></div>
  <div class="label__group"><span class="label">Район</span><span class="info">Център</span></div>
</div>
"""

# Hypothetical richer shape (never confirmed live) - a gallery strip with
# a real second/third photo plus a site logo and a placeholder mixed in,
# and one genuinely new label alongside the two known ones. Proves the
# extractors would pick this up correctly if a real page like this exists,
# without ever having been built assuming it does.
HYPOTHETICAL_GALLERY_AND_EXTRA_LABEL_SHAPE = """
<div class="item__expanded">
  <div class="head"><img src="/upload/99001/1/main.jpg"></div>
  <div class="gallery">
    <img src="/upload/99001/1/main.jpg">
    <img src="/upload/99001/2/second.jpg">
    <img src="/upload/99001/3/third.jpg">
    <img src="https://sales.bcpea.org/img/site-logo.png">
    <img src="/img/photo-placeholder.png">
  </div>
  <div class="label__group"><span class="label">РАЙОН</span><span class="info">Триадица</span></div>
  <div class="label__group"><span class="label">Описание</span><span class="info">Легален текст.</span></div>
  <div class="label__group"><span class="label">Квадратура</span><span class="info">65 кв.м</span></div>
</div>
"""

NO_EXTRA_IMAGES_MULTIPLE_HEAD_REFERENCES_SHAPE = """
<div class="item__expanded">
  <div class="head"><img src="/upload/5/5/only.jpg"></div>
  <div class="label__group"><span class="label">Описание</span><span class="info">Текст.</span></div>
</div>
"""


def _expanded(html):
    return BeautifulSoup(html, "html.parser").find(class_="item__expanded")


class ExtractPhotosBcpeaTest(unittest.TestCase):
    def test_single_confirmed_real_shape_yields_one_photo(self):
        # The only shape ever actually confirmed - must not manufacture a
        # gallery that isn't there (same honesty standard as imoti.bg's
        # single-photo case).
        photos = extract_photos_bcpea(_expanded(REAL_SHAPE_SINGLE_PHOTO_TWO_LABELS))
        self.assertEqual(
            photos,
            ["https://sales.bcpea.org/upload/91569/457032/IMG_20260722_112419.jpg?w=270&h=270"],
        )

    def test_placeholder_only_yields_no_photos(self):
        self.assertEqual(extract_photos_bcpea(_expanded(PLACEHOLDER_ONLY_SHAPE)), [])

    def test_relative_src_resolved_against_base_url(self):
        photos = extract_photos_bcpea(_expanded(NO_EXTRA_IMAGES_MULTIPLE_HEAD_REFERENCES_SHAPE))
        self.assertEqual(photos, [BASE_URL + "/upload/5/5/only.jpg"])

    def test_gallery_shape_captures_extra_real_photos_head_first(self):
        photos = extract_photos_bcpea(_expanded(HYPOTHETICAL_GALLERY_AND_EXTRA_LABEL_SHAPE))
        self.assertEqual(
            photos,
            [
                "https://sales.bcpea.org/upload/99001/1/main.jpg",
                "https://sales.bcpea.org/upload/99001/2/second.jpg",
                "https://sales.bcpea.org/upload/99001/3/third.jpg",
            ],
        )
        # Logo and placeholder must never be treated as real photos.
        self.assertFalse(any("logo" in p for p in photos))
        self.assertFalse(any("placeholder" in p for p in photos))

    def test_head_image_deduped_against_gallery_repeat(self):
        # .head's own image also appearing again inside the gallery strip
        # (as in the hypothetical fixture above) must not be listed twice.
        photos = extract_photos_bcpea(_expanded(HYPOTHETICAL_GALLERY_AND_EXTRA_LABEL_SHAPE))
        self.assertEqual(len(photos), len(set(photos)))

    def test_no_expanded_images_at_all_yields_empty_list(self):
        html = '<div class="item__expanded"><div class="label__group"><span class="label">Район</span><span class="info">X</span></div></div>'
        self.assertEqual(extract_photos_bcpea(_expanded(html)), [])


class UnrecognizedLabelsBcpeaTest(unittest.TestCase):
    def test_confirmed_real_shape_has_no_unrecognized_labels(self):
        # The only shape ever actually confirmed - proves the tripwire
        # stays silent on exactly the page this scraper already handles in
        # production, not just on contrived input.
        self.assertEqual(unrecognized_labels(_expanded(REAL_SHAPE_SINGLE_PHOTO_TWO_LABELS)), [])

    def test_settlement_label_from_grid_markup_not_flagged(self):
        html = '<div class="item__expanded"><div class="label__group"><span class="label">Населено място</span><span class="info">София</span></div></div>'
        self.assertEqual(unrecognized_labels(_expanded(html)), [])

    def test_genuinely_new_label_is_flagged(self):
        labels = unrecognized_labels(_expanded(HYPOTHETICAL_GALLERY_AND_EXTRA_LABEL_SHAPE))
        self.assertEqual(labels, ["Квадратура"])

    def test_case_insensitive_known_labels_not_flagged(self):
        html = '<div class="item__expanded"><div class="label__group"><span class="label">РАЙОН</span><span class="info">X</span></div></div>'
        self.assertEqual(unrecognized_labels(_expanded(html)), [])

    def test_no_label_groups_at_all_yields_empty_list(self):
        html = '<div class="item__expanded"><p>No structured labels here.</p></div>'
        self.assertEqual(unrecognized_labels(_expanded(html)), [])


class LabelInfoStillWorksAlongsideNewHelpersTest(unittest.TestCase):
    # Confirms the pre-existing label_info() helper (unchanged by this
    # task) keeps working correctly on the same fixtures the new helpers
    # above are tested against - a regression guard, not new behavior.
    def test_district_and_description_still_extracted(self):
        expanded = _expanded(REAL_SHAPE_SINGLE_PHOTO_TWO_LABELS)
        self.assertEqual(label_info(expanded, "Район"), "Лозенец")
        self.assertIn("68134.4082.31", label_info(expanded, "Описание"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
