import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://bazar.bg/obiava-55509986/dvustaen-apartament-63-m-kv"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
    page = context.new_page()

    all_requests = []
    page.on("request", lambda req: all_requests.append(req.url))

    print(f"Navigating to {URL}")
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    print("\n=== elements with 'map' in id or class ===")
    els = page.evaluate("""
        () => {
            const out = [];
            document.querySelectorAll('*').forEach(el => {
                const id = el.id || '';
                const cls = el.className && el.className.toString ? el.className.toString() : '';
                if (/map/i.test(id) || /map/i.test(cls)) {
                    out.push({tag: el.tagName, id, cls: cls.slice(0,80), display: getComputedStyle(el).display, w: el.offsetWidth, h: el.offsetHeight});
                }
            });
            return out.slice(0, 30);
        }
    """)
    for el in els:
        print(" ", el)

    if els:
        print("\nscrolling first map-related element into view and waiting 8s...")
        page.evaluate("""
            () => {
                const el = document.querySelector('[class*="map" i], [id*="map" i]');
                if (el) el.scrollIntoView({behavior: 'instant', block: 'center'});
            }
        """)
        page.wait_for_timeout(8000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

    print(f"\ntotal requests so far: {len(all_requests)}")
    google_reqs = [u for u in all_requests if "google" in u.lower()]
    print(f"google-domain requests: {len(google_reqs)}")
    for u in google_reqs[:15]:
        print(" ", u[:250])

    print("\n=== re-check map elements after scroll+wait ===")
    els2 = page.evaluate("""
        () => {
            const out = [];
            document.querySelectorAll('*').forEach(el => {
                const id = el.id || '';
                const cls = el.className && el.className.toString ? el.className.toString() : '';
                if (/map/i.test(id) || /map/i.test(cls)) {
                    out.push({tag: el.tagName, id, cls: cls.slice(0,80), display: getComputedStyle(el).display, w: el.offsetWidth, h: el.offsetHeight, innerHTMLLen: el.innerHTML.length});
                }
            });
            return out.slice(0, 30);
        }
    """)
    for el in els2:
        print(" ", el)

    print("\niframe src attributes after scroll+wait:")
    iframes = page.eval_on_selector_all("iframe", "els => els.map(e => e.src)")
    for src in iframes:
        print(" ", src[:300])

    browser.close()
