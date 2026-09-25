"""
Tests for the 2026-09-25 addendum to the scrape.yml GH001 incident fix
(see geo_utils.py's "Compressed on-disk JSON storage" comment for the
full real-data numbers): evict_stale_records() alone was found NOT to
unblock the very next scrape.yml run, since dd83178's homes.bg tracking-ID
collision fix means that run's own real record count jumps ~1.90x
(74,012 -> 140,337) independent of anything stale. Capping the `photos`
array (the obvious-looking lever) was checked and rejected - it's a real,
live Supabase/frontend-gallery call site, not dead weight, and even an
extreme cap didn't get under the limit on its own. Gzip compression
(measured: ~92% smaller with zero data loss on real homes.bg data) is what
actually does, so homes.bg's own HISTORY_FILE/LEADS_FILE are now
`.json.gz`, not plain `.json`.

Covers:
  1. geo_utils.load_json_any()/save_json_any() as standalone units - the
     one read/write path every consumer of these two files now goes
     through.
  2. merge_history_conflict.py's is_history_file()/git_show()/resolve()
     stay correct for a `.json.gz` conflicted path (this matters because
     `git show` returns raw blob bytes regardless of format, and this
     script decides "did I get a real merge" - the exact failure mode
     that caused the original alo.bg silent-data-loss incident this
     script exists to prevent, docs/backlog.md item 3).
  3. sync_to_supabase.py's load_all_listings() reads homes.bg's real
     `.json.gz` leads file transparently, same as every plain-.json
     portal.

Run with: python3 -m pytest tests/test_gzip_json_storage.py -v
"""
import gzip
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geo_utils import load_json_any, save_json_any
import merge_history_conflict as m
import sync_to_supabase as sts


# --- geo_utils.load_json_any() / save_json_any() ---------------------------

def test_save_then_load_gz_round_trips(tmp_path):
    path = tmp_path / "history_homes.json.gz"
    obj = {"homes_1": {"first_seen": "2026-09-01T00:00:00+00:00", "snapshots": [], "latest": {"title": "Апартамент"}}}
    save_json_any(path, obj)
    assert load_json_any(path) == obj


def test_save_then_load_plain_json_unchanged(tmp_path):
    # Every non-.gz portal's own behavior must stay byte-for-byte what it
    # was before this change: plain, pretty-printed (indent=2).
    path = tmp_path / "history_imot.json"
    obj = {"a": 1, "b": [1, 2, 3]}
    save_json_any(path, obj)
    assert path.read_text(encoding="utf-8") == json.dumps(obj, ensure_ascii=False, indent=2)
    assert load_json_any(path) == obj


def test_gz_file_is_actually_smaller_than_plain_for_the_same_data(tmp_path):
    obj = [{"id": f"homes_{i}", "photos": [f"https://g1.homes.bg/{i}_{j}.jpg" for j in range(8)]} for i in range(500)]
    gz_path = tmp_path / "leads_homes.json.gz"
    plain_path = tmp_path / "leads_homes_plain.json"
    save_json_any(gz_path, obj)
    save_json_any(plain_path, obj)
    assert gz_path.stat().st_size < plain_path.stat().st_size * 0.25


def test_gz_round_trip_preserves_unicode_exactly(tmp_path):
    path = tmp_path / "leads_homes.json.gz"
    obj = [{"title": "Тристаен, 230m², жк. Лозенец, София", "area": "жк. Лозенец"}]
    save_json_any(path, obj)
    assert load_json_any(path) == obj


def test_load_json_any_raises_on_missing_file(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_json_any(tmp_path / "does_not_exist.json.gz")


def test_save_json_any_accepts_str_path(tmp_path):
    path_str = str(tmp_path / "history_homes.json.gz")
    save_json_any(path_str, {"x": 1})
    assert load_json_any(path_str) == {"x": 1}


# --- merge_history_conflict.py: gzip-aware conflict resolution -------------

def test_is_history_file_recognizes_gz_and_plain():
    assert m.is_history_file("data/history_homes.json.gz") is True
    assert m.is_history_file("data/history_homes.json") is True
    assert m.is_history_file("data/history.json.gz") is True
    assert m.is_history_file("data/history.json") is True
    assert m.is_history_file("data/leads_homes.json.gz") is False
    assert m.is_history_file("data/leads_homes.json") is False


def test_git_show_decompresses_gz_blob(tmp_path, monkeypatch):
    # git_show() shells out to `git show <stage><path>` - simulate what
    # that returns for a gzip-compressed blob (raw bytes, exactly what a
    # real `git show` on a committed .json.gz file returns) without
    # needing a real git repo/conflict fixture.
    payload = {"homes_1": {"first_seen": "x", "snapshots": [], "latest": {}}}
    gz_bytes = gzip.compress(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    class _FakeResult:
        returncode = 0
        stdout = gz_bytes

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult())
    result = m.git_show("main", "data/history_homes.json.gz")
    assert json.loads(result) == payload


def test_git_show_returns_none_on_missing_stage(monkeypatch):
    class _FakeResult:
        returncode = 128
        stdout = b""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult())
    assert m.git_show("main", "data/history_homes.json.gz") is None


