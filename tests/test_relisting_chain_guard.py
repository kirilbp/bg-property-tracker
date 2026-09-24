"""
Regression tests for docs/backlog.md's 2026-09-24 scrape.yml commit-failure
incident (data/leads_homes.json + data/history_homes.json exceeded GitHub's
100MB push limit at 182.01MB/179.26MB - real numbers off GitHub Actions job
logs for runs 35883682311/35918395367/35945698190).

Root cause: a 3-consecutive-run git commit/push outage (git push rejected
with GH001) meant homes.bg's checked-out history kept comparing detect_
relistings.py's GONE_AFTER cutoff against an increasingly stale committed
baseline. The next run's crawl found huge swaths of its own backlog
crossing that cutoff while simultaneously being freshly re-scraped under
new listing IDs, and detect_relistings.py's chain logic misread that as
61,862 simultaneous delisted-then-relisted pairs in one run (83.6% of
homes.bg's tracked backlog) - injecting that many synthetic snapshots and
ballooning both files past GitHub's push limit.

Fix: geo_utils.relisting_chain_guard_tripped() (RELISTING_GUARD_ABS=2000,
RELISTING_GUARD_RATIO=0.05, calibrated from real committed relisting-rate
history - see that constant's own comment for the calibration numbers)
skips chain-injection for a portal entirely, loudly (::error::), when a
single run's matched pairs blow past either threshold - instead of
silently injecting them. detect_relistings.py's main() then exits non-
zero so scrape.yml's own end-of-job check (mirroring docs/backlog.md item
30's olx.bg pattern) can surface it as a real, visible workflow failure.

These tests exercise the guard both as a standalone function (the exact
incident numbers, and real historical healthy-day per-run rates) and
through detect_portal()'s real two-pass pipeline (confirming a tripped
guard skips injection and leaves the history file byte-for-byte untouched
on disk, and that normal below-threshold relisting behavior is unchanged
from before this fix - same injected count, same file writes).
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import detect_relistings
from geo_utils import RELISTING_GUARD_ABS, RELISTING_GUARD_RATIO, relisting_chain_guard_tripped


# --- Standalone guard function -------------------------------------------

def test_guard_trips_on_real_incident_numbers():
    # The actual 2026-09-24 storm: 61,862 matched pairs out of homes.bg's
    # 74,012-listing tracked backlog (83.6%) - real numbers off the
    # incident's own committed data.
    assert relisting_chain_guard_tripped("homes.bg", 61862, 74012) is True


def test_guard_does_not_trip_on_real_healthy_per_run_rate():
    # bazar.bg's real steady-state per-run injection rate, diffed run-by-run
    # from git history (not the cumulative-total-divided-by-runs figure an
    # earlier version of this comment used, which Missy's review caught as
    # wrong - that conflated a one-time go-live backfill with ongoing
    # behavior): 6-28 relistings/run, 0.01%-0.06% of its 51,860-listing
    # backlog. 208 here is a deliberately conservative stand-in - roughly
    # 7x the real observed maximum (28) - so this test still clears the
    # guard with real headroom even against a number well above anything
    # actually seen, not just the true real-world rate.
    assert relisting_chain_guard_tripped("bazar.bg", 208, 51860) is False


def test_guard_does_not_trip_at_several_times_busiest_real_rate():
    # 5x the conservative 208 stand-in above (itself already ~7x the real
    # observed per-run maximum of 28) - still well under both thresholds,
    # confirming the guard has genuine headroom above anything resembling
    # a portal's normal busiest day, not a threshold sitting right on top
    # of it.
    assert relisting_chain_guard_tripped("bazar.bg", 1040, 51860) is False


def test_guard_trips_on_absolute_threshold_alone():
    # Large backlog, ratio well under 5%, but the absolute count alone
    # clears RELISTING_GUARD_ABS.
    assert relisting_chain_guard_tripped("bazar.bg", RELISTING_GUARD_ABS, 10_000_000) is True


def test_guard_trips_on_ratio_threshold_alone():
    # Small backlog where the absolute count never reaches
    # RELISTING_GUARD_ABS, but the fraction of the whole portal clears
    # RELISTING_GUARD_RATIO - the exact shape a smaller portal's own
    # storm would take.
    small_total = 1000
    matched = int(small_total * RELISTING_GUARD_RATIO) + 1
    assert matched < RELISTING_GUARD_ABS
    assert relisting_chain_guard_tripped("imoti.bg", matched, small_total) is True


def test_guard_does_not_trip_on_zero_matches():
    assert relisting_chain_guard_tripped("olx.bg", 0, 36586) is False


# --- Through detect_portal()'s real pipeline ------------------------------

def _write_history(tmp_path, history):
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    path = data_dir / "history_homes.json"
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _homes_photo_key_fn():
    return detect_relistings.PORTALS["homes.bg"][1]


def test_detect_portal_skips_injection_and_leaves_file_untouched_when_tripped(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(hours=30)).isoformat()
    new_ts = now.isoformat()

    # Storm shape: 60 "gone" (stale) listings each sharing a photo-id
    # pattern with a distinct "active" (freshly re-scraped) listing, out
    # of 120 total tracked (50% - well past both guard thresholds).
    history = {}
    for i in range(60):
        history[f"homes_gone_{i}"] = {
            "first_seen": old_ts,
            "snapshots": [{"seen_at": old_ts, "price_eur": 100000}],
            "latest": {"photo": f"https://img.homes.bg/photos/{1000 + i}.jpg"},
        }
        history[f"homes_active_{i}"] = {
            "first_seen": new_ts,
            "snapshots": [{"seen_at": new_ts, "price_eur": 95000}],
            "latest": {"photo": f"https://img.homes.bg/photos/{1000 + i}.jpg"},
        }

    path = _write_history(tmp_path, history)
    before_bytes = path.read_bytes()
    monkeypatch.setattr(detect_relistings, "DATA_DIR", tmp_path / "data")

    injected, tripped = detect_relistings.detect_portal("homes.bg", "history_homes.json", _homes_photo_key_fn())

    assert tripped is True
    assert injected == 0
    # The guard must trip BEFORE any mutation - the file on disk is
    # byte-for-byte unchanged, not just "no net new relistings".
    assert path.read_bytes() == before_bytes
    written = json.loads(path.read_text(encoding="utf-8"))
    assert not any(
        s.get("source") == "relisted_from" for rec in written.values() for s in rec["snapshots"]
    )


def test_detect_portal_still_injects_normally_below_threshold(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(hours=30)).isoformat()
    new_ts = now.isoformat()

    # 3 real relisting pairs out of 10,000 tracked (0.03%) - far under both
    # thresholds; behavior must match the pre-guard implementation exactly.
    history = {}
    for i in range(3):
        history[f"homes_gone_{i}"] = {
            "first_seen": old_ts,
            "snapshots": [{"seen_at": old_ts, "price_eur": 100000}],
            "latest": {"photo": f"https://img.homes.bg/photos/{2000 + i}.jpg"},
        }
        history[f"homes_active_{i}"] = {
            "first_seen": new_ts,
            "snapshots": [{"seen_at": new_ts, "price_eur": 95000}],
            "latest": {"photo": f"https://img.homes.bg/photos/{2000 + i}.jpg"},
        }
    for i in range(9994):
        history[f"homes_pad_{i}"] = {
            "first_seen": new_ts,
            "snapshots": [{"seen_at": new_ts, "price_eur": 50000}],
            "latest": {"photo": f"https://img.homes.bg/photos/pad{i}.jpg"},
        }

    path = _write_history(tmp_path, history)
    monkeypatch.setattr(detect_relistings, "DATA_DIR", tmp_path / "data")

    injected, tripped = detect_relistings.detect_portal("homes.bg", "history_homes.json", _homes_photo_key_fn())

    assert tripped is False
    assert injected == 3
    written = json.loads(path.read_text(encoding="utf-8"))
    relisted = [
        s for i in range(3) for s in written[f"homes_active_{i}"]["snapshots"] if s.get("source") == "relisted_from"
    ]
    assert len(relisted) == 3
    for i, s in enumerate(relisted):
        assert s["relisted_from"] == f"homes_gone_{i}"
        assert s["price_eur"] == 100000


def test_main_exits_nonzero_when_any_portal_guard_trips(tmp_path, monkeypatch, capsys):
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(hours=30)).isoformat()
    new_ts = now.isoformat()

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    history = {}
    for i in range(60):
        history[f"homes_gone_{i}"] = {
            "first_seen": old_ts,
            "snapshots": [{"seen_at": old_ts, "price_eur": 100000}],
            "latest": {"photo": f"https://img.homes.bg/photos/{i}.jpg"},
        }
        history[f"homes_active_{i}"] = {
            "first_seen": new_ts,
            "snapshots": [{"seen_at": new_ts, "price_eur": 95000}],
            "latest": {"photo": f"https://img.homes.bg/photos/{i}.jpg"},
        }
    (data_dir / "history_homes.json").write_text(json.dumps(history), encoding="utf-8")

    monkeypatch.setattr(detect_relistings, "DATA_DIR", data_dir)
    # Only exercise homes.bg for this test - the other 4 portals' files
    # simply don't exist under tmp_path, and detect_portal() already
    # returns (0, False) for a missing file.
    monkeypatch.setattr(
        detect_relistings,
        "PORTALS",
        {"homes.bg": ("history_homes.json", _homes_photo_key_fn())},
    )

    try:
        detect_relistings.main()
        raised = False
    except SystemExit as e:
        raised = True
        code = e.code

    assert raised is True
    assert code == 1
