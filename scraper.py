"""
Scrapes current Bulgaria-wide listings from imoti.net, keeps a history of
every time each listing was seen, and works out:
  - price drops and days-on-market from that history
  - each listing's price per m2 vs the average for its area, as a %

Search results are paginated with ?page=N (confirmed via the site's own
paginator, which lists a "last page" link up to page 396 at 30 items/page
for the Sofia-only search). The scraper originally only fetched page 1
with no pagination loop at all - fixed by paging through page=2, page=3,
... until a page comes back with no listings, same "stop on empty page"
pattern as scraper_bazar.py, scraper_imot.py, and scraper_imoti_bg.py,
capped at MAX_PAGES as a safety limit. Confirmed against the live site
that imoti.net hard-blocks (HTTP 403) at page 200 regardless of pacing.

Nationwide conversion: imoti.net's URL is /en/obiavi/r/prodava/<city-slug>
- unlike homes.bg, there's no single "drop the filter" nationwide switch
(every guess without a city segment - no segment, "bulgaria", a bare query
string - 404s). Live-verified this is a required per-city path segment,
and that the page-200 block is per-QUERY, not per-session (paged Sofia to
the 403 wall, then immediately fetched a different city's page 1 in the
same requests.Session with no issue) - so, unlike what was assumed here
before, this doesn't need IP rotation/session-cycling to go further; it
just needs the depth cap sliced away per query, same idea as
scraper_homes.py's price-band bisection, but the site already hands us a
free slicing dimension via CITY_SLUGS instead of needing price bands.
CITY_SLUGS is the live-verified subset (23 of the 30 cities tracked
elsewhere in this project - index.html's BG_CITIES) whose lowercase-
transliterated slug actually resolves; the other 7 (Veliko Tarnovo,
Asenovgrad, Kazanlak, Kyustendil, Dimitrovgrad, Dupnitsa, Svishtov) 404 on
that guess and are left out rather than silently sending broken requests -
their real slugs weren't worth further reverse-engineering (the site's
location picker is JS-driven, not server-rendered, so there was no direct
way to read them off the page) for what's a small fraction of national
coverage. Each request's city is already known from which slug built the
URL, so it's attached to every listing directly - far more robust than
parsing a city name back out of scraped text, and generalizes
extract_area() away from its old Sofia-only ", Sofia" split.

If any single city's own listing count is still large enough to hit the
page-200 cap (most likely candidate: Sofia, the country's biggest market
by far), that city's data is truncated there for now, same graceful-
degradation as before - logged clearly rather than silently lost, so a
follow-up price-band slicing pass (mirroring scraper_homes.py's, if
imoti.net's URLs support a price filter param - not yet confirmed) can be
added specifically for whichever city actually needs it, once real per-
city counts from a live run show which ones do.

A page fetch retries a few times with backoff before being treated as the
end of pagination, so a one-off transient failure (a connect timeout, not
a real block) doesn't get mistaken for having reached the last page - the
persistent page-200 block above still stops the run the same way, just
after retries confirm it isn't transient.

days_on_market: each listing's own page carries a genuine schema.org
"datePosted" field in its JSON-LD block (e.g. "2026-08-15" - a real date,
not "today"), confirmed live. Getting it means visiting every tracked
listing's own page once per scrape, on top of the ~200-page grid crawl -
a real cost (~6000 extra requests, ~2+ hours added to this portal's 24h
run) accepted deliberately because "days on market" is otherwise a fake
number computed from our own tracking start date rather than the
listing's real age. A detail-page fetch that fails (retries exhausted,
including the same page-block behavior the grid crawl hits) just leaves
that one listing without a real date for this run - it falls back to the
first-seen estimate rather than aborting the whole scrape.

That same detail-page fetch also carries the listing's real coordinates as
plain "latitude"/"longitude" JSON keys (confirmed live, no JS execution
needed) - extracted here at no extra request cost via geo_utils, along
with a keyword-based property category (apartment/house/land/commercial)
since imoti.net's search isn't apartments-only. Both feed the frontend's
same-category radius-average feature.
"""

import re
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from geo_utils import classify_category, extract_coords_imoti_net

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.imoti.net/en/obiavi/r/prodava"

