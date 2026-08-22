import re
from playwright.sync_api import sync_playwright

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CANDIDATES = {
    "imot.bg": "https://www.imot.bg/obiavi/prodazhbi",
    "olx.bg": "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/",
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()
    for name, url in CANDIDATES.items():
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            html = page.content()
            print(f"=== {name} === {url}")
            print(f"len={len(html)}")
            for m in re.finditer(r'([\d\s,\.]{2,10})\s*(обяви|resultat|results|listings|imota|imoti|обявени)', html, re.IGNORECASE):
                print("  match:", m.group(0)[:60])
            for m in re.finditer(r'(намерихме|намерени|открихме|found)[^\d]{0,20}([\d\s,\.]{2,10})', html, re.IGNORECASE):
                print("  match2:", m.group(0)[:60])
        except Exception as e:
            print(f"=== {name} === FAILED: {e}")
        print()
    browser.close()
