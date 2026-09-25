"""
Regression tests for scraper_alo.py's fetch_with_retries() connection-level
fast-fail fix (2026-09-25).

Real GitHub Actions job logs (run id 36085734587, backfill-detail-alo.yml,
2026-09-25 02:18-02:55 UTC) showed 55 distinct URLs in one 35-minute
backfill_detail_alo.py run that never completed a TCP handshake to alo.bg
at all (requests.exceptions.ConnectTimeout: "Connection to www.alo.bg timed
out. (connect timeout=8)"). Under the old fetch_with_retries() - MAX_RETRIES
= 3 attempts at timeout=(8, 15) with RETRY_BACKOFF_SECONDS = 5 * attempt
escalating backoff between tries - each one of those cost up to
3*8s + 5s + 10s = 39s worst case, and 55 * 39s =~2,145s (~35.75 min) is
effectively the entire TIME_BUDGET_SECONDS = 35*60 run budget, all spent on
URLs that were never going to answer.

The fix distinguishes connection-level failures (requests.ConnectTimeout,
and plain requests.ConnectionError where no response was ever received)
from failures where a connection succeeded or a real HTTP response came
back (requests.ReadTimeout, requests.HTTPError from a 5xx status). Only the
former gets cut down to CONNECT_FAILURE_MAX_RETRIES attempts with
CONNECT_FAILURE_BACKOFF_SECONDS (0) backoff; the latter keeps the full
MAX_RETRIES/RETRY_BACKOFF_SECONDS treatment, since a real HTTP-level
failure has an actual chance of succeeding on retry. A 404/410 must still
raise PermanentlyGone on the very first attempt, undisturbed by any of
this.

This sandbox has no network egress to alo.bg, so requests.get() is mocked
throughout - no live dispatch, per this repo's CLAUDE.md.

Run with: python3 -m unittest tests.test_scraper_alo_fetch_retries -v
(no pytest / other test framework is installed in this repo - see
tests/test_update_history.py's own note.)
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

import scraper_alo


def _http_error_response(status_code):
    """A requests.Response-shaped mock whose raise_for_status() raises
    requests.HTTPError carrying that status code on .response, matching
    what fetch_with_retries() actually inspects."""
    resp = mock.Mock()
    resp.status_code = status_code
    error = requests.HTTPError(f"{status_code} error", response=resp)
    resp.raise_for_status.side_effect = error
    return resp


class ConnectionLevelFailureFastFailsTests(unittest.TestCase):
    """(a) A connect-timeout-shaped failure now fails fast with fewer
    retries/less backoff than the old MAX_RETRIES=3 / escalating-backoff
    treatment."""

    def test_connect_timeout_gets_fewer_attempts_than_old_max_retries(self):
        with mock.patch(
            "scraper_alo.requests.get",
            side_effect=requests.exceptions.ConnectTimeout(
                "Connection to www.alo.bg timed out. (connect timeout=8)"
            ),
        ) as mock_get, mock.patch("scraper_alo.time.sleep") as mock_sleep:
            result = scraper_alo.fetch_with_retries("https://www.alo.bg/dead-listing-1")

        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, scraper_alo.CONNECT_FAILURE_MAX_RETRIES)
        self.assertLess(
            scraper_alo.CONNECT_FAILURE_MAX_RETRIES,
            scraper_alo.MAX_RETRIES,
            "connection-level failures must get fewer attempts than the old MAX_RETRIES",
        )

    def test_connect_timeout_uses_no_backoff_between_attempts(self):
        with mock.patch(
            "scraper_alo.requests.get",
            side_effect=requests.exceptions.ConnectTimeout("connect timeout=8"),
        ), mock.patch("scraper_alo.time.sleep") as mock_sleep:
            scraper_alo.fetch_with_retries("https://www.alo.bg/dead-listing-2")

        # CONNECT_FAILURE_BACKOFF_SECONDS is 0 - fetch_with_retries() must
        # not call time.sleep(0), and definitely never with the old
        # escalating RETRY_BACKOFF_SECONDS * attempt values (5, 10, ...).
        for call in mock_sleep.call_args_list:
            self.assertNotIn(call.args[0] if call.args else None, (5, 10, 15))
        self.assertEqual(mock_sleep.call_count, 0)

    def test_worst_case_time_budget_for_dead_url_is_cut_substantially(self):
        """Reproduces this fix's own time-budget math: worst case per
        connection-dead URL, in connect-timeout seconds (the 8s connect
        timeout is the dominant cost; backoff is now zero)."""
        connect_timeout_seconds = 8
        old_worst_case = (
            scraper_alo.MAX_RETRIES * connect_timeout_seconds
            + sum(
                scraper_alo.RETRY_BACKOFF_SECONDS * attempt
                for attempt in range(1, scraper_alo.MAX_RETRIES)
            )
        )
        new_worst_case = scraper_alo.CONNECT_FAILURE_MAX_RETRIES * connect_timeout_seconds

        self.assertEqual(old_worst_case, 39)  # matches the task's own figure
        self.assertEqual(new_worst_case, 16)
        self.assertLess(new_worst_case, old_worst_case * 0.5)

        # Same 55-dead-URLs-per-run figure observed in the real job logs,
        # used here only as a stand-in for the size of the effect, not
        # asserted as a guaranteed constant.
        observed_dead_urls_per_run = 55
        old_total = observed_dead_urls_per_run * old_worst_case
        new_total = observed_dead_urls_per_run * new_worst_case
        freed_seconds = old_total - new_total

        self.assertEqual(old_total, 2145)
        self.assertEqual(new_total, 880)
        self.assertEqual(freed_seconds, 1265)  # ~21 minutes freed per run
        self.assertGreater(freed_seconds, 20 * 60)

    def test_plain_connection_error_also_fast_fails(self):
        """A connection refused/never-resolved (plain ConnectionError, not
        specifically a ConnectTimeout) is just as much a "never got a
        response" case and must get the same fast-fail treatment."""
        with mock.patch(
            "scraper_alo.requests.get",
            side_effect=requests.exceptions.ConnectionError(
                "Failed to establish a new connection: [Errno 111] Connection refused"
            ),
        ) as mock_get, mock.patch("scraper_alo.time.sleep") as mock_sleep:
            result = scraper_alo.fetch_with_retries("https://www.alo.bg/dead-listing-3")

        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, scraper_alo.CONNECT_FAILURE_MAX_RETRIES)
        self.assertEqual(mock_sleep.call_count, 0)


