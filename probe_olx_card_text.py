"""
Diagnostic-only: round 4 (final) for olx.bg nationwide. Confirms the real
card text layout for non-Sofia oblast queries, since AREA_LINE_RE
currently only matches "^гр\\. София, ..." (hardcoded) and per-oblast
slicing at this granularity can return listings from multiple settlements
within an oblast, not just its namesake city - so the city tag needs to
come from parsed text (like alo.bg), not trusted from the query the way
imot.bg's per-city queries could.

Samples real Plovdiv and Varna oblast card text directly.

Read-only, no commit step - deleted once the question is answered.
"""

import re

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/d/ad/[^\"'#]*-ID(\w+)\.html")
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
        if 1 <= len(matches) <= 1 and len(text) <= 500:
            return node
    return None


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()

    for label, slug in [("Plovdiv oblast", "oblast-plovdiv"), ("Varna oblast", "oblast-varna"), ("Burgas oblast", "oblast-burgas")]:
        page.goto(f"{BASE}/{slug}/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        all_links = soup.find_all("a", href=True)
        matching = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
        print(f"=== {label}: {len(matching)} listing links, showing first 5 cards ===")
        shown = 0
        for a in matching:
            container = smallest_container_with_price(a)
            if container is None:
                continue
            lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
            print(f"  lines: {lines[:4]}")
            shown += 1
            if shown >= 5:
                break

    browser.close()

print("\ndone")
