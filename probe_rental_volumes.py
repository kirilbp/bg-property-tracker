"""
Follow-up to probe_rental_sections.py (throwaway diagnostic, backlog: rental-
portal volume investigation). The plain-HTTP probe found real rental-section
links on 4 portals but couldn't read a single listing count off any of them -
these portals render their result counts client-side with JS, which a bare
`requests.get()` never executes, and separately got hard-blocked (403) trying
olx.bg's homepage at all. This uses a real headless Chromium (via Playwright,
same browser the 8 scrapers already drive) to load each candidate URL,
wait for the page to settle, and grab whatever visible text mentions a
count - answering the "rough volume" half of the original ask that the
static-HTML pass couldn't.

Also re-checks homes.bg (no link found in raw HTML - possibly a JS-rendered
nav) and olx.bg (blocked over plain HTTP - a real browser's headers/TLS
fingerprint may fare better) directly with a real browser rather than
accepting the earlier inconclusive result.

Best-effort text scraping only, same as the plain-HTTP pass - this is
throwaway diagnostic code to inform a decision, not production scraping.
"""

import re

from playwright.sync_api import sync_playwright

TIMEOUT_MS = 30000

# (portal, url, is_homepage) - homepage entries also look for a rental nav
# link since the static pass found none there.
TARGETS = [
    ("imoti.net", "https://www.imoti.net/en/obiavi/r/dava-pod-naem/bulgaria/?sid=jmJlvG", False),
    ("bazar.bg", "https://bazar.bg/obiavi/stai-pod-naem", False),
    ("imot.bg", "https://www.imot.bg/naemi", False),
    ("imoti.bg", "https://imoti.bg/наеми", False),
    ("homes.bg", "https://www.homes.bg/", True),
    ("olx.bg", "https://www.olx.bg/", True),
]

RENTAL_LINK_RE = re.compile(r"под\s*наем|наем|pod[\s-]?naem|naem", re.IGNORECASE)
COUNT_RE = re.compile(
    r"(\d[\d\s ]{0,9})\s*(обяви|imoti|listings|results|резултат[аи]?)",
    re.IGNORECASE,
)


def guess_counts(text):
    return [(m.group(0).strip()) for m in COUNT_RE.finditer(text)][:5]


def find_rental_nav_text(page):
    links = page.eval_on_selector_all(
        "a", "els => els.map(e => ({text: e.textContent || '', href: e.href || ''}))"
    )
    matches = [l for l in links if RENTAL_LINK_RE.search(l["text"]) or RENTAL_LINK_RE.search(l["href"])]
    return matches[:5]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0 (compatible; PersonalDealTracker/1.0)")

        for portal, url, is_homepage in TARGETS:
            print(f"\n=== {portal} ===  ({url})")
            try:
                page.goto(url, timeout=TIMEOUT_MS, wait_until="networkidle")
            except Exception as e:
                print(f"  ERROR loading page: {e}")
                continue

            if is_homepage:
                nav_matches = find_rental_nav_text(page)
                if nav_matches:
                    print(f"  Rental nav link(s) found via real browser: {nav_matches}")
                else:
                    print("  Still no rental nav link found, even JS-rendered.")

            body_text = page.inner_text("body")
            counts = guess_counts(body_text)
            if counts:
                print(f"  Count-like text found: {counts}")
            else:
                print("  No count-like text found on this page.")

        browser.close()


if __name__ == "__main__":
    main()
