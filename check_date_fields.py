import re
import json
import requests
from playwright.sync_api import sync_playwright

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}

# homes.bg: inspect one real offer object for date-ish fields
r = requests.get("https://www.homes.bg/", headers=HEADERS, timeout=20)
m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", r.text, re.DOTALL)
state = json.loads(m.group(1))
offers = state.get("data", {}).get("offers", {}).get("result", [])
if offers:
    print("=== homes.bg: keys of one offer object ===")
    print(sorted(offers[0].keys()))
    for k, v in offers[0].items():
        if isinstance(v, (str, int)) and ("date" in k.lower() or "time" in k.lower() or "created" in k.lower() or "updated" in k.lower() or "publish" in k.lower()):
            print(f"  DATE-ISH: {k} = {v}")
print()

# olx.bg: get real raw text samples around "Обновено"/Днес/Вчера
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()
    page.goto("https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    html = page.content()
    print("=== olx.bg: raw date-line samples ===")
    matches = re.findall(r'гр\.\s*София,\s*[^<]{0,60}?(?:Обновено на[^<]{0,20}|Днес[^<]{0,20}|Вчера[^<]{0,20})', html)
    for mm in matches[:15]:
        print("  ", repr(mm))
    browser.close()
