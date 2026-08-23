import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

COORD_RE = re.compile(r"(4[0-9]\.\d{4,8})\D{1,20}(2[0-9]\.\d{4,8})")

TARGETS = {
    "imoti.bg (premium listing)": "https://imoti.bg/продажби/тристаен-апартамент/софия/център-512778.htm/di:софия/cu:BGN",
    "imot.bg (retry)": "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag",
}

COOKIE_BUTTON_TEXTS = [
    "Приемам", "Съгласен съм", "Accept all", "Accept", "Разбрах", "ОК", "Ок",
    "Приемане", "Съгласявам се", "Allow all", "I agree",
]


def try_accept_cookies(page):
    for text in COOKIE_BUTTON_TEXTS:
        try:
            btn = page.get_by_text(text, exact=False).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=2000)
                print(f"  accepted cookies via button text '{text}'")
                return True
        except Exception:
            continue
    try:
        for frame in page.frames:
            if "consent" in frame.url.lower() or "privacy" in frame.url.lower() or "cmp" in frame.url.lower():
                for text in COOKIE_BUTTON_TEXTS:
                    try:
                        btn = frame.get_by_text(text, exact=False).first
                        if btn.count() > 0:
                            btn.click(timeout=2000)
                            print(f"  accepted cookies via iframe button text '{text}'")
                            return True
                    except Exception:
                        continue
    except Exception:
        pass
    return False


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for portal, url in TARGETS.items():
        print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
        context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
        page = context.new_page()

        captured = []

        def on_response(resp, store=captured):
            u = resp.url
            if "google" in u.lower() and ("map" in u.lower() or "geocode" in u.lower() or "viewport" in u.lower() or "tile" in u.lower()):
                try:
                    body = resp.text()
                except Exception:
                    body = ""
                store.append((u, body))

        page.on("response", on_response)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"NAVIGATION FAILED: {e}")
            context.close()
            continue

        page.wait_for_timeout(2000)
        print("  attempting to accept cookie consent...")
        accepted = try_accept_cookies(page)
        if not accepted:
            print("  no cookie banner found/accepted")
        page.wait_for_timeout(1500)

        for _ in range(20):
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(300)

        map_els = page.evaluate("""
            () => {
                const out = [];
                document.querySelectorAll('a, button, div, span').forEach(el => {
                    const id = (el.id || '').toLowerCase();
                    const cls = (el.className && el.className.toString ? el.className.toString() : '').toLowerCase();
                    const txt = (el.textContent || '').trim().toLowerCase();
                    if (/map|location|adres|geo|karta/.test(id) || /map|location|adres|geo|karta/.test(cls)) {
                        out.push({tag: el.tagName, id: el.id, cls: cls.slice(0,60), txt: txt.slice(0,40)});
                    }
                });
                return out.slice(0, 20);
            }
        """)
        print(f"  map-related elements found: {len(map_els)}")
        for el in map_els[:15]:
            print("   ", el)

        for el in map_els[:5]:
            selector = f"#{el['id']}" if el['id'] else None
            if selector:
                try:
                    page.click(selector, timeout=2000)
                    print(f"  clicked {selector}")
                except Exception:
                    pass

        page.wait_for_timeout(4000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        print(f"  captured {len(captured)} google map-related responses")
        for u, body in captured:
            print(f"    {u[:150]}")
            m = COORD_RE.findall(body)
            if m:
                print(f"    COORD MATCHES: {m[:5]}")

        context.close()

    browser.close()
