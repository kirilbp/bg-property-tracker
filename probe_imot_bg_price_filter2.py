"""
Diagnostic-only: round 4 for imot.bg nationwide. Round 3 found real price-
related form fields named srcena0..srcena6 (not a free-form price_from/to
param - our guesses didn't change result counts). This dumps the raw HTML
around those field names to see the actual form structure (select options,
values, submit method/action) so we can figure out how to actually submit
a price-band-scoped search as a URL.

Read-only, no commit step - deleted once the question is answered.
"""

import re

from playwright.sync_api import sync_playwright

BASE = "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()
    page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1200)
    html = page.content()

    print("=== forms on the page ===")
    for m in re.finditer(r"<form[^>]*>", html, re.IGNORECASE):
        print(m.group(0))

    print("\n=== context around each srcena field (300 chars before/after) ===")
    for name in ["srcena0", "srcena1", "srcena2", "srcena3", "srcena4", "srcena5", "srcena6"]:
        idx = html.find(f'name="{name}"')
        if idx == -1:
            idx = html.find(f"name='{name}'")
        if idx == -1:
            print(f"{name}: NOT FOUND")
            continue
        snippet = html[max(0, idx - 250):idx + 250]
        print(f"--- {name} ---")
        print(snippet)
        print()

    print("=== any <select> tags with 'cena' in surrounding 100 chars ===")
    for m in re.finditer(r"<select[^>]*>.*?</select>", html, re.IGNORECASE | re.DOTALL):
        block = m.group(0)
        if "cena" in block.lower() or "price" in block.lower():
            print(block[:1500])
            print("---")

    browser.close()

print("\ndone")
