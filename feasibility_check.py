"""
One-off exploration script to find Homes.bg's real search URL for Sofia
apartments for sale. Not part of the scraper suite - run manually via the
temporary feasibility-check workflow, then deleted.
"""

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

KEYWORDS = ["sofia", "sofiya", "apartament", "prodaj", "prodazh", "imot", "search"]


def dump_links(url):
    print("=" * 70)
    print("FETCHING:", url)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"status: {resp.status_code}  len: {len(resp.text)}")
    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.find("title")
    print("title:", title.get_text() if title else None)

    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(k in href.lower() for k in KEYWORDS):
            links.add(href)
    print(f"found {len(links)} relevant links:")
    for l in sorted(links)[:60]:
        print("  ", l)

    forms = soup.find_all("form")
    for f in forms:
        print("form action:", f.get("action"), "method:", f.get("method"))

    return resp.text


def try_urls(urls):
    for name, url in urls:
        print("=" * 70)
        print(f"{name}  ->  {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
            text = resp.text
            print(f"status: {resp.status_code}  final_url: {resp.url}  len: {len(text)}")
            price_hits = len(re.findall(r"(\d[\d\s]{2,10})\s?(лв|bgn|eur|€)", text, re.IGNORECASE))
            print(f"  price-like patterns: {price_hits}")
            print(f"  snippet: {text[:500].strip().replace(chr(10), ' ')}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")


def main():
    dump_links("https://www.homes.bg/")

    print()
    print("### robots.txt ###")
    try:
        r = requests.get("https://www.homes.bg/robots.txt", headers=HEADERS, timeout=15)
        print(r.text[:2000])
    except Exception as e:
        print("ERROR:", e)

    print()
    print("### sitemap.xml ###")
    try:
        r = requests.get("https://www.homes.bg/sitemap.xml", headers=HEADERS, timeout=15)
        print(f"status: {r.status_code} len: {len(r.text)}")
        print(r.text[:2000])
    except Exception as e:
        print("ERROR:", e)

    try_urls([
        ("candidate 1", "https://www.homes.bg/imoti/sofia/prodajba/apartamenti"),
        ("candidate 2", "https://www.homes.bg/bg/prodazhbi/apartamenti/sofia"),
        ("candidate 3", "https://www.homes.bg/search?type=1&city=sofia"),
        ("candidate 4", "https://www.homes.bg/offers/sales/apartments/sofia"),
    ])


if __name__ == "__main__":
    main()
