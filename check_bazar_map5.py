import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://bazar.bg/obiava-55509986/dvustaen-apartament-63-m-kv"
COORD_RE = re.compile(r"(4[0-9]\.\d{4,8})\D{1,20}(2[0-9]\.\d{4,8})")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
    page = context.new_page()

    captured_bodies = []

    def on_response(resp):
        u = resp.url
        if "GetViewportInfo" in u or "StaticMapService" in u:
            try:
                body = resp.text()
                captured_bodies.append((u, body))
            except Exception as e:
                captured_bodies.append((u, f"<error reading body: {e}>"))

    page.on("response", on_response)

    print(f"Navigating to {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    for _ in range(15):
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(300)

    try:
        page.click("#see_on_map", timeout=5000)
        print("clicked #see_on_map")
    except Exception as e:
        print(f"click failed: {e}")

    page.wait_for_timeout(4000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    print(f"\ncaptured {len(captured_bodies)} relevant response bodies")
    for u, body in captured_bodies:
        print(f"\n--- {u[:150]} ---")
        print("body length:", len(body))
        print("body (first 800 chars):", body[:800])
        matches = COORD_RE.findall(body)
        if matches:
            print("COORDINATE MATCHES:", matches[:10])

    browser.close()
