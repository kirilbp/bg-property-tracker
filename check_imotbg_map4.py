from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag"

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
    page.wait_for_timeout(1000)

    print("\n=== mapgsparams form inputs (by name attribute) BEFORE trigger ===")
    inputs_before = page.evaluate("""
        () => {
            const form = document.forms['mapgsparams'];
            if (!form) return 'NO FORM NAMED mapgsparams FOUND';
            return Array.from(form.elements).map(el => ({name: el.name, value: el.value}));
        }
    """)
    print(inputs_before)

    print("\n=== calling AvrPricesShowGmap() ===")
    try:
        page.evaluate("() => AvrPricesShowGmap()")
        print("called successfully")
    except Exception as e:
        print(f"call failed: {e}")

    page.wait_for_timeout(3000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    print("\n=== mapgsparams form inputs AFTER trigger ===")
    inputs_after = page.evaluate("""
        () => {
            const form = document.forms['mapgsparams'];
            if (!form) return 'NO FORM NAMED mapgsparams FOUND';
            return Array.from(form.elements).map(el => ({name: el.name, value: el.value}));
        }
    """)
    print(inputs_after)

    print("\n=== #gmap div content after trigger ===")
    gmap_html = page.evaluate("""
        () => {
            const el = document.getElementById('gmap');
            return el ? el.outerHTML.slice(0, 2000) : 'NO #gmap ELEMENT';
        }
    """)
    print(gmap_html)

    print("\n=== iframes present after trigger ===")
    iframes = page.eval_on_selector_all("iframe", "els => els.map(e => e.src)")
    for src in iframes:
        print(" ", src[:300])

    browser.close()
