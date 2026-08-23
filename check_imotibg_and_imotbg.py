import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

COORD_RE = re.compile(r"(4[0-9]\.\d{4,8})\D{1,20}(2[0-9]\.\d{4,8})")

TARGETS = {
    "imoti.bg": "https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/di:софия/cu:BGN",
    "imot.bg": "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag",
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for portal, url in TARGETS.items():
        print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
        context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
        page = context.new_page()

        captured_bodies = []

        def on_response(resp, store=captured_bodies):
            u = resp.url
            if "GetViewportInfo" in u or "StaticMapService" in u or "geocode" in u.lower():
                try:
                    body = resp.text()
                    store.append((u, body))
                except Exception as e:
                    store.append((u, f"<error: {e}>"))

        page.on("response", on_response)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"NAVIGATION FAILED: {e}")
            context.close()
            continue

        page.wait_for_timeout(2000)
        for _ in range(15):
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(300)

        for text in ["Виж на картата", "виж на картата", "Покажи на картата", "Карта", "на картата"]:
            try:
                el = page.get_by_text(text, exact=False).first
                if el.count() > 0:
                    el.click(timeout=3000)
                    print(f"clicked element with text '{text}'")
                    break
            except Exception:
                continue

        page.wait_for_timeout(4000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        print(f"captured {len(captured_bodies)} relevant response bodies")
        for u, body in captured_bodies:
            print(f"  --- {u[:150]}")
            print("  body length:", len(body))
            matches = COORD_RE.findall(body) if isinstance(body, str) else []
            if matches:
                print("  COORDINATE MATCHES:", matches[:5])

        context.close()

    browser.close()
