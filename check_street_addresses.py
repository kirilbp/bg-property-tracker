import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"}

URLS = {
    "homes.bg": "https://www.homes.bg/offer/apartament-za-prodazhba/tristaen-270m2-sofiya-zhk.-lozenec/as1700401",
    "bazar.bg": "https://bazar.bg/obiava-55620361/prodava-2-staen-gr-sofiia-mladost-4",
    "imot.bg": "https://www.imot.bg/obiava-1b178506444161565-prodava-dvustaen-apartament-grad-sofiya-mladost-4",
    "imoti.bg": "https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/di:софия/cu:BGN",
    "olx.bg": "https://www.olx.bg/d/ad/predlagam-tsyala-samostoyatelna-sgrada-s-11-apartamenta-CID368-ID9QcUA.html?search_reason=search%7Corganic",
}

STREET_RE = re.compile(r"((?:ул|бул)\.?\s*[«\"']?\s*[А-Я][а-я]+(?:\s+[А-Яа-я]+){0,3}\s*\d{0,4})")
ZHK_RE = re.compile(r"ж\.?к\.?\s*[«\"']?\s*[А-Я][а-я]+(?:\s+[А-Яа-я0-9]+){0,2}")


def fetch(url):
    parts = url.split("://", 1)
    scheme, rest = parts[0], parts[1]
    host, path = rest.split("/", 1) if "/" in rest else (rest, "")
    safe_path = "/".join(urllib.parse.quote(seg, safe=":?&=%") for seg in path.split("/"))
    req = urllib.request.Request(f"{scheme}://{host}/{safe_path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


for portal, url in URLS.items():
    print(f"\n{'='*70}\n{portal}\n{'='*70}")
    try:
        html = fetch(url)
        text_only = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL)
        text_only = re.sub(r"<style.*?</style>", " ", text_only, flags=re.DOTALL)
        text_only = re.sub(r"<[^>]+>", " ", text_only)
        text_only = re.sub(r"\s+", " ", text_only)
    except Exception as e:
        print(f"FETCH FAILED: {e}")
        continue

    street_matches = STREET_RE.findall(text_only)
    zhk_matches = ZHK_RE.findall(text_only)
    print(f"  street-level address mentions (ул./бул.): {street_matches[:5]}")
    print(f"  district-only mentions (ж.к.): {zhk_matches[:3]}")
