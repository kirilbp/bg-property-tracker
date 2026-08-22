"""
Round 11: test whether the Sofia-filtered sales URL discovered via the click
flow (https://imoti.bg/продажби/di:софия/cu:BGN) is bookmarkable/stateless -
i.e. whether it can be fetched directly (plain requests, or a fresh
Playwright navigation with no prior click flow) without needing to repeat
the select2+search click simulation on every scrape run. If so, the
production scraper can skip the fragile click flow entirely for pages 2+
(and possibly page 1 too).
"""

import requests
from playwright.sync_api import sync_playwright

DIRECT_URL = "https://imoti.bg/продажби/di:софия/cu:BGN"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def check_requests():
    print("=== plain requests.get ===")
    try:
        r = requests.get(DIRECT_URL, headers={"User-Agent": USER_AGENT, "Accept-Language": "bg-BG,bg;q=0.9"}, timeout=15)
        print("status:", r.status_code, "length:", len(r.text))
        print("contains 'Надежда' (a real Sofia area seen before):", "Надежда" in r.text)
        print("contains listing href pattern:", "-апартамент/софия/" in r.text)
    except Exception as e:
        print("ERROR:", e)


def check_playwright_direct():
    print("\n=== fresh Playwright navigation, no click flow ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()
        page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        print("final URL:", page.url)
        print("title:", page.title())
        html = page.content()
        print("contains 'Надежда':", "Надежда" in html)
        print("contains listing href pattern:", "-апартамент/софия/" in html)
        browser.close()


def main():
    check_requests()
    check_playwright_direct()


if __name__ == "__main__":
    main()
