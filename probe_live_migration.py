"""
Diagnostic-only: final check before merging the Supabase-backed frontend to
main (and therefore to the live GitHub Pages site) - serves the real,
unmodified index.html locally on this runner and drives it with Playwright
against the REAL Supabase project (this runner has real network access,
unlike the sandbox this was developed in, which is blocked from reaching
Supabase entirely). Confirms the page actually loads real data end to end,
not just against locally-mocked responses. Read-only, no commit step -
deleted once the question is answered.
"""

import http.server
import socketserver
import threading
import time

from playwright.sync_api import sync_playwright

PORT = 8850


def serve():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        httpd.serve_forever()


def main():
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    time.sleep(1)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(f"http://localhost:{PORT}/index.html")
        page.wait_for_function("typeof MERGED_LISTINGS !== 'undefined' && MERGED_LISTINGS.length > 0", timeout=30000)
        page.wait_for_timeout(1500)

        print("page errors:", errors)
        print("console errors:", console_errors)
        print("MERGED_LISTINGS.length:", page.evaluate("MERGED_LISTINGS.length"))
        print("ALL_LISTINGS.length:", page.evaluate("ALL_LISTINGS.length"))
        print("subtitle:", page.evaluate("document.getElementById('subtitle').textContent"))

        page.evaluate("showSection('leads')")
        page.wait_for_timeout(500)
        print("grid card count:", page.evaluate("document.querySelectorAll('#grid .listing').length"))
        print("count text:", page.evaluate("document.getElementById('count').textContent"))

        detail_target = page.evaluate("""
          () => { const m = MERGED_LISTINGS.find(l => l.sources.length > 1); return m ? m.id : MERGED_LISTINGS[0].id; }
        """)
        page.evaluate("(id) => showListingDetail(id)", detail_target)
        page.wait_for_timeout(500)
        print("detail title:", page.evaluate("document.querySelector('.detail-title')?.textContent"))
        print("source switcher buttons:", page.evaluate("document.querySelectorAll('.source-switcher-btn').length"))

        page.screenshot(path="live_migration_home.png")
        page.evaluate("showSection('leads')")
        page.wait_for_timeout(500)
        page.screenshot(path="live_migration_leads.png")

        browser.close()

    if errors or console_errors:
        raise SystemExit("Page or console errors detected - see output above")


if __name__ == "__main__":
    main()
