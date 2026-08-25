"""
Diagnostic-only, round 5: rounds 2-4 exhausted every guess-based approach
against the server-rendered homepage HTML - guessed URL path slugs (round
2), grepped page text/preloaded-state tree (round 3), and a type= query
param (round 4) all came back identical: nationwide Sofia-dropped
(?locationId=0 works, confirmed) but permanently apartment-only. The
homepage's own state.data only has one top-level key ("offers"), no
criteria/menu catalog of the other 5 property types anywhere in the
server-rendered payload.

This means the type selector is client-side-only: real users must click a
JS-rendered control that fires an XHR/fetch to some internal API with the
other "*Sell" business-object names, not a plain page navigation. This
round finds that API by reading the actual JS the browser executes:
  1. Extracts every <script src="..."> bundle URL referenced by the
     homepage.
  2. Fetches each bundle and searches it for two things a URL-guessing
     approach can never find: literal "XxxSell" business-object name
     strings (the other 5 categories' real names, however they're
     spelled/capitalized) and API path patterns (fetch/axios/XHR calls,
     "/api/..." or "/API/..." string literals).

Read-only, no commit step - deleted once the question is answered.
"""

import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE_URL = "https://www.homes.bg"


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


html = fetch(BASE_URL + "/")

print("=== <script src> bundle URLs on homepage ===")
scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
for s in scripts:
    print(" ", s)

SELL_RE = re.compile(r'"([A-Za-z]{3,20}Sell)"')
API_RE = re.compile(r'["\'](/[A-Za-z0-9_\-/]*[Aa][Pp][Ii][A-Za-z0-9_\-/]*)["\']')

for s in scripts:
    url = s if s.startswith("http") else (BASE_URL + s if s.startswith("/") else f"{BASE_URL}/{s}")
    try:
        js = fetch(url)
    except requests.RequestException as e:
        print(f"\n=== FAILED to fetch {url}: {e} ===")
        continue

    sell_matches = sorted(set(SELL_RE.findall(js)))
    api_matches = sorted(set(API_RE.findall(js)))
    if sell_matches or api_matches:
        print(f"\n=== {url} ({len(js)} bytes) ===")
        if sell_matches:
            print("  *Sell business names:", sell_matches)
        if api_matches:
            print("  API-ish path literals (first 30):", api_matches[:30])
