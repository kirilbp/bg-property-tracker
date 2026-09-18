"""
Checks the `reminders` table (supabase/schema.sql) for reminders that are
now due and haven't been notified about yet, and opens a GitHub issue for
each one - a free, zero-new-infrastructure stand-in for email: this repo's
owner already gets GitHub's own notification email for a new issue in a
repo they're watching (the default for a repo's own creator), so this
needs no email service, no API key, and nothing new to maintain beyond
this script. Reminders themselves are set from the site's listing detail
page and always show up on the Dashboard regardless of whether this script
ever runs - this is the "also nudge me outside the site" half described in
the backlog, not the only way a reminder becomes visible.

A reminder is "due" once remind_at <= now(); "notified" (notified_at set)
once this script has successfully opened its issue - checked so a reminder
doesn't get a fresh issue opened every single day it stays undismissed.
notified_at is written with the secret/service-role key (bypasses RLS,
same as sync_to_supabase.py) - the anon key's own update policy on this
table only exists so the browser can set "dismissed" from the Dashboard,
never notified_at (see schema.sql's own comment on why that's not
column-scoped, but harmless either way: it's a purely internal bookkeeping
timestamp, not something the browser has any legitimate reason to touch).

Deliberately fails loudly (sys.exit(1)) on any Supabase or GitHub API
error, exactly like audit_cross_city_merges.py - a reminder that silently
fails to fire is worse than useless (it looks like it worked), and this
job runs unattended on a schedule with nobody watching its output unless
it actually fails. "No reminders due today" is NOT a failure and exits 0
normally; only a real inability to check or notify is.
"""

import os
import sys

import requests

REQUEST_TIMEOUT = 30


def supabase_headers(secret_key):
    return {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }


def fetch_due_reminders(base_url, headers):
    # dismissed=false and notified_at=null are both required - a dismissed-
    # but-not-yet-notified reminder (the user acted on it before this ever
    # ran) shouldn't still open an issue, and an already-notified one
    # obviously shouldn't open a second.
    params = {
        "select": "id,listing_id,listing_title,listing_portal,note,remind_at",
        "dismissed": "eq.false",
        "notified_at": "is.null",
        "remind_at": f"lte.{now_iso()}",
        "order": "remind_at.asc",
    }
    resp = requests.get(f"{base_url}/rest/v1/reminders", headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def mark_notified(base_url, headers, reminder_id):
    resp = requests.patch(
        f"{base_url}/rest/v1/reminders",
        headers=headers,
        params={"id": f"eq.{reminder_id}"},
        json={"notified_at": now_iso()},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()


def open_github_issue(repo, token, reminder):
    listing_desc = reminder.get("listing_title") or reminder.get("listing_id") or "a listing"
    portal = reminder.get("listing_portal")
    if portal:
        listing_desc += f" ({portal})"

    title = f"\U0001f514 Reminder due: {reminder['note'][:80]}"
    body_lines = [
        f"**Listing:** {listing_desc}",
        f"**Note:** {reminder['note']}",
        f"**Due:** {reminder['remind_at']}",
    ]
    if reminder.get("listing_id"):
        body_lines.append(f"\nOpen it: https://imotenradar.com/#/listing/{reminder['listing_id']}")
    body_lines.append(
        "\n---\nOpened automatically by check_reminders.py. This reminder also shows on the "
        "site's Dashboard - closing this issue doesn't dismiss it there; use the Dashboard's "
        "own Dismiss button for that."
    )

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": title, "body": "\n".join(body_lines), "labels": ["reminder"]},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["html_url"]


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = os.environ.get("GITHUB_REPOSITORY")

    missing = [
        name for name, val in [
            ("SUPABASE_URL", supabase_url), ("SUPABASE_SECRET_KEY", secret_key),
            ("GITHUB_TOKEN", github_token), ("GITHUB_REPOSITORY", github_repo),
        ] if not val
    ]
    if missing:
        print(f"ERROR: missing required environment variable(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    base_url = supabase_url.rstrip("/")
    headers = supabase_headers(secret_key)

    try:
        due = fetch_due_reminders(base_url, headers)
    except requests.RequestException as e:
        print(f"ERROR: failed to query Supabase for due reminders: {e}", file=sys.stderr)
        sys.exit(1)

    if not due:
        print("No reminders due right now.")
        return

    print(f"{len(due)} reminder(s) due - opening GitHub issues...")
    failures = []
    for reminder in due:
        try:
            issue_url = open_github_issue(github_repo, github_token, reminder)
            mark_notified(base_url, headers, reminder["id"])
            print(f"  reminder {reminder['id']}: {issue_url}")
        except requests.RequestException as e:
            print(f"  reminder {reminder['id']}: FAILED - {e}", file=sys.stderr)
            failures.append(reminder["id"])

    if failures:
        print(
            f"\nERROR: {len(failures)} of {len(due)} due reminder(s) failed to notify "
            f"(ids: {failures}) - see errors above. Not silently swallowed: this run failed.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\nAll {len(due)} due reminder(s) notified successfully.")


if __name__ == "__main__":
    main()
