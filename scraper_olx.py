"""
Scrapes current Sofia apartment listings from OLX.bg.

OLX.bg blocks plain requests-based fetching (an Akamai-style edge check
returns a 403 before any content), but a real headless browser gets through
cleanly - confirmed via Playwright/Chromium against the live site. Each
listing card is the smallest ancestor whose text mentions the price
("<amount> €") exactly once, same "climb from the link" approach as
scraper.py, scraper_alo.py, and scraper_imot.py. Within that card the text
follows a consistent per-line layout:
    line 0: title (free text, e.g. "Двустаен апартамент в Младост")
    line 1: "<price> €"
    line 2: "гр. София, <area> - Обновено на <date>" (or Днес/Вчера etc.)
    line 3: "<sqm> кв.м - <price per sqm>"

Search results are paginated with ?page=N (confirmed via the site's own
paginator, and the site itself states "Открихме повече от 1000 обяви" -
found more than 1000 listings). The scraper originally only fetched page 1
with no pagination loop at all - fixed by paging through page=2, page=3,
... until a page comes back with no listings, same "stop on empty page"
pattern as the other scrapers, reusing one browser/page across all
requests (same approach as scraper_imot.py) rather than relaunching
Chromium per page.

A page navigation retries a few times with backoff before being treated as
the end of pagination, so a transient failure doesn't get mistaken for
having reached the last page - and, since scrape.yml runs all 5 scrapers
sequentially with a single git commit step at the end, an uncaught
exception here would otherwise silently discard every other scraper's
output for that run too.

Line 2's "Обновено на <date>" (confirmed live format: "20 август 2026 г.")
or bare "Днес"/"Вчера" reflects when the listing was actually last updated
on OLX, and was previously discarded entirely (only the area before it was
kept). Now parsed into a real date, so days_on_market/motivation score are
computed from that instead of purely from when we first scraped the
listing - otherwise a listing that's actually been up for months shows as
"0 days on market" just because we only just started tracking it.
"""

import re
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/"
BASE_URL = "https://www.olx.bg"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_olx.json"
LEADS_FILE = OUT_DIR / "leads_olx.json"

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1
MAX_PAGES = 40
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

LISTING_LINK_RE = re.compile(r"/d/ad/[^\"'#]*-ID(\w+)\.html")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?€")
PRICE_LINE_RE = re.compile(r"^([\d\s]{3,10})\s?€$")
AREA_LINE_RE = re.compile(r"^гр\.\s*София,\s*(.+?)\s-\s")
UPDATED_RE = re.compile(r"-\s*(Днес|Вчера|Обновено на\s+(\d{1,2})\s+(\S+)\s+(\d{4})\s*г\.?)", re.IGNORECASE)
SQM_RE = re.compile(r"([\d.,]+)\s?кв\.?м")

BG_MONTHS = {
    "януари": 1, "февруари": 2, "март": 3, "април": 4, "май": 5, "юни": 6,
    "юли": 7, "август": 8, "септември": 9, "октомври": 10, "ноември": 11, "декември": 12,
}


def parse_site_updated_at(line):
    m = UPDATED_RE.search(line)
    if not m:
        return None
    now = datetime.now(timezone.utc)
    label = m.group(1).lower()
    if label.startswith("днес"):
        return now.isoformat()
    if label.startswith("вчера"):
        return (now - timedelta(days=1)).isoformat()
    day, month_name, year = m.group(2), m.group(3).lower(), m.group(4)
    month = BG_MONTHS.get(month_name)
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day), tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def fetch_html(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)
    # Listing photos are lazy-loaded as cards enter the viewport, so scroll
    # all the way to the bottom (slowly, so each batch has time to actually
    # finish loading, not just get requested) to force them all in before
    # reading src.
    for _ in range(35):
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(500)
        at_bottom = page.evaluate(
            "window.innerHeight + window.scrollY >= document.body.scrollHeight - 10"
        )
        if at_bottom:
            break
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    return page.content()


def smallest_container_with_price(link_tag, max_levels=8):
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


def fetch_html_with_retries(page, url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fetch_html(page, url)
        except Exception as e:
            print(f"DEBUG: navigation failed for {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                page.wait_for_timeout(RETRY_BACKOFF_SECONDS * attempt * 1000)
    return None


def fetch_listings_page(page, url, seen):
    html = fetch_html_with_retries(page, url)
    if html is None:
        return None
    print(f"DEBUG: fetched HTML length = {len(html)}")
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

        area = "Sofia"
        site_updated_at = None
        for l in lines:
            m = AREA_LINE_RE.match(l)
            if m:
                area = m.group(1).strip()
                site_updated_at = parse_site_updated_at(l)
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
            if candidate and candidate.startswith("http") and "icon" not in candidate.lower():
                img_url = candidate
                break

        href = a["href"]
        full_url = href if href.startswith("http") else BASE_URL + href
        title = f"{lines[0]}, {area}" if lines else area

        seen[listing_id] = {
            "id": "olx_" + listing_id,
            "url": full_url,
            "photo": img_url,
            "price_eur": price_eur,
            "sqm": sqm,
            "area": area,
            "title": title[:150],
            "portal": "olx.bg",
            "site_updated_at": site_updated_at,
        }
    return len(matching_links)


def fetch_listings():
    seen = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            url = SEARCH_URL if page_num == 1 else f"{SEARCH_URL}?page={page_num}"
            link_count = fetch_listings_page(page, url, seen)
            print(f"DEBUG: page {page_num} links matching listing URL pattern = {link_count}")
            if not link_count:
                break

        browser.close()
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
        site_updated_at = latest.get("site_updated_at")
        reference_date = datetime.fromisoformat(site_updated_at) if site_updated_at else datetime.fromisoformat(rec["first_seen"])
        days_on_market = max((datetime.now(timezone.utc) - reference_date).days, 0)
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
