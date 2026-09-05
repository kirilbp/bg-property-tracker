"""
Scrapes current listings from OLX.bg, nationwide.

OLX.bg blocks plain requests-based fetching (an Akamai-style edge check
returns a 403 before any content), but a real headless browser gets through
cleanly - confirmed via Playwright/Chromium against the live site. Each
listing card is the smallest ancestor whose text mentions the price
("<amount> €") exactly once, same "climb from the link" approach as
scraper.py, scraper_alo.py, and scraper_imot.py. Within that card the text
follows one of two layouts depending on whether the listing is in a city
or a village (confirmed live across Plovdiv/Varna/Burgas oblasts):
    line 0: title (free text)
    line 1: "<price> €"
    line 2 (city listing): "гр. <City>, <area> - Обновено на <date>"
    line 2 (village listing): "с. <Village> - Обновено на <date>"
      (villages have no separate sub-area - the settlement itself is both
      the city and the area)
    line 3: "<sqm> кв.м - <price per sqm>"

Unlike imot.bg/imoti.net (no single "nationwide" URL exists at all), OLX.bg
does have one: dropping the region path segment entirely
(/nedvizhimi-imoti/prodazhbi/, no oblast-<slug> suffix) returns real,
distinct listings - but it turned out to hit the SAME real per-query depth
cap (~page 26-27, ~1,000-1,400 listings) as any single oblast-scoped query,
live-verified against Sofia and Plovdiv independently in the same browser
session. So the bare nationwide URL alone can't carry full national
coverage; oblast-level slicing (OBLAST_SLUGS below, each a live-verified
/nedvizhimi-imoti/prodazhbi/oblast-<slug>/ URL) is used instead, the same
pattern imot.bg needed at city granularity. 26 of Bulgaria's 28
administrative oblasts resolved to a real olx.bg oblast page (Targovishte
and Sofia-oblast/Sofia-province - distinct from Sofia-city, which IS
covered - didn't resolve to a guessed slug and are skipped).

Because oblast slicing is coarser than a real city (an oblast query returns
listings from every settlement in it, not just its namesake city), each
listing's city/area is parsed from its own card text rather than trusted
from the query - same reasoning as alo.bg's LOCATION_RE, just with the
extra city-vs-village branch above.

Search results are paginated with ?page=N (confirmed via the site's own
paginator). A page navigation retries a few times with backoff before
being treated as the end of pagination, so a transient failure doesn't get
mistaken for having reached the last page - and, since scrape.yml runs
several scrapers sequentially with a single git commit step at the end, an
uncaught exception here would otherwise silently discard every other
scraper's output for that run too. Past the real depth cap boundary, the
site still renders a page with exactly one stray listing link (not zero) -
confirmed live - so pagination stops on <=1 real links, not only on 0.

Line 2's "Обновено на <date>" (confirmed live format: "20 август 2026 г.")
or bare "Днес"/"Вчера" reflects when the listing was actually last updated
on OLX, and is parsed into a real date so days_on_market/motivation score
are computed from that instead of purely from when we first scraped the
listing - otherwise a listing that's actually been up for months shows as
"0 days on market" just because we only just started tracking it.

olx.bg carries no coordinates anywhere on its own pages, but every
listing's real settlement/neighborhood name is genuinely geocodable -
resolved here via OpenStreetMap Nominatim (geo_utils.Geocoder). At
nationwide scale, doing that live and inline during the scrape doesn't fit
in a single run (the same problem scraper_homes.py hit first - see its
module docstring), so this only does a cache-only lookup and leaves the
rest for backfill_geocode_olx.py to fill in as a separate, decoupled pass.
This portal's search also isn't apartments-only (it's "all real estate for
sale"), so each listing's category (apartment/house/land/commercial) is
classified from its title too, for the frontend's same-category
radius-average feature.
"""

import re
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from geo_utils import Geocoder, classify_category, extract_description_ldjson, extract_photos_ldjson, prune_snapshots

