"""
Fills in lat/lng for olx.bg listings that scraper_olx.py left uncoordinated.

scraper_olx.py's nationwide rewrite deliberately stopped doing live
Nominatim geocoding in-line during the scrape (see its module docstring
for the full story - the same problem scraper_homes.py hit first at
nationwide scale). It now only does a cache-only lookup and leaves
everything else as lat=lng=None.

This script is the other half: a separate, decoupled pass that does the
real live geocoding (same rate-limited, cached Geocoder as before) against
whatever's still missing coordinates in the committed history file, so the
scrape itself stays fast and reliable while location data catches up over
however many runs it takes - the same pattern backfill_geocode_homes.py
already established.

Not scheduled automatically (see backfill-geocode-olx.yml) - re-run it
by hand (or on a cron, later) until the missing-coordinate count reaches
zero, same as any other backfill.
"""

import json

import scraper_olx as so
from geo_utils import Geocoder

# Caps a single run's live-lookup count so this can't itself balloon into
# an unbounded, multi-hour job the way in-line geocoding did at nationwide
# scale (see the module docstring) - meant to be re-run repeatedly (now
# hourly, on a schedule) until the missing-coordinate count hits zero.
# 250 (down from 1500) fits comfortably inside the 45-minute timeout an
# hourly cron needs - see backfill_geocode_homes.py's own comment for the
# full per-lookup timing reasoning.
MAX_LOOKUPS_PER_RUN = 250


def main():
    history = so.load_history()
    geocoder = Geocoder()

    missing = [
        (lid, rec) for lid, rec in history.items()
        if rec.get("latest", {}).get("lat") is None
    ]
    print(f"DEBUG: {len(missing)} / {len(history)} listings missing coordinates")

    filled = 0
    for lid, rec in missing[:MAX_LOOKUPS_PER_RUN]:
        latest = rec["latest"]
        area = latest.get("area", "")
        city = latest.get("city", "")
        # Same query shape scraper_olx.py builds at scrape time - the
        # cache is keyed by this exact string, so a live lookup here later
        # counts as a hit for any future scrape run too.
        geo_query = f"{area}, {city}, България" if area and city else None
        if not geo_query:
            continue
        coords = geocoder.geocode(geo_query)
        if coords:
            latest["lat"] = coords["lat"]
            latest["lng"] = coords["lng"]
            filled += 1

    so.save_history(history)
    geocoder.save()

    leads = so.compute_leads(history)
    so.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    processed = min(len(missing), MAX_LOOKUPS_PER_RUN)
    print(f"DEBUG: filled {filled} / {processed} attempted this run ({len(missing) - processed} still queued for a future run)")


if __name__ == "__main__":
    main()
