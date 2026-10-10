"""
Tests for the 2026-10-10 fix to sync_to_supabase.py's upsert(): a Postgres
statement timeout (57014) on a WRITE batch (not the read-side verification/
cleanup queries backlog item 76 already fixed) must not crash the whole
script after most of the upsert has already succeeded.

Real evidence (run 38041416146 / job 114182255312, 2026-10-10): upsert()
was writing listing_sources in batches of 500 and got 98.9% of the way
through (438,500 of 443,247 rows) before the final batch
(rows 438500-443247) hit a sustained Postgres 57014 through every one of
request_with_retries()'s own retry attempts. The uncaught HTTPError this
used to raise crashed the whole process with exit code 1 - losing the
merged_listings upsert (the very next line in main(), never reached) and
every cleanup step after it, not just this one batch's ~4,747 rows.

This is deliberately a DIFFERENT fix shape from backlog item 76's read-side
fix, not a reuse of StatementTimeoutError: a write failing isn't "nothing
lost, re-check next cycle" by itself - it's only safe to skip because
main() rebuilds its full row set from the committed data files and
re-upserts everything (idempotent, resolution=merge-duplicates) on every
run, confirmed by reading load_all_listings()/build_rows(), not assumed.

Covers:
  1. upsert() on a batch that hits 57014 on every retry attempt: logs a
     warning naming the batch's row range and table, skips just that
     batch, and continues upserting the REMAINING batches instead of
     crashing - reproduces the exact 98.9%-complete scenario above
     (several successful batches, then one 57014 batch, then more
     batches after it that must still run).
  2. upsert() still raises via resp.raise_for_status() (an ordinary
     HTTPError) for a DIFFERENT 500 body (not 57014) on the same call
     site - a genuinely different failure must not be silently absorbed.
  3. upsert() still raises via resp.raise_for_status() for a genuine auth
     failure (401) on a batch - never caught as a timeout.
  4. upsert() logs a final summary warning naming the total skipped row/
     batch counts, not just a single per-batch message.
  5. The pre-existing missing-column (PGRST204) retry-and-strip behavior
     is completely unaffected by this change - unchanged regression
     guard.
  6. main() end to end, every Supabase call mocked except upsert() itself:
     a 57014 on the FINAL listing_sources batch does not raise - main()
     still proceeds to upsert merged_listings and run the normal
     cleanup/verification flow, reaching "Sync complete".

Run with: python3 -m pytest tests/test_sync_upsert_write_timeout.py -v
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


_OK_RESPONSE = _FakeResponse(200)

# A real 57014 body, byte-for-byte the shape the confirmed incident logged.
_TIMEOUT_BODY = {
    "code": "57014",
    "details": None,
    "hint": None,
    "message": "canceling statement due to statement timeout",
}


def _make_timeout_response():
    return _FakeResponse(500, json_body=_TIMEOUT_BODY)


def _rows(n, prefix="r"):
    return [{"portal": "alo.bg", "source_id": f"{prefix}_{i}"} for i in range(n)]


# --- upsert(): the 98.9%-complete batch-timeout scenario --------------------

def test_upsert_skips_one_timed_out_batch_and_continues_with_the_rest(monkeypatch, capsys):
    # 3 batches of BATCH_SIZE (500) rows: batch 0 succeeds, batch 1 (the
    # "final" one in the real incident's shape) hits 57014 on every retry,
    # batch 2 (rows AFTER the failed one) must still be attempted and
    # succeed - this is the part a naive "stop entirely on first timeout"
    # fix would get wrong, and the exact gap request_with_retries()'s own
    # retries don't cover (it already retries within one batch's request;
    # this is about what happens to the NEXT batch after it gives up).
    rows = _rows(3 * sts.BATCH_SIZE)
    calls = []

    def fake_request_with_retries(method, url, **kwargs):
        batch = kwargs["json"]
        calls.append(batch)
        if len(calls) == 2:  # the second batch (index 500-1000) times out
            return _make_timeout_response()
        return _OK_RESPONSE

    monkeypatch.setattr(sts, "request_with_retries", fake_request_with_retries)

    sts.upsert("https://example.invalid", {}, "listing_sources", rows, on_conflict="portal,source_id")

    assert len(calls) == 3, "all 3 batches must be attempted - the timed-out one must not stop the loop"
    out = capsys.readouterr().out
    assert "::warning::" in out
    assert "listing_sources" in out
    assert f"{sts.BATCH_SIZE}-{2 * sts.BATCH_SIZE}" in out, "the warning should name the exact skipped row range"
    assert "did NOT land" in out or "did not land" in out.lower()


def test_upsert_still_raises_http_error_for_different_500(monkeypatch):
    other_500 = _FakeResponse(500, json_body={"code": "XX000", "message": "genuinely broken"})
    monkeypatch.setattr(sts, "request_with_retries", lambda *a, **k: other_500)
    with pytest.raises(requests.exceptions.HTTPError):
        sts.upsert("https://example.invalid", {}, "listing_sources", _rows(10), on_conflict="portal,source_id")


def test_upsert_still_raises_http_error_for_auth_failure(monkeypatch):
    unauthorized = _FakeResponse(401, text="Invalid API key")
    monkeypatch.setattr(sts, "request_with_retries", lambda *a, **k: unauthorized)
    with pytest.raises(requests.exceptions.HTTPError):
        sts.upsert("https://example.invalid", {}, "listing_sources", _rows(10), on_conflict="portal,source_id")


def test_upsert_logs_a_final_summary_of_skipped_batches(monkeypatch, capsys):
    rows = _rows(2 * sts.BATCH_SIZE)

    def fake_request_with_retries(method, url, **kwargs):
        return _make_timeout_response()

    monkeypatch.setattr(sts, "request_with_retries", fake_request_with_retries)
    sts.upsert("https://example.invalid", {}, "listing_sources", rows, on_conflict="portal,source_id")

    out = capsys.readouterr().out
    # Both batches skipped: 2 batches, BATCH_SIZE*2 rows total.
    assert str(2 * sts.BATCH_SIZE) in out
    assert "2 batch" in out or "across 2" in out


def test_upsert_missing_column_retry_unaffected(monkeypatch):
    # Pre-existing PGRST204 behavior (strip the missing column from every
    # row, retry the same batch index) must be completely unchanged by
    # this fix - it's a separate branch, checked first, that must still
    # `continue` without incrementing past the batch or treating it as a
    # skip.
    rows = [{"portal": "alo.bg", "source_id": "r_0", "area_key": "sofia"}]
    responses = [
        _FakeResponse(400, text="Could not find the 'area_key' column of 'listing_sources' in the schema cache"),
        _OK_RESPONSE,
    ]
    calls = {"n": 0}

    def fake_request_with_retries(method, url, **kwargs):
        resp = responses[calls["n"]]
        calls["n"] += 1
        return resp

    monkeypatch.setattr(sts, "request_with_retries", fake_request_with_retries)
    sts.upsert("https://example.invalid", {}, "listing_sources", rows, on_conflict="portal,source_id")

    assert calls["n"] == 2
    assert "area_key" not in rows[0], "the missing column must still be stripped from the row"


# --- main() end to end: a write-side timeout must not block merged_listings
#     or the normal cleanup flow that follows ----------------------------

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
    monkeypatch.setattr(sts, "check_portal_counts", lambda *a, **k: {"alo.bg": {"alo_1"}})
    monkeypatch.setattr(sts, "delete_stale_merged_listings", lambda *a, **k: None)
    monkeypatch.setattr(sts, "delete_stale_listing_sources", lambda *a, **k: None)
    return None


def test_main_survives_write_side_timeout_on_final_listing_sources_batch(monkeypatch, main_env, capsys):
    # Reproduces the real incident's shape end to end: listing_sources'
    # one and only batch hits 57014 on every retry, but main() must still
    # proceed to upsert merged_listings and run the normal
    # verification/cleanup flow, reaching "Sync complete" - not crash with
    # exit code 1 and lose all of that, as it did in the real run.
    merged_upsert_calls = {"n": 0}
    real_upsert = sts.upsert

    def tracking_upsert(base_url, headers, table, rows, on_conflict):
        if table == "merged_listings":
            merged_upsert_calls["n"] += 1
            return
        # listing_sources: delegate to the real upsert() against a
        # request_with_retries that always times out, so this exercises
        # the real skip-and-continue code path, not a stub.
        monkeypatch.setattr(sts, "request_with_retries", lambda *a, **k: _make_timeout_response())
        return real_upsert(base_url, headers, table, rows, on_conflict)

    monkeypatch.setattr(sts, "upsert", tracking_upsert)

    sts.main()  # must not raise, must not call sys.exit

    out = capsys.readouterr().out
    assert "Sync complete" in out
    assert "::warning::" in out
    assert merged_upsert_calls["n"] == 1, "merged_listings upsert must still run after listing_sources' timeout"
