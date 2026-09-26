"""
One-time correction pass: independently re-verifies every cached
"<area>, <city>, България" geocode against a live geocode of the bare
settlement name alone, and corrects any entry that disagrees by more
than 30km AND whose bare name is independently confident (Nominatim's
own top-3 results for it cluster within 30km of each other - see
geo_utils.Geocoder._bare_name_is_confident) - the same signature
discovered live for Cherven Bryag, wrongly geocoded via a "Ловеч"
(Lovech) qualifier that several portals' own city/oblast-sliced search
pages happened to attribute it to.

A first version of both this script and geo_utils.Geocoder.geocode()'s
own cross-check hand-excluded only Bulgaria's 4 biggest cities
(София/Пловдив/Варна/Бургас) from the check, on the theory that only
megacities reuse generic district names (Център/Дружба/Изток...) across
unrelated towns. That was wrong: mid-sized cities (Ruse, Haskovo,
Pazardzhik, and others) have the same generic district names, and a
real dispatch of that version wrongly "corrected" 42 cache entries and
propagated bad coordinates to 4,244 real listings before being caught
(via manual log review, before any sync to production) and reverted.
This version replaces the hand-maintained exclusion list with the
general confidence check instead, which needs no advance knowledge of
which cities are "safe".

ALWAYS run with --dry-run first and manually review the output before
running for real - the confidence check is a heuristic, not a proof,
and a previous heuristic here already caused real data corruption once.

This exists because geo_utils.Geocoder.geocode()'s cross-check only
protects FUTURE geocode calls (cache misses going forward) - it can't
retroactively re-check entries already sitting in
data/geocode_cache.json from before the fix existed. This script is that
one-time catch-up pass over the qualified entries that have no
already-cached bare counterpart to check against for free.

For every corrected cache entry, also finds and fixes every listing
across all 8 portals' history_*.json/leads_*.json whose lat/lng exactly
matches the old (wrong) cached value - the same propagation the earlier
manual Cherven Bryag fix did, generalized here to run over the whole
remaining backlog in one pass.

Not scheduled - a one-time correction, run by hand once, its job done.
"""

import json
import math
from pathlib import Path

from geo_utils import Geocoder, _haversine_km, load_json_any, save_json_any

DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "geocode_cache.json"
MISMATCH_KM = 30

# homes.bg's own pair is .json.gz, not plain .json - 2026-09-25 addendum
# to the GH001 incident fix (see geo_utils.py's "Compressed on-disk JSON
# storage" comment). propagate_fix() below reads/writes through
# load_json_any()/save_json_any(), which are extension-aware.
PORTAL_FILES = [
    ("history_imot.json.gz", "leads_imot.json.gz"),
    ("history_imoti_bg.json", "leads_imoti_bg.json"),
    ("history_olx.json.gz", "leads_olx.json.gz"),
    ("history_alo.json.gz", "leads_alo.json.gz"),
    ("history_bazar.json.gz", "leads_bazar.json.gz"),
    ("history_homes.json.gz", "leads_homes.json.gz"),
    ("history.json", "leads.json"),
    ("history_bcpea.json", "leads_bcpea.json"),
]


def find_candidates(cache):
    """Every qualified ("<area>, <city>, България") cache entry with no
    already-cached bare counterpart. No city is excluded up front (an
    earlier version hand-excluded Bulgaria's 4 biggest cities, on the
    theory that only megacities have generic, reused district names -
    that assumption was wrong: mid-sized cities like Ruse and Haskovo
    have them too, and the exclusion list let those slip through
    uncaught). Safety instead comes entirely from main()'s confidence
    gate (Geocoder._bare_name_is_confident) at the point each candidate
    is actually checked live, which works for any city without needing
    to know its name in advance."""
    qualified = {k: v for k, v in cache.items() if v and len(k.split(",")) >= 3}
    candidates = []
    for key, val in qualified.items():
        parts = [p.strip() for p in key.split(",")]
        bare_key = f"{parts[0]}, България"
        if cache.get(bare_key) is not None:
            continue  # already handled by the local-only pass
        candidates.append((key, val, bare_key))
    return candidates


def propagate_fix(old_lat, old_lng, new_lat, new_lng):
    fixed_total = 0
    for history_name, leads_name in PORTAL_FILES:
        history_path = DATA_DIR / history_name
        leads_path = DATA_DIR / leads_name
        if not history_path.exists() or not leads_path.exists():
            continue

        history = load_json_any(history_path)
        fixed_ids = []
        for lid, rec in history.items():
            latest = rec.get("latest", {})
            if latest.get("lat") == old_lat and latest.get("lng") == old_lng:
                latest["lat"] = new_lat
                latest["lng"] = new_lng
                fixed_ids.append(lid)
        if fixed_ids:
            save_json_any(history_path, history)

            leads = load_json_any(leads_path)
            for entry in leads:
                if entry.get("id") in fixed_ids:
                    entry["lat"] = new_lat
                    entry["lng"] = new_lng
            save_json_any(leads_path, leads)

            print(f"    propagated to {len(fixed_ids)} listing(s) in {history_name}: {fixed_ids}")
            fixed_total += len(fixed_ids)
    return fixed_total


def main():
    import sys
    dry_run = "--dry-run" in sys.argv
    print(f"DEBUG: dry_run={dry_run}")

    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    candidates = find_candidates(cache)
    print(f"DEBUG: {len(candidates)} qualified cache entries need a live bare-name check")

    geocoder = Geocoder()
    geocoder.cache = cache  # reuse the already-loaded cache directly

    corrected = 0
    listings_fixed = 0
    for i, (key, val, bare_key) in enumerate(candidates, 1):
        bare_result = geocoder.geocode(bare_key)  # live call, cached afterwards
        if not bare_result:
            continue
        dist = _haversine_km(val["lat"], val["lng"], bare_result["lat"], bare_result["lng"])
        if dist <= MISMATCH_KM:
            continue
        # Same confidence gate as Geocoder.geocode()'s own cross-check - a
        # disagreement alone isn't enough (see that function's docstring
        # for why: a generic district name reused across many towns will
        # always "disagree" with an arbitrary same-named place elsewhere,
        # without that being evidence of anything wrong).
        if not geocoder._bare_name_is_confident(bare_key):
            print(f"[{i}/{len(candidates)}] mismatch {dist:.0f}km but bare name AMBIGUOUS, skipping: "
                  f"{key!r} -> {val} vs bare {bare_key!r} -> {bare_result}")
            continue
        print(f"[{i}/{len(candidates)}] MISMATCH {dist:.0f}km: {key!r} -> {val} "
              f"vs bare {bare_key!r} -> {bare_result}")
        if dry_run:
            corrected += 1
            continue
        old_lat, old_lng = val["lat"], val["lng"]
        cache[key] = bare_result
        corrected += 1
        listings_fixed += propagate_fix(old_lat, old_lng, bare_result["lat"], bare_result["lng"])
        if i % 25 == 0:
            print(f"DEBUG: checked {i}/{len(candidates)}")

    if dry_run:
        print(f"\nDRY RUN done: {corrected} would be corrected (no files written)")
        return

    geocoder.cache = cache
    geocoder._dirty = True
    geocoder.save()

    print(f"\nDone: {corrected} cache entries corrected, {listings_fixed} listings fixed across all portals")


if __name__ == "__main__":
    main()
