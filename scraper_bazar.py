"""
Scrapes current Sofia apartment-for-sale listings from bazar.bg.

bazar.bg is a general classifieds site (cars, jobs, real estate, etc), so
this scopes to its own "apartments for sale in Sofia" category URL
(https://bazar.bg/obiavi/prodazhba-apartamenti/sofia) rather than a sitewide
search - the site itself filters out unrelated categories. Confirmed by
sampling 68 live listings during development: 100% were genuine
apartment-for-sale titles ("Продава <N>-СТАЕН, гр. София, <area>" or
"Продава МЕЗОНЕТ/МНОГОСТАЕН, гр. София, <area>"), none from other
categories. bazar.bg has no bot-blocking - plain requests work fine.

Each listing card is the smallest ancestor whose text mentions the price
("<amount> €") exactly once, same "climb from the link" approach as
scraper.py, scraper_alo.py, scraper_imot.py, and scraper_olx.py. Within
that card the price amount and the "€" sign are on separate lines, so the
price is read by finding the "€" line and taking the digits from the line
right before it. bazar.bg's listing grid doesn't show square meters (only
the individual listing page does), so sqm/price_per_sqm are left null here
- the same graceful degradation compute_leads() already applies to any
listing missing sqm.

Search results are paginated with ?page=N, and MAX_PAGES was originally
hard-capped at 3 - confirmed against the live site that real listings
continue at least through page 10 (the site's own paginator), so raised
the cap and let the existing "stop on empty page" logic be the real
stopping condition, same pattern as the other scrapers.

A page fetch retries a few times with backoff before being treated as the
end of pagination (same pattern as scraper.py/scraper_alo.py), so a
transient failure doesn't get mistaken for having reached the last page -
and, since scrape.yml runs all 5 scrapers sequentially with a single git
commit step at the end, an uncaught exception here would otherwise
silently discard every other scraper's output for that run too.

Real coordinates live only on each listing's own detail page, as
data-lat/data-long attributes on its #see_on_map element (confirmed live
via a plain, non-JS HTTP fetch - no headless browser needed). Getting
them means visiting every tracked listing's own page once per scrape, on
top of the grid crawl - a real added cost (~1 extra request per listing,
~1s apart) accepted deliberately so the radius-average feature has real
per-listing coordinates instead of none at all for this portal. A
detail-page fetch that fails just leaves that one listing without
coordinates for this run rather than aborting the whole scrape.
"""

import re
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from geo_utils import classify_category, extract_coords_bazar

SEARCH_URL = "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia"
BASE_URL = "https://bazar.bg"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_bazar.json"
LEADS_FILE = OUT_DIR / "leads_bazar.json"

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1
MAX_PAGES = 60
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
REQUEST_DELAY_SECONDS = 1.0

LISTING_LINK_RE = re.compile(r"obiava-(\d+)")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?€")
AREA_LINE_RE = re.compile(r"^гр\.\s*София,\s*(.+)$")


