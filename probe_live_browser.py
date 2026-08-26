"""
Diagnostic: confirm the live page is actually serving the latest
index.html (not a stale cache somewhere between GitHub Pages and
imotenradar.com), by fetching the raw HTML and checking for a fingerprint
string unique to the latest fetchAllRows() fix.
"""

import requests

URL = "https://imotenradar.com/"


def main():
    resp = requests.get(URL, timeout=30, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
    print(f"status: {resp.status_code}")
    print(f"headers: {dict(resp.headers)}")
    html = resp.text
    print(f"html length: {len(html)}")
    print(f"contains 'const concurrency = 3': {'const concurrency = 3' in html}")
    print(f"contains 'const concurrency = 5': {'const concurrency = 5' in html}")
    print(f"contains 'orderCols': {'orderCols' in html}")
    print(f"contains 'orderCol =': {'orderCol =' in html}")


if __name__ == "__main__":
    main()
