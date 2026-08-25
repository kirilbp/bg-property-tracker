"""
Diagnostic-only: checks whether the other portals in this project (besides
homes.bg, which is confirmed to hard-cap pagination at page 49 regardless of
true offersCount - see probe_homes_slicing.py / commit history) have a
similar fixed pagination depth cap.

imoti.net (scraper.py) already has a *confirmed* real cap from prior live
testing, documented in scraper.py's own header: HTTP 403 at page 200 of 396,
regardless of request pacing - not re-tested here, just restated.

For the remaining 5 (alo.bg, imot.bg, olx.bg, bazar.bg, imoti.bg), this
probes real, deep page numbers directly (not sequential crawling) against
each site's current Sofia-only search, spread across and beyond the range
each scraper's own MAX_PAGES currently covers, watching for:
  - a hard block (403/429/challenge page) that isn't just "ran out of
    listings" (empty page with a normal 200)
  - a page number where content stops appearing well short of what the
    site's own UI claims exists

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def count_price_cards(html, max_text_len, max_price_mentions=1):
    soup = BeautifulSoup(html, "html.parser")
    count = 0
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if "€" in text and len(text) < max_text_len and text.count("€") <= max_price_mentions:
            count += 1
    return count


print("=== alo.bg (plain requests) ===")
base = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342"
for page in [1, 50, 100, 150, 200, 250, 300, 330, 340]:
    url = base if page == 1 else f"{base}&page={page}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        n = len(re.findall(r'href="/obiava/', resp.text))
        print(f"  page {page}: status={resp.status_code} len={len(resp.text)} listing-link-matches={n}")
    except requests.RequestException as e:
        print(f"  page {page}: REQUEST FAILED: {e}")
    time.sleep(1)

print("\n=== bazar.bg (plain requests) ===")
base = "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia"
for page in [1, 10, 20, 40, 60, 80, 100, 150]:
    url = base if page == 1 else f"{base}?page={page}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"/obiava/"))
        print(f"  page {page}: status={resp.status_code} len={len(resp.text)} listing-links={len(links)}")
        if page == 1:
            page_links = soup.find_all("a", href=re.compile(r"[?&]page="))
            nums = sorted({int(m.group(1)) for a in page_links if (m := re.search(r"page=(\d+)", a["href"]))})
            print(f"    site's own paginator page numbers seen on page 1: {nums}")
    except requests.RequestException as e:
        print(f"  page {page}: REQUEST FAILED: {e}")
    time.sleep(1)

print("\n=== imot.bg (playwright) ===")
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(user_agent=UA)
    page_obj = context.new_page()
    base = "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya"
    for pnum in [1, 10, 20, 30, 50, 80, 120]:
        url = base if pnum == 1 else f"{base}/p-{pnum}"
        try:
            resp = page_obj.goto(url, wait_until="domcontentloaded", timeout=30000)
            page_obj.wait_for_timeout(1200)
            html = page_obj.content()
            n = len(re.findall(r"€", html))
            status = resp.status if resp else "?"
            print(f"  page {pnum}: http_status={status} html_len={len(html)} euro-sign-count={n}")
        except Exception as e:
            print(f"  page {pnum}: NAV FAILED: {e}")
        time.sleep(1)
    browser.close()

print("\n=== olx.bg (playwright) ===")
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(user_agent=UA)
    page_obj = context.new_page()
    base = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/"
    for pnum in [1, 10, 20, 30, 40, 60, 90]:
        url = base if pnum == 1 else f"{base}?page={pnum}"
        try:
            resp = page_obj.goto(url, wait_until="domcontentloaded", timeout=30000)
            page_obj.wait_for_timeout(1200)
            html = page_obj.content()
            n = len(re.findall(r"€", html))
            status = resp.status if resp else "?"
            print(f"  page {pnum}: http_status={status} html_len={len(html)} euro-sign-count={n}")
        except Exception as e:
            print(f"  page {pnum}: NAV FAILED: {e}")
        time.sleep(1)
    browser.close()

print("\n=== imoti.bg (plain requests) ===")
base = "https://www.imoti.bg/bg/imoti-prodazhbi/grad-sofia"
for page in [1, 50, 100, 300, 600, 1000, 2000]:
    url = base if page == 1 else f"{base}/page:{page}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        n = len(re.findall(r"€", resp.text))
        print(f"  page {page}: status={resp.status_code} len={len(resp.text)} euro-sign-count={n}")
    except requests.RequestException as e:
        print(f"  page {page}: REQUEST FAILED: {e}")
    time.sleep(1)

print("\ndone")
