"""
Scrapes current Sofia apartment-for-sale listings from bazar.bg.

bazar.bg is a general classifieds site (cars, jobs, real estate, etc), so
this scopes to its own "apartments for sale in Sofia" category URL
(https://bazar.bg/obiavi/prodazhba-apartamenti/sofia) rather than a sitewide
search - the site itself filters out unrelated categories. Confirmed by
sampling 68 live listings during development: 100% were genuine
apartment-for-sale titles ("Продава <N>-СТАЕН, гр. София, <area>" or
"Продава МЕЗОНЕТ/МНОГОСТАЕН, гр. София, <area>"), none from other
categories. bazar.bg has no bot-blocking - plain requests work fine.

Each listing card is the smallest ancestor whose text mentions the price
("<amount> €") exactly once, same "climb from the link" approach as
scraper.py, scraper_alo.py, scraper_imot.py, and scraper_olx.py. Within
that card the price amount and the "€" sign are on separate lines, so the
price is read by finding the "€" line and taking the digits from the line
right before it. bazar.bg's listing grid doesn't show square meters (only
the individual listing page does), so sqm/price_per_sqm are left null here
- the same graceful degradation compute_leads() already applies to any
listing missing sqm.
"""

import re
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia"
BASE_URL = "https://bazar.bg"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_bazar.json"
LEADS_FILE = OUT_DIR / "leads_bazar.json"

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1
MAX_PAGES = 3

LISTING_LINK_RE = re.compile(r"obiava-(\d+)")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?€")
AREA_LINE_RE = re.compile(r"^гр\.\s*София,\s*(.+)$")


def fetch_html(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def smallest_container_with_price(link_tag, max_levels=9):
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


def fetch_listings_page(url):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]

    listings = {}
    for a in matching_links:
        match = LISTING_LINK_RE.search(a["href"])
        listing_id = match.group(1)
        if listing_id in listings:
            continue

        container = smallest_container_with_price(a)
        if container is None:
            continue

        lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
        if not lines:
            continue

        price_eur = None
        for i, l in enumerate(lines):
            if l == "€" and i > 0:
                digits = re.sub(r"\D", "", lines[i - 1])
                if digits:
                    price_eur = int(digits)
                break
        if price_eur is None or price_eur < 1000:
            continue

        area = "Sofia"
        for l in lines:
            m = AREA_LINE_RE.match(l)
            if m:
                area = m.group(1).strip()
                break

        img_url = None
        for img in container.find_all("img"):
            candidate = img.get("src") or img.get("data-src")
            if candidate and "icons/" not in candidate.lower():
                if candidate.startswith("//"):
                    candidate = "https:" + candidate
                elif candidate.startswith("/"):
                    candidate = BASE_URL + candidate
                img_url = candidate
                break

        href = a["href"]
        full_url = href if href.startswith("http") else BASE_URL + href
        title = lines[0] if lines else area

        listings[listing_id] = {
            "id": "bazar_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": None,
            "area": area,
            "title": title[:150],
            "portal": "bazar.bg",
        }
    return listings


def fetch_listings():
    all_listings = {}
    for page in range(1, MAX_PAGES + 1):
        url = SEARCH_URL if page == 1 else f"{SEARCH_URL}?page={page}"
        page_listings = fetch_listings_page(url)
        if not page_listings:
            break
        all_listings.update(page_listings)
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
