"""
Scrapes current Bulgaria-wide apartment listings from alo.bg.

Search results are paginated with &page=N. The scraper originally only
fetched page 1 with no pagination loop at all - fixed by paging through
page=2, page=3, ... until a page comes back with no listings, same "stop
on empty page" pattern as scraper_bazar.py, scraper_imot.py, and
scraper_imoti_bg.py, capped at MAX_PAGES as a safety limit. Learned from
scraper.py's imoti.net fix: a delay between requests is needed to avoid
getting rate-limited (HTTP 403) partway through, and a failed request is
treated as "no more listings" (stop and keep what was collected) rather
than crashing the whole run.

Found in production (not in earlier live testing) that a single request can
also fail transiently - e.g. a connect timeout with no HTTP response at all,
unrelated to any real block - and treating that identically to "no more
listings" cut a real run off at page 21 of ~166, keeping only 613 of the
old Sofia-only ~9995 listings. A page fetch retries a few times with
backoff first, but at nationwide scale (2,800 pages instead of 166) even a
low per-page failure rate means SOME page exhausting all retries becomes
likely over a full run, not a rare fluke - confirmed live as the real
cause of alo.bg's chronic nationwide undercount (~15,000 tracked against
this scraper's own ~80,424-listing live-verified total): fetch_listings()
still couldn't tell "this one page failed after retries" (a transient
blip - the crawl should skip it and keep going) apart from "a real empty
page" (genuinely reached the end - the crawl should stop), so the first
page anywhere in a 2,800-page run to exhaust its retries silently ended
the entire crawl right there. Now tracked separately: a page that
exhausts retries is skipped (losing only that one page's ~60 listings,
not the rest of the run) and only enough CONSECUTIVE page-level failures
in a row (suggesting a real, sustained outage rather than one-off
flakiness) actually stops the crawl early.

Nationwide conversion: the Sofia scope was two URL params, ?region_id=22
&location_ids=4342 - live-verified that dropping them entirely (or setting
region_id=0, same effect) gives nationwide results, jumping the site's own
stated total from ~10,009 to ~80,424 (apartments only; this scraper still
doesn't cover other property types, same as before). Paged all the way to
~2600 with real content and no block of any kind (unlike homes.bg/
imoti.net's confirmed depth caps) before hitting a genuine 404 past the
real last page - alo.bg's own per-page listing count is also higher
nationwide (60/page vs 30/page Sofia-only), so the real total is closer to
~156,000. MAX_PAGES raised well past that with real margin.

LOCATION_RE replaces the old Sofia-only AREA_RE (which matched "<area
words>, София" specifically) - live samples of real non-Sofia cards found
the consistent shape "<settlement>, [област ]<city>" immediately before
"Цена :" (note: alo.bg's "област" - region - is a PREFIX before the city/
region name here, unlike imoti.bg's own listings elsewhere in this project
where it's a trailing suffix - these are two different portals' own text
conventions, not the same rule). Captures settlement as "area" (unchanged
meaning) and the city/region name (with any "област " prefix stripped) as
a new "city" field, matching what index.html's/sync_to_supabase.py's
city-key logic already expects.

days_on_market/coords/category: previously fetched inline during the main
scrape by visiting every listing's own page (the search grid carries no
date signal at all). At nationwide scale (~156,000 listings vs. the old
~10,000 Sofia-only) that's no longer affordable in a single scrape pass,
so it's decoupled the same way homes.bg's/imoti.bg's geocoding was:
fetch_listings() now only does the fast grid crawl, and
backfill_detail_alo.py (a separate, resumable, prioritized-by-newest-first
job) visits listing pages over time to fill in site_updated_at/lat,lng/
description via fetch_update_dates() (kept here, now unused by the main
scrape path but still imported and reused by the backfill script).
description is extracted via geo_utils.extract_description_alo(), which
strips a fixed boilerplate prefix (contact instructions/reference number/
broker name) that precedes the real text on agency-posted listings.
"""

import re
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from geo_utils import extract_coords_alo, extract_description_alo
from category_classifier import classify_listing

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
SEARCH_URL = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=0"
BASE_URL = "https://www.alo.bg"

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_alo.json"
LEADS_FILE = OUT_DIR / "leads_alo.json"

