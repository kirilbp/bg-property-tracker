"""
Scrapes public property-auction listings ("публични продани") from
sales.bcpea.org, the official sales registry run by the Chamber of Private
Enforcement Agents (Камара на частните съдебни изпълнители). These are
court-ordered foreclosure auctions, not ordinary for-sale listings - the
price shown on the site is a legal minimum starting bid ("Начална цена"),
not a negotiable asking price. Tracked here the same way as every other
portal (price history, days-on-market, area averages) since a repeat
listing at a lower price genuinely does mean something concrete: Bulgarian
enforcement procedure re-lists a failed auction at a reduced price, so a
real "price_drop" here reflects a real second/third-round auction, not a
seller softening.

Unlike the other 6 portals (all scoped to Sofia via their own search URL),
this scraper pulls nationwide - the site's own court filter (`court=`)
covers all 28 Bulgarian judicial districts, and capping to Sofia would
throw away most of the ~1,300 total listings for very little request
savings. The frontend has no Sofia-only assumption baked in (area filters,
search, and the lead-generator feature all work off whatever `area` values
actually appear in the data), so this becomes the first real nationwide
data source without needing any frontend change.

Development note: sales.bcpea.org is blocked by this sandbox's network
egress policy (no live requests possible from here), so this scraper was
written entirely from two real saved HTML pages the user provided (a
`/properties` grid page and a `/properties/{id}` detail page, both viewed
live in a real browser) rather than from a live fetch during development,
unlike every other scraper in this repo. The parsing logic below matches
those saved pages exactly and was verified field-by-field against them.

A first live run (via workflow_dispatch) confirmed the one thing that
couldn't be checked from the sandbox: sales.bcpea.org bot-blocks a plain
requests.get() with a 403 on every attempt, retries included - the same
Akamai/Cloudflare-style edge check scraper_olx.py and scraper_imot.py
already document and solve on other portals. Fixed the same way here: a
real headless browser (Playwright/Chromium) gets through cleanly, reusing
one browser page across every grid and detail request rather than
relaunching Chromium per request (same approach as scraper_imot.py).

Listing grid (`/properties?p=N&perpage=36`): each result is a `.item__group`
div, direct child of `.item__container`, containing the property type as a
plain title ("Двустаен апартамент", "Гараж", "Парцел", ...), sqm, a price in
either EUR or BGN (both currencies appear - BGN converted at the fixed
1.95583 peg, same constant scraper.py and scraper_homes.py already use),
the settlement name, and a link to the detail page carrying the listing ID
(confirmed live: no "гр./с." prefix stripped from settlement here). The
grid card's own image is very often a shared "photo-placeholder.png" even
when the listing has real photos - the real gallery only exists on the
detail page.

Each tracked listing's own detail page is fetched once per run (~1,300
requests, 1 req/sec - a couple hours during either GitHub Actions
scheduled hourly window used elsewhere in this repo, so bundled into the
main 6-hourly scrape.yml rather than the 24h scrape-large.yml) for two
things not present in the grid:
  - "Район" (district), a much more precise location than the grid's
    bare settlement name - for Sofia listings this is the same kind of
    neighborhood name (e.g. "Красно село") the other 5 Sofia-scoped
    scrapers already use as `area`, so bcpea listings can genuinely group
    and radius-average alongside them rather than sitting in their own
    unmatched "Sofia" bucket.
  - a real photo, when the grid only had the placeholder.
A detail-page fetch that fails just leaves that listing with the grid's
coarser settlement name and whatever photo the grid had, rather than
aborting the run - same "graceful degradation" pattern as scraper_bazar.py.

No portal-embedded coordinates exist anywhere on this site (confirmed in
both saved pages - no data-lat/lng attributes, no map JS object, despite
leaflet.css being loaded sitewide for some other page), so coordinates
come from the same OpenStreetMap Nominatim geocoder every no-coordinate
portal already shares (geo_utils.Geocoder), queried at district+settlement
level (not full street address) so the disk cache is actually reused
across listings in the same district, same reasoning geo_utils.py already
documents for the other geocoded portals.
"""

