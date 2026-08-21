"""
One-off feasibility check for candidate portals: fetch each site's Sofia
apartment-for-sale search page and report whether it returns real listing
HTML or blocks the request. Not part of the scraper suite - run manually via
the temporary feasibility-check workflow, then deleted.
"""

import re
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

SITES = [
    ("OLX.bg", "https://www.olx.bg/nedvizhimi-imoti/apartamenti/prodazhbi/grad-sofia/"),
    ("Homes.bg", "https://www.homes.bg/prodazhbi/apartamenti/sofia"),
    ("Holmes.bg", "https://holmes.bg/"),
    ("Imoti.info", "https://www.imoti.info/sofia/prodazhba/apartamenti"),
    ("Objavi.bg", "https://www.objavi.bg/"),
    ("Obqvi.bg", "https://www.obqvi.bg/"),
    ("BezplatniObqvi.com", "https://www.bezplatniobqvi.com/"),
    ("Oglasibg.com", "https://www.oglasibg.com/"),
]

BLOCK_MARKERS = [
    "captcha", "cloudflare", "access denied", "just a moment",
    "не е намерена", "403 forbidden", "attention required",
]

PRICE_RE = re.compile(r"(\d[\d\s]{2,10})\s?(лв|bgn|eur|€)", re.IGNORECASE)


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
            price_hits = len(PRICE_RE.findall(text))
            print(f"  price-like patterns found: {price_hits}")
            print(f"  snippet: {text[:300].strip().replace(chr(10), ' ')}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
