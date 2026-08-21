"""
One-off exploration script, round 3: confirm photo URL pattern, total
listing count, and pagination behavior for Homes.bg.
Not part of the scraper suite - run manually, then deleted.
"""

import json
import re
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}


def get_state(session, url):
    resp = session.get(url, headers=HEADERS, timeout=20)
    m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", resp.text, re.DOTALL)
    state = json.loads(m.group(1)) if m else None
    return resp, state


def main():
    session = requests.Session()

    resp, state = get_state(session, "https://www.homes.bg/")
    print(f"page 1 status: {resp.status_code}")
    offers_block = state["data"]["offers"]
    print("offers block keys:", list(offers_block.keys()))
    print("result count:", len(offers_block.get("result", [])))
    for k, v in offers_block.items():
        if k != "result":
            print(f"  {k}: {v}")

    # find an actual <img> tag for a known photo id to determine URL pattern
    first_photo = offers_block["result"][0]["photo"]
    print("\nfirst offer photo meta:", first_photo)
    name = first_photo["name"]
    idx = resp.text.find(name)
    if idx != -1:
        print("--- context around photo id in raw HTML ---")
        print(resp.text[max(0, idx - 300):idx + 100])
    else:
        print("photo id not found as plain text in HTML (only inside JSON blob)")

    # look for any <img src=...> pointing at a CDN host, to infer the pattern
    img_srcs = sorted(set(re.findall(r'<img[^>]+src="([^"]+)"', resp.text)))[:10]
    print("\nsample <img src> values found in HTML:")
    for s in img_srcs:
        print("  ", s)

    # test page 2 with the same session (cookies) to check pagination + distinct results
    resp2, state2 = get_state(session, "https://www.homes.bg/?page=2")
    print(f"\npage 2 status: {resp2.status_code}")
    if state2:
        ids_p1 = {o["id"] for o in offers_block["result"]}
        ids_p2 = {o["id"] for o in state2["data"]["offers"]["result"]}
        print("page2 result count:", len(ids_p2))
        print("overlap between page1 and page2 ids:", len(ids_p1 & ids_p2))
    else:
        print("no PRELOADED_STATE on page 2")


if __name__ == "__main__":
    main()
