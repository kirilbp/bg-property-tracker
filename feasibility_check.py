"""
Round 9: dump ALL hrefs on the Sofia results grid (not filtered by a guessed
pattern) to find the real per-listing link structure, since round 8 showed
0 matches for the homepage-widget's "-id.htm" pattern despite 8 pages of
confirmed pagination existing.
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
        page.wait_for_timeout(2500)

        print("resulting URL:", page.url)

        all_hrefs = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href]')).map(a => a.getAttribute('href'))
        """)
        print("total <a> tags:", len(all_hrefs))

        # Group by a rough "shape": strip digits to find repeating URL patterns.
        from collections import Counter
        shapes = Counter()
        examples = {}
        for h in all_hrefs:
            if not h or h.startswith("javascript") or h.startswith("#"):
                continue
            shape = re.sub(r"\d+", "#", h)
            shapes[shape] += 1
            if shape not in examples:
                examples[shape] = h

        print("\n--- most common href shapes (likely listing cards among the high-count ones) ---")
        for shape, count in shapes.most_common(20):
            print(f"count={count}  shape={shape}  example={examples[shape]}")

        browser.close()


if __name__ == "__main__":
    main()
