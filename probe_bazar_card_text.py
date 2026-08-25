"""
Diagnostic-only: round 4 (final) for bazar.bg nationwide. Confirms the
real card text layout for non-Sofia city queries, since AREA_LINE_RE
currently only matches "^гр\\. София, ..." (hardcoded). Samples real
Plovdiv, Varna and Burgas card text directly.

Read-only, no commit step - deleted once the question is answered.
"""

import re

import requests
from bs4 import BeautifulSoup

BASE = "https://bazar.bg/obiavi/prodazhba-apartamenti"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}
LISTING_LINK_RE = re.compile(r"obiava-(\d+)")
PRICE_RE = re.compile(r"[\d\s]{3,10}\s?€")


def smallest_container_with_price(link_tag, max_levels=9):
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


for city, slug in [("Plovdiv", "plovdiv"), ("Varna", "varna"), ("Burgas", "burgas")]:
    r = requests.get(f"{BASE}/{slug}", headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    all_links = soup.find_all("a", href=True)
    matching = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
    print(f"=== {city}: {len(matching)} listing links, showing first 5 cards ===")
    shown = 0
    for a in matching:
        container = smallest_container_with_price(a)
        if container is None:
            continue
        lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
        print(f"  lines: {lines[:6]}")
        shown += 1
        if shown >= 5:
            break

print("\ndone")
