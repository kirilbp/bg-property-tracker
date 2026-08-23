import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URLS = {
    "imot.bg": "https://www.imot.bg/obiava-1b178506444161565-prodava-dvustaen-apartament-grad-sofiya-mladost-4",
    "olx.bg": "https://www.olx.bg/d/ad/predlagam-tsyala-samostoyatelna-sgrada-s-11-apartamenta-CID368-ID9QcUA.html?search_reason=search%7Corganic",
}

PATTERNS = {
    "lat/lng JSON pair": re.compile(
        r'(?:lat(?:itude)?)["\']?\s*[:=]\s*["\']?(4[0-9]\.\d{3,8})["\']?[^}]{0,100}?'
        r'(?:lng|lon(?:gitude)?)["\']?\s*[:=]\s*["\']?(2[0-9]\.\d{3,8})',
        re.IGNORECASE,
    ),
    "data-lat attr": re.compile(r'data-lat[a-z]*=["\']?(-?\d{1,3}\.\d{2,8})', re.IGNORECASE),
    "map iframe src": re.compile(r'<iframe[^>]+src=["\']([^"\']*(?:map|google)[^"\']*)["\']', re.IGNORECASE),
    "google maps href": re.compile(r'maps\.google\.com/\?q=(-?\d{1,3}\.\d{2,8}),(-?\d{1,3}\.\d{2,8})', re.IGNORECASE),
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="bg-BG")
    page = context.new_page()

    for portal, url in URLS.items():
        print(f"\n{'='*70}\n{portal}: {url}\n{'='*70}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            html = page.content()
            print(f"fetched {len(html)} bytes (rendered)")
        except Exception as e:
            print(f"NAVIGATION FAILED: {e}")
            continue

        found_any = False
        for label, pat in PATTERNS.items():
            matches = pat.findall(html)
            if matches:
                print(f"  [{label}] {matches[:3]}")
                found_any = True
        if not found_any:
            print("  NO coordinates found even after JS rendering")

    browser.close()
