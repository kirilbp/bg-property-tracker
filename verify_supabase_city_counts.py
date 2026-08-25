"""
Diagnostic: fetch every merged_listings row's city_key directly from
Supabase (the live table the frontend's Browse-by-city panel queries) and
print the real distribution, to confirm whether the site's displayed
counts genuinely reflect what's in the table right now - the user reports
the panel shows the exact same numbers before and after a full nationwide
scrape+sync completed, which would mean either the table itself didn't
really change the way expected, or the frontend isn't actually reading
current table state. This script bypasses the frontend entirely and reads
the table straight, using the same service-role auth sync_to_supabase.py
uses, so it's authoritative for "what's actually in the table."

Read-only: does not touch the table's contents. Only ever run via
workflow_dispatch, never scheduled.
"""

import os
import sys

import requests

BG_CITIES = [
    ("sofia", "София"), ("plovdiv", "Пловдив"), ("varna", "Варна"), ("burgas", "Бургас"),
    ("ruse", "Русе"), ("stara_zagora", "Стара Загора"), ("pleven", "Плевен"), ("sliven", "Сливен"),
    ("dobrich", "Добрич"), ("shumen", "Шумен"), ("pernik", "Перник"), ("haskovo", "Хасково"),
    ("yambol", "Ямбол"), ("pazardzhik", "Пазарджик"), ("blagoevgrad", "Благоевград"),
    ("veliko_tarnovo", "Велико Търново"), ("vratsa", "Враца"), ("gabrovo", "Габрово"),
    ("vidin", "Видин"), ("asenovgrad", "Асеновград"), ("kazanlak", "Казанлък"),
    ("kyustendil", "Кюстендил"), ("kardzhali", "Кърджали"), ("montana", "Монтана"),
    ("dimitrovgrad", "Димитровград"), ("targovishte", "Търговище"), ("lovech", "Ловеч"),
    ("silistra", "Силистра"), ("dupnitsa", "Дупница"), ("svishtov", "Свищов"),
]
KEY_TO_LABEL = {k: n for k, n in BG_CITIES}


def fetch_all_city_keys(base_url, headers):
    keys = []
    offset = 0
    batch = 1000
    while True:
        resp = requests.get(
            f"{base_url}/rest/v1/merged_listings",
            headers={**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + batch - 1}"},
            params={"select": "id,city_key"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        keys.extend(row.get("city_key") for row in page)
        print(f"DEBUG: fetched {len(keys)} rows so far", flush=True)
        if len(page) < batch:
            break
        offset += batch
    return keys


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not secret_key:
        print("SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)

    headers = {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
    }

    keys = fetch_all_city_keys(supabase_url, headers)
    print(f"\nTotal merged_listings rows fetched: {len(keys)}", flush=True)

    counts = {}
    for k in keys:
        counts[k] = counts.get(k, 0) + 1

    print("\n=== Real city_key distribution in merged_listings RIGHT NOW ===", flush=True)
    for key, label in BG_CITIES:
        print(f"{label} ({key}): {counts.get(key, 0)}", flush=True)

    other_keys = set(counts) - {k for k, _ in BG_CITIES}
    if other_keys:
        print("\n=== city_key values NOT in the canonical 30-city list (bug signal) ===", flush=True)
        for k in sorted(other_keys, key=lambda x: -counts[x]):
            print(f"{k!r}: {counts[k]}", flush=True)


if __name__ == "__main__":
    main()
