import re
import json
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with open("data/leads_alo.json", encoding="utf-8") as f:
    alo = json.load(f)
url = alo[0]["url"] if isinstance(alo, list) else next(iter(alo.values()))["url"]

print(f"URL: {url}")
resp = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "bg-BG,bg;q=0.9"}, timeout=20)
html = resp.text
print(f"HTTP {resp.status_code}, {len(html)} chars")

for kw in ["lat", "lng", "lon", "coord", "geo", "\"y\":", "\"x\":", "marker", "google.com/maps", "maps.google", "staticmap"]:
    idxs = [m.start() for m in re.finditer(re.escape(kw), html, re.I)]
    print(f"\n keyword '{kw}': {len(idxs)} occurrences")
    for i in idxs[:5]:
        start = max(0, i - 60)
        print(f"   ...{html[start:i+80]!r}...")

iframes = re.findall(r'<iframe[^>]+src="([^"]+)"', html, re.I)
print(f"\n iframes: {len(iframes)}")
for src in iframes[:10]:
    print("  ", src[:200])

data_attrs = re.findall(r'data-(lat|lng|latitude|longitude|geo-lat|geo-lng)="([^"]+)"', html, re.I)
print(f"\n data-lat/lng attrs: {data_attrs[:10]}")
