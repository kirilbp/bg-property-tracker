"""
Scrapes current for-sale listings from imoti.bg, nationwide, across all 6
property categories (flat/house/land/garage/shop/business) - the first
scraper converted for the nationwide expansion (see category_classifier.py
and the Supabase migration this builds on). Picked as the first portal to
convert because it's the smallest today (71 Sofia listings vs. thousands
on every other portal), so any pagination/field-extraction mistakes here
are cheap to find and fix before applying the same approach to the much
larger portals.

imoti.bg's homepage location filter is a select2 widget wrapping a hidden
native <select>, with the actual URL built client-side on search-button
click - there's no separate API call to intercept. But the resulting
filtered URL turned out to be stateless/bookmarkable, confirmed live via
plain requests with no need to repeat the dropdown-click simulation.
Removing the location filter entirely (di:софия) gives the nationwide,
all-cities URL; the old Sofia-only scraper was already scoping down to
apartments only after the fact (APARTMENT_SLUGS) even though the search
itself already mixed every property type - so going nationwide-and-
all-categories only means removing two filters that were already just
being discarded downstream, not a new capability the site lacks.

Each listing's permalink URL embeds both its property-type slug (e.g.
"тристаен-апартамент", "къща", "парцел", "гараж") and its city slug
(e.g. "софия", "пловдив", "варна") - LISTING_LINK_RE now captures both
generically instead of the old Sofia-only, apartment-only enum, since
every city and category shares the same URL shape on this site.

Each listing card is the smallest ancestor whose text mentions the price
("<amount> EUR") exactly once, same "climb from the link" approach as the
other portals' scrapers. A page fetch retries a few times with backoff
before being treated as the end of pagination, so a transient failure
doesn't get mistaken for having reached the last page.

Nationwide expansion also requires fields the Sofia-only card-only scrape
never captured: a full description and a real listing-posted date, both
only available on each listing's own detail page - fetch_listing_detail()
adds one extra request per listing for these (same pattern already used
by scraper_alo.py for site_updated_at/coordinates). This is the first
portal to pay that cost nationwide; whether the same approach scales to
the much larger portals (imoti.net, alo.bg, bazar.bg - tens of thousands
of listings each) is exactly what the staged rollout is meant to surface
before committing to it there.

imoti.bg genuinely carries no coordinates anywhere in its own pages
(confirmed by a real headless browser finding no map DOM node/object/
iframe, and a plain static fetch finding nothing either), so each
listing's area name is geocoded via OpenStreetMap Nominatim instead
(geo_utils.Geocoder), cached by query string.

fetch_listings_page() originally called Geocoder.geocode() directly - a
live, blocking Nominatim request on every cache miss. That was fine
Sofia-only (a few hundred distinct neighborhood names, one-time cost),
but a real nationwide production run (started before this fix existed)
took over 4 hours instead of its usual ~35 minutes - nationwide means far
more distinct city/area combinations, so most calls were live round-trips
rather than cache hits, the identical failure mode later confirmed and
fixed the same way for scraper_homes.py's own nationwide rewrite (see
its module docstring for the full story). Fixed the same way here:
fetch_listings_page() now does a cache-only lookup
(Geocoder.geocode_cached_only - no network call); backfill_geocode_imoti_bg.py
+ its workflow do the live, rate-limited lookups as a separate, resumable
pass. The "city" field is now persisted alongside "area" specifically so
that backfill script can rebuild the exact same query string later
without needing to re-derive it from the page HTML.
"""

import re
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from geo_utils import Geocoder
from category_classifier import classify_listing

BASE_URL = "https://imoti.bg"
SEARCH_URL = "https://imoti.bg/продажби/cu:BGN"
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
# Nationwide, all-categories replaces the old Sofia-only MAX_PAGES=12 cap -
# stop condition is an empty page (see fetch_listings()), not a fixed cap,
# consistent with the "full pagination, no caps" requirement.
MAX_PAGES = 5000
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
REQUEST_DELAY_SECONDS = 0.5
MAX_CONSECUTIVE_PAGE_FAILURES = 5

# Captures (category_slug, city_slug, title_slug, id) generically - the old
# regex only matched a hardcoded apartment-slug enum under /софия/. Every
# city and every property-type slug shares this same URL shape.
LISTING_LINK_RE = re.compile(r"/продажби/([^/]+)/([^/]+)/([^/]+)-(\d{5,})\.htm")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?EUR")
PRICE_LINE_RE = re.compile(r"^([\d\s]{3,10})\s?EUR$")
# A card's location line is "<City>, <area>" - genuinely any city now, not
# just "София," - split on the first comma rather than anchoring to Sofia.
LOCATION_LINE_RE = re.compile(r"^([^,]+),\s*(.+)$")
SQM_RE = re.compile(r"([\d.,]+)\s?кв\.?м\.?")

