"""
Regression/proof tests for scraper_bcpea.py's detail-page gallery/spec
investigation added 2026-09-24: extract_photos_bcpea() (new - a full photo
set, not just the single `.head` image already captured) and
unrecognized_labels() (new - a zero-cost tripwire for a genuine new
property-spec label, should sales.bcpea.org ever start rendering one).

CORRECTED 2026-09-25: this docstring, and extract_photos_bcpea()'s own,
previously described `.item__expanded`/`.head` as "CONFIRMED real markup".
A production audit found "photos" at a flat 0% (0/2,246) despite 100%
detail-page coverage and a 64% success rate for "Описание"/district on
those SAME pages - conclusive that `.head` inside `.item__expanded` never
actually matches real sales.bcpea.org markup, so "confirmed" is no longer
an accurate description of that specific claim (only `.item__expanded`
itself, and `.label__group`/`.label`/`.info`, remain genuinely confirmed -
those two fields DO populate in production). See
extract_photos_bcpea()'s own 2026-09-25 correction in scraper_bcpea.py for
the full reasoning, and expanded_image_diagnostic() (tested below,
alongside its capped call site in fetch_listing_detail()) for the
zero-cost, guess-free tripwire added instead of a blind selector fix -
this sandbox has no live access to sales.bcpea.org to confirm the real
fix, and CLAUDE.md rules out finding out via live workflow_dispatch
iteration.

Unlike tests/test_alo_detail_extraction.py's fixtures (built from real
user-supplied screenshots, since alo.bg's exact DOM shape was never
directly confirmed), these fixtures use markup this scraper already
parses successfully in production for OTHER fields: `.item__expanded`,
`.label__group`/`.label`/`.info` (see scraper_bcpea.py's own module
docstring and fetch_listing_detail()). The `.head`-based photo fixtures
below are kept (extract_photos_bcpea() must still handle that shape
correctly if it's ever right) but are no longer claimed as confirmed real -
see the correction above.

Run with: python3 -m unittest tests.test_bcpea_detail_extraction -v
(no pytest / other test framework is installed in this repo.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup

from scraper_bcpea import (
    BASE_URL,
    expanded_image_diagnostic,
    extract_photos_bcpea,
    label_info,
    unrecognized_labels,
)


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


# --- expanded_image_diagnostic() (added 2026-09-25) ---------------------
# The zero-cost tripwire fetch_listing_detail() now logs (capped, see
# tests/test_scraper_bcpea_photo_miss_tripwire.py) whenever
# extract_photos_bcpea() comes up empty. Modeled on the concrete real-world
# possibility extract_photos_bcpea()'s own correction names: `.head` living
# as a SIBLING section above an "expanded details" accordion, rather than
# nested inside `.item__expanded` as originally assumed.

# `.head` is a sibling of `.item__expanded`, not nested inside it - the
# hypothesis this diagnostic exists to help confirm or rule out.
HEAD_OUTSIDE_EXPANDED_SHAPE = """
<div class="item">
  <div class="head"><img src="/upload/1/1/real.jpg"></div>
  <div class="item__expanded">
    <div class="label__group"><span class="label">Район</span><span class="info">Център</span></div>
  </div>
</div>
"""

# The originally-assumed shape: `.head` nested inside `.item__expanded`.
HEAD_INSIDE_EXPANDED_SHAPE = REAL_SHAPE_SINGLE_PHOTO_TWO_LABELS


def _soup_and_expanded(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup, soup.find(class_="item__expanded")


class ExpandedImageDiagnosticTest(unittest.TestCase):
    def test_head_inside_expanded_reported_as_inside(self):
        soup, expanded = _soup_and_expanded(HEAD_INSIDE_EXPANDED_SHAPE)
        diag = expanded_image_diagnostic(soup, expanded)
        self.assertEqual(diag["inside_expanded"], ["(no class)"])
        self.assertEqual(diag["outside_expanded"], [])

    def test_head_outside_expanded_reported_as_outside(self):
        soup, expanded = _soup_and_expanded(HEAD_OUTSIDE_EXPANDED_SHAPE)
        diag = expanded_image_diagnostic(soup, expanded)
        self.assertEqual(diag["inside_expanded"], [])
        self.assertEqual(diag["outside_expanded"], ["(no class)"])

    def test_no_images_anywhere_yields_empty_lists(self):
        soup, expanded = _soup_and_expanded(
            '<div class="item__expanded"><p>No images here.</p></div>'
        )
        diag = expanded_image_diagnostic(soup, expanded)
        self.assertEqual(diag, {"inside_expanded": [], "outside_expanded": []})

    def test_distinct_class_lists_are_deduped(self):
        html = """
        <div class="item__expanded">
          <img class="thumb" src="/a.jpg">
          <img class="thumb" src="/b.jpg">
          <img class="thumb secondary" src="/c.jpg">
        </div>
        """
        soup, expanded = _soup_and_expanded(html)
        diag = expanded_image_diagnostic(soup, expanded)
        self.assertEqual(diag["inside_expanded"], ["thumb", "thumb secondary"])

    def test_handles_none_expanded(self):
        soup = BeautifulSoup(
            '<div class="head"><img src="/x.jpg"></div>', "html.parser"
        )
        diag = expanded_image_diagnostic(soup, None)
        self.assertEqual(diag["inside_expanded"], [])
        self.assertEqual(diag["outside_expanded"], ["(no class)"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
