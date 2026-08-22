"""
Investigate OLX.bg's pagination structure for the Sofia real-estate-sales
search (scraper_olx.py). scraper_olx.py currently only fetches SEARCH_URL
once with no pagination loop at all - check for a page-number URL pattern
or "load more" mechanism, and any stated total listing count.
"""

import re
from playwright.sync_api import sync_playwright

SEARCH_URL = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        print("page url:", page.url)
        print("page title:", page.title())

        body_text = page.inner_text("body")
        for m in re.finditer(r"[\d][\d\s,]{1,8}\s?(обяви|резултат[а-я]*|listings?|offers?)", body_text, re.IGNORECASE):
            print("COUNT CANDIDATE:", repr(body_text[max(0, m.start()-40):m.end()+10]))

        print("\n--- pagination-related links ---")
        links = page.eval_on_selector_all("a[href]", """
        els => els.map(a => ({href: a.getAttribute('href'), text: a.textContent.trim().slice(0,40)}))
        """)
        seen = set()
        for l in links:
            href = l["href"] or ""
            text = l["text"] or ""
            if re.search(r"page", href, re.IGNORECASE) or re.fullmatch(r"\d{1,4}", text.strip()):
                if href not in seen:
                    seen.add(href)
                    print(repr(href), "|", repr(text))

        print("\n--- elements with class/id containing 'pag' ---")
        pag_html = page.eval_on_selector_all("[class*=pag i], [data-testid*=pag i]", """
        els => els.slice(0, 5).map(e => e.outerHTML.slice(0, 500))
        """)
        for h in pag_html:
            print(h)
            print("---")

        listing_count = page.eval_on_selector_all("a[href*='/d/ad/']", "els => els.length")
        print("\nlisting-link count on this load:", listing_count)

        browser.close()


if __name__ == "__main__":
    main()
