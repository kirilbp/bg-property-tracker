"""
One-off feasibility check: can a headless browser (Playwright) get past
OLX.bg's Akamai-style edge 403 where plain requests-based fetching is
blocked? Not part of the scraper suite - run manually, then deleted.
"""

import re
from playwright.sync_api import sync_playwright

BLOCK_MARKERS = [
    "captcha", "cloudflare", "access denied", "just a moment",
    "не е намерена", "403 forbidden", "attention required", "are you human",
    "pardon our interruption", "verify you are human", "request could not be satisfied",
]


def check(page, url, label):
    print("=" * 70)
    print(f"{label}  ->  {url}")
    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    print(f"status: {resp.status if resp else None}  final_url: {page.url}")
    page.wait_for_timeout(2000)
    html = page.content()
    print(f"html length: {len(html)}")
    print(f"title: {page.title()}")
    lower = html.lower()
    hits = [m for m in BLOCK_MARKERS if m in lower]
    if hits:
        print(f"  BLOCK MARKERS FOUND: {hits}")
    else:
        print("  no block markers found")
    price_hits = len(re.findall(r"[\d\s]{3,12}\s?(лв|eur|€)", html, re.IGNORECASE))
    print(f"  price-like patterns: {price_hits}")
    links = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    relevant = sorted(set(
        h for h in links
        if h and any(k in h.lower() for k in ["sofia", "sofiya", "apartament", "prodazh", "obiava", "-id"])
    ))
    print(f"  relevant links found: {len(relevant)}")
    for l in relevant[:30]:
        print("    ", l)
    print(f"  snippet: {html[:600]}")
    return html


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="bg-BG",
        )
        page = context.new_page()

        check(page, "https://www.olx.bg/", "Homepage")
        check(page, "https://www.olx.bg/nedvizhimi-imoti/apartamenti/prodazhbi/grad-sofia/", "Guessed Sofia apartment sales")

        browser.close()


if __name__ == "__main__":
    main()
