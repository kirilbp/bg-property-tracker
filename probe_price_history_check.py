"""
Diagnostic: sample real merged_listings rows with a non-trivial
price_history to confirm price movements are actually being recorded
end-to-end into the live database, not just correct in the scraper code.
"""

import requests

SUPABASE_URL = "https://eoufgmmgwczixfajebhc.supabase.co"
ANON_KEY = "sb_publishable_8m7t7ejFdAr9wWqxz26fcw_LUWURIcL"
HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}


def main():
    url = f"{SUPABASE_URL}/rest/v1/merged_listings"
    params = {
        "select": "id,portal,price_eur,price_drop_count,drop_pct,price_history,days_on_market",
        "price_drop_count": "gt.0",
        "limit": "10",
        "order": "price_drop_count.desc",
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    print(f"status: {resp.status_code}")
    if resp.status_code >= 400:
        print(resp.text[:300])
        return
    rows = resp.json()
    print(f"rows with price_drop_count > 0: {len(rows)}")
    for r in rows:
        ph = r.get("price_history") or []
        print(f"  id={r['id']} portal={r['portal']} price_drop_count={r['price_drop_count']} "
              f"days_on_market={r['days_on_market']} price_history_len={len(ph)}")
        for p in ph[:5]:
            print(f"    {p}")

    # Also check overall: how many merged_listings have a price_history with 2+ entries at all
    params2 = {"select": "id", "price_drop_count": "gt.0", "limit": "0"}
    headers2 = {**HEADERS, "Range-Unit": "items", "Range": "0-0", "Prefer": "count=exact"}
    resp2 = requests.get(url, headers=headers2, params={"price_drop_count": "gt.0", "select": "id"}, timeout=30)
    print(f"\ncount with price_drop_count > 0: status={resp2.status_code} Content-Range={resp2.headers.get('Content-Range')}")


if __name__ == "__main__":
    main()
