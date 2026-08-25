"""
Fast, bounded, page-1-only listing-count probe across the 4 per-city/
per-oblast-sliced portals (bazar.bg, imoti.net, imot.bg, olx.bg), for
every city each portal's CITY_SLUGS/OBLAST_SLUGS list covers.

Purpose: answer "is a suspiciously low per-city count on the live site
real market scarcity or a real coverage/matching bug" WITHOUT waiting on
the full multi-hour production scrape.yml/scrape-large.yml run - this
only fetches page 1 of each city's already-verified search URL (the same
URLs each nationwide scraper itself queries), reusing each scraper
module's own page-1 parsing function directly so the counts reflect
exactly what the real scraper would find, just without paginating deeper.
A real per-city total can be higher than this page-1 count (results
continue past page 1), so this is a floor, not an exact total - but a
near-zero page-1 count for a city where the live site clearly shows many
listings (checked separately, manually) would indicate a real bug, not
just "count trails off deeper in pagination."

Read-only: no commits, no history/leads writes - printed to job logs only.
"""

import scraper_bazar as sbazar
import scraper as simoti_net
import scraper_imot as simot
import scraper_olx as solx
from geo_utils import Geocoder
from playwright.sync_api import sync_playwright


def main():
    results = {}

    print("=== bazar.bg (plain requests) ===", flush=True)
    for city_display, slug in sbazar.CITY_SLUGS:
        url = f"{sbazar.SEARCH_BASE}/{slug}"
        page_listings = sbazar.fetch_listings_page(url, city_display)
        count = len(page_listings) if page_listings else 0
        results.setdefault(city_display, {})["bazar.bg"] = count
        print(f"bazar.bg {city_display}: {count}", flush=True)

    print("=== imoti.net (plain requests) ===", flush=True)
    for slug, city_display in simoti_net.CITY_SLUGS:
        url = f"{simoti_net.BASE_URL}/{slug}"
        seen = {}
        count = simoti_net.fetch_listings_page(url, seen, city_display)
        results.setdefault(city_display, {})["imoti.net"] = count or 0
        print(f"imoti.net {city_display}: {count}", flush=True)

    geocoder = Geocoder()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(user_agent=simot.USER_AGENT)
        page = context.new_page()

        print("=== imot.bg (playwright) ===", flush=True)
        for city_display, slug in simot.CITY_SLUGS:
            url = f"{simot.SEARCH_BASE}/{slug}"
            html = simot.goto_with_retries(page, url)
            seen = {}
            count = simot.parse_listings_page(html, seen, geocoder, city_display) if html else 0
            results.setdefault(city_display, {})["imot.bg"] = count or 0
            print(f"imot.bg {city_display}: {count}", flush=True)

        print("=== olx.bg (playwright, per-oblast) ===", flush=True)
        for oblast_display, slug in solx.OBLAST_SLUGS:
            url = f"{solx.SEARCH_BASE}/{slug}"
            seen = {}
            count = solx.fetch_listings_page(page, url, seen, geocoder, oblast_display)
            results.setdefault(oblast_display, {})["olx.bg(oblast)"] = count or 0
            print(f"olx.bg {oblast_display}: {count}", flush=True)

        browser.close()

    print("\n=== SUMMARY: page-1 listing counts per city per portal ===", flush=True)
    for city in sorted(results):
        row = results[city]
        total = sum(row.values())
        print(f"{city}: total={total} " + ", ".join(f"{k}={v}" for k, v in row.items()), flush=True)


if __name__ == "__main__":
    main()
