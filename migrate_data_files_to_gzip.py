"""
One-time migration: converts alo.bg/bazar.bg/olx.bg/imot.bg's currently
committed data/history_*.json and data/leads_*.json to data/*.json.gz -
the exact same gzip fix already proven for homes.bg (2026-09-25 addendum
to docs/backlog.md item 37; see geo_utils.py's "Compressed on-disk JSON
storage" comment for the full real-data reasoning).

2026-09-26 incident: alo.bg's backfill-detail-alo.yml push was rejected
with a hard GH001 (data/leads_alo.json 101.60MB/data/history_alo.json
99.41MB per that run's own real error text - real committed sizes as of
this migration: leads_alo.json 104,292,257 bytes/history_alo.json
101,950,671 bytes) - already over GitHub's 100MB hard push limit, so
every scheduled run keeps failing identically. bazar.bg is right behind
it (leads_bazar.json 100,191,086 bytes/history_bazar.json 98,734,614
bytes - already at/over the limit too). olx.bg (leads 83.2MB/history
81.75MB) and imot.bg (leads 67.68MB/history 68.23MB) are proactively
migrated in the same pass rather than firefighted individually as each
one crosses the threshold - same unbounded-growth dynamics item 37
already root-caused (evict_stale_records() bounds this going forward, but
alo.bg's/bazar.bg's own tracked history is still too young for 180-day
eviction to reclaim anything yet).

This script does ONLY the one-time file-format conversion (compress the
already-committed data, verify it round-trips byte-for-byte, then remove
the plain original) - it does not touch record contents, ordering, or any
field. Every future read/write already goes through geo_utils.py's
load_json_any()/save_json_any() (this session's own scraper_*.py /
backfill_*.py / sync_to_supabase.py / evict_stale_history.py / etc.
changes), which are extension-aware, so nothing downstream needs to know
this migration happened.

Deliberately standalone/dependency-free in spirit (only imports geo_utils
for its already-shared load_json_any()/save_json_any(), the same as
evict_stale_history.py already does) - safe to run from any checkout with
this repo's base requirements (requests/bs4), no playwright needed.

Usage:
    python3 migrate_data_files_to_gzip.py                # all 4 portals
    python3 migrate_data_files_to_gzip.py alo bazar       # just these
    python3 migrate_data_files_to_gzip.py --dry-run       # report only
"""
import sys
from pathlib import Path

from geo_utils import load_json_any, save_json_any

DATA_DIR = Path(__file__).parent / "data"

# portal short name -> (history filename, leads filename), plain .json ->
# .json.gz, matching each scraper's own new HISTORY_FILE/LEADS_FILE.
PORTAL_FILES = {
    "alo": ("history_alo.json", "leads_alo.json"),
    "bazar": ("history_bazar.json", "leads_bazar.json"),
    "olx": ("history_olx.json", "leads_olx.json"),
    "imot": ("history_imot.json", "leads_imot.json"),
}


def _migrate_one(plain_name, dry_run=False):
    plain_path = DATA_DIR / plain_name
    gz_path = DATA_DIR / (plain_name + ".gz")

    if not plain_path.exists():
        if gz_path.exists():
            print(f"  {plain_name}: already migrated ({gz_path.name} exists, no plain original) - skipping")
        else:
            print(f"  {plain_name}: not found, skipping")
        return None

    before_size = plain_path.stat().st_size
    data = load_json_any(plain_path)
    record_count = len(data)

    if dry_run:
        print(f"  {plain_name}: {record_count} records, {before_size:,} bytes plain - "
              f"would write {gz_path.name} (dry-run, nothing written)")
        return None

    save_json_any(gz_path, data)

    # Verify: decompress the just-written .gz and confirm it is EXACTLY
    # the same Python object as what was read from the plain file (not
    # just "same byte length" or "same record count") - a real,
    # structural round-trip check, not a proxy for one. json.dump's
    # ensure_ascii=False/separators choice doesn't change the round-
    # tripped Python value at all, so full equality is the right bar
    # here, not merely "close enough."
    roundtripped = load_json_any(gz_path)
    if roundtripped != data:
        gz_path.unlink()
        raise RuntimeError(
            f"{plain_name}: round-trip verification FAILED - {gz_path.name} does not decompress back to "
            f"the exact original data. Removed the bad .gz file; the plain original is untouched."
        )
    if len(roundtripped) != record_count:
        gz_path.unlink()
        raise RuntimeError(
            f"{plain_name}: record count changed across migration ({record_count} -> {len(roundtripped)}) "
            f"- removed the bad .gz file; the plain original is untouched."
        )

    after_size = gz_path.stat().st_size
    pct = (1 - after_size / before_size) * 100 if before_size else 0
    print(f"  {plain_name}: {record_count} records verified byte-for-byte identical after round-trip - "
          f"{before_size:,} -> {after_size:,} bytes ({pct:.1f}% smaller)")

    # Only remove the plain original once the .gz file has been fully
    # written AND verified above - never delete first.
    plain_path.unlink()
    return {
        "records": record_count,
        "before_bytes": before_size,
        "after_bytes": after_size,
    }


def migrate_portal(portal, dry_run=False):
    history_fn, leads_fn = PORTAL_FILES[portal]
    print(f"=== {portal} ===")
    history_result = _migrate_one(history_fn, dry_run=dry_run)
    leads_result = _migrate_one(leads_fn, dry_run=dry_run)
    return history_result, leads_result


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    portals = [a for a in args if a != "--dry-run"] or list(PORTAL_FILES)

    unknown = [p for p in portals if p not in PORTAL_FILES]
    if unknown:
        print(f"Unknown portal(s): {unknown}. Known portals: {list(PORTAL_FILES)}")
        sys.exit(2)

    for portal in portals:
        migrate_portal(portal, dry_run=dry_run)


if __name__ == "__main__":
    main()
