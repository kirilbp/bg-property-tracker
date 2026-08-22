"""
One-off feasibility check: can a plain requests-based fetch reach imoti.bg's
Sofia apartment-for-sale search page, or does it get blocked?
Not part of the scraper suite - run manually, then deleted.
"""

import re
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

BLOCK_MARKERS = [
    "captcha", "cloudflare", "access denied", "just a moment",
    "не е намерена", "403 forbidden", "attention required", "are you human",
]

SITES = [
    ("Homepage", "https://www.imoti.bg/"),
    ("Guessed Sofia sales 1", "https://www.imoti.bg/obiavi/prodazhba/sofia/apartamenti"),
    ("Guessed Sofia sales 2", "https://www.imoti.bg/sofia/prodazhba/apartamenti"),
]


def main():
    for name, url in SITES:
        print("=" * 70)
        print(f"{name}  ->  {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
            text = resp.text
            print(f"status: {resp.status_code}  final_url: {resp.url}  len: {len(text)}")
            lower = text.lower()
            hits = [m for m in BLOCK_MARKERS if m in lower]
            if hits:
                print(f"  BLOCK MARKERS FOUND: {hits}")
            price_hits = len(re.findall(r"[\d\s]{3,10}\s?(лв|eur|€)", text, re.IGNORECASE))
            print(f"  price-like patterns: {price_hits}")
            print(f"  snippet: {text[:400].strip().replace(chr(10), ' ')}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
