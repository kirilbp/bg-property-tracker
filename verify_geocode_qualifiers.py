"""
One-time correction pass: independently re-verifies every cached
"<area>, <city>, България" geocode whose <city> qualifier is NOT one of
Bulgaria's 4 biggest cities (София/Пловдив/Варна/Бургас - see geo_utils.
Geocoder.geocode()'s own cross-check for why those are excluded) against
a live geocode of the bare settlement name alone, and corrects any entry
that disagrees by more than 30km - the same signature discovered live for
Cherven Bryag, wrongly geocoded via a "Ловеч" (Lovech) qualifier that
several portals' own city/oblast-sliced search pages happened to
attribute it to.

This exists because geo_utils.Geocoder.geocode()'s new cross-check only
protects FUTURE geocode calls (cache misses going forward) - it can't
retroactively re-check the ~1,100 entries already sitting in
data/geocode_cache.json from before the fix existed. This script is that
one-time catch-up pass over the entries that couldn't be checked using
only what's already cached locally (see the accompanying investigation:
393 qualified entries total, 15 already-cacheable mismatches found and
fixed by hand for Cherven Bryag's cluster, 226 protected by the megacity
exclusion, leaving these ~152 needing a real, live bare-name lookup to
judge).

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

from geo_utils import Geocoder, _MEGACITIES_WITH_COMMON_DISTRICT_NAMES, _haversine_km

DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "geocode_cache.json"
MISMATCH_KM = 30

PORTAL_FILES = [
    ("history_imot.json", "leads_imot.json"),
    ("history_imoti_bg.json", "leads_imoti_bg.json"),
    ("history_olx.json", "leads_olx.json"),
    ("history_alo.json", "leads_alo.json"),
    ("history_bazar.json", "leads_bazar.json"),
    ("history_homes.json", "leads_homes.json"),
    ("history.json", "leads.json"),
    ("history_bcpea.json", "leads_bcpea.json"),
]


def find_candidates(cache):
    qualified = {k: v for k, v in cache.items() if v and len(k.split(",")) >= 3}
    candidates = []
    for key, val in qualified.items():
        parts = [p.strip() for p in key.split(",")]
        if parts[1] in _MEGACITIES_WITH_COMMON_DISTRICT_NAMES:
            continue
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

        history = json.loads(history_path.read_text(encoding="utf-8"))
        fixed_ids = []
        for lid, rec in history.items():
            latest = rec.get("latest", {})
            if latest.get("lat") == old_lat and latest.get("lng") == old_lng:
                latest["lat"] = new_lat
                latest["lng"] = new_lng
                fixed_ids.append(lid)
        if fixed_ids:
            history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

            leads = json.loads(leads_path.read_text(encoding="utf-8"))
            for entry in leads:
                if entry.get("id") in fixed_ids:
                    entry["lat"] = new_lat
                    entry["lng"] = new_lng
            leads_path.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

            print(f"    propagated to {len(fixed_ids)} listing(s) in {history_name}: {fixed_ids}")
            fixed_total += len(fixed_ids)
    return fixed_total


def main():
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
        if dist > MISMATCH_KM:
            print(f"[{i}/{len(candidates)}] MISMATCH {dist:.0f}km: {key!r} -> {val} "
                  f"vs bare {bare_key!r} -> {bare_result}")
            old_lat, old_lng = val["lat"], val["lng"]
            cache[key] = bare_result
            corrected += 1
            listings_fixed += propagate_fix(old_lat, old_lng, bare_result["lat"], bare_result["lng"])
        if i % 25 == 0:
            print(f"DEBUG: checked {i}/{len(candidates)}")

    geocoder.cache = cache
    geocoder._dirty = True
    geocoder.save()

    print(f"\nDone: {corrected} cache entries corrected, {listings_fixed} listings fixed across all portals")


if __name__ == "__main__":
    main()
