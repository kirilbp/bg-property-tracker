"""
Round 5: fix two bugs found in round 4 - (1) a JS-dispatched .click() on the
select2 list item doesn't fire select2's real mouse event handlers, so use a
real Playwright click on the exact-match locator instead; (2) a cookie-
consent banner intercepts pointer events on the search button, so dismiss it
first. Then complete the full click flow and inspect results.
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

        print("Step 0: dismiss cookie-consent banner if present")
        for text in ["Приемам", "Разбрах", "Съгласен", "OK", "Приеми"]:
            btn = page.locator(f"button:has-text('{text}'), a:has-text('{text}')")
            if btn.count() > 0:
                try:
                    btn.first.click(timeout=3000)
                    print("  dismissed via button text:", text)
                    break
                except Exception as e:
                    print("  click failed for", text, e)
        page.evaluate("() => { const b = document.querySelector('.cc_banner-wrapper'); if (b) b.remove(); }")
        page.wait_for_timeout(300)

        print("\nStep 1: open the select2 location dropdown")
        page.click("#s2id_district_id .select2-choice")
        page.wait_for_timeout(500)

        print("Step 2: real Playwright click on the exact 'София' list item")
        # Use exact text match via get_by_text(exact=True) restricted to the results list.
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
