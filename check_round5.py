import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

COORD_RE = re.compile(r"(4[0-9]\.\d{4,8})\D{1,20}(2[0-9]\.\d{4,8})")

TARGETS = {
    "imot.bg (#map anchor)":
        "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag#map",
    "imoti.bg (premium listing)":
        "https://imoti.bg/продажби/тристаен-апартамент/софия/център-512778.htm/di:софия/cu:BGN",
}

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages', { get: () => ['bg-BG', 'bg', 'en-US', 'en'] });
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);
"""

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
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--enable-gpu-rasterization",
            "--disable-blink-features=AutomationControlled",
        ],
    )

    for portal, url in TARGETS.items():
        print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
        context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
        context.add_init_script(STEALTH_SCRIPT)
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

        webdriver_flag = page.evaluate("() => navigator.webdriver")
        print(f"  navigator.webdriver after stealth patch: {webdriver_flag}")

        page.wait_for_timeout(2000)
        accepted = try_accept_cookies(page)
        if not accepted:
            print("  no cookie banner found/accepted")
        page.wait_for_timeout(1500)

        for _ in range(20):
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(300)

        page.wait_for_timeout(5000)

        gmap_state = page.evaluate("""
            () => {
                const ids = ['gmap', 'map', 'map_canvas', 'mapCanvas', 'googleMap'];
                const out = {};
                for (const id of ids) {
                    const el = document.getElementById(id);
                    out[id] = el ? { childCount: el.children.length, html: el.innerHTML.slice(0, 300) } : null;
                }
                return out;
            }
        """)
        print("  map-container div states:", gmap_state)

        map_instances = page.evaluate("""
            () => {
                const found = [];
                for (const key of Object.keys(window)) {
                    try {
                        const val = window[key];
                        if (val && typeof val === 'object' && typeof val.getCenter === 'function') {
                            const c = val.getCenter();
                            if (c && typeof c.lat === 'function') {
                                found.push({key, lat: c.lat(), lng: c.lng()});
                            }
                        }
                    } catch (e) {}
                }
                return found;
            }
        """)
        print("  live google.maps.Map instances found on window:", map_instances)

        iframe_srcs = page.evaluate("() => Array.from(document.querySelectorAll('iframe')).map(f => f.src)")
        gmap_iframes = [s for s in iframe_srcs if "google" in s.lower() and "map" in s.lower()]
        print(f"  google-maps iframes: {gmap_iframes}")

        print(f"  captured {len(captured)} google map-related responses")
        for u, body in captured:
            print(f"    {u[:150]}")
            m = COORD_RE.findall(body)
            if m:
                print(f"    COORD MATCHES: {m[:5]}")

        context.close()

    browser.close()
