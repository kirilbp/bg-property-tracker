"""
Round 2: find imoti.bg's real listing link pattern and Sofia sales search
URL, and inspect one listing card's HTML structure.
"""

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

KEYWORDS = ["sofia", "apartament", "prodaj", "prodazh", "obiava", "imot"]


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
    for l in sorted(links)[:50]:
        print("  ", l)
    return resp.text, soup


def main():
    text, soup = dump_links("https://www.imoti.bg/")

    print()
    print("### robots.txt ###")
    try:
        r = requests.get("https://www.imoti.bg/robots.txt", headers=HEADERS, timeout=15)
        print(r.text[:1500])
    except Exception as e:
        print("ERROR:", e)


if __name__ == "__main__":
    main()
