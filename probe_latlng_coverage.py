"""
One-shot probe: investigate why a radius-mode lead generator centered on
Cherven Bryag (a small town in Pleven oblast, ~10km radius) returned zero
matches, and whether lat/lng coverage is a real, isolated small-town gap
or a broader systemic problem.

matchesLeadGenerator()'s radius mode (index.html) requires l.lat/l.lng to
be non-null on the listing itself - a text/area-name match is not enough.
This checks: (1) overall lat/lng null rate across all merged_listings,
broken down by portal, (2) how many listings even exist whose area/city/
title mentions Cherven Bryag or its municipality/oblast at all, and of
those, how many have real coordinates.

Not part of the scraper pipeline - dispatched by hand, read once, then
deleted.
"""

import json

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}


def fetch_all(table, select, order_col="id", extra_params=None, page_size=1000, max_rows=None):
    """Keyset-paginated fetch (see index.html's fetchAllRows() for why -
    OFFSET pagination times out on a large table)."""
    rows = []
    cursor = None
    while True:
        params = {"select": select, "order": order_col, "limit": page_size}
        if extra_params:
            params.update(extra_params)
        if cursor is not None:
            params[order_col] = f"gt.{cursor}"
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        rows.extend(data)
        if len(data) < page_size or (max_rows and len(rows) >= max_rows):
            break
        cursor = data[-1][order_col]
    return rows


def main():
    # 1. Total row count + overall lat/lng null rate + per-portal breakdown.
    print("Fetching all merged_listings (id, lat, lng, member_portals, area, city_key)...")
    rows = fetch_all("merged_listings", "id,lat,lng,member_portals,area,city_key,oblast_key")
    total = len(rows)
    with_coords = sum(1 for r in rows if r.get("lat") is not None and r.get("lng") is not None)
    print(f"\nTOTAL merged_listings: {total}")
    print(f"With real lat/lng: {with_coords} ({100*with_coords/total:.1f}%)")
    print(f"Without lat/lng: {total - with_coords} ({100*(total-with_coords)/total:.1f}%)")

    portal_total = {}
    portal_with_coords = {}
    for r in rows:
        has_coords = r.get("lat") is not None and r.get("lng") is not None
        for p in (r.get("member_portals") or []):
            portal_total[p] = portal_total.get(p, 0) + 1
            if has_coords:
                portal_with_coords[p] = portal_with_coords.get(p, 0) + 1
    print("\nPer-portal lat/lng coverage:")
    for p in sorted(portal_total):
        t = portal_total[p]
        w = portal_with_coords.get(p, 0)
        print(f"  {p}: {w}/{t} ({100*w/t:.1f}%)")

    # 2. City_key/oblast_key distribution sanity check - is Cherven Bryag's
    # own area even represented anywhere?
    cherven_keys = [r for r in rows if r.get("city_key") and "cherven" in r["city_key"].lower()]
    print(f"\nRows with city_key containing 'cherven': {len(cherven_keys)}")

    # 3. Text search: does ANY listing's area field mention Cherven Bryag,
    # its municipality, or the surrounding oblast (Pleven/Lukovit) at all?
    # Server-side ilike filters (not a client-side scan of the full table -
    # listing_sources has no single orderable "id" column to keyset-
    # paginate through cheaply, so let Postgres do the filtering).
    needles_bg = ["червен бряг", "луковит"]
    needles_en = ["cherven bryag", "lukovit"]

    or_filter = ",".join([f"area.ilike.*{n}*" for n in needles_bg + needles_en])
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/merged_listings",
        headers=HEADERS,
        params={"select": "id,area,city_key,oblast_key,lat,lng,member_portals", "or": f"({or_filter})", "limit": 200},
        timeout=30,
    )
    resp.raise_for_status()
    area_matches = resp.json()
    print(f"\nmerged_listings rows whose 'area' field mentions Cherven Bryag/Lukovit: {len(area_matches)}")
    coords_among_matches = sum(1 for r in area_matches if r.get("lat") is not None and r.get("lng") is not None)
    print(f"  of those, with real lat/lng: {coords_among_matches}")
    print(f"  oblast_key values seen: {sorted(set(r.get('oblast_key') for r in area_matches))}")
    print(f"  city_key values seen: {sorted(set(r.get('city_key') for r in area_matches))}")
    for r in area_matches[:20]:
        print(f"    id={r['id']} area={r.get('area')!r} city_key={r.get('city_key')} "
              f"oblast_key={r.get('oblast_key')} lat={r.get('lat')} lng={r.get('lng')} "
              f"portals={r.get('member_portals')}")

    # 4. Also check listing_sources' own title/area fields directly (area
    # on merged_listings comes from just one representative source - a
    # different source in the same merged group might mention Cherven
    # Bryag in its own title/area even if the representative doesn't).
    resp2 = requests.get(
        f"{SUPABASE_URL}/rest/v1/listing_sources",
        headers=HEADERS,
        params={"select": "portal,source_id,title,area,lat,lng", "or": f"({or_filter})", "limit": 200},
        timeout=30,
    )
    resp2.raise_for_status()
    src_area_matches = resp2.json()
    print(f"\nlisting_sources rows mentioning Cherven Bryag/Lukovit: {len(src_area_matches)}")
    coords_among_src = sum(1 for r in src_area_matches if r.get("lat") is not None and r.get("lng") is not None)
    print(f"  of those, with real lat/lng: {coords_among_src}")
    for r in src_area_matches[:20]:
        print(f"    {r.get('portal')}/{r.get('source_id')}: title={r.get('title')!r} area={r.get('area')!r} "
              f"lat={r.get('lat')} lng={r.get('lng')}")

    # 5. Same again but searching title too, in case "area" itself never
    # carries the settlement name for some portals (e.g. a neighborhood-
    # only area value with the town only ever appearing in the title).
    or_filter_title = ",".join([f"title.ilike.*{n}*" for n in needles_bg + needles_en])
    resp3 = requests.get(
        f"{SUPABASE_URL}/rest/v1/listing_sources",
        headers=HEADERS,
        params={"select": "portal,source_id,title,area,lat,lng", "or": f"({or_filter_title})", "limit": 200},
        timeout=30,
    )
    resp3.raise_for_status()
    title_matches = resp3.json()
    print(f"\nlisting_sources rows whose TITLE mentions Cherven Bryag/Lukovit: {len(title_matches)}")
    for r in title_matches[:20]:
        print(f"    {r.get('portal')}/{r.get('source_id')}: title={r.get('title')!r} area={r.get('area')!r} "
              f"lat={r.get('lat')} lng={r.get('lng')}")


if __name__ == "__main__":
    main()
