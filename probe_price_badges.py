"""
Diagnostic-only script: checks whether any of our 8 source portals expose a
listing's ORIGINAL or previously-reduced price directly on the listing's own
page (a "price reduced" badge, a struck-through old price, an embedded price
history, etc.).

This matters because it would be a real, portal-native source of price
history from BEFORE we started tracking a listing - unlike two things already
ruled out this session: the Wayback Machine (2.5% coverage, see the removed
wayback_probe.py / PR #40) and cross-portal photo-ID matching (proved that
imot.bg and bazar.bg share a backend and 56% of listings overlap, but on
inspection both portals only ever show the CURRENT price - matching them
doesn't recover any price from before our own tracking began either).

Read-only and side-effect-free: doesn't touch history_*.json or
leads_*.json, just fetches N real listing detail pages per portal and
searches the raw HTML for keywords/markup patterns that Bulgarian and
English real-estate sites commonly use to show a price cut (BG: "предишна
цена", "стара цена", "намалена цена", "намаление"; EN: "previous price",
"old price", "price reduced", "price drop"; markup: <del>/<s> tags or
"line-through"/"old-price" CSS classes near a price figure). Prints a
snippet of context around every hit so a human can judge whether it's a
real signal or a false positive (e.g. an unrelated promo banner), plus a
per-portal hit count. A human decides what to do with that from here.
"""

import json
import random
import re
import time
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
REQUEST_DELAY_SECONDS = 1.5
SAMPLE_SIZE_PER_PORTAL = 10
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 4
CONTEXT_CHARS = 90

DATA_DIR = Path(__file__).parent / "data"
PORTAL_FILES = {
    "imoti.net": "leads.json",
    "alo.bg": "leads_alo.json",
    "homes.bg": "leads_homes.json",
    "imot.bg": "leads_imot.json",
    "olx.bg": "leads_olx.json",
    "bazar.bg": "leads_bazar.json",
    "imoti.bg": "leads_imoti_bg.json",
    # sales.bcpea.org excluded: public auctions publish one starting bid,
    # not a seller-adjustable asking price, so "price reduced" doesn't apply.
}

# Each pattern is checked case-insensitively against the raw HTML text.
KEYWORD_PATTERNS = [
    r"предишна\s+цена",
    r"стара\s+цена",
    r"намалена\s+цена",
    r"намаление\s+на\s+цена",
    r"оригинална\s+цена",
    r"цена\s+преди",
    r"previous\s+price",
    r"old[\s-]?price",
    r"price\s+reduced",
    r"price\s+drop",
    r"price\s+history",
    r"ценова\s+история",
]
MARKUP_PATTERNS = [
    r"<del[^>]*>[^<]{0,40}(?:€|лв)",
    r"<s[^>]*>[^<]{0,40}(?:€|лв)",
    r"line-through",
    r"old-price",
    r"price-old",
    r"price_old",
]
ALL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in KEYWORD_PATTERNS + MARKUP_PATTERNS]


def fetch_with_retries(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"DEBUG: request failed for {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
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

    hits = 0
    failures = 0
    for l in sample:
        url = l["url"]
        time.sleep(REQUEST_DELAY_SECONDS)
        html = fetch_with_retries(url)
        if html is None:
            failures += 1
            print(f"  FAILED: {url}")
            continue

        found_any = False
        for pat in ALL_PATTERNS:
            for m in pat.finditer(html):
                found_any = True
                start = max(0, m.start() - CONTEXT_CHARS)
                end = min(len(html), m.end() + CONTEXT_CHARS)
                snippet = re.sub(r"\s+", " ", html[start:end]).strip()
                print(f"  HIT [{pat.pattern}] {url}\n    ...{snippet}...")
        if found_any:
            hits += 1
        else:
            print(f"  miss: {url}")

    print(f"--- {portal} summary: {hits}/{len(sample)} sampled listings show "
          f"a price-history/reduction signal, {failures} request failures")


def main():
    for portal, filename in PORTAL_FILES.items():
        probe_portal(portal, filename)


if __name__ == "__main__":
    main()
