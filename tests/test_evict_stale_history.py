"""
Tests for the 2026-09-25 scrape.yml GH001 fix: unbounded growth of
history_*.json/leads_*.json from never removing records for listings that
have been gone (sold/delisted) for a long time - see geo_utils.py's own
STALE_RECORD_RETENTION comment for the real measurements (record count,
not per-record payload or snapshot bloat, is the dominant size driver;
homes.bg alone has 74,012 tracked records with zero ever evicted) and the
180-day retention window's justification (calibrated from 261 real
"relisted_from" pairs already recorded across every portal: 0.2-31.7 day
gap, median 10.7, 96% within 30 days).

Covers three layers:
  1. geo_utils.evict_stale_records() as a standalone unit.
  2. Its wiring into a scraper's own save_history() (using scraper_homes.py
     and scraper_alo.py as representative - one from scrape.yml's 6
     GH001-blocked portals, one from the separately-flagged near-the-wall
     alo.bg), confirming the eviction is visible both in the rewritten
     history file AND in that same run's own compute_leads() output.
  3. evict_stale_history.py, the standalone one-off/on-demand migration -
     against synthetic data engineered to actually be old enough to evict
     (unlike this repo's own real committed data, which - as measured
     directly - is only ~35 days old and has nothing past the 180-day
     cutoff yet; see this module's own real-data measurement test below).

Run with: python3 -m pytest tests/test_evict_stale_history.py -v
"""
import copy
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geo_utils
from geo_utils import evict_stale_records, STALE_RECORD_RETENTION, load_json_any, save_json_any
import scraper_homes
import scraper_alo
import evict_stale_history


NOW = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)


def _rec(seen_at, first_seen=None, **extra_latest):
    return {
        "first_seen": first_seen or seen_at,
        "snapshots": [{"seen_at": seen_at, "price_eur": 100000}],
        "latest": {"id": "x", "price_eur": 100000, "photo": "https://x/1.jpg", **extra_latest},
    }


# --- geo_utils.evict_stale_records() --------------------------------------

def test_default_retention_is_180_days():
    assert STALE_RECORD_RETENTION == timedelta(days=180)


def test_evicts_records_older_than_retention():
    old_ts = (NOW - timedelta(days=181)).isoformat()
    recent_ts = (NOW - timedelta(days=179)).isoformat()
    history = {
        "gone_old": _rec(old_ts),
        "gone_recent": _rec(recent_ts),
    }
    evicted = evict_stale_records(history, now=NOW)
    assert evicted == 1
    assert "gone_old" not in history
    assert "gone_recent" in history


def test_keeps_active_and_recently_removed_records():
    # Simulates the current real-world shape of this repo's own committed
    # data (measured directly): everything tracked so far is well inside
    # the retention window, including listings currently reading as
    # "removed" only because of a commit-pipeline outage (this incident's
    # own root symptom), not genuinely gone.
    history = {
        "active": _rec(NOW.isoformat()),
        "removed_2_days": _rec((NOW - timedelta(days=2)).isoformat()),
        "removed_34_days": _rec((NOW - timedelta(days=34)).isoformat()),
    }
    evicted = evict_stale_records(history, now=NOW)
    assert evicted == 0
    assert set(history) == {"active", "removed_2_days", "removed_34_days"}


def test_boundary_exactly_at_retention_is_not_evicted():
    ts = (NOW - STALE_RECORD_RETENTION).isoformat()
    history = {"boundary": _rec(ts)}
    evicted = evict_stale_records(history, now=NOW)
    assert evicted == 0
    assert "boundary" in history


def test_boundary_one_second_past_retention_is_evicted():
    ts = (NOW - STALE_RECORD_RETENTION - timedelta(seconds=1)).isoformat()
    history = {"boundary": _rec(ts)}
    evicted = evict_stale_records(history, now=NOW)
    assert evicted == 1
    assert "boundary" not in history


def test_records_with_no_snapshots_are_skipped_not_crashed():
    history = {"empty": {"first_seen": NOW.isoformat(), "snapshots": [], "latest": {}}}
    evicted = evict_stale_records(history, now=NOW)
    assert evicted == 0
    assert "empty" in history


def test_custom_retention_override():
    ts = (NOW - timedelta(days=10)).isoformat()
    history = {"gone_10d": _rec(ts)}
    evicted = evict_stale_records(history, retention=timedelta(days=7), now=NOW)
    assert evicted == 1


def test_eviction_uses_last_snapshot_not_first_seen():
    # A long-lived listing (first_seen far in the past) that is STILL
    # being actively re-scraped (last snapshot recent) must never be
    # evicted - eviction is about "not seen recently", not "old".
    history = {
        "long_lived_active": _rec(NOW.isoformat(), first_seen=(NOW - timedelta(days=300)).isoformat()),
    }
    evicted = evict_stale_records(history, now=NOW)
    assert evicted == 0
    assert "long_lived_active" in history


