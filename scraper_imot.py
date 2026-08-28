"""
Scrapes current listings from imot.bg, nationwide.

imot.bg blocks plain requests-based fetching (a Cloudflare/Akamai-style bot
check returns a JS challenge page instead of real content), but a real
headless browser gets through cleanly - confirmed via Playwright/Chromium
against the live site. Each listing card is the smallest ancestor whose
text mentions the price ("<amount> €") exactly once, same "climb from the
link" approach as scraper.py and scraper_alo.py. Within that card the text
follows a consistent per-line layout, confirmed identical across Sofia,
Plovdiv, Varna and Burgas:
    line 0: title (e.g. "Продава 2-СТАЕН")
    line 1: "град <City>, <area>"
    line 2: "<price> €"
    line 3: "<sqm> кв.м, <floor/description/phone...>"

Unlike homes.bg/alo.bg (a single URL switch drops the location filter for
a genuine nationwide result) or imoti.net (city segments requiring their
own English-spelled slug), imot.bg has no "all cities" URL at all AND its
own per-query pagination hits a real depth cap around page 27-28
(~1,080 listings at 40/page) regardless of scope - live-verified: Sofia,
Plovdiv, and even the bare /obiavi/prodazhbi URL (no city segment) all cap
at the same boundary independently. Extensive live probing (a price-filter
form turned out to be 82 hidden POST fields with no usable GET param, and
no district/kvartal URL segment exists either - see git history for the
full diagnostic trail) found no way to sub-slice a single over-cap city
further. City-only slicing (CITY_SLUGS below, each a live-verified
/obiavi/prodazhbi/grad-<slug> URL) is therefore the best available
coverage: every city fits comfortably under the cap except Sofia itself
(confirmed 1000+ listings by the site's own UI), which is accepted as
still capped at ~1,080 rather than fully complete - a known, documented
limitation, not a bug. 24 of 29 canonical BG_CITIES resolved to a real
imot.bg city page; the other 5 (smaller towns - Asenovgrad, Kazanlak,
Dimitrovgrad, Dupnitsa, Svishtov) don't appear to have their own page and
are skipped.

Each listing's city is tagged directly from which CITY_SLUGS entry
produced it (known from the URL, not re-parsed from text) - matches the
pattern already used for imoti.net/alo.bg's nationwide conversions and
feeds the frontend's city-key filtering directly instead of relying on
title-parsing fallbacks.

A page navigation retries a few times with backoff, and if all retries for
one page are exhausted, that page is skipped (not treated as the end of
the city's pagination) - only MAX_CONSECUTIVE_PAGE_FAILURES in a row gives
up on a city. Without this, one bad request mid-crawl would silently
truncate every remaining page for that city, identically to the bug found
in scraper.py/scraper_alo.py. Separately, since scrape.yml runs all 5
scrapers sequentially with a single git commit step at the end, an
uncaught exception here would otherwise silently discard every other
scraper's output for that run too.

imot.bg genuinely carries no coordinates anywhere in its own pages -
confirmed by a real headless browser (cookie consent handled, WebGL
software rendering enabled, navigator.webdriver patched away) finding no
map DOM node, no live google.maps.Map object, and no maps iframe on a
real listing, plus a plain static-HTML fetch turning up nothing either.
So each listing's real area name is geocoded via OpenStreetMap Nominatim
(geo_utils.Geocoder) - but at nationwide scale, doing that live and inline
during the scrape doesn't fit in a single run (the same problem
scraper_homes.py hit first - see its module docstring), so this only does
a cache-only lookup and leaves the rest for backfill_geocode_imot.py to
fill in as a separate, decoupled pass. This portal's search also isn't
apartments-only (it's "all sales" per city), so each listing's category is
classified from its title too, for the frontend's same-category
radius-average feature.
"""

import re
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from geo_utils import Geocoder, classify_category, extract_description_imot, extract_photos_imot

BASE_URL = "https://www.imot.bg"
SEARCH_BASE = "https://www.imot.bg/obiavi/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# (city display name, URL slug) - each slug live-verified to return a real
# imot.bg city page (status 200, real listing links) before being trusted
# here; see the module docstring for the diagnostic trail. Sofia keeps its
# already-proven slug from the original Sofia-only scraper.
CITY_SLUGS = [
    ("София", "grad-sofiya"),
    ("Пловдив", "grad-plovdiv"),
    ("Варна", "grad-varna"),
    ("Бургас", "grad-burgas"),
    ("Русе", "grad-ruse"),
    ("Стара Загора", "grad-stara-zagora"),
    ("Плевен", "grad-pleven"),
    ("Сливен", "grad-sliven"),
    ("Добрич", "grad-dobrich"),
    ("Шумен", "grad-shumen"),
    ("Перник", "grad-pernik"),
    ("Хасково", "grad-haskovo"),
    ("Ямбол", "grad-yambol"),
    ("Пазарджик", "grad-pazardzhik"),
    ("Благоевград", "grad-blagoevgrad"),
    ("Велико Търново", "grad-veliko-tarnovo"),
    ("Враца", "grad-vratsa"),
    ("Габрово", "grad-gabrovo"),
    ("Видин", "grad-vidin"),
    ("Кюстендил", "grad-kyustendil"),
    ("Кърджали", "grad-kardzhali"),
    ("Монтана", "grad-montana"),
    ("Търговище", "grad-targovishte"),
    ("Ловеч", "grad-lovech"),
    ("Силистра", "grad-silistra"),
]

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_imot.json"
LEADS_FILE = OUT_DIR / "leads_imot.json"

