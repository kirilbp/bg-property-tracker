import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

URLS = {
    "alo.bg": "https://www.alo.bg/sobstvenik-prodava-2-staen-apartament-ot-62-42-kv-m-v-gr-sofiya-kv-goce-delchev-11054526",
    "homes.bg": "https://www.homes.bg/offer/apartament-za-prodazhba/tristaen-270m2-sofiya-zhk.-lozenec/as1700401",
    "imot.bg": "https://www.imot.bg/obiava-1b178506444161565-prodava-dvustaen-apartament-grad-sofiya-mladost-4",
    "bazar.bg": "https://bazar.bg/obiava-55620361/prodava-2-staen-gr-sofiia-mladost-4",
    "imoti.bg": "https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/di:софия/cu:BGN",
}

PATTERNS = {
    "data-lat attr": re.compile(r'data-lat[a-z]*=["\']?(-?\d{1,3}\.\d{2,8})', re.IGNORECASE),
    "LatLng(": re.compile(r'LatLng\(\s*(-?\d{1,3}\.\d{2,8})\s*,\s*(-?\d{1,3}\.\d{2,8})', re.IGNORECASE),
    "L.marker(": re.compile(r'L\.marker\(\s*\[\s*(-?\d{1,3}\.\d{2,8})\s*,\s*(-?\d{1,3}\.\d{2,8})', re.IGNORECASE),
    "maps google iframe": re.compile(r'(?:google\.com/maps[^"\']*|maps\.google[^"\']*)["\']', re.IGNORECASE),
    "center: {lat": re.compile(r'center["\']?\s*:\s*\{\s*lat["\']?\s*:\s*(-?\d{1,3}\.\d{2,8})', re.IGNORECASE),
    "q= coord in url": re.compile(r'[?&]q=(-?\d{1,3}\.\d{2,8}),(-?\d{1,3}\.\d{2,8})'),
    "any 'map' mention": re.compile(r'(leaflet|mapbox|googlemaps|google\.maps|yandex\.maps|карта)', re.IGNORECASE),
}


def fetch(url):
    parts = url.split("://", 1)
    scheme, rest = parts[0], parts[1]
    host, path = rest.split("/", 1) if "/" in rest else (rest, "")
    safe_path = "/".join(urllib.parse.quote(seg, safe=":?&=%") for seg in path.split("/"))
    safe_url = f"{scheme}://{host}/{safe_path}"
    req = urllib.request.Request(safe_url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


for portal, url in URLS.items():
    print(f"\n{'='*70}\n{portal}\n{'='*70}")
    try:
        html = fetch(url)
        print(f"fetched {len(html)} bytes")
    except Exception as e:
        print(f"FETCH FAILED: {e}")
        continue

    for label, pat in PATTERNS.items():
        matches = pat.findall(html)
        if matches:
            print(f"  [{label}] {matches[:3]}")
