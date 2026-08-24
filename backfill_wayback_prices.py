"""
One-time backfill: injects real pre-tracking price history for imot.bg and
bazar.bg listings, sourced from the Wayback Machine's archived captures of
each portal's Sofia search page.

Why this works when nothing else did: individual listing pages are almost
never archived (~2.5% coverage, see the removed wayback_probe.py), but
search/category pages are crawled far more often since they're linked-to
and indexed. probe_wayback_category.py confirmed this empirically: imot.bg's
search page has 18 real captures (Apr 2025 - Jul 2026), and a meaningful
fraction of the listing IDs on those old archived pages are STILL present
in our currently-tracked data - the most recent capture alone overlapped
35% of a 40-listing sample. That overlap is exactly what makes this useful:
for those specific listings, the Wayback Machine saw a real price before we
ever did.

This fetches every real capture of each search page (not a sample), parses
listing cards using the same technique as the live scrapers
(scraper_imot.py / scraper_bazar.py), and for every listing that's both
(a) currently in our tracked history and (b) was captured at a timestamp
earlier than our own first_seen for it, inserts that as a real historical
snapshot - never touching or reordering anything we observed ourselves.
Each injected snapshot is tagged "source": "wayback" so it stays
distinguishable from our own live observations (compute_leads() ignores
unknown keys, so this doesn't change how price_history gets derived - a
genuine price difference between the Wayback snapshot and whatever we
first recorded shows up as a real point on the chart, honestly sourced).

Only run once per portal's available captures - Wayback doesn't crawl more
often by re-running this, so there's nothing to gain from scheduling it.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
ARCHIVE_UA = "bg-property-tracker/1.0 (personal deal-tracking tool, non-commercial)"
CDX_URL = "http://web.archive.org/cdx/search/cdx"
REQUEST_DELAY_SECONDS = 2.0
MAX_RETRIES = 4
PORTAL_COOLDOWN_SECONDS = 30

DATA_DIR = Path(__file__).parent / "data"

# (portal, category url, history filename, id prefix, id regex, price line regex)
PORTALS = [
    (
        "imot.bg",
        "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya",
        "history_imot.json",
        "imot_",
        # Deliberately looser than scraper_imot.py's own LISTING_LINK_RE
        # (which requires a trailing "-" right after the ID): a first
        # backfill attempt using that exact live-site regex matched zero
        # links on every one of 18 archived snapshots, even a July-2026
        # one using an essentially current template - while this looser
        # pattern (no trailing-hyphen requirement) is the one that
        # actually found the real overlapping IDs in the first place
        # (probe_wayback_category.py). Archived hrefs apparently don't
        # reliably carry that trailing hyphen.
        re.compile(r"obiava-(\d[a-z0-9]{15,20})"),
        re.compile(r"^([\d\s]{3,10})\s?€$"),
    ),
    (
        "bazar.bg",
        "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia",
        "history_bazar.json",
        "bazar_",
        re.compile(r"obiava-(\d+)"),
        None,  # bazar.bg's price line is a bare "€" marker on the line AFTER the digits; handled specially
    ),
]


def cdx_all_captures(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                CDX_URL,
                params={"url": url, "output": "json", "collapse": "digest", "limit": 500, "fl": "timestamp,statuscode"},
                headers={"User-Agent": ARCHIVE_UA},
                timeout=25,
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows or len(rows) < 2:
                return []
            header, *data_rows = rows
            return sorted(set(r[0] for r in data_rows if r[1] == "200"))
        except Exception as e:
            print(f"  CDX attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(REQUEST_DELAY_SECONDS * attempt)
    return None


def fetch_snapshot(timestamp, original_url):
    wayback_url = f"http://web.archive.org/web/{timestamp}id_/{original_url}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(wayback_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"    snapshot fetch attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                # A first backfill run got "Connection refused" on every one
                # of bazar.bg's fetches, right after 18 straight successful
                # imot.bg fetches - looks like archive.org started
                # throttling this runner's IP after a sustained burst.
                # Exponential (not linear) backoff gives it real room to
                # cool down between retries.
                time.sleep(REQUEST_DELAY_SECONDS * (3 ** attempt))
    return None


def timestamp_to_iso(ts):
    dt = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_imot_prices(html, id_re, price_re):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if id_re.search(a["href"])]

    results = {}
    for a in matching_links:
        m = id_re.search(a["href"])
        listing_id = m.group(1)
        if listing_id in results:
            continue
        node = a
        found_price = None
        for _ in range(8):
            if node.parent is None:
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            if len(text) > 800:
                break
            lines = [l.strip() for l in node.get_text("\n", strip=True).split("\n") if l.strip()]
            prices = []
            for l in lines:
                pm = price_re.match(l)
                if pm:
                    prices.append(int(re.sub(r"\D", "", pm.group(1))))
            if len(prices) == 1:
                found_price = prices[0]
                break
            if len(prices) > 1:
                break

        if found_price is None:
            # Fallback for archived templates where the price isn't its own
            # exact text line (e.g. inline with other text): search the
            # smallest reasonably-sized ancestor for a single "NNN NNN €"
            # substring anywhere in its text, same technique as the live
            # scraper's smallest_container_with_price, just applied second
            # rather than first since it's more prone to false matches.
            node = a
            loose_price_re = re.compile(r"[\d\s]{3,10}\s?€")
            for _ in range(8):
                if node.parent is None:
                    break
                node = node.parent
                text = node.get_text(" ", strip=True)
                if len(text) > 800:
                    break
                matches = loose_price_re.findall(text)
                if len(matches) == 1:
                    found_price = int(re.sub(r"\D", "", matches[0]))
                    break
                if len(matches) > 1:
                    break

        if found_price and found_price >= 1000:
            results[listing_id] = found_price
    return results


def parse_bazar_prices(html, id_re):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    all_links = soup.find_all("a", href=True)
    matching_links = [a for a in all_links if id_re.search(a["href"])]

    results = {}
    for a in matching_links:
        m = id_re.search(a["href"])
        listing_id = m.group(1)
        if listing_id in results:
            continue
        node = a
        found_price = None
        for _ in range(9):
            if node.parent is None:
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            if len(text) > 1500:
                break
            lines = [l.strip() for l in node.get_text("\n", strip=True).split("\n") if l.strip()]
            for i, l in enumerate(lines):
                if l == "€" and i > 0:
                    prev = lines[i - 1]
                    if re.fullmatch(r"[\d\s]{3,10}", prev):
                        found_price = int(re.sub(r"\s", "", prev))
                    break
            if found_price:
                break
        if found_price and 1000 <= found_price <= 10_000_000:
            results[listing_id] = found_price
    return results


def backfill_portal(portal, url, history_filename, id_prefix, id_re, price_re):
    print(f"\n\n===== {portal} =====")
    history_path = DATA_DIR / history_filename
    if not history_path.exists():
        print(f"  {history_filename} not found, skipping")
        return 0
    history = json.loads(history_path.read_text(encoding="utf-8"))

    print("  fetching capture list...")
    timestamps = cdx_all_captures(url)
    if not timestamps:
        print("  no captures available, skipping")
        return 0
    print(f"  {len(timestamps)} real captures found")

    injected = 0
    for ts in timestamps:
        time.sleep(REQUEST_DELAY_SECONDS)
        html = fetch_snapshot(ts, url)
        if html is None:
            print(f"  snapshot {ts}: FAILED to fetch, skipping")
            continue

        if portal == "imot.bg":
            prices = parse_imot_prices(html, id_re, price_re)
        else:
            prices = parse_bazar_prices(html, id_re)

        archived_iso = timestamp_to_iso(ts)
        matched = 0
        for listing_id, price_eur in prices.items():
            lid = id_prefix + listing_id
            rec = history.get(lid)
            if rec is None:
                continue
            first_seen = rec.get("first_seen")
            if not first_seen or archived_iso >= first_seen:
                continue
            already_injected = any(
                s.get("source") == "wayback" and s.get("seen_at") == archived_iso
                for s in rec["snapshots"]
            )
            if already_injected:
                continue
            rec["snapshots"].insert(0, {"seen_at": archived_iso, "price_eur": price_eur, "source": "wayback"})
            rec["snapshots"].sort(key=lambda s: s["seen_at"])
            if archived_iso < rec["first_seen"]:
                rec["first_seen"] = archived_iso
            matched += 1
            injected += 1
        print(f"  snapshot {ts}: {len(prices)} listings parsed, {matched} injected as real pre-tracking history")

    if injected:
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  wrote {injected} injected snapshots to {history_filename}")
    else:
        print("  nothing to inject, history file unchanged")
    return injected


def main():
    total_injected = {}
    for i, (portal, url, history_filename, id_prefix, id_re, price_re) in enumerate(PORTALS):
        if i > 0:
            print(f"\ncooling down {PORTAL_COOLDOWN_SECONDS}s before starting {portal}...")
            time.sleep(PORTAL_COOLDOWN_SECONDS)
        total_injected[portal] = backfill_portal(portal, url, history_filename, id_prefix, id_re, price_re)

    print("\n\n===== SUMMARY =====")
    for portal, count in total_injected.items():
        print(f"{portal}: {count} snapshots injected")

    if sum(total_injected.values()) == 0:
        print("Nothing injected - not regenerating leads files")
        return

    sys.path.insert(0, str(Path(__file__).parent))
    if total_injected.get("imot.bg"):
        import scraper_imot
        history = json.loads((DATA_DIR / "history_imot.json").read_text(encoding="utf-8"))
        leads = scraper_imot.compute_leads(history)
        (DATA_DIR / "leads_imot.json").write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"regenerated leads_imot.json ({len(leads)} leads)")

    if total_injected.get("bazar.bg"):
        import scraper_bazar
        history = json.loads((DATA_DIR / "history_bazar.json").read_text(encoding="utf-8"))
        leads = scraper_bazar.compute_leads(history)
        (DATA_DIR / "leads_bazar.json").write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"regenerated leads_bazar.json ({len(leads)} leads)")


if __name__ == "__main__":
    main()
