"""
Diagnostic: reproduce the exact concurrent request pattern fetchAllRows()
now uses (3 concurrent range queries per table, both tables at once via
threads) directly against Supabase, to isolate whether concurrency itself
(not query shape) is what's tripping the statement timeout - the ordering
fix (5.6x faster in isolation) didn't stop the live page from still
hitting "canceling statement due to statement timeout".
"""

import concurrent.futures
import time

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}


def fetch_page(table, order, offset, limit=1000):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"select": "*", "order": order}
    headers = {**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset + limit - 1}"}
    start = time.monotonic()
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    elapsed = time.monotonic() - start
    ok = resp.status_code < 400
    detail = "" if ok else f" body={resp.text[:150]}"
    return f"{table} offset={offset}: status={resp.status_code} elapsed={elapsed:.2f}s{detail}"


def main():
    jobs = []
    for i in range(3):
        jobs.append(("merged_listings", "id", i * 1000))
    for i in range(3):
        jobs.append(("listing_sources", "portal,source_id", i * 1000))

    print(f"Firing {len(jobs)} concurrent requests (matches live fetchAllRows() pattern)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futures = [ex.submit(fetch_page, *job) for job in jobs]
        for f in concurrent.futures.as_completed(futures):
            print(f.result())


if __name__ == "__main__":
    main()
