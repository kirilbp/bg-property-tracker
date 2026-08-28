"""
One-shot diagnostic: for each portal that currently stores only a single
"photo" (thumbnail) per listing, fetch one real detail page and look for
signals of a full photo gallery - multiple distinct image URLs in a
gallery/carousel container, or a JSON blob (ld+json, inline script, or a
Next.js/Nuxt data island) carrying a photo array, the same way
homes.bg's own listing-grid API response already does (see
scraper_homes.py's "photos" field - the one portal that already has this).

Run via probe-nationwide-urls.yml (repoint its run step at this file),
not scheduled - a one-time investigation, dormant after its answer is in.
"""

import json
import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

SAMPLES = {
    "imot.bg": "https://www.imot.bg/obiava-1b175093643714011-prodava-dvustaen-apartament-grad-sofiya-lyulin-4",
    "olx.bg": "https://www.olx.bg/d/ad/top-zemedelska-zemya-ot-sobstvenik-na-gl-pat-karlovo-burgas-CID368-ID9YBbB.html",
    "bazar.bg": "https://bazar.bg/obiava-53259179/prodava-3-staen-gr-sofiia-tsentar",
    "imoti.bg": "https://imoti.bg/продажби/парцел/добрич-област/сжегларци-514972.htm/cu:BGN",
    "alo.bg": "https://www.alo.bg/dvustaen-apartament-v-kv-manastirski-livadi-zapad-11332379",
    "imoti.net": "https://www.imoti.net/en/obiava/prodava/sofia/manastirski-livadi/dvustaen/6291321/",
    "bcpea": "https://sales.bcpea.org/properties/88853",
}


def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        return f"__FETCH_ERROR__ {e}"


def find_image_urls(html):
    """All distinct absolute image URLs referenced anywhere in the page
    (img src/data-src, srcset entries, and any http(s) URL ending in a
    common image extension inside inline scripts/JSON) - a first,
    unfiltered pass to see what's even on the page before writing a
    precise per-portal extractor."""
    urls = set()
    for m in re.finditer(r'(https?://[^\s"\'<>\\]+?\.(?:jpg|jpeg|png|webp))(?:[?"\'\s>]|$)', html, re.IGNORECASE):
        urls.add(m.group(1))
    return urls


def main():
    for portal, url in SAMPLES.items():
        print(f"\n{'=' * 70}\n{portal}: {url}")
        html = fetch(url)
        if html.startswith("__FETCH_ERROR__"):
            print(f"  {html}")
            continue
        print(f"  fetched {len(html)} bytes")

        image_urls = find_image_urls(html)
        print(f"  {len(image_urls)} distinct image-like URLs found on the page")
        for u in sorted(image_urls)[:30]:
            print(f"    {u}")

        # ld+json blocks often carry an "image" array for the real gallery.
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            blobs = data if isinstance(data, list) else [data]
            for blob in blobs:
                if isinstance(blob, dict) and blob.get("image"):
                    img = blob["image"]
                    count = len(img) if isinstance(img, list) else 1
                    print(f"  ld+json 'image' key: {count} entr(y/ies): {img if count <= 5 else str(img)[:300]}")

        # Common gallery/carousel container class-name signals.
        for cls_kw in ("gallery", "carousel", "slider", "swiper", "photos", "images", "thumb"):
            hits = soup.find_all(class_=re.compile(cls_kw, re.IGNORECASE))
            if hits:
                print(f"  {len(hits)} element(s) with class matching /{cls_kw}/i (first tag: {hits[0].name})")


if __name__ == "__main__":
    main()