# Live-verified subset of index.html's BG_CITIES whose lowercase-
# transliterated slug actually resolves on imoti.net (23/30 - see module
# docstring for the 7 that don't and why they're left out). Each maps to
# the same real Cyrillic city name index.html/sync_to_supabase.py's
# BG_CITY_BY_NAME already expects in a listing's "city" field, so the
# city-key logic there (see index.html's listingCityKey()) works on these
# listings without any portal-specific handling.
CITY_SLUGS = [
    ("sofia", "София"), ("plovdiv", "Пловдив"), ("varna", "Варна"), ("burgas", "Бургас"),
    ("ruse", "Русе"), ("stara-zagora", "Стара Загора"), ("pleven", "Плевен"),
    ("sliven", "Сливен"), ("dobrich", "Добрич"), ("shumen", "Шумен"), ("pernik", "Перник"),
    ("haskovo", "Хасково"), ("yambol", "Ямбол"), ("pazardzhik", "Пазарджик"),
    ("blagoevgrad", "Благоевград"), ("vratsa", "Враца"), ("gabrovo", "Габрово"),
    ("vidin", "Видин"), ("kardzhali", "Кърджали"), ("montana", "Монтана"),
    ("targovishte", "Търговище"), ("lovech", "Ловеч"), ("silistra", "Силистра"),
]

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history.json"
LEADS_FILE = OUT_DIR / "leads.json"

BGN_TO_EUR = 1.95583
MAX_CARD_TEXT_LENGTH = 400
MAX_PRICE_MENTIONS = 2
MAX_PAGES = 420
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

LISTING_LINK_RE = re.compile(r"^/en/obiava/prodava[^\"'#]*?/(\d+)/")
BGN_RE = re.compile(r"([\d\s]{3,12})\s?BGN")
SQM_RE = re.compile(r"(\d+)\s?\u043c\s?2")
DESC_RE = re.compile(r"for sale (.{5,90}?)\s+[\d\s]{2,10}\s?\u20ac")
DATE_POSTED_RE = re.compile(r'"datePosted"\s*:\s*"(\d{4}-\d{2}-\d{2})"')


def extract_area(title):
    # title is a free-text description snippet (see DESC_RE), consistently
    # shaped "<type>, <sqm> м 2 <City>, <area>" - the neighborhood/area is
    # always the last comma-separated segment, regardless of city. The old
    # Sofia-only version matched a literal "Sofia," split instead; trying
    # the same trick generically by re-matching each CITY_SLUGS name broke
    # on Burgas, live-confirmed: the site's own English text spells it
    # "Bourgas", not "burgas" - a real, silent split failure that dumped
    # the *entire* title into "area" instead of just "Lazur". Splitting on
    # the last comma sidesteps needing to know every city's exact English
    # spelling variant at all, same pattern scraper_homes.py's own
    # extract_area() already uses.
    if "," in title:
        area = title.rsplit(",", 1)[1].strip()
        return area or title.strip()
    return title.strip()


def smallest_container_with_price(link_tag, max_levels=6):
    node = link_tag
    for _ in range(max_levels):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        matches = BGN_RE.findall(text)
        if len(matches) > MAX_PRICE_MENTIONS:
            return None
        if 1 <= len(matches) <= MAX_PRICE_MENTIONS and len(text) <= MAX_CARD_TEXT_LENGTH:
            return node
    return None


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


def fetch_listings_page(url, seen, city_name):
    html = fetch_with_retries(url)
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

        text = container.get_text(" ", strip=True)

        bgn_match = BGN_RE.search(text)
        sqm_match = SQM_RE.search(text)
        desc_match = DESC_RE.search(text)
        if not bgn_match:
            continue

        price_bgn = int(re.sub(r"\D", "", bgn_match.group(1)))
        if price_bgn < 1000:
            continue
        price_eur = round(price_bgn / BGN_TO_EUR)
        sqm = int(sqm_match.group(1)) if sqm_match else None

        img = container.find("img")
        img_url = None
        if img:
            img_url = img.get("src") or img.get("data-src")
        if img_url and img_url.startswith("/"):
            img_url = "https://www.imoti.net" + img_url

        full_url = a["href"] if a["href"].startswith("http") else "https://www.imoti.net" + a["href"]
        title = desc_match.group(1).strip() if desc_match else None
        if not title:
            continue

        seen[listing_id] = {
            "id": listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": extract_area(title),
            "city": city_name,
            "title": title,
            "portal": "imoti.net",
        }
    return len(matching_links)


def parse_date_posted(html):
    m = DATE_POSTED_RE.search(html)
    return m.group(1) if m else None


