import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag#map"

COORD_RE = re.compile(r"(4[0-9]\.\d{4,8})\D{1,15}(2[0-9]\.\d{4,8})")

all_requests = []
xhr_bodies = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="bg-BG")
    page = context.new_page()

    def on_request(req):
        all_requests.append(req.url)

    def on_response(resp):
        try:
            ct = resp.headers.get("content-type", "")
            if "json" in ct or "javascript" in ct:
                body = resp.text()
                if COORD_RE.search(body):
                    xhr_bodies.append((resp.url, COORD_RE.findall(body)[:3]))
        except Exception:
            pass

    page.on("request", on_request)
    page.on("response", on_response)

    print(f"Navigating to {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    for _ in range(20):
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(400)
    page.wait_for_timeout(4000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    print(f"\ntotal requests captured: {len(all_requests)}")
    print("responses whose body contains a Bulgaria-range coordinate pair:")
    for url, coords in xhr_bodies:
        print(f"  {url[:150]} -> {coords}")

    print("\nchecking common JS globals for map/coord data:")
    globals_check = page.evaluate("""
        () => {
            const out = {};
            for (const key of Object.keys(window)) {
                if (/lat|lng|coord|geo|map/i.test(key)) {
                    try { out[key] = JSON.stringify(window[key]).slice(0, 200); } catch(e) { out[key] = '<unserializable>'; }
                }
            }
            return out;
        }
    """)
    print(" ", globals_check)

    print("\nfull visible page text search for coordinate-like numbers near 'Местоположение' or 'Карта':")
    body_text = page.inner_text("body")
    idx = body_text.find("Местоположение")
    if idx >= 0:
        print(" context:", body_text[idx:idx+300].replace("\n", " | "))

    browser.close()
