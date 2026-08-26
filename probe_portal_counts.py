"""
Diagnostic: fetch every listing_sources row's portal directly from
Supabase and print the real per-portal count right now, to check against
what the deployed frontend displays and what a fresh local recomputation
from the currently-committed data/leads_*.json files would produce.

Read-only. Only ever run via workflow_dispatch.
"""

import os
import sys
from collections import Counter

import requests


def fetch_all_portals(base_url, headers):
    portals = []
    offset = 0
    batch = 1000
    while True:
        resp = requests.get(
            f"{base_url}/rest/v1/listing_sources",
            headers={**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + batch - 1}"},
            params={"select": "portal,source_id"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        portals.extend(r["portal"] for r in page)
        if len(page) < batch:
            break
        offset += batch
    return portals


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not secret_key:
        print("SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)
    headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}

    portals = fetch_all_portals(supabase_url, headers)
    print(f"Total listing_sources rows: {len(portals)}", flush=True)
    counts = Counter(portals)
    for portal, count in counts.most_common():
        print(f"{portal}: {count}", flush=True)


if __name__ == "__main__":
    main()
