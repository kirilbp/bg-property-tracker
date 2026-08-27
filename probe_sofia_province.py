"""
One-shot live-browser check: does "Sofia Province" now show a non-zero
count in Browse by Council after the geo-based oblast_key sync? (Previously
stuck at 0 forever - text matching can't distinguish it from Sofia-grad,
only the new point-in-polygon lookup can.)
"""
from playwright.sync_api import sync_playwright

URL = "https://imotenradar.com/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#oblastTabRow .city-tab-btn", timeout=60000)
    page.wait_for_timeout(1500)

    oblast_btns = page.query_selector_all("#oblastTabRow .city-tab-btn")
    print(f"oblast tab buttons: {len(oblast_btns)}")
    for b in oblast_btns:
        key = b.get_attribute("data-oblast-filter")
        text = b.inner_text().replace("\n", " ")
        if key in ("sofia", "sofia_grad", "others"):
            print(f"  {key} -> {text}")

    print("console errors:", len(console_errors))
    browser.close()
