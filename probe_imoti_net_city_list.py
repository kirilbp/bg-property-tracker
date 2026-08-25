"""
Diagnostic-only: round 2 for the imoti.net nationwide conversion. Round 1
confirmed the page-200 block is per-query (good - slicing will work) and
that there's no single "drop the filter" nationwide URL like homes.bg had -
/en/obiavi/r/prodava/<city-slug> requires a real city slug, and guesses for
"no segment"/"bulgaria"/bare query all 404. This looks for the real,
complete list of region/city slugs directly in the site's own location
filter widget (same approach used to find homes.bg's real URL mechanism -
read what the site itself actually offers, don't guess), so the scraper
can enumerate real slugs instead of guessing transliterations for all 28
administrative regions/settlements and silently missing whatever guesses
are wrong.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}

print("=== Looking for a location-filter widget on the Sofia search page ===")
resp = requests.get("https://www.imoti.net/en/obiavi/r/prodava/sofia", headers=HEADERS, timeout=20)
html = resp.text
print(f"status={resp.status_code} len={len(html)}")

# Any link matching the same URL shape used for city-scoped search
region_links = sorted(set(re.findall(r'href="(/en/obiavi/r/prodava/[a-z0-9\-]+)"', html)))
print(f"region/city-scoped links found on page: {len(region_links)}")
for l in region_links[:60]:
    print(" ", l)

# Look for a <select>/data attribute holding location options (id/name/slug)
select_blocks = re.findall(r'<select[^>]*id="[^"]*[Rr]egion[^"]*"[^>]*>(.*?)</select>', html, re.DOTALL)
print(f"\nregion <select> blocks found: {len(select_blocks)}")
for block in select_blocks[:1]:
    options = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', block)
    print(f"  options in first select: {len(options)}")
    for val, label in options[:60]:
        print(f"    {val!r} -> {label!r}")

print("\n=== Try robots.txt / sitemap for a region index ===")
for path in ["/robots.txt", "/sitemap.xml", "/en/sitemap.xml"]:
    try:
        r = requests.get(f"https://www.imoti.net{path}", headers=HEADERS, timeout=15)
        print(f"  {path}: status={r.status_code} len={len(r.text)}")
        if r.status_code == 200 and "sitemap" in path:
            print("   ", r.text[:500])
    except requests.RequestException as e:
        print(f"  {path}: FAILED {e}")
    time.sleep(0.5)

print("\ndone")
