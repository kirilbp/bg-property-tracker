"""
One-shot diagnostic: does any portal's detail page expose a postal code
("пощенски код", "п.к.", or a bare 4-digit code near the address) for a
listing - a signal that could disambiguate a settlement name shared by
more than one real place (e.g. "Бяла", a real, different municipality in
both Varna and Ruse oblasts, with no coordinates anywhere on homes.bg's
own pages to tell them apart - see backfill_others_geocode.py's own
docstring).

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

KEYWORDS = ["пощенски код", "п.к.", "postal code", "zip code", "postcode"]
# Bulgarian postal codes are 4 digits, 1000-9999.
POSTCODE_RE = re.compile(r"\b([1-9]\d{3})\b")


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
            print("  no postal-code keyword found anywhere on the page")

        # Dump the visible text (not raw HTML/CSS/JS noise) so a bare
        # 4-digit code sitting next to an address is actually inspectable,
        # not buried in a sea of unrelated numeric IDs from markup/scripts.
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        codes = POSTCODE_RE.findall(text)
        print(f"  {len(codes)} bare 4-digit numbers (1000-9999) in visible text: {codes[:20]}")


if __name__ == "__main__":
    main()