def test_resolve_writes_a_real_gzip_file_and_git_adds_it(tmp_path, monkeypatch):
    main_payload = {"a": {"first_seen": "2026-09-01T00:00:00+00:00", "snapshots": [{"seen_at": "2026-09-01T00:00:00+00:00", "price_eur": 100000}], "latest": {"portal": "homes.bg"}}}
    local_payload = {"b": {"first_seen": "2026-09-02T00:00:00+00:00", "snapshots": [{"seen_at": "2026-09-02T00:00:00+00:00", "price_eur": 90000}], "latest": {"portal": "homes.bg"}}}

    path = tmp_path / "history_homes.json.gz"

    def fake_run(cmd, **kwargs):
        class _R:
            pass
        r = _R()
        if cmd[:2] == ["git", "show"]:
            stage_path = cmd[2]
            if stage_path.startswith(":2:"):
                r.returncode = 0
                r.stdout = gzip.compress(json.dumps(main_payload).encode("utf-8"))
            elif stage_path.startswith(":3:"):
                r.returncode = 0
                r.stdout = gzip.compress(json.dumps(local_payload).encode("utf-8"))
            else:
                r.returncode = 1
                r.stdout = b""
            return r
        # `git add <path>` - no-op for this test, just needs check=True to
        # not raise.
        r.returncode = 0
        r.stdout = b""
        return r

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = m.resolve(str(path))
    assert ok is True
    on_disk = load_json_any(path)
    assert set(on_disk) == {"a", "b"}  # real per-id union, neither side discarded


def _fake_git_run_one_side_missing(missing_stage, present_payload):
    """Builds a fake subprocess.run() for resolve()'s git_show() calls
    where ONE stage genuinely doesn't exist (git show exits non-zero for
    that stage - the real signature of an "add/add" conflict, e.g. this
    exact path was newly created independently on both sides, or one side
    never touched it at all) while the other stage has real content."""
    def fake_run(cmd, **kwargs):
        class _R:
            pass
        r = _R()
        if cmd[:2] == ["git", "show"]:
            stage_path = cmd[2]
            stage = ":2:" if stage_path.startswith(":2:") else ":3:" if stage_path.startswith(":3:") else None
            if stage == missing_stage or stage is None:
                r.returncode = 128
                r.stdout = b""
            else:
                r.returncode = 0
                r.stdout = gzip.compress(json.dumps(present_payload).encode("utf-8"))
            return r
        r.returncode = 0
        r.stdout = b""
        return r
    return fake_run


def test_resolve_handles_newly_created_file_missing_on_main(tmp_path, monkeypatch):
    # scrape.yml's own scenario for a brand-new/first-ever history file on
    # a portal, or a genuine "add/add" conflict: this run's own commit
    # (local, stage :3:) has real content, but `git show :2:<path>`
    # (main) fails - main never had this path at the point of conflict.
    # merge_history_conflict.py must not discard local's data just
    # because the "other side" doesn't exist - a newly-created file is
    # exactly the case a blind checkout --ours would handle worst (main
    # has nothing to check out `--ours` FROM, so a naive script could
    # either crash or silently produce an empty file).
    local_payload = {"homes_1": {"first_seen": "2026-09-25T00:00:00+00:00", "snapshots": [{"seen_at": "2026-09-25T00:00:00+00:00", "price_eur": 70000}], "latest": {"portal": "homes.bg"}}}
    path = tmp_path / "history_homes.json.gz"
    monkeypatch.setattr(subprocess, "run", _fake_git_run_one_side_missing(":2:", local_payload))
    ok = m.resolve(str(path))
    assert ok is True
    on_disk = load_json_any(path)
    # local's own freshly-scraped record survives untouched - nothing to
    # merge it against, so it passes straight through.
    assert on_disk == local_payload


def test_resolve_handles_file_missing_on_local(tmp_path, monkeypatch):
    # The mirror image: this run's own commit never touched this path
    # (stage :3: missing) but main has real content (stage :2: present) -
    # main's data must be kept, not wiped out to an empty file.
    main_payload = {"homes_2": {"first_seen": "2026-09-20T00:00:00+00:00", "snapshots": [{"seen_at": "2026-09-20T00:00:00+00:00", "price_eur": 60000}], "latest": {"portal": "homes.bg"}}}
    path = tmp_path / "history_homes.json.gz"
    monkeypatch.setattr(subprocess, "run", _fake_git_run_one_side_missing(":3:", main_payload))
    ok = m.resolve(str(path))
    assert ok is True
    on_disk = load_json_any(path)
    assert on_disk == main_payload


def test_resolve_returns_false_when_neither_stage_exists(tmp_path, monkeypatch):
    # Degenerate case (shouldn't happen in a real conflict, since a
    # conflicted path must exist on at least one side) - resolve() must
    # not crash or silently write an empty file; it leaves the path
    # unresolved for the caller's own checkout --ours fallback.
    path = tmp_path / "history_homes.json.gz"

    class _MissingResult:
        returncode = 128
        stdout = b""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _MissingResult())
    ok = m.resolve(str(path))
    assert ok is False
    assert not path.exists()


# --- sync_to_supabase.py: reads homes.bg's real .json.gz leads file --------

def test_load_all_listings_reads_gz_leads_file_for_homes(tmp_path, monkeypatch):
    monkeypatch.setattr(sts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(sts, "PORTAL_FILES", {"homes.bg": "leads_homes.json.gz"})
    leads = [{"id": "homes_1", "photos": ["https://g1.homes.bg/1.jpg", "https://g1.homes.bg/2.jpg"]}]
    save_json_any(tmp_path / "leads_homes.json.gz", leads)

    all_listings = sts.load_all_listings()
    assert len(all_listings) == 1
    assert all_listings[0]["id"] == "homes_1"
    assert all_listings[0]["photos"] == leads[0]["photos"]  # full array survives, not truncated
    assert all_listings[0]["portal"] == "homes.bg"
