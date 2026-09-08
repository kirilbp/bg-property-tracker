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

Paginates by keyset (the table's own primary key, portal+source_id) rather
than OFFSET/LIMIT. Two live runs against this table both failed partway
through with a 500 from Supabase - the first at offset=166000, a later
one (after the table had grown further) at offset=221000 - after ~10+
minutes of otherwise-silent successful paging. That's the classic
deep-OFFSET failure mode: an OFFSET query still has to scan and discard
every row before the offset, so its cost grows with how deep the page is,
until it eventually exceeds the server's statement timeout - a genuine
retry of the same offset would very likely fail again the same way, not
just a one-off blip. Keyset pagination (order by the primary key, filter
for "greater than the last row seen") does the same amount of work no
matter how deep the page is, so it doesn't have this failure mode at all.
"""

import json
import os
import sys
import time
from collections import defaultdict

import requests

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5


def fetch_page(base_url, headers, page_size, cursor):
    """cursor is None for the first page, else (last_portal, last_source_id)
    of the previous page's final row - ordering matches the table's own
    primary key, so this is a total order with no ties to worry about."""
    params = {
        "select": "portal,source_id,merged_id,city_key",
        "order": "portal.asc,source_id.asc",
        "limit": page_size,
    }
    if cursor is not None:
        last_portal, last_source_id = cursor
        params["or"] = (
            f"(portal.gt.{last_portal},"
            f"and(portal.eq.{last_portal},source_id.gt.{last_source_id}))"
        )
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                f"{base_url}/rest/v1/listing_sources",
                headers=headers,
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"DEBUG: page fetch failed at cursor {cursor} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    print(f"ERROR: giving up on page at cursor {cursor} after {MAX_RETRIES} attempts", file=sys.stderr)
    sys.exit(1)


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
    page_size = 1000
    total_rows = 0
    cursor = None
    while True:
        rows = fetch_page(base_url, headers, page_size, cursor)
        if not rows:
            break
        for r in rows:
            by_merged_id[r["merged_id"]].append(r)
        total_rows += len(rows)
        cursor = (rows[-1]["portal"], rows[-1]["source_id"])
        if total_rows % 20000 == 0:
            print(f"DEBUG: loaded {total_rows} rows so far...")
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
