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

Pagination depth cap and the price-band slicing fix: a real nationwide
run found every type's pagination stopping at exactly page 49
(~980-1,000 results) regardless of the much larger offersCount each type
reports - a site-side depth cap, not a natural end of results (confirmed:
even a single narrow-enough slice paginates cleanly past where the cap
would otherwise bite, to a real partial last page with hasMoreItems=
False). Live diagnostics (probe_homes_slicing.py, kept for reference)
found priceFrom/priceTo are real, working filter params, and that the
real nationwide price distribution is heavily skewed - flat price bands
aren't fine-grained enough in the dense middle of the market, so
bisect_price_slices() recursively narrows each type's [0, 1,000,000)
price range, splitting any slice whose own offersCount is still over a
900-result safety margin (SLICE_THRESHOLD, comfortably under the ~1,000
cap), until every leaf slice is safely paginable to its true end;
everything above 1,000,000 (confirmed consistently small - 108-573
listings per type - across live checks) is scraped as one final tail
slice. This full scheme was verified live before being wired in here:
236 count-only requests found the real retrievable total across all 4
types is ~70,253 listings, versus the ~3,900 the old flat per-type loop
actually retrieved.
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
MAX_CONSECUTIVE_PAGE_FAILURES = 5

# (typeId query value, our 6-category bucket). LandParcel and LandAgro are
# two distinct homes.bg search categories (regular plots vs agricultural
# land) that both map onto our single "land" bucket.
TYPE_QUERIES = [
    ("ApartmentSell", "flat"),
    ("HouseSell", "house"),
    ("LandParcel", "land"),
    ("LandAgro", "land"),
]

# Safety margin under homes.bg's confirmed ~1,000-result pagination depth
# cap - a slice at or under this is trusted to paginate cleanly to its real
# end. MAX_SLICE_PRICE is where price-band bisection stops and the rest
# (confirmed consistently small - 108-573 listings/type live) is scraped as
# one final tail slice instead of being bisected further.
SLICE_THRESHOLD = 900
MAX_SLICE_PRICE = 1_000_000
MAX_BISECT_DEPTH = 12
MIN_SLICE_WIDTH = 500

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_homes.json"
LEADS_FILE = OUT_DIR / "leads_homes.json"

BGN_TO_EUR = 1.95583

STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)
SQM_RE = re.compile(r"(\d+)\s?m²")


def parse_price_eur(price):
    # A "price on request" listing reports "value": false (a bool, not a
    # numeric string) instead of omitting the field - found live on a real
    # nationwide run (a HouseSell listing crashed the whole scrape here,
    # discarding everything already fetched since fetch_listings() only
    # returns its results at the very end). Any other unparseable value
    # gets the same treatment: no price to report, not a crash.
    raw = price.get("value")
    if not isinstance(raw, str):
        return None
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    if price.get("currency") == "BGN":
        return round(value / BGN_TO_EUR)
    return round(value)


def extract_area(location):
    if not location:
        return "Bulgaria"
    if "," in location:
        area = location.rsplit(",", 1)[0].strip()
        return area or location.strip()
    return location.strip()


def extract_city(location):
    # location is "<neighborhood/settlement>, <city>" - extract_area() above
    # keeps the more specific first part; the city name after the last comma
    # was previously discarded entirely, which is what left every homes.bg
    # listing's "city" field empty and made the frontend's city filter/tabs
    # fall back to always assuming Sofia (see index.html's listingCityKey()).
    # A location with no comma (rare) has no separate city to extract.
    if not location or "," not in location:
        return None
    city = location.rsplit(",", 1)[1].strip()
    return city or None


