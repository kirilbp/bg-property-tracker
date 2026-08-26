"""
Diagnostic: the just-completed sync reported 114,129 merged_listings,
notably lower than the 125,139 confirmed live minutes earlier - and the
city-allocation fix just shipped doesn't touch group_listings() (the
cross-portal merge logic) at all, so the total shouldn't have moved.
Re-check the live count directly right now, plus per-portal listing_sources
counts, to confirm whether this is real data loss or something else
(e.g. merge-group membership shifting because sync's on_conflict=id upsert
doesn't delete old merged_listings rows whose membership changed under a
new id - orphaned old rows could still exist, or somehow got removed).
"""

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}

PORTALS = ["imoti.net", "alo.bg", "homes.bg", "imot.bg", "olx.bg", "bazar.bg", "imoti.bg", "sales.bcpea.org"]


def exact_count(table, extra_params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"select": "id" if table == "merged_listings" else "source_id", **(extra_params or {})}
    headers = {**HEADERS, "Range-Unit": "items", "Range": "0-0", "Prefer": "count=exact"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    cr = resp.headers.get("Content-Range")
    return resp.status_code, cr


def main():
    status, cr = exact_count("merged_listings")
    print(f"merged_listings total: status={status} Content-Range={cr}")

    total = 0
    for p in PORTALS:
        status, cr = exact_count("listing_sources", {"portal": f"eq.{p}"})
        print(f"listing_sources[{p}]: status={status} Content-Range={cr}")
        if cr and "/" in cr:
            try:
                total += int(cr.split("/")[1])
            except ValueError:
                pass
    print(f"sum of per-portal listing_sources counts: {total}")


if __name__ == "__main__":
    main()
