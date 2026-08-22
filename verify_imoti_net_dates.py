import json
import re
import time
import urllib.request

UA = "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"
DATE_POSTED_RE = re.compile(r'"datePosted"\s*:\s*"(\d{4}-\d{2}-\d{2})"')


def parse_date_posted(html):
    m = DATE_POSTED_RE.search(html)
    return m.group(1) if m else None


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


with open("data/leads.json", encoding="utf-8") as f:
    urls = [l["url"] for l in json.load(f)[:15]]

for url in urls:
    try:
        html = fetch(url)
        date_posted = parse_date_posted(html)
        print(f"{url[-55:]}: datePosted={date_posted}")
    except Exception as e:
        print(f"{url[-55:]}: FETCH FAILED {e}")
    time.sleep(1)
