"""
Diagnostic-only: scraper_bcpea.py has been stuck at exactly 36 listings
(one page) since it was first built - confirmed via data/history_bcpea.json
(36 total tracked, ever) and via live run logs showing the bot-challenge
interstitial ("Един момент...") clears for the very first request in a
browser session but then reappears and never clears (waited up to 9s,
every time) for every request after that - page 2 onward, and all 36
detail-page fetches. That's not "genuinely slow to clear sometimes", it's
a 100% failure rate after request 1, which points at fingerprint/pattern
detection escalating after the first request, not raw timing.

Tests several concrete, different candidate fixes against the real site
(this sandbox can't reach it directly) rather than guessing which one to
ship blind:
  A. Control: reproduce the current scraper's exact approach (one shared
     page/context, default Chromium) on page 1 then page 2, to confirm
     the failure still reproduces here.
  B. Stealth: same shared context, but with navigator.webdriver patched
     via an init script and automation-control Chromium flags disabled -
     tests whether this is fingerprint-based bot detection.
  C. Fresh context per request: a brand new browser context (not just a
     new page) for every single navigation, discarding any
     session/cookie-based "this looks automated" state between requests -
     tests whether the escalation is tied to reusing one session.
  D. Slower pacing: same as A, but with a much longer, randomized delay
     before the page-2 request - tests whether it's really just a
     request-rate/timing signal.

Prints which variant(s), if any, actually get past the challenge on page
2. Read-only towards the site (fetches pages, doesn't submit anything),
doesn't touch any data file.
"""

import random
import time

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SEARCH_URL = "https://sales.bcpea.org/properties"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CHALLENGE_TITLE_MARKERS = ("един момент", "just a moment", "checking your browser")
POLL_ATTEMPTS = 8
POLL_INTERVAL_MS = 2000

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['bg-BG', 'bg', 'en-US', 'en'] });
window.chrome = { runtime: {} };
"""


def is_challenge_title(title):
    title = (title or "").lower()
    return any(marker in title for marker in CHALLENGE_TITLE_MARKERS)


def check_page(page, url, label):
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(500)
    title = page.title()
    if not is_challenge_title(title):
        print(f"  [{label}] {url} -> NO challenge on first look (title={title!r})")
        return True
    for attempt in range(POLL_ATTEMPTS):
        page.wait_for_timeout(POLL_INTERVAL_MS)
        title = page.title()
        if not is_challenge_title(title):
            print(f"  [{label}] {url} -> challenge CLEARED after {(attempt + 1) * POLL_INTERVAL_MS / 1000:.0f}s")
            return True
    soup = BeautifulSoup(page.content(), "html.parser")
    body_text = soup.get_text(" ", strip=True)[:150] if soup.body else None
    print(f"  [{label}] {url} -> challenge NEVER cleared after "
          f"{POLL_ATTEMPTS * POLL_INTERVAL_MS / 1000:.0f}s (title={title!r}, body_start={body_text!r})")
    return False


def variant_a_control(browser):
    print("\n=== Variant A: control (shared context, default Chromium, matches current scraper) ===")
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()
    check_page(page, f"{SEARCH_URL}?perpage=36&p=1", "A-page1")
    time.sleep(1)
    check_page(page, f"{SEARCH_URL}?perpage=36&p=2", "A-page2")
    context.close()


def variant_b_stealth(browser):
    print("\n=== Variant B: stealth (navigator.webdriver patched, automation flags hidden) ===")
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    context.add_init_script(STEALTH_INIT_SCRIPT)
    page = context.new_page()
    check_page(page, f"{SEARCH_URL}?perpage=36&p=1", "B-page1")
    time.sleep(1)
    check_page(page, f"{SEARCH_URL}?perpage=36&p=2", "B-page2")
    context.close()


def variant_c_fresh_context(browser):
    print("\n=== Variant C: fresh browser context per request (no shared session/cookies) ===")
    context1 = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page1 = context1.new_page()
    check_page(page1, f"{SEARCH_URL}?perpage=36&p=1", "C-page1")
    context1.close()

    time.sleep(1)
    context2 = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page2 = context2.new_page()
    check_page(page2, f"{SEARCH_URL}?perpage=36&p=2", "C-page2")
    context2.close()


def variant_d_slow_pacing(browser):
    print("\n=== Variant D: shared context, long randomized delay before page 2 ===")
    context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
    page = context.new_page()
    check_page(page, f"{SEARCH_URL}?perpage=36&p=1", "D-page1")
    delay = random.uniform(8, 14)
    print(f"  waiting {delay:.1f}s before page 2...")
    time.sleep(delay)
    check_page(page, f"{SEARCH_URL}?perpage=36&p=2", "D-page2")
    context.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        variant_a_control(browser)
        variant_b_stealth(browser)
        variant_c_fresh_context(browser)
        variant_d_slow_pacing(browser)
        browser.close()


if __name__ == "__main__":
    main()
