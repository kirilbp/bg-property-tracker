"""
Diagnostic: after fixing the city_key 'sofia' fallback (PR #92), the
frontend's Sofia count crashed from ~24,650 to ~1,565 instead of settling
somewhere reasonable - meaning most listings, including what should be
obvious Sofia listings from Sofia-heavy portals, are failing to match
ANY canonical city name at all, not just edge-case small towns. This
pulls a sample of merged_listings rows with city_key IS NULL, grouped by
portal, with their raw city/title text, to see exactly what's failing to
match and why.

Read-only. Only ever run via workflow_dispatch.
"""

import os
import sys
from collections import Counter

import requests


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not secret_key:
        print("SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)

    headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}

    rows = []
    offset = 0
    batch = 1000
    while True:
        resp = requests.get(
            f"{supabase_url}/rest/v1/merged_listings",
            headers={**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + batch - 1}"},
            params={"select": "id,portal,city,city_key,title", "city_key": "is.null"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < batch:
            break
        offset += batch
    print(f"Total city_key IS NULL rows: {len(rows)}", flush=True)

    by_portal = Counter(r.get("portal") for r in rows)
    print("\n=== Unmatched rows by portal ===", flush=True)
    for portal, count in by_portal.most_common():
        print(f"{portal}: {count}", flush=True)

    print("\n=== Sample rows per portal (city field + title) ===", flush=True)
    seen_portals = set()
    for r in rows:
        p = r.get("portal")
        if p in seen_portals:
            continue
        seen_portals.add(p)
        print(f"\n--- {p} ---", flush=True)
        samples = [x for x in rows if x.get("portal") == p][:8]
        for s in samples:
            print(f"  city={s.get('city')!r}  title={(s.get('title') or '')[:80]!r}", flush=True)


if __name__ == "__main__":
    main()
