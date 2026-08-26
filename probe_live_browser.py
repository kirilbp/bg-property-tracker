"""
Diagnostic: load the real, live imotenradar.com in a headless browser and
confirm the fetchAllRows() fix actually resolves the load - checks that
the grid/subtitle shows real data (not "Could not load listings data.")
and reports how long the full load took.
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

        # Poll for the subtitle to settle instead of waiting for
        # networkidle (which the old sequential loop never reached inside
        # a sane timeout) - up to 3 minutes, generous headroom over the
        # fix's expected ~15-25s.
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

        listing_count = page.evaluate("window.MERGED_LISTINGS ? window.MERGED_LISTINGS.length : 'MERGED_LISTINGS not global'")
        print(f"MERGED_LISTINGS length (if exposed): {listing_count}")

        print(f"\n=== console errors ({len(console_errors)}) ===")
        for e in console_errors:
            print(e)

        page.screenshot(path="live_site_screenshot.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
