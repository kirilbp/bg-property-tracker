import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://bazar.bg/obiava-55509986/dvustaen-apartament-63-m-kv"

resp = requests.get(URL, headers={"User-Agent": UA, "Accept-Language": "bg-BG,bg;q=0.9"}, timeout=20)
html = resp.text
print(f"HTTP {resp.status_code}, {len(html)} chars")

for kw in ["lat", "lng", "lon", "coord", "geo", "marker", "google.com/maps", "maps.google", "staticmap", "see_on_map", "map_canvas"]:
    idxs = [m.start() for m in re.finditer(re.escape(kw), html, re.I)]
    print(f"\n keyword '{kw}': {len(idxs)} occurrences")
    for i in idxs[:5]:
        start = max(0, i - 60)
        print(f"   ...{html[start:i+100]!r}...")

iframes = re.findall(r'<iframe[^>]+src="([^"]+)"', html, re.I)
print(f"\n iframes: {len(iframes)}")
for src in iframes[:10]:
    print("  ", src[:200])

BROAD_RE = re.compile(r"(4[0-2]\.\d{3,})\D{1,10}(2[2-9]\.\d{3,})")
matches = BROAD_RE.findall(html)
print(f"\n broad coord matches: {matches[:10]}")
