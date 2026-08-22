"""
Round 5: test the real query-param search URL using the district/type IDs
found in the search form (Sofia = 5e60b66a0cbea, residential = 5e940970d1ab0).
"""

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}


def check(name, url):
    print("=" * 70)
    print(f"{name}  ->  {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    text = resp.text
    print(f"status: {resp.status_code}  final_url: {resp.url}  len: {len(text)}")
    soup = BeautifulSoup(text, "html.parser")
    title = soup.find("title")
    print("title:", title.get_text() if title else None)
    all_htm_links = [a["href"] for a in soup.find_all("a", href=True) if ".htm" in a["href"]]
    sofia_links = [h for h in all_htm_links if "софия" in h.lower()]
    print(f"  total .htm links: {len(all_htm_links)}, sofia .htm links: {len(sofia_links)}")
    for l in sorted(set(sofia_links))[:15]:
        print("    ", l)
    non_sofia_sample = [h for h in all_htm_links if "софия" not in h.lower()][:5]
    print("  non-sofia sample:", non_sofia_sample)


def main():
    check("Sofia district only", "https://imoti.bg/продажби?district_id_multi=5e60b66a0cbea")
    check("Sofia + residential type", "https://imoti.bg/продажби?district_id_multi=5e60b66a0cbea&type_id_multi=5e940970d1ab0")
    check("Sofia + residential, page2", "https://imoti.bg/продажби?district_id_multi=5e60b66a0cbea&type_id_multi=5e940970d1ab0&pagination=2")


if __name__ == "__main__":
    main()
