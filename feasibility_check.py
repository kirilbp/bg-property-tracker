"""
Round 6: widen the card climb to find sqm/rooms info, sample more listings to
verify category filtering (all titles/areas genuinely Sofia apartments), and
check pagination.
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
LISTING_RE = re.compile(r"obiava-(\d+)")


def main():
    r = requests.get(URL, headers=HEADERS, timeout=15)
    print("status:", r.status_code, "length:", len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")

    links = [a for a in soup.find_all("a", href=True) if LISTING_RE.search(a["href"])]
    print(f"total listing links found: {len(links)}")

    seen_ids = set()
    all_titles = []
    shown = 0
    for a in links:
        m = LISTING_RE.search(a["href"])
        lid = m.group(1)
        if lid in seen_ids:
            continue
        seen_ids.add(lid)

        node = a
        card = None
        for _ in range(9):
            if node.parent is None:
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            if 40 <= len(text) <= 900:
                card = node
                # keep climbing a bit more to see if a bigger card captures sqm too;
                # but stop once we clearly exceed one listing (multiple price/€ signs)
                euro_count = text.count("€")
                if euro_count > 1:
                    card = None
                    break

        if card is not None:
            lines = [l.strip() for l in card.get_text("\n", strip=True).split("\n") if l.strip()]
            title = lines[0] if lines else ""
            all_titles.append(title)
            if shown < 10:
                print("=" * 70)
                print("id:", lid)
                for l in lines:
                    print("   ", repr(l))
        shown += 1

    print("\n--- ALL sampled titles (category-filtering sanity check) ---")
    for t in all_titles:
        print(" ", repr(t))

    print("\n--- pagination check ---")
    for a in soup.find_all("a", href=True):
        if "page=" in a["href"]:
            print(repr(a["href"]), "|", repr(a.get_text(strip=True)))


if __name__ == "__main__":
    main()
