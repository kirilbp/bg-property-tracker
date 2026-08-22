"""
Round 4: inspect the actual listing card markup on bazar.bg's Sofia
apartments-for-sale page, to design the scraper's extraction logic.
"""

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

URL = "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia"


def main():
    r = requests.get(URL, headers=HEADERS, timeout=15)
    print("status:", r.status_code, "length:", len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")

    # Listing detail links usually look like /obiava-<id>/<slug>
    LISTING_RE = re.compile(r"^/obiava-(\d+)/")
    links = [a for a in soup.find_all("a", href=True) if LISTING_RE.match(a["href"])]
    print(f"total listing links found: {len(links)}")

    seen_ids = set()
    shown = 0
    for a in links:
        m = LISTING_RE.match(a["href"])
        lid = m.group(1)
        if lid in seen_ids:
            continue
        seen_ids.add(lid)

        # climb up to find a reasonably-sized card container
        node = a
        card = None
        for _ in range(6):
            if node.parent is None:
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            if 40 <= len(text) <= 600:
                card = node
                break

        print("=" * 70)
        print("id:", lid, "href:", a["href"])
        if card is not None:
            lines = [l.strip() for l in card.get_text("\n", strip=True).split("\n") if l.strip()]
            for l in lines:
                print("   ", repr(l))
        else:
            print("   (no card found)")

        shown += 1
        if shown >= 8:
            break

    print("\n--- page listing-count text (sanity check on total for-sale-apartments-sofia count) ---")
    h1 = soup.find("h1")
    print("h1:", h1.get_text(strip=True) if h1 else None)
    # look for a count string like "1 234 обяви" near top
    body_text = soup.get_text(" ", strip=True)
    m = re.search(r"[\d\s]{2,7}обяви", body_text)
    print("count text near top:", m.group(0) if m else None)


if __name__ == "__main__":
    main()
