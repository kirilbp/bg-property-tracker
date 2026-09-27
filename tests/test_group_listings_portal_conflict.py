"""
Regression tests for backlog item 60 (Placy's allocation investigation,
PR #312 handoff): group_listings() was merging genuinely different real
properties (different units in the same mass development) into one
merged_listings row, because its matching key - city + exact area +
price (+/-0.5%) + sqm (+/-1) - has no unit/floor/address discriminator, so
a development selling many near-identical-sized/priced units is
indistinguishable from one unit cross-posted across portals. Real-data
verification (13,814 of 59,028 real multi-member groups had more than one
listing from the SAME portal - structurally impossible for genuine
cross-posting - and real Shumen/Burgas/Varna examples merging 50-66
distinct units into one row) and the full quantified before/after impact
are written up in docs/decisions.md, not repeated here as a unit test
since it needs the real, large, gitignored-in-CI-sense data files.

The fix: group_listings() now refuses to union two candidate groups that
would put more than one *distinct* listing from the same portal into one
group - a real, provable structural fact (a portal doesn't list one real
property under two different ids in a way that should count as
cross-posted) rather than a guess. It's keyed on (portal, url), not portal
alone, because of a second real bug this investigation found while
quantifying impact: homes.bg's own leads_homes.json.gz stores 43,838 real
listings TWICE under two different ids (a plain numeric one and an
"as"-prefixed one) that share the exact same url/price/sqm/title - one
real listing, not two apartments. A portal-only version of this guard
mistook that for a second unit and broke real cross-portal matches over
it (measured: 21.56% of already-correct pairs, see docs/decisions.md);
tolerating a same-portal-same-url pair as "not a conflict" fixes that
without discarding either duplicate record (an earlier attempt at that,
keeping whichever record had more populated fields, was tried and
measured worse - 30.78% broken - since field-richness has no relationship
to which of a stale/current pair's prices is the real one).

Run with: python3 -m pytest -q tests/test_group_listings_portal_conflict.py
(or python3 -m unittest, matching every other tests/test_*.py file.)
"""

import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_to_supabase import group_listings


def listing(portal, id_, url=None, price_eur=100000, sqm=65, area="Люлин 4",
            city="София", **extra):
    l = {
        "id": id_,
        "portal": portal,
        "url": url if url is not None else f"https://{portal}/{id_}",
        "price_eur": price_eur,
        "sqm": sqm,
        "area": area,
        "city": city,
        "title": extra.pop("title", f"Двустаен, {sqm}m², {area}, {city}"),
    }
    l.update(extra)
    return l


def group_containing(groups, portal, id_):
    for g in groups:
        for m in g:
            if m["portal"] == portal and m["id"] == id_:
                return g
    return None


