"""
Diagnostic-only: a production audit found `data/history_bcpea.json`'s
"photos" field at a flat 0% (0/2,246), despite 100% of listings having gone
through fetch_listing_detail()'s photo extraction (extract_photos_bcpea())
unconditionally, and despite that SAME detail-page fetch successfully
extracting "Описание"/district for 64% of those same listings. See
extract_photos_bcpea()'s own 2026-09-25 docstring correction in
scraper_bcpea.py for the full reasoning: the `.head` element inside
`.item__expanded` this function (and the single-photo extraction that
predates it, present since this scraper's very first commit) has always
assumed - called "already-proven"/"already-confirmed-real" on the strength
of "two real saved HTML pages the user provided" back when this scraper was
first built - can no longer be verified from anything preserved in this
repo's history, and the flat, unmoved "photo" coverage rate (43.6% before
this function ever existed, 43.4% today after 100% of listings went through
it) is itself evidence against that claim ever having been true.

This fetches a handful of REAL bcpea listing detail pages (ids taken
straight from the currently committed data/history_bcpea.json - two whose
"photo" is already set from the grid crawl, two whose "photo" is null even
though detail_checked is true) and dumps, for each one:
  - whether `.item__expanded` is found at all (should be true for all four -
    "Описание"/district already extract successfully on these exact pages)
  - every <img> tag found ANYWHERE on the page (src, class, and whether it
    falls inside `.item__expanded`) - specifically to answer: does a real,
    non-placeholder photo exist on this page at all, and if so, is it
    actually nested inside `.item__expanded`, or is it a sibling section
    (e.g. a top-of-page gallery above an "expanded details" accordion)?
  - the exact class list of `.item__expanded`'s own parent chain, in case
    `.head` turns out to be a few levels up rather than a sibling

Read-only, doesn't touch any data file or the committed scraper. Delete
once the question is answered (same lifecycle as this repo's other
probe_*.py scripts - see probe_alo_photos.py's own history for the
pattern, though that one has since been removed after its own question was
answered).

NOT dispatched by the session that wrote this - see CLAUDE.md's standing
rule against iterating via live workflow_dispatch. This is meant to be run
ONCE, either by a human with their own access to sales.bcpea.org, or by a
future session that genuinely has live network access, and its output
pasted back for a real (evidence-based, not guessed) fix to
extract_photos_bcpea()'s search scope.
"""

import time

from playwright.sync_api import sync_playwright

BASE_URL = "https://sales.bcpea.org"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Real listing URLs pulled straight from the currently committed
# data/history_bcpea.json.
CASES = [
    ("has grid photo", "https://sales.bcpea.org/properties/91569"),
    ("has grid photo", "https://sales.bcpea.org/properties/91550"),
    ("no photo at all yet", "https://sales.bcpea.org/properties/91568"),
    ("no photo at all yet", "https://sales.bcpea.org/properties/91567"),
]

CHALLENGE_TITLE_MARKERS = ("един момент", "just a moment", "checking your browser")
CHALLENGE_POLL_ATTEMPTS = 6
CHALLENGE_POLL_INTERVAL_MS = 1500


def is_challenge_title(title):
    title = (title or "").lower()
    return any(marker in title for marker in CHALLENGE_TITLE_MARKERS)


def fetch_html(browser, url):
    # Same bot-challenge handling as scraper_bcpea.py's own fetch_html() -
    # a fresh context per request, wait out the self-clearing Cloudflare-
    # style JS challenge rather than giving up after one attempt.
    context = browser.new_context(user_agent=USER_AGENT)
    page = context.new_page()
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        for _ in range(CHALLENGE_POLL_ATTEMPTS):
            if not is_challenge_title(page.title()):
                break
            page.wait_for_timeout(CHALLENGE_POLL_INTERVAL_MS)
        html = page.content()
    finally:
        context.close()
    return html


def inspect(browser, label, url):
    from bs4 import BeautifulSoup

    print(f"\n=== [{label}] {url} ===")
    try:
        html = fetch_html(browser, url)
    except Exception as e:
        print(f"  FETCH FAILED: {e}")
        return

    soup = BeautifulSoup(html, "html.parser")
    if is_challenge_title(soup.title.get_text(strip=True) if soup.title else None):
        print("  STILL A BOT CHALLENGE PAGE after polling - real markup not reached")
        return

    expanded = soup.find(class_="item__expanded")
    print(f"  .item__expanded found: {expanded is not None}")

    all_imgs = soup.find_all("img")
    expanded_img_ids = {id(t) for t in (expanded.find_all("img") if expanded is not None else [])}
    print(f"  total <img> tags on page: {len(all_imgs)}")
    for img in all_imgs:
        inside = id(img) in expanded_img_ids
        print(f"    src={img.get('src')!r} class={img.get('class')} inside_expanded={inside}")

    head = soup.find(class_="head")
    print(f"  a .head element exists ANYWHERE on the page: {head is not None}")
    if head is not None and expanded is not None:
        is_inside = head in expanded.find_all(True)
        print(f"  that .head element is inside .item__expanded: {is_inside}")
        if not is_inside:
            # Walk expanded's own ancestor chain to see how many levels up
            # a shared wrapper (if any) sits relative to .head.
            ancestor_classes = []
            node = expanded.parent
            depth = 0
            while node is not None and depth < 6:
                ancestor_classes.append((depth, node.get("class")))
                node = node.parent
                depth += 1
            print(f"  .item__expanded's own ancestor class chain (up to 6 levels): {ancestor_classes}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label, url in CASES:
            inspect(browser, label, url)
            time.sleep(1.0)
        browser.close()


if __name__ == "__main__":
    main()
