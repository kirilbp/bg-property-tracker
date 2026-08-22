import re
import json
from collections import Counter
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}

session = requests.Session()
values = Counter()
samples = {}

for page in range(1, 15):
    url = "https://www.homes.bg/" + ("" if page == 1 else f"?page={page}")
    r = session.get(url, headers=HEADERS, timeout=20)
    m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", r.text, re.DOTALL)
    if not m:
        break
    state = json.loads(m.group(1))
    offers = state.get("data", {}).get("offers", {})
    results = offers.get("result", [])
    for offer in results:
        t = offer.get("time")
        values[t] += 1
        if t not in samples:
            samples[t] = offer.get("id")
    if not offers.get("hasMoreItems"):
        break

print("distinct 'time' values across", sum(values.values()), "offers:")
for v, count in values.most_common(30):
    print(f"  {v!r}: {count} (e.g. offer id {samples[v]})")
