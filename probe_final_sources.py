"""
Diagnostic-only: two genuinely untried angles before concluding the
price-history investigation has hit its real ceiling (34/~17,000 listings
backfilled so far, all from Wayback Machine captures of imot.bg/bazar.bg's
search-page FIRST page only).

1. Common Crawl (index.commoncrawl.org) is a separate, independent web
   archive from the Wayback Machine - a different crawler with different
   scope and schedule. It's never been checked this session. Queries its
   public CDX-style index API for the same category URLs (and a sample of
   individual listing URLs) across all 8 portals to see if it has ANY
   coverage Wayback doesn't.

2. The Wayback backfill that found real overlap only ever checked each
   portal's category URL with no ?page=N - meaning only ~40 listings per
   archived snapshot were ever visible (page 1 of results). This checks
   whether Wayback also archived page=2, page=3, etc. of imot.bg's and
   bazar.bg's search results at any point, which would extend coverage
   per snapshot without needing any new data source.

Read-only, no data files touched. Prints raw findings.
"""

import json
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
CC_UA = "bg-property-tracker/1.0 (personal deal-tracking tool, non-commercial; common crawl coverage probe)"
REQUEST_DELAY_SECONDS = 1.5

CATEGORY_PAGES = {
    "imoti.net": "https://www.imoti.net/en/obiavi/r/prodava/sofia",
    "alo.bg": "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342",
    "homes.bg": "https://www.homes.bg/",
    "imot.bg": "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya",
    "olx.bg": "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/",
    "bazar.bg": "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia",
    "imoti.bg": "https://imoti.bg/продажби/di:софия/cu:BGN",
}

# A recent, a mid-range, and an older Common Crawl index - coverage varies
# significantly by crawl, so check a few rather than just the latest.
CC_INDEXES = [
    "CC-MAIN-2026-30",
    "CC-MAIN-2025-38",
    "CC-MAIN-2024-51",
]


def check_common_crawl():
    print("\n\n===== CHECK 1: Common Crawl coverage (separate from Wayback) =====")
    for portal, url in CATEGORY_PAGES.items():
        for index in CC_INDEXES:
            time.sleep(REQUEST_DELAY_SECONDS)
            cc_url = f"https://index.commoncrawl.org/{index}-index"
            try:
                resp = requests.get(
                    cc_url,
                    params={"url": url, "output": "json"},
                    headers={"User-Agent": CC_UA},
                    timeout=25,
                )
                if resp.status_code == 404:
                    print(f"  {portal} [{index}]: 0 captures")
                    continue
                resp.raise_for_status()
                lines = [l for l in resp.text.strip().split("\n") if l.strip()]
                print(f"  {portal} [{index}]: {len(lines)} captures")
                for l in lines[:2]:
                    rec = json.loads(l)
                    print(f"    timestamp={rec.get('timestamp')} status={rec.get('status')} url={rec.get('url')}")
            except Exception as e:
                print(f"  {portal} [{index}]: FAILED - {e}")


def check_wayback_pagination():
    print("\n\n===== CHECK 2: Wayback pagination depth (page=2,3,4,5) for imot.bg/bazar.bg =====")
    targets = {
        "imot.bg": "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya",
        "bazar.bg": "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia",
    }
    for portal, base_url in targets.items():
        for page in [2, 3, 5, 10]:
            paged_url = f"{base_url}?page={page}" if portal == "imot.bg" else f"{base_url}/{page}"
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                resp = requests.get(
                    "https://web.archive.org/cdx/search/cdx",
                    params={"url": paged_url, "output": "json", "collapse": "digest", "limit": 20, "fl": "timestamp,statuscode"},
                    headers={"User-Agent": CC_UA},
                    timeout=25,
                )
                resp.raise_for_status()
                rows = resp.json()
                if not rows or len(rows) < 2:
                    print(f"  {portal} page={page} ({paged_url}): 0 captures")
                    continue
                header, *data_rows = rows
                print(f"  {portal} page={page} ({paged_url}): {len(data_rows)} captures")
            except Exception as e:
                print(f"  {portal} page={page}: FAILED - {e}")


def main():
    check_common_crawl()
    check_wayback_pagination()


if __name__ == "__main__":
    main()
