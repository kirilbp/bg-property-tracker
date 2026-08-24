"""
Diagnostic-only, round 2: the first attempt (nationwide_check.py/_pw.py,
removed in 96d777d/965546b/bbb799a) had a wrong imoti.net URL (404), and
its regex-based total-count extraction for bazar.bg/olx.bg/homes.bg
produced numbers that don't reconcile with what's actually tracked today
(bazar.bg matched "97110 обяви" - a 38x jump from the current 2,559
Sofia-only count, versus alo.bg's clean 8x; olx.bg matched a suspicious
flat "1000"; homes.bg's 12,333 offersCount came back from a request that,
per the scraper's own docstring, should already be Sofia-scoped by
default, yet is 8x the currently-tracked 1,476). None of those numbers
should be trusted without cross-checking against a second signal.

This round tries several things per portal: (a) the correct nationwide URL
derived from removing each scraper's own city-scoping URL segment/params,
with status codes for any candidate that might 404, (b) more than one
signal for the total count where possible (a text match AND last-page-
number * per-page-count, so a single regex false-positive doesn't stand
alone), and (c) a sample nationwide (non-Sofia) listing's own page dumped
for description/address/category signals, to check what's actually
available to scrape for the fields the nationwide expansion needs beyond
what today's Sofia-only scrapers already capture.

Read-only, no commit step - deleted once the question is answered.
"""

import json
import re

from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

COUNT_RE = re.compile(
    r"([\d][\d\s,\.]{1,9})\s*(обяви|резултат|imota|imoti|listings|results)",
    re.IGNORECASE,
)


def dump_counts(html, label):
    seen = set()
    for m in COUNT_RE.finditer(html):
        snippet = m.group(0).strip()
        if snippet not in seen:
            seen.add(snippet)
            print(f"  [{label}] count-like match: {snippet!r}")
    if not seen:
        print(f"  [{label}] no count-like text found")


def dump_listing_signal(html, label):
    checks = {
        "has 'описание' (description label)": "описание" in html.lower(),
        "has 'адрес' (address label)": "адрес" in html.lower(),
        "has schema.org JSON-LD": "application/ld+json" in html,
        "has meta description": '"description"' in html or "og:description" in html,
    }
    for k, v in checks.items():
        print(f"  [{label}] {k}: {v}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()

        # --- imoti.net: current Sofia URL is .../en/obiavi/r/prodava/sofia,
        # round 1 tried removing just "/sofia" and got a 404. Try several
        # plausible nationwide variants.
        print("\n=== imoti.net: candidate nationwide URLs ===")
        for url in [
            "https://www.imoti.net/en/obiavi/r/prodava",
            "https://www.imoti.net/en/obiavi/r/prodava/",
            "https://www.imoti.net/bg/obiavi/r/prodava",
            "https://www.imoti.net/en/obiavi/prodava",
            "https://www.imoti.net/en/",
        ]:
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                print(f"  {url} -> status={resp.status if resp else '?'} title={page.title()!r}")
            except Exception as e:
                print(f"  {url} -> FAILED: {e}")

        # --- alo.bg: round 1's nationwide URL (removing region_id/location_ids)
        # returned a clean, consistent 81,147 three times - re-confirm once more
        # and grab a nationwide (non-Sofia) listing's own page.
        print("\n=== alo.bg: nationwide count + sample listing ===")
        url = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        dump_counts(page.content(), "alo.bg listing page")
        links = page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.href).filter(h => /-\\d{6,9}$/.test(h))"
        )
        non_sofia = [l for l in links if "sofia" not in l.lower()][:1] or links[:1]
        if non_sofia:
            page.goto(non_sofia[0], wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(500)
            dump_listing_signal(page.content(), "alo.bg sample listing " + non_sofia[0])

        # --- homes.bg: default homepage is documented as Sofia-scoped, but
        # round 1's offersCount (12,333) is 8x the currently-tracked 1,476 -
        # dump the full searchCriteria to see what's actually being applied,
        # and look for a real "all Bulgaria" filter link/param in the state.
        print("\n=== homes.bg: searchCriteria + offersCount ===")
        page.goto("https://www.homes.bg/", wait_until="domcontentloaded", timeout=30000)
        html = page.content()
        m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", html, re.DOTALL)
        if m:
            state = json.loads(m.group(1))
            offers = state.get("data", {}).get("offers", {})
            print("  searchCriteria:", json.dumps(offers.get("searchCriteria"), ensure_ascii=False))
            print("  offersCount:", offers.get("offersCount"))
            print("  actual result array length:", len(offers.get("result", [])))
            first = (offers.get("result") or [{}])[0]
            print("  first offer keys:", list(first.keys()))
            print("  first offer location-ish fields:", {
                k: v for k, v in first.items()
                if isinstance(v, str) and any(w in k.lower() for w in ("area", "location", "city", "address", "region"))
            })

        # --- imot.bg: current Sofia URL is .../obiavi/prodazhbi/grad-sofiya,
        # nationwide should be .../obiavi/prodazhbi - find the real results
        # count element/text and a nationwide sample listing.
        print("\n=== imot.bg: nationwide count + sample listing ===")
        page.goto("https://www.imot.bg/obiavi/prodazhbi", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        html = page.content()
        dump_counts(html, "imot.bg listing page")
        # imot.bg shows a page-count style paginator - try to read the last page number.
        last_page_texts = page.eval_on_selector_all(
            "a, span", "els => els.map(e => e.textContent.trim()).filter(t => /^\\d{1,4}$/.test(t))"
        )
        print("  numeric pagination-looking texts (last few):", last_page_texts[-10:])

        # --- olx.bg: current Sofia URL segment is oblast-sofiya-grad/,
        # nationwide removes it - round 1's "1000" match looked spurious.
        print("\n=== olx.bg: nationwide count + sample listing ===")
        page.goto("https://www.olx.bg/nedvizhimi-imoti/prodazhbi/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        html = page.content()
        dump_counts(html, "olx.bg listing page")
        ld_json = page.eval_on_selector_all(
            "script[type='application/ld+json']", "els => els.map(e => e.textContent.slice(0, 500))"
        )
        print("  JSON-LD blocks found:", len(ld_json))
        for block in ld_json[:2]:
            print("   ", block[:300])

        # --- bazar.bg: current Sofia URL is .../prodazhba-apartamenti/sofia,
        # nationwide removes /sofia - cross-check the 97,110 match against
        # last-page-number * per-page-count as a second signal.
        print("\n=== bazar.bg: nationwide count (cross-checked) ===")
        page.goto("https://bazar.bg/obiavi/prodazhba-apartamenti", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        html = page.content()
        dump_counts(html, "bazar.bg listing page")
        page_links = page.eval_on_selector_all(
            "a[href*='page=']", "els => els.map(e => e.href)"
        )
        page_nums = sorted(set(int(m.group(1)) for l in page_links if (m := re.search(r"page=(\d+)", l))))
        print("  page= numbers seen in pagination links:", page_nums[-10:] if page_nums else "none")
        cards = page.eval_on_selector_all("[class*='listing'], [class*='item']", "els => els.length")
        print("  elements matching [class*=listing]/[class*=item] on page 1:", cards)

        # --- imoti.bg: current Sofia URL is .../продажби/di:софия/cu:BGN,
        # nationwide removes the di: segment - round 1's requests-based fetch
        # found nothing (likely needs real JS rendering).
        print("\n=== imoti.bg: nationwide count + sample listing ===")
        page.goto("https://imoti.bg/продажби/cu:BGN", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        html = page.content()
        dump_counts(html, "imoti.bg listing page")

        browser.close()


if __name__ == "__main__":
    main()
