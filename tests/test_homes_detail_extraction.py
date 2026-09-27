"""
Proof tests for geo_utils.extract_description_homes() - docs/backlog.md
item 9d (homes.bg description backfill).

This sandbox's network egress to homes.bg is fully blocked (confirmed via
both curl and WebFetch against several hosts - see item 9d's own
investigation log in docs/backlog.md), so none of this could be tested
against a real live page. These fixtures are synthetic HTML built to
exercise the 3-tier search order extract_description_homes() actually uses
(heading text "Описание" -> <meta name="description">/og:description ->
application/ld+json "description"), each tier modeled on a technique
already PROVEN to work on at least one other portal in this exact codebase
(see geo_utils.py's own comment above extract_description_homes() for the
full evidentiary trail on why each tier was chosen). Since the real DOM
structure is genuinely unverified, the heading-text tier is deliberately
structure-agnostic (works whether the heading and body share one wrapper or
are separate siblings) and every tier is proven here to degrade to None
on a non-matching page rather than guess or crash.

Run with: python3 -m unittest tests.test_homes_detail_extraction -v
(no pytest / other test framework is installed in this repo.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geo_utils import extract_description_homes


# A plausible detail-page shape: heading + sibling paragraph, real prose
# well over the minimum length guard.
HEADING_SIBLING_SHAPE = """
<html><body>
<h1>Тристаен апартамент, кв. Витоша, София, 78 кв.м</h1>
<div class="specs">...</div>
<section class="description-card">
<h2>Описание</h2>
<p>Продавам просторен тристаен апартамент в отлично състояние, разположен на
тих etage в кв. Витоша. Апартаментът разполага с две тераси, паркомясто и
допълнително мазе. В непосредствена близост до метростанция и училище.</p>
</section>
</body></html>
"""

# Same content, a different DOM shape - heading and body share one wrapper
# div instead of being separate sibling tags - proves the ancestor walk key
# off label TEXT, not a specific tag/class shape.
HEADING_SHARED_WRAPPER_SHAPE = """
<html><body>
<div class="offer-description-block">
  <strong>Описание:</strong>
  Просторен четиристаен апартамент с внушително тухлено строителство, две
  бани и голяма всекидневна с камина. Дворно място от 400 кв.м.
</div>
</body></html>
"""

# imot.bg-style label variant ("Описание на имота:") - homes.bg may or may
# not use this exact longer form; the heading regex accepts both.
HEADING_LONG_LABEL_SHAPE = """
<html><body>
<section>
<h3>Описание на имота:</h3>
<p>Двустаен апартамент в кв. Люлин, изцяло обновен през 2024 година, с нова
дограма, инсталации и настилки. Подходящ за живеене или инвестиция.</p>
</section>
</body></html>
"""

# A page with none of the known section labels at all.
UNRELATED_PAGE = """
<html><body>
<h1>404 - Обявата е премахната</h1>
<p>Съжаляваме, но тази обява вече не е налична.</p>
</body></html>
"""

# Reproduces the exact bug PR #217 already fixed: a "description"-labeled
# section that actually holds the short construction-material/furnishing
# tag line, not real prose - must be rejected by MIN_HOMES_DESCRIPTION_LENGTH,
# not returned as if it were a real description.
HEADING_WITH_ONLY_CONSTRUCTION_TAG_SHAPE = """
<html><body>
<h2>Описание</h2>
<p>Тухла/Бетон, Полуобзаведен</p>
</body></html>
"""

# The heading exists, but its own ancestor's text is just a title echo -
# same failure mode alo.bg's own fix guards against.
HEADING_TITLE_ECHO_SHAPE = """
<html><body>
<h2>Описание</h2>
<p>Тристаен апартамент, кв. Витоша, София, 78 кв.м</p>
</body></html>
"""

# No heading at all, but a real, substantial meta description tag.
META_DESCRIPTION_ONLY_PAGE = """
<html><head>
<meta name="description" content="Отлично поддържан тристаен апартамент за продажба в кв. Дружба, София - южно изложение, асансьор, паркинг, близо до метростанция.">
</head><body>
<h1>Апартамент, Дружба, София</h1>
</body></html>
"""

# og:description only (no plain "description" meta tag).
OG_DESCRIPTION_ONLY_PAGE = """
<html><head>
<meta property="og:description" content="Просторна двустайна къща в село Лозен с голям двор и лятна кухня, идеална за постоянно обитаване.">
</head><body></body></html>
"""

# A short, generic site-wide meta description (e.g. the homepage's own
# boilerplate leaking onto every page) - must be rejected as too short to
# plausibly be this listing's own real description.
SHORT_GENERIC_META_PAGE = """
<html><head>
<meta name="description" content="Имоти в България - homes.bg">
</head><body></body></html>
"""

# No heading, no meta description - only an ld+json block, the same shape
# olx.bg/bazar.bg already use successfully (extract_description_ldjson()).
LDJSON_ONLY_PAGE = """
<html><head>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Product",
 "description": "Реновирана гарсониера в центъра на Варна, готова за нанасяне, с нови мебели и електроуреди."}
