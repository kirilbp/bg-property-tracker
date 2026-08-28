"""
Round 2: probe_photos.py's first pass found imot.bg/bazar.bg/imoti.net
already expose a full gallery via plain HTML, but left two open
questions - dump raw detail for those here (see probe_photos.py's
docstring for the overall goal).

alo.bg: only 1 image URL was found by a generic regex despite 14
elements with a class matching /images/i - dump those elements' raw
HTML to see what attribute actually carries each photo (data-src,
srcset, a JSON blob, etc.) instead of a plain src.

imoti.bg: the one sample probed was a land parcel with a single
photo - check a real apartment listing to see if it has (and exposes)
more than one.
"""

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


print("=" * 70)
print("alo.bg - raw HTML of each /images/i-classed element")
html = fetch("https://www.alo.bg/dvustaen-apartament-v-kv-manastirski-livadi-zapad-11332379")
soup = BeautifulSoup(html, "html.parser")
hits = soup.find_all(class_=re.compile("images", re.IGNORECASE))
for i, el in enumerate(hits[:14]):
    print(f"--- element {i} ({el.name}) ---")
    print(str(el)[:400])

print("\nany JSON-looking script blobs mentioning 'photo' or 'image'?")
for script in soup.find_all("script"):
    text = script.string or ""
    if ("photo" in text.lower() or "gallery" in text.lower()) and len(text) < 5000:
        print("---")
        print(text[:1000])

print("\n" + "=" * 70)
print("imoti.bg apartment listing - image URLs")
html2 = fetch("https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/cu:BGN")
urls = set(re.findall(r'(https?://[^\s"\'<>\\]+?\.(?:jpg|jpeg|png|webp))(?:[?"\'\s>]|$)', html2, re.IGNORECASE))
print(f"{len(urls)} distinct image-like URLs:")
for u in sorted(urls):
    print(f"  {u}")
