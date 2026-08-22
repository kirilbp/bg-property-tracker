"""
Scrapes current Sofia apartment listings from homes.bg.

Unlike imoti.net and alo.bg, homes.bg's homepage embeds a structured JSON
blob (window.__PRELOADED_STATE__) with the listing data already parsed out
by their own frontend - no HTML/regex scraping needed, just pull the JSON.
The homepage's default search is already "Apartments for sale - Sofia"
(confirmed via searchCriteria in that JSON), and further pages are fetched
with ?page=N.

The pagination loop already stops on the API's own hasMoreItems=False, but
was also hard-capped at PAGES_TO_FETCH=2 regardless - confirmed against the
live site that hasMoreItems is still True well past page 2 (checked through
page 7), so real results were being cut off early. Raised the cap to a
generous safety limit and let hasMoreItems be the real stopping condition,
same pattern as the other scrapers' "stop on empty page".

A page fetch retries a few times with backoff before being treated as the
end of pagination, so a transient failure doesn't get mistaken for having
reached the last page - and, since scrape.yml runs all 5 scrapers
sequentially with a single git commit step at the end, an uncaught
exception here would otherwise silently discard every other scraper's
output for that run too.

Each offer's raw JSON also carries a full "description" and a "photos"
array (not just the single cover "photo") - both previously discarded
even though already present in every fetch, now captured and surfaced on
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
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.homes.bg"
PAGES_TO_FETCH = 100
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

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
    parts = re.split(r",\s*София", location)
    area = parts[0].strip() if parts else location.strip()
    return area or "Sofia"


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


def fetch_listings():
    session = requests.Session()
    seen = {}

    for page in range(1, PAGES_TO_FETCH + 1):
        url = BASE_URL + ("/" if page == 1 else f"/?page={page}")
        text = fetch_with_retries(session, url)
        if text is None:
            break

        match = STATE_RE.search(text)
        if not match:
            print(f"DEBUG: no __PRELOADED_STATE__ found on page {page}")
            continue
        state = json.loads(match.group(1))
        offers = state.get("data", {}).get("offers", {})
        results = offers.get("result", [])
        print(f"DEBUG: page {page} offers count = {len(results)}")

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

            seen[listing_id] = {
                "id": listing_id,
                "url": BASE_URL + offer["viewHref"],
                "photo": photo_url,
                "photos": photos,
                "description": offer.get("description") or None,
                "price_eur": parse_price_eur(offer["price"]),
                "sqm": sqm,
                "area": extract_area(offer.get("location", "")),
                "title": f"{offer.get('title', '')}, {offer.get('location', '')}".strip(", "),
                "portal": "homes.bg",
            }

        if not offers.get("hasMoreItems"):
            break

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


def compute_leads(history):
    leads = []
    for lid, rec in history.items():
        prices = [s["price_eur"] for s in rec["snapshots"] if s["price_eur"]]
        if not prices:
            continue
        first_price, last_price = prices[0], prices[-1]
        drop_pct = round((first_price - last_price) / first_price * 100, 1) if first_price else 0
        first_seen = datetime.fromisoformat(rec["first_seen"])
        days_on_market = (datetime.now(timezone.utc) - first_seen).days
        score = round(min(max(drop_pct, 0) / 20, 1) * 50 + min(days_on_market / 180, 1) * 50)

        latest = rec["latest"]
        price_per_sqm = round(last_price / latest["sqm"]) if latest.get("sqm") else None

        entry = dict(latest)
        entry["price_eur"] = last_price
        entry["price_per_sqm"] = price_per_sqm
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
