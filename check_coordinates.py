import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

URLS = {
    "imoti.net": "https://www.imoti.net/en/obiava/prodava/sofia/lulin-3/dvustaen/6290402/?sid=icNBCK&page=1",
    "alo.bg": "https://www.alo.bg/sobstvenik-prodava-2-staen-apartament-ot-62-42-kv-m-v-gr-sofiya-kv-goce-delchev-11054526",
    "homes.bg": "https://www.homes.bg/offer/apartament-za-prodazhba/tristaen-270m2-sofiya-zhk.-lozenec/as1700401",
    "imot.bg": "https://www.imot.bg/obiava-1b178506444161565-prodava-dvustaen-apartament-grad-sofiya-mladost-4",
    "olx.bg": "https://www.olx.bg/d/ad/predlagam-tsyala-samostoyatelna-sgrada-s-11-apartamenta-CID368-ID9QcUA.html?search_reason=search%7Corganic",
    "bazar.bg": "https://bazar.bg/obiava-55620361/prodava-2-staen-gr-sofiia-mladost-4",
    "imoti.bg": "https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/di:софия/cu:BGN",
}

GENERIC_COORD_RE = re.compile(
    r'(?:lat(?:itude)?)["\']?\s*[:=]\s*["\']?(4[0-9]\.\d{3,8})["\']?[^}]{0,80}?'
    r'(?:lng|lon(?:gitude)?)["\']?\s*[:=]\s*["\']?(2[0-9]\.\d{3,8})',
    re.IGNORECASE,
)
GEO_META_RE = re.compile(r'name=["\']geo\.position["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE)
ICBM_RE = re.compile(r'name=["\']ICBM["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE)
MAP_MARKER_RE = re.compile(r'(4[0-9]\.\d{4,8})\s*,\s*(2[0-9]\.\d{4,8})')


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
    print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
    try:
        html = fetch(url)
        print(f"fetched {len(html)} bytes")
    except Exception as e:
        print(f"FETCH FAILED: {e}")
        continue

    found_any = False

    m = GEO_META_RE.search(html)
    if m:
        print(f"  geo.position meta tag: {m.group(1)}")
        found_any = True
    m = ICBM_RE.search(html)
    if m:
        print(f"  ICBM meta tag: {m.group(1)}")
        found_any = True

    m = GENERIC_COORD_RE.search(html)
    if m:
        print(f"  lat/lng JSON pair: {m.group(1)}, {m.group(2)}")
        found_any = True

    matches = MAP_MARKER_RE.findall(html)
    if matches:
        sofia_matches = [(a, b) for a, b in matches if 42.4 < float(a) < 43.0 and 23.0 < float(b) < 23.6]
        if sofia_matches:
            print(f"  raw Sofia-range coordinate pairs found ({len(sofia_matches)}): {sofia_matches[:5]}")
            found_any = True

    if not found_any:
        print("  NO coordinates found anywhere in the page")
