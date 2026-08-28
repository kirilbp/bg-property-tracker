"""
One-shot probe: reproduce index.html's fetchAllRows('merged_listings')
exactly (same batch size, concurrency, retry count) against the live
Supabase project, to find out why the site is showing "Could not load
listings data." on every refresh right now.

Not part of the scraper pipeline - dispatched by hand, read once, then
deleted.
"""

import time
import concurrent.futures

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}

BATCH_SIZE = 1000
CONCURRENCY = 3
MAX_RETRIES = 3


def fetch_batch(offset):
    url = f"{SUPABASE_URL}/rest/v1/merged_listings"
    params = {"select": "*", "order": "id", "offset": offset, "limit": BATCH_SIZE}
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.monotonic()
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
            elapsed = time.monotonic() - t0
            if resp.status_code == 200:
                data = resp.json()
                return offset, len(data), elapsed, None
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            print(f"DEBUG: offset={offset} attempt={attempt} FAILED {last_err} (t={elapsed:.1f}s)", flush=True)
        except Exception as e:
            elapsed = time.monotonic() - t0
            last_err = f"{type(e).__name__}: {e}"
            print(f"DEBUG: offset={offset} attempt={attempt} EXCEPTION {last_err} (t={elapsed:.1f}s)", flush=True)
        if attempt < MAX_RETRIES:
            time.sleep(0.5 * attempt)
    return offset, None, None, last_err


def main():
    # First: a single simple request to confirm basic connectivity/latency
    # and get a real total count via the Content-Range header.
    t0 = time.monotonic()
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/merged_listings",
        headers={**HEADERS, "Prefer": "count=exact"},
        params={"select": "id", "limit": 1},
        timeout=30,
    )
    print(f"DEBUG: single-row probe -> {resp.status_code} in {time.monotonic() - t0:.1f}s, "
          f"Content-Range={resp.headers.get('content-range')}", flush=True)
    if resp.status_code != 200:
        print("DEBUG: body:", resp.text[:500], flush=True)
        return

    total = int(resp.headers.get("content-range", "0/0").split("/")[-1])
    print(f"DEBUG: total rows reported = {total}", flush=True)

    # Now reproduce the real paging pattern: waves of CONCURRENCY concurrent
    # batches, same as fetchAllRows() in index.html.
    offset = 0
    wave_num = 0
    total_fetched = 0
    failures = []
    start = time.monotonic()
    while True:
        wave_num += 1
        offsets = [offset + i * BATCH_SIZE for i in range(CONCURRENCY)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
            results = list(ex.map(fetch_batch, offsets))

        done = False
        for off, count, elapsed, err in results:
            if err:
                failures.append((off, err))
                print(f"DEBUG: PERMANENT FAILURE at offset={off}: {err}", flush=True)
                done = True
                continue
            total_fetched += count
            if count < BATCH_SIZE:
                done = True
        offset += CONCURRENCY * BATCH_SIZE
        elapsed_total = time.monotonic() - start
        print(f"DEBUG: wave {wave_num} done, offset now {offset}, total_fetched={total_fetched}, "
              f"failures={len(failures)}, t={elapsed_total:.0f}s", flush=True)
        if done or failures or offset > total + BATCH_SIZE * CONCURRENCY:
            break

    print(f"\nRESULT: fetched {total_fetched} rows (expected {total}), "
          f"{len(failures)} permanent batch failures, total time {time.monotonic() - start:.0f}s", flush=True)
    if failures:
        print("First failure:", failures[0], flush=True)


if __name__ == "__main__":
    main()
