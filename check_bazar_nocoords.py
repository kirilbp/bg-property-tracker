import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URLS = [
    "https://bazar.bg/obiava-55738083/prodava-2-staen-gr-sofiia-manastirski-livadi",
    "https://bazar.bg/obiava-55581677/prodava-2-staen-gr-sofiia-strelbishte",
    "https://bazar.bg/obiava-55620361/prodava-2-staen-gr-sofiia-mladost-4",
]

SEE_ON_MAP_TAG_RE = re.compile(r'<a\b[^>]*\bid="see_on_map"[^>]*>')

for url in URLS:
    print(f"\n{'='*70}\n{url}\n{'='*70}")
    resp = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "bg-BG,bg;q=0.9"}, timeout=20)
    html = resp.text
    print(f"HTTP {resp.status_code}, {len(html)} chars")

    m = SEE_ON_MAP_TAG_RE.search(html)
    print("see_on_map tag found:", bool(m))
    if m:
        print("tag:", m.group(0)[:300])

    for kw in ["see_on_map", "map_canvas", 'id="location', "data-lat", "data-long"]:
        count = html.count(kw)
        print(f"  occurrences of '{kw}': {count}")

    loc_idx = html.find('class="location"')
    if loc_idx != -1:
        print("  context around class=\"location\":", html[max(0,loc_idx-50):loc_idx+300])
