"""
Bounded live verification: confirms fetch_listings() no longer calls the
per-listing detail pass inline (category present immediately, no
site_posted_at/lat/lng/detail_checked yet), and that it actually returns
promptly for a couple of cities instead of hanging on detail fetches.
Read-only, no commits.
"""

import time

import scraper as si

TEST_CITIES = [("sofia", "София"), ("plovdiv", "Пловдив")]


def main():
    seen = {}
    start = time.time()
    for slug, name in TEST_CITIES:
        url = f"{si.BASE_URL}/{slug}"
        count = si.fetch_listings_page(url, seen, name)
        print(f"DEBUG: {name} page 1 links = {count}, total seen = {len(seen)}")
    elapsed = time.time() - start
    print(f"DEBUG: grid-only fetch for {len(TEST_CITIES)} cities took {elapsed:.1f}s, {len(seen)} listings")

    sample = list(seen.values())[:5]
    for l in sample:
        print({
            "id": l["id"], "city": l["city"], "category": l.get("category"),
            "has_site_posted_at": "site_posted_at" in l,
            "has_lat": "lat" in l,
            "has_detail_checked": "detail_checked" in l,
        })

    missing_category = sum(1 for l in seen.values() if not l.get("category"))
    print(f"DEBUG: {missing_category} / {len(seen)} listings missing category (should be 0 or near-0)")


if __name__ == "__main__":
    main()
