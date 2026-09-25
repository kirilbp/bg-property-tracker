"""
Tests for the 2026-09-25 hardening to sync_to_supabase.py's
request_with_retries() - run 36106917335 hit a bare
requests.exceptions.ReadTimeout on the very last upsert() request of that
run, after successfully processing hundreds of thousands of rows over
~37 minutes with no other failures, and it exhausted all MAX_HTTP_RETRIES
attempts before raising. See request_with_retries()'s own comment for the
full incident writeup and reasoning.

Covers:
  1. A Timeout gets TIMEOUT_EXTRA_RETRIES attempts beyond MAX_HTTP_RETRIES
     (so a request that keeps timing out but would have succeeded on one
     more try now gets that try).
  2. A Timeout that STILL never succeeds eventually raises (this is a
     bounded extra allowance, not infinite patience).
  3. A non-Timeout RequestException (e.g. a hard ConnectionError) is
     NOT given the extra allowance - it must still give up at exactly
     MAX_HTTP_RETRIES attempts, unchanged from before this fix. Timeout
     is deliberately special-cased, not every transient failure.
  4. REQUEST_TIMEOUT_SECONDS (the actual per-request timeout= value) is
     used at every Supabase HTTP call site in this file - a regression
     here would silently mean the "longer timeout" half of this fix
     doesn't actually apply to the call that hit it.
  5. The bonus attempt granted by TIMEOUT_EXTRA_RETRIES (attempt
     max_attempts, i.e. MAX_HTTP_RETRIES + TIMEOUT_EXTRA_RETRIES) must
     still be able to return a live, non-ok response instead of falling
     through the loop with an implicit `return None`. This was a real bug
     found in review: the "are we done" check used to compare `attempt ==
     MAX_HTTP_RETRIES` (the *old* loop bound) instead of `max_attempts`
     (the *actual*, decoupled loop bound), so a live non-ok response on
     the timeout bonus attempt (attempt 5) never matched and the function
     fell off the end of the for loop, implicitly returning None. Every
     caller (upsert(), _fetch_stored_source_ids(),
     delete_stale_merged_listings(), delete_stale_listing_sources()) then
     crashes with an uncaught AttributeError on `None.ok` /
     `None.raise_for_status()` instead of a clean, diagnosable HTTP error.

Run with: python3 -m pytest tests/test_supabase_retry_timeout.py -v
"""
import inspect
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sync_to_supabase as sts


class _FakeOkResponse:
    ok = True
    status_code = 200
    text = ""


def test_timeout_gets_one_extra_retry_beyond_max_http_retries(monkeypatch):
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        # Times out on every attempt except the very last one allowed
        # (MAX_HTTP_RETRIES + TIMEOUT_EXTRA_RETRIES) - only reachable at
        # all if the extra retry is actually granted.
        if calls["n"] < sts.MAX_HTTP_RETRIES + sts.TIMEOUT_EXTRA_RETRIES:
            raise requests.exceptions.ReadTimeout("simulated read timeout")
        return _FakeOkResponse()

    monkeypatch.setattr(requests, "request", fake_request)
    monkeypatch.setattr(sts.time, "sleep", lambda s: None)  # don't actually wait in tests

    resp = sts.request_with_retries("POST", "https://example.invalid/rest/v1/x")
    assert resp.ok
    assert calls["n"] == sts.MAX_HTTP_RETRIES + sts.TIMEOUT_EXTRA_RETRIES


def test_timeout_that_never_succeeds_eventually_raises(monkeypatch):
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        raise requests.exceptions.ReadTimeout("simulated read timeout")

    monkeypatch.setattr(requests, "request", fake_request)
    monkeypatch.setattr(sts.time, "sleep", lambda s: None)

    with pytest.raises(requests.exceptions.ReadTimeout):
        sts.request_with_retries("POST", "https://example.invalid/rest/v1/x")
    # Bounded, not infinite: exactly MAX_HTTP_RETRIES + TIMEOUT_EXTRA_RETRIES
    # attempts, then it gives up.
    assert calls["n"] == sts.MAX_HTTP_RETRIES + sts.TIMEOUT_EXTRA_RETRIES


def test_non_timeout_request_exception_not_given_extra_retries(monkeypatch):
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        raise requests.exceptions.ConnectionError("simulated hard connection failure")

    monkeypatch.setattr(requests, "request", fake_request)
    monkeypatch.setattr(sts.time, "sleep", lambda s: None)

    with pytest.raises(requests.exceptions.ConnectionError):
        sts.request_with_retries("POST", "https://example.invalid/rest/v1/x")
    # Unchanged from before this fix - only MAX_HTTP_RETRIES attempts, no
    # TIMEOUT_EXTRA_RETRIES bonus for a non-timeout failure.
    assert calls["n"] == sts.MAX_HTTP_RETRIES


class _FakeErrorResponse:
    ok = False
    status_code = 500
    text = "simulated live server error"


def test_live_non_ok_response_on_timeout_bonus_attempt_is_returned_not_none(monkeypatch):
    # Reproduces the confirmed regression: MAX_HTTP_RETRIES (4) simulated
    # ReadTimeouts, retried via the TIMEOUT_EXTRA_RETRIES allowance, then a
    # live (non-exception) non-ok response on the final/bonus attempt
    # (attempt 5 == max_attempts). Before the fix, the "are we done" check
    # only matched attempt == MAX_HTTP_RETRIES (4), so this case fell
    # through the bottom of the loop and request_with_retries() returned
    # None instead of the response - crashing every caller with an
    # AttributeError on None.ok / None.raise_for_status().
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        if calls["n"] <= sts.MAX_HTTP_RETRIES:
            raise requests.exceptions.ReadTimeout("simulated read timeout")
        return _FakeErrorResponse()

    monkeypatch.setattr(requests, "request", fake_request)
    monkeypatch.setattr(sts.time, "sleep", lambda s: None)

    resp = sts.request_with_retries("POST", "https://example.invalid/rest/v1/x")

    assert resp is not None, (
        "request_with_retries() returned None instead of the live non-ok "
        "response on the timeout bonus attempt - this is the exact bug "
        "Missy's review found: callers do resp.ok/resp.raise_for_status() "
        "on this and crash with an uncaught AttributeError"
    )
    assert resp.status_code == 500
    assert resp.ok is False
    assert calls["n"] == sts.MAX_HTTP_RETRIES + sts.TIMEOUT_EXTRA_RETRIES


def test_request_timeout_constant_used_at_every_call_site():
    # Guards against a future call site hardcoding timeout=60 (or any
    # other literal) again instead of using the shared constant - source
    # inspection, not a live network assertion.
    source = inspect.getsource(sts)
    assert "timeout=60" not in source, (
        "found a hardcoded timeout=60 - Supabase call sites should use "
        "sts.REQUEST_TIMEOUT_SECONDS so the 2026-09-25 timeout hardening "
        "actually applies everywhere"
    )
    assert sts.REQUEST_TIMEOUT_SECONDS > 60, (
        "REQUEST_TIMEOUT_SECONDS should be longer than the old 60s literal "
        "it replaced - see request_with_retries()'s own comment"
    )
