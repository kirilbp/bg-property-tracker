import json
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"
UPDATED_TEXT_RE = re.compile(r">((?:Актуализирана|Публикувана)[^<]{0,40})<")
DAYS_AGO_RE = re.compile(r"преди\s+(\d+)\s+д")


def parse_days_ago(html):
    m = UPDATED_TEXT_RE.search(html)
    if not m:
        return None
    text = m.group(1)
    if "днес" in text:
        return 0
    if "вчера" in text:
        return 1
    m2 = DAYS_AGO_RE.search(text)
    return int(m2.group(1)) if m2 else None


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


with open("data/leads_alo.json", encoding="utf-8") as f:
    urls = [l["url"] for l in json.load(f)[:15]]

for url in urls:
    try:
        html = fetch(url)
        days_ago = parse_days_ago(html)
        if days_ago is None:
            print(f"{url[-45:]}: PARSE FAILED (no match)")
        else:
            computed = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date().isoformat()
            print(f"{url[-45:]}: days_ago={days_ago} -> site_updated_at date={computed}")
    except Exception as e:
        print(f"{url[-45:]}: FETCH FAILED {e}")
    time.sleep(1)
