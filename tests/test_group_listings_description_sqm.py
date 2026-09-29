"""
Regression tests for the жк. Надежда 4 false merge (user-reported,
spot-checked live on imotenradar.com): "Двустаен, 174m2, жк. Надежда 4,
София" merged a real homes.bg listing (174 sqm, EUR173,200) with a
completely different bazar.bg listing (EUR174,000) whose own description
literally says "Площ: 71 кв.м." (71 sqm) - 174m2 and 71m2 cannot be the
same physical apartment.

Root cause, confirmed against the real committed data (data/leads_homes.
json.gz's homes_as1600786 and data/leads_bazar.json.gz's bazar_55365467):
bazar.bg's structured `sqm` field was null for that listing, so
group_listings() ran it through the without_sqm/solo_sqmless price-only
attach pass (price + area + city proximity, no per-listing unit
discriminator) instead of the strict with_sqm pass - exactly the
"sqm-less second pass" risk docs/decisions.md already disclosed (18.31%
accepted false-negative-adjacent regression, concentrated in exactly this
kind of busy жк. housing complex with many similar-priced units).

The fix: extract_description_sqm() recovers a real sqm figure from a
listing's own description text when its structured field is missing,
narrowly matching only the literal "Площ:" label (the same structured-field
-style text this confirmed case itself has embedded in its description) -
not free-form prose, which more often describes a balcony/plot/other
structure. group_listings() then uses this recovered value (via
_effective_sqm()) to decide which pass a listing goes through, so more
sqm-less listings get routed to the strict, already-tuned with_sqm pass
instead of the risky one. This does NOT touch the (portal, url) conflict
guard or any of the sqm_range/price_range/tie-break logic tuned in backlog
item 64, and it does NOT write the recovered value back onto the listing's
own `sqm` field - it is used for matching only, per docs/backlog.md.

Run with: python3 -m pytest -q tests/test_group_listings_description_sqm.py
(or python3 -m unittest, matching every other tests/test_*.py file.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_to_supabase import extract_description_sqm, group_listings


def listing(portal, id_, url=None, price_eur=100000, sqm=None, area="жк. Надежда 4",
            city="София", description=None, **extra):
    l = {
        "id": id_,
        "portal": portal,
        "url": url if url is not None else f"https://{portal}/{id_}",
        "price_eur": price_eur,
        "sqm": sqm,
        "area": area,
        "city": city,
        "description": description,
        "title": extra.pop("title", f"Апартамент, {area}, {city}"),
    }
    l.update(extra)
    return l


def group_containing(groups, portal, id_):
    for g in groups:
        for m in g:
            if m["portal"] == portal and m["id"] == id_:
                return g
    return None


class ExtractDescriptionSqmTests(unittest.TestCase):
    """Unit tests for the regex itself, independent of grouping."""

    def test_extracts_the_confirmed_real_bazar_description(self):
        # The exact confirmed real text (bazar_55365467's own description).
        desc = (
            "ЕМ ДЖИ Естейт продава двустаен апартамент в гр. София, ж.к. "
            "Надежда 4, бл. 429Площ: 71 кв.м.Етаж: 4.Изложение: север/юг"
        )
        self.assertEqual(extract_description_sqm(desc), 71)

    def test_handles_comma_decimal_and_dotless_kvm(self):
        self.assertEqual(extract_description_sqm("Площ: 62,88 кв.м"), 63)

    def test_returns_none_when_no_colon_label_present(self):
        # Free prose like "апартамент с площ от 90 кв.м" is deliberately
        # NOT matched - only the exact "Площ:" label is trusted (see the
        # module-level comment in sync_to_supabase.py for why).
        self.assertIsNone(
            extract_description_sqm("Просторен апартамент с площ от 90 кв.м, ремонтиран")
        )

    def test_returns_none_for_missing_description(self):
        self.assertIsNone(extract_description_sqm(None))
        self.assertIsNone(extract_description_sqm(""))

    def test_rejects_implausible_value(self):
        self.assertIsNone(extract_description_sqm("Площ: 99999 кв.м."))

    def test_rejects_qualified_area_labels(self):
        # Missy's review (2026-09-29): the first version of this regex
        # matched these too, via a bare search() for "площ:" that doesn't
        # care what word comes before it. "Чиста"/"Обща"/"Разгъната
        # застроена" площ are standard, different, non-comparable
        # measurements (net vs. gross/built area) from the unit's own
        # plain living area - routinely 10-20%+ apart for the same real
        # apartment, so none of these should ever be trusted as "the" sqm.
        self.assertIsNone(extract_description_sqm("Чиста площ: 68.21 кв.м + мазе"))
        self.assertIsNone(extract_description_sqm("Обща площ: 90 кв.м"))
        self.assertIsNone(extract_description_sqm("Разгъната застроена площ: 145 кв.м"))
        self.assertIsNone(extract_description_sqm("Полезна площ: 55 кв.м"))

    def test_falls_through_to_a_later_unqualified_площ_after_a_qualified_one(self):
        # A qualified "Обща площ:" earlier in the text must not block a
        # later, genuinely bare "Площ:" from being found and used.
        desc = "Обща площ: 90 кв.м. Жилището има Площ: 71 кв.м. по нотариален акт."
        self.assertEqual(extract_description_sqm(desc), 71)


class NadezhdaFourFalseMergeTests(unittest.TestCase):
    """The exact confirmed false merge this fix targets."""

    def test_sqm_less_listing_with_description_sqm_no_longer_merges_on_price_alone(self):
        homes_side = listing(
            "homes.bg", "homes_as1600786", price_eur=173200, sqm=174,
            title="Двустаен, 174m2, жк. Надежда 4, София",
        )
        bazar_side = listing(
            "bazar.bg", "bazar_55365467", price_eur=174000, sqm=None,
            title="Продава 2-СТАЕН, гр. София, Надежда 4",
            description=(
                "ЕМ ДЖИ Естейт продава двустаен апартамент в гр. София, "
                "ж.к. Надежда 4, бл. 429Площ: 71 кв.м.Етаж: 4."
            ),
        )
        groups = group_listings([homes_side, bazar_side])
        self.assertIsNot(
            group_containing(groups, "homes.bg", "homes_as1600786"),
            group_containing(groups, "bazar.bg", "bazar_55365467"),
            "174m2 and 71m2 must not be merged as the same apartment",
        )

    def test_sqm_less_listing_still_merges_when_description_sqm_genuinely_matches(self):
        # The other side of the fix: a bazar.bg listing whose description
        # sqm genuinely agrees with its cross-portal partner must still
        # merge - this is a precision improvement, not a new source of
        # false negatives on already-correct matches.
        homes_side = listing(
            "homes.bg", "homes_1", price_eur=173200, sqm=174,
            title="Двустаен, 174m2, жк. Надежда 4, София",
        )
        bazar_side = listing(
            "bazar.bg", "bazar_1", price_eur=173500, sqm=None,
            title="Продава 2-СТАЕН, гр. София, Надежда 4",
            description="Просторен апартамент.Площ: 174 кв.м.Етаж: 4.",
        )
        groups = group_listings([homes_side, bazar_side])
        self.assertIs(
            group_containing(groups, "homes.bg", "homes_1"),
            group_containing(groups, "bazar.bg", "bazar_1"),
        )

    def test_sqm_less_listing_with_no_extractable_description_still_falls_back_safely(self):
        # A listing with no "Площ:" text at all (e.g. bazar_53949423, the
        # second real false-merge candidate found in the same жк. Надежда 4
        # complex, whose description never states an area) keeps going
        # through the original without_sqm/solo_sqmless price-only pass
        # unchanged - this fix narrows the risky pass's population, it does
        # not remove it or change its own behavior. This is a known,
        # disclosed gap (see docs/backlog.md), not a regression.
        homes_side = listing(
            "homes.bg", "homes_1", price_eur=173200, sqm=174,
            title="Двустаен, 174m2, жк. Надежда 4, София",
        )
        bazar_side = listing(
            "bazar.bg", "bazar_2", price_eur=172982, sqm=None,
            title="Продава 2-СТАЕН, гр. София, Надежда 4",
            description="За повече информация: www.tobo-nadejda.bg. Обектът е със статут на АТЕЛИЕ.",
        )
        groups = group_listings([homes_side, bazar_side])
        self.assertIs(
            group_containing(groups, "homes.bg", "homes_1"),
            group_containing(groups, "bazar.bg", "bazar_2"),
        )


if __name__ == "__main__":
    unittest.main()
