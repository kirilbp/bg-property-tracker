"""
Diagnostic-only: round 8 (final) for imot.bg nationwide. Round 7 resolved
22/29 city slugs; 7 failed (all likely transliteration mismatches, not
real gaps in imot.bg's coverage) - pazardzhik/kardzhali/kazanlak etc. are
real cities imot.bg should have their own page for. Retries those 7 with
alternate transliterations before accepting any as genuinely unavailable.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

from playwright.sync_api import sync_playwright

BASE = "https://www.imot.bg/obiavi/prodazhbi"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LISTING_LINK_RE = re.compile(r"/obiava-(\d[a-z]\d{10,})-")

RETRY_SLUGS = {
    "pazardzhik": ["grad-pazardzhik", "grad-pazardjik-oblast"],
    "asenovgrad": ["grad-asenovgrad-oblast-plovdiv", "asenovgrad"],
    "kazanlak": ["grad-kazanluk", "grad-kazanlak-oblast-stara-zagora"],
    "kardzhali": ["grad-kardzhali", "grad-kirdjali"],
    "dimitrovgrad": ["grad-dimitrovgrad-oblast-haskovo", "dimitrovgrad"],
    "dupnitsa": ["grad-dupnitsa-oblast-kyustendil", "dupnitsa"],
    "svishtov": ["grad-svishtov-oblast-veliko-tarnovo", "svishtov"],
}


def check(page, url):
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        html = page.content()
        n = len(set(LISTING_LINK_RE.findall(html)))
        status = resp.status if resp else "?"
        return status, n, len(html)
    except Exception as e:
        return f"ERROR: {e}", 0, 0


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()

    for key, slugs in RETRY_SLUGS.items():
        print(f"--- {key} ---")
        for slug in slugs:
            url = f"{BASE}/{slug}"
            status, n, length = check(page, url)
            print(f"  {slug}: status={status} listing_links={n} len={length}")
            time.sleep(0.8)

    browser.close()

print("\ndone")