MAX_CARD_TEXT_LENGTH = 800
MAX_PRICE_MENTIONS = 1
# The real per-query depth cap sits around page 27-28 (~1,080 listings at
# 40/page) - 30 gives a small safety margin before giving up on a city
# without wasting requests deep past the cap.
MAX_PAGES = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
MAX_CONSECUTIVE_PAGE_FAILURES = 5

LISTING_LINK_RE = re.compile(r"/obiava-(\d[a-z]\d{10,})-")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?€")
# Every sampled card (Sofia, Plovdiv, Varna, Burgas) follows "град <City>,
# <area>" - matching just the "град <anything>," prefix instead of a
# specific city name sidesteps needing each city's exact card-text
# spelling, since the queried city is already known from CITY_SLUGS.
AREA_LINE_RE = re.compile(r"^град\s+\S.*?,\s*(.+)$")
PRICE_LINE_RE = re.compile(r"^([\d\s]{3,10})\s?€$")
SQM_RE = re.compile(r"([\d.,]+)\s?кв\.?м")


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


def parse_listings_page(html, seen, geocoder, city_display):
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

        area = city_display
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
            candidate = img.get("data-src") or img.get("src")
            if candidate and "icons/" not in candidate:
                img_url = candidate
                break
        if img_url:
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                img_url = BASE_URL + img_url

        href = a["href"]
        full_url = "https:" + href if href.startswith("//") else (BASE_URL + href if href.startswith("/") else href)
        title = f"{lines[0]}, {area}" if lines else area
        coords = geocoder.geocode_cached_only(f"{area}, {city_display}, България")

        seen[listing_id] = {
            "id": "imot_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": area,
            "city": city_display,
            "title": title[:150],
            "portal": "imot.bg",
            "lat": coords["lat"] if coords else None,
            "lng": coords["lng"] if coords else None,
            "category": classify_category(lines[0] if lines else title),
        }
    return len(matching_links)


def goto_with_retries(page, url):
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
    # pattern scraper.py/scraper_bcpea.py already established for their own
    # detail backfills.
    listing["detail_checked"] = True
    html = goto_with_retries(page, listing["url"])
    if html is None:
        return
    description = extract_description_imot(html)
    if description:
        listing["description"] = description
    photos = extract_photos_imot(html)
    if photos:
        listing["photos"] = photos


def fetch_listing_details(listings):
    # One shared browser/page reused across the whole batch (like the main
    # grid crawl already does across many page navigations) rather than a
    # fresh context per listing - much cheaper than scraper_bcpea.py's own
    # detail backfill, which needs a fresh context per listing for other
    # reasons (see its module docstring).
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

        for city_display, slug in CITY_SLUGS:
            search_url = f"{SEARCH_BASE}/{slug}"
            city_before = len(seen)
            consecutive_failures = 0
            for page_num in range(1, MAX_PAGES + 1):
                url = search_url if page_num == 1 else f"{search_url}/p-{page_num}"
                html = goto_with_retries(page, url)
                if html is None:
                    # A failed fetch (all in-page retries exhausted) is not the
                    # same signal as a genuinely empty page - treating it as
                    # "end of city" would silently truncate every remaining
                    # page for that city on one bad request (the same bug
                    # found in scraper.py/scraper_alo.py). Skip it and keep
                    # going, only giving up on the city after several in a row.
                    consecutive_failures += 1
                    print(f"DEBUG: {city_display} page {page_num} fetch failed ({consecutive_failures}/{MAX_CONSECUTIVE_PAGE_FAILURES} consecutive)")
                    if consecutive_failures >= MAX_CONSECUTIVE_PAGE_FAILURES:
                        break
                    continue
                consecutive_failures = 0

                link_count = parse_listings_page(html, seen, geocoder, city_display)
                print(f"DEBUG: {city_display} page {page_num} links matching listing URL pattern = {link_count}")
                if link_count == 0:
                    break
            print(f"DEBUG: {city_display} done, {len(seen) - city_before} new listings")

        browser.close()
    geocoder.save()
    return list(seen.values())


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
