"""
One-time diagnostic: how many existing merged_listings groups in Supabase
actually span more than one city?

group_listings() (sync_to_supabase.py) currently matches purely on
(price bucket, normalized area) with no city check at all - a live report
found a bazar.bg listing genuinely in Veliko Tarnovo merged with a
homes.bg/alo.bg pair genuinely in Dobrich, all sharing the generic area
name "Център" ("center" - identical text in every Bulgarian town) at a
coincidentally matching price. This script quantifies the damage before
the fix ships: listing_sources.city_key is already a stored column per
source row (computed once at sync time), so this is a pure read/aggregate
over existing data, no recomputation needed.

Groups things by merged_id, counts how many groups have more than one
distinct non-null city_key among their member sources. A group with only
one city_key represented (even if some members have city_key=None,
unclassified) is NOT counted as cross-city - only a group with two or
more DIFFERENT known cities is real, confirmed corruption.

Read-only, workflow_dispatch only.
"""

import json
import os
import sys
from collections import defaultdict

import requests


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

    by_merged_id = defaultdict(list)
    offset = 0
    page_size = 1000
    total_rows = 0
    while True:
        resp = requests.get(
            f"{base_url}/rest/v1/listing_sources",
            headers=headers,
            params={
                "select": "portal,source_id,merged_id,city_key",
                "limit": page_size,
                "offset": offset,
            },
            timeout=60,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break
        for r in rows:
            by_merged_id[r["merged_id"]].append(r)
        total_rows += len(rows)
        offset += page_size
        if len(rows) < page_size:
            break

    print(f"Loaded {total_rows} listing_sources rows across {len(by_merged_id)} merged groups")

    cross_city_groups = []
    for merged_id, members in by_merged_id.items():
        if len(members) < 2:
            continue
        cities = {m["city_key"] for m in members if m.get("city_key")}
        if len(cities) > 1:
            cross_city_groups.append((merged_id, members, cities))

    print(f"\n{len(cross_city_groups)} merged groups span more than one city "
          f"(out of {sum(1 for m in by_merged_id.values() if len(m) >= 2)} groups with >=2 members)")

    print("\nSample of up to 20 cross-city groups:")
    for merged_id, members, cities in cross_city_groups[:20]:
        print(f"  {merged_id}  cities={sorted(cities)}")
        for m in members:
            print(f"    {m['portal']:16s} {m['source_id']:20s} city_key={m.get('city_key')}")

    with open("cross_city_merge_ids.json", "w", encoding="utf-8") as f:
        json.dump([mid for mid, _, _ in cross_city_groups], f)
    print(f"\nWrote {len(cross_city_groups)} affected merged_ids to cross_city_merge_ids.json")


if __name__ == "__main__":
    main()
