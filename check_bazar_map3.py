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

    all_requests = []
    page.on("request", lambda req: all_requests.append(req.url))

    print(f"Navigating to {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    for _ in range(15):
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(300)

    print("\n=== map_canvas innerHTML BEFORE click ===")
    before = page.evaluate("() => { const el = document.getElementById('map_canvas'); return el ? el.innerHTML : 'NOT FOUND'; }")
    print(repr(before))

    print("\n=== see_on_map href/onclick attributes ===")
    attrs = page.evaluate("""
        () => {
            const el = document.getElementById('see_on_map');
            if (!el) return 'NOT FOUND';
            return {href: el.getAttribute('href'), onclick: el.getAttribute('onclick'), outerHTML: el.outerHTML};
        }
    """)
    print(attrs)

    print("\n=== clicking #see_on_map ===")
    try:
        page.click("#see_on_map", timeout=5000)
        print("clicked")
    except Exception as e:
        print(f"click failed: {e}")

    page.wait_for_timeout(4000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    print("\n=== map_canvas innerHTML AFTER click (first 1500 chars) ===")
    after = page.evaluate("() => { const el = document.getElementById('map_canvas'); return el ? el.innerHTML : 'NOT FOUND'; }")
    print(after[:1500] if after else after)

    print("\n=== coordinate pattern search in map_canvas content ===")
    if after:
        m = COORD_RE.findall(after)
        print(m)

    print(f"\ngoogle-domain requests after click: {len([u for u in all_requests if 'google' in u.lower()])}")
    map_reqs = [u for u in all_requests if "google" in u.lower() and ("maps" in u.lower() or "tile" in u.lower() or "geocode" in u.lower())]
    print(f"maps-specific google requests: {len(map_reqs)}")
    for u in map_reqs[:10]:
        print(" ", u[:300])
        m = COORD_RE.search(u)
        if m:
            print(f"    COORD MATCH: {m.group(1)}, {m.group(2)}")

    browser.close()
