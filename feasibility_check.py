"""
Round 2: find imot.bg's real Sofia apartments-for-sale search URL, following
the /obiavi/prodazhbi link pattern found on the homepage.
"""

import re
from playwright.sync_api import sync_playwright

BLOCK_MARKERS = [
    "captcha", "cloudflare", "access denied", "just a moment",
    "не е намерена", "403 forbidden", "attention required", "are you human",
]


def check(page, url, label):
    print("=" * 70)
    print(f"{label}  ->  {url}")
    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    print(f"status: {resp.status if resp else None}  final_url: {page.url}")
    page.wait_for_timeout(1500)
    html = page.content()
    print(f"html length: {len(html)}  title: {page.title()}")
    lower = html.lower()
    hits = [m for m in BLOCK_MARKERS if m in lower]
    if hits:
        print(f"  BLOCK MARKERS FOUND: {hits}")
    links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    relevant = sorted(set(
        h for h in links
        if h and ("sofia" in h.lower() or "sofiya" in h.lower())
    ))
    print(f"  sofia-relevant links: {len(relevant)}")
    for l in relevant[:40]:
        print("    ", l)
    return page.url, html


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="bg-BG",
        )
        page = context.new_page()

        check(page, "https://www.imot.bg/obiavi/prodazhbi", "Sales category root")
        check(page, "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya", "Guessed Sofia sales")
        check(page, "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya/dvustaen", "Guessed Sofia 2-room sales")

        browser.close()


if __name__ == "__main__":
    main()
