"""
Diagnostic-only follow-up to probe_price_badges.py: that probe found a
"notification-popup-price-old" / "notification-popup-price-new" widget in
imot.bg's listing-page HTML, fed from a JS variable called `payload` with
`payload.data.old_price` / `payload.data.new_price` - a real, portal-native
price-change signal, unlike anything found so far this session. But the
80-char context window in that probe only showed the innerHTML-assignment
line, not where `payload` itself comes from (an inline JSON blob already
on the page? an AJAX call to some endpoint we could query directly for any
listing? something gated behind a login/cookie?).

This fetches a handful of real imot.bg listing pages in full and dumps
every <script> block that mentions "payload" or "notification-popup"
verbatim, so a human can read the actual mechanism before anyone tries to
build extraction logic against it. Read-only, no data files touched.
"""

import json
import re
import time
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
SAMPLE_SIZE = 5
REQUEST_DELAY_SECONDS = 1.5

DATA_DIR = Path(__file__).parent / "data"
LEADS_FILE = DATA_DIR / "leads_imot.json"


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def main():
    listings = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
    sample = listings[:SAMPLE_SIZE]

    for l in sample:
        url = l["url"]
        time.sleep(REQUEST_DELAY_SECONDS)
        print(f"\n\n########## {url} ##########")
        try:
            html = fetch(url)
        except Exception as e:
            print(f"FAILED: {e}")
            continue

        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
        for script in scripts:
            if "payload" in script or "notification-popup" in script or "old_price" in script:
                print("---- script block ----")
                print(script.strip())

        # Also dump the raw HTML around the notification-popup element itself,
        # with a much wider window than the previous probe used.
        for m in re.finditer(r"notification-popup", html):
            start = max(0, m.start() - 600)
            end = min(len(html), m.end() + 600)
            print("---- wide HTML context around notification-popup ----")
            print(html[start:end])


if __name__ == "__main__":
    main()
