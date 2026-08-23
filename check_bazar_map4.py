from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://bazar.bg/obiava-55509986/dvustaen-apartament-63-m-kv"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
    page = context.new_page()

    print(f"Navigating to {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    for _ in range(15):
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(300)

    try:
        page.click("#see_on_map", timeout=5000)
        print("clicked #see_on_map")
    except Exception as e:
        print(f"click failed: {e}")

    page.wait_for_timeout(4000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    print("\n=== searching window globals for a Google Maps Map instance (duck-typed via getCenter) ===")
    result = page.evaluate("""
        () => {
            const found = [];
            for (const key of Object.keys(window)) {
                try {
                    const val = window[key];
                    if (val && typeof val === 'object' && typeof val.getCenter === 'function') {
                        const c = val.getCenter();
                        if (c && typeof c.lat === 'function') {
                            found.push({key, lat: c.lat(), lng: c.lng(), zoom: val.getZoom ? val.getZoom() : null});
                        }
                    }
                } catch (e) {}
            }
            return found;
        }
    """)
    print("direct window-level map instances found:", result)

    print("\n=== also checking any object with __gm (google maps internal marker) via DOM data ===")
    gm_check = page.evaluate("""
        () => {
            const canvas = document.getElementById('map_canvas');
            if (!canvas) return 'no map_canvas';
            const keys = Object.keys(canvas).filter(k => k.startsWith('__') || k.includes('google'));
            return {keys, hasJQueryData: typeof window.jQuery !== 'undefined' && window.jQuery(canvas).data ? window.jQuery(canvas).data() : null};
        }
    """)
    print(gm_check)

    browser.close()
