import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


html = fetch("https://www.registryagency.bg/bg/registri/imoten-registar/")
print(f"fetched {len(html)} bytes")

links = re.findall(r'href="([^"]+)"[^>]*>([^<]{0,80}(?:ценоразпис|тарифа|такси)[^<]{0,80})</a>', html, re.IGNORECASE)
print("fee-related links found on main page:", links[:10])

for kw in ["ценоразпис", "тарифа"]:
    for m in re.finditer(re.escape(kw), html, re.IGNORECASE):
        snippet = re.sub(r"\s+", " ", html[max(0, m.start()-150):m.start()+200])
        print(f"  [{kw}] ...{snippet}...")

for label, url in [
    ("Registry Agency tariff page", "https://www.registryagency.bg/bg/registri/imoten-registar/taksi/"),
    ("Portal registryagency prices", "https://portal.registryagency.bg/"),
]:
    print(f"\n{'='*70}\n{label}: {url}\n{'='*70}")
    try:
        h = fetch(url)
        print(f"fetched {len(h)} bytes")
        for m in re.finditer(r"справк\w*", h, re.IGNORECASE):
            snippet = re.sub(r"\s+", " ", h[max(0, m.start()-100):m.start()+200])
            print(f"  ...{snippet}...")
    except Exception as e:
        print("FETCH FAILED:", e)
