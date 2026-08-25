"""
Diagnostic: fetch every merged_listings row's city_key directly from
Supabase and print the distribution, to confirm a fix actually landed.

Read-only. Only ever run via workflow_dispatch, never scheduled.
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


def fetch_all(base_url, headers):
    rows = []
    offset = 0
    batch = 1000
    while True:
        resp = requests.get(
            f"{base_url}/rest/v1/merged_listings",
            headers={**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + batch - 1}"},
            params={"select": "id,city_key,status"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < batch:
            break
        offset += batch
    return rows


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not secret_key:
        print("SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)

    headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}
    rows = fetch_all(supabase_url, headers)
    print(f"Total merged_listings rows: {len(rows)}", flush=True)

    active = [r for r in rows if r.get("status") == "available"]
    print(f"Active (available): {len(active)}", flush=True)

    counts_all = {}
    counts_active = {}
    for r in rows:
        k = r.get("city_key")
        counts_all[k] = counts_all.get(k, 0) + 1
        if r.get("status") == "available":
            counts_active[k] = counts_active.get(k, 0) + 1

    print("\n=== ALL rows (active + sold) ===", flush=True)
    for key, label in BG_CITIES:
        print(f"{label} ({key}): {counts_all.get(key, 0)}", flush=True)
    print(f"unmatched (None): {counts_all.get(None, 0)}", flush=True)

    print("\n=== ACTIVE-ONLY rows ===", flush=True)
    for key, label in BG_CITIES:
        print(f"{label} ({key}): {counts_active.get(key, 0)}", flush=True)
    print(f"unmatched (None): {counts_active.get(None, 0)}", flush=True)


if __name__ == "__main__":
    main()
