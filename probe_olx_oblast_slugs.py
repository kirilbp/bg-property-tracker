"""
Diagnostic-only: round 3 for olx.bg nationwide. Round 2 confirmed the bare
nationwide URL (dropping the region segment) hits the SAME real depth cap
as any single oblast (~page 26-27, ~1,000-1,400 listings) - so it can't
carry full national coverage alone. Per-oblast slicing (oblast-plovdiv,
oblast-varna already confirmed live) is the real mechanism needed, same
pattern as imot.bg's per-city slicing.

This verifies the real oblast-<slug> URL for all 28 Bulgarian oblasts
(administrative provinces - Sofia-grad/Sofia-city and Sofia oblast/
Sofia-province are two separate ones) against olx.bg directly, same
"verify before trusting a guessed slug" discipline used for imoti.net/
imot.bg (both had real transliteration mismatches).

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

from playwright.sync_api import sync_playwright

BASE = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/d/ad/[^\"'#]*-ID(\w+)\.html")

# (oblast key, guessed slug) - transliterated from the 28 Bulgarian
# administrative oblasts. sofiya-grad and sofiya (oblast) are separate.
OBLAST_SLUGS = [
    ("sofia_grad", "oblast-sofiya-grad"),
    ("sofia_oblast", "oblast-sofiya"),
    ("plovdiv", "oblast-plovdiv"),
    ("varna", "oblast-varna"),
    ("burgas", "oblast-burgas"),
    ("ruse", "oblast-ruse"),
    ("stara_zagora", "oblast-stara-zagora"),
    ("pleven", "oblast-pleven"),
    ("sliven", "oblast-sliven"),
    ("dobrich", "oblast-dobrich"),
    ("shumen", "oblast-shumen"),
    ("pernik", "oblast-pernik"),
    ("haskovo", "oblast-haskovo"),
    ("yambol", "oblast-yambol"),
    ("pazardzhik", "oblast-pazardzhik"),
    ("blagoevgrad", "oblast-blagoevgrad"),
    ("veliko_tarnovo", "oblast-veliko-tarnovo"),
    ("vratsa", "oblast-vratsa"),
    ("gabrovo", "oblast-gabrovo"),
    ("vidin", "oblast-vidin"),
    ("kyustendil", "oblast-kyustendil"),
    ("kardzhali", "oblast-kardzhali"),
    ("montana", "oblast-montana"),
    ("targovishte", "oblast-targovishte"),
    ("lovech", "oblast-lovech"),
    ("silistra", "oblast-silistra"),
    ("razgrad", "oblast-razgrad"),
    ("smolyan", "oblast-smolyan"),
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

    ok, bad = [], []
    for key, slug in OBLAST_SLUGS:
        url = f"{BASE}/{slug}/"
        status, n, length = check(page, url)
        result = f"{key} ({slug}): status={status} listing_links={n} len={length}"
        print(f"  {result}")
        if status == 200 and n > 0:
            ok.append(key)
        else:
            bad.append(key)
        time.sleep(0.8)

    print(f"\n=== summary: {len(ok)}/{len(OBLAST_SLUGS)} slugs resolved ===")
    print(f"OK: {ok}")
    print(f"BAD: {bad}")

    browser.close()

print("\ndone")
