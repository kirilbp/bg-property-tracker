import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

COORD_RE = re.compile(r"(4[0-9]\.\d{4,8})\D{1,20}(2[0-9]\.\d{4,8})")

TARGETS = {
    "imot.bg (#map anchor, matches user's screenshot)":
        "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag#map",
    "imoti.bg (premium listing)":
        "https://imoti.bg/продажби/тристаен-апартамент/софия/център-512778.htm/di:софия/cu:BGN",
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
    return False


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for portal, url in TARGETS.items():
        print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
        context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
        page = context.new_page()

        captured = []

        def on_response(resp, store=captured):
            try:
                ct = resp.headers.get("content-type", "")
            except Exception:
                ct = ""
            u = resp.url
            is_google = "google" in u.lower() and ("map" in u.lower() or "geocode" in u.lower() or "viewport" in u.lower() or "tile" in u.lower())
            is_jsonish = ("json" in ct or "javascript" in ct) and resp.status == 200
            if is_google or is_jsonish:
                try:
                    body = resp.text()
                except Exception:
                    body = ""
                if is_google or COORD_RE.search(body):
                    store.append((u, body))

        page.on("response", on_response)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"NAVIGATION FAILED: {e}")
            context.close()
            continue

        page.wait_for_timeout(2000)
        accepted = try_accept_cookies(page)
        if not accepted:
            print("  no cookie banner found/accepted")
        page.wait_for_timeout(1500)

        for _ in range(20):
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(300)

        page.wait_for_timeout(3000)

        iframe_srcs = page.evaluate("() => Array.from(document.querySelectorAll('iframe')).map(f => f.src)")
        print(f"  iframes found: {len(iframe_srcs)}")
        for src in iframe_srcs:
            print(f"    iframe src: {src[:250]}")
            m = COORD_RE.search(src)
            if m:
                print(f"    COORD MATCH IN IFRAME SRC: {m.group(1)}, {m.group(2)}")

        img_srcs = page.evaluate("""
            () => Array.from(document.querySelectorAll('img'))
                .map(i => i.src)
                .filter(s => /map|staticmap|googleapis/i.test(s))
        """)
        print(f"  map-related <img> srcs found: {len(img_srcs)}")
        for src in img_srcs:
            print(f"    img src: {src[:250]}")
            m = COORD_RE.search(src)
            if m:
                print(f"    COORD MATCH IN IMG SRC: {m.group(1)}, {m.group(2)}")

        map_candidates = page.evaluate("""
            () => {
                const els = document.querySelectorAll('[class*="map" i], [id*="map" i]');
                return Array.from(els).slice(0, 15).map(el => ({
                    tag: el.tagName, id: el.id,
                    cls: (el.className && el.className.toString) ? el.className.toString() : String(el.className),
                    outer: el.outerHTML.slice(0, 200)
                }));
            }
        """)
        print(f"  case-insensitive map-class/id elements found: {len(map_candidates)}")
        for c in map_candidates:
            print("   ", c)

        click_result = page.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll('[class*="map" i], [id*="map" i]'));
                let clicked = 0;
                for (const el of els.slice(0, 8)) {
                    try { el.click(); clicked++; } catch (e) {}
                }
                return clicked;
            }
        """)
        print(f"  JS-native .click() invoked on {click_result} candidate elements")

        page.wait_for_timeout(4000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        iframe_srcs_after = page.evaluate("() => Array.from(document.querySelectorAll('iframe')).map(f => f.src)")
        new_iframes = [s for s in iframe_srcs_after if s not in iframe_srcs]
        if new_iframes:
            print(f"  NEW iframes appeared after click: {new_iframes}")
            for src in new_iframes:
                m = COORD_RE.search(src)
                if m:
                    print(f"    COORD MATCH IN NEW IFRAME SRC: {m.group(1)}, {m.group(2)}")

        print(f"  captured {len(captured)} relevant network responses")
        for u, body in captured:
            print(f"    {u[:150]}")
            m = COORD_RE.findall(body)
            if m:
                print(f"    COORD MATCHES: {m[:5]}")

        context.close()

    browser.close()
