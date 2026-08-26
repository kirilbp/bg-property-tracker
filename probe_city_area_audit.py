"""
Diagnostic: sample real listing_sources rows to check city/area allocation
quality - per-portal breakdown of city_key IS NULL counts, a sample of
raw city/area/title text for null-city_key rows per portal, and a sample
of homes.bg/alo.bg's own city/area fields alongside their computed
city_key to spot mis-tagging patterns.
"""

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}

PORTALS = ["imoti.net", "alo.bg", "homes.bg", "imot.bg", "olx.bg", "bazar.bg", "imoti.bg", "sales.bcpea.org"]


def get(params, headers_extra=None):
    url = f"{SUPABASE_URL}/rest/v1/listing_sources"
    headers = {**HEADERS, **(headers_extra or {})}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    return resp


def null_city_count_by_portal():
    print("=== city_key IS NULL count by portal ===")
    for p in PORTALS:
        headers = {"Range-Unit": "items", "Range": "0-0", "Prefer": "count=exact"}
        resp = get({"select": "source_id", "portal": f"eq.{p}", "city_key": "is.null"}, headers)
        cr = resp.headers.get("Content-Range")
        print(f"{p}: status={resp.status_code} Content-Range={cr}")


def sample_null_city(portal, n=8):
    print(f"\n=== sample city_key IS NULL rows for {portal} ===")
    resp = get({
        "select": "source_id,city_key,area,title",
        "portal": f"eq.{portal}",
        "city_key": "is.null",
        "limit": str(n),
    })
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
        return
    for row in resp.json():
        print(f"  area={row.get('area')!r} title={row.get('title')!r}")


def sample_tagged(portal, n=10):
    print(f"\n=== sample city_key-tagged rows for {portal} (city_key, area, title) ===")
    resp = get({
        "select": "city_key,area,title",
        "portal": f"eq.{portal}",
        "city_key": "not.is.null",
        "limit": str(n),
    })
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
        return
    for row in resp.json():
        print(f"  city_key={row.get('city_key')!r} area={row.get('area')!r} title={row.get('title')!r}")


def main():
    null_city_count_by_portal()
    for p in ["homes.bg", "alo.bg", "imoti.bg", "olx.bg"]:
        sample_null_city(p)
        sample_tagged(p)


if __name__ == "__main__":
    main()
