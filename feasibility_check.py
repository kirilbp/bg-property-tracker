"""
Round 3: find imoti.bg's real Sofia apartments-for-sale search URL by
inspecting the search form page and trying category-page candidates.
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}


def try_urls(urls):
    for name, url in urls:
        print("=" * 70)
        print(f"{name}  ->  {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
            text = resp.text
            print(f"status: {resp.status_code}  final_url: {resp.url}  len: {len(text)}")
            soup = BeautifulSoup(text, "html.parser")
            title = soup.find("title")
            print("title:", title.get_text() if title else None)
            listing_links = [a["href"] for a in soup.find_all("a", href=True) if ".htm" in a["href"] and "софия" in a["href"].lower()]
            print(f"  sofia .htm listing links: {len(listing_links)}")
            for l in sorted(set(listing_links))[:15]:
                print("    ", l)
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")


def inspect_search_form():
    print("=" * 70)
    print("### /търсене form inspection ###")
    resp = requests.get("https://imoti.bg/търсене", headers=HEADERS, timeout=20)
    print(f"status: {resp.status_code} len: {len(resp.text)}")
    soup = BeautifulSoup(resp.text, "html.parser")
    for form in soup.find_all("form"):
        print("form action:", form.get("action"), "method:", form.get("method"))
    for sel in soup.find_all("select"):
        print("select name:", sel.get("name"), "id:", sel.get("id"))
        for opt in sel.find_all("option")[:10]:
            print("   option:", opt.get("value"), "->", opt.get_text(strip=True))


def main():
    inspect_search_form()
    try_urls([
        ("candidate: продажби/софия", "https://imoti.bg/продажби/софия"),
        ("candidate: продажби/апартаменти/софия", "https://imoti.bg/продажби/апартаменти/софия"),
        ("candidate: продажби/апартамент/софия", "https://imoti.bg/продажби/апартамент/софия"),
        ("продажби (general)", "https://imoti.bg/продажби"),
    ])


if __name__ == "__main__":
    main()
