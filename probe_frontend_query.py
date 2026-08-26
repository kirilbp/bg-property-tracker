"""
Diagnostic: reproduce the exact frontend query (anon/publishable key,
select('*').order(col).range(...)) against both tables, with an exact
row-count header, to confirm current totals directly.

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
    headers = {**HEADERS, "Range-Unit": "items", "Range": "0-0", "Prefer": "count=exact"}
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    print(f"=== {table} order={order_col} (exact count) ===")
    print(f"status: {resp.status_code}")
    print(f"Content-Range: {resp.headers.get('Content-Range')}")
    if resp.status_code >= 400:
        print(f"body: {resp.text[:2000]}")


def try_sample(table, order_col):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"select": "*", "order": order_col}
    headers = {**HEADERS, "Range-Unit": "items", "Range": "0-4"}
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    print(f"=== {table} order={order_col} (sample 5) ===")
    print(f"status: {resp.status_code}")
    if resp.status_code < 400:
        data = resp.json()
        print(f"rows returned: {len(data)}")
        if data:
            print(f"sample keys: {sorted(data[0].keys())}")
    else:
        print(f"body: {resp.text[:2000]}")


def main():
    try_query("merged_listings", "id")
    try_sample("merged_listings", "id")
    try_query("listing_sources", "source_id")
    try_sample("listing_sources", "source_id")


if __name__ == "__main__":
    main()
