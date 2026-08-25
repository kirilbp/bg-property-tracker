"""
Diagnostic-only: round 9 (final) for imot.bg nationwide. Confirms the
card text layout (title / "град <City>, <area>" / price / sqm) that
scraper_imot.py's AREA_LINE_RE ("^град София,\\s*(.+)$") currently assumes
Sofia-only still holds for non-Sofia cities, before generalizing the
regex. Samples real Plovdiv and Varna card text directly.

Read-only, no commit step - deleted once the question is answered.
"""

import re

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE = "https://www.imot.bg/obiavi/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/obiava-(\d[a-z]\d{10,})-")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?€")


def smallest_container_with_price(link_tag, max_levels=8):
    node = link_tag
    for _ in range(max_levels):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        matches = PRICE_RE.findall(text)
        if len(matches) > 1:
            return None
        if 1 <= len(matches) <= 1 and len(text) <= 800:
            return node
    return None


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()

    for city, slug in [("Plovdiv", "grad-plovdiv"), ("Varna", "grad-varna"), ("Burgas", "grad-burgas")]:
        page.goto(f"{BASE}/{slug}", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1200)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        all_links = soup.find_all("a", href=True)
        matching = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
        print(f"=== {city}: {len(matching)} listing links, showing first 3 cards ===")
        shown = 0
        for a in matching:
            container = smallest_container_with_price(a)
            if container is None:
                continue
            lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
            print(f"  lines: {lines[:5]}")
            shown += 1
            if shown >= 3:
                break

    browser.close()

print("\ndone")