BASE_URL = "https://www.olx.bg"
SEARCH_BASE = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# (oblast display name, URL slug) - each slug live-verified to return a
# real olx.bg oblast page (status 200, real listing links) before being
# trusted here; see the module docstring for the diagnostic trail.
OBLAST_SLUGS = [
    ("София", "oblast-sofiya-grad"),
    ("Пловдив", "oblast-plovdiv"),
    ("Варна", "oblast-varna"),
    ("Бургас", "oblast-burgas"),
    ("Русе", "oblast-ruse"),
    ("Стара Загора", "oblast-stara-zagora"),
    ("Плевен", "oblast-pleven"),
    ("Сливен", "oblast-sliven"),
    ("Добрич", "oblast-dobrich"),
    ("Шумен", "oblast-shumen"),
    ("Перник", "oblast-pernik"),
    ("Хасково", "oblast-haskovo"),
    ("Ямбол", "oblast-yambol"),
    ("Пазарджик", "oblast-pazardzhik"),
    ("Благоевград", "oblast-blagoevgrad"),
    ("Велико Търново", "oblast-veliko-tarnovo"),
    ("Враца", "oblast-vratsa"),
    ("Габрово", "oblast-gabrovo"),
    ("Видин", "oblast-vidin"),
    ("Кюстендил", "oblast-kyustendil"),
    ("Кърджали", "oblast-kardzhali"),
    ("Монтана", "oblast-montana"),
    ("Ловеч", "oblast-lovech"),
    ("Силистра", "oblast-silistra"),
    ("Разград", "oblast-razgrad"),
    ("Смолян", "oblast-smolyan"),
]

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_olx.json"
LEADS_FILE = OUT_DIR / "leads_olx.json"

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1
# The real per-query depth cap sits around page 26-27 (~1,000-1,400
# listings) - 30 gives a small safety margin before giving up on an oblast
# without wasting requests deep past the cap.
MAX_PAGES = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
MAX_CONSECUTIVE_PAGE_FAILURES = 5

LISTING_LINK_RE = re.compile(r"/d/ad/[^\"'#]*-ID(\w+)\.html")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?€")
PRICE_LINE_RE = re.compile(r"^([\d\s]{3,10})\s?€$")
CITY_AREA_LINE_RE = re.compile(r"^гр\.\s*(.+?),\s*(.+?)\s-\s")
VILLAGE_LINE_RE = re.compile(r"^с\.\s*(.+?)\s-\s")
UPDATED_RE = re.compile(r"-\s*(Днес|Вчера|Обновено на\s+(\d{1,2})\s+(\S+)\s+(\d{4})\s*г\.?)", re.IGNORECASE)
SQM_RE = re.compile(r"([\d.,]+)\s?кв\.?м")

BG_MONTHS = {
    "януари": 1, "февруари": 2, "март": 3, "април": 4, "май": 5, "юни": 6,
    "юли": 7, "август": 8, "септември": 9, "октомври": 10, "ноември": 11, "декември": 12,
}


def parse_site_updated_at(line):
    m = UPDATED_RE.search(line)
    if not m:
        return None
    now = datetime.now(timezone.utc)
    label = m.group(1).lower()
    if label.startswith("днес"):
        return now.isoformat()
    if label.startswith("вчера"):
        return (now - timedelta(days=1)).isoformat()
    day, month_name, year = m.group(2), m.group(3).lower(), m.group(4)
    month = BG_MONTHS.get(month_name)
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day), tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def fetch_html(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)
    # Listing photos are lazy-loaded as cards enter the viewport, so scroll
    # all the way to the bottom (slowly, so each batch has time to actually
    # finish loading, not just get requested) to force them all in before
    # reading src.
    for _ in range(35):
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(500)
        at_bottom = page.evaluate(
            "window.innerHeight + window.scrollY >= document.body.scrollHeight - 10"
        )
        if at_bottom:
            break
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    return page.content()


def smallest_container_with_price(link_tag, max_levels=8):
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


