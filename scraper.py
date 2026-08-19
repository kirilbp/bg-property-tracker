"""
Scrapes current Sofia listings from imoti.net, keeps a history of every time
each listing was seen, and works out price drops and days-on-market from
that history.

Note: each genuine listing card normally mentions BGN twice -- once for the
total price, once for the price-per-square-metre -- so "more than 2 price
mentions" (not "more than 1") is the signal that a container spans multiple
listings rather than being a single card.
"""

import re
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
SEARCH_URL = "https://www.imoti.net/en/obiavi/r/prodava/sofia"

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history.json"
LEADS_FILE = OUT_DIR / "leads.json"

BGN_TO_EUR = 1.95583
MAX_CARD_TEXT_LENGTH = 400
MAX_PRICE_MENTIONS = 2  # total price + price-per-sqm is normal for one card

LISTING_LINK_RE = re.compile(r"^/en/obiava/prodava[^\"'#]*?/(\d+)/")
BGN_RE = re.compile(r"([\d\s]{3,12})\s?BGN")
SQM_RE = re.compile(r"(\d+)\s?\u043c\s?2")
DESC_RE = re.compile(r"for sale (.{5,90}?)\s+[\d\s]{2,10}\s?\u20ac")


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


def fetch_listings(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"DEBUG: HTTP status code = {resp.status_code}")
    print(f"DEBUG: response length = {len(resp.text)} characters")

    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
    print(f"DEBUG: links matching listing URL pattern = {len(matching_links)}")

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
            "title": title,
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
        leads.append({
            **rec["latest"],
            "price_eur": last_price,
            "drop_pct": drop_pct,
            "days_on_market": days_on_market,
            "score": score,
        })
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
