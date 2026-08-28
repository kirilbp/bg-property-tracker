"""
Proper re-investigation: the user found real, live Cherven Bryag listings
on bazar.bg (32), olx.bg (~3), and imot.bg (23) directly on those sites -
contradicting the previous probe's "0 mentions found" conclusion, which
was methodologically flawed (an UNORDERED merged_listings query capped at
PostgREST's 1000-row limit, filtered to oblast_key=pleven - real Cherven
Bryag rows could easily have been outside that arbitrary 1000-row slice
if Pleven oblast has more than 1000 tracked listings total).

This probe queries listing_sources directly, scoped per portal (using the
portal index to keep each query cheap - no full-table scan), with a
server-side ilike filter on area AND title, to settle definitively: does
our own scraped data actually contain these portals' real Cherven Bryag
listings, or were they never captured at all?

Not part of the scraper pipeline - dispatched by hand, read once, then
deleted.
"""

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}

PORTALS = ["olx.bg", "bazar.bg", "imot.bg", "alo.bg", "homes.bg", "imoti.net", "imoti.bg", "sales.bcpea.org"]
NEEDLES = ["червен бряг", "cherven bryag"]


def main():
    or_filter_area = ",".join([f"area.ilike.*{n}*" for n in NEEDLES])
    or_filter_title = ",".join([f"title.ilike.*{n}*" for n in NEEDLES])

    for portal in PORTALS:
        # Total rows this portal has right now (sanity check the portal
        # count matches what's shown on the site).
        count_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/listing_sources",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={"select": "source_id", "portal": f"eq.{portal}", "limit": 1},
            timeout=30,
        )
        total = count_resp.headers.get("content-range", "?/?").split("/")[-1]

        area_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/listing_sources",
            headers=HEADERS,
            params={
                "select": "source_id,title,area,lat,lng,price_eur,url",
                "portal": f"eq.{portal}",
                "or": f"({or_filter_area})",
                "limit": 100,
            },
            timeout=30,
        )
        area_hits = area_resp.json() if area_resp.ok else f"ERROR {area_resp.status_code}: {area_resp.text[:200]}"

        title_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/listing_sources",
            headers=HEADERS,
            params={
                "select": "source_id,title,area,lat,lng,price_eur,url",
                "portal": f"eq.{portal}",
                "or": f"({or_filter_title})",
                "limit": 100,
            },
            timeout=30,
        )
        title_hits = title_resp.json() if title_resp.ok else f"ERROR {title_resp.status_code}: {title_resp.text[:200]}"

        print(f"\n=== {portal} (total tracked: {total}) ===")
        print(f"  area matches: {len(area_hits) if isinstance(area_hits, list) else area_hits}")
        if isinstance(area_hits, list):
            for r in area_hits[:10]:
                print(f"    {r['source_id']}: title={r.get('title')!r} area={r.get('area')!r} "
                      f"lat={r.get('lat')} lng={r.get('lng')} price={r.get('price_eur')}")
        print(f"  title matches: {len(title_hits) if isinstance(title_hits, list) else title_hits}")
        if isinstance(title_hits, list):
            for r in title_hits[:10]:
                print(f"    {r['source_id']}: title={r.get('title')!r} area={r.get('area')!r} "
                      f"lat={r.get('lat')} lng={r.get('lng')} price={r.get('price_eur')}")


if __name__ == "__main__":
    main()