import re
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from geo_utils import Geocoder, classify_category

SEARCH_URL = "https://sales.bcpea.org/properties"
BASE_URL = "https://sales.bcpea.org"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_bcpea.json"
LEADS_FILE = OUT_DIR / "leads_bcpea.json"

BGN_TO_EUR = 1.95583
PERPAGE = 36
MAX_PAGES = 100
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
REQUEST_DELAY_SECONDS = 1.0

LISTING_ID_RE = re.compile(r"/properties/(\d+)")
PRICE_RE = re.compile(r"([\d][\d\s\xa0]*(?:[.,]\d{1,2})?)\s*(EUR|лв\.?)", re.IGNORECASE)
SQM_RE = re.compile(r"([\d.,]+)\s?кв\.?м")
PUBLISHED_RE = re.compile(
    r"Публикувано на\s+(\d{1,2})\s+(\S+)\s+(\d{4})\s*г\.?\s*в\s+(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)

BG_MONTHS = {
    "януари": 1, "февруари": 2, "март": 3, "април": 4, "май": 5, "юни": 6,
    "юли": 7, "август": 8, "септември": 9, "октомври": 10, "ноември": 11, "декември": 12,
}


def parse_price_eur(text):
    m = PRICE_RE.search(text or "")
    if not m:
        return None
    amount_str, currency = m.groups()
    amount_str = amount_str.replace("\xa0", "").replace(" ", "")
    if "," in amount_str and "." not in amount_str:
        amount_str = amount_str.replace(",", ".")
    else:
        amount_str = amount_str.replace(",", "")
    try:
        amount = float(amount_str)
    except ValueError:
        return None
    if currency.upper().startswith("EUR"):
        return round(amount)
    return round(amount / BGN_TO_EUR)


def parse_published_at(text):
    m = PUBLISHED_RE.search(text or "")
    if not m:
        return None
    day, month_name, year, hour, minute = m.groups()
    month = BG_MONTHS.get(month_name.lower())
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day), int(hour), int(minute), tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def clean_settlement(text):
    return re.sub(r"^(гр\.|с\.)\s*", "", (text or "").strip()) or None


