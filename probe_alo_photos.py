"""
Diagnostic-only, round 2: verifies the real fix in scraper_alo.py's
fetch_listings_page() (prefer <img class="listtop-image-img">, the real
property photo, over the agency's <img class="listtop-logo"> avatar, which
DOM order alone put first) against multiple real live search-result pages -
calls the actual scraper function directly rather than reimplementing the
extraction logic, so this validates the exact code that will ship.

Reports, per page fetched: how many listings' selected photo is an avatar
(should now be 0) vs a real photo (matches the listing's own numeric id in
the filename, confirmed as the reliable "real photo" signal against
already-correct historical data). Read-only, no commit step - deleted once
the question is answered.
"""

import re

from scraper_alo import fetch_listings_page

PAGES = [
    "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342",
    "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342&page=2",
    "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342&page=3",
]

AVATAR_RE = re.compile(r"avatar\.jpg", re.IGNORECASE)


def main():
    total = 0
    avatar_count = 0
    missing_count = 0
    own_id_count = 0
    other_count = 0

    for url in PAGES:
        seen = {}
        result = fetch_listings_page(url, seen)
        print(f"\n=== {url} ===")
        print(f"  matching links processed: {result}, listings extracted: {len(seen)}")
        for lid, entry in seen.items():
            total += 1
            photo = entry.get("photo")
            if not photo:
                missing_count += 1
                continue
            if AVATAR_RE.search(photo):
                avatar_count += 1
                print(f"    STILL AVATAR: {entry['id']} -> {photo}")
                continue
            raw_id = entry["id"].replace("alo_", "")
            if f"/{raw_id}_" in photo or photo.rsplit("/", 1)[-1].startswith(raw_id + "_"):
                own_id_count += 1
            else:
                other_count += 1
                print(f"    photo present, not own-id-prefixed (still fine, just noting): {entry['id']} -> {photo}")

    print(f"\n=== TOTALS across {len(PAGES)} live pages ===")
    print(f"  total listings: {total}")
    print(f"  photo is agency avatar (the bug): {avatar_count}")
    print(f"  photo missing/null: {missing_count}")
    print(f"  photo is real, own-id-prefixed: {own_id_count}")
    print(f"  photo present, other pattern: {other_count}")


if __name__ == "__main__":
    main()
