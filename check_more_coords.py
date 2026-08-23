import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_encoded(url):
    parts = url.split("://", 1)
    scheme, rest = parts[0], parts[1]
    host, path = rest.split("/", 1) if "/" in rest else (rest, "")
    safe_path = "/".join(urllib.parse.quote(seg, safe=":?&=%") for seg in path.split("/"))
    return fetch(f"{scheme}://{host}/{safe_path}")


print("=" * 70)
print("homes.bg: dumping one offer's JSON keys from __PRELOADED_STATE__")
print("=" * 70)
STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)
html = fetch("https://www.homes.bg/")
m = STATE_RE.search(html)
if m:
    state = json.loads(m.group(1))
    offers = state.get("data", {}).get("offers", {}).get("result", [])
    if offers:
        offer = offers[0]
        print("top-level keys:", sorted(offer.keys()))
        for k in offer.keys():
            if "lat" in k.lower() or "lon" in k.lower() or "geo" in k.lower() or "coord" in k.lower() or "map" in k.lower():
                print(f"  candidate key '{k}':", offer[k])
    else:
        print("no offers found")
else:
    print("no PRELOADED_STATE found")

print("\n" + "=" * 70)
print("bazar.bg: broader coordinate search on individual listing page")
print("=" * 70)
html = fetch("https://bazar.bg/obiava-55620361/prodava-2-staen-gr-sofiia-mladost-4")
print(f"fetched {len(html)} bytes")
for pat_label, pat in [
    ("lat/lng JSON key", re.compile(r'"lat(?:itude)?"\s*:\s*"?(-?\d{1,3}\.\d{2,8})"?[^}]{0,100}?"lon(?:gitude)?"\s*:\s*"?(-?\d{1,3}\.\d{2,8})', re.IGNORECASE)),
    ("data-lat attr", re.compile(r'data-lat[a-z]*=["\']?(-?\d{1,3}\.\d{2,8})', re.IGNORECASE)),
    ("map iframe src", re.compile(r'<iframe[^>]+src=["\']([^"\']*(?:map|google)[^"\']*)["\']', re.IGNORECASE)),
]:
    mm = pat.findall(html)
    if mm:
        print(f"  [{pat_label}]", mm[:3])

print("\n" + "=" * 70)
print("imoti.bg: broader coordinate search on individual listing page")
print("=" * 70)
html = fetch_encoded("https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/di:софия/cu:BGN")
print(f"fetched {len(html)} bytes")
for pat_label, pat in [
    ("lat/lng JSON key", re.compile(r'"lat(?:itude)?"\s*:\s*"?(-?\d{1,3}\.\d{2,8})"?[^}]{0,100}?"lon(?:gitude)?"\s*:\s*"?(-?\d{1,3}\.\d{2,8})', re.IGNORECASE)),
    ("data-lat attr", re.compile(r'data-lat[a-z]*=["\']?(-?\d{1,3}\.\d{2,8})', re.IGNORECASE)),
    ("map iframe src", re.compile(r'<iframe[^>]+src=["\']([^"\']*(?:map|google)[^"\']*)["\']', re.IGNORECASE)),
]:
    mm = pat.findall(html)
    if mm:
        print(f"  [{pat_label}]", mm[:3])
