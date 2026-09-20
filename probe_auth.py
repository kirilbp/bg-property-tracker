"""
One-off diagnostic for the "login still doesn't work" investigation. This
sandbox's own egress proxy flatly denies CONNECT to *.supabase.co
(organization policy - confirmed live, not a transient network issue), so
this has to run on GitHub's own network via workflow_dispatch, the same
pattern used for every other network-dependent probe in this project.

Reports the EXACT reachability/response for each of:
1. GET /auth/v1/health - is the Auth (GoTrue) service itself up at all.
2. GET /auth/v1/settings - is Auth configured to allow email+password
   sign-in (this project doesn't use a public sign-up form, just
   signInWithPassword, so if email auth got toggled off this would be it).
3. POST /auth/v1/token?grant_type=password with a deliberately WRONG
   password - proves whether the CURRENT SUPABASE_ANON_KEY (a "publishable"
   key, not a legacy JWT anon key) is even accepted by the Auth endpoint,
   and whether the service responds with a normal "invalid credentials"
   (proves the pipeline works end-to-end short of a real password) versus
   a 401/500/other failure that would point at the real root cause. Never
   needs or touches a real password.
4. GET /rest/v1/merged_listings?select=id&limit=1 with the same anon key -
   isolates whether this is Auth-specific or the whole project (e.g. still
   paused/degraded right after the Pro upgrade) is unreachable.

Reads SUPABASE_URL/SUPABASE_ANON_KEY straight out of index.html on the
branch this runs from, not hardcoded, so there's no chance of testing a
stale/wrong value.
"""

import json
import re
import sys

import requests

TIMEOUT = 20


def read_from_index_html():
    html = open("index.html", encoding="utf-8").read()
    url = re.search(r"const SUPABASE_URL = '([^']+)'", html).group(1)
    key = re.search(r"const SUPABASE_ANON_KEY = '([^']+)'", html).group(1)
    return url, key


def report(label, resp=None, exc=None):
    print(f"\n=== {label} ===")
    if exc is not None:
        print(f"  EXCEPTION: {type(exc).__name__}: {exc}")
        return
    print(f"  HTTP {resp.status_code}")
    print(f"  Headers of interest: content-type={resp.headers.get('content-type')}")
    body = resp.text[:2000]
    print(f"  Body: {body}")


def main():
    url, key = read_from_index_html()
    print(f"SUPABASE_URL (from index.html on this branch): {url}")
    print(f"SUPABASE_ANON_KEY (from index.html on this branch): {key}")

    headers = {"apikey": key}

    try:
        resp = requests.get(f"{url}/auth/v1/health", headers=headers, timeout=TIMEOUT)
        report("1. GET /auth/v1/health", resp)
    except requests.RequestException as e:
        report("1. GET /auth/v1/health", exc=e)

    try:
        resp = requests.get(f"{url}/auth/v1/settings", headers=headers, timeout=TIMEOUT)
        report("2. GET /auth/v1/settings", resp)
    except requests.RequestException as e:
        report("2. GET /auth/v1/settings", exc=e)

    try:
        resp = requests.post(
            f"{url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={**headers, "Content-Type": "application/json"},
            json={"email": "diagnostic-probe-never-a-real-account@example.com", "password": "definitely-wrong-password-123"},
            timeout=TIMEOUT,
        )
        report("3. POST /auth/v1/token?grant_type=password (deliberately wrong credentials)", resp)
    except requests.RequestException as e:
        report("3. POST /auth/v1/token?grant_type=password", exc=e)

    try:
        resp = requests.get(
            f"{url}/rest/v1/merged_listings",
            params={"select": "id", "limit": 1},
            headers=headers,
            timeout=TIMEOUT,
        )
        report("4. GET /rest/v1/merged_listings?select=id&limit=1 (same anon key, REST not Auth)", resp)
    except requests.RequestException as e:
        report("4. GET /rest/v1/merged_listings", exc=e)


if __name__ == "__main__":
    main()
