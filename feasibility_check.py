"""
Round 3: simulate the real click flow on imoti.bg's homepage search form -
open the select2 location dropdown, click "София" (the city option, not
"София област"), keep "Продажба" (sell) selected, click the real "Търси"
button, then inspect the resulting page: URL, listing count, neighbourhood
diversity, pagination depth. This is the actual test of whether Sofia
filtering produces genuine results or the same thin nationwide batch as
before.
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

        print("Step 1: open the select2 location dropdown")
        page.click("#s2id_district_id .select2-choice")
        page.wait_for_timeout(500)

        print("Step 2: type 'София' into the select2 search box")
        page.fill("#s2id_autogen1_search", "София")
        page.wait_for_timeout(800)

        print("Step 3: dump visible dropdown results")
        results = page.evaluate("""
        () => Array.from(document.querySelectorAll('.select2-results li')).map(li => li.textContent.trim())
        """)
        print("visible options:", results)

        print("Step 4: click the exact 'София' result (not 'София област')")
        # select2 renders results as <li><div>Text</div></li>; match exact text.
        clicked = page.evaluate("""
        () => {
          const items = Array.from(document.querySelectorAll('.select2-results li'));
          const exact = items.find(li => li.textContent.trim() === 'София');
          if (exact) { exact.querySelector('div, span, .select2-result-label')?.click() || exact.click(); return true; }
          return false;
        }
        """)
        print("clicked exact match via JS:", clicked)
        page.wait_for_timeout(500)

        selected_text = page.evaluate("() => document.getElementById('select2-chosen-1')?.textContent")
        print("select2 now shows:", selected_text)
        district_value = page.eval_on_selector("#district_id", "el => el.value")
        print("underlying select value:", district_value)

        print("\nStep 5: click the real 'Търси' search button")
        with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
            page.click("a.button.button-primary:has-text('Търси')")
        page.wait_for_timeout(1500)

        print("\nresulting URL:", page.url)
        print("resulting title:", page.title())

        html = page.content()
        listing_link_count = len(re.findall(r'href="https://imoti\.bg/(продажби|наеми)/[^"]+"', html))
        print("listing-detail links found on results page:", listing_link_count)

        # sample some listing titles/areas from the page text
        sample = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href*="/продажби/"], a[href*="/наеми/"]'))
          .map(a => a.textContent.trim()).filter(t => t.length > 10).slice(0, 20)
        """)
        print("\nsample listing texts:")
        for s in sample:
            print(" ", repr(s))

        # pagination check
        page_links = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href*="page="], .pagination a')).map(a => a.textContent.trim()).slice(0, 20)
        """)
        print("\npagination elements:", page_links)

        browser.close()


if __name__ == "__main__":
    main()
