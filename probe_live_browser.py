"""
Diagnostic: full end-to-end load of the real, live imotenradar.com,
confirming the listing_sources column-trimming fix actually resolves the
statement-timeout failure, not just another parameter tweak.
"""

import time

from playwright.sync_api import sync_playwright

URL = "https://imotenradar.com/"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        start = time.monotonic()
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)

        subtitle_text = None
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            subtitle_text = page.evaluate("document.getElementById('subtitle')?.textContent")
            if subtitle_text and "Loading" not in subtitle_text:
                break
            page.wait_for_timeout(1000)
        elapsed = time.monotonic() - start

        print(f"elapsed: {elapsed:.1f}s")
        print(f"subtitle text: {subtitle_text!r}")

        print(f"\n=== console errors ({len(console_errors)}) ===")
        for e in console_errors:
            print(e)

        browser.close()


if __name__ == "__main__":
    main()