MAX_CARD_TEXT_LENGTH = 1500
MAX_PRICE_MENTIONS = 1
# ~156,000 listings at 60/page nationwide is ~2,600 real pages (live-
# verified: real content through page 2600, a genuine 404 at page 2700,
# no block of any kind) - well past the old Sofia-only 350.
MAX_PAGES = 2800
REQUEST_DELAY_SECONDS = 1.0
# A run of this many CONSECUTIVE page-level failures (each already having
# exhausted its own retries) is treated as a real, sustained outage worth
# stopping for - anything less is just skipped, one bad page at a time, so
# a handful of scattered transient blips across a 2,800-page run can't
# truncate the rest of it the way a single one used to.
MAX_CONSECUTIVE_PAGE_FAILURES = 5
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
UPDATED_TEXT_RE = re.compile(r">((?:Актуализирана|Публикувана)[^<]{0,40})<")
DAYS_AGO_RE = re.compile(r"преди\s+(\d+)\s+д")
# alo.bg's regular listing cards ("listtop-item") format this "Цена:" tight,
# but its promoted/VIP cards ("listvip-item" - the template used on paginated
# pages, which is most of them) format it "Цена :" with a space before the
# colon. That mismatch alone caused the extraction to silently drop ~85-95%
# of listings on every page past page 1 - allow optional whitespace here.
PRICE_RE = re.compile(r"Цена\s*:\s*([\d\s]+)\s?€")
SQM_RE = re.compile(r"Квадратура:\s*([\d.,]+)\s?кв\.?м")
AREA_WORD = r"[А-Я][а-я]*"
# Replaces the old Sofia-only "<area words>, София" match - live samples of
# real non-Sofia cards found the consistent shape "<settlement>,
# [област ]<city>" right before "Цена :" (see module docstring). Group 1 is
# the settlement/neighborhood (kept as "area", same meaning as before);
# group 2 is the city/region name with any "област " prefix already
# stripped by the non-capturing group ahead of it.
LOCATION_RE = re.compile(
    "((?:" + AREA_WORD + r"\s+){0,3}" + AREA_WORD + r"(?:\s+\d+)?),\s*"
    r"(?:област\s+)?(" + AREA_WORD + r"(?:\s+" + AREA_WORD + r")?)\s*Цена\s*:"
)


# AREA_WORD matches any capitalized Cyrillic word with no semantic filter,
# so a property-type label sitting right before the real area in the card's
# raw text (no comma between them - "Двустаен Лазур Лазур, Бургас Цена :")
# gets swept into the same match. Live-sampled: 347/14,983 currently-active
# listings had an area value starting with one of these.
AREA_TYPE_PREFIXES = (
    "Едностаен", "Двустаен", "Тристаен", "Четиристаен", "Многостаен",
    "Мезонет", "Ателие", "Стая",
)


def dedup_area(area):
    words = area.split()
    while words and words[0] in AREA_TYPE_PREFIXES:
        words = words[1:]
    if not words:
        # Nothing left after stripping the type label(s) - the real area
        # apparently wasn't part of this match at all (a different card
        # layout LOCATION_RE doesn't fully cover). Keep the original rather
        # than return an empty string.
        return area
    if len(words) > 1:
        first = words[0]
        for i in range(len(words) - 1, 0, -1):
            if words[i] == first:
                return " ".join(words[i:])
        # The site's own card markup sometimes repeats just the area name
        # itself, immediately, with no other duplication ("Лазур Лазур",
        # "Витоша Витоша") - the loop above only catches the *first* word
        # recurring later, so check the simpler last-word-repeats-once case
        # separately.
        if words[-1] == words[-2]:
            return words[-1]
    return " ".join(words)


def smallest_container_with_price(link_tag, max_levels=6):
    node = link_tag
    for i in range(max_levels):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        matches = PRICE_RE.findall(text)
        if len(matches) > MAX_PRICE_MENTIONS:
            return None
        if len(matches) == 1 and len(text) <= MAX_CARD_TEXT_LENGTH:
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


def fetch_listings_page(url, seen):
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

        price_match = PRICE_RE.search(text)
        sqm_match = SQM_RE.search(text)
        location_match = LOCATION_RE.search(text)
        if not price_match:
            continue

        price_eur = int(re.sub(r"\D", "", price_match.group(1)))
        if price_eur < 1000:
            continue
        sqm = None
        if sqm_match:
            sqm_str = sqm_match.group(1).replace(",", ".")
            try:
                sqm = round(float(sqm_str))
            except ValueError:
                sqm = None

        if location_match:
            area = dedup_area(location_match.group(1).strip())
            city = dedup_area(location_match.group(2).strip())
        else:
            area, city = "Bulgaria", None

        # An agency-posted card has TWO images in this container: its own
        # branding/avatar (class "listtop-logo") *before* the real property
        # photo (class "listtop-image-img") in DOM order - confirmed live
        # against real cards via probe_alo_photos.py. Plain container.find(
        # "img") grabbed whichever came first, which was the agency's logo
        # for every agency-posted listing (93.8% of currently tracked
        # listings, one avatar reused across 1,201 unrelated ones) - the
        # actual property photo was sitting right there, just second.
        # Individually-posted listings (no agency) only ever have the one,
        # correctly-classed image, so this still works for them unchanged.
        img = container.find("img", class_="listtop-image-img")
        if img is None:
            # Fall back to the first non-avatar/non-logo image rather than
            # blindly taking whatever's first, in case the class name ever
            # changes - never show an avatar as if it were the property.
            img = next(
                (i for i in container.find_all("img")
                 if i.get("src") and "avatar" not in i["src"].lower()
                 and (not i.get("class") or "listtop-logo" not in i.get("class"))),
                None,
            )
        img_url = img.get("src") if img else None
        if img_url:
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                img_url = BASE_URL + img_url
            elif not img_url.startswith("http"):
                img_url = BASE_URL + "/" + img_url

        full_url = BASE_URL + a["href"]
        title = a.get_text(" ", strip=True) or text[:100]

        listing_title = title[:120]
        category, category_confidence, _ = classify_listing(title=listing_title, url=full_url)
        seen[listing_id] = {
            "id": "alo_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": area,
            "city": city,
            "title": listing_title,
            "portal": "alo.bg",
            "category": category,
            "category_confidence": category_confidence,
        }
    return len(matching_links)


