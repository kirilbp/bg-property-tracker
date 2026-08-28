"""
One-shot diagnostic: does any portal's detail page expose a floor plan
image (Bulgarian: "разпределение"/"скица") separately from its regular
photo gallery? Checks for the Bulgarian keywords in alt text, captions,
and nearby labels, plus filenames/URLs hinting at a plan/layout image.

Run via probe-nationwide-urls.yml (repoint its run step at this file),
not scheduled - a one-time investigation, dormant after its answer is in.
"""

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

SAMPLES = {
    "imot.bg": "https://www.imot.bg/obiava-1b175093643714011-prodava-dvustaen-apartament-grad-sofiya-lyulin-4",
    "bazar.bg": "https://bazar.bg/obiava-53259179/prodava-3-staen-gr-sofiia-tsentar",
    "imoti.bg": "https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/cu:BGN",
    "alo.bg": "https://www.alo.bg/dvustaen-apartament-v-kv-manastirski-livadi-zapad-11332379",
    "imoti.net": "https://www.imoti.net/en/obiava/prodava/sofia/manastirski-livadi/dvustaen/6291321/",
}

KEYWORDS = ["разпределение", "скица", "план на имота", "floor plan", "floorplan", "layout"]


def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        return f"__FETCH_ERROR__ {e}"


def main():
    for portal, url in SAMPLES.items():
        print(f"\n{'=' * 70}\n{portal}: {url}")
        html = fetch(url)
        if html.startswith("__FETCH_ERROR__"):
            print(f"  {html}")
            continue
        lower = html.lower()
        for kw in KEYWORDS:
            count = lower.count(kw.lower())
            if count:
                idx = lower.index(kw.lower())
                print(f"  found {count}x {kw!r} - context: ...{html[max(0, idx - 100):idx + 150]}...")
        if not any(kw.lower() in lower for kw in KEYWORDS):
            print("  no floor-plan keyword found anywhere on the page")

        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            alt = (img.get("alt") or "").lower()
            src = (img.get("src") or "").lower()
            if any(kw.lower() in alt or kw.lower() in src for kw in KEYWORDS):
                print(f"  img with plan-like alt/src: alt={img.get('alt')!r} src={img.get('src')!r}")


if __name__ == "__main__":
    main()