def fetch_listing_dates(seen):
    total = len(seen)
    for i, (listing_id, l) in enumerate(seen.items(), 1):
        time.sleep(REQUEST_DELAY_SECONDS)
        html = fetch_with_retries(l["url"])
        if html is None:
            continue
        date_posted = parse_date_posted(html)
        if date_posted:
            l["site_posted_at"] = date_posted
        coords = extract_coords_imoti_net(html)
        if coords:
            l["lat"] = coords["lat"]
            l["lng"] = coords["lng"]
        l["category"] = classify_category(l.get("title"))
        if i % 200 == 0:
            print(f"DEBUG: fetched detail dates for {i}/{total} listings")


# imoti.net shows 30 listings/page (see module docstring) - a city whose
# last fetched page still came back full when pagination stopped (either
# a fetch failure - most likely the confirmed page-200 block - or hitting
# MAX_PAGES) means real listings were probably left uncollected, unlike a
# city that stopped on a genuinely partial or empty page.
PAGE_SIZE = 30


def fetch_listings():
    seen = {}
    for city_slug, city_name in CITY_SLUGS:
        search_url = f"{BASE_URL}/{city_slug}"
        city_start_count = len(seen)
        last_link_count = 0
        for page_num in range(1, MAX_PAGES + 1):
            if page_num > 1:
                time.sleep(REQUEST_DELAY_SECONDS)
            url = search_url if page_num == 1 else f"{search_url}?page={page_num}"
            link_count = fetch_listings_page(url, seen, city_name)
            if link_count is None:
                print(f"DEBUG: {city_name} page {page_num} fetch failed (likely the page-200 "
                      f"block) - stopping this city here, {len(seen) - city_start_count} listings collected")
                last_link_count = None
                break
            print(f"DEBUG: {city_name} page {page_num} links = {link_count}")
            last_link_count = link_count
            if not link_count:
                break
        if last_link_count is None or last_link_count >= PAGE_SIZE:
            print(f"DEBUG: WARNING - {city_name} may be truncated (last page was still full or "
                  f"a fetch failed) - real total could be higher than the "
                  f"{len(seen) - city_start_count} listings collected")
        print(f"DEBUG: finished {city_name}, {len(seen) - city_start_count} listings, "
              f"{len(seen)} total so far")
    print(f"DEBUG: fetching posted dates for {len(seen)} listings")
    fetch_listing_dates(seen)
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
# scrape cycle due to pagination timing/site load. This scraper runs on its
# OWN 24h schedule (scrape-large.yml, not the 6-hourly scrape.yml the other
# portals use - see that workflow's own comment for why), unlike the 20h
# threshold detect_relistings.py uses for the 6-hourly portals - a 20h cutoff
# here would flag every single listing "removed" the moment a day passes
# without a scrape, confirmed live against this scraper's own committed
# history.json (100% of listings came back "removed" at 20h). 48h gives a
# full extra cycle of slack for an occasionally slow/delayed run before
# concluding a listing is genuinely gone. Once removed, days_on_market/score
# freeze at the day it was last confirmed live instead of continuing to
# climb forever against an ad that's no longer there.
GONE_AFTER = timedelta(hours=48)


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
        site_posted_at = latest.get("site_posted_at")
        reference_date = (
            datetime.fromisoformat(site_posted_at).replace(tzinfo=timezone.utc)
            if site_posted_at
            else datetime.fromisoformat(rec["first_seen"])
        )
        days_on_market = max((effective_now - reference_date).days, 0)
        score = round(min(max(drop_pct, 0) / 20, 1) * 50 + min(days_on_market / 180, 1) * 50)

        price_per_sqm = round(last_price / latest["sqm"]) if latest.get("sqm") else None

        leads.append({
            **latest,
            # Records from before this nationwide conversion never had an
            # "area"/"city" key at all (the old Sofia-only scraper didn't
            # set one) - every listing tracked back then genuinely was
            # Sofia, so that's a correct fallback, not a guess, and keeps
            # the area-average loop below from crashing on a missing key
            # until each pre-existing listing is next re-scraped and gets
            # a real area/city from fetch_listings_page().
            "area": latest.get("area") or "Sofia",
            "city": latest.get("city") or "София",
            "price_eur": last_price,
            "price_per_sqm": price_per_sqm,
            "price_history": price_history,
            "price_drop_count": price_drop_count,
            "drop_pct": drop_pct,
            "days_on_market": days_on_market,
            "score": score,
            "source_status": source_status,
            "removed_at": last_seen.isoformat() if source_status == "removed" else None,
        })

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
