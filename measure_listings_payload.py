"""One-time diagnostic for backlog item 6 (site slow to load/refresh).

Measures the REAL payload-size difference between index.html's current
`select('*')` bulk fetch of `merged_listings` and a narrowed column list that
drops the heavy `description`/`photos`/`price_history` jsonb columns - the
change proposed as the core fix. Read-only, no writes, run once by hand via
its matching workflow (measure-listings-payload.yml), same pattern as
verify_price_history_in_supabase.py.

Not shipped application code - a measurement tool for this one investigation,
kept in the repo afterward only as a reusable diagnostic (matches the
existing verify_price_history_in_supabase.py precedent), never referenced by
index.html or any scraper/sync script.
"""
import os
import sys
import time

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    print("SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_SECRET_KEY,
    "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
}

# Every column merged_listings has today (supabase/schema.sql) EXCEPT the
# three heavy jsonb columns the fix direction says to drop from the bulk
# list-view fetch: description, photos, price_history.
#
# area_key deliberately left OUT here even though schema.sql defines it
# (backlog item 18) - a live run of this script (2026-09-22) got
# "column merged_listings.area_key does not exist" back from Supabase
# itself (a 400, not the earlier-suspected 42703 alone - same underlying
# cause), independently confirming backlog item 18's already-flagged open
# item: that migration has not actually been applied to the live table
# yet. Add it back in once that's confirmed applied. Matches
# index.html's own MERGED_LISTINGS_BULK_COLUMNS, which excludes it for
# the identical reason.
NARROW_COLUMNS = (
    "id,portal,url,photo,price_eur,sqm,area,title,category,"
    "category_confidence,type_bucket,city_key,oblast_key,lat,lng,"
    "price_per_sqm,price_drop_count,drop_pct,days_on_market,score,status,"
    "member_count,member_portals,area_avg_price_per_sqm,pct_vs_area_avg,"
    "site_updated_at,site_posted_at,updated_at"
)


def get_total_count():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/merged_listings",
        headers={**HEADERS, "Prefer": "count=exact"},
        params={"select": "id", "limit": "1"},
        timeout=30,
    )
    if not r.ok:
        print(f"get_total_count failed: {r.status_code} {r.reason}", file=sys.stderr)
        print(f"response body: {r.text[:2000]}", file=sys.stderr)
    r.raise_for_status()
    content_range = r.headers.get("content-range", "")
    # format: "0-0/123456"
    total = int(content_range.split("/")[-1])
    return total


def measure(select_clause, sample_size, label):
    t0 = time.time()
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/merged_listings",
        headers=HEADERS,
        params={"select": select_clause, "order": "id", "limit": str(sample_size)},
        timeout=60,
    )
    if not r.ok:
        print(f"[{label}] failed: {r.status_code} {r.reason}", file=sys.stderr)
        print(f"response body: {r.text[:2000]}", file=sys.stderr)
    r.raise_for_status()
    elapsed = time.time() - t0
    rows = r.json()
    n = len(rows)
    total_bytes = len(r.content)
    bytes_per_row = total_bytes / n if n else 0
    print(f"[{label}] sampled {n} rows: {total_bytes:,} bytes, "
          f"{bytes_per_row:,.0f} bytes/row, {elapsed:.2f}s for this request")
    return bytes_per_row


def main():
    print("=== backlog item 6: measuring merged_listings payload size ===")
    # count=exact itself hit Postgres's statement_timeout live on a prior run
    # (a real finding in its own right, not just a script bug - see
    # docs/backlog.md item 6/docs/decisions.md) - this fallback (already
    # proven live on a real successful run) keeps the actual byte-per-row
    # comparison below from being blocked by that.
    try:
        total_rows = get_total_count()
        print(f"merged_listings total row count (Prefer: count=exact): {total_rows:,}")
    except requests.exceptions.HTTPError as e:
        print(f"count=exact itself failed ({e}) - this is itself a real finding, "
              f"not just a script bug: an exact COUNT(*) over merged_listings is "
              f"apparently expensive enough to hit Postgres's statement_timeout. "
              f"Falling back to the last known real row count from backlog item "
              f"18's own investigation (~214,889) to still get the per-row byte "
              f"comparison below.", file=sys.stderr)
        total_rows = 214889

    sample_size = 500
    full_bpr = measure("*", sample_size, "select(*) - current code")
    narrow_bpr = measure(NARROW_COLUMNS, sample_size, "narrowed select() - proposed fix")

    full_total_mb = full_bpr * total_rows / (1024 * 1024)
    narrow_total_mb = narrow_bpr * total_rows / (1024 * 1024)
    reduction_pct = 100 * (1 - narrow_bpr / full_bpr) if full_bpr else 0

    round_trips = -(-total_rows // 1000)  # ceil div, batchSize=1000 in fetchAllRows()

    print()
    print("=== extrapolated to the full table (what a real page load transfers) ===")
    print(f"select(*)     : ~{full_total_mb:,.1f} MB total, {round_trips} sequential round trips")
    print(f"narrowed      : ~{narrow_total_mb:,.1f} MB total, {round_trips} sequential round trips")
    print(f"payload reduction from column narrowing alone: {reduction_pct:.1f}%")
    print()
    print("Round-trip count is unchanged by column narrowing alone - that's what "
          "the caching layer half of the fix addresses (avoiding these round trips "
          "entirely on a cache-fresh refresh), not this measurement.")


if __name__ == "__main__":
    main()
