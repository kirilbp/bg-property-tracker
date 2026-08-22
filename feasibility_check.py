"""
Round 3: drill into OLX.bg's real-estate category to find sale/apartment/
Sofia subcategory links and inspect one real listing card's structure.
"""

import json
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="bg-BG",
        )
        page = context.new_page()
        page.goto("https://www.olx.bg/nedvizhimi-imoti/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        print("title:", page.title())
        print("final url:", page.url)

        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.getAttribute('href'), text: e.innerText.trim()}))"
        )
        seen = set()
        candidates = []
        for l in links:
            href = l["href"] or ""
            text = l["text"] or ""
            if href in seen or not href.startswith("/nedvizhimi-imoti"):
                continue
            seen.add(href)
            candidates.append((href, text))

        print(f"\nreal-estate subcategory/filter links: {len(candidates)}")
        for href, text in sorted(candidates):
            print(f"  {href!r:60s} text={text!r}")

        # also grab a sample of actual ad links + prices from this general page
        ad_links = page.eval_on_selector_all(
            "a[href*='/d/ad/']", "els => els.slice(0,10).map(e => e.getAttribute('href'))"
        )
        print(f"\nsample ad links on /nedvizhimi-imoti/: {len(ad_links)}")
        for l in ad_links:
            print("  ", l)

        browser.close()


if __name__ == "__main__":
    main()
