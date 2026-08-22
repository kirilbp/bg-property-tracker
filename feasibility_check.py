"""
Round 6: fix cookie-banner dismissal - round 5's substring text match
('Съгласен') likely hit the newsletter agreement checkbox label instead of
the actual cookie banner button, leaving the page in a broken state. Target
the banner specifically by its known wrapper class (.cc_banner-wrapper) and
verify the select2 dropdown is still present before continuing.
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

        print("Step 0: dismiss cookie-consent banner (scoped to .cc_banner-wrapper only)")
        banner = page.locator(".cc_banner-wrapper")
        print("banner present:", banner.count())
        if banner.count() > 0:
            btn_texts = page.evaluate("""
            () => Array.from(document.querySelectorAll('.cc_banner-wrapper button, .cc_banner-wrapper a'))
              .map(b => b.textContent.trim())
            """)
            print("banner buttons/links:", btn_texts)
            removed = page.evaluate("""
            () => { const b = document.querySelector('.cc_banner-wrapper'); if (b) { b.remove(); return true; } return false; }
            """)
            print("banner force-removed via JS:", removed)
        page.wait_for_timeout(300)

        print("\nverify select2 dropdown element still present:")
        print("count:", page.locator("#s2id_district_id").count())

        print("\nStep 1: open the select2 location dropdown")
        page.click("#s2id_district_id .select2-choice", timeout=10000)
        page.wait_for_timeout(500)

        print("Step 2: real Playwright click on the exact 'София' list item")
        sofia_item = page.locator("#select2-results-1 li").filter(has_text=re.compile(r"^София$"))
        print("matches for exact 'София':", sofia_item.count())
        sofia_item.first.click(timeout=5000)
        page.wait_for_timeout(500)

        selected_text = page.evaluate("() => document.getElementById('select2-chosen-1')?.textContent")
        print("select2 now shows:", selected_text)
        district_value = page.eval_on_selector("#district_id", "el => el.value")
        print("underlying select value:", district_value)

        print("\nStep 3: click the real 'Търси' search button")
        with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
            page.click("#btnSearch2", force=True)
        page.wait_for_timeout(1500)

        print("\nresulting URL:", page.url)
        print("resulting title:", page.title())

        html = page.content()
        listing_link_count = len(re.findall(r'href="https://imoti\.bg/(продажби|наеми)/[^"]+"', html))
        print("listing-detail links found on results page:", listing_link_count)

        sample = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href*="/продажби/"], a[href*="/наеми/"]'))
          .map(a => a.textContent.trim()).filter(t => t.length > 10).slice(0, 25)
        """)
        print("\nsample listing texts:")
        for s in sample:
            print(" ", repr(s))

        page_links = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href*="page="], .pagination a')).map(a => a.textContent.trim()).slice(0, 20)
        """)
        print("\npagination elements:", page_links)

        browser.close()


if __name__ == "__main__":
    main()