def fetch_html_with_retries(page, url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fetch_html(page, url)
        except Exception as e:
            print(f"DEBUG: navigation failed for {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                page.wait_for_timeout(RETRY_BACKOFF_SECONDS * attempt * 1000)
    return None


def fetch_listings_page(page, url, seen, geocoder, oblast_display):
    html = fetch_html_with_retries(page, url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]

    for a in matching_links:
        match = LISTING_LINK_RE.search(a["href"])
        listing_id = match.group(1)
        if listing_id in seen:
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

        city = oblast_display
        area = oblast_display
        site_updated_at = None
        for l in lines:
            m = CITY_AREA_LINE_RE.match(l)
            if m:
                city, area = m.group(1).strip(), m.group(2).strip()
                site_updated_at = parse_site_updated_at(l)
                break
            m2 = VILLAGE_LINE_RE.match(l)
            if m2:
                city = area = m2.group(1).strip()
                site_updated_at = parse_site_updated_at(l)
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
            if candidate and candidate.startswith("http") and "icon" not in candidate.lower():
                img_url = candidate
                break

        href = a["href"]
        full_url = href if href.startswith("http") else BASE_URL + href
        title = f"{lines[0]}, {area}" if lines else area
        coords = geocoder.geocode_cached_only(f"{area}, {city}, България")

        seen[listing_id] = {
            "id": "olx_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": area,
            "city": city,
            "title": title[:150],
            "portal": "olx.bg",
            "site_updated_at": site_updated_at,
            "lat": coords["lat"] if coords else None,
            "lng": coords["lng"] if coords else None,
            "category": classify_category(lines[0] if lines else title),
        }
    return len(matching_links)


def goto_with_retries(page, url):
    # Lighter-weight than fetch_html()/fetch_html_with_retries() above - those
    # scroll the whole page to force lazy-loaded card photos into the DOM,
    # which only matters on a search-results grid page, not a single
    # listing's own detail page (nothing here is lazy-loaded behind scroll).
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
            return page.content()
        except Exception as e:
            print(f"DEBUG: navigation failed for {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                page.wait_for_timeout(RETRY_BACKOFF_SECONDS * attempt * 1000)
    return None


def fetch_listing_detail(page, listing):
    # Marked unconditionally so a backlog scan can tell "already attempted,
    # nothing more to gain" apart from "never visited yet" - same marker
    # pattern scraper.py/scraper_bcpea.py/scraper_imot.py already
    # established for their own detail backfills.
    listing["detail_checked"] = True
    html = goto_with_retries(page, listing["url"])
    if html is None:
        return
    description = extract_description_ldjson(html)
    if description:
        listing["description"] = description
    # Best-effort - olx.bg wasn't directly reachable to confirm its ld+json
    # blob carries an "image" key the way bazar.bg's does (see
    # geo_utils.extract_photos_ldjson()'s docstring); harmlessly returns
    # nothing if it doesn't.
    photos = extract_photos_ldjson(html)
    if photos:
        listing["photos"] = photos


def fetch_listing_details(listings):
    # One shared browser/page reused across the whole batch, same as
    # scraper_imot.py's own detail backfill.
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()
        for listing in listings:
            fetch_listing_detail(page, listing)
        browser.close()


def fetch_listings():
    seen = {}
    geocoder = Geocoder()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()

        for oblast_display, slug in OBLAST_SLUGS:
            search_url = f"{SEARCH_BASE}/{slug}/"
            oblast_before = len(seen)
            consecutive_failures = 0
            for page_num in range(1, MAX_PAGES + 1):
                url = search_url if page_num == 1 else f"{search_url}?page={page_num}"
                link_count = fetch_listings_page(page, url, seen, geocoder, oblast_display)
                print(f"DEBUG: {oblast_display} page {page_num} links matching listing URL pattern = {link_count}")
                if link_count is None:
                    # A failed fetch (all in-page retries exhausted) is not
                    # the real end-of-results signal (link_count <= 1 below
                    # is) - giving up on the whole oblast here would silently
                    # truncate every remaining page after one bad request,
                    # the same bug found in scraper.py/scraper_alo.py/
                    # scraper_imot.py/scraper_homes.py. Skip it and keep
                    # going, only giving up on the oblast after several in a
                    # row.
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_PAGE_FAILURES:
                        break
                    continue
                consecutive_failures = 0
                if link_count <= 1:
                    break
            print(f"DEBUG: {oblast_display} done, {len(seen) - oblast_before} new listings")

        browser.close()
    geocoder.save()
    return list(seen.values())


def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {}


def save_history(history):
    prune_snapshots(history)
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

        last_seen = datetime.fromisoformat(rec["snapshots"][-1]["seen_at"])
        source_status = "active" if (datetime.now(timezone.utc) - last_seen) <= GONE_AFTER else "removed"
        effective_now = last_seen if source_status == "removed" else datetime.now(timezone.utc)

        latest = rec["latest"]
        site_updated_at = latest.get("site_updated_at")
        reference_date = datetime.fromisoformat(site_updated_at) if site_updated_at else datetime.fromisoformat(rec["first_seen"])
        days_on_market = max((effective_now - reference_date).days, 0)
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
