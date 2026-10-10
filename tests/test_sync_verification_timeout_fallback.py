"""
Tests for the 2026-10-10 fix to sync_to_supabase.py: a Postgres statement
timeout (57014) on the post-upsert verification/cleanup reads must not
crash the whole script after the real upsert work has already succeeded.

Real evidence (both already-confirmed production occurrences, see
docs/backlog.md for the full writeup):

  1. run 37198858695 / job 111426216987 (2026-10-04): after all 302,143
     rows were upserted successfully, check_portal_counts() ->
     _fetch_stored_source_ids() crashed on a listing_sources read with
     Postgres 57014, taking the whole script down with exit code 1.
  2. run 38019738767 / job 114117861396 (2026-10-10): after all 6
     scrapers and the real upsert work completed successfully,
     delete_stale_merged_listings()'s own merged_listings read crashed
     the same way.

Covers:
  1. _fetch_stored_source_ids() raises StatementTimeoutError (not a bare
     HTTPError) when request_with_retries() exhausts every retry and the
     final response is still a genuine Postgres 57014.
  2. _fetch_stored_source_ids() still raises via resp.raise_for_status()
     (an ordinary HTTPError) for a DIFFERENT 500 body (not 57014) - a
     different real failure at this call site must not be silently
     treated as "safe to skip".
  3. _fetch_stored_source_ids() still raises via resp.raise_for_status()
     for a genuine auth failure (401) - never caught as a timeout.
  4. delete_stale_merged_listings() raises StatementTimeoutError the
     same way, on its own merged_listings read loop.
  5. main(), end to end with every Supabase call mocked: a
     StatementTimeoutError from check_portal_counts() is caught, logged
     as a warning, and main() completes normally (no sys.exit, "Sync
     complete" reached) - the upsert work is never undone or retried.
  6. main(): a StatementTimeoutError from delete_stale_merged_listings()
     alone (check_portal_counts() succeeds) still lets
     delete_stale_listing_sources() run and main() complete normally -
     only the merged_listings cleanup for this run is skipped.
  7. main(): the pre-existing DataLossGuardTripped path (a genuinely
     different, intentional failure) is completely unchanged by this fix
     - it still exits with sys.exit(1).

Run with: python3 -m pytest tests/test_sync_verification_timeout_fallback.py -v
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sync_to_supabase as sts


class _FakeResponse:
    def __init__(self, status_code, json_body=None, text=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json_body = json_body
        self.text = text if text is not None else ""

    def json(self):
        if self._json_body is None:
            raise ValueError("no JSON body on this fake response")
        return self._json_body

    def raise_for_status(self):
        if not self.ok:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Server Error: fake for url", response=self
            )


# A real 57014 body, byte-for-byte the shape both confirmed incidents logged.
_TIMEOUT_BODY = {
    "code": "57014",
    "details": None,
    "hint": None,
    "message": "canceling statement due to statement timeout",
}


def _make_timeout_response():
    return _FakeResponse(500, json_body=_TIMEOUT_BODY)


# --- _is_statement_timeout() itself -----------------------------------------

def test_is_statement_timeout_true_for_real_57014_body():
    assert sts._is_statement_timeout(_make_timeout_response()) is True


def test_is_statement_timeout_false_for_different_500_body():
    other_500 = _FakeResponse(500, json_body={"code": "XX000", "message": "something else broke"})
    assert sts._is_statement_timeout(other_500) is False


def test_is_statement_timeout_false_for_non_500_status():
    unauthorized = _FakeResponse(401, json_body=_TIMEOUT_BODY)  # same body, wrong status
    assert sts._is_statement_timeout(unauthorized) is False


def test_is_statement_timeout_false_for_non_json_500_body():
    malformed = _FakeResponse(500, json_body=None, text="not json at all")
    assert sts._is_statement_timeout(malformed) is False


def test_is_statement_timeout_true_for_non_json_but_matching_raw_text():
    # The fallback substring check - covers a response whose body isn't
    # valid JSON (e.g. truncated by a proxy) but still plainly carries the
    # real error code in its raw text.
    raw = _FakeResponse(500, json_body=None, text='{"code":"57014","details":null}')
    assert sts._is_statement_timeout(raw) is True


# --- _fetch_stored_source_ids() ---------------------------------------------

def test_fetch_stored_source_ids_raises_statement_timeout_error(monkeypatch):
    monkeypatch.setattr(sts, "request_with_retries", lambda *a, **k: _make_timeout_response())
    with pytest.raises(sts.StatementTimeoutError):
        sts._fetch_stored_source_ids("https://example.invalid", {}, "alo.bg")


def test_fetch_stored_source_ids_still_raises_http_error_for_different_500(monkeypatch):
    other_500 = _FakeResponse(500, json_body={"code": "XX000", "message": "genuinely broken"})
    monkeypatch.setattr(sts, "request_with_retries", lambda *a, **k: other_500)
    with pytest.raises(requests.exceptions.HTTPError):
        sts._fetch_stored_source_ids("https://example.invalid", {}, "alo.bg")


def test_fetch_stored_source_ids_still_raises_http_error_for_auth_failure(monkeypatch):
    unauthorized = _FakeResponse(401, text="Invalid API key")
    monkeypatch.setattr(sts, "request_with_retries", lambda *a, **k: unauthorized)
    with pytest.raises(requests.exceptions.HTTPError):
        sts._fetch_stored_source_ids("https://example.invalid", {}, "alo.bg")


def test_fetch_stored_source_ids_succeeds_normally_across_pages(monkeypatch):
    # Unaffected-path regression guard: two pages of real-looking rows,
    # the normal keyset-pagination success case, must still work exactly
    # as before this fix.
    pages = [
        [{"source_id": f"alo_{i}"} for i in range(1000)],
        [{"source_id": "alo_1000"}],
    ]
    calls = {"n": 0}

    def fake_request_with_retries(method, url, **kwargs):
        rows = pages[calls["n"]]
        calls["n"] += 1
        return _FakeResponse(200, json_body=rows)

    monkeypatch.setattr(sts, "request_with_retries", fake_request_with_retries)
    result = sts._fetch_stored_source_ids("https://example.invalid", {}, "alo.bg")
    assert result == {f"alo_{i}" for i in range(1000)} | {"alo_1000"}
    assert calls["n"] == 2


# --- delete_stale_merged_listings() -----------------------------------------

def test_delete_stale_merged_listings_raises_statement_timeout_error(monkeypatch):
    monkeypatch.setattr(sts, "request_with_retries", lambda *a, **k: _make_timeout_response())
    with pytest.raises(sts.StatementTimeoutError):
        sts.delete_stale_merged_listings("https://example.invalid", {}, current_ids=set())


def test_delete_stale_merged_listings_still_raises_http_error_for_different_500(monkeypatch):
    other_500 = _FakeResponse(500, json_body={"code": "XX000", "message": "genuinely broken"})
    monkeypatch.setattr(sts, "request_with_retries", lambda *a, **k: other_500)
    with pytest.raises(requests.exceptions.HTTPError):
        sts.delete_stale_merged_listings("https://example.invalid", {}, current_ids=set())


# --- main() end to end, every Supabase call mocked --------------------------

@pytest.fixture
def main_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "fake-secret-key")
    monkeypatch.setattr(sts, "load_all_listings", lambda: [{"portal": "alo.bg", "source_id": "alo_1"}])
    monkeypatch.setattr(
        sts,
        "build_rows",
        lambda all_listings: (
            [{"portal": "alo.bg", "source_id": "alo_1"}],
            [{"id": "m_alo_1"}],
        ),
    )
    monkeypatch.setattr(sts, "upsert", lambda *a, **k: None)
    return None


def test_main_survives_statement_timeout_in_check_portal_counts(monkeypatch, main_env, capsys):
    # Reproduces occurrence 1 (run 37198858695/job 111426216987): the real
    # upsert work above succeeds, then check_portal_counts() hits the
    # timeout. main() must log a warning and reach "Sync complete" instead
    # of letting the exception propagate (which, before this fix, crashed
    # the process with exit code 1 - no sys.exit(1) here at all now).
    def fake_check_portal_counts(base_url, headers, current_by_portal):
        raise sts.StatementTimeoutError("listing_sources read for portal='alo.bg' timed out")

    delete_calls = {"merged": 0, "sources": 0}
    monkeypatch.setattr(sts, "check_portal_counts", fake_check_portal_counts)
    monkeypatch.setattr(sts, "delete_stale_merged_listings", lambda *a, **k: delete_calls.__setitem__("merged", delete_calls["merged"] + 1))
    monkeypatch.setattr(sts, "delete_stale_listing_sources", lambda *a, **k: delete_calls.__setitem__("sources", delete_calls["sources"] + 1))

    sts.main()  # must not raise, must not call sys.exit

    out = capsys.readouterr().out
    assert "Sync complete" in out
    assert "::warning::" in out
    assert "57014" not in out or "timed out" in out  # the warning should read as a timeout, not a raw code dump
    # Cleanup is skipped entirely when check_portal_counts() itself fails -
    # delete_stale_listing_sources() needs its per-portal stored ids, which
    # were never obtained.
    assert delete_calls == {"merged": 0, "sources": 0}


def test_main_survives_statement_timeout_in_delete_stale_merged_listings(monkeypatch, main_env, capsys):
    # Reproduces occurrence 2 (run 38019738767/job 114117861396): the real
    # upsert work succeeds, check_portal_counts() succeeds this time, but
    # delete_stale_merged_listings()'s own read times out. Only that one
    # cleanup step should be skipped - delete_stale_listing_sources() (an
    # independent call that already has its stored ids in hand) must still
    # run, and main() must still reach "Sync complete".
    monkeypatch.setattr(sts, "check_portal_counts", lambda *a, **k: {"alo.bg": {"alo_1"}})

    def fake_delete_stale_merged_listings(base_url, headers, current_ids):
        raise sts.StatementTimeoutError("merged_listings read timed out")

    sources_calls = {"n": 0}
    monkeypatch.setattr(sts, "delete_stale_merged_listings", fake_delete_stale_merged_listings)
    monkeypatch.setattr(
        sts, "delete_stale_listing_sources",
        lambda *a, **k: sources_calls.__setitem__("n", sources_calls["n"] + 1),
    )

    sts.main()  # must not raise

    out = capsys.readouterr().out
    assert "Sync complete" in out
    assert "::warning::" in out
    assert sources_calls["n"] == 1, "delete_stale_listing_sources() should still run - its own data was unaffected"


def test_main_data_loss_guard_still_exits_nonzero_unchanged(monkeypatch, main_env):
    # This fix must not touch the pre-existing, intentional
    # DataLossGuardTripped behavior - a genuinely broken scrape (not a
    # transient timeout) must still stop the run with a non-zero exit.
    def fake_check_portal_counts(base_url, headers, current_by_portal):
        raise sts.DataLossGuardTripped("alo.bg: 2 listing(s) this run (was 83939 live) - near-zero")

    monkeypatch.setattr(sts, "check_portal_counts", fake_check_portal_counts)
    monkeypatch.setattr(sts, "delete_stale_merged_listings", lambda *a, **k: pytest.fail("should not be called"))
    monkeypatch.setattr(sts, "delete_stale_listing_sources", lambda *a, **k: pytest.fail("should not be called"))

    with pytest.raises(SystemExit) as exc_info:
        sts.main()
    assert exc_info.value.code == 1
