import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

URLS = {
    "imoti.net": "https://www.imoti.net/en/obiava/prodava/sofia/lulin-3/dvustaen/6290402/?sid=icNBCK&page=1",
    "alo.bg": "https://www.alo.bg/sobstvenik-prodava-2-staen-apartament-ot-62-42-kv-m-v-gr-sofiya-kv-goce-delchev-11054526",
    "imot.bg": "https://www.imot.bg/obiava-1b178506444161565-prodava-dvustaen-apartament-grad-sofiya-mladost-4",
    "bazar.bg": "https://bazar.bg/obiava-55620361/prodava-2-staen-gr-sofiia-mladost-4",
    "imoti.bg": "https://imoti.bg/продажби/едностаен-апартамент/софия/надежда-3-515750.htm/di:софия/cu:BGN",
}

KEYWORDS = [
    "публикувана", "публикуван", "дата на публикуване", "обявена на", "качена на",
    "качен на", "публикация от", "добавена на", "добавен на", "актуализирана",
    "актуализиран", "обновена на", "обновен на", "дата на обявата", "posted on",
    "listed on", "date added", "publish", "created_at", "createdAt", "publishedAt",
    "published_at", "datePosted", "dateModified", "date_added", "listing_date",
]

for portal, url in URLS.items():
    print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "bg,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        print(f"fetched {len(html)} bytes, status OK")
    except Exception as e:
        print(f"FETCH FAILED: {e}")
        continue

    found_any = False
    for kw in KEYWORDS:
        for m in re.finditer(re.escape(kw), html, re.IGNORECASE):
            start = max(0, m.start() - 80)
            end = min(len(html), m.end() + 120)
            snippet = html[start:end].replace("\n", " ").replace("\r", "")
            snippet = re.sub(r"\s+", " ", snippet)
            print(f"  [{kw}] ...{snippet}...")
            found_any = True
            break

    if not found_any:
        print("  no date-related keywords found")

    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        print("  JSON-LD block found:", m.group(1)[:400].replace("\n", " "))
