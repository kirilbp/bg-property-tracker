"""
Scrapes current Bulgaria-wide apartment, house, and land listings from
homes.bg.

Unlike imoti.net and alo.bg, homes.bg's homepage embeds a structured JSON
blob (window.__PRELOADED_STATE__) with the listing data already parsed out
by their own frontend - no HTML/regex scraping needed, just pull the JSON.

Nationwide + all-categories mechanism (found via live diagnostic probing,
since neither is documented or guessable from the URL alone):
  - City filter: the homepage defaults to Sofia-only. Adding
    ?locationId=0 drops the location filter entirely (confirmed live:
    offersCount jumped from 12,351 Sofia-only to 44,111 nationwide, first
    result a non-Sofia city) - this is the one nationwide switch, used on
    every request below.
  - Property type: a plain ?type=<anything> query param is silently
    ignored - every guess (URL slugs, short codes, full business names)
    fell back to the same Sofia-dropped-but-still-apartment-only result.
    The real mechanism, found by reading homes.bg's own client JS bundle
    (static/js/client.*.js), is ?typeId=<PascalCase business name> - e.g.
    ?typeId=HouseSell. homes.bg has only 4 real for-sale property types
    total (no office/shop/garage/warehouse exist on this portal at all,
    unlike imoti.bg): ApartmentSell, HouseSell, LandParcel (regular land
    plots) and LandAgro (agricultural land) - confirmed nationwide counts
    44,111 / 9,625 / 13,406 / 2,115 respectively. TYPE_QUERIES below
    drives one full paginated pass per type.

Because the category comes straight from which portal search category
the listing was fetched under (ground truth from homes.bg's own search
index), not inferred from title/description text, category_confidence is
always "high" here - this is more reliable than the keyword-based
classifier used for portals that don't expose a real per-listing type.

The pagination loop stops on the API's own hasMoreItems=False; MAX_PAGES
is just a generous safety cap in case that flag ever misbehaves.

A page fetch retries a few times with backoff before being treated as the
end of pagination, so a transient failure doesn't get mistaken for having
reached the last page - and, since scrape.yml runs all scrapers
sequentially with a single git commit step at the end, an uncaught
exception here would otherwise silently discard every other scraper's
output for that run too.

Each offer's raw JSON also carries a full "description" and a "photos"
array (not just the single cover "photo") - both captured and surfaced on
the listing detail page. There's also a "time" field, initially assumed
to be a real "last updated" signal (like olx.bg's, see scraper_olx.py) -
but sampling 280 live offers found 100% of them reporting "днес" (today)
with zero variation, meaning homes.bg apparently marks every actively
displayed listing as "today" regardless of true listing age. Using it
for days_on_market would make every homes.bg listing permanently show 0
days, which is worse than not using it at all - it would mask exactly
the stagnant, long-listed properties this tool exists to surface. So
days_on_market here stays purely tracking-based (time since we first
scraped the listing), same as before.

homes.bg carries no coordinates anywhere on its own pages, but every
offer's "location" string (neighborhood/settlement + city/region) is
genuinely geocodable via OpenStreetMap Nominatim (geo_utils.Geocoder).
Sofia-only scraping could afford a live geocode call per cache miss
in-line (a few hundred distinct neighborhood names total, one-time
cost) - nationwide, that assumption breaks: a bounded 1-page-per-type
trial run (~80 listings, almost all cache misses against the old
Sofia-only cache) took over 10 minutes and was still running when
cancelled, even after cutting Nominatim's request timeout from 15s to
8s. Blocking the actual scrape on live geocoding at nationwide scale
risks either starving it of runtime or hammering Nominatim's free,
rate-limited public endpoint well past what a single sequential 1
req/sec caller can clear in one run. So fetch_listings() now only does
a cache-only lookup (Geocoder.geocode_cached_only - no network call,
returns None on a miss) - existing cached areas (mostly Sofia, from
prior runs) resolve for free, everything new starts as lat=lng=None and
gets filled in over time by backfill_geocode_homes.py, a separate
workflow_dispatch job that does the live, rate-limited Nominatim calls
without competing with the scrape for time or blocking it on network
flakiness. extract_area() used to split specifically on ", София"
(Sofia-only scraping never needed anything else); now that every city
in Bulgaria shows up here, it generically splits on the last comma
instead, keeping the more specific neighborhood/settlement part as
"area" - the geocode query itself (built the same way here and in the
backfill script) uses the full location string rather than assuming a
Sofia suffix.
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

from geo_utils import Geocoder

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.homes.bg"
MAX_PAGES = 5000
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

# (typeId query value, our 6-category bucket). LandParcel and LandAgro are
# two distinct homes.bg search categories (regular plots vs agricultural
# land) that both map onto our single "land" bucket.
TYPE_QUERIES = [
    ("ApartmentSell", "flat"),
    ("HouseSell", "house"),
    ("LandParcel", "land"),
    ("LandAgro", "land"),
]

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_homes.json"
LEADS_FILE = OUT_DIR / "leads_homes.json"

BGN_TO_EUR = 1.95583

STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)
SQM_RE = re.compile(r"(\d+)\s?m²")


def parse_price_eur(price):
    value = float(price["value"].replace(",", ""))
    if price["currency"] == "BGN":
        return round(value / BGN_TO_EUR)
    return round(value)


def extract_area(location):
    if not location:
        return "Bulgaria"
    if "," in location:
        area = location.rsplit(",", 1)[0].strip()
        return area or location.strip()
    return location.strip()


def fetch_with_retries(session, url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"DEBUG: request failed for {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    return None


def build_url(type_id, page):
    params = {"locationId": "0", "typeId": type_id}
    if page > 1:
        params["page"] = str(page)
    return f"{BASE_URL}/?{urlencode(params)}"


def fetch_listings():
    session = requests.Session()
    seen = {}
    geocoder = Geocoder()

    for type_id, category in TYPE_QUERIES:
        for page in range(1, MAX_PAGES + 1):
            url = build_url(type_id, page)
            text = fetch_with_retries(session, url)
            if text is None:
                break

            match = STATE_RE.search(text)
            if not match:
                print(f"DEBUG: no __PRELOADED_STATE__ found on {type_id} page {page}")
                continue
            state = json.loads(match.group(1))
            offers = state.get("data", {}).get("offers", {})
            results = offers.get("result", [])
            print(f"DEBUG: {type_id} page {page} offers count = {len(results)}")

            for offer in results:
                listing_id = "homes_" + str(offer["id"])
                if listing_id in seen:
                    continue

                sqm_match = SQM_RE.search(offer.get("title", ""))
                sqm = int(sqm_match.group(1)) if sqm_match else None

                photo = offer.get("photo")
                photo_url = None
                if photo:
                    photo_url = f"https://g1.homes.bg/{photo['path']}{photo['name']}b.jpg"

                photos = []
                for p in offer.get("photos") or []:
                    if isinstance(p, dict) and p.get("path") and p.get("name"):
                        photos.append(f"https://g1.homes.bg/{p['path']}{p['name']}b.jpg")
                if not photos and photo_url:
                    photos = [photo_url]

                location = offer.get("location", "")
                area = extract_area(location)
                title = f"{offer.get('title', '')}, {location}".strip(", ")
                geo_query = f"{location}, България" if location else f"{area}, България"
                coords = geocoder.geocode_cached_only(geo_query)

                seen[listing_id] = {
                    "id": listing_id,
                    "url": BASE_URL + offer["viewHref"],
                    "photo": photo_url,
                    "photos": photos,
                    "description": offer.get("description") or None,
                    "price_eur": parse_price_eur(offer["price"]),
                    "sqm": sqm,
                    "area": area,
                    "title": title,
                    "portal": "homes.bg",
                    "lat": coords["lat"] if coords else None,
                    "lng": coords["lng"] if coords else None,
                    "category": category,
                    "category_confidence": "high",
                }

            if not offers.get("hasMoreItems"):
                break

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
