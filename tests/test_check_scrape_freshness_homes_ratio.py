"""
Tests for the 2026-09-26 recalibration of check_scrape_freshness.py's
PER_PORTAL_MIN_ACTIVE_RATIO["homes"] floor.

Background (see check_scrape_freshness.py's own inline comment for the
full writeup, and docs/decisions.md's 2026-09-26 entry): the 0.55 floor
set on 2026-09-24 was calibrated against homes.bg's pre-2026-09-23
healthy baseline (91.2%). dd83178 (2026-09-23) fixed a homes.bg
tracking-ID type-collision bug, and the resulting one-time backfill
correction roughly doubled the tracked-record denominator (~74,012 ->
~140,337) while the real-world active-listing count stayed capped by
homes.bg's actual nationwide inventory (~70,253) - so the new
mathematically-expected healthy ratio is ~47-48%, not 91%. Left
uncorrected, the stale 0.55 floor failed every scheduled scrape.yml run
for ~20h+ (#189-193) as a false alarm.

This file covers the ratio-check logic in isolation (so it doesn't
depend on live production data) plus one documentation test against the
real committed data/leads_homes.json.gz, mirroring the pattern already
used in tests/test_evict_stale_history.py and tests/test_gzip_json_storage.py.
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import check_scrape_freshness as csf


# --- The recalibrated constant itself ---------------------------------------

def test_homes_floor_is_recalibrated_down_from_the_stale_0_55():
    # The old 0.55 floor (calibrated against the pre-collision-fix 91.2%
    # baseline) must not silently creep back in - it's what caused the
    # 5-run false-alarm incident this change fixes.
    assert csf.PER_PORTAL_MIN_ACTIVE_RATIO["homes"] == 0.25


def test_other_portals_floors_untouched_by_this_recalibration():
    # Only homes.bg's floor changes in this fix - every other portal's
    # own, separately-calibrated floor must be unaffected.
    assert csf.PER_PORTAL_MIN_ACTIVE_RATIO["imot"] == 0.45
    assert csf.PER_PORTAL_MIN_ACTIVE_RATIO["olx"] == 0.20
    assert csf.PER_PORTAL_MIN_ACTIVE_RATIO["bazar"] == 0.20
    assert csf.PER_PORTAL_MIN_ACTIVE_RATIO["imoti_bg"] == 0.55
    assert csf.PER_PORTAL_MIN_ACTIVE_RATIO["bcpea"] == 0.35


# --- check_leads_active_ratio() against synthetic data ----------------------

def _write_leads(path, total, active_count):
    leads = [{"source_status": "active"} for _ in range(active_count)]
    leads += [{"source_status": "removed"} for _ in range(total - active_count)]
    path.write_text(json.dumps(leads), encoding="utf-8")


def test_new_floor_passes_at_the_real_observed_post_fix_baseline(tmp_path, capsys):
    # The exact band actually observed across runs #189-193 on real
    # committed data: 47.3%-48.0% active. The new floor must not flag it.
    path = tmp_path / "leads_homes.json"
    _write_leads(path, total=140387, active_count=66377)  # 47.3%, the low end
    min_ratio = csf.PER_PORTAL_MIN_ACTIVE_RATIO["homes"]
    assert csf.check_leads_active_ratio(path, min_ratio) is True
    assert "::error::" not in capsys.readouterr().out


def test_new_floor_still_fails_a_genuinely_pathological_ratio(tmp_path, capsys):
    # A real dead/stuck crawl (e.g. something in the 5-10% range, the
    # same shape as alo.bg's real 0.0% incident) must still be caught -
    # the recalibration must not have gutted the guard itself.
    path = tmp_path / "leads_homes.json"
    _write_leads(path, total=140000, active_count=8000)  # ~5.7%
    min_ratio = csf.PER_PORTAL_MIN_ACTIVE_RATIO["homes"]
    assert csf.check_leads_active_ratio(path, min_ratio) is False
    assert "::error::" in capsys.readouterr().out


def test_new_floor_fails_just_below_it_and_passes_just_above_it(tmp_path):
    min_ratio = csf.PER_PORTAL_MIN_ACTIVE_RATIO["homes"]
    below = tmp_path / "leads_below.json"
    _write_leads(below, total=100000, active_count=24999)  # 24.999%
    above = tmp_path / "leads_above.json"
    _write_leads(above, total=100000, active_count=25001)  # 25.001%
    assert csf.check_leads_active_ratio(below, min_ratio) is False
    assert csf.check_leads_active_ratio(above, min_ratio) is True


# --- Documentation test against the real committed data ---------------------

def test_real_committed_homes_data_clears_the_new_floor_with_margin():
    # Mirrors the pattern in tests/test_evict_stale_history.py /
    # tests/test_gzip_json_storage.py: a documentation test against this
    # repo's own real, currently-committed data, so this stays true (and
    # visibly breaks, rather than silently drifting) if that data changes.
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    leads_path = os.path.join(data_dir, "leads_homes.json.gz")
    if not os.path.exists(leads_path):
        import pytest
        pytest.skip("data/leads_homes.json.gz not present in this checkout")
    with gzip.open(leads_path, "rt", encoding="utf-8") as f:
        leads = json.load(f)
    total = len(leads)
    active = sum(1 for l in leads if l.get("source_status") == "active")
    ratio = active / total
    min_ratio = csf.PER_PORTAL_MIN_ACTIVE_RATIO["homes"]
    assert ratio > min_ratio, (
        f"real homes.bg active ratio {ratio:.1%} no longer clears the "
        f"{min_ratio:.0%} floor with margin - re-derive the floor rather "
        f"than assuming this test is wrong"
    )
    # Documents the real, currently-expected band (see the module comment) -
    # a real regression or a genuine new incident should move this outside
    # 40%-55%; a value in that band is the expected post-fix norm, not
    # something to silently accept forever without re-checking.
    assert 0.40 < ratio < 0.55
