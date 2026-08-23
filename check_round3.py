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

CLASS_CLICK_TARGETS = {
    "imot.bg (retry)": ["a.mapbutton1", ".mapbutton1"],
    "imoti.bg (premium listing)": ["span.mdi-map-marker", ".icon-1.mdi-map-marker", "#locationsBox span"],
}


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

        print("  --- candidate element outerHTML dump ---")
        for sel in CLASS_CLICK_TARGETS.get(portal, []):
            try:
                html = page.eval_on_selector(sel, "el => el.outerHTML")
                print(f"    {sel} -> {html[:300]}")
            except Exception as e:
                print(f"    {sel} -> NOT FOUND ({e})")

        clicked_any = False
        for sel in CLASS_CLICK_TARGETS.get(portal, []):
            try:
                page.click(sel, timeout=3000)
                print(f"  clicked '{sel}'")
                clicked_any = True
                page.wait_for_timeout(2500)
            except Exception as e:
                print(f"  click '{sel}' failed: {e}")

        if not clicked_any:
            print("  WARNING: no class-based candidate was clickable")

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

        full_html = page.content()
        dom_matches = COORD_RE.findall(full_html)
        if dom_matches:
            print(f"  DOM-embedded coordinate-like matches (raw HTML scan): {dom_matches[:10]}")
        else:
            print("  no coordinate-like patterns found in raw page HTML")

        link_matches = page.evaluate("""
            () => {
                const out = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    if (/google\\.[a-z.]+\\/maps|maps\\?q=|q=\\d/.test(a.href)) {
                        out.push(a.href);
                    }
                });
                document.querySelectorAll('[onclick]').forEach(el => {
                    const oc = el.getAttribute('onclick');
                    if (oc && /\\d{2}\\.\\d{3,}/.test(oc)) out.push('onclick:' + oc.slice(0,200));
                });
                return out.slice(0, 15);
            }
        """)
        if link_matches:
            print("  candidate map links / onclick coords:", link_matches)

        context.close()

    browser.close()
