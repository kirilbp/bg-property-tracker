"""
Diagnostic-only: round 6 for imot.bg nationwide. Rounds 3-5 dead-ended on
a price filter: imot.bg's price UI is not a URL-toggleable filter at all
- the entire <form name="search"> is 82 inputs and EVERY one is
type="hidden" (no visible inputs/selects in the static HTML at all), and
POSTs to /pcgi/imot.cgi. The srcena0..srcena6 values aren't sorted
price-band boundaries either. Not worth reverse-engineering a client-JS-
driven POST form for a scraper.

This checks the other realistic sub-slicing option: does imot.bg support
a district/quarter (kvartal) URL segment under a city, the same way it
already supports a city segment (grad-sofiya)? Bulgarian portals often
use a 'kv-<name>' slug. If real, sofia sliced into ~20 districts would
each individually be well under the ~1,080-listing cap without needing
any price filter at all - the same pattern imoti.net already uses one
level up (city instead of district).

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

from playwright.sync_api import sync_playwright

BASE = "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/obiava-(\d[a-z]\d{10,})-")

DISTRICT_SLUGS = [
    "kv-lozenets", "kv-mladost-1", "kv-mladost-4", "kv-krasno-selo",
    "kv-liulin", "kv-nadejda", "kv-studentski-grad", "kv-iztok",
    "kv-strelbishte", "kv-vitosha",
]


def check(page, url):
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1200)
        html = page.content()
        n = len(set(LISTING_LINK_RE.findall(html)))
        status = resp.status if resp else "?"
        return status, n, len(html)
    except Exception as e:
        return f"ERROR: {e}", 0, 0


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()

    print("=== baseline: full Sofia, page 1 ===")
    status, n, length = check(page, BASE)
    print(f"  Sofia (no district): status={status} listing_links={n} len={length}")

    print("\n=== look for district/quarter links anywhere in the Sofia search page ===")
    html = page.content()
    kv_links = sorted(set(re.findall(r'href="([^"]*grad-sofiya/kv-[^"]*)"', html)))
    print(f"  kv- links found in page: {kv_links[:20]}")
    quartal_hint = sorted(set(re.findall(r'href="([^"]*kvartal[^"]*)"', html, re.IGNORECASE)))
    print(f"  'kvartal' links found: {quartal_hint[:20]}")

    print("\n=== try guessed district slugs directly ===")
    for slug in DISTRICT_SLUGS:
        url = f"{BASE}/{slug}"
        status, n, length = check(page, url)
        print(f"  {slug}: status={status} listing_links={n} len={length}")
        time.sleep(1)

    browser.close()

print("\ndone")
