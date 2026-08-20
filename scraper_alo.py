"""
Scrapes current Sofia apartment listings from alo.bg.
"""

import re
import json
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

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1

LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
PRICE_RE = re.compile(r"\u0426\u0435\u043d\u0430:\s*([\d\s]+)\s?\u20ac")
SQM_RE = re.compile(r"\u041a\u0432\u0430\u0434\u0440\u0430\u0442\u0443\u0440\u0430:\s*([\d.,]+)\s?\u043a\u0432\.?\u043c")
AREA_RE = re.compile(r"([\u0410-\u042f\u0430-\u044f\w\s]{2,30}),\s*\u0421\u043e\u0444\u0438\u044f")


def smallest_container_with_price(link_tag, max_levels=6, debug=False):
    node = link_tag
    for i in range(max_levels):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        matches = PRICE_RE.findall(text)
        if debug:
            print(f"DEBUG:   level {i+1}: {len(matches)} price matches, text length {len(text)}")
        if len(matches) > MAX_PRICE_MENTIONS:
            if debug:
                print("DEBUG:   -> too many price mentions, giving up on this link")
            return None
        if len(matches) == 1 and len(text) <= MAX_CARD_TEXT_LENGTH:
            if debug:
                print("DEBUG:   -> accepted this container")
            return node
    if debug:
        print("DEBUG:   -> ran out of levels, no container found")
    return None


def fetch_listings(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"DEBUG: HTTP status code = {resp.status_code}")

    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
    print(f"DEBUG: links matching listing URL pattern = {len(matching_links)}")

    seen = {}
    debug_count = 0
    for a in matching_links:
        match = LISTING_LINK_RE.search(a["href"])
        listing_id = match.group(1)
        if listing_id in seen:
            continue

        show_debug = debug_count < 3
        if show_debug:
            print(f"DEBUG: trying link href={a['href']}")
            debug_count += 1

        container = smallest_container_with_price(a, debug=show_debug)
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
        if img_url and img_url.startswith("/"):
            img_url = BASE_URL + img_url

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
            history[lid] =
