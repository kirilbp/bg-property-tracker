"""
Round 8: fix the listing selector - round 7's `a[href*="/продажби/"]` matched
category/filter badge links (e.g. "tm:жилищни-имоти", "fi:3_68") as well as
real listings, undercounting genuine results. Real individual listing pages
have a numeric-id + .htm suffix (e.g. "...надежда-3-515750.htm", seen on the
homepage). Use that pattern specifically to get an accurate count and sample
real listing card content (title, area, price).
"""

import re
from playwright.sync_api import sync_playwright

URL = "https://imoti.bg"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

LISTING_HREF_RE = re.compile(r"-\d{5,}\.htm(?:$|[?#])")


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

        all_hrefs = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href]')).map(a => a.getAttribute('href'))
        """)
        real_listing_hrefs = sorted(set(h for h in all_hrefs if h and LISTING_HREF_RE.search(h)))
        print("real listing-detail hrefs (numeric id + .htm):", len(real_listing_hrefs))
        for h in real_listing_hrefs[:10]:
            print(" ", h)

        # For each real listing link, climb to its card and dump text.
        print("\n--- sample card contents ---")
        shown = 0
        for h in real_listing_hrefs[:15]:
            loc = page.locator(f'a[href="{h}"]').first
            try:
                card_text = loc.evaluate("""
                (el) => {
                  let node = el;
                  for (let i = 0; i < 6; i++) {
                    if (!node.parentElement) break;
                    node = node.parentElement;
                    const t = node.textContent.trim();
                    if (t.length > 30 && t.length < 400) return t;
                  }
                  return node.textContent.trim().slice(0, 400);
                }
                """)
            except Exception as e:
                card_text = f"(error: {e})"
            print("=" * 60)
            print("href:", h)
            print("card text:", repr(card_text[:300]))
            shown += 1

        print("\ntotal real listings:", len(real_listing_hrefs))

        # pagination
        page_links = page.evaluate("""
        () => Array.from(document.querySelectorAll('a')).filter(a => /page|стр/i.test(a.href) || /\\d+/.test(a.textContent.trim()) && a.textContent.trim().length < 4).map(a => a.textContent.trim() + '|' + a.href).slice(0, 20)
        """)
        print("\npossible pagination elements:", page_links)

        browser.close()


if __name__ == "__main__":
    main()
