"""
Scrapes current Sofia apartment listings from alo.bg. Same approach as
scraper.py (find listing links, climb to the smallest container that has
exactly one price mention, skip anything ambiguous), adapted to alo.bg's
page structure -- which conveniently gives price directly in EUR and even
pre-calculates price-per-m2, so there's no BGN conversion needed here.
"""

import re
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
SEARCH_URL = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342"

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_alo.json"
LEADS_FILE = OUT_DIR / "leads_alo.json"

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1

LISTING_LINK_RE = re.compile(r"^https://www\.alo\.bg/[a-z0-9\-]+-(\d{6,9})$")
PRICE_RE = re.compile(r"\u0426\u0435\u043d\u0430:\s*([\d\s]+)\s?\u20ac")
SQM_RE = re.compile(r"\u041a\u0432\u0430\u0434\u0440\u0430\u0442\u0443\u0440\u0430:\s*([\d.,]+)\s?\u043a\u0432\.?\u043c")
AREA_RE = re.compile(r"([\u0410-\u042f\u0430-\u044f\w\s]{2,30}),\s*\u0421\u043e\u0444\u0438\u044f")


def smallest_container_with_price(link_tag, max_levels=6):
    node = link_tag
    for _ in range(max_levels):
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


def fetch_listings(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]

    seen = {}
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
        area_match = AREA_RE.search(text)
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

        area = area_match.group(1).strip() if area_match else "Sofia"

        img = container.find("img")
        img_url = img.get("src") if img else None

        title = a.get_text(" ", strip=True) or text[:100]

        seen[listing_id] = {
            "id": "alo_" + listing_id,
            "url": a["href"],
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": area,
            "title": title[:120],
            "portal": "alo.bg",
        }
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

        leads.append({
            **latest,
            "price_eur": last_price,
            "price_per_sqm": price_per_sqm,
            "drop_pct": drop_pct,
            "days_on_market": days_on_market,
            "score": score,
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
    listings = fetch_listings(SEARCH_URL)
    history = load_history()
    history = update_history(history, listings)
    save_history(history)
    leads = compute_leads(history)
    LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Found {len(listings)} listings, {len(leads)} tracked leads")


if __name__ == "__main__":
    main()
