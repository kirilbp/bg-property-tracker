import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

TARGETS = {
    "imot.bg": "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag",
    "imoti.bg": "https://imoti.bg/продажби/тристаен-апартамент/софия/център-512778.htm/di:софия/cu:BGN",
}

KEYWORDS = ["lat", "lng", "lon", "coord", "geo", "marker", "google.com/maps", "maps.google",
            "staticmap", "see_on_map", "map_canvas", "data-lat", "data-long", "data-lng"]

BROAD_RE = re.compile(r"(4[0-2]\.\d{3,})\D{1,15}(2[2-9]\.\d{3,})")

for portal, url in TARGETS.items():
    print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
    try:
        resp = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "bg-BG,bg;q=0.9"}, timeout=20)
    except Exception as e:
        print(f"FETCH FAILED: {e}")
        continue
    html = resp.text
    print(f"HTTP {resp.status_code}, {len(html)} chars")

    for kw in KEYWORDS:
        idxs = [m.start() for m in re.finditer(re.escape(kw), html, re.I)]
        if not idxs:
            continue
        print(f"\n keyword '{kw}': {len(idxs)} occurrences")
        for i in idxs[:5]:
            start = max(0, i - 60)
            print(f"   ...{html[start:i+120]!r}...")

    iframes = re.findall(r'<iframe[^>]+src="([^"]+)"', html, re.I)
    print(f"\n iframes: {len(iframes)}")
    for src in iframes[:10]:
        print("  ", src[:200])

    matches = BROAD_RE.findall(html)
    print(f"\n broad coord matches: {matches[:10]}")
