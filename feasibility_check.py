"""
Round 5: diagnose why area extraction and photo extraction are failing on
scraper_olx.py, by dumping the raw per-line text and all <img> tags for a
few real listing containers.
"""

import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

MAX_CARD_TEXT_LENGTH = 500
MAX_PRICE_MENTIONS = 1
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
        if len(matches) > MAX_PRICE_MENTIONS:
            return None
        if 1 <= len(matches) <= MAX_PRICE_MENTIONS and len(text) <= MAX_CARD_TEXT_LENGTH:
            return node
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
    print(f"total matching links: {len(matching_links)}")

    seen_ids = set()
    shown = 0
    for a in matching_links:
        m = LISTING_LINK_RE.search(a["href"])
        lid = m.group(1)
        if lid in seen_ids:
            continue
        seen_ids.add(lid)

        container = smallest_container_with_price(a)
        if container is None:
            continue

        lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
        print("=" * 70)
        print("id:", lid)
        print("lines (repr):")
        for l in lines:
            print("   ", repr(l))

        imgs = container.find_all("img")
        print(f"  <img> tags found: {len(imgs)}")
        for img in imgs:
            print("    src=", img.get("src"), "data-src=", img.get("data-src"),
                  "srcset=", (img.get("srcset") or "")[:100], "class=", img.get("class"))

        shown += 1
        if shown >= 5:
            break


if __name__ == "__main__":
    main()
