"""
Diagnostic-only, round 3: round 1 found ?locationId=0 (nationwide, drops
city filter). Round 2 guessed candidate type-scoped URL slugs
(kashti/parceli/ofisi/...) - all failed, landing on some non-search page
(preloaded state present but data.offers empty), so homes.bg's real
type-selector is not a guessable URL path segment.

This round instead reads real signal off the live homepage:
  1. Full <a href="..."> nav links containing property-type words, not just
     ~80-char text context (round 2's proximity search may have anchored on
     the page <title>/meta tag, not real nav markup).
  2. The full window.__PRELOADED_STATE__ JSON tree, recursively, for any
     key/value that looks like a type id/slug/menu (offerTypeId, category,
     estateType, menu items, etc.) - the client-side app has to get its
     type list from *somewhere* in that state even if the homepage only
     renders apartments by default.

Read-only, no commit step - deleted once the question is answered.
"""

import json
import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.homes.bg"
STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


html = fetch(BASE_URL + "/")

print("=== full <a href> nav links mentioning property-type words ===")
TYPE_WORDS = ["апартамент", "къща", "парцел", "земеделск", "офис", "магазин", "гараж", "склад", "имот"]
seen = set()
for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE):
    href, text = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
    low = (href + " " + text).lower()
    if any(w in low for w in TYPE_WORDS):
        key = (href, text)
        if key not in seen:
            seen.add(key)
            print(f"  href={href!r} text={text!r}")

print("\n=== any <select>/<option> blocks (type dropdown) ===")
for m in re.finditer(r"<select\b[^>]*>.*?</select>", html, re.DOTALL | re.IGNORECASE):
    block = m.group(0)
    if any(w in block.lower() for w in TYPE_WORDS):
        print(" ", re.sub(r"\s+", " ", block)[:2000])

print("\n=== recursive scan of __PRELOADED_STATE__ for type/menu/category keys ===")
m = STATE_RE.search(html)
if m:
    state = json.loads(m.group(1))
    KEY_HINTS = re.compile(r"(type|categor|menu|estate|offertype|propert)", re.IGNORECASE)

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{path}.{k}" if path else k
                if KEY_HINTS.search(k):
                    if isinstance(v, (dict, list)):
                        s = json.dumps(v, ensure_ascii=False)
                        print(f"  {p} = {s[:500]}")
                    else:
                        print(f"  {p} = {v!r}")
                walk(v, p)
        elif isinstance(obj, list):
            for i, item in enumerate(obj[:20]):
                walk(item, f"{path}[{i}]")

    walk(state)
else:
    print("  no preloaded state found on homepage")

print("\n=== raw search for offerType-style numeric ids in full HTML ===")
for m in re.finditer(r'"(offerTypeId|estateTypeId|typeId|categoryId)"\s*:\s*"?(\d+)"?', html):
    print(" ", m.group(0))
