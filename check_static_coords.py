import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

COORD_RE = re.compile(r"(4[0-9]\.\d{4,8})\D{1,20}(2[0-9]\.\d{4,8})")
LATLNG_KEY_RE = re.compile(r'"(lat|latitude|lng|lon|longitude)"\s*:\s*"?(-?\d{1,3}\.\d{3,8})"?', re.I)

TARGETS = {
    "bazar.bg": "https://bazar.bg/obiava-55509986/dvustaen-apartament-63-m-kv",
    "alo.bg": None,
    "imoti.net": None,
}

with open("data/leads_alo.json", encoding="utf-8") as f:
    import json
    alo = json.load(f)
    TARGETS["alo.bg"] = alo[0]["url"] if isinstance(alo, list) else next(iter(alo.values()))["url"]

with open("data/leads.json", encoding="utf-8") as f:
    import json
    net = json.load(f)
    TARGETS["imoti.net"] = net[0]["url"] if isinstance(net, list) else next(iter(net.values()))["url"]

for portal, url in TARGETS.items():
    print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
    try:
        resp = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "bg-BG,bg;q=0.9"}, timeout=20)
        print(f"  HTTP {resp.status_code}, {len(resp.text)} chars")
    except Exception as e:
        print(f"  FETCH FAILED: {e}")
        continue

    html = resp.text
    coord_matches = COORD_RE.findall(html)
    print(f"  raw coord-pattern matches: {len(coord_matches)}")
    for m in coord_matches[:10]:
        print(f"    {m}")

    key_matches = LATLNG_KEY_RE.findall(html)
    print(f"  lat/lng-keyed JSON matches: {len(key_matches)}")
    for m in key_matches[:15]:
        print(f"    {m}")

    for m in COORD_RE.finditer(html):
        start = max(0, m.start() - 80)
        print(f"  CONTEXT: ...{html[start:m.end()+40]}...")
        break
