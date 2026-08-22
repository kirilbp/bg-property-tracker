import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


print("=" * 70)
print("imoti.bg (retry with encoded URL)")
print("=" * 70)
imoti_bg_url = "https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/di:софия/cu:BGN"
parts = imoti_bg_url.split("://", 1)
scheme, rest = parts[0], parts[1]
host, path = rest.split("/", 1)
encoded_path = "/".join(urllib.parse.quote(seg, safe=":") for seg in path.split("/"))
safe_url = f"{scheme}://{host}/{encoded_path}"
print("encoded url:", safe_url)
try:
    html = fetch(safe_url)
    print(f"fetched {len(html)} bytes")
    for kw in ["публикувана", "публикуван", "дата на публикуване", "обявена на", "качена на",
               "актуализирана", "актуализиран", "datePosted", "createdAt", "published_at"]:
        for m in re.finditer(re.escape(kw), html, re.IGNORECASE):
            start = max(0, m.start() - 80)
            end = min(len(html), m.end() + 120)
            snippet = re.sub(r"\s+", " ", html[start:end].replace("\n", " "))
            print(f"  [{kw}] ...{snippet}...")
            break
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        print("  JSON-LD:", m.group(1)[:400].replace("\n", " "))
except Exception as e:
    print("FETCH FAILED:", e)

with open("data/leads_alo.json", encoding="utf-8") as f:
    alo_urls = [l["url"] for l in json.load(f)[:12]]
with open("data/leads_bazar.json", encoding="utf-8") as f:
    bazar_urls = [l["url"] for l in json.load(f)[:12]]

print("\n" + "=" * 70)
print("alo.bg: sampling 12 individual listings for date variation")
print("=" * 70)
for url in alo_urls:
    try:
        html = fetch(url)
        m = re.search(r'<span>(Актуализирана[^<]*|Публикувана[^<]*)</span>', html)
        print(f"  {url[-50:]}: {m.group(1) if m else 'NO MATCH'}")
    except Exception as e:
        print(f"  {url[-50:]}: FETCH FAILED {e}")

print("\n" + "=" * 70)
print("bazar.bg: sampling 12 individual listings for date variation")
print("=" * 70)
for url in bazar_urls:
    try:
        html = fetch(url)
        m = re.search(r'<span class="adDate">\s*([^<]*)</span>', html)
        print(f"  {url[-50:]}: {m.group(1).strip() if m else 'NO MATCH'}")
    except Exception as e:
        print(f"  {url[-50:]}: FETCH FAILED {e}")