# --- Real committed data measurement (documents the honest finding that --
# --- eviction alone gives zero size relief on TODAY's actual files) ------

def test_real_committed_homes_data_has_nothing_old_enough_to_evict_yet():
    # This is a documentation test, not a correctness test: it records,
    # against this repo's real currently-committed data/history_homes.json,
    # that the 180-day retention evicts nothing right now - the dataset
    # has only been tracking listings since 2026-08-21 (~35 days as of
    # this writing), so nothing has crossed 180 days gone yet. The real,
    # immediate fix for TODAY's specific push failure is therefore the
    # ongoing per-run mechanism converging future growth, not this
    # migration reclaiming space that doesn't exist yet - see this repo's
    # PR description/incident report for the full reasoning. Skipped
    # gracefully if the real data file isn't present in this checkout.
    # .json.gz, not plain .json - 2026-09-25 addendum to this same
    # incident (see geo_utils.py's "Compressed on-disk JSON storage"
    # comment): homes.bg's own committed file is now gzip-compressed.
    path = Path(__file__).parent.parent / "data" / "history_homes.json.gz"
    if not path.exists():
        import pytest
        pytest.skip("data/history_homes.json.gz not present in this checkout")
    history = load_json_any(path)
    copy_for_eviction = copy.deepcopy(history)
    evicted = evict_stale_records(copy_for_eviction, now=datetime(2026, 9, 25, tzinfo=timezone.utc))
    assert evicted == 0
    assert len(copy_for_eviction) == len(history)


# --- Wired into a scraper's own save_history() -----------------------------

def test_scraper_homes_save_history_evicts_and_leads_reflect_it(tmp_path, monkeypatch):
    # .json.gz, not plain .json - real production paths since the
    # 2026-09-25 addendum (see geo_utils.py's "Compressed on-disk JSON
    # storage" comment), so this exercises the actual gzip write/read path,
    # not just the eviction logic in isolation.
    history_file = tmp_path / "history_homes.json.gz"
    leads_file = tmp_path / "leads_homes.json.gz"
    monkeypatch.setattr(scraper_homes, "HISTORY_FILE", history_file)
    monkeypatch.setattr(scraper_homes, "LEADS_FILE", leads_file)

    old_ts = (NOW - timedelta(days=200)).isoformat()
    recent_ts = (NOW - timedelta(days=5)).isoformat()
    history = {
        "homes_long_gone": {
            "first_seen": old_ts, "snapshots": [{"seen_at": old_ts, "price_eur": 100000}],
            "latest": {
                "id": "homes_long_gone", "price_eur": 100000, "sqm": 50, "area": "Center",
                "city": "Sofia", "title": "Old", "portal": "homes.bg", "photo": None, "photos": [],
                "category": "apartment",
            },
        },
        "homes_still_around": {
            "first_seen": recent_ts, "snapshots": [{"seen_at": recent_ts, "price_eur": 90000}],
            "latest": {
                "id": "homes_still_around", "price_eur": 90000, "sqm": 60, "area": "Center",
                "city": "Sofia", "title": "Recent", "portal": "homes.bg", "photo": None, "photos": [],
                "category": "apartment",
            },
        },
    }

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(geo_utils, "datetime", _FrozenDatetime)

    scraper_homes.save_history(history)

    # in-memory `history` (same object save_history() mutated) already has
    # the stale record gone, so a compute_leads() call right after - the
    # exact shape every scraper's own main() uses - excludes it too.
    assert "homes_long_gone" not in history
    assert "homes_still_around" in history
    leads = scraper_homes.compute_leads(history)
    leads_ids = {l["id"] for l in leads}
    assert "homes_long_gone" not in leads_ids
    assert "homes_still_around" in leads_ids

    on_disk = load_json_any(history_file)
    assert "homes_long_gone" not in on_disk
    assert "homes_still_around" in on_disk


def test_scraper_alo_save_history_also_wired(tmp_path, monkeypatch):
    # alo.bg was separately flagged (measured at ~96-98% of GitHub's 100MB
    # push limit against this repo's real committed data.json files) - the
    # same mechanism is wired into its save_history() too, not just the 6
    # portals scrape.yml itself commits.
    history_file = tmp_path / "history_alo.json"
    monkeypatch.setattr(scraper_alo, "HISTORY_FILE", history_file)

    old_ts = (NOW - timedelta(days=181)).isoformat()
    history = {
        "alo_gone": {
            "first_seen": old_ts, "snapshots": [{"seen_at": old_ts, "price_eur": 50000}],
            "latest": {"id": "alo_gone", "price_eur": 50000, "photo": None},
        },
    }

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(geo_utils, "datetime", _FrozenDatetime)
    scraper_alo.save_history(history)
    assert "alo_gone" not in history


