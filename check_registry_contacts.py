import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


html = fetch("https://www.registryagency.bg/bg/kontakti/")
print(f"fetched {len(html)} bytes")

emails = sorted(set(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html)))
print("emails found on contacts page:", emails)

phones = sorted(set(re.findall(r"0\d{1,3}[\s/]?\d{3}[\s-]?\d{3,4}", html)))
print("phone-like patterns found:", phones[:15])

for m in re.finditer(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html):
    snippet = re.sub(r"\s+", " ", html[max(0, m.start()-200):m.start()+30])
    snippet = re.sub(r"<[^>]+>", " ", snippet)
    print(f"\ncontext for {m.group(0)}:\n  ...{snippet}...")
