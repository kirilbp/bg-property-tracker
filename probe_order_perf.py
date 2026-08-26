"""
Diagnostic: time a deep-offset paginated query against listing_sources
under two orderings - order=source_id alone (does NOT match its primary
key, which is the composite (portal, source_id)) vs order=portal,source_id
(matches the primary key exactly) - to confirm the mismatched order is
what's forcing a full-table sort and tripping the statement timeout seen
on the live site.
"""

import time

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}


def timed_query(label, order, offset, limit=1000):
    url = f"{SUPABASE_URL}/rest/v1/listing_sources"
    params = {"select": "source_id,portal", "order": order}
    headers = {**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset + limit - 1}"}
    start = time.monotonic()
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    elapsed = time.monotonic() - start
    print(f"{label}: status={resp.status_code} elapsed={elapsed:.2f}s")
    if resp.status_code >= 400:
        print(f"  body: {resp.text[:300]}")
    else:
        data = resp.json()
        print(f"  rows: {len(data)}")


def main():
    for offset in (0, 50000, 150000):
        timed_query(f"order=source_id.asc offset={offset}", "source_id.asc", offset)
        timed_query(f"order=portal.asc,source_id.asc offset={offset}", "portal.asc,source_id.asc", offset)


if __name__ == "__main__":
    main()