# --- evict_stale_history.py (standalone migration script) -----------------

def _write_synthetic_portal(tmp_data_dir, history_fn, leads_fn, n_old=50, n_recent=20):
    old_ts = (NOW - timedelta(days=200)).isoformat()
    recent_ts = (NOW - timedelta(days=3)).isoformat()
    history = {}
    leads = []
    # Old, genuinely-gone records - bulked up with a "photos" array to
    # mirror this repo's own real finding (photos is ~42% of a real
    # leads_homes.json's bytes) so the size-before/after numbers this
    # script reports are representative, not misleadingly tiny.
    padding_photos = [f"https://cdn.example.com/photo_{j}.jpg" for j in range(8)]
    for i in range(n_old):
        lid = f"old_{i}"
        history[lid] = {
            "first_seen": old_ts,
            "snapshots": [{"seen_at": old_ts, "price_eur": 100000}],
            "latest": {"id": lid, "price_eur": 100000, "photos": padding_photos, "photo": padding_photos[0]},
        }
        leads.append({"id": lid, "price_eur": 100000, "photos": padding_photos, "source_status": "removed"})
    for i in range(n_recent):
        lid = f"recent_{i}"
        history[lid] = {
            "first_seen": recent_ts,
            "snapshots": [{"seen_at": recent_ts, "price_eur": 90000}],
            "latest": {"id": lid, "price_eur": 90000, "photos": padding_photos, "photo": padding_photos[0]},
        }
        leads.append({"id": lid, "price_eur": 90000, "photos": padding_photos, "source_status": "active"})

    # save_json_any() is extension-aware (gzip for .json.gz, plain
    # pretty-printed otherwise) - callers pass whichever filename matches
    # the real portal's own PORTAL_FILES entry, so this transparently
    # covers both formats.
    save_json_any(tmp_data_dir / history_fn, history)
    save_json_any(tmp_data_dir / leads_fn, leads)
    return history, leads


def test_migrate_portal_evicts_old_and_keeps_recent(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(evict_stale_history, "DATA_DIR", data_dir)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(geo_utils, "datetime", _FrozenDatetime)

    # .json.gz, not plain .json - matches the real PORTAL_FILES["homes"]
    # entry (2026-09-25 addendum, see geo_utils.py's "Compressed on-disk
    # JSON storage" comment), so this exercises the actual gzip path.
    _write_synthetic_portal(data_dir, "history_homes.json.gz", "leads_homes.json.gz", n_old=50, n_recent=20)
    hist_before = (data_dir / "history_homes.json.gz").stat().st_size
    leads_before = (data_dir / "leads_homes.json.gz").stat().st_size

    evict_stale_history.migrate_portal("homes")

    history_after = load_json_any(data_dir / "history_homes.json.gz")
    leads_after = load_json_any(data_dir / "leads_homes.json.gz")

    assert len(history_after) == 20
    assert all(lid.startswith("recent_") for lid in history_after)
    assert len(leads_after) == 20
    assert all(l["id"].startswith("recent_") for l in leads_after)

    hist_after = (data_dir / "history_homes.json.gz").stat().st_size
    leads_after_size = (data_dir / "leads_homes.json.gz").stat().st_size
    assert hist_after < hist_before
    assert leads_after_size < leads_before


def test_migrate_portal_dry_run_does_not_write(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(evict_stale_history, "DATA_DIR", data_dir)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(geo_utils, "datetime", _FrozenDatetime)

    _write_synthetic_portal(data_dir, "history_homes.json.gz", "leads_homes.json.gz", n_old=10, n_recent=5)
    before_bytes = (data_dir / "history_homes.json.gz").read_bytes()

    evict_stale_history.migrate_portal("homes", dry_run=True)

    after_bytes = (data_dir / "history_homes.json.gz").read_bytes()
    assert before_bytes == after_bytes
    history = load_json_any(data_dir / "history_homes.json.gz")
    assert len(history) == 15  # untouched


def test_migrate_portal_missing_file_is_a_noop(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(evict_stale_history, "DATA_DIR", data_dir)
    evict_stale_history.migrate_portal("bcpea")  # no file written - should not raise
    out = capsys.readouterr().out
    assert "not found" in out


def test_main_rejects_unknown_portal():
    import pytest
    old_argv = sys.argv
    try:
        sys.argv = ["evict_stale_history.py", "not_a_real_portal"]
        with pytest.raises(SystemExit):
            evict_stale_history.main()
    finally:
        sys.argv = old_argv


def test_main_defaults_to_all_eight_portals():
    assert set(evict_stale_history.PORTAL_FILES) == {
        "homes", "imot", "olx", "bazar", "imoti_bg", "bcpea", "alo", "imoti_net",
    }
