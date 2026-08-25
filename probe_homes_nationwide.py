"""
Diagnostic-only, round 6: round 5 found real business-object names inside
the client JS bundle (static/js/client.09e890f5.js) - "ApartmentSell" AND
"HouseSell" - confirming the type selector works through internal names
like this, not a URL slug/query-param guess. The regex there only matched
quoted 3-20 char "XxxSell" literals though, so it likely missed the other
4 categories (case variants, different quoting, or longer names like
"CommercialSell"/"WarehouseSell").

This round:
  1. Re-fetches the same bundle and does a loose, unquoted, case-insensitive
     search for "Sell" anywhere, printing ~120 chars of context around each
     hit - to catch every business name the strict round-5 regex missed,
     and see how each one is actually used (route table, URL builder,
     dropdown option list, numeric-id map, etc.).
  2. Same loose treatment for the second bundle (320.0014221a.js), which
     round 5 skipped entirely (zero strict matches) - it may still contain
     a route/vendor table with the full category list even if it doesn't
     construct URLs directly.

Read-only, no commit step - deleted once the question is answered.
"""

import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.homes.bg"
BUNDLES = [
    "https://www.homes.bg/static/js/320.0014221a.js",
    "https://www.homes.bg/static/js/client.09e890f5.js",
]


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


LOOSE_SELL_RE = re.compile(r"[A-Za-z]{2,25}Sell", re.IGNORECASE)

for url in BUNDLES:
    js = fetch(url)
    print(f"\n=== {url} ({len(js)} bytes) - loose 'Sell' context scan ===")
    seen_texts = set()
    for m in LOOSE_SELL_RE.finditer(js):
        text = m.group(0)
        if text in seen_texts:
            continue
        seen_texts.add(text)
        start = max(0, m.start() - 60)
        end = min(len(js), m.end() + 60)
        snippet = js[start:end].replace("\n", " ")
        print(f"  [{text}] ...{snippet}...")

    # Also: how is "HouseSell" (confirmed real) actually referenced? Print
    # every occurrence with wider context to see the calling pattern.
    print(f"\n=== all 'HouseSell' occurrences with wide context ===")
    for m in re.finditer("HouseSell", js):
        start = max(0, m.start() - 150)
        end = min(len(js), m.end() + 150)
        print(f"  ...{js[start:end]}...")