def fetch_html(page, url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(500)
            return page.content()
        except Exception as e:
            print(f"DEBUG: navigation failed for {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                page.wait_for_timeout(RETRY_BACKOFF_SECONDS * attempt * 1000)
    return None


def label_info(scope, label_text):
    """Find a .label__group in scope whose .label text matches label_text
    (case-insensitive - the same site uses both "НАСЕЛЕНО МЯСТО" on the
    grid and "Населено място" on the detail page for the same field) and
    return its .info text, or None."""
    for group in scope.find_all(class_="label__group"):
        label = group.find(class_="label")
        info = group.find(class_="info")
        if label and info and label.get_text(strip=True).upper() == label_text.upper():
            return info.get_text(" ", strip=True)
    return None


def fetch_listings_page(page, url):
    html = fetch_html(page, url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(class_="item__container")
    if container is None:
        return {}
    cards = container.find_all(class_="item__group", recursive=False)

    listings = {}
    for card in cards:
        link = card.find("a", href=LISTING_ID_RE)
        if not link:
            continue
        listing_id = LISTING_ID_RE.search(link["href"]).group(1)

        title_el = card.find(class_="title")
        category_el = card.find(class_="category")
        price_el = card.find(class_="price")
        date_el = card.find(class_="date")

        title = title_el.get_text(strip=True) if title_el else None
        price_eur = parse_price_eur(price_el.get_text(" ", strip=True)) if price_el else None
        if price_eur is None or price_eur < 100:
            continue

        sqm = None
        if category_el:
            m = SQM_RE.search(category_el.get_text(strip=True))
            if m:
                try:
                    sqm = round(float(m.group(1).replace(",", ".")))
                except ValueError:
                    pass

        settlement = clean_settlement(label_info(card, "НАСЕЛЕНО МЯСТО")) or "България"
        site_updated_at = parse_published_at(date_el.get_text(strip=True)) if date_el else None

        img = card.find("img")
        photo = None
        if img and img.get("src") and "placeholder" not in img["src"].lower():
            src = img["src"]
            photo = src if src.startswith("http") else BASE_URL + src

        href = link["href"]
        full_url = href if href.startswith("http") else BASE_URL + href

        listings[listing_id] = {
            "id": "bcpea_" + listing_id,
            "url": full_url,
            "photo": photo,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": settlement,
            "title": (f"{title}, {settlement}" if title else settlement)[:150],
            "portal": "sales.bcpea.org",
            "site_updated_at": site_updated_at,
            "category": classify_category(title),
            "_settlement": settlement,
        }
    return listings


def fetch_listing_detail(page, listing, geocoder):
    html = fetch_html(page, listing["url"])
    if html is None:
        return
    soup = BeautifulSoup(html, "html.parser")
    expanded = soup.find(class_="item__expanded")
    if expanded is None:
        return

    settlement = listing.get("_settlement")
    district = label_info(expanded, "Район")
    if district:
        listing["area"] = district if (settlement or "").lower() in ("софия", "sofia") \
            else f"{settlement}, {district}" if settlement else district

    if not listing.get("photo"):
        head = expanded.find(class_="head")
        img_tag = head.find("img") if head else None
        if img_tag and img_tag.get("src") and "placeholder" not in img_tag["src"].lower():
            src = img_tag["src"]
            listing["photo"] = src if src.startswith("http") else BASE_URL + src

    query_parts = [p for p in [district, settlement, "България"] if p]
    if query_parts:
        coords = geocoder.geocode(", ".join(query_parts))
        if coords:
            listing["lat"] = coords["lat"]
            listing["lng"] = coords["lng"]


def fetch_listings():
    all_listings = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            url = f"{SEARCH_URL}?perpage={PERPAGE}&p={page_num}"
            page_listings = fetch_listings_page(page, url)
            count = len(page_listings) if page_listings is not None else None
            print(f"DEBUG: page {page_num} listings parsed = {count}")
            if not page_listings:
                break
            all_listings.update(page_listings)

        listings = list(all_listings.values())
        print(f"DEBUG: fetching detail pages for {len(listings)} listings")
        geocoder = Geocoder()
        detail_failures = 0
        for i, l in enumerate(listings, 1):
            page.wait_for_timeout(int(REQUEST_DELAY_SECONDS * 1000))
            fetch_listing_detail(page, l, geocoder)
            if l.get("lat") is None:
                detail_failures += 1
                if detail_failures <= 3:
                    print(f"DEBUG: detail fetch produced no coords for {l['url']}")
            if i % 200 == 0:
                print(f"DEBUG: fetched detail for {i}/{len(listings)} listings ({detail_failures} failures so far)")
        print(f"DEBUG: detail fetch finished, {detail_failures}/{len(listings)} listings got no coords")
        geocoder.save()

        browser.close()

    for l in listings:
        l.pop("_settlement", None)
        l.setdefault("lat", None)
        l.setdefault("lng", None)
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


def compute_leads(history):
    leads = []
    for lid, rec in history.items():
        prices = [s["price_eur"] for s in rec["snapshots"] if s["price_eur"]]
        if not prices:
            continue
        first_price, last_price = prices[0], prices[-1]
        drop_pct = round((first_price - last_price) / first_price * 100, 1) if first_price else 0

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
        site_updated_at = latest.get("site_updated_at")
        reference_date = datetime.fromisoformat(site_updated_at) if site_updated_at else datetime.fromisoformat(rec["first_seen"])
        days_on_market = max((datetime.now(timezone.utc) - reference_date).days, 0)
        score = round(min(max(drop_pct, 0) / 20, 1) * 50 + min(days_on_market / 180, 1) * 50)

        price_per_sqm = round(last_price / latest["sqm"]) if latest.get("sqm") else None

        entry = dict(latest)
        entry["price_eur"] = last_price
        entry["price_per_sqm"] = price_per_sqm
        entry["price_history"] = price_history
        entry["price_drop_count"] = price_drop_count
        entry["drop_pct"] = drop_pct
        entry["days_on_market"] = days_on_market
        entry["score"] = score
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
