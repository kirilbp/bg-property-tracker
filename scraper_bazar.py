"""
Scrapes current apartment-for-sale listings from bazar.bg, nationwide.

bazar.bg is a general classifieds site (cars, jobs, real estate, etc), so
this scopes to its own "apartments for sale" category URL per city
(https://bazar.bg/obiavi/prodazhba-apartamenti/<city>) rather than a
sitewide search - the site itself filters out unrelated categories.
Confirmed by sampling 68 live listings during development: 100% were
genuine apartment-for-sale titles ("Продава <N>-СТАЕН, гр. <City>, <area>"
or "Продава МЕЗОНЕТ/МНОГОСТАЕН, гр. <City>, <area>"), none from other
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

Nationwide mechanism: bazar.bg supports BOTH a bare "drop the city
segment" nationwide URL AND per-city path segments (unlike imot.bg/
imoti.net, which need per-city slugs exclusively) - but live pagination
testing found the site clamps out-of-range page numbers to its real last
page and repeats it verbatim, rather than ever showing an empty page
(confirmed: page 30's and page 50's listing ID sets were byte-identical).
That means the old "stop on empty page" logic never actually fires past
the real depth - it would silently loop through every remaining page
re-fetching the same content. Real content on a single query stops
changing around page 26, so CITY_SLUGS (each a live-verified
/obiavi/prodazhba-apartamenti/<slug> URL, 29 of Bulgaria's 30 largest
cities - Yambol's guessed slug didn't resolve and is skipped) slices by
city instead, and pagination now stops as soon as a page's listing ID set
exactly matches the previous page's (the real plateau signal), not just
on an empty page - confirmed live that a different city query still gets
fresh content in the same session after a previous city has already
plateaued.

Each listing's city is tagged directly from which CITY_SLUGS entry
produced it (known from the URL, not re-parsed from text) - matches the
pattern already used for imot.bg's nationwide conversion. AREA_LINE_RE
generalizes away from the old hardcoded "гр. София," match to any
"гр. <City>," prefix, live-verified against real Plovdiv/Varna/Burgas
card text.

Search results are paginated with ?page=N. A page fetch retries a few
times with backoff before being treated as the end of pagination (same
pattern as scraper.py/scraper_alo.py), so a transient failure doesn't get
mistaken for having reached the last page - and, since scrape.yml runs
several scrapers sequentially with a single git commit step at the end,
an uncaught exception here would otherwise silently discard every other
scraper's output for that run too.

Real coordinates live only on each listing's own detail page, as
data-lat/data-long attributes on its #see_on_map element (confirmed live
via a plain, non-JS HTTP fetch - no headless browser needed). At
nationwide scale, visiting every tracked listing's own page during the
main scrape doesn't fit in a single run (the same problem
scraper_homes.py hit first - see its module docstring), so this no longer
does that inline - backfill_detail_bazar.py does it as a separate,
decoupled pass. A detail-page fetch that fails there just leaves that one
listing without coordinates for that run rather than aborting the whole
backfill.
"""

import re
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from geo_utils import classify_category

BASE_URL = "https://bazar.bg"
SEARCH_BASE = "https://bazar.bg/obiavi/prodazhba-apartamenti"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

# (city display name, URL slug) - each slug live-verified to return a real
# bazar.bg city page (status 200, real listing links) before being trusted
# here; see the module docstring for the diagnostic trail.
CITY_SLUGS = [
    ("София", "sofia"),
    ("Пловдив", "plovdiv"),
    ("Варна", "varna"),
    ("Бургас", "burgas"),
    ("Русе", "ruse"),
    ("Стара Загора", "stara-zagora"),
    ("Плевен", "pleven"),
    ("Сливен", "sliven"),
    ("Добрич", "dobrich"),
    ("Шумен", "shumen"),
    ("Перник", "pernik"),
    ("Хасково", "haskovo"),
    ("Пазарджик", "pazardzhik"),
    ("Благоевград", "blagoevgrad"),
    ("Велико Търново", "veliko-tarnovo"),
    ("Враца", "vratsa"),
    ("Габрово", "gabrovo"),
    ("Видин", "vidin"),
    ("Асеновград", "asenovgrad"),
    ("Казанлък", "kazanlak"),
    ("Кюстендил", "kyustendil"),
    ("Кърджали", "kardzhali"),
    ("Монтана", "montana"),
    ("Димитровград", "dimitrovgrad"),
    ("Търговище", "targovishte"),
    ("Ловеч", "lovech"),
    ("Силистра", "silistra"),
    ("Дупница", "dupnitsa"),
    ("Свищов", "svishtov"),
]

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_bazar.json"
LEADS_FILE = OUT_DIR / "leads_bazar.json"

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1
# Real content on a single city query stops changing around page 26 (the
# site clamps out-of-range page numbers to the last real page instead of
# ever going empty - see the module docstring) - 30 gives a small safety
# margin before the plateau-detection stop condition kicks in.
MAX_PAGES = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
MAX_CONSECUTIVE_PAGE_FAILURES = 5

LISTING_LINK_RE = re.compile(r"obiava-(\d+)")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?€")
AREA_LINE_RE = re.compile(r"^гр\.\s*\S.*?,\s*(.+)$")


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


def fetch_listings_page(url, city_display):
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

        area = city_display
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
            "city": city_display,
            "title": title[:150],
            "portal": "bazar.bg",
            "lat": None,
            "lng": None,
            "category": classify_category(title),
        }
    return listings


def fetch_listings():
    all_listings = {}
    for city_display, slug in CITY_SLUGS:
        search_url = f"{SEARCH_BASE}/{slug}"
        city_before = len(all_listings)
        prev_ids = None
        consecutive_failures = 0
        for page_num in range(1, MAX_PAGES + 1):
            url = search_url if page_num == 1 else f"{search_url}?page={page_num}"
            page_listings = fetch_listings_page(url, city_display)
            if page_listings is None:
                # A failed fetch (all in-request retries exhausted) is not
                # the real end-of-results signal (an empty page, or the
                # clamped-page-id-repeat check below, is) - giving up on the
                # whole city here would silently truncate every remaining
                # page after one bad request, the same bug found in
                # scraper.py/scraper_alo.py/scraper_imot.py/scraper_homes.py/
                # scraper_olx.py. Skip it and keep going, only giving up on
                # the city after several in a row.
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_PAGE_FAILURES:
                    break
                continue
            consecutive_failures = 0
            page_ids = frozenset(page_listings.keys())
            print(f"DEBUG: {city_display} page {page_num} links matching listing URL pattern = {len(page_listings)}")
            if not page_listings or page_ids == prev_ids:
                # Empty page, or the site clamped this out-of-range page
                # number back to the same last real page (its listing ID
                # set is identical to the previous page's) - either way
                # there's nothing new past this point.
                break
            all_listings.update(page_listings)
            prev_ids = page_ids
        print(f"DEBUG: {city_display} done, {len(all_listings) - city_before} new listings")

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
