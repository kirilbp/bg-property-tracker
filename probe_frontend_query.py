"""
Diagnostic: reproduce the exact frontend query (anon/publishable key,
select('*').order(col).range(...)) against both tables to find out why
the deployed page is showing "Could not load listings data." - this
error only fires on a real exception from the fetchAllRows() calls, so
whatever broke should surface directly as an HTTP error body here.

Uses the anon/publishable key hardcoded in index.html (meant to be
public, RLS-protected - not a secret). Read-only. Only ever run via
workflow_dispatch.
"""

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"

HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}


def try_query(table, order_col):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"select": "*", "order": order_col}
    headers = {**HEADERS, "Range-Unit": "items", "Range": "0-999"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    print(f"=== {table} order={order_col} ===")
    print(f"status: {resp.status_code}")
    print(f"Content-Range: {resp.headers.get('Content-Range')}")
    if resp.status_code >= 400:
        print(f"body: {resp.text[:2000]}")
    else:
        data = resp.json()
        print(f"rows returned: {len(data)}")
        if data:
            print(f"sample keys: {list(data[0].keys())}")


def main():
    try_query("merged_listings", "id")
    try_query("listing_sources", "source_id")


if __name__ == "__main__":
    main()
