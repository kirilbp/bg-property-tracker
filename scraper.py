"""
Scrapes current Sofia listings from imoti.net, keeps a history of every time
each listing was seen, and works out price drops and days-on-market from
that history. Designed to be re-run automatically (see the GitHub Actions
workflow file) so the history builds up over days and weeks.
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

LISTING_LINK_RE = re.compile(r"/en/obiava/[^\"'#]+?/(\d+)/")


def fetch_listings(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen = {}
    for a in soup.find_all("a", href=True):
        match = LISTING_LINK_RE.search(a["href"])
        if not match:
            continue
        listing_id = match.group(1)
        if listing_id in seen:
            continue

        container = a
        for _ in range(4):
            if container.parent:
                container = container.parent

        text = container.get_text(" ", strip=True)
        price_match = re.search(r"([\d\s]{4,10})\s?\u20ac", text)
        sqm_match = re.search(r"(\d+)\s?\u043c2", text)
        img = container.find("img")
        img_url = img["src"] if img and img.get("src") else None
        if img_url and img_url.startswith("/"):
            img_url = "https://www.imoti.net" + img_url
        full_url = a["href"] if a["href"].startswith("http") else "https://www.imoti.net" + a["href"]
        price = int(re.sub(r"\D", "", price_match.group(1))) if price_match else None
        sqm = int(sqm_match.group(1)) if sqm_match else None

        seen[listing_id] = {
            "id": listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price,
            "sqm": sqm,
            "title": text[:120],
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
        score = round(min(drop_pct / 20, 1) * 50 + min(days_on_market / 180, 1) * 50)
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
