"""
Round 4: dig into the actual search mechanism - form inputs, hidden fields,
and any embedded JS API/state that reveals how city filtering really works.
"""

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}


def main():
    resp = requests.get("https://imoti.bg/продажби", headers=HEADERS, timeout=20)
    text = resp.text
    print(f"status: {resp.status_code} len: {len(text)}")
    soup = BeautifulSoup(text, "html.parser")

    for form in soup.find_all("form"):
        print("=" * 60)
        print("FORM action:", form.get("action"), "method:", form.get("method"), "id:", form.get("id"))
        for inp in form.find_all(["input", "select"]):
            print("  ", inp.name, "name=", inp.get("name"), "value=", inp.get("value"), "id=", inp.get("id"))

    # look for any city-related select/options anywhere on page, not just inside forms
    for sel in soup.find_all("select"):
        name = sel.get("name") or sel.get("id") or ""
        if "sel" not in locals():
            pass
        opts = sel.find_all("option")
        print(f"\nSELECT name={sel.get('name')} id={sel.get('id')} options={len(opts)}")
        for opt in opts[:15]:
            print("   ", opt.get("value"), "->", opt.get_text(strip=True))

    # look for embedded JS config / API base / city IDs
    print("\n### JS clues ###")
    api_refs = sorted(set(re.findall(r'["\'](/api/[^"\']{0,80})["\']', text)))
    print("api refs:", api_refs[:20])
    city_refs = sorted(set(re.findall(r'["\']([^"\']{0,40}[Ss]ofia[^"\']{0,40})["\']', text)))
    print("sofia-ish JS string refs:", city_refs[:20])

    # check pagination links
    page_links = sorted(set(re.findall(r'href="([^"]*стр[^"]*)"', text, re.IGNORECASE)))
    print("\npagination-looking links:", page_links[:10])


if __name__ == "__main__":
    main()
