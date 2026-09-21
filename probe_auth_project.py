"""
One-off diagnostic for the "login rejects real credentials" investigation.
The user suspects index.html's SUPABASE_URL/SUPABASE_ANON_KEY (and/or the
SUPABASE_SECRET_KEY GitHub Actions secret) may be pointed at the wrong
Supabase project - a different org's project ("Paris"), not the real
imotenradar.com one their account lives in. Read-only, needs no real
password (never sends one), and does two independent checks:

1. GET /auth/v1/admin/users with the SECRET key (the same one sync_to_
   supabase.py/backfill_reminder_owner.py/check_reminders.py already use)
   - lists every real account in whichever project SUPABASE_URL actually
   points to. If the user's own email isn't in this list, the account is
   NOT in this project, full stop - wrong-project confirmed regardless of
   password. This exact call returned 0 users once before
   (backfill_reminder_owner.py, days ago) and was never explained - this
   re-runs it now, post the Supabase Pro upgrade, to see if that's still
   true.
2. GET /rest/v1/merged_listings?select=id&limit=1 with the PUBLISHABLE
   key from index.html - confirms both keys really do point at the same
   project (comparing the project ref embedded in each URL is not
   enough on its own: two different orgs could each name a project
   something confusingly similar). If this project has real listings
   AND 0 real users, that's the wrong-project theory conclusively
   confirmed - the working data pipeline and the broken auth pipeline
   are simply pointed at two different concerns of the SAME project,
   and login fails because no matching account exists there.
"""

import json
import os
import re
import sys

import requests

TIMEOUT = 20


def read_frontend_url_and_key():
    html = open("index.html", encoding="utf-8").read()
    url = re.search(r"const SUPABASE_URL = '([^']+)'", html).group(1)
    key = re.search(r"const SUPABASE_ANON_KEY = '([^']+)'", html).group(1)
    return url, key


def main():
    frontend_url, publishable_key = read_frontend_url_and_key()
    secret_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")

    print(f"index.html SUPABASE_URL:        {frontend_url}")
    print(f"GitHub secret SUPABASE_URL:     {secret_url}")
    print(f"URLs match: {frontend_url.rstrip('/') == (secret_url or '').rstrip('/')}")

    print("\n=== 1. GET /auth/v1/admin/users (secret key - lists real accounts in this project) ===")
    try:
        resp = requests.get(
            f"{secret_url.rstrip('/')}/auth/v1/admin/users",
            headers={"apikey": secret_key, "Authorization": f"Bearer {secret_key}"},
            timeout=TIMEOUT,
        )
        print(f"  HTTP {resp.status_code}")
        body = resp.json()
        users = body.get("users", body) if isinstance(body, dict) else body
        if isinstance(users, list):
            print(f"  {len(users)} account(s) found:")
            for u in users:
                print(f"    - {u.get('email')}  (id={u.get('id')}, created_at={u.get('created_at')})")
        else:
            print(f"  Unexpected body shape: {json.dumps(body)[:1000]}")
    except requests.RequestException as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")

    print("\n=== 2. GET /rest/v1/merged_listings?select=id&limit=1 (publishable key from index.html) ===")
    try:
        resp = requests.get(
            f"{frontend_url.rstrip('/')}/rest/v1/merged_listings",
            params={"select": "id", "limit": 1},
            headers={"apikey": publishable_key},
            timeout=TIMEOUT,
        )
        print(f"  HTTP {resp.status_code}")
        print(f"  Body: {resp.text[:500]}")
    except requests.RequestException as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
