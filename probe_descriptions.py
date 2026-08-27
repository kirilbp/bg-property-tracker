"""
One-shot probe: fetch a real sample detail page from each of the 6
portals currently missing description coverage, and dump every plausible
description-bearing signal (meta description, og:description, JSON-LD,
and any labeled text blocks) so extraction code can be written against
real page structure instead of guesswork.

Not part of the scraper pipeline - dispatched by hand via the dormant
"Probe nationwide search URLs" workflow, read once, then deleted.
"""

import json
import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

SAMPLES = {
    "imot.bg": "https://www.imot.bg/obiava-1b175093643714011-prodava-dvustaen-apartament-grad-sofiya-lyulin-4",
    "olx.bg": "https://www.olx.bg/d/ad/prodavam-3-stayno-zhilische-v-bakston-CID368-IDa42p7.html",
    "bazar.bg": "https://bazar.bg/obiava-53259179/prodava-3-staen-gr-sofiia-tsentar",
    "alo.bg": "https://www.alo.bg/dvustaen-apartament-v-kv-manastirski-livadi-zapad-11332379",
    "imoti.net": "https://www.imoti.net/en/obiava/prodava/sofia/manastirski-livadi/dvustaen/6291321/",
    "bcpea": "https://sales.bcpea.org/properties/88853",
}


def dump_signals(name, html):
    print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
    soup = BeautifulSoup(html, "html.parser")

    meta_desc = soup.find("meta", attrs={"name": "description"})
    print("meta[name=description]:", (meta_desc.get("content") if meta_desc else None))

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    print("meta[property=og:description]:", (og_desc.get("content") if og_desc else None))

    scripts = soup.find_all("script", type="application/ld+json")
    print(f"JSON-LD blocks: {len(scripts)}")
    for i, s in enumerate(scripts):
        try:
            data = json.loads(s.string or "{}")
        except Exception as e:
            print(f"  [{i}] parse error: {e}")
            continue
        if isinstance(data, list):
            for d in data:
                if isinstance(d, dict) and "description" in d:
                    print(f"  [{i}] description: {d['description'][:300]!r}")
        elif isinstance(data, dict):
            if "description" in data:
                print(f"  [{i}] description: {data['description'][:300]!r}")
            else:
                print(f"  [{i}] keys: {list(data.keys())}")

    # Any element whose class/id hints at "description"/"opisanie".
    candidates = soup.find_all(attrs={"class": re.compile(r"descri|opisan|text-content|adv-text|ad-description", re.I)})
    print(f"class/id description-hint elements: {len(candidates)}")
    for c in candidates[:5]:
        text = c.get_text(" ", strip=True)
        print(f"  <{c.name} class={c.get('class')}>: {text[:200]!r}")

    print("--- HTML length:", len(html))


def main():
    for name, url in SAMPLES.items():
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            print(f"\nFETCH {name} {url} -> {resp.status_code}")
            if resp.status_code == 200:
                dump_signals(name, resp.text)
            else:
                print("body snippet:", resp.text[:300])
        except Exception as e:
            print(f"\nFETCH {name} {url} -> EXCEPTION {e}")


if __name__ == "__main__":
    main()