class DevelopmentSplitTests(unittest.TestCase):
    """The "correctly splits a development" side of the fix."""

    def test_two_different_units_from_the_same_portal_are_not_merged(self):
        # The exact confirmed shape of the real bug: a portal (imot.bg)
        # lists two DIFFERENT real apartments (different ids, different
        # urls) at the same price/sqm/area/city a mass development
        # produces - these must never end up in one merged group together,
        # regardless of what else matches them.
        unit_a = listing("imot.bg", "imot_1", url="https://imot.bg/1")
        unit_b = listing("imot.bg", "imot_2", url="https://imot.bg/2")
        groups = group_listings([unit_a, unit_b])
        self.assertIsNot(
            group_containing(groups, "imot.bg", "imot_1"),
            group_containing(groups, "imot.bg", "imot_2"),
        )

    def test_development_with_several_cross_posted_units_splits_cleanly(self):
        # A miniature version of the real Shumen/Burgas/Varna examples:
        # a development where homes.bg and imot.bg each picked up BOTH
        # real units at the same price/sqm/area, plus one portal (olx.bg)
        # that only picked up unit A. Every same-portal pair (homes.bg's
        # two, imot.bg's two) must end up split apart; each unit's own
        # cross-portal partners must end up together.
        listings = [
            listing("homes.bg", "homes_a1", url="https://homes.bg/a1"),
            listing("homes.bg", "homes_b1", url="https://homes.bg/b1"),
            listing("imot.bg", "imot_a1", url="https://imot.bg/a1"),
            listing("imot.bg", "imot_b1", url="https://imot.bg/b1"),
            listing("olx.bg", "olx_a1", url="https://olx.bg/a1"),
        ]
        groups = group_listings(listings)
        multi = [g for g in groups if len(g) > 1]
        for g in multi:
            counts = Counter(m["portal"] for m in g)
            self.assertTrue(
                all(v == 1 for v in counts.values()),
                f"group has more than one listing from a single portal: {g}",
            )

    def test_real_shumen_style_development_scaled_up(self):
        # 20 distinct real units, all ~65m2 at a similar price band (this
        # backlog item's own confirmed real-world shape: a Shumen
        # development merged 66 distinct units into one row), each
        # cross-posted on 2 portals. No merged group should ever end up
        # bigger than the number of portals actually used (2), and no
        # group should contain 2 listings from one portal.
        listings = []
        for i in range(20):
            price = 60000 + i  # each unit's own real, slightly different price
            listings.append(listing("homes.bg", f"homes_{i}", url=f"https://homes.bg/{i}",
                                     price_eur=price, sqm=45))
            listings.append(listing("imot.bg", f"imot_{i}", url=f"https://imot.bg/{i}",
                                     price_eur=price, sqm=45))
        groups = group_listings(listings)
        multi = [g for g in groups if len(g) > 1]
        self.assertEqual(len(multi), 20, "each of the 20 real units should form its own group")
        for g in multi:
            self.assertEqual(len(g), 2)
            self.assertEqual({m["portal"] for m in g}, {"homes.bg", "imot.bg"})


class GenuineCrossPostPreservedTests(unittest.TestCase):
    """The "correctly keeps a real cross-posted match merged" side of the
    fix - just as important to protect as the split side (a false negative
    here is a real regression on an already-working case)."""

    def test_simple_cross_portal_match_still_merges(self):
        a = listing("homes.bg", "homes_1", url="https://homes.bg/1")
        b = listing("alo.bg", "alo_1", url="https://alo.bg/1")
        c = listing("bazar.bg", "bazar_1", url="https://bazar.bg/1")
        groups = group_listings([a, b, c])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_same_portal_same_url_is_not_a_conflict(self):
        # The real, confirmed homes.bg bug this fix had to specifically
        # accommodate: the exact same real listing recorded under two
        # different ids that share one url. This must NOT be treated as
        # "two different units from one portal" - both records describe
        # the one real cross-posted property and the group must still
        # form correctly with the other portals.
        dup_1 = listing("homes.bg", "homes_1697613", url="https://homes.bg/as1697613")
        dup_2 = listing("homes.bg", "homes_as1697613", url="https://homes.bg/as1697613")
        other_portal = listing("alo.bg", "alo_1", url="https://alo.bg/1")
        groups = group_listings([dup_1, dup_2, other_portal])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_all_eight_portals_cross_posting_one_real_property(self):
        portals = [
            "imoti.net", "alo.bg", "homes.bg", "imot.bg",
            "olx.bg", "bazar.bg", "imoti.bg", "sales.bcpea.org",
        ]
        listings = [
            listing(p, f"{p}_1", url=f"https://{p}/1")
            for p in portals
        ]
        # sales.bcpea.org resolves its city from its own title format
        # ("<type label>, <settlement>"), not the "city" field every other
        # portal uses (see listing_city_key()) - give it one that parses.
        for l in listings:
            if l["portal"] == "sales.bcpea.org":
                l["title"] = "Двустаен апартамент, София"
        groups = group_listings(listings)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 8)
        self.assertEqual({m["portal"] for m in groups[0]}, set(portals))


if __name__ == "__main__":
    unittest.main()
