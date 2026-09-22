"""
Fails the workflow loudly when a scraper's just-committed output shows no
sign of a fresh crawl having actually landed - the "fail loud, never
silent" counterpart, for a different failure shape, to sync_to_supabase.
py's existing near-zero-results data-loss guard (see that file's own
"Data-loss safety guard" section): that guard catches a scraper that
returns almost nothing; this one catches a scraper that keeps returning a
healthy count every run while the file that's actually supposed to land
on disk silently stops updating - alo.bg's grid crawl did exactly this
for 6 days (docs/backlog.md item 3): scraper_alo.py's own step reported
success and "Found 77,000+ listings" in its logs every single day, but
none of it ever reached the committed data/history_alo.json (see
merge_history_conflict.py's docstring for the actual root cause and its
fix) - so every downstream signal that only looks at "did the step
exit 0" stayed green throughout, and it took a human audit to notice.

Two independent checks, either one failing fails the whole check:
1. Freshness: the single most recent snapshot across the whole history
   file must be recent - if it isn't, this run's crawl (or an earlier
   day's) never actually landed in the file now on disk, regardless of
   what the scraper step itself reported.
2. Active ratio: the computed leads file's source_status="active" share
   must clear a floor well under every portal's own healthy range (see
   MIN_ACTIVE_RATIO below) - catches the downstream symptom directly (an
   entire portal flipping "removed"/"sold" in one pass) as a second,
   independent signal in case the freshness check above is ever fooled by
   something this script's author didn't anticipate.

Run this AFTER the commit/push step succeeds (so it's checking the exact
state that actually landed on main, not this run's pre-conflict-resolution
local state) and WITHOUT continue-on-error, so a real staleness event
makes the workflow run itself report a failure - unlike scraper_alo.py's
own step, whose continue-on-error is deliberately about isolating one
scraper's crash from the rest of the run, not about hiding a bad result.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Generous slack above this repo's cron cadences (24h for scrape-large.yml,
# 6h for scrape.yml) so an occasionally slow/delayed run doesn't trip this -
# tight enough that a crawl silently dead for days (alo.bg's real incident)
# fails fast instead of taking 48h+ (GONE_AFTER's own threshold) to show up
# as a symptom.
MAX_FRESHEST_SNAPSHOT_AGE_HOURS = 30

# Corrected 2026-09-22 (Missy's PR #197 review): this threshold is only
# actually safe for the portals currently wired up below (alo.bg, imoti.net)
# - it is NOT comfortably under every portal's real active ratio. Measured
# directly against the real committed data: imoti.net 63.8%, imot.bg 68.8%,
# alo.bg 0.0% (the real incident this check exists to catch), olx.bg 43.3%,
# homes.bg 91.2%, bazar.bg 45.2%, imoti.bg 90.3%, bcpea 60.1%. olx.bg and
# bazar.bg sit only 3-5 points above this 40% floor - a normal day's
# fluctuation could trip a false portal-wide-failure alarm for either of
# them. Do NOT extend this check to olx.bg or bazar.bg with this same
# threshold without first re-deriving a real per-portal margin from their
# own healthy-day data, the way this was done for alo.bg/imoti.net.
MIN_ACTIVE_RATIO = 0.40
MIN_LISTINGS_FOR_RATIO_CHECK = 50


def check_history_freshness(history_path):
    if not history_path.exists():
        print(f"::error::check_scrape_freshness.py: {history_path} does not exist - nothing to check")
        return False
    history = json.loads(history_path.read_text(encoding="utf-8"))
    if not history:
        print(f"check_scrape_freshness.py: {history_path} is empty - skipping (nothing tracked yet)")
        return True
    newest = None
    for rec in history.values():
        snaps = rec.get("snapshots") or []
        if not snaps:
            continue
        seen_at = snaps[-1].get("seen_at")
        if not seen_at:
            continue
        ts = datetime.fromisoformat(seen_at)
        if newest is None or ts > newest:
            newest = ts
    if newest is None:
        print(f"::error::check_scrape_freshness.py: {history_path}: no listing has a single snapshot with "
              f"a seen_at - can't tell when this portal was last actually crawled")
        return False
    age_hours = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
    if age_hours > MAX_FRESHEST_SNAPSHOT_AGE_HOURS:
        print(
            f"::error::check_scrape_freshness.py: {history_path}: freshest snapshot across all "
            f"{len(history)} tracked listings is {age_hours:.1f}h old (limit "
            f"{MAX_FRESHEST_SNAPSHOT_AGE_HOURS}h) - this run's crawl doesn't look like it actually "
            f"landed on disk, even though the scraper step itself may have reported success. See "
            f"docs/backlog.md item 3 and merge_history_conflict.py's docstring for the known cause "
            f"of this exact failure shape."
        )
        return False
    print(f"OK: check_scrape_freshness.py: {history_path}: freshest snapshot is {age_hours:.1f}h old "
          f"(limit {MAX_FRESHEST_SNAPSHOT_AGE_HOURS}h)")
    return True


def check_leads_active_ratio(leads_path):
    if not leads_path.exists():
        print(f"::error::check_scrape_freshness.py: {leads_path} does not exist - nothing to check")
        return False
    leads = json.loads(leads_path.read_text(encoding="utf-8"))
    total = len(leads)
    if total < MIN_LISTINGS_FOR_RATIO_CHECK:
        print(f"check_scrape_freshness.py: {leads_path} has only {total} listings - skipping active-ratio check")
        return True
    active = sum(1 for l in leads if l.get("source_status") == "active")
    ratio = active / total
    if ratio < MIN_ACTIVE_RATIO:
        print(
            f"::error::check_scrape_freshness.py: {leads_path}: only {active}/{total} listings "
            f"({ratio:.1%}) are source_status=active (floor {MIN_ACTIVE_RATIO:.0%}) - this looks like "
            f"a portal-wide false-removal event (a dead/stuck crawl aging every listing past its own "
            f"GONE_AFTER threshold), not a real mass delisting."
        )
        return False
    print(f"OK: check_scrape_freshness.py: {leads_path}: {active}/{total} ({ratio:.1%}) active")
    return True


def main():
    if len(sys.argv) < 2:
        print('Usage: check_scrape_freshness.py <portal_suffix> [<portal_suffix> ...]')
        print('  e.g. "alo" checks data/history_alo.json + data/leads_alo.json; '
              '"" checks data/history.json + data/leads.json')
        sys.exit(2)
    ok = True
    for suffix in sys.argv[1:]:
        suffix_part = f"_{suffix}" if suffix else ""
        history_path = DATA_DIR / f"history{suffix_part}.json"
        leads_path = DATA_DIR / f"leads{suffix_part}.json"
        ok = check_history_freshness(history_path) and ok
        ok = check_leads_active_ratio(leads_path) and ok
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
