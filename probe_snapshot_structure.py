"""
Diagnostic-only: the Wayback backfill (backfill_wayback_prices.py) has now
failed twice to parse ANY listings out of imot.bg's archived category-page
snapshots, even after fixing the id regex - despite probe_wayback_category.py
proving, via a simple whole-text re.findall(), that real listing IDs (and
real overlap with our tracked data) ARE present in that exact same raw HTML.

The only structural difference: this fetches ONE real snapshot and checks
whether "obiava-" IDs actually live inside real <a href="..."> tags (which
is what BeautifulSoup's `soup.find_all("a", href=True)` requires) or
somewhere else entirely - e.g. inline JSON/JS text, a different attribute,
or content only present after client-side rendering that a plain fetch
never sees. Prints exactly what it finds so the real fix (if any) is
obvious rather than guessed at a third time. Read-only.
"""

import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
SNAPSHOT_URL = "http://web.archive.org/web/20260727190434id_/https://www.imot.bg/obiavi/prodazhbi/grad-sofiya"
ID_RE = re.compile(r"obiava-(\d[a-z0-9]{15,20})")


def main():
    resp = requests.get(SNAPSHOT_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text
    print(f"fetched {len(html)} chars")

    all_matches = list(ID_RE.finditer(html))
    print(f"\ntotal 'obiava-ID' matches anywhere in raw text: {len(all_matches)}")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    all_a_tags = soup.find_all("a")
    a_with_href = soup.find_all("a", href=True)
    print(f"total <a> tags: {len(all_a_tags)}")
    print(f"<a> tags with an href attribute: {len(a_with_href)}")

    a_href_with_id = [a for a in a_with_href if ID_RE.search(a["href"])]
    print(f"<a href> tags whose href contains an obiava ID: {len(a_href_with_id)}")

    # For the first 5 raw text matches, print a window of context to see
    # what kind of markup/text actually surrounds them.
    print("\n--- context around first 5 raw matches ---")
    for m in all_matches[:5]:
        start = max(0, m.start() - 120)
        end = min(len(html), m.end() + 40)
        snippet = re.sub(r"\s+", " ", html[start:end])
        print(f"  ...{snippet}...")

    # Check for common SPA/hydration signals that would explain why the
    # static fetch has IDs in inline data but no real <a href> markup.
    print("\n--- SPA/hydration signals ---")
    for marker in ["__NEXT_DATA__", "__NUXT__", "__INITIAL_STATE__", "window.__", "id=\"app\"", "id=\"root\""]:
        count = html.count(marker)
        if count:
            print(f"  found '{marker}': {count} times")


if __name__ == "__main__":
    main()
