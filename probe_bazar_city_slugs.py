"""
Diagnostic-only: round 3 for bazar.bg nationwide. Rounds 1-2 confirmed:
- Both a bare nationwide URL and per-city slugs work as real, distinct
  queries (plovdiv/varna/burgas already confirmed).
- Sofia's own pagination doesn't return an empty page past its real
  depth - it clamps to the last real page and repeats it verbatim (page
  30's listing ID set == page 50's, byte-identical) - real content stops
  changing around page 26. A different city query (Plovdiv) still gets
  fresh content in the same session after Sofia has already plateaued.

This verifies the real bazar.bg city-path-segment URL for every city in
the project's canonical BG_CITIES list (sync_to_supabase.py), same
"verify before trusting a guessed slug" discipline used for imoti.net/
imot.bg/olx.bg (all had real transliteration mismatches somewhere).

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests

BASE = "https://bazar.bg/obiavi/prodazhba-apartamenti"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}
LISTING_LINK_RE = re.compile(r"obiava-(\d+)")

# (city_key, guessed slug) - transliterated from sync_to_supabase.py's
# BG_CITIES, matching bazar.bg's own English-slug URL convention.
CITY_SLUGS = [
    ("sofia", "sofia"),
    ("plovdiv", "plovdiv"),
    ("varna", "varna"),
    ("burgas", "burgas"),
    ("ruse", "ruse"),
    ("stara_zagora", "stara-zagora"),
    ("pleven", "pleven"),
    ("sliven", "sliven"),
    ("dobrich", "dobrich"),
    ("shumen", "shumen"),
    ("pernik", "pernik"),
    ("haskovo", "haskovo"),
    ("yambol", "yambol"),
    ("pazardzhik", "pazardzhik"),
    ("blagoevgrad", "blagoevgrad"),
    ("veliko_tarnovo", "veliko-tarnovo"),
    ("vratsa", "vratsa"),
    ("gabrovo", "gabrovo"),
    ("vidin", "vidin"),
    ("asenovgrad", "asenovgrad"),
    ("kazanlak", "kazanlak"),
    ("kyustendil", "kyustendil"),
    ("kardzhali", "kardzhali"),
    ("montana", "montana"),
    ("dimitrovgrad", "dimitrovgrad"),
    ("targovishte", "targovishte"),
    ("lovech", "lovech"),
    ("silistra", "silistra"),
    ("dupnitsa", "dupnitsa"),
    ("svishtov", "svishtov"),
]


def check(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        n = len(set(LISTING_LINK_RE.findall(r.text)))
        return r.status_code, n, len(r.text)
    except Exception as e:
        return f"ERROR: {e}", 0, 0


ok, bad = [], []
for key, slug in CITY_SLUGS:
    url = f"{BASE}/{slug}"
    status, n, length = check(url)
    result = f"{key} ({slug}): status={status} listing_links={n} len={length}"
    print(f"  {result}")
    if status == 200 and n > 0:
        ok.append(key)
    else:
        bad.append(key)
    time.sleep(0.8)

print(f"\n=== summary: {len(ok)}/{len(CITY_SLUGS)} slugs resolved ===")
print(f"OK: {ok}")
print(f"BAD: {bad}")

print("\ndone")
