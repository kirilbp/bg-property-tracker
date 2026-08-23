import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


candidates = [
    ("imoti.bg - Оценка на имот", "https://imoti.bg/otsenka-na-imot"),
    ("homes.bg valuation", "https://www.homes.bg/otsenka-na-imot"),
    ("data.egov.bg dataset search - property registry", "https://data.egov.bg/organisation/dataset?q=%D0%B8%D0%BC%D0%BE%D1%82%D0%B5%D0%BD"),
    ("data.egov.bg dataset search - notarial deeds", "https://data.egov.bg/organisation/dataset?q=%D0%BD%D0%BE%D1%82%D0%B0%D1%80%D0%B8%D0%B0%D0%BB%D0%BD%D0%B8"),
]

for name, url in candidates:
    print(f"\n{'='*70}\n{name}: {url}\n{'='*70}")
    try:
        html = fetch(url)
        print(f"fetched {len(html)} bytes, status OK")
        for kw in ["API", "отворени данни", "нотариал", "продажна цена", "регистър", "bulk", "справк", "dataset", "няма резултати"]:
            found = kw.lower() in html.lower()
            if found:
                print(f"  contains '{kw}': True")
        title_m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        print("title:", title_m.group(1).strip()[:150] if title_m else None)
    except Exception as e:
        print(f"FETCH FAILED: {e}")
