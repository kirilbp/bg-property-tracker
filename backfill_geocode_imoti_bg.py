"""
Fills in lat/lng for imoti.bg listings that scraper_imoti_bg.py left
uncoordinated.

scraper_imoti_bg.py's fetch_listings_page() used to call Geocoder.geocode()
directly during the scrape - a live Nominatim request on every cache miss.
That was fine when scraping was Sofia-only, but a real nationwide
production run took over 4 hours instead of its usual ~35 minutes:
nationwide means far more distinct city/area combinations, so most calls
were live, several-second round trips rather than cache hits. Fixed by
switching to a cache-only lookup during the scrape (see
scraper_imoti_bg.py's module docstring) - this script is the other half,
a separate, decoupled pass that does the real live geocoding against
whatever's still missing coordinates in the committed history file, same
pattern backfill_geocode_homes.py already established for homes.bg.

Not scheduled automatically (see backfill-geocode-imoti-bg.yml) - re-run
it by hand (or on a cron, later) until the missing-coordinate count
reaches zero, same as any other backfill.
"""

import json

import scraper_imoti_bg as sib
from geo_utils import Geocoder

# Caps a single run's live-lookup count so this can't itself balloon into
# an unbounded, multi-hour job the way in-line geocoding did at nationwide
# scale. At ~1.1-9s per uncached lookup, 1500 lookups is roughly 30-225
# minutes worst case - comfortably inside a single job.
MAX_LOOKUPS_PER_RUN = 1500


def main():
    history = sib.load_history()
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
        # Same query shape scraper_imoti_bg.py builds at scrape time - the
        # cache is keyed by this exact string, so a live lookup here later
        # counts as a hit for any future scrape run too. Older records
        # scraped before "city" was persisted fall back to area-only.
        if area and city:
            geo_query = f"{area}, {city}, България"
        elif area:
            geo_query = f"{area}, България"
        else:
            continue
        coords = geocoder.geocode(geo_query)
        if coords:
            latest["lat"] = coords["lat"]
            latest["lng"] = coords["lng"]
            filled += 1

    sib.save_history(history)
    geocoder.save()

    leads = sib.compute_leads(history)
    sib.LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    processed = min(len(missing), MAX_LOOKUPS_PER_RUN)
    print(f"DEBUG: filled {filled} / {processed} attempted this run ({len(missing) - processed} still queued for a future run)")


if __name__ == "__main__":
    main()
