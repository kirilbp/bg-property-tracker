"""
One-shot live-browser verification for the new "Others" city bucket +
"Browse by Council" oblast section (see index.html's BG_OBLASTS/
listingOblastKey and the cityTabRow/oblastTabRow UI). Confirms the real
production site actually renders and filters correctly post-sync, not just
that the sync script logged success - same discipline used throughout this
project (CORS/DB-timeout failures are only ever visible to a real browser).
"""
import json
from playwright.sync_api import sync_playwright

URL = "https://imotenradar.com/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    print("Loading", URL)
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#cityTabRow .city-tab-btn", timeout=60000)
    page.wait_for_selector("#oblastTabRow .city-tab-btn", timeout=60000)
    page.wait_for_timeout(1000)

    city_btns = page.query_selector_all("#cityTabRow .city-tab-btn")
    oblast_btns = page.query_selector_all("#oblastTabRow .city-tab-btn")
    print(f"city tab buttons: {len(city_btns)} (expect 31 = 30 cities + Others)")
    print(f"oblast tab buttons: {len(oblast_btns)} (expect 29 = 28 oblasts + Others)")

    def btn_info(btn):
        return btn.inner_text().replace("\n", " | ")

    print("\n--- city tabs (last 3, should end with Others) ---")
    for b in city_btns[-3:]:
        print(" ", btn_info(b))

    print("\n--- oblast tabs (all 29) ---")
    oblast_data = []
    for b in oblast_btns:
        key = b.get_attribute("data-oblast-filter")
        text = btn_info(b)
        oblast_data.append((key, text))
        print(" ", key, "->", text)

    total_oblast_count = 0
    for key, text in oblast_data:
        num = text.split("|")[-1].strip().replace(",", "")
        total_oblast_count += int(num) if num.isdigit() else 0
    print("\nsum of all oblast bucket counts:", total_oblast_count)

    # Click "Others" in Browse by Council and confirm it filters correctly.
    others_oblast_btn = page.query_selector('#oblastTabRow .city-tab-btn[data-oblast-filter="others"]')
    others_oblast_btn.click()
    page.wait_for_timeout(1500)
    banner = page.query_selector("#oblastFilterBanner")
    banner_text = banner.inner_text() if banner and banner.is_visible() else None
    print("\nAfter clicking oblast 'Others': banner =", repr(banner_text))
    result_cards = page.query_selector_all(".listing-card, .lead-card")
    print("listing cards rendered after filter:", len(result_cards))

    # Click a real oblast (sofia_grad) and confirm it also works + clears the "others" state.
    page.go_back()
    page.wait_for_timeout(1000)
    sofia_grad_btn = page.query_selector('#oblastTabRow .city-tab-btn[data-oblast-filter="sofia_grad"]')
    if sofia_grad_btn:
        sofia_grad_btn.click()
        page.wait_for_timeout(1500)
        banner2 = page.query_selector("#oblastFilterBanner")
        print("After clicking Sofia-grad oblast: banner =", repr(banner2.inner_text() if banner2 and banner2.is_visible() else None))

    print("\nconsole errors:", len(console_errors))
    for e in console_errors[:10]:
        print(" ", e)

    browser.close()