</script>
</head><body></body></html>
"""

GARBAGE_HTML = "<<<not even html"

# The heading exists, but every ancestor within the search depth ALSO
# contains unrelated content (the page's own <h1> title, a specs
# placeholder) BEFORE the heading, so the heading never sits at the front
# of any candidate ancestor's flattened text. Must return None rather than
# leak that unrelated leading content back as if it were the description.
HEADING_WITH_UNRELATED_LEADING_CONTENT_SHAPE = """
<html><body>
<h1>Тристаен апартамент, кв. Витоша, София, 78 кв.м</h1>
<div class="specs">3 стаи, 78 кв.м, 2-ри етаж</div>
<h2>Описание</h2>
<p>Продавам просторен тристаен апартамент в отлично състояние.</p>
</body></html>
"""


class ExtractDescriptionHomesTest(unittest.TestCase):
    def test_extracts_real_description_heading_sibling_shape(self):
        desc = extract_description_homes(HEADING_SIBLING_SHAPE)
        self.assertIsNotNone(desc)
        self.assertIn("Продавам просторен тристаен апартамент", desc)
        self.assertIn("училище", desc)
        self.assertNotIn("Описание", desc)

    def test_extracts_real_description_shared_wrapper_shape(self):
        desc = extract_description_homes(HEADING_SHARED_WRAPPER_SHAPE)
        self.assertIsNotNone(desc)
        self.assertIn("Просторен четиристаен апартамент", desc)
        self.assertNotIn("Описание", desc)

    def test_extracts_real_description_long_label_shape(self):
        desc = extract_description_homes(HEADING_LONG_LABEL_SHAPE)
        self.assertIsNotNone(desc)
        self.assertIn("Двустаен апартамент в кв. Люлин", desc)
        self.assertNotIn("Описание", desc)

    def test_returns_none_when_no_tier_matches(self):
        self.assertIsNone(extract_description_homes(UNRELATED_PAGE))

    def test_rejects_construction_tag_masquerading_as_description(self):
        # The exact PR #217 bug shape, reached via a labeled section instead
        # of the grid JSON's "description" key - must not resurface here.
        self.assertIsNone(extract_description_homes(HEADING_WITH_ONLY_CONSTRUCTION_TAG_SHAPE))

    def test_rejects_title_echo(self):
        self.assertIsNone(
            extract_description_homes(
                HEADING_TITLE_ECHO_SHAPE,
                title="Тристаен апартамент, кв. Витоша, София, 78 кв.м",
            )
        )

    def test_falls_back_to_meta_description_when_no_heading(self):
        desc = extract_description_homes(META_DESCRIPTION_ONLY_PAGE)
        self.assertIsNotNone(desc)
        self.assertIn("кв. Дружба", desc)

    def test_falls_back_to_og_description(self):
        desc = extract_description_homes(OG_DESCRIPTION_ONLY_PAGE)
        self.assertIsNotNone(desc)
        self.assertIn("село Лозен", desc)

    def test_rejects_short_generic_meta_description(self):
        self.assertIsNone(extract_description_homes(SHORT_GENERIC_META_PAGE))

    def test_falls_back_to_ldjson_when_no_heading_or_meta(self):
        desc = extract_description_homes(LDJSON_ONLY_PAGE)
        self.assertIsNotNone(desc)
        self.assertIn("Варна", desc)

    def test_heading_tier_wins_over_meta_when_both_present(self):
        html = HEADING_SIBLING_SHAPE.replace(
            "<h1>", '<meta name="description" content="A completely different, unrelated meta description text here."><h1>'
        )
        desc = extract_description_homes(html)
        self.assertIn("Продавам просторен тристаен апартамент", desc)

    def test_returns_none_on_garbage_html(self):
        self.assertIsNone(extract_description_homes(GARBAGE_HTML))
        self.assertIsNone(extract_description_homes(""))

    def test_does_not_leak_unrelated_leading_content_when_heading_not_at_front(self):
        # No meta/ld+json fallback in this fixture either, so a correct
        # implementation must return None here, not the page's own <h1>
        # title text concatenated with the real description.
        self.assertIsNone(extract_description_homes(HEADING_WITH_UNRELATED_LEADING_CONTENT_SHAPE))


if __name__ == "__main__":
    unittest.main(verbosity=2)
