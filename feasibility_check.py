"""
Round 1: check whether bazar.bg is reachable via plain requests, and discover
the URL for its Sofia apartments-for-sale category (it's a general classifieds
site, not property-only, so we need the real estate sub-section).
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

BLOCK_MARKERS = ["captcha", "access denied", "cloudflare", "just a moment", "attention required"]


def check(url):
    print("=" * 70)
    print("GET", url)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print("status:", r.status_code, "length:", len(r.text))
        lower = r.text.lower()
        markers = [m for m in BLOCK_MARKERS if m in lower]
        if markers:
            print("BLOCK MARKERS FOUND:", markers)
        return r
    except Exception as e:
        print("ERROR:", e)
        return None


def main():
    r = check("https://bazar.bg/")
    if r is None or r.status_code != 200:
        print("Homepage not reachable via plain requests.")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    print("\n--- links mentioning 'imot' (real estate) in href or text ---")
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if "imot" in href.lower() or "imot" in text.lower():
            key = href
            if key not in seen:
                seen.add(key)
                print(repr(href), "|", repr(text[:60]))
        if len(seen) >= 30:
            break

    print("\n--- title ---")
    print(soup.title.string if soup.title else None)


if __name__ == "__main__":
    main()
