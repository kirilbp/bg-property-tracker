"""
Diagnostic-only: scraper_alo.py's `photo` field turns out to be the agent's
avatar image (not the property) for 93.8% of currently tracked alo.bg
listings (confirmed against data/leads_alo.json - 9,281 of 9,897 photo URLs
match *avatar.jpg, one avatar file reused across as many as 1,201 different
listings). The scraper picks `container.find("img")` - the FIRST <img> tag
inside the smallest DOM ancestor of the listing link that mentions the
price exactly once - with no filtering, so if the avatar happens to appear
before the real photo in that container's DOM order, the avatar wins.

This fetches a handful of REAL currently-avatar-contaminated listing pages
(ids taken directly from data/leads_alo.json) plus one already-correct one,
and dumps every <img> tag found inside that same container (src, class,
alt) so the real fix can be based on what's actually there - either a
smarter selector (skip avatar-looking srcs, prefer one whose filename
contains the listing's own id - confirmed as the real-photo naming pattern
in 94.8% of already-correct entries) if a real photo IS present in the
DOM and just being missed, or accepting that alo.bg genuinely shows only
the agency avatar for many agency-posted listings (in which case the fix
is: don't show a misleading avatar as the property photo at all - fall
back to no photo).

Read-only, doesn't touch any data file or committed scraper.
"""

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
PRICE_RE = re.compile(r"Цена\s*:\s*([\d\s]+)\s?€")
MAX_PRICE_MENTIONS = 1
MAX_CARD_TEXT_LENGTH = 2000

# Real avatar-contaminated listing URLs pulled straight from the currently
# committed data/leads_alo.json (their `url` field, not `photo`).
CASES = [
    ("avatar-contaminated", "https://www.alo.bg/dvustaen-apartament-88-kv-m-tuhla-2024-g-3-etaj-neposleden-11363257"),
    ("avatar-contaminated", "https://www.alo.bg/sky-towers-by-amur-noviyat-standart-za-luks-v-sofiya-10727638"),
    ("avatar-contaminated", "https://www.alo.bg/tristaen-apartament-endrevahouses-11319466"),
]


def smallest_container_with_price(link_tag, max_levels=6):
    node = link_tag
    for _ in range(max_levels):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        matches = PRICE_RE.findall(text)
        if len(matches) > MAX_PRICE_MENTIONS:
            return None
        if len(matches) == 1 and len(text) <= MAX_CARD_TEXT_LENGTH:
            return node
    return None


def inspect(url, label):
    print(f"\n=== [{label}] {url} ===")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  FETCH FAILED: {e}")
        return
    soup = BeautifulSoup(resp.text, "html.parser")

    # This is a single listing's OWN page, not a search-results grid page -
    # scraper_alo.py normally does this container-climb on a link found
    # inside a GRID page's listing card, not on the detail page itself. So
    # instead: find the listing's own id from the URL, then search the
    # whole page for every <img> tag and print each one - on the real grid
    # page the equivalent card is one of many; on the single listing's own
    # page, this at least reveals whether a same-id-prefixed real photo
    # exists ANYWHERE in the markup this listing ships, which the grid
    # card is presumably drawing from too.
    m = re.search(r"-(\d{6,9})$", url)
    listing_id = m.group(1) if m else "?"
    print(f"  listing id: {listing_id}")

    imgs = soup.find_all("img")
    print(f"  total <img> tags on page: {len(imgs)}")
    own_id_imgs = [img for img in imgs if img.get("src") and listing_id in img.get("src")]
    avatar_imgs = [img for img in imgs if img.get("src") and "avatar" in img.get("src").lower()]
    print(f"  <img> srcs containing the listing's own id: {len(own_id_imgs)}")
    for img in own_id_imgs[:5]:
        print(f"    OWN-ID: {img.get('src')} class={img.get('class')}")
    print(f"  <img> srcs containing 'avatar': {len(avatar_imgs)}")
    for img in avatar_imgs[:5]:
        print(f"    AVATAR: {img.get('src')} class={img.get('class')}")

    # Also try the actual grid-scraping logic against a real SEARCH page to
    # see the container-climb + first-img selection in its natural habitat.


def inspect_grid_page():
    print("\n=== grid page: apartment listings search, page 1 ===")
    url = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  FETCH FAILED: {e}")
        return
    soup = BeautifulSoup(resp.text, "html.parser")
    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if LISTING_LINK_RE.search(a["href"])]
    print(f"  matching listing links found: {len(matching_links)}")

    checked = 0
    for a in matching_links:
        if checked >= 8:
            break
        container = smallest_container_with_price(a)
        if container is None:
            continue
        checked += 1
        match = LISTING_LINK_RE.search(a["href"])
        listing_id = match.group(1)
        imgs = container.find_all("img")
        print(f"\n  -- listing {listing_id} ({a['href']}) -- container has {len(imgs)} <img> tag(s)")
        for i, img in enumerate(imgs):
            src = img.get("src")
            is_avatar = src and "avatar" in src.lower()
            has_own_id = src and listing_id in src
            print(f"     [{i}] src={src} avatar={is_avatar} own_id={has_own_id} class={img.get('class')}")


def main():
    for label, url in CASES[:3]:
        inspect(url, label)
    inspect_grid_page()


if __name__ == "__main__":
    main()
