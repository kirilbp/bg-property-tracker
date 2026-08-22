"""
Round 10: with the real listing-link pattern confirmed (ends in -<id>.htm
followed by /di:.../cu:... filter-context suffix, not end-of-string), inspect
actual card content (price, area, photo) for apartment-type listings only, to
design the real scraper's extraction logic.
"""

import re
from playwright.sync_api import sync_playwright

URL = "https://imoti.bg"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

APARTMENT_SLUGS = [
    "едностаен-апартамент", "двустаен-апартамент", "тристаен-апартамент",
    "четиристаен-апартамент", "многостаен", "мезонет",
]
LISTING_HREF_RE = re.compile(r"/продажби/(" + "|".join(APARTMENT_SLUGS) + r")/софия/([^/]+)-(\d{5,})\.htm")


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
        apt_hrefs = sorted(set(h for h in all_hrefs if h and LISTING_HREF_RE.search(h)))
        print("apartment-type listing hrefs found:", len(apt_hrefs))

        print("\n--- sample card contents (climbing from link) ---")
        for h in apt_hrefs[:10]:
            loc = page.locator(f'a[href="{h}"]').first
            try:
                lines = loc.evaluate("""
                (el) => {
                  let node = el;
                  let best = null;
                  for (let i = 0; i < 8; i++) {
                    if (!node.parentElement) break;
                    node = node.parentElement;
                    const t = node.textContent.trim();
                    if (t.length > 20 && t.length < 500) { best = t; }
                    if (t.length >= 500) break;
                  }
                  return best;
                }
                """)
            except Exception as e:
                lines = f"(error: {e})"
            print("=" * 60)
            print("href:", h)
            print("card text:", repr(lines))

            imgs = loc.evaluate("""
            (el) => {
              let node = el;
              for (let i = 0; i < 8; i++) {
                if (!node.parentElement) break;
                node = node.parentElement;
                const imgs = node.querySelectorAll('img');
                if (imgs.length > 0) {
                  return Array.from(imgs).slice(0,3).map(img => ({src: img.getAttribute('src'), dataSrc: img.getAttribute('data-src')}));
                }
              }
              return [];
            }
            """)
            print("imgs:", imgs)

        browser.close()


if __name__ == "__main__":
    main()
