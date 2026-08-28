"""
One-shot probe: does ANY listing near Cherven Bryag (Pleven oblast,
Lukovit municipality) exist at all, and if so, why doesn't it have
coordinates? Uses the indexed oblast_key column (cheap) instead of a
full-table ILIKE scan (what crashed probe_latlng_coverage.py's second
query with a statement timeout on the pre-cleanup, still-bloated table).

Not part of the scraper pipeline - dispatched by hand, read once, then
deleted.
"""

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}


def main():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/merged_listings",
        headers=HEADERS,
        params={
            "select": "id,area,city_key,lat,lng,member_portals,price_eur",
            "oblast_key": "eq.pleven",
            "limit": 5000,
        },
        timeout=60,
    )
    resp.raise_for_status()
    rows = resp.json()
    print(f"merged_listings rows with oblast_key=pleven: {len(rows)}")

    with_coords = [r for r in rows if r.get("lat") is not None]
    print(f"  of those, with real lat/lng: {len(with_coords)}")

    needles = ["червен бряг", "cherven bryag", "луковит", "lukovit"]

    def matches(r):
        return any(n in (r.get("area") or "").lower() for n in needles)

    hits = [r for r in rows if matches(r)]
    print(f"\nRows whose area mentions Cherven Bryag/Lukovit: {len(hits)}")
    for r in hits[:30]:
        print(f"  id={r['id']} area={r.get('area')!r} city_key={r.get('city_key')} "
              f"lat={r.get('lat')} lng={r.get('lng')} price={r.get('price_eur')} portals={r.get('member_portals')}")

    # City_key distribution within Pleven oblast, to see what settlement
    # names ARE present (sanity check that Pleven-area data exists at all,
    # even if not exactly "Cherven Bryag").
    city_keys = {}
    for r in rows:
        ck = r.get("city_key") or "(none)"
        city_keys[ck] = city_keys.get(ck, 0) + 1
    print("\ncity_key distribution within oblast_key=pleven:")
    for ck, count in sorted(city_keys.items(), key=lambda x: -x[1])[:20]:
        print(f"  {ck}: {count}")

    # Sample a few raw area strings that don't match any known city_key
    # (city_key is None / falls into "Others") to see what they actually
    # say - might reveal Cherven Bryag under a spelling/format this probe's
    # needle list doesn't catch.
    unclassified = [r for r in rows if not r.get("city_key")]
    print(f"\nRows in Pleven oblast with no city_key (small-town 'Others' bucket): {len(unclassified)}")
    for r in unclassified[:30]:
        print(f"  area={r.get('area')!r} lat={r.get('lat')} lng={r.get('lng')}")


if __name__ == "__main__":
    main()
