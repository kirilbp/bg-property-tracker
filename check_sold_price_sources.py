import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def report(name, url):
    print(f"\n{'='*70}\n{name}: {url}\n{'='*70}")
    try:
        html = fetch(url)
        print(f"fetched {len(html)} bytes, status OK")
        return html
    except Exception as e:
        print(f"FETCH FAILED: {e}")
        return None


html = report("Registry Agency (Имотен регистър)", "https://www.registryagency.bg/bg/registri/imoten-registar/")
if html:
    for kw in ["безплатно", "такса", "API", "отворени данни", "цена на справка", "лв."]:
        idxs = [m.start() for m in re.finditer(re.escape(kw), html, re.IGNORECASE)][:2]
        for i in idxs:
            snippet = re.sub(r"\s+", " ", html[max(0,i-100):i+150])
            print(f"  [{kw}] ...{snippet}...")

html = report("NSI - Housing price statistics", "https://www.nsi.bg/bg/content/2977/индекс-на-цените-на-жилищата")
if html:
    for kw in ["индекс на цените", "продаж", "открити данни", "excel", "xlsx", "csv"]:
        idxs = [m.start() for m in re.finditer(re.escape(kw), html, re.IGNORECASE)][:2]
        for i in idxs:
            snippet = re.sub(r"\s+", " ", html[max(0,i-80):i+150])
            print(f"  [{kw}] ...{snippet}...")

for name, url, kw_list in [
    ("imoti.net", "https://www.imoti.net/en/obiavi/r/prodava/sofia", ["sold", "archive"]),
    ("homes.bg", "https://www.homes.bg", ["продаден", "архив"]),
    ("imot.bg", "https://www.imot.bg", ["продаден", "архив"]),
]:
    html = report(f"{name} homepage (checking for sold/archive links)", url)
    if html:
        for kw in kw_list:
            found = kw.lower() in html.lower()
            print(f"  contains '{kw}': {found}")
