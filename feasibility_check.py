"""
Round 2: explore bazar.bg's /obiavi/imoti category page to find how to filter
to Sofia + apartments + for-sale (query params, sub-category links, etc).
"""

import re
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
    r = check("https://bazar.bg/obiavi/imoti")
    soup = BeautifulSoup(r.text, "html.parser")

    print("\n--- all links under /obiavi/imoti (sub-categories/filters) ---")
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/obiavi/imoti" in href or "imoti" in href.lower():
            text = a.get_text(strip=True)
            if href not in seen:
                seen.add(href)
                print(repr(href), "|", repr(text[:60]))
        if len(seen) >= 60:
            break

    print("\n--- form elements (selects/inputs) that might be filters ---")
    for form in soup.find_all("form"):
        print("FORM action=", form.get("action"), "method=", form.get("method"))
        for sel in form.find_all("select"):
            print("  select name=", sel.get("name"))
            for opt in sel.find_all("option")[:15]:
                print("    option value=", repr(opt.get("value")), "text=", repr(opt.get_text(strip=True)))

    print("\n--- search for 'sofia' or 'apartament' anywhere in href attributes ---")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"sofia|apartament", href, re.I):
            print(repr(href), "|", repr(a.get_text(strip=True)[:60]))


if __name__ == "__main__":
    main()
