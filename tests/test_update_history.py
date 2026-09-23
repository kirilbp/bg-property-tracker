"""
Regression test for docs/backlog.md item 9a.

update_history() in scraper_imot.py, scraper_olx.py, scraper_bcpea.py,
scraper_alo.py, scraper_bazar.py, and scraper.py (imoti.net) used to do
    history[lid]["latest"] = l
unconditionally, where `l` is that run's fresh GRID-crawl-only record.
scrape.yml re-touches every still-active listing every ~6 hours, so this
silently wiped out already-backfilled detail-page-only fields
(description, photos, detail_checked, and portal-specific equivalents)
on every single run for every still-active listing.

This test proves, for each of the six scrapers, that a grid-only
re-touch of a listing that already has those detail fields no longer
clears them - the actual bug this fixes - while still confirming the
grid's own fresh fields (price, etc.) really do get applied, so the fix
is a merge, not an accidental freeze.

Run with: python3 -m unittest tests.test_update_history -v
(no pytest / other test framework is installed in this repo - see the
commit this test shipped in for that check).
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper as scraper_imoti_net  # imoti.net
import scraper_alo
import scraper_bazar
import scraper_bcpea
import scraper_imot
import scraper_olx


def _buggy_update_history(history, listings):
    """The original, unfixed shape of update_history() - `history[lid]
    ["latest"] = l` unconditionally. Used below only to prove this test
    actually discriminates the bug (i.e. it isn't vacuously true), by
    running the exact same case against it and asserting it DOES lose
    the detail fields.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    for l in listings:
        lid = l["id"]
        if lid not in history:
            history[lid] = {"first_seen": now, "snapshots": []}
        history[lid]["snapshots"].append({"seen_at": now, "price_eur": l["price_eur"]})
        history[lid]["latest"] = l
    return history


class UpdateHistoryDetailPreservationTest(unittest.TestCase):
    def _make_history(self, lid, prior_latest):
        return {
            lid: {
                "first_seen": "2026-09-01T00:00:00+00:00",
                "snapshots": [
                    {"seen_at": "2026-09-01T00:00:00+00:00", "price_eur": prior_latest["price_eur"]}
                ],
                "latest": copy.deepcopy(prior_latest),
            }
        }

    def _assert_preserved_and_updated(self, module, lid, prior_latest, fresh_grid_record,
                                       preserved_fields, new_price):
        history = self._make_history(lid, prior_latest)
        fresh = copy.deepcopy(fresh_grid_record)
        fresh["price_eur"] = new_price

        result = module.update_history(history, [fresh])
        latest = result[lid]["latest"]

        for field in preserved_fields:
            self.assertEqual(
                latest.get(field),
                prior_latest.get(field),
                f"{module.__name__}.update_history() wiped detail-page field {field!r} "
                f"on a grid-only re-touch (got {latest.get(field)!r}, "
                f"expected preserved {prior_latest.get(field)!r})",
            )

        # The fix is a MERGE, not a freeze - fresh grid data (price here)
        # must still actually take effect, and a new snapshot must still
        # be appended, exactly as before the fix.
        self.assertEqual(latest["price_eur"], new_price)
        self.assertEqual(len(result[lid]["snapshots"]), 2)
        self.assertEqual(result[lid]["snapshots"][-1]["price_eur"], new_price)
        return latest

    # -- imot.bg --------------------------------------------------------
    def test_scraper_imot_preserves_detail_fields(self):
        prior_latest = {
            "id": "imot_1", "url": "https://imot.bg/1", "photo": "https://imot.bg/1.jpg",
            "price_eur": 100000, "sqm": 80, "area": "Center", "city": "Sofia",
            "title": "Apartment", "portal": "imot.bg", "lat": 42.6, "lng": 23.3,
            "category": "apartment",
            "description": "A real 3-bedroom apartment with a nice view, near the metro.",
            "photos": ["https://imot.bg/1_1.jpg", "https://imot.bg/1_2.jpg"],
            "detail_checked": True,
        }
        fresh_grid = {
            "id": "imot_1", "url": "https://imot.bg/1", "photo": "https://imot.bg/1.jpg",
            "sqm": 80, "area": "Center", "city": "Sofia", "title": "Apartment",
            "portal": "imot.bg", "lat": 42.6, "lng": 23.3, "category": "apartment",
        }
        self._assert_preserved_and_updated(
            scraper_imot, "imot_1", prior_latest, fresh_grid,
            ["description", "photos", "detail_checked"], new_price=95000,
        )

    # -- olx.bg -----------------------------------------------------------
    def test_scraper_olx_preserves_detail_fields(self):
        prior_latest = {
            "id": "olx_1", "url": "https://olx.bg/1", "photo": "https://olx.bg/1.jpg",
            "price_eur": 80000, "sqm": 60, "area": "Mladost", "city": "Sofia",
            "title": "Studio", "portal": "olx.bg", "site_updated_at": "2026-08-01T00:00:00+00:00",
            "lat": 42.65, "lng": 23.38, "category": "apartment",
            "description": "Bright studio, recently renovated, close to shops.",
            "photos": ["https://olx.bg/1_1.jpg"],
            "detail_checked": True,
        }
        fresh_grid = {
            "id": "olx_1", "url": "https://olx.bg/1", "photo": "https://olx.bg/1.jpg",
            "sqm": 60, "area": "Mladost", "city": "Sofia", "title": "Studio",
            "portal": "olx.bg", "site_updated_at": "2026-09-20T00:00:00+00:00",
            "lat": 42.65, "lng": 23.38, "category": "apartment",
        }
        self._assert_preserved_and_updated(
            scraper_olx, "olx_1", prior_latest, fresh_grid,
            ["description", "photos", "detail_checked"], new_price=78000,
        )

    # -- sales.bcpea.org --------------------------------------------------
    def test_scraper_bcpea_preserves_detail_fields(self):
        prior_latest = {
            "id": "bcpea_1", "url": "https://sales.bcpea.org/1", "photo": "https://sales.bcpea.org/1.jpg",
            "price_eur": 50000, "sqm": 70, "area": "Sofia, Lozenets", "title": "Apartment, Sofia",
            "portal": "sales.bcpea.org", "site_updated_at": "2026-08-01T00:00:00+00:00",
            "category": "apartment", "_settlement": "Sofia",
            "description": "Cadastral identifier 68134.4082.31, real legal description text.",
            "detail_checked": True,
            "lat": 42.68, "lng": 23.31,
        }
        # Grid crawl on its own: area is settlement-only (no district), photo
        # is whatever thumbnail it found this run, lat/lng are always the
        # None placeholder (real coords only ever come from the detail pass).
        fresh_grid = {
            "id": "bcpea_1", "url": "https://sales.bcpea.org/1", "photo": "https://sales.bcpea.org/1.jpg",
            "sqm": 70, "area": "Sofia", "title": "Apartment, Sofia",
            "portal": "sales.bcpea.org", "site_updated_at": "2026-09-20T00:00:00+00:00",
            "category": "apartment", "_settlement": "Sofia",
            "lat": None, "lng": None,
        }
        latest = self._assert_preserved_and_updated(
            scraper_bcpea, "bcpea_1", prior_latest, fresh_grid,
            ["description", "detail_checked", "lat", "lng"], new_price=45000,
        )
        # Documented, deliberate scope boundary (see scraper_bcpea.py's own
        # comment above _DETAIL_ONLY_FIELDS): "area" is NOT preserved since
        # the grid always supplies a real, non-empty value for it (just a
        # less detailed one before a detail visit) - confirm that's still
        # true post-fix, i.e. the grid's fresh value really does win here.
        self.assertEqual(latest["area"], "Sofia")

    # -- alo.bg -------------------------------------------------------------
    def test_scraper_alo_preserves_detail_fields(self):
        prior_latest = {
            "id": "alo_1", "url": "https://alo.bg/1", "photo": "https://alo.bg/1.jpg",
            "price_eur": 60000, "sqm": 55, "area": "Center", "city": "Plovdiv",
            "title": "2-bedroom apartment", "portal": "alo.bg", "category": "apartment",
            "category_confidence": "high",
            "description": "Real free text description scraped from the detail page.",
            "photos": ["https://alo.bg/1_1.jpg", "https://alo.bg/1_2.jpg"],
            "site_updated_at": "2026-09-10T00:00:00+00:00",
            "lat": 42.14, "lng": 24.75,
            "_detail_fetched": True, "_photos_checked": True,
        }
        # alo's grid parser (fetch_listings_page()) never sets these keys
        # at all - confirmed by reading the parser directly.
        fresh_grid = {
            "id": "alo_1", "url": "https://alo.bg/1", "photo": "https://alo.bg/1.jpg",
            "sqm": 55, "area": "Center", "city": "Plovdiv", "title": "2-bedroom apartment",
            "portal": "alo.bg", "category": "apartment", "category_confidence": "high",
        }
        self._assert_preserved_and_updated(
            scraper_alo, "alo_1", prior_latest, fresh_grid,
            ["description", "photos", "site_updated_at", "lat", "lng",
             "_detail_fetched", "_photos_checked"],
            new_price=58000,
        )

    # -- bazar.bg -------------------------------------------------------
    def test_scraper_bazar_preserves_detail_fields(self):
        prior_latest = {
            "id": "bazar_1", "url": "https://bazar.bg/1", "photo": "https://bazar.bg/1.jpg",
            "price_eur": 40000, "sqm": None, "area": "Varna", "city": "Varna",
            "title": "House for sale", "portal": "bazar.bg", "category": "house",
            "description": "Real listing description from the ld+json block.",
            "photos": ["https://bazar.bg/1_1.jpg"],
            "coords_checked": True,
            "lat": 43.21, "lng": 27.91,
        }
        # bazar's grid parser always sets lat/lng to the None placeholder.
        fresh_grid = {
            "id": "bazar_1", "url": "https://bazar.bg/1", "photo": "https://bazar.bg/1.jpg",
            "sqm": None, "area": "Varna", "city": "Varna", "title": "House for sale",
            "portal": "bazar.bg", "lat": None, "lng": None, "category": "house",
        }
        self._assert_preserved_and_updated(
            scraper_bazar, "bazar_1", prior_latest, fresh_grid,
            ["description", "photos", "coords_checked", "lat", "lng"], new_price=39000,
        )

    # -- imoti.net --------------------------------------------------------
    def test_scraper_imoti_net_preserves_detail_fields(self):
        prior_latest = {
            "id": "imoti_net_1", "url": "https://imoti.net/1", "photo": "https://imoti.net/1.jpg",
            "price_eur": 70000, "sqm": 65, "area": "Center", "city": "Burgas",
            "title": "Apartment", "portal": "imoti.net", "category": "apartment",
            "category_confidence": "high",
            "site_posted_at": "2026-08-15T00:00:00+00:00",
            "lat": 42.5, "lng": 27.47,
            "photos": ["https://imoti.net/1_1.jpg"],
            "detail_checked": True,
        }
        fresh_grid = {
            "id": "imoti_net_1", "url": "https://imoti.net/1", "photo": "https://imoti.net/1.jpg",
            "sqm": 65, "area": "Center", "city": "Burgas", "title": "Apartment",
            "portal": "imoti.net", "category": "apartment", "category_confidence": "high",
        }
        self._assert_preserved_and_updated(
            scraper_imoti_net, "imoti_net_1", prior_latest, fresh_grid,
            ["site_posted_at", "lat", "lng", "photos", "detail_checked"], new_price=68000,
        )

    # -- new listing (no prior history) still works normally --------------
    def test_new_listing_with_no_prior_history_is_unaffected(self):
        fresh_grid = {
            "id": "imot_new", "url": "https://imot.bg/new", "photo": None,
            "price_eur": 100000, "sqm": 50, "area": "Center", "city": "Sofia",
            "title": "New listing", "portal": "imot.bg", "lat": None, "lng": None,
            "category": "apartment",
        }
        history = {}
        result = scraper_imot.update_history(history, [fresh_grid])
        latest = result["imot_new"]["latest"]
        self.assertEqual(latest["price_eur"], 100000)
        self.assertNotIn("description", latest)
        self.assertNotIn("photos", latest)
        self.assertNotIn("detail_checked", latest)
        self.assertEqual(len(result["imot_new"]["snapshots"]), 1)


class BuggyUpdateHistoryReallyDoesLoseData(unittest.TestCase):
    """Sanity check that this test suite actually discriminates the bug:
    running the exact same imot.bg case through the ORIGINAL, unfixed
    `history[lid]["latest"] = l` shape must lose the detail fields - proving
    the assertions above aren't vacuously true regardless of whether the
    fix is in place.
    """

    def test_original_shape_wipes_detail_fields(self):
        prior_latest = {
            "id": "imot_1", "price_eur": 100000, "sqm": 80, "area": "Center",
            "description": "A real description.", "photos": ["https://imot.bg/1_1.jpg"],
            "detail_checked": True,
        }
        history = {
            "imot_1": {
                "first_seen": "2026-09-01T00:00:00+00:00",
                "snapshots": [{"seen_at": "2026-09-01T00:00:00+00:00", "price_eur": 100000}],
                "latest": copy.deepcopy(prior_latest),
            }
        }
        fresh_grid = {"id": "imot_1", "price_eur": 95000, "sqm": 80, "area": "Center"}
        result = _buggy_update_history(history, [fresh_grid])
        latest = result["imot_1"]["latest"]
        self.assertNotIn("description", latest)
        self.assertNotIn("photos", latest)
        self.assertNotIn("detail_checked", latest)


if __name__ == "__main__":
    unittest.main(verbosity=2)
