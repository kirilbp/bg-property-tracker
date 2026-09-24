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

scraper_imoti_bg.py has the identical `update_history()` bug shape but was
missed by that original fix - it wasn't part of the "all six scrapers with
this function" investigation, even though it genuinely has the same
function. Its own exposure is slightly different in mechanism (it calls
its best-effort fetch_listing_detail() inline for every listing on every
run rather than as a separate backfill pass, so a single transient
per-run failure there - not just a grid-only re-touch - can also produce
the None that gets wiped in), but the fix and the field-preservation
behavior being tested are the same.

This test proves, for each of these seven scrapers, that a grid-only
re-touch (or, for imoti.bg, a simulated transient detail-fetch failure)
of a listing that already has those detail fields no longer clears them -
the actual bug this fixes - while still confirming fresh data (price,
and for imoti.bg a successful description/site_posted_at re-fetch) really
does get applied, so the fix is a merge, not an accidental freeze.

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
import scraper_imoti_bg
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
            "photos": ["https://sales.bcpea.org/1.jpg", "https://sales.bcpea.org/1b.jpg"],
            "detail_checked": True,
            "lat": 42.68, "lng": 23.31,
        }
        # Grid crawl on its own: area is settlement-only (no district),
        # lat/lng are always the None placeholder (real coords only ever
        # come from the detail pass), photo is None whenever this run's
        # card image happened to be the shared placeholder graphic (see
        # fetch_listings_page(): "photo-placeholder.png" -> photo=None) -
        # simulated here rather than a real thumbnail, to exercise exactly
        # the case this test guards against - and photos is never set at
        # all by the grid crawl (extract_photos_bcpea() only ever runs
        # from a detail visit, see _DETAIL_ONLY_FIELDS' own comment).
        fresh_grid = {
            "id": "bcpea_1", "url": "https://sales.bcpea.org/1", "photo": None,
            "sqm": 70, "area": "Sofia", "title": "Apartment, Sofia",
            "portal": "sales.bcpea.org", "site_updated_at": "2026-09-20T00:00:00+00:00",
            "category": "apartment", "_settlement": "Sofia",
            "lat": None, "lng": None,
        }
        latest = self._assert_preserved_and_updated(
            scraper_bcpea, "bcpea_1", prior_latest, fresh_grid,
            ["description", "detail_checked", "lat", "lng", "photo", "photos"], new_price=45000,
        )
        # Documented, deliberate scope boundary (see scraper_bcpea.py's own
        # comment above _DETAIL_ONLY_FIELDS): "area" is NOT preserved since
        # the grid always supplies a real, non-empty value for it (just a
        # less detailed one before a detail visit) - confirm that's still
        # true post-fix, i.e. the grid's fresh value really does win here.
        self.assertEqual(latest["area"], "Sofia")

    def test_scraper_bcpea_grid_real_photo_still_updates(self):
        # The fix must be a merge, not a freeze: once the grid crawl finds
        # a genuine (non-placeholder) card image on a later run, it should
        # still overwrite the previously detail-backfilled photo - "photo"
        # must not become permanently sticky just because it's now in
        # _DETAIL_ONLY_FIELDS.
        prior_latest = {
            "id": "bcpea_2", "url": "https://sales.bcpea.org/2", "photo": "https://sales.bcpea.org/2-detail.jpg",
            "price_eur": 30000, "sqm": 55, "area": "Sofia, Lozenets", "title": "Apartment, Sofia",
            "portal": "sales.bcpea.org", "site_updated_at": "2026-08-01T00:00:00+00:00",
            "category": "apartment", "_settlement": "Sofia",
            "description": "Cadastral identifier 68134.4082.32, real legal description text.",
            "detail_checked": True,
            "lat": 42.68, "lng": 23.31,
        }
        fresh_grid = {
            "id": "bcpea_2", "url": "https://sales.bcpea.org/2", "photo": "https://sales.bcpea.org/2-grid-new.jpg",
            "sqm": 55, "area": "Sofia", "title": "Apartment, Sofia",
            "portal": "sales.bcpea.org", "site_updated_at": "2026-09-20T00:00:00+00:00",
            "category": "apartment", "_settlement": "Sofia",
            "lat": None, "lng": None,
        }
        latest = self._assert_preserved_and_updated(
            scraper_bcpea, "bcpea_2", prior_latest, fresh_grid,
            ["description", "detail_checked", "lat", "lng"], new_price=28000,
        )
        self.assertEqual(latest["photo"], "https://sales.bcpea.org/2-grid-new.jpg")

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

    # -- alo.bg specs/contact fields (2026-09-24) --------------------------
    def test_scraper_alo_preserves_detail_specs_and_contact_and_sqm(self):
        # Same shape as test_scraper_alo_preserves_detail_fields above, but
        # for the new fields wired in from geo_utils.extract_specs_alo()/
        # extract_contact_alo() - see scraper_alo.py's _DETAIL_ONLY_FIELDS
        # comment on why "sqm" specifically needed to join this list once
        # fetch_update_dates() could also populate it (previously a
        # grid-only field, sqm before this fix would be silently wiped by
        # a grid re-touch that (as usual - see docs/backlog.md) found no
        # "Квадратура:" text on the card).
        prior_latest = {
            "id": "alo_2", "url": "https://alo.bg/2", "photo": "https://alo.bg/2.jpg",
            "price_eur": 110000, "sqm": 57, "area": "Zona B19", "city": "Sofia",
            "title": "Atelier", "portal": "alo.bg", "category": "apartment",
            "category_confidence": "high",
            "property_type_raw": "Ателие/Студио", "construction_type": "ЕПК/ПК",
            "built_year": 1980, "completion_status": "Готов (завършен)",
            "floor_number": 12, "floor_qualifier": "Непоследен",
            "features": ["Асансьор", "Необзаведен", "ТЕЦ"],
            "has_elevator": True, "furnished": False, "has_central_heating": True,
            "agency_name": "ENDREVA HAUSES", "agency_website": "https://endreva-houses.com",
            "_detail_fetched": True, "_photos_checked": True,
        }
        # alo's grid parser (fetch_listings_page()) never sets any of the
        # new spec/contact fields, and here (the overwhelming majority
        # case - ~99% of real listings per docs/backlog.md) also doesn't
        # find "Квадратура:" text on the card, so sqm comes back None too.
        fresh_grid = {
            "id": "alo_2", "url": "https://alo.bg/2", "photo": "https://alo.bg/2.jpg",
            "sqm": None, "area": "Zona B19", "city": "Sofia", "title": "Atelier",
            "portal": "alo.bg", "category": "apartment", "category_confidence": "high",
        }
        latest = self._assert_preserved_and_updated(
            scraper_alo, "alo_2", prior_latest, fresh_grid,
            ["sqm", "property_type_raw", "construction_type", "built_year", "completion_status",
             "floor_number", "floor_qualifier", "features", "has_elevator", "furnished",
             "has_central_heating", "agency_name", "agency_website"],
            new_price=108000,
        )
        # furnished=False is a real, meaningful value (not "missing") -
        # confirm it survives the merge as False, not accidentally coerced
        # to None/dropped by the "is this falsy" check update_history()
        # uses to decide whether to restore the prior value.
        self.assertIs(latest["furnished"], False)

    def test_scraper_alo_grid_sqm_still_overwrites_detail_sqm_when_present(self):
        # The fix must be a merge, not a freeze: if a later grid crawl DOES
        # find real "Квадратура:" text on the card (a genuine edit, or a
        # card layout that happens to include it), that fresh value must
        # still win over whatever fetch_update_dates() previously filled
        # in - sqm must not become permanently sticky just because it's
        # now in _DETAIL_ONLY_FIELDS.
        prior_latest = {
            "id": "alo_3", "url": "https://alo.bg/3", "photo": "https://alo.bg/3.jpg",
            "price_eur": 90000, "sqm": 57, "area": "Center", "city": "Sofia",
            "title": "Studio", "portal": "alo.bg", "category": "apartment",
            "category_confidence": "high", "_detail_fetched": True, "_photos_checked": True,
        }
        fresh_grid = {
            "id": "alo_3", "url": "https://alo.bg/3", "photo": "https://alo.bg/3.jpg",
            "sqm": 60, "area": "Center", "city": "Sofia", "title": "Studio",
            "portal": "alo.bg", "category": "apartment", "category_confidence": "high",
        }
        history = self._make_history("alo_3", prior_latest)
        fresh = copy.deepcopy(fresh_grid)
        fresh["price_eur"] = 88000
        result = scraper_alo.update_history(history, [fresh])
        self.assertEqual(result["alo_3"]["latest"]["sqm"], 60)

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

    # -- imoti.bg -----------------------------------------------------------
    # Unlike the other five portals above, imoti.bg's fetch_listings() calls
    # fetch_listing_detail(l["url"]) inline for EVERY listing on EVERY run
    # (not a separate, one-time backfill pass) and writes its two results
    # (description, site_posted_at) onto the fresh record unconditionally.
    # fetch_listing_detail()'s own docstring says it's best-effort and
    # "never raises... a missing description/date shouldn't drop a
    # listing", so a single transient per-run failure (timeout, a missing
    # meta tag that day, a page render hiccup) legitimately produces
    # (None, None) for a listing that had a real description/
    # site_posted_at on a previous run - update_history() must not let that
    # wipe the previously-captured values.
    def test_scraper_imoti_bg_preserves_detail_fields_on_transient_failure(self):
        prior_latest = {
            "id": "imotibg_1", "url": "https://imoti.bg/1", "photo": "https://imoti.bg/1.jpg",
            "price_eur": 90000, "sqm": 72, "area": "Center", "city": "Пловдив",
            "title": "Тристаен апартамент, Center", "portal": "imoti.bg",
            "lat": 42.14, "lng": 24.75, "category": "apartment", "category_confidence": "high",
            "description": "Реален текст на обявата, взет от детайлната страница.",
            "site_posted_at": "2026-08-20T00:00:00+00:00",
        }
        # Simulates fetch_listing_detail() hitting a transient failure this
        # run: fetch_listings() still calls it unconditionally and writes
        # whatever it returns - (None, None) here - straight onto the fresh
        # record, exactly as fetch_listings() itself does.
        fresh_grid = {
            "id": "imotibg_1", "url": "https://imoti.bg/1", "photo": "https://imoti.bg/1.jpg",
            "sqm": 72, "area": "Center", "city": "Пловдив", "title": "Тристаен апартамент, Center",
            "portal": "imoti.bg", "lat": 42.14, "lng": 24.75,
            "category": "apartment", "category_confidence": "high",
            "description": None, "site_posted_at": None,
        }
        self._assert_preserved_and_updated(
            scraper_imoti_bg, "imotibg_1", prior_latest, fresh_grid,
            ["description", "site_posted_at"], new_price=87000,
        )

    def test_scraper_imoti_bg_updates_detail_fields_on_successful_refetch(self):
        # The fix must be a merge, not a freeze: when fetch_listing_detail()
        # DOES succeed and returns new, real values, those must still take
        # effect rather than description/site_posted_at becoming
        # permanently sticky once set.
        prior_latest = {
            "id": "imotibg_2", "url": "https://imoti.bg/2", "photo": "https://imoti.bg/2.jpg",
            "price_eur": 55000, "sqm": 48, "area": "Lozenets", "city": "София",
            "title": "Двустаен апартамент, Lozenets", "portal": "imoti.bg",
            "lat": 42.68, "lng": 23.32, "category": "apartment", "category_confidence": "high",
            "description": "Стар текст на обявата.",
            "site_posted_at": "2026-06-01T00:00:00+00:00",
        }
        fresh_grid = {
            "id": "imotibg_2", "url": "https://imoti.bg/2", "photo": "https://imoti.bg/2.jpg",
            "sqm": 48, "area": "Lozenets", "city": "София", "title": "Двустаен апартамент, Lozenets",
            "portal": "imoti.bg", "lat": 42.68, "lng": 23.32,
            "category": "apartment", "category_confidence": "high",
            "description": "Нов, обновен текст на обявата от детайлната страница.",
            "site_posted_at": "2026-09-20T00:00:00+00:00",
        }
        history = self._make_history("imotibg_2", prior_latest)
        fresh = copy.deepcopy(fresh_grid)
        fresh["price_eur"] = 53000
        result = scraper_imoti_bg.update_history(history, [fresh])
        latest = result["imotibg_2"]["latest"]
        self.assertEqual(latest["description"], fresh_grid["description"])
        self.assertEqual(latest["site_posted_at"], fresh_grid["site_posted_at"])
        self.assertEqual(latest["price_eur"], 53000)

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
