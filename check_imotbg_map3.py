from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag#map"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="bg-BG")
    page = context.new_page()

    print(f"Navigating to {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    for _ in range(20):
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(400)
    page.wait_for_timeout(3000)

    for fn_name in ["AvrPricesShowGmap", "fmapset", "mapgfnew"]:
        src = page.evaluate(f"() => typeof {fn_name} === 'function' ? {fn_name}.toString() : null")
        print(f"\n=== {fn_name} source ===")
        print(src)

    print("\n=== hidden inputs / elements with lat/lng/gmap in id or class ===")
    els = page.evaluate("""
        () => {
            const out = [];
            document.querySelectorAll('*').forEach(el => {
                const id = el.id || '';
                const cls = el.className && el.className.toString ? el.className.toString() : '';
                if (/lat|lng|gmap|coord/i.test(id) || /lat|lng|gmap|coord/i.test(cls)) {
                    out.push({tag: el.tagName, id, cls, value: el.value || null, dataset: JSON.stringify(el.dataset)});
                }
            });
            return out.slice(0, 20);
        }
    """)
    for el in els:
        print(" ", el)

    browser.close()
