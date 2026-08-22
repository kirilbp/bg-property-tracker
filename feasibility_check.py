"""
Round 3: explore bazar.bg's /obiavi/prodazhba-imoti (for-sale) page to find how
it links to city-filtered and apartment-only combined URLs.
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}


def check(url):
    print("=" * 70)
    print("GET", url)
    r = requests.get(url, headers=HEADERS, timeout=15)
    print("status:", r.status_code, "length:", len(r.text))
    return r


def main():
    r = check("https://bazar.bg/obiavi/prodazhba-imoti")
    soup = BeautifulSoup(r.text, "html.parser")

    print("\n--- links containing 'sofia' or 'apartament' ---")
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "sofia" in href.lower() or "apartament" in href.lower():
            text = a.get_text(strip=True)
            if href not in seen:
                seen.add(href)
                print(repr(href), "|", repr(text[:70]))

    print("\n--- nav/breadcrumb/category links near top of page (first 400 chars of body classes/nav) ---")
    nav = soup.find("nav")
    if nav:
        print(nav.get_text(" ", strip=True)[:500])

    # Try some plausible combined URLs directly.
    for guess in [
        "https://bazar.bg/obiavi/prodazhba-apartamenti",
        "https://bazar.bg/obiavi/prodazhba-imoti/sofia",
        "https://bazar.bg/obiavi/apartamenti/sofia",
        "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia",
        "https://bazar.bg/obiavi/prodazhba-apartamenti-sofia",
    ]:
        rr = check(guess)
        if rr is not None and rr.status_code == 200:
            s2 = BeautifulSoup(rr.text, "html.parser")
            title = s2.title.string if s2.title else None
            h1 = s2.find("h1")
            print("  title:", title)
            print("  h1:", h1.get_text(strip=True) if h1 else None)


if __name__ == "__main__":
    main()