# Common Bulgarian real-estate-site date-label patterns for a listing's own
# "posted on" date, tried against each detail page - same idea as
# scraper_alo.py's UPDATED_TEXT_RE. Not yet confirmed against imoti.bg's
# real detail-page markup (this sandbox has no network route to verify
# live) - first live run (see the nationwide-rollout verification workflow)
# confirms whether this actually matches, and gets corrected if not.
POSTED_DATE_RE = re.compile(
    r"(?:Публикувана|Публикувано|Дата на публикуване|Създадена)[^\d]{0,20}"
    r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})"
)


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
    # line, so unlike some other scrapers the first ancestor with exactly
    # one price mention is too small to also contain the area - keep
    # climbing and return the largest ancestor that still satisfies the
    # constraints.
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


def fetch_listing_detail(url):
    """Best-effort description + posted-date from a listing's own page.
    Returns (description, site_posted_at_iso) - either may be None if not
    found, never raises (a missing description/date shouldn't drop an
    otherwise-good listing).

    Does not extract a photo gallery: confirmed live via probe_photos.py/
    probe_photos_round2.py (one land-parcel and one apartment sample) that
    imoti.bg's own detail page embeds only one photo (as "large"/"small"
    size variants of the same image, both under /assets/offers/) - a
    genuine per-portal limitation, same as imoti.net's missing description
    (see backfill_detail_imoti_net.py's docstring). The single photo it
    does have is already captured below as "photo"."""
    html = fetch_html(url)
    if html is None:
        return None, None

    description = None
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        content = meta["content"].strip()
        # A generic site-wide meta description (not this listing's own
        # text) is worse than none - short boilerplate rarely exceeds a
        # few words, a real per-listing description is a real paragraph.
        if len(content) > 40:
            description = content
    if description is None:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
            except (ValueError, TypeError):
                continue
            candidates = data if isinstance(data, list) else [data]
            for c in candidates:
                if isinstance(c, dict) and isinstance(c.get("description"), str) and len(c["description"]) > 40:
                    description = c["description"].strip()
                    break
            if description:
                break

    site_posted_at = None
    m = POSTED_DATE_RE.search(html)
    if m:
        day, month, year = m.groups()
        year = int(year) if len(year) == 4 else 2000 + int(year)
        try:
            site_posted_at = datetime(year, int(month), int(day), tzinfo=timezone.utc).isoformat()
        except ValueError:
            site_posted_at = None

    return description, site_posted_at


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
        category_slug, city_slug, title_slug, listing_id = match.groups()
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

        city = city_slug.replace("-", " ").strip().title()
        area = city
        for l in lines:
            m = LOCATION_LINE_RE.match(l)
            if m:
                city = m.group(1).strip() or city
                area = m.group(2).strip() or area
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
        raw_type = lines[1] if len(lines) > 1 else category_slug.replace("-", " ")
        full_title = f"{raw_type}, {area}"[:150]
        coords = geocoder.geocode_cached_only(f"{area}, {city}, България")

        listings[listing_id] = {
            "id": "imotibg_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": area,
            "city": city,
            "title": full_title,
            "portal": "imoti.bg",
            "lat": coords["lat"] if coords else None,
            "lng": coords["lng"] if coords else None,
            # category/confidence/reason filled in by fetch_listings() once
            # the detail page's description is available too, since the
            # classifier scores description as a third signal alongside
            # title and URL.
            "_category_slug": category_slug,
        }
    return listings


def fetch_listings():
    all_listings = {}
    geocoder = Geocoder()
    consecutive_failures = 0
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            time.sleep(REQUEST_DELAY_SECONDS)
        url = SEARCH_URL if page == 1 else f"{SEARCH_URL}/page:{page}"
        page_listings = fetch_listings_page(url, geocoder)
        print(f"DEBUG: page {page} listings found = {len(page_listings) if page_listings else 0}")
        if page_listings is None:
            # A failed fetch (all in-request retries exhausted) is not the
            # real end-of-results signal (an empty dict is) - giving up here
            # would silently truncate every remaining page after one bad
            # request, the same bug found in scraper.py/scraper_alo.py/
            # scraper_imot.py/scraper_homes.py/scraper_olx.py/
            # scraper_bazar.py. Skip it and keep going, only giving up after
            # several failures in a row.
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_PAGE_FAILURES:
                break
            continue
        consecutive_failures = 0
        if not page_listings:
            break
        all_listings.update(page_listings)
    geocoder.save()

    low_confidence_count = 0
    low_confidence_reasons = {}
    for l in all_listings.values():
        time.sleep(REQUEST_DELAY_SECONDS)
        description, site_posted_at = fetch_listing_detail(l["url"])
        l["description"] = description
        l["site_posted_at"] = site_posted_at

        category, confidence, reason = classify_listing(
            title=l["title"], description=description, url=l["url"] + " " + l.pop("_category_slug")
        )
        l["category"] = category
        l["category_confidence"] = confidence
        if confidence == "low":
            low_confidence_count += 1
            low_confidence_reasons[reason] = low_confidence_reasons.get(reason, 0) + 1

    total = len(all_listings)
    print(f"DEBUG: category confidence - {total - low_confidence_count}/{total} high confidence, "
          f"{low_confidence_count}/{total} low confidence {low_confidence_reasons}")

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

        latest = rec["latest"]
        site_posted_at = latest.get("site_posted_at")
        reference_date = datetime.fromisoformat(site_posted_at) if site_posted_at else first_seen
        days_on_market = max((effective_now - reference_date).days, 0)
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
