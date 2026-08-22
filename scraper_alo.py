"""
Scrapes current Sofia apartment listings from alo.bg.

Search results are paginated with &page=N (confirmed via the site's own
paginator; alo.bg itself states ~9995 apartment listings for this search at
30/page, i.e. ~333 pages). The scraper originally only fetched page 1 with
no pagination loop at all - fixed by paging through page=2, page=3, ...
until a page comes back with no listings, same "stop on empty page" pattern
as scraper_bazar.py, scraper_imot.py, and scraper_imoti_bg.py, capped at
MAX_PAGES as a safety limit. Learned from scraper.py's imoti.net fix: a
delay between requests is needed to avoid getting rate-limited (HTTP 403)
partway through, and a failed request is treated as "no more listings"
(stop and keep what was collected) rather than crashing the whole run.
"""

import re
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
SEARCH_URL = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342"
BASE_URL = "https://www.alo.bg"

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_alo.json"
LEADS_FILE = OUT_DIR / "leads_alo.json"

MAX_CARD_TEXT_LENGTH = 1500
MAX_PRICE_MENTIONS = 1
MAX_PAGES = 350
REQUEST_DELAY_SECONDS = 1.0

LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
PRICE_RE = re.compile(r"Цена:\s*([\d\s]+)\s?€")
SQM_RE = re.compile(r"Квадратура:\s*([\d.,]+)\s?кв\.?м")
AREA_WORD = r"[А-Я][а-я]*"
AREA_RE = re.compile(
    "((?:" + AREA_WORD + r"\s+){0,3}" + AREA_WORD + r"(?:\s+\d+)?),\s*София"
)


def dedup_area(area):
    words = area.split()
    if len(words) > 1:
        first = words[0]
        for i in range(len(words) - 1, 0, -1):
            if words[i] == first:
                return " ".join(words[i:])
    return area


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


def fetch_listings_page(url, seen):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"DEBUG: request failed for {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]

    page_ids = {LISTING_LINK_RE.search(a["href"]).group(1) for a in matching_links}
    already_seen_count = sum(1 for pid in page_ids if pid in seen)
    container_fail_count = 0
    parse_fail_count = 0
    added_count = 0

    for a in matching_links:
        match = LISTING_LINK_RE.search(a["href"])
        listing_id = match.group(1)
        if listing_id in seen:
            continue

        container = smallest_container_with_price(a)
        if container is None:
            container_fail_count += 1
            continue

        text = container.get_text(" ", strip=True)

        price_match = PRICE_RE.search(text)
        sqm_match = SQM_RE.search(text)
        area_match = AREA_RE.search(text)
        if not price_match:
            parse_fail_count += 1
            continue

        price_eur = int(re.sub(r"\D", "", price_match.group(1)))
        if price_eur < 1000:
            parse_fail_count += 1
            continue
        sqm = None
        if sqm_match:
            sqm_str = sqm_match.group(1).replace(",", ".")
            try:
                sqm = round(float(sqm_str))
            except ValueError:
                sqm = None

        area = dedup_area(area_match.group(1).strip()) if area_match else "Sofia"

        img = container.find("img")
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

        seen[listing_id] = {
            "id": "alo_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": area,
            "title": title[:120],
            "portal": "alo.bg",
        }
        added_count += 1
    print(f"DEBUG: page detail - raw_links={len(matching_links)} unique_ids_on_page={len(page_ids)} "
          f"already_in_seen={already_seen_count} container_fail={container_fail_count} "
          f"parse_fail={parse_fail_count} added={added_count}")
    return len(matching_links)


def fetch_listings():
    seen = {}
    for page_num in range(1, MAX_PAGES + 1):
        if page_num > 1:
            time.sleep(REQUEST_DELAY_SECONDS)
        url = SEARCH_URL if page_num == 1 else f"{SEARCH_URL}&page={page_num}"
        link_count = fetch_listings_page(url, seen)
        print(f"DEBUG: page {page_num} links matching listing URL pattern = {link_count}")
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


def compute_leads(history):
    leads = []
    for lid, rec in history.items():
        prices = [s["price_eur"] for s in rec["snapshots"] if s["price_eur"]]
        if not prices:
            continue
        first_price = prices[0]
        last_price = prices[-1]
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


main()
