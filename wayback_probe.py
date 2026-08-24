"""
Diagnostic-only script: checks how many of our tracked listing URLs have
ANY snapshot at all in the Wayback Machine, before investing in building
full per-portal archived-page price parsers.

This exists because sales.bcpea.org's public price-change history isn't
something any of the 8 portals expose themselves - only our own scraper's
periodic re-visits build that up, starting from whenever we first saw each
listing. The only other possible source of a listing's price *before* we
started tracking it would be an old snapshot of that exact URL already
sitting in the Internet Archive's Wayback Machine. Individual real-estate
listing pages are rarely linked-to or crawled by outside bots, so the
realistic expectation here is a low hit rate - this script's job is to
measure that rate for real, on real URLs, before writing (and trusting)
any actual price-extraction logic against archived HTML none of us have
seen yet.

Read-only and side-effect-free: doesn't touch history_*.json or
leads_*.json, just samples N real URLs per portal, queries the Wayback
CDX API (https://archive.org/help/wayback_api.php) for each, and prints a
per-portal summary - total sampled, how many have 1+ snapshot, and the
date range of whatever was found. A human (or a follow-up script) decides
what to do with that from here.
"""

import json
import random
import time
import urllib.parse
from pathlib import Path

import requests

CDX_URL = "http://web.archive.org/cdx/search/cdx"
USER_AGENT = "bg-property-tracker/1.0 (personal deal-tracking tool, non-commercial; wayback coverage probe)"
REQUEST_DELAY_SECONDS = 2.0
SAMPLE_SIZE_PER_PORTAL = 15
MAX_RETRIES = 2

DATA_DIR = Path(__file__).parent / "data"
PORTAL_FILES = {
    "imoti.net": "leads.json",
    "alo.bg": "leads_alo.json",
    "homes.bg": "leads_homes.json",
    "imot.bg": "leads_imot.json",
    "olx.bg": "leads_olx.json",
    "bazar.bg": "leads_bazar.json",
    "imoti.bg": "leads_imoti_bg.json",
    "sales.bcpea.org": "leads_bcpea.json",
}


def strip_query(url):
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def query_cdx(url):
    """Returns a list of {timestamp, statuscode} dicts for this URL's
    known captures (collapse=digest so repeated identical content across
    many captures counts once), or None on a request failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                CDX_URL,
                params={
                    "url": url,
                    "output": "json",
                    "collapse": "digest",
                    "limit": 30,
                    "fl": "timestamp,statuscode",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                return []
            header, *data_rows = rows
            return [dict(zip(header, row)) for row in data_rows]
        except Exception as e:
            print(f"DEBUG: CDX query failed for {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(REQUEST_DELAY_SECONDS * attempt)
    return None


def probe_portal(portal, filename):
    path = DATA_DIR / filename
    if not path.exists():
        print(f"\n=== {portal}: {filename} not found, skipping ===")
        return

    listings = json.loads(path.read_text(encoding="utf-8"))
    if not listings:
        print(f"\n=== {portal}: no listings, skipping ===")
        return

    sample = random.sample(listings, min(SAMPLE_SIZE_PER_PORTAL, len(listings)))
    print(f"\n=== {portal}: probing {len(sample)}/{len(listings)} listings ===")

    with_snapshots = 0
    failures = 0
    earliest_overall = None
    for l in sample:
        url = strip_query(l["url"])
        time.sleep(REQUEST_DELAY_SECONDS)
        rows = query_cdx(url)
        if rows is None:
            failures += 1
            print(f"  FAILED: {url}")
            continue
        if rows:
            with_snapshots += 1
            timestamps = sorted(r["timestamp"] for r in rows)
            earliest, latest = timestamps[0], timestamps[-1]
            if earliest_overall is None or earliest < earliest_overall:
                earliest_overall = earliest
            print(f"  HIT ({len(rows)} captures, {earliest} to {latest}): {url}")
        else:
            print(f"  miss: {url}")

    print(f"--- {portal} summary: {with_snapshots}/{len(sample)} sampled listings have "
          f"1+ archived snapshot, {failures} request failures, "
          f"earliest capture seen: {earliest_overall}")


def main():
    for portal, filename in PORTAL_FILES.items():
        probe_portal(portal, filename)


if __name__ == "__main__":
    main()
