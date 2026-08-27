"""
Round 2: round 1 (plain requests.get) showed imot.bg/imoti.net have no
free-text description in the raw HTML (just auto-generated title-style
meta tags), alo.bg's meta description looks like it embeds real text
after a boilerplate prefix (truncated at 200 chars, needs a full dump),
and olx.bg/bcpea are blocked outright by anti-bot (403) under plain
requests - both are scraped via Playwright already (scraper_olx.py,
scraper_bcpea.py), so this round re-fetches those three via a real
browser context to see what a real scraper visit would actually get.

Not part of the scraper pipeline - dispatched by hand, read once, then
deleted.
"""

import json
import re

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def dump_signals(name, html):
    print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
    soup = BeautifulSoup(html, "html.parser")

    meta_desc = soup.find("meta", attrs={"name": "description"})
    print("FULL meta[name=description]:", (meta_desc.get("content") if meta_desc else None))

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    print("FULL meta[property=og:description]:", (og_desc.get("content") if og_desc else None))

    scripts = soup.find_all("script", type="application/ld+json")
    for i, s in enumerate(scripts):
        try:
            data = json.loads(s.string or "{}")
        except Exception as e:
            print(f"  ld+json[{i}] parse error: {e}")
            continue
        blobs = data if isinstance(data, list) else [data]
        for d in blobs:
            if isinstance(d, dict):
                if "description" in d:
                    print(f"  ld+json[{i}] FULL description: {d['description']!r}")
                else:
                    print(f"  ld+json[{i}] keys (no description): {list(d.keys())}")

    # Broad sweep: any element with class/id hinting at description-like
    # Bulgarian/English words, plus any <p>/<div> with >150 chars of text
    # that isn't obviously nav/footer boilerplate.
    hint_re = re.compile(
        r"descri|opisan|podrobnost|detail|content|body|text|info|param|charact|характер|описан",
        re.I,
    )
    candidates = soup.find_all(attrs={"class": hint_re})
    print(f"class-hint elements: {len(candidates)}")
    seen_texts = set()
    for c in candidates:
        text = c.get_text(" ", strip=True)
        if len(text) < 80 or text in seen_texts:
            continue
        seen_texts.add(text)
        print(f"  <{c.name} class={c.get('class')}> len={len(text)}: {text[:250]!r}")
        if len(seen_texts) >= 8:
            break

    print("--- HTML length:", len(html))


def fetch_via_requests(name, url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    print(f"\nFETCH(requests) {name} {url} -> {resp.status_code}")
    if resp.status_code == 200:
        dump_signals(name, resp.text)
    else:
        print("body snippet:", resp.text[:200])


def fetch_via_playwright(page, name, url):
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        html = page.content()
        print(f"\nFETCH(playwright) {name} {url} -> ok, len={len(html)}")
        dump_signals(name, html)
    except Exception as e:
        print(f"\nFETCH(playwright) {name} {url} -> EXCEPTION {e}")


def main():
    fetch_via_requests("alo.bg", "https://www.alo.bg/dvustaen-apartament-v-kv-manastirski-livadi-zapad-11332379")
    fetch_via_requests("imoti.net", "https://www.imoti.net/en/obiava/prodava/sofia/manastirski-livadi/dvustaen/6291321/")
    fetch_via_requests("imot.bg (requests, for comparison)", "https://www.imot.bg/obiava-1b175093643714011-prodava-dvustaen-apartament-grad-sofiya-lyulin-4")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()

        fetch_via_playwright(page, "imot.bg", "https://www.imot.bg/obiava-1b175093643714011-prodava-dvustaen-apartament-grad-sofiya-lyulin-4")
        fetch_via_playwright(page, "olx.bg", "https://www.olx.bg/d/ad/prodavam-3-stayno-zhilische-v-bakston-CID368-IDa42p7.html")
        fetch_via_playwright(page, "bcpea", "https://sales.bcpea.org/properties/88853")

        browser.close()


if __name__ == "__main__":
    main()
