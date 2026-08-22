"""
Round 1: check whether Obqvi.bg is reachable via headless Chromium
(Playwright), and specifically whether it gates access with an actual
interactive CAPTCHA (reCAPTCHA/hCaptcha/Turnstile widget, "I'm not a robot"
checkbox, image-selection challenge) on top of Cloudflare, as opposed to a
plain JS timer/fingerprint challenge like imoti.info and holmes.bg had.

This script is detection-only: it never attempts to click, solve, or
otherwise interact with any CAPTCHA it finds.
"""

from playwright.sync_api import sync_playwright

URL = "https://obqvi.bg"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CF_MARKERS = ["just a moment", "checking your browser", "cf-browser-verification",
              "cloudflare", "attention required"]
CAPTCHA_MARKERS = ["captcha", "hcaptcha", "recaptcha", "turnstile", "i'm not a robot",
                    "не съм робот", "потвърдете, че сте човек"]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)

        print("navigator.webdriver:", page.evaluate("() => navigator.webdriver"))
        print("page url:", page.url)
        print("page title:", page.title())

        html = page.content()
        print("html length:", len(html))
        lower = html.lower()
        cf_markers = [m for m in CF_MARKERS if m in lower]
        captcha_text_markers = [m for m in CAPTCHA_MARKERS if m in lower]
        print("cloudflare markers found:", cf_markers)
        print("captcha text markers found:", captcha_text_markers)

        # Look for actual captcha widget elements (iframes/divs), not just text.
        captcha_selectors = [
            "iframe[src*='recaptcha']", "iframe[src*='hcaptcha']",
            "iframe[src*='turnstile']", "iframe[title*='captcha' i]",
            "div.g-recaptcha", "div.h-captcha", "div.cf-turnstile",
            "input[type='checkbox'][id*='captcha' i]",
        ]
        found_widgets = []
        for sel in captcha_selectors:
            count = page.locator(sel).count()
            if count > 0:
                found_widgets.append((sel, count))
        print("captcha widget elements found:", found_widgets)

        if cf_markers:
            page.wait_for_timeout(20000)
            html2 = page.content()
            lower2 = html2.lower()
            print("page title (after +20s):", page.title())
            print("cloudflare markers found (after 28s total):", [m for m in CF_MARKERS if m in lower2])
            found_widgets2 = []
            for sel in captcha_selectors:
                count = page.locator(sel).count()
                if count > 0:
                    found_widgets2.append((sel, count))
            print("captcha widget elements found (after 28s total):", found_widgets2)

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