def fetch_with_retries(session, url):
    for attempt in range(1, MAX_RETRIES + 1):
        resp = None
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            # Logging the real HTTP status (when there is one) distinguishes
            # "homes.bg is throttling us" (429/403) from a plain timeout/
            # connection error (no response at all) - both look identical
            # as a generic "request failed" message otherwise, and a real
            # multi-hour run needs this to be diagnosable after the fact.
            status = resp.status_code if resp is not None else "no response (timeout/connection error)"
            print(f"DEBUG: request failed for {url} (attempt {attempt}/{MAX_RETRIES}, status={status}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    return None


def build_url(type_id, page, price_from=None, price_to=None):
    params = {"locationId": "0", "typeId": type_id}
    if price_from is not None:
        params["priceFrom"] = str(price_from)
    if price_to is not None:
        params["priceTo"] = str(price_to)
    if page > 1:
        params["page"] = str(page)
    return f"{BASE_URL}/?{urlencode(params)}"


def get_offers_count(session, type_id, price_from, price_to):
    text = fetch_with_retries(session, build_url(type_id, 1, price_from, price_to))
    if text is None:
        return 0
    match = STATE_RE.search(text)
    if not match:
        return 0
    state = json.loads(match.group(1))
    return state.get("data", {}).get("offers", {}).get("offersCount", 0) or 0


def bisect_price_slices(session, type_id, lo, hi, depth=0):
    """Recursively narrows [lo, hi) until each leaf slice's own offersCount
    is under the depth-cap safety threshold, so it can paginate to its real
    end instead of being truncated. See the module docstring for the live
    verification this mirrors."""
    count = get_offers_count(session, type_id, lo, hi)
    if count <= SLICE_THRESHOLD or depth >= MAX_BISECT_DEPTH or hi - lo < MIN_SLICE_WIDTH:
        return [(lo, hi)]
    mid = lo + (hi - lo) // 2
    return (bisect_price_slices(session, type_id, lo, mid, depth + 1)
            + bisect_price_slices(session, type_id, mid, hi, depth + 1))


def parse_offer(offer, category, geocoder):
    # A single malformed offer (an unexpected field shape homes.bg's own
    # JSON hasn't shown before) must not crash the whole run - the caller
    # only returns its results at the very end, so an uncaught exception
    # here would discard every page already fetched. Confirmed as a real
    # failure mode live: a "price on request" listing reports "value":
    # false (a bool, not a numeric string) instead of omitting the field,
    # which crashed parse_price_eur() and lost 49 ApartmentSell + 14
    # HouseSell pages of already-fetched results in one real nationwide run.
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

    price_eur = parse_price_eur(offer["price"])
    if price_eur is None:
        return None

    location = offer.get("location", "")
    area = extract_area(location)
    city = extract_city(location)
    title = f"{offer.get('title', '')}, {location}".strip(", ")
    geo_query = f"{location}, България" if location else f"{area}, България"
    coords = geocoder.geocode_cached_only(geo_query)

    return {
        "id": "homes_" + str(offer["id"]),
        "url": BASE_URL + offer["viewHref"],
        "photo": photo_url,
        "photos": photos,
        "description": offer.get("description") or None,
        "price_eur": price_eur,
        "sqm": sqm,
        "area": area,
        "city": city,
        "title": title,
        "portal": "homes.bg",
        "lat": coords["lat"] if coords else None,
        "lng": coords["lng"] if coords else None,
        "category": category,
        "category_confidence": "high",
    }


def scrape_slice(session, geocoder, type_id, category, lo, hi, seen, start_time):
    consecutive_failures = 0
    for page in range(1, MAX_PAGES + 1):
        url = build_url(type_id, page, lo, hi)
        text = fetch_with_retries(session, url)
        if text is None:
            # A failed fetch (all in-request retries exhausted) is not the
            # real end-of-results signal (that's hasMoreItems below) - giving
            # up on the whole slice here would silently truncate every
            # remaining page after one bad request, the same bug found in
            # scraper.py/scraper_alo.py/scraper_imot.py. Skip it and keep
            # going, only giving up on the slice after several in a row.
            consecutive_failures += 1
            print(f"DEBUG: {type_id} price[{lo}-{hi}] page {page} fetch failed ({consecutive_failures}/{MAX_CONSECUTIVE_PAGE_FAILURES} consecutive)")
            if consecutive_failures >= MAX_CONSECUTIVE_PAGE_FAILURES:
                break
            continue
        consecutive_failures = 0

        match = STATE_RE.search(text)
        if not match:
            print(f"DEBUG: no __PRELOADED_STATE__ found on {type_id} price[{lo}-{hi}] page {page}")
            continue
        state = json.loads(match.group(1))
        offers = state.get("data", {}).get("offers", {})
        results = offers.get("result", [])
        # t= is wall-clock elapsed since fetch_listings() started, not this
        # page/slice alone - a real multi-hour run with no way to see live
        # logs needs this to tell "still making progress" from "stuck
        # retrying the same page", after the fact from the final log.
        elapsed = time.monotonic() - start_time
        print(f"DEBUG: {type_id} price[{lo}-{hi}] page {page} offers count = {len(results)} "
              f"(t={elapsed:.0f}s, {len(seen)} listings so far)")

        for offer in results:
            listing_id = "homes_" + str(offer.get("id"))
            if listing_id in seen:
                continue
            try:
                parsed = parse_offer(offer, category, geocoder)
                if parsed is not None:
                    seen[parsed["id"]] = parsed
            except Exception as e:
                print(f"DEBUG: skipping malformed offer {listing_id} on {type_id} price[{lo}-{hi}] page {page}: {e}")
                continue

        if not offers.get("hasMoreItems"):
            break


def fetch_listings():
    start_time = time.monotonic()
    session = requests.Session()
    seen = {}
    geocoder = Geocoder()

    for type_id, category in TYPE_QUERIES:
        type_start = time.monotonic()
        print(f"DEBUG: starting {type_id} at t={type_start - start_time:.0f}s, {len(seen)} listings so far")

        slices = bisect_price_slices(session, type_id, 0, MAX_SLICE_PRICE)
        tail_count = get_offers_count(session, type_id, MAX_SLICE_PRICE, None)
        if tail_count > SLICE_THRESHOLD:
            print(f"DEBUG: {type_id} tail slice ({MAX_SLICE_PRICE}+) has {tail_count} offers, "
                  f"over the {SLICE_THRESHOLD} safety threshold - pagination may truncate it")
        slices.append((MAX_SLICE_PRICE, None))
        print(f"DEBUG: {type_id} split into {len(slices)} price slices for full pagination")

        for lo, hi in slices:
            scrape_slice(session, geocoder, type_id, category, lo, hi, seen, start_time)

        print(f"DEBUG: finished {type_id} in {time.monotonic() - type_start:.0f}s, {len(seen)} listings so far")

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
