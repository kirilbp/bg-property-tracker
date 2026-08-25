"""
Diagnostic-only: round 3 for the alo.bg nationwide conversion. Rounds 1-2
confirmed the location filter can just be dropped for nationwide results
(~156,000 listings, no depth cap through page 2600) and that per-page
listing count is 60 nationwide (vs 30 Sofia-only). Before touching
AREA_RE (currently hardcoded to match "<area words>, София" specifically),
this pulls real full container text for a handful of non-Sofia listings
from a deep nationwide page, since the area name sits inside a much
longer card text blob (agency name, "преди N дни", sqm, etc, all
comma-separated too) - unlike imoti.net's clean title-only string, so a
generic "last comma" split isn't safe to assume without seeing the real
shape first.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/"
LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
PRICE_RE = re.compile(r"Цена\s*:\s*([\d\s]+)\s?€")
MAX_CARD_TEXT_LENGTH = 1500
MAX_PRICE_MENTIONS = 1


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


url = f"{BASE}?page=800"
resp = requests.get(url, headers=HEADERS, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")
all_links = soup.find_all("a", href=True)
matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
print(f"page 800: {len(matching_links)} listing links found")

shown = 0
for a in matching_links:
    if shown >= 10:
        break
    container = smallest_container_with_price(a)
    if container is None:
        continue
    text = container.get_text(" ", strip=True)
    if "София" in text:
        continue  # skip Sofia ones, we want to see non-Sofia card shape
    print(f"\n--- listing {shown + 1} (href={a['href']}) ---")
    print(text[:600])
    shown += 1
    time.sleep(0.1)

print(f"\ndone, showed {shown} non-Sofia samples")
