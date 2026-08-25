"""
Diagnostic-only: round 7 (final) for imot.bg nationwide. Rounds 3-6
confirmed there's no usable price or district URL filter (the search form
is 82 hidden POST fields, no visible price inputs; no kv-/kvartal URL
segment exists) - so unlike homes.bg, over-cap cities can't be sub-sliced
further. City-only slicing (matching imoti.net's proven pattern) is the
only real option; only Sofia is confirmed to exceed the ~1,080-listing
per-query cap (the site's own UI already states 1000+ Sofia listings) -
every other city is expected to fit under it.

This verifies the real grad-<slug> URL for every city in the project's
canonical BG_CITIES list (sync_to_supabase.py) against imot.bg directly -
same "verify before trusting a guessed slug" discipline used for
imoti.net (which had real spelling mismatches, e.g. 'Bourgas' not
'burgas' - though imot.bg is Cyrillic-first, so transliteration might
differ from imoti.net's English-first spelling).

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

from playwright.sync_api import sync_playwright

BASE = "https://www.imot.bg/obiavi/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/obiava-(\d[a-z]\d{10,})-")

# (city_key, guessed slug) - transliterated from sync_to_supabase.py's BG_CITIES
CITY_SLUGS = [
    ("plovdiv", "grad-plovdiv"),
    ("varna", "grad-varna"),
    ("burgas", "grad-burgas"),
    ("ruse", "grad-ruse"),
    ("stara_zagora", "grad-stara-zagora"),
    ("pleven", "grad-pleven"),
    ("sliven", "grad-sliven"),
    ("dobrich", "grad-dobrich"),
    ("shumen", "grad-shumen"),
    ("pernik", "grad-pernik"),
    ("haskovo", "grad-haskovo"),
    ("yambol", "grad-yambol"),
    ("pazardzhik", "grad-pazardjik"),
    ("blagoevgrad", "grad-blagoevgrad"),
    ("veliko_tarnovo", "grad-veliko-tarnovo"),
    ("vratsa", "grad-vratsa"),
    ("gabrovo", "grad-gabrovo"),
    ("vidin", "grad-vidin"),
    ("asenovgrad", "grad-asenovgrad"),
    ("kazanlak", "grad-kazanlak"),
    ("kyustendil", "grad-kyustendil"),
    ("kardzhali", "grad-kardjali"),
    ("montana", "grad-montana"),
    ("dimitrovgrad", "grad-dimitrovgrad"),
    ("targovishte", "grad-targovishte"),
    ("lovech", "grad-lovech"),
    ("silistra", "grad-silistra"),
    ("dupnitsa", "grad-dupnitsa"),
    ("svishtov", "grad-svishtov"),
]


def check(page, url):
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
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
    for key, slug in CITY_SLUGS:
        url = f"{BASE}/{slug}"
        status, n, length = check(page, url)
        result = f"{key} ({slug}): status={status} listing_links={n} len={length}"
        print(f"  {result}")
        if status == 200 and n > 0:
            ok.append(key)
        else:
            bad.append(key)
        time.sleep(0.8)

    print(f"\n=== summary: {len(ok)}/{len(CITY_SLUGS)} slugs resolved ===")
    print(f"OK: {ok}")
    print(f"BAD (need a different slug or don't have their own imot.bg page): {bad}")

    browser.close()

print("\ndone")
