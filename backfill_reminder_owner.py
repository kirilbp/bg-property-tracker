"""
One-time backfill for backlog #62: reminders created before the reminders
table had a user_id column (i.e. anything set between check-reminders.yml
going live and this migration landing) have user_id = NULL. Now that
reminders' RLS policy requires auth.uid() = user_id, a NULL-owner row is
permanently invisible to everyone, including the person who created it -
a safe failure mode (never cross-user-visible), but still worth fixing so
nothing anyone already set gets silently stranded.

Uses the Supabase Auth admin API (service-role key, same as sync_to_
supabase.py bypasses RLS) to find the account to assign these to. Refuses
to guess if there isn't exactly one: this app has exactly one real user by
design at this point, so "exactly one" is the only case this can resolve
safely - more than one means a second account exists for a reason this
script has no way to know, and zero means nobody's logged in yet to own
them.

Safe to run more than once - only ever touches rows where user_id is still
NULL, so a rerun after the backlog is already clear finds nothing to do.
"""

import os
import sys

import requests

REQUEST_TIMEOUT = 30


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not secret_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)

    base_url = supabase_url.rstrip("/")
    headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}

    try:
        resp = requests.get(f"{base_url}/auth/v1/admin/users", headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: failed to list accounts via the Auth admin API: {e}", file=sys.stderr)
        sys.exit(1)

    body = resp.json()
    # GoTrue's admin/users has returned either a bare array or
    # {"users": [...], ...} depending on version - handle both rather than
    # assume one.
    users = body.get("users", body) if isinstance(body, dict) else body

    if len(users) != 1:
        emails = [u.get("email", "?") for u in users]
        print(
            f"ERROR: expected exactly 1 account, found {len(users)} ({emails}) - refusing to guess "
            f"which one owns the orphaned reminders. Backfill manually if a second account was "
            f"created on purpose.",
            file=sys.stderr,
        )
        sys.exit(1)

    user_id = users[0]["id"]
    print(f"Sole account found: {users[0].get('email')} ({user_id})")

    try:
        patch = requests.patch(
            f"{base_url}/rest/v1/reminders",
            headers={**headers, "Content-Type": "application/json", "Prefer": "return=representation"},
            params={"user_id": "is.null"},
            json={"user_id": user_id},
            timeout=REQUEST_TIMEOUT,
        )
        patch.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: failed to backfill orphaned reminders: {e}", file=sys.stderr)
        sys.exit(1)

    updated = patch.json()
    print(f"Backfilled {len(updated)} previously-orphaned reminder(s) to {user_id}.")


if __name__ == "__main__":
    main()
