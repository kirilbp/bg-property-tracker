"""
Round 6: use a headless browser to actually interact with imoti.bg's search
form (select Sofia district, trigger search) and capture the resulting
network request(s), to find out whether there's a real underlying API we
could hit directly with plain requests.
"""

import json
from playwright.sync_api import sync_playwright


def main():
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="bg-BG",
        )
        page = context.new_page()

        def on_request(req):
            if req.resource_type in ("xhr", "fetch"):
                captured.append({"url": req.url, "method": req.method})

        page.on("request", on_request)

        page.goto("https://imoti.bg/продажби", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        try:
            page.select_option("#district_id_multi", "5e60b66a0cbea")
            print("selected district via #district_id_multi")
        except Exception as e:
            print("select_option failed:", e)

        # try to find and click a submit/search button
        for sel in ["button[type=submit]", "#frmSearch button", "input[type=submit]", ".btn-search", "#frmSearch"]:
            try:
                el = page.query_selector(sel)
                if el:
                    print("found candidate submit element:", sel)
            except Exception:
                pass

        try:
            page.eval_on_selector("#frmSearch", "f => f.submit()")
            print("submitted #frmSearch via JS")
        except Exception as e:
            print("form submit failed:", e)

        page.wait_for_timeout(3000)
        print("final URL after interaction:", page.url)

        html = page.content()
        print("html length after interaction:", len(html))
        sofia_count = html.lower().count("софия")
        print("софия mentions in final html:", sofia_count)

        browser.close()

    print("\ncaptured XHR/fetch requests:")
    for c in captured[:40]:
        print("  ", c["method"], c["url"])


if __name__ == "__main__":
    main()
