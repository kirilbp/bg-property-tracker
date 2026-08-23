import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://bazar.bg/obiava-55509986/dvustaen-apartament-63-m-kv"

COORD_URL_RE = re.compile(r"[!@]?(?:3d|4d|ll=|center=|q=|lat=)(-?\d{1,3}\.\d{3,8})[,!@]*(?:4d|lng=|,)(-?\d{1,3}\.\d{3,8})")

requests_seen = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
    page = context.new_page()

    def on_request(req):
        u = req.url
        if "google" in u.lower() and ("map" in u.lower() or "geocode" in u.lower() or "tile" in u.lower()):
            requests_seen.append(u)

    page.on("request", on_request)

    print(f"Navigating to {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    for _ in range(15):
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(400)
    page.wait_for_timeout(3000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    print(f"\ngoogle map-related network requests captured: {len(requests_seen)}")
    for u in requests_seen[:20]:
        print(" ", u[:250])

    print("\nsearching captured request URLs for coordinate patterns:")
    for u in requests_seen:
        m = COORD_URL_RE.search(u)
        if m:
            print(f"  MATCH: {m.group(1)}, {m.group(2)}  <- from {u[:150]}")

    html = page.content()
    print(f"\nrendered HTML length: {len(html)}")
    burgas_re = re.compile(r"(4[0-9]\.\d{4,8})\D{1,15}(2[0-9]\.\d{4,8})")
    matches = burgas_re.findall(html)
    print("coordinate-like pairs in rendered HTML:", matches[:10])

    print("\niframe src attributes:")
    iframes = page.eval_on_selector_all("iframe", "els => els.map(e => e.src)")
    for src in iframes:
        print(" ", src[:300])

    browser.close()
