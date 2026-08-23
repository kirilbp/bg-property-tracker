import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


for label, url in [
    ("Average apartment purchase price (39/124)", "https://www.nsi.bg/statistical-data/39/124"),
    ("Related dataset (39/123)", "https://www.nsi.bg/statistical-data/39/123"),
]:
    print(f"\n{'='*70}\n{label}: {url}\n{'='*70}")
    try:
        html = fetch(url)
        print(f"fetched {len(html)} bytes")
        title_m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        print("title:", title_m.group(1).strip() if title_m else None)
        links = re.findall(r'href="([^"]+\.(?:xlsx|xls|csv))"', html, re.IGNORECASE)
        print("data file links:", links[:10])
        for kw in ["София", "област", "град", "село", "тримесечие", "година", "лв./кв.м", "лв. /кв.м", "2025", "2026"]:
            found = kw in html
            print(f"  contains '{kw}': {found}")
        table_m = re.search(r"<table.*?</table>", html, re.DOTALL)
        if table_m:
            text_only = re.sub(r"<[^>]+>", " ", table_m.group(0))
            text_only = re.sub(r"\s+", " ", text_only).strip()
            print("table text snippet:", text_only[:600])
    except Exception as e:
        print("FETCH FAILED:", e)
