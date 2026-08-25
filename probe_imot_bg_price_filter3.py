"""
Diagnostic-only: round 5 for imot.bg nationwide. Round 4 found the
srcena0..srcena6 fields are hidden, non-monotonic values (428156.85,
5673.44, 1001, 88012, 1652676, 371607, 5342.31) inside a POST form
(name="search", action="/pcgi/imot.cgi") - not a GET query-string filter,
and not sorted like price-band boundaries would be. They're probably
histogram/chart stats, not a usable filter.

This dumps the FULL <form name="search"> HTML (not just fields with
'cena'/'price' in the name) to find the real price-range input field
names, so we can check whether they're forms of a real GET-submittable
price filter (or determine none exists and fall back to a different
strategy for over-cap cities).

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

    m = re.search(r'<form name="search".*?</form>', html, re.IGNORECASE | re.DOTALL)
    if not m:
        print("search form not found")
    else:
        form_html = m.group(0)
        print(f"form length: {len(form_html)}")
        # Extract all input/select tags with their name+value/visible text
        inputs = re.findall(r'<input[^>]*>', form_html, re.IGNORECASE)
        print(f"\n=== {len(inputs)} <input> tags in search form ===")
        for inp in inputs:
            name_m = re.search(r'name="([^"]*)"', inp)
            type_m = re.search(r'type="([^"]*)"', inp)
            val_m = re.search(r'value="([^"]*)"', inp)
            name = name_m.group(1) if name_m else "?"
            typ = type_m.group(1) if type_m else "text"
            val = val_m.group(1) if val_m else ""
            if typ != "hidden":
                print(f"  VISIBLE name={name!r} type={typ!r} value={val!r}")

        print("\n=== all hidden input names (for reference) ===")
        hidden_names = [re.search(r'name="([^"]*)"', inp).group(1) for inp in inputs
                         if 'type="hidden"' in inp and re.search(r'name="([^"]*)"', inp)]
        print(hidden_names)

        selects = re.findall(r'<select[^>]*name="([^"]*)"[^>]*>', form_html, re.IGNORECASE)
        print(f"\n=== {len(selects)} <select> names in search form ===")
        print(selects)

        # Look specifically near the Bulgarian word for price (Цена) in the visible form
        idx = form_html.find("Цена")
        if idx != -1:
            print("\n=== HTML around visible 'Цена' label ===")
            print(form_html[max(0, idx - 400):idx + 800])

    browser.close()

print("\ndone")
