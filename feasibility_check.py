"""
One-off exploration script, round 2: inspect homes.bg homepage structure in
detail - does it embed structured listing data (JSON) or only HTML text?
Not part of the scraper suite - run manually, then deleted.
"""

import re
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}


def main():
    resp = requests.get("https://www.homes.bg/", headers=HEADERS, timeout=20)
    text = resp.text
    print(f"status: {resp.status_code}  len: {len(text)}")

    # Look for a PRELOADED_STATE-style embedded JSON blob
    m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", text, re.DOTALL)
    if m:
        blob = m.group(1)
        print(f"PRELOADED_STATE found, length {len(blob)}")
        print(blob[:3000])
    else:
        print("No __PRELOADED_STATE__ found on homepage")

    # look for any other embedded JSON-looking globals
    for match in re.finditer(r"window\.(__\w+__)\s*=", text):
        print("found global:", match.group(1))

    # currency/price patterns - try several variants
    variants = {
        "лв (cyrillic)": re.findall(r"[\d\s.,]{3,12}\s?лв", text),
        "EUR word": re.findall(r"[\d\s.,]{3,12}\s?EUR", text, re.IGNORECASE),
        "euro sign": re.findall(r"[\d\s.,]{3,12}\s?€", text),
        "sq meters bg (кв.м)": re.findall(r"[\d.,]{1,8}\s?кв\.?\s?м", text),
    }
    for label, hits in variants.items():
        print(f"{label}: {len(hits)} matches, sample: {hits[:5]}")

    # Grep for "/api/" references in the raw HTML/JS to find the underlying data API
    api_refs = sorted(set(re.findall(r'["\'](/api/[^"\']{0,80})["\']', text)))
    print(f"\n/api/ references found in homepage HTML: {len(api_refs)}")
    for r in api_refs[:30]:
        print("  ", r)

    # Print a chunk of HTML around the first offer card to see its structure
    idx = text.find("as1700385")
    if idx == -1:
        idx = text.find("/offer/")
    if idx != -1:
        start = max(0, idx - 800)
        print("\n--- HTML around first offer card ---")
        print(text[start:idx + 800])

    # Check for a "next page" / "see all" link and pagination clues
    page_links = sorted(set(re.findall(r'href="([^"]*page[^"]*)"', text, re.IGNORECASE)))
    print(f"\npagination-looking links: {page_links[:10]}")


if __name__ == "__main__":
    main()
