"""
Diagnostic-only script, third and final round of the price-history
investigation. Three independent checks, each targeting a genuinely
different angle from what was already ruled out (Wayback on individual
listing URLs: ~2.5% coverage, PR #40; cross-portal photo-ID matching:
doesn't reach pre-tracking history, PR #41; imot.bg's price-notification
widget: FCM push-only, no queryable history, PR #43):

1. homes.bg raw offer JSON. scraper_homes.py pulls its listings from a
   structured `window.__PRELOADED_STATE__` JSON blob already embedded in
   the page (no HTML scraping needed) but only extracts a handful of the
   fields on each offer object (id, title, location, photo, price, ...).
   Dumps the FULL raw offer dict for a few real offers so a human can see
   every field actually present - there may be an untapped
   previousPrice/oldPrice/discount/createdAt field the current scraper
   just never looked for.

2. Wayback coverage of each portal's SEARCH/CATEGORY page (not individual
   listings). Category pages are far more likely to be crawled/archived
   than deep listing pages since they're linked-to and indexed - if the
   Wayback Machine has multiple old snapshots of e.g. imot.bg's Sofia
   apartment search page, each snapshot shows dozens of listings' prices
   at once, which could be cross-referenced against our own tracked
   listing IDs for real historical prices.

3. Reduced-price ribbon/badge check on live search-grid pages (not
   individual listing detail pages, which were already checked in PR #42
   and only found imot.bg's FCM widget). Portals commonly show a visual
   "reduced" marker on the thumbnail card in search results specifically,
   separate from anything on the full listing page.

Read-only, no data files touched. Prints raw findings for a human to read.
"""

import json
import re
import time
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
CDX_URL = "http://web.archive.org/cdx/search/cdx"
REQUEST_DELAY_SECONDS = 1.5

SEARCH_PAGES = {
    "imoti.net": "https://www.imoti.net/en/obiavi/r/prodava/sofia",
    "alo.bg": "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342",
    "homes.bg": "https://www.homes.bg/",
    "imot.bg": "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya",
    "olx.bg": "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/",
    "bazar.bg": "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia",
    "imoti.bg": "https://imoti.bg/продажби/di:софия/cu:BGN",
}

RIBBON_PATTERNS = [
    r"намален", r"уценк", r"уцене", r"reduced", r"price[\s_-]?drop",
    r"ribbon", r"badge[\s_-]?(sale|discount|reduce)", r"discount",
]
RIBBON_RE = re.compile("|".join(RIBBON_PATTERNS), re.IGNORECASE)


def check_1_homes_bg_raw_json():
    print("\n\n===== CHECK 1: homes.bg raw offer JSON fields =====")
    try:
        resp = requests.get("https://www.homes.bg/", headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"FAILED to fetch homes.bg: {e}")
        return

    m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", resp.text, re.DOTALL)
    if not m:
        print("no __PRELOADED_STATE__ found")
        return
    state = json.loads(m.group(1))
    offers = state.get("data", {}).get("offers", {}).get("result", [])
    print(f"got {len(offers)} offers on page 1")
    for offer in offers[:3]:
        print("---- full raw offer dict ----")
        print(json.dumps(offer, ensure_ascii=False, indent=2))


def check_2_wayback_category_pages():
    print("\n\n===== CHECK 2: Wayback coverage of SEARCH/CATEGORY pages =====")
    for portal, url in SEARCH_PAGES.items():
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            resp = requests.get(
                CDX_URL,
                params={"url": url, "output": "json", "collapse": "digest", "limit": 50, "fl": "timestamp,statuscode"},
                headers={"User-Agent": "bg-property-tracker/1.0 (personal deal-tracking tool, non-commercial)"},
                timeout=25,
            )
            resp.raise_for_status()
            rows = resp.json()
        except Exception as e:
            print(f"{portal}: FAILED - {e}")
            continue
        if not rows or len(rows) < 2:
            print(f"{portal}: 0 captures of {url}")
            continue
        header, *data_rows = rows
        timestamps = sorted(r[0] for r in data_rows)
        print(f"{portal}: {len(data_rows)} captures of {url}, {timestamps[0]} to {timestamps[-1]}")


def check_3_ribbon_badges():
    print("\n\n===== CHECK 3: reduced-price ribbon/badge on live search-grid pages =====")
    for portal, url in SEARCH_PAGES.items():
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            print(f"{portal}: FAILED - {e}")
            continue

        matches = list(RIBBON_RE.finditer(html))
        if not matches:
            print(f"{portal}: no ribbon/badge keyword found on search-grid page")
            continue
        print(f"{portal}: {len(matches)} keyword matches")
        seen_snippets = set()
        for mt in matches[:15]:
            start = max(0, mt.start() - 80)
            end = min(len(html), mt.end() + 80)
            snippet = re.sub(r"\s+", " ", html[start:end]).strip()
            if snippet not in seen_snippets:
                seen_snippets.add(snippet)
                print(f"  ...{snippet}...")


def main():
    check_1_homes_bg_raw_json()
    check_2_wayback_category_pages()
    check_3_ribbon_badges()


if __name__ == "__main__":
    main()
