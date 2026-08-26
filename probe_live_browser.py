"""
Diagnostic: load the real, live imotenradar.com in a headless browser
(same engine class as a real user's browser, unlike a plain Python
requests probe which never enforces CORS) and capture every console
message and failed network request. A CORS misconfiguration, stale CDN
cache, or JS exception would all be invisible to a raw HTTP probe but
would show up here exactly as it does for a real visitor.
"""

from playwright.sync_api import sync_playwright

URL = "https://imotenradar.com/"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_messages = []
        failed_requests = []

        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} -> {req.failure}"))
        page.on("response", lambda res: (
            print(f"RESPONSE {res.status} {res.url}")
            if "supabase.co" in res.url else None
        ))

        page.goto(URL, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)

        subtitle = page.evaluate("document.getElementById('subtitle')?.textContent") if page.query_selector("#subtitle") else None
        print(f"subtitle text: {subtitle!r}")

        print(f"\n=== console messages ({len(console_messages)}) ===")
        for m in console_messages:
            print(m)

        print(f"\n=== failed requests ({len(failed_requests)}) ===")
        for f in failed_requests:
            print(f)

        page.screenshot(path="live_site_screenshot.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