def parse_days_ago(html):
    m = UPDATED_TEXT_RE.search(html)
    if not m:
        return None
    text = m.group(1)
    if "днес" in text:
        return 0
    if "вчера" in text:
        return 1
    m2 = DAYS_AGO_RE.search(text)
    return int(m2.group(1)) if m2 else None


def fetch_update_dates(seen):
    for listing_id, l in seen.items():
        time.sleep(REQUEST_DELAY_SECONDS)
        html = fetch_with_retries(l["url"])
        if html is None:
            continue
        days_ago = parse_days_ago(html)
        if days_ago is not None:
            l["site_updated_at"] = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        coords = extract_coords_alo(html)
        if coords:
            l["lat"] = coords["lat"]
            l["lng"] = coords["lng"]
        description = extract_description_alo(html)
        if description:
            l["description"] = description
        # category is now classified at grid-crawl time (title/url only,
        # no detail-page visit needed - see fetch_listings_page()), so this
        # backfill pass no longer touches it. "_detail_fetched" is the new
        # not-yet-enriched marker for backfill_detail_alo.py - site_updated_at/
        # lat,lng can genuinely stay unset even after a real visit (the site
        # doesn't always show them), so presence of an actual field can't be
        # used as the "was this visited" signal; this explicit marker can.
        l["_detail_fetched"] = True


def fetch_listings():
    # Grid crawl only - no detail-page visits here, see module docstring
    # (backfill_detail_alo.py handles site_updated_at/coords/category as a
    # separate, resumable pass; nationwide scale made doing it inline no
    # longer affordable in a single run).
    start_time = time.monotonic()
    seen = {}
    consecutive_failures = 0
    for page_num in range(1, MAX_PAGES + 1):
        if page_num > 1:
            time.sleep(REQUEST_DELAY_SECONDS)
        url = SEARCH_URL if page_num == 1 else f"{SEARCH_URL}&page={page_num}"
        link_count = fetch_listings_page(url, seen)
        elapsed = time.monotonic() - start_time

        if link_count is None:
            consecutive_failures += 1
            print(f"DEBUG: page {page_num} fetch failed after retries "
                  f"({consecutive_failures}/{MAX_CONSECUTIVE_PAGE_FAILURES} consecutive) - "
                  f"skipping this page (t={elapsed:.0f}s, {len(seen)} listings so far)")
            if consecutive_failures >= MAX_CONSECUTIVE_PAGE_FAILURES:
                print(f"DEBUG: {consecutive_failures} consecutive page failures - "
                      f"stopping (looks like a real outage, not just one-off flakiness)")
                break
            continue

        consecutive_failures = 0
        print(f"DEBUG: page {page_num} links matching listing URL pattern = {link_count} "
              f"(t={elapsed:.0f}s, {len(seen)} listings so far)")
        if not link_count:
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


# A listing not seen in a scrape for at least this long is treated as no
# longer actually posted on this portal ("removed"), not just skipped by one
# scrape cycle due to pagination timing/site load. This scraper runs on its
# OWN 24h schedule (scrape-large.yml, not the 6-hourly scrape.yml the other
# portals use - see that workflow's own comment for why), unlike the 20h
# threshold detect_relistings.py uses for the 6-hourly portals - a 20h cutoff
# here would flag every single listing "removed" the moment a day passes
# without a scrape, confirmed live against imoti.net's own committed
# history.json (100% of listings came back "removed" at 20h; same scraper
# structure applies here). 48h gives a full extra cycle of slack for an
# occasionally slow/delayed run before concluding a listing is genuinely
# gone. Once removed, days_on_market/score freeze at the day it was last
# confirmed live instead of continuing to climb forever against an ad
# that's no longer there.
GONE_AFTER = timedelta(hours=48)


def compute_leads(history):
    leads = []
    for lid, rec in history.items():
        prices = [s["price_eur"] for s in rec["snapshots"] if s["price_eur"]]
        if not prices:
            continue
        first_price = prices[0]
        last_price = prices[-1]
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
        reference_date = (
            datetime.fromisoformat(site_updated_at) if site_updated_at else datetime.fromisoformat(rec["first_seen"])
        )
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
    area_avg = {}
    for area, v in area_totals.items():
        area_avg[area] = sum(v) / len(v)

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
    print("Found " + str(len(listings)) + " listings, " + str(len(leads)) + " tracked leads")


if __name__ == "__main__":
    main()
