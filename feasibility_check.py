"""
Round 1: check whether imoti.info is reachable via headless Chromium
(Playwright) despite previously returning a Cloudflare "Just a moment..."
challenge page to plain requests - same approach that worked for imot.bg and
OLX.bg. Also try to find the Sofia apartments-for-sale search URL.
"""

from playwright.sync_api import sync_playwright

URL = "https://imoti.info"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BLOCK_MARKERS = ["just a moment", "checking your browser", "cf-browser-verification",
                  "cloudflare", "attention required", "captcha"]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        # Round 1 (6s wait) still showed the Cloudflare challenge page - give it
        # much longer in case this is a heavier "managed challenge" than the
        # simple JS challenge that resolved quickly for imot.bg/OLX.bg.
        page.wait_for_timeout(20000)
        print("navigator.webdriver:", page.evaluate("() => navigator.webdriver"))

        print("page url:", page.url)
        print("page title:", page.title())

        html = page.content()
        print("html length:", len(html))
        lower = html.lower()
        markers = [m for m in BLOCK_MARKERS if m in lower]
        print("block markers found:", markers)

        print("\n--- links mentioning 'sofia'/'sofiya'/'софия' or 'apartament' ---")
        links = page.eval_on_selector_all("a[href]", """
        els => els.map(a => ({href: a.getAttribute('href'), text: a.textContent.trim().slice(0,60)}))
        """)
        seen = set()
        count = 0
        for l in links:
            href = l["href"] or ""
            text = l["text"] or ""
            if any(k in (href + text).lower() for k in ["sofia", "sofiya", "софия", "apartament", "апартамент"]):
                key = href
                if key not in seen:
                    seen.add(key)
                    print(repr(href), "|", repr(text))
                    count += 1
            if count >= 30:
                break

        browser.close()


if __name__ == "__main__":
    main()
