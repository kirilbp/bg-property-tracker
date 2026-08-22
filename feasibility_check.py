"""
Investigate imot.bg's pagination structure for the Sofia sale-listings search,
and find the site's own stated total listing count so we can verify the fix
against it. scraper_imot.py currently only fetches SEARCH_URL once (page 1,
46 listings) with no pagination loop at all, while imot.bg's own UI claims
1000+ Sofia sale listings.
"""

from playwright.sync_api import sync_playwright

SEARCH_URL = "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya"
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
        # Look for any "N обяви" / "N резултата" / total-count style text near the top.
        import re
        for m in re.finditer(r"[\d\s]{2,7}(обяви|резултат[а-я]*|imots?)", body_text, re.IGNORECASE):
            snippet = body_text[max(0, m.start()-40):m.end()+10].replace("\n", " | ")
            print("COUNT CANDIDATE:", repr(snippet))

        print("\n--- pagination-related links/elements ---")
        links = page.eval_on_selector_all("a[href]", """
        els => els.map(a => ({href: a.getAttribute('href'), text: a.textContent.trim().slice(0,40)}))
        """)
        seen = set()
        for l in links:
            href = l["href"] or ""
            text = l["text"] or ""
            if re.search(r"page|f1=|str=|p=\d", href, re.IGNORECASE) or re.fullmatch(r"\d{1,4}", text.strip()):
                key = href
                if key not in seen:
                    seen.add(key)
                    print(repr(href), "|", repr(text))

        print("\n--- elements with class/id containing 'pag' ---")
        pag_html = page.eval_on_selector_all("[class*=pag i], [id*=pag i]", """
        els => els.slice(0, 5).map(e => e.outerHTML.slice(0, 500))
        """)
        for h in pag_html:
            print(h)
            print("---")

        # Count listing links on page 1 to sanity-check against the known 46.
        listing_count = page.eval_on_selector_all(
            "a[href*='/obiava-']", "els => els.length"
        )
        print("\nlisting-link count on page 1:", listing_count)

        browser.close()


if __name__ == "__main__":
    main()
