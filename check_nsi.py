import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


raw_url = "https://www.nsi.bg/bg/content/2977/индекс-на-цените-на-жилищата"
parts = raw_url.split("://", 1)
scheme, rest = parts[0], parts[1]
host, path = rest.split("/", 1)
safe_url = f"{scheme}://{host}/" + "/".join(urllib.parse.quote(seg, safe=":") for seg in path.split("/"))
print("encoded:", safe_url)

try:
    html = fetch(safe_url)
    print(f"fetched {len(html)} bytes")
    for kw in ["индекс на цените", "продаж", "открити данни", "excel", "xlsx", "csv", "тримесеч", "средна цена"]:
        idxs = [m.start() for m in re.finditer(re.escape(kw), html, re.IGNORECASE)][:2]
        for i in idxs:
            snippet = re.sub(r"\s+", " ", html[max(0, i - 80):i + 150])
            print(f"  [{kw}] ...{snippet}...")
    links = re.findall(r'href="([^"]+\.(?:xlsx|xls|csv))"', html, re.IGNORECASE)
    print("data file links found:", links[:10])
except Exception as e:
    print("FETCH FAILED:", e)


def encode_url(u):
    p = u.split("://", 1)
    h, pth = p[1].split("/", 1)
    return f"{p[0]}://{h}/" + "/".join(urllib.parse.quote(s, safe=":") for s in pth.split("/"))


try:
    html2 = fetch(encode_url("https://www.nsi.bg/bg/content/6413/отворени-данни"))
except Exception as e:
    html2 = None
    print("open data portal FETCH FAILED:", e)
if html2:
    print(f"\nopen data portal page fetched: {len(html2)} bytes")
