"""
Diagnostic: current per-portal listing_sources counts. Filters on
"portal" which matches the leading column of listing_sources' composite
primary key (portal, source_id), so this is a fast indexed count, not a
full-table scan - safe to run with the anon key.
"""

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}

PORTALS = ["imoti.net", "alo.bg", "homes.bg", "imot.bg", "olx.bg", "bazar.bg", "imoti.bg", "sales.bcpea.org"]


def count_for_portal(portal):
    url = f"{SUPABASE_URL}/rest/v1/listing_sources"
    params = {"select": "source_id", "portal": f"eq.{portal}"}
    headers = {**HEADERS, "Range-Unit": "items", "Range": "0-0", "Prefer": "count=exact"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    cr = resp.headers.get("Content-Range")
    print(f"{portal}: status={resp.status_code} Content-Range={cr}")
    if resp.status_code >= 400:
        print(f"  body: {resp.text[:200]}")


def main():
    for p in PORTALS:
        count_for_portal(p)


if __name__ == "__main__":
    main()
