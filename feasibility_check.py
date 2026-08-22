"""
Round 2: find OLX.bg's real real-estate/Sofia category navigation links.
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
        page.goto("https://www.olx.bg/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.getAttribute('href'), text: e.innerText.trim()}))"
        )
        # dedupe, keep only nav-looking ones (short text, category-ish paths)
        seen = set()
        candidates = []
        for l in links:
            href = l["href"] or ""
            text = l["text"] or ""
            if href in seen:
                continue
            seen.add(href)
            if href.startswith("/") and not href.startswith("/d/ad/") and len(href) < 60:
                candidates.append((href, text))

        print(f"total unique nav-like links: {len(candidates)}")
        for href, text in sorted(candidates):
            print(f"  {href!r:55s} text={text!r}")

        browser.close()


if __name__ == "__main__":
    main()
