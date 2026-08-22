"""
Round 7: with the click flow confirmed working, pull actual listing card
content (title, area, price) from the Sofia-filtered results page to verify
data richness and diversity - not just the raw link count.
"""

import re
from playwright.sync_api import sync_playwright

URL = "https://imoti.bg"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        page.evaluate("() => { const b = document.querySelector('.cc_banner-wrapper'); if (b) b.remove(); }")
        page.wait_for_timeout(300)

        page.click("#s2id_district_id .select2-choice", timeout=10000)
        page.wait_for_timeout(500)
        sofia_item = page.locator("#select2-results-1 li").filter(has_text=re.compile(r"^София$"))
        sofia_item.first.click(timeout=5000)
        page.wait_for_timeout(500)

        with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
            page.click("#btnSearch2", force=True)
        page.wait_for_timeout(2000)

        print("resulting URL:", page.url)

        # Climb from each listing link to a reasonably sized card and dump its text.
        links = page.locator('a[href*="/продажби/"], a[href*="/наеми/"]')
        n = links.count()
        print("total matching links:", n)

        seen_hrefs = set()
        shown = 0
        for i in range(n):
            href = links.nth(i).get_attribute("href")
            if not href or href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            text = links.nth(i).inner_text().strip()
            if len(text) > 15:
                print("=" * 60)
                print("href:", href)
                print("text:", repr(text))
                shown += 1
            if shown >= 15:
                break

        print("\nunique hrefs total:", len(seen_hrefs))

        browser.close()


if __name__ == "__main__":
    main()
