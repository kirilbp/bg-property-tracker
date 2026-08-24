"""
Diagnostic-only: verifies a candidate nationwide (all-Bulgaria) search URL
for each of the 7 portals currently scoped to Sofia only, before changing
any production scraper. sales.bcpea.org is excluded - already confirmed
nationwide by inspecting its own tracked data (listings scattered across
Svishtov, Nikopol, Obzor etc, not just Sofia).

For each portal, fetches both the CURRENT (Sofia-scoped) URL and a
candidate nationwide URL, and reports: status code, response size, and a
rough "how many listing links does this page contain" count for each -
so a real, much larger number on the candidate is direct evidence it's
genuinely broader, not just a differently-worded Sofia-only page. Doesn't
touch any scraper or data file.
"""

import json
import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}

# (portal, current Sofia-scoped URL, candidate nationwide URL, listing-link regex)
CHECKS = [
    (
        "imoti.net",
        "https://www.imoti.net/en/obiavi/r/prodava/sofia",
        "https://www.imoti.net/en/obiavi/r/prodava",
        re.compile(r"/obiavi/\d+/"),
    ),
    (
        "alo.bg",
        "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342",
        "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/",
        re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$", re.MULTILINE),
    ),
    (
        "imot.bg",
        "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya",
        "https://www.imot.bg/obiavi/prodazhbi",
        re.compile(r"/obiava-(\d[a-z]\d{10,})-"),
    ),
    (
        "olx.bg",
        "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/",
        "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/",
        re.compile(r"/d/obiava/"),
    ),
    (
        "bazar.bg",
        "https://bazar.bg/obiavi/prodazhba-apartamenti/sofia",
        "https://bazar.bg/obiavi/prodazhba-apartamenti",
        re.compile(r"obiava-(\d+)"),
    ),
    (
        "imoti.bg",
        "https://imoti.bg/продажби/di:софия/cu:BGN",
        "https://imoti.bg/продажби/cu:BGN",
        re.compile(r"/assets/offers/"),
    ),
]


def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        return resp.status_code, len(resp.text), resp.text
    except Exception as e:
        return None, None, f"FAILED: {e}"


STATE_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL)


def check_homes_bg():
    # homes.bg's scraper pulls listings from window.__PRELOADED_STATE__ on
    # the homepage itself (no URL-path-based search like the other
    # portals) - dumping its real searchCriteria/location fields here
    # instead of guessing a candidate URL blind, since there's no obvious
    # "/sofia" segment to just strip like the others have.
    print("\n=== homes.bg ===")
    status, size, text = fetch("https://www.homes.bg/")
    print(f"  homepage [{status}] {size} bytes")
    if not isinstance(text, str):
        return
    m = STATE_RE.search(text)
    if not m:
        print("  no __PRELOADED_STATE__ found")
        return
    state = json.loads(m.group(1))
    offers = state.get("data", {}).get("offers", {})
    print(f"  offers.result count on this page: {len(offers.get('result', []))}")
    print(f"  offers.hasMoreItems: {offers.get('hasMoreItems')}")
    search_criteria = offers.get("searchCriteria") or state.get("data", {}).get("searchCriteria")
    print(f"  searchCriteria: {json.dumps(search_criteria, ensure_ascii=False)[:800]}")
    # also surface any top-level keys that look location-related, in case
    # searchCriteria isn't where it actually lives
    for k in state.get("data", {}).keys():
        if "location" in k.lower() or "region" in k.lower() or "city" in k.lower():
            print(f"  data.{k}: {json.dumps(state['data'][k], ensure_ascii=False)[:400]}")


def main():
    check_homes_bg()
    for portal, sofia_url, candidate_url, link_re in CHECKS:
        print(f"\n=== {portal} ===")
        status, size, text = fetch(sofia_url)
        sofia_count = len(link_re.findall(text)) if isinstance(text, str) else None
        print(f"  Sofia-scoped  [{status}] {size} bytes, ~{sofia_count} listing-link matches: {sofia_url}")

        status, size, text = fetch(candidate_url)
        cand_count = len(link_re.findall(text)) if isinstance(text, str) else None
        print(f"  candidate nat [{status}] {size} bytes, ~{cand_count} listing-link matches: {candidate_url}")

        if isinstance(sofia_count, int) and isinstance(cand_count, int):
            if cand_count > sofia_count:
                print(f"  -> candidate looks broader ({cand_count} > {sofia_count})")
            elif cand_count == sofia_count:
                print(f"  -> SAME count as Sofia-scoped - candidate may not actually be broader, needs a closer look")
            else:
                print(f"  -> candidate found FEWER matches - likely wrong URL, needs a different candidate")


if __name__ == "__main__":
    main()