def fetch_html(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            print(f"DEBUG: request failed for {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    return None


def smallest_container_with_price(link_tag, max_levels=9):
    node = link_tag
    for _ in range(max_levels):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        matches = PRICE_RE.findall(text)
        if len(matches) > MAX_PRICE_MENTIONS:
            return None
        if 1 <= len(matches) <= MAX_PRICE_MENTIONS and len(text) <= MAX_CARD_TEXT_LENGTH:
            return node
    return None


def fetch_listings_page(url):
    html = fetch_html(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]

    listings = {}
    for a in matching_links:
        match = LISTING_LINK_RE.search(a["href"])
        listing_id = match.group(1)
        if listing_id in listings:
            continue

        container = smallest_container_with_price(a)
        if container is None:
            continue

        lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
        if not lines:
            continue

        price_eur = None
        for i, l in enumerate(lines):
            if l == "€" and i > 0:
                # Confirmed against imot.bg (same underlying Focus-backend
                # listings, matched via shared photo IDs): stripping all
                # non-digits from the previous line, unchecked, occasionally
                # swallowed a stray adjacent number (e.g. floor/sqm) into the
                # price when the two got merged with no separator during text
                # extraction - producing a price ~100x too large. Requiring
                # the previous line to be purely digits/whitespace (a real
                # price line never has anything else on it) rejects those.
                prev_line = lines[i - 1]
                if re.fullmatch(r"[\d\s]{3,10}", prev_line):
                    price_eur = int(re.sub(r"\s", "", prev_line))
                break
        if price_eur is None or price_eur < 1000 or price_eur > 10_000_000:
            continue

        area = "Sofia"
        for l in lines:
            m = AREA_LINE_RE.match(l)
            if m:
                area = m.group(1).strip()
                break

        img_url = None
        for img in container.find_all("img"):
            candidate = img.get("src") or img.get("data-src")
            if candidate and "icons/" not in candidate.lower():
                if candidate.startswith("//"):
                    candidate = "https:" + candidate
                elif candidate.startswith("/"):
                    candidate = BASE_URL + candidate
                img_url = candidate
                break

        href = a["href"]
        full_url = href if href.startswith("http") else BASE_URL + href
        title = lines[0] if lines else area

        listings[listing_id] = {
            "id": "bazar_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": None,
            "area": area,
            "title": title[:150],
            "portal": "bazar.bg",
        }
    return listings


def fetch_listing_coords(listings):
    # bazar.bg's grid pages carry no coordinates, but its detail page
    # embeds them directly as data-lat/data-long attributes on the
    # #see_on_map element - confirmed live via a plain (non-JS) HTTP
    # fetch, so this needs no headless browser, just one extra request
    # per listing (same cost pattern as scraper.py's/scraper_alo.py's
    # detail-page fetches).
    total = len(listings)
    for i, l in enumerate(listings, 1):
        time.sleep(REQUEST_DELAY_SECONDS)
        html = fetch_html(l["url"])
        if html is None:
            continue
        coords = extract_coords_bazar(html)
        if coords:
            l["lat"] = coords["lat"]
            l["lng"] = coords["lng"]
        l["category"] = classify_category(l.get("title"))
        if i % 200 == 0:
            print(f"DEBUG: fetched detail coords for {i}/{total} listings")


def fetch_listings():
    all_listings = {}
    for page in range(1, MAX_PAGES + 1):
        url = SEARCH_URL if page == 1 else f"{SEARCH_URL}?page={page}"
        page_listings = fetch_listings_page(url)
        if not page_listings:
            break
        all_listings.update(page_listings)
    listings = list(all_listings.values())
    print(f"DEBUG: fetching detail coords for {len(listings)} listings")
    fetch_listing_coords(listings)
    return listings


def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {}


def save_history(history):
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def update_history(history, listings):
    now = datetime.now(timezone.utc).isoformat()
    for l in listings:
        lid = l["id"]
        if lid not in history:
            history[lid] = {"first_seen": now, "snapshots": []}
        history[lid]["snapshots"].append({"seen_at": now, "price_eur": l["price_eur"]})
        history[lid]["latest"] = l
    return history


# A listing not seen in a scrape for at least this long is treated as no
# longer actually posted on this portal ("removed"), not just skipped by one
# scrape cycle due to pagination timing/site load - same threshold
# detect_relistings.py already uses for the same reason. Once removed,
# days_on_market/score freeze at the day it was last confirmed live instead
# of continuing to climb forever against an ad that's no longer there.
GONE_AFTER = timedelta(hours=20)


def compute_leads(history):
    leads = []
    for lid, rec in history.items():
        prices = [s["price_eur"] for s in rec["snapshots"] if s["price_eur"]]
        if not prices:
            continue
        first_price, last_price = prices[0], prices[-1]
        drop_pct = round((first_price - last_price) / first_price * 100, 1) if first_price else 0
        first_seen = datetime.fromisoformat(rec["first_seen"])
        last_seen = datetime.fromisoformat(rec["snapshots"][-1]["seen_at"])
        source_status = "active" if (datetime.now(timezone.utc) - last_seen) <= GONE_AFTER else "removed"
        effective_now = last_seen if source_status == "removed" else datetime.now(timezone.utc)
        days_on_market = (effective_now - first_seen).days
        score = round(min(max(drop_pct, 0) / 20, 1) * 50 + min(days_on_market / 180, 1) * 50)

        price_history = []
        last_hist_price = None
        for s in rec["snapshots"]:
            p = s.get("price_eur")
            if not p or p == last_hist_price:
                continue
            price_history.append({"date": s["seen_at"], "price_eur": p})
            last_hist_price = p
        price_drop_count = sum(
            1 for i in range(1, len(price_history)) if price_history[i]["price_eur"] < price_history[i - 1]["price_eur"]
        )

        latest = rec["latest"]
        price_per_sqm = round(last_price / latest["sqm"]) if latest.get("sqm") else None

        entry = dict(latest)
        entry["price_eur"] = last_price
        entry["price_per_sqm"] = price_per_sqm
        entry["price_history"] = price_history
        entry["price_drop_count"] = price_drop_count
        entry["drop_pct"] = drop_pct
        entry["days_on_market"] = days_on_market
        entry["score"] = score
        entry["source_status"] = source_status
        entry["removed_at"] = last_seen.isoformat() if source_status == "removed" else None
        leads.append(entry)

    area_totals = {}
    for l in leads:
        if l["price_per_sqm"]:
            area_totals.setdefault(l["area"], []).append(l["price_per_sqm"])
    area_avg = {area: sum(v) / len(v) for area, v in area_totals.items()}

    for l in leads:
        if l["price_per_sqm"] and l["area"] in area_avg:
            avg = area_avg[l["area"]]
            l["area_avg_price_per_sqm"] = round(avg)
            l["pct_vs_area_avg"] = round((l["price_per_sqm"] - avg) / avg * 100, 1)
        else:
            l["area_avg_price_per_sqm"] = None
            l["pct_vs_area_avg"] = None

    leads.sort(key=lambda x: x["score"], reverse=True)
    return leads


def main():
    listings = fetch_listings()
    history = load_history()
    history = update_history(history, listings)
    save_history(history)
    leads = compute_leads(history)
    LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Found {len(listings)} listings, {len(leads)} tracked leads")


if __name__ == "__main__":
    main()