class TransientHttpFailureKeepsFullRetryTests(unittest.TestCase):
    """(b) A genuinely-transient HTTP-level failure (a 500 response, or a
    read-timeout-after-connecting) still gets the full existing MAX_RETRIES
    / escalating-backoff treatment, unaffected by this fix."""

    def test_500_response_gets_full_max_retries_and_escalating_backoff(self):
        with mock.patch(
            "scraper_alo.requests.get", return_value=_http_error_response(500)
        ) as mock_get, mock.patch("scraper_alo.time.sleep") as mock_sleep:
            result = scraper_alo.fetch_with_retries("https://www.alo.bg/listing-500")

        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, scraper_alo.MAX_RETRIES)
        expected_backoffs = [
            scraper_alo.RETRY_BACKOFF_SECONDS * attempt
            for attempt in range(1, scraper_alo.MAX_RETRIES)
        ]
        actual_backoffs = [call.args[0] for call in mock_sleep.call_args_list]
        self.assertEqual(actual_backoffs, expected_backoffs)

    def test_read_timeout_after_connecting_gets_full_max_retries(self):
        # ReadTimeout is a sibling of ConnectionError (both subclass
        # Timeout/RequestException independently) - a read timeout means
        # the connection itself succeeded, so it must NOT be routed onto
        # the connection-level fast-fail path.
        self.assertFalse(
            issubclass(requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError)
        )
        with mock.patch(
            "scraper_alo.requests.get",
            side_effect=requests.exceptions.ReadTimeout("read timeout=15"),
        ) as mock_get, mock.patch("scraper_alo.time.sleep") as mock_sleep:
            result = scraper_alo.fetch_with_retries("https://www.alo.bg/listing-slow")

        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, scraper_alo.MAX_RETRIES)
        expected_backoffs = [
            scraper_alo.RETRY_BACKOFF_SECONDS * attempt
            for attempt in range(1, scraper_alo.MAX_RETRIES)
        ]
        actual_backoffs = [call.args[0] for call in mock_sleep.call_args_list]
        self.assertEqual(actual_backoffs, expected_backoffs)

    def test_eventual_success_after_transient_failure_returns_text(self):
        ok_response = mock.Mock()
        ok_response.raise_for_status.return_value = None
        ok_response.text = "<html>ok</html>"

        with mock.patch(
            "scraper_alo.requests.get",
            side_effect=[_http_error_response(503), ok_response],
        ) as mock_get, mock.patch("scraper_alo.time.sleep") as mock_sleep:
            result = scraper_alo.fetch_with_retries("https://www.alo.bg/listing-flaky")

        self.assertEqual(result, "<html>ok</html>")
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(scraper_alo.RETRY_BACKOFF_SECONDS * 1)


class PermanentlyGoneUndisturbedTests(unittest.TestCase):
    """(c) A 404/410 still raises PermanentlyGone immediately, on the very
    first attempt, exactly as before this fix."""

    def test_404_raises_permanently_gone_on_first_attempt(self):
        with mock.patch(
            "scraper_alo.requests.get", return_value=_http_error_response(404)
        ) as mock_get, mock.patch("scraper_alo.time.sleep") as mock_sleep:
            with self.assertRaises(scraper_alo.PermanentlyGone):
                scraper_alo.fetch_with_retries("https://www.alo.bg/gone-listing")

        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(mock_sleep.call_count, 0)

    def test_410_raises_permanently_gone_on_first_attempt(self):
        with mock.patch(
            "scraper_alo.requests.get", return_value=_http_error_response(410)
        ) as mock_get, mock.patch("scraper_alo.time.sleep") as mock_sleep:
            with self.assertRaises(scraper_alo.PermanentlyGone):
                scraper_alo.fetch_with_retries("https://www.alo.bg/gone-listing-2")

        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(mock_sleep.call_count, 0)


if __name__ == "__main__":
    unittest.main()
