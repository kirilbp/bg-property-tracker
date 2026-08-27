"""
The Sofia Province live-check timed out waiting for #oblastTabRow to
render (60s) - investigating whether this is a real regression (the
dataset just grew from 114,129 to 174,909 merged_listings, close to the
same territory as the original "Could not load listings data." bug this
session already fixed once) or just needs a longer timeout at the new
scale. Captures everything: full console log, page errors, network
failures, visible error text, and total load time.
"""
import time
from playwright.sync_api import sync_playwright

URL = "https://imotenradar.com/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    console_msgs = []
    page.on("console", lambda msg: console_msgs.append((msg.type, msg.text)))
    page.on("pageerror", lambda exc: console_msgs.append(("pageerror", str(exc))))

    failed_requests = []
    page.on("requestfailed", lambda req: failed_requests.append((req.url, req.failure)))

    t0 = time.time()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    print(f"domcontentloaded at {time.time()-t0:.1f}s")

    try:
        page.wait_for_selector("#oblastTabRow .city-tab-btn", timeout=120000)
        print(f"oblastTabRow populated at {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"TIMED OUT waiting for oblastTabRow after {time.time()-t0:.1f}s: {e}")

    body_text = page.inner_text("body")
    if "Could not load" in body_text or "error" in body_text.lower()[:2000]:
        print("--- possible visible error text on page ---")
        idx = body_text.lower().find("could not load")
        if idx == -1:
            idx = body_text.lower().find("error")
        print(body_text[max(0, idx - 100):idx + 300])

    print(f"\ntotal console messages: {len(console_msgs)}")
    for typ, text in console_msgs[:40]:
        print(f"  [{typ}] {text[:300]}")

    print(f"\nfailed network requests: {len(failed_requests)}")
    for url, failure in failed_requests[:20]:
        print(f"  {url} -> {failure}")

    oblast_btns = page.query_selector_all("#oblastTabRow .city-tab-btn")
    city_btns = page.query_selector_all("#cityTabRow .city-tab-btn")
    print(f"\nfinal state: oblastTabRow buttons={len(oblast_btns)} cityTabRow buttons={len(city_btns)}")

    browser.close()
