"""
One-time check: does Supabase's listing_sources.price_history actually
hold the full price history for a listing, or something truncated/partial?

Picks the listings with the longest price_history chains in the currently
committed data/leads_*.json (the deepest available stress test - these are
the listings a truncation bug would be most likely to show up on), fetches
the same (portal, source_id) rows from Supabase, and compares length and
content. This is the evidence for the pruning decision in progress: pruning
git's history_*.json only makes sense if Supabase already holds the
complete record independently.

Read-only, one-time, not scheduled - run once via workflow_dispatch.
"""

import glob
import json
import os
import sys

import requests

DATA_DIR = "data"
TOP_N = 25


def load_candidates():
    candidates = []
    for path in glob.glob(os.path.join(DATA_DIR, "leads_*.json")):
        listings = json.loads(open(path, encoding="utf-8").read())
        for l in listings:
            ph = l.get("price_history") or []
            if len(ph) >= 2:
                candidates.append((len(ph), l.get("portal"), l.get("id"), ph))
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[:TOP_N]


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not secret_key:
        print("SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)

    headers = {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
    }
    base_url = supabase_url.rstrip("/")

    candidates = load_candidates()
    print(f"Checking {len(candidates)} listings with the longest git-JSON price_history chains\n")

    mismatches = 0
    for git_len, portal, source_id, git_history in candidates:
        resp = requests.get(
            f"{base_url}/rest/v1/listing_sources",
            headers=headers,
            params={
                "portal": f"eq.{portal}",
                "source_id": f"eq.{source_id}",
                "select": "price_history",
            },
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            print(f"MISSING  portal={portal!r} id={source_id!r}: no row found in Supabase at all")
            mismatches += 1
            continue

        sb_history = rows[0].get("price_history") or []
        status = "OK" if len(sb_history) >= git_len else "SHORTER"
        if status != "OK":
            mismatches += 1
        print(f"{status:8s} portal={portal!r:20s} id={source_id!r:20s} git_len={git_len:3d} supabase_len={len(sb_history):3d}")
        if status != "OK":
            print(f"         git:      {git_history}")
            print(f"         supabase: {sb_history}")

    print()
    if mismatches == 0:
        print(f"All {len(candidates)} checked listings: Supabase price_history is >= git's committed price_history.")
    else:
        print(f"{mismatches}/{len(candidates)} listings had shorter or missing price_history in Supabase - investigate before pruning.")


if __name__ == "__main__":
    main()
