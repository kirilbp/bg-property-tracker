"""
Scrapes current Sofia apartment-for-sale listings from imoti.bg.

imoti.bg's homepage location filter is a select2 widget wrapping a hidden
native <select>, with the actual URL built client-side on search-button
click - there's no separate API call to intercept. But the resulting
filtered URL (https://imoti.bg/продажби/di:софия/cu:BGN) turned out to be
stateless/bookmarkable: it's reachable directly via plain requests, with no
need to repeat the dropdown-click simulation on every scrape run (confirmed
against the live site). Pagination uses the same URL with a "/page:N" suffix
(imoti.bg itself showed up to 8 pages of Sofia sales listings across all
property types at the time of testing).

imoti.bg mixes all property types (apartments, houses, commercial, etc.)
under this URL, since the type_id filter wasn't also applied - so this
scopes to apartments specifically by checking each listing link's category
slug (едностаен-апартамент, двустаен-апартамент, etc.), matching the
apartment-only scope of the other scrapers.

Each listing card is the smallest ancestor whose text mentions the price
("<amount> EUR") exactly once, same "climb from the link" approach as
scraper.py, scraper_alo.py, scraper_imot.py, scraper_olx.py, and
scraper_bazar.py. Within that card the text follows a consistent per-line
layout:
    line 0: "<price> EUR"
    line 1: property type (e.g. "Тристаен апартамент")
    line 2: "София, <area>"
    line 3: "<sqm> кв.м."

A page fetch retries a few times with backoff before being treated as the
end of pagination, so a transient failure doesn't get mistaken for having
reached the last page - and, since scrape.yml runs all 5 scrapers
sequentially with a single git commit step at the end, an uncaught
exception here would otherwise silently discard every other scraper's
output for that run too.

imoti.bg genuinely carries no coordinates anywhere in its own pages -
confirmed by a real headless browser (cookie consent handled, WebGL
software rendering enabled, navigator.webdriver patched away) finding no
map DOM node, no live google.maps.Map object, and no maps iframe on a
real listing, plus a plain static-HTML fetch turning up nothing either.
So each listing's real area name (line 2's "София, <area>") is geocoded
via OpenStreetMap Nominatim instead (geo_utils.Geocoder), cached by the
query string so the same area name reused across many listings costs one
real geocode request total. A category is attached too (always
"apartment" here, since this scraper is already apartments-only via
APARTMENT_SLUGS) for consistency with the other portals feeding the
frontend's same-category radius-average feature.
"""

import re
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from geo_utils import Geocoder, classify_category

BASE_URL = "https://imoti.bg"
SEARCH_URL = "https://imoti.bg/продажби/di:софия/cu:BGN"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_imoti_bg.json"
LEADS_FILE = OUT_DIR / "leads_imoti_bg.json"

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1
MAX_PAGES = 12
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

APARTMENT_SLUGS = [
    "едностаен-апартамент", "двустаен-апартамент", "тристаен-апартамент",
    "четиристаен-апартамент", "многостаен", "мезонет",
]
LISTING_LINK_RE = re.compile(
    r"/продажби/(?:" + "|".join(APARTMENT_SLUGS) + r")/софия/([^/]+)-(\d{5,})\.htm"
)
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?EUR")
PRICE_LINE_RE = re.compile(r"^([\d\s]{3,10})\s?EUR$")
AREA_LINE_RE = re.compile(r"^София,\s*(.+)$")
SQM_RE = re.compile(r"([\d.,]+)\s?кв\.?м\.?")


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
    # imoti.bg's price sits in a deeper single-purpose element than the area
    # line, so unlike the other scrapers the first ancestor with exactly one
    # price mention is too small to also contain the area - keep climbing
    # and return the largest ancestor that still satisfies the constraints.
    node = link_tag
    best = None
    for _ in range(max_levels):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        matches = PRICE_RE.findall(text)
        if len(matches) > MAX_PRICE_MENTIONS:
            break
        if 1 <= len(matches) <= MAX_PRICE_MENTIONS and len(text) <= MAX_CARD_TEXT_LENGTH:
            best = node
    return best


def fetch_listings_page(url, geocoder):
    html = fetch_html(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]

    listings = {}
    for a in matching_links:
        match = LISTING_LINK_RE.search(a["href"])
        listing_id = match.group(2)
        if listing_id in listings:
            continue

        container = smallest_container_with_price(a)
        if container is None:
            continue

        lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
        if not lines:
            continue

        price_eur = None
        for l in lines:
            m = PRICE_LINE_RE.match(l)
            if m:
                price_eur = int(re.sub(r"\D", "", m.group(1)))
                break
        if price_eur is None or price_eur < 1000:
            continue

        area = "Sofia"
        for l in lines:
            m = AREA_LINE_RE.match(l)
            if m:
                area = m.group(1).strip()
                break

        sqm = None
        for l in lines:
            m = SQM_RE.search(l)
            if m:
                try:
                    sqm = round(float(m.group(1).replace(",", ".")))
                except ValueError:
                    pass
                break

        img_url = None
        for img in container.find_all("img"):
            candidate = img.get("src") or img.get("data-src")
            if candidate and "icons/" not in candidate.lower():
                img_url = urljoin(BASE_URL + "/", candidate)
                break

        href = a["href"]
        full_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        title = lines[1] if len(lines) > 1 else area
        full_title = f"{title}, {area}"[:150]
        coords = geocoder.geocode(f"{area}, София, България")

        listings[listing_id] = {
            "id": "imotibg_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": area,
            "title": full_title,
            "portal": "imoti.bg",
            "lat": coords["lat"] if coords else None,
            "lng": coords["lng"] if coords else None,
            "category": classify_category(full_title),
        }
    return listings


def fetch_listings():
    all_listings = {}
    geocoder = Geocoder()
    for page in range(1, MAX_PAGES + 1):
        url = SEARCH_URL if page == 1 else f"{SEARCH_URL}/page:{page}"
        page_listings = fetch_listings_page(url, geocoder)
        if not page_listings:
            break
        all_listings.update(page_listings)
    geocoder.save()
    return list(all_listings.values())


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
