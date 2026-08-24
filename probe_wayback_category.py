"""
Diagnostic-only follow-up to probe_deeper_history.py CHECK 2: that check
found imot.bg's SEARCH/CATEGORY page has 18 real Wayback captures from
April 2025 to July 2026 (unlike individual listing pages, which had ~2.5%
coverage - see the removed wayback_probe.py / PR #40). bazar.bg had 5
captures, olx.bg 6 (but all before 2021 - too old to matter), and
imoti.net/alo.bg/imoti.bg failed with transient 503/timeout errors so
their real coverage is still unknown.

This does the decisive test before committing to building real extraction
logic: retries the failed CDX lookups, then actually fetches a couple of
imot.bg's and bazar.bg's archived category-page snapshots, extracts
whatever listing IDs + prices are parseable from them, and checks how many
of those IDs are STILL present in our currently-tracked leads_imot.json /
leads_bazar.json. If the overlap is zero or near-zero (plausible - Sofia
apartment listings often sell or get taken down within months), building a
full archived-page parser would be wasted effort regardless of how easy
the old page format is to parse. If there's real overlap, it's worth it.

Read-only, no data files touched.
"""

import json
import re
import time
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
ARCHIVE_UA = "bg-property-tracker/1.0 (personal deal-tracking tool, non-commercial)"
CDX_URL = "http://web.archive.org/cdx/search/cdx"
REQUEST_DELAY_SECONDS = 2.0
MAX_RETRIES = 4

DATA_DIR = Path(__file__).parent / "data"

RETRY_TARGETS = {
    "imoti.net": "https://www.imoti.net/en/obiavi/r/prodava/sofia",
    "alo.bg": "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342",
    "imoti.bg": "https://imoti.bg/продажби/di:софия/cu:BGN",
}

# (portal, category url, leads file, listing-id regex on archived HTML)
SNAPSHOT_TARGETS = [
    ("imot.bg", "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya", "leads_imot.json",
     re.compile(r"obiava-(\d[a-z0-9]{15,20})")),
    ("bazar.bg", "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia", "leads_bazar.json",
     re.compile(r"obiava-(\d+)")),
]


def cdx_query(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                CDX_URL,
                params={"url": url, "output": "json", "collapse": "digest", "limit": 200, "fl": "timestamp,statuscode"},
                headers={"User-Agent": ARCHIVE_UA},
                timeout=25,
            )
            resp.raise_for_status()
            rows = resp.json()
            return rows
        except Exception as e:
            print(f"  attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(REQUEST_DELAY_SECONDS * attempt)
    return None


def retry_failed_lookups():
    print("\n===== Retrying failed CDX lookups (503/timeout, not \"no coverage\") =====")
    for portal, url in RETRY_TARGETS.items():
        print(f"\n{portal}: {url}")
        rows = cdx_query(url)
        if rows is None:
            print(f"  still failing after {MAX_RETRIES} attempts")
            continue
        if not rows or len(rows) < 2:
            print("  0 captures")
            continue
        header, *data_rows = rows
        timestamps = sorted(r[0] for r in data_rows)
        print(f"  {len(data_rows)} captures, {timestamps[0]} to {timestamps[-1]}")


def fetch_snapshot(timestamp, original_url):
    # "id_" suffix = the raw archived content, unmodified by Wayback's toolbar/link-rewriting
    wayback_url = f"http://web.archive.org/web/{timestamp}id_/{original_url}"
    resp = requests.get(wayback_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def check_snapshot_overlap():
    print("\n\n===== Checking real overlap: archived listing IDs vs currently-tracked listings =====")
    for portal, url, leads_file, id_re in SNAPSHOT_TARGETS:
        print(f"\n--- {portal} ---")
        time.sleep(REQUEST_DELAY_SECONDS)
        rows = cdx_query(url)
        if not rows or len(rows) < 2:
            print("  no captures available")
            continue
        header, *data_rows = rows
        timestamps = sorted(set(r[0] for r in data_rows))
        # sample the oldest, middle, and newest snapshot
        sample_timestamps = sorted(set([timestamps[0], timestamps[len(timestamps) // 2], timestamps[-1]]))

        leads_path = DATA_DIR / leads_file
        current_ids = set()
        if leads_path.exists():
            current = json.loads(leads_path.read_text(encoding="utf-8"))
            for l in current:
                m = id_re.search(l.get("url", ""))
                if m:
                    current_ids.add(m.group(1))
        print(f"  {len(current_ids)} currently-tracked listing IDs loaded from {leads_file}")

        for ts in sample_timestamps:
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                html = fetch_snapshot(ts, url)
            except Exception as e:
                print(f"  snapshot {ts}: FAILED to fetch - {e}")
                continue
            archived_ids = set(id_re.findall(html))
            overlap = archived_ids & current_ids
            print(f"  snapshot {ts}: {len(archived_ids)} listing IDs found on archived page, "
                  f"{len(overlap)} still in our currently-tracked set")
            if overlap:
                print(f"    overlapping IDs: {sorted(overlap)[:10]}")


def main():
    retry_failed_lookups()
    check_snapshot_overlap()


if __name__ == "__main__":
    main()
