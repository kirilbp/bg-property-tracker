"""
One-off diagnostic (backlog: rental-portal volume investigation, run once
via probe-rental-sections.yml on GitHub's own network - this sandbox has
no route to any of these hosts). Answers, for each of the 7 non-auction
portals, two questions before any rental scraper gets built: does it have
a real, distinct "for rent" section at all, and roughly how many listings
does it show.

Deliberately doesn't guess a rental URL from each sale-search URL's own
pattern (e.g. assuming "prodazhbi" -> "naemi") - instead fetches each
portal's own homepage and follows whatever link IT presents as its rental
section, since a wrong guess here would misreport a portal as having no
rentals when the real URL just used a different word. sales.bcpea.org is
excluded outright: it lists court-ordered forced-sale auctions, not
anything a landlord would list for rent.

Best-effort listing-count extraction only (regmatches specific patterns);
"found a link, page has more listings shown than empty-state text pending
verification manually" is expected and fine for some portals.
"""

import re
import sys

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
TIMEOUT = 20

PORTALS = {
    "imoti.net": "https://www.imoti.net/en/",
    "alo.bg": "https://www.alo.bg/",
    "bazar.bg": "https://bazar.bg/",
    "homes.bg": "https://www.homes.bg/",
    "imot.bg": "https://www.imot.bg/",
    "imoti.bg": "https://imoti.bg/",
    "olx.bg": "https://www.olx.bg/",
}

# Case-insensitive; matches both Latin-transliterated and Cyrillic forms
# ("naem"/"наем" = "rent"; "pod naem"/"под наем" = "for rent").
RENTAL_LINK_RE = re.compile(
    r'href="([^"]+)"[^>]*>[^<]{0,80}(?:под\s*наем|наем|pod[\s-]?naem|naem)',
    re.IGNORECASE,
)
# Fallback: href itself contains the keyword, regardless of link text
# (covers portals whose link text is an icon/image with no visible words).
RENTAL_HREF_RE = re.compile(r'href="([^"]*(?:naem|наем)[^"]*)"', re.IGNORECASE)

COUNT_RE = re.compile(
    r'([\d\s ]{1,3}(?:[\s ][\d]{3})*)\s*(?:обяви|imoti|listings|results|резултат)',
    re.IGNORECASE,
)


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def find_rental_link(html, base_url):
    m = RENTAL_LINK_RE.search(html)
    if not m:
        m = RENTAL_HREF_RE.search(html)
    if not m:
        return None
    href = m.group(1)
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{href}"
    return base_url.rstrip("/") + "/" + href


def guess_count(html):
    matches = COUNT_RE.findall(html)
    if not matches:
        return None
    # Take the largest plausible number found - a nav badge/footer count is
    # more likely the real total than a smaller incidental number elsewhere
    # on the page (pagination "page 3", etc.).
    nums = []
    for m in matches:
        digits = re.sub(r"[\s ]", "", m)
        if digits.isdigit():
            nums.append(int(digits))
    return max(nums) if nums else None


def main():
    results = {}
    for portal, homepage in PORTALS.items():
        print(f"\n=== {portal} ===")
        try:
            html = fetch(homepage)
        except requests.RequestException as e:
            print(f"  ERROR fetching homepage: {e}")
            results[portal] = {"error": str(e)}
            continue

        rental_url = find_rental_link(html, homepage)
        if not rental_url:
            print("  No rental link found on homepage (may genuinely not have one, "
                  "may be JS-rendered nav this plain-HTTP fetch can't see, or may use "
                  "wording this regex doesn't catch - needs manual confirmation).")
            results[portal] = {"rental_url": None}
            continue

        print(f"  Rental link found: {rental_url}")
        try:
            rental_html = fetch(rental_url)
        except requests.RequestException as e:
            print(f"  ERROR fetching rental page: {e}")
            results[portal] = {"rental_url": rental_url, "error": str(e)}
            continue

        count = guess_count(rental_html)
        print(f"  Best-effort listing count guess: {count if count is not None else 'could not extract - needs manual check'}")
        results[portal] = {"rental_url": rental_url, "guessed_count": count}

    print("\n\n=== SUMMARY ===")
    for portal, r in results.items():
        if "error" in r:
            print(f"{portal:12s} ERROR: {r['error']}")
        elif r.get("rental_url") is None:
            print(f"{portal:12s} NO RENTAL LINK FOUND")
        else:
            print(f"{portal:12s} {r['rental_url']}  guessed_count={r.get('guessed_count')}")


if __name__ == "__main__":
    main()
