"""
One-time backfill for backlog #62: reminders created before the reminders
table had a user_id column (i.e. anything set between check-reminders.yml
going live and this migration landing) have user_id = NULL. Now that
reminders' RLS policy requires auth.uid() = user_id, a NULL-owner row is
permanently invisible to everyone, including the person who created it -
a safe failure mode (never cross-user-visible), but still worth fixing so
nothing anyone already set gets silently stranded.

Originally tried the Supabase Auth admin API (GET /auth/v1/admin/users)
to find the account to assign these to. A real run against the live
project returned HTTP 200 with zero users despite the account existing
and already owning migrated saved_listings/lead_generators rows -
SUPABASE_SECRET_KEY is proven to work against the ordinary PostgREST API
(sync_to_supabase.py uses the exact same secret against /rest/v1/ on
every scrape), so the simplest explanation is that whatever key format
this project issues as its "secret" key isn't accepted the same way by
the separate GoTrue admin surface. Rather than debug a key format this
script has no way to introspect, it now finds the account the same way
sync_to_supabase.py already reliably does: query a table that RLS scopes
to a real user (saved_listings, then lead_generators as a fallback) via
the ordinary REST API and read the user_id off an existing row. Still
refuses to guess if that comes back with zero or more than one distinct
owner - "exactly one" is the only case this can resolve safely.

Safe to run more than once - only ever touches rows where user_id is still
NULL, so a rerun after the backlog is already clear finds nothing to do.
"""

import os
import sys

import requests

REQUEST_TIMEOUT = 30
OWNER_SOURCE_TABLES = ["saved_listings", "lead_generators"]


def find_sole_owner(base_url, headers):
    for table in OWNER_SOURCE_TABLES:
        try:
            resp = requests.get(
                f"{base_url}/rest/v1/{table}",
                headers=headers,
                params={"select": "user_id", "user_id": "not.is.null"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"ERROR: failed to read {table} while looking up the account: {e}", file=sys.stderr)
            sys.exit(1)

        owner_ids = {row["user_id"] for row in resp.json()}
        if len(owner_ids) == 1:
            return next(iter(owner_ids)), table
        if len(owner_ids) > 1:
            print(
                f"ERROR: expected exactly 1 account, found {len(owner_ids)} distinct user_id(s) "
                f"owning rows in {table} ({sorted(owner_ids)}) - refusing to guess which one owns "
                f"the orphaned reminders. Backfill manually if a second account was created on "
                f"purpose.",
                file=sys.stderr,
            )
            sys.exit(1)
        # Empty for this table - fall through and try the next one before
        # giving up, since a fresh account may not have saved_listings yet
        # but could already have a lead_generators row, or vice versa.

    print(
        "ERROR: found 0 accounts with any rows in "
        f"{OWNER_SOURCE_TABLES} - refusing to guess which one owns the orphaned reminders. "
        "Nobody has saved a listing or lead generator yet to identify the account by.",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not secret_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)

    base_url = supabase_url.rstrip("/")
    headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}

    user_id, source_table = find_sole_owner(base_url, headers)
    print(f"Sole account found via {source_table}: {user_id}")

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
