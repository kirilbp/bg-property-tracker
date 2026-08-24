"""
Computes the same cross-portal-deduped view index.html's groupListings()
computes client-side (ported 1:1 from index.html: same CYR_TO_LAT
transliteration table, same normalizeArea/areasMatch/pricesMatch rules, same
two-pass no-bridging-through-sqm-less-listings union-find, same
BCPEA_TYPE_LOOKUP/BG_CITIES type-bucket and city-key logic - verified against
the real algorithm in index.html, not reimplemented from scratch), and
upserts it into Supabase (listing_sources + merged_listings) so the frontend
can query just what it needs server-side instead of shipping every
scraper's whole JSON file to the browser on every page load.

A merged listing's id is a deterministic hash of its sorted member
(portal, source_id) pairs - NOT "whichever source currently scores highest"
(today's in-browser approach), which drifts day to day as days_on_market
changes and silently breaks bookmarked #/listing/<id> links. A group's id
only changes when its actual membership changes.

Reads the 8 already-committed data/leads_*.json files - the scrapers
themselves are unchanged, JSON stays the source of truth and safety net.
This script only writes to Supabase.

Auth: SUPABASE_URL and SUPABASE_SECRET_KEY must be set as environment
variables (GitHub Actions repo secrets in production). The secret key
bypasses Row Level Security entirely (see supabase/schema.sql, which has no
write policies at all), so it must never reach the browser or be written to
disk/committed - only ever passed in via the environment.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"

PORTAL_FILES = {
    "imoti.net": "leads.json",
    "alo.bg": "leads_alo.json",
    "homes.bg": "leads_homes.json",
    "imot.bg": "leads_imot.json",
    "olx.bg": "leads_olx.json",
    "bazar.bg": "leads_bazar.json",
    "imoti.bg": "leads_imoti_bg.json",
    "sales.bcpea.org": "leads_bcpea.json",
}

# --- Cross-portal duplicate detection - ported 1:1 from index.html --------
# (index.html:1163-1303 - see that file's own comments for the reasoning
# behind every rule here; this is a straight port, not a redesign.)

CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sht", "ъ": "a", "ь": "", "ю": "yu", "я": "ya",
}


def transliterate(s):
    return "".join(CYR_TO_LAT.get(c, c) for c in s)


AREA_PREFIX_RE = re.compile(r"^(v|kv\.?|zh\.?k?\.?)\s+")


def normalize_area(area):
    if not area:
        return ""
    s = transliterate(area.lower().strip())
    for _ in range(3):
        s = AREA_PREFIX_RE.sub("", s).strip()
    return s


def areas_match(a1, a2):
    n1, n2 = normalize_area(a1), normalize_area(a2)
    return bool(n1) and n1 == n2


def prices_match(p1, p2):
    if not p1 or not p2:
        return False
    return abs(p1 - p2) <= 1


def group_listings(all_listings):
    with_sqm = [l for l in all_listings if l.get("sqm")]
    without_sqm = [l for l in all_listings if not l.get("sqm")]

    price_buckets = {}
    for l in with_sqm:
        key = round(l.get("price_eur") or 0)
        price_buckets.setdefault(key, []).append(l)

    parent = {id(l): l for l in with_sqm}

    def find(x):
        while parent[id(x)] is not x:
            parent[id(x)] = parent[id(parent[id(x)])]
            x = parent[id(x)]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra is not rb:
            parent[id(ra)] = rb

    for l in with_sqm:
        key = round(l.get("price_eur") or 0)
        for dk in (-1, 0, 1):
            bucket = price_buckets.get(key + dk)
            if not bucket:
                continue
            for other in bucket:
                if other is l or l["portal"] == other["portal"]:
                    continue
                if (
                    prices_match(l.get("price_eur"), other.get("price_eur"))
                    and abs(l["sqm"] - other["sqm"]) <= 1
                    and areas_match(l.get("area"), other.get("area"))
                ):
                    union(l, other)

    groups_by_root = {}
    for l in with_sqm:
        root = find(l)
        groups_by_root.setdefault(id(root), []).append(l)
    groups = list(groups_by_root.values())

    group_buckets = {}
    for g in groups:
        key = round(g[0].get("price_eur") or 0)
        group_buckets.setdefault(key, []).append(g)

    solo_sqmless = []
    for l in without_sqm:
        key = round(l.get("price_eur") or 0)
        attached = False
        for dk in (-1, 0, 1):
            candidates = group_buckets.get(key + dk)
            if not candidates:
                continue
            for group in candidates:
                if any(m["portal"] == l["portal"] for m in group):
                    continue
                rep = group[0]
                if prices_match(l.get("price_eur"), rep.get("price_eur")) and areas_match(
                    l.get("area"), rep.get("area")
                ):
                    group.append(l)
                    attached = True
                    break
            if attached:
                break
        if not attached:
            solo_sqmless.append([l])

    return groups + solo_sqmless


# --- Type buckets + city keys - ported 1:1 from index.html ----------------

BCPEA_RAW_TYPES = [
    ("flat", ["Едностаен апартамент", "Двустаен апартамент", "Тристаен апартамент",
              "Многостаен апартамент", "Мезонет", "Ателие, Таван", "Стая"]),
    ("house", ["Вила", "Етаж от къща", "Къща", "Жилищна сграда", "Къща с парцел"]),
    ("land", ["Парцел", "Земеделска земя", "Земеделски имот", "Парцел с къща"]),
    ("garage", ["Гараж", "Паркомясто"]),
    ("shop", ["Магазин", "Заведение"]),
    ("business", ["Офис", "Склад", "Фабрика", "Хотел", "Търговски имот",
                  "Производствен имот", "Бензиностанция", "Газстанция", "Автомивка"]),
]
# Longest raw type first, so a type string that's a prefix of another (e.g.
# "Къща" vs "Къща с парцел") always resolves to the more specific one.
BCPEA_TYPE_LOOKUP = sorted(
    ((raw_type, key) for key, raw_types in BCPEA_RAW_TYPES for raw_type in raw_types),
    key=lambda pair: -len(pair[0]),
)

CATEGORY_TO_BUCKET = {"apartment": "flat", "house": "house", "land": "land", "commercial": "business"}


def bcpea_type_match(title):
    if not title:
        return None
    for raw_type, key in BCPEA_TYPE_LOOKUP:
        if title.startswith(raw_type):
            return raw_type, key
    return None


def type_filter_bucket(l):
    if l.get("portal") == "sales.bcpea.org":
        match = bcpea_type_match(l.get("title"))
        return match[1] if match else "other"
    return CATEGORY_TO_BUCKET.get(l.get("category"), "other")


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
BG_CITY_BY_NAME = {name: key for key, name in BG_CITIES}


def bcpea_settlement_from_title(title):
    match = bcpea_type_match(title)
    if not match:
        return None
    raw_type, _ = match
    rest = title[len(raw_type):]
    return re.sub(r"^,\s*", "", rest).strip() or None


def listing_city_key(l):
    if l.get("portal") != "sales.bcpea.org":
        return "sofia"
    settlement = bcpea_settlement_from_title(l.get("title"))
    return BG_CITY_BY_NAME.get(settlement) if settlement else None


# --- Load, merge, shape rows -----------------------------------------------

def load_all_listings():
    all_listings = []
    for portal, filename in PORTAL_FILES.items():
        path = DATA_DIR / filename
        if not path.exists():
            print(f"WARNING: {path} not found, skipping {portal}")
            continue
        listings = json.loads(path.read_text(encoding="utf-8"))
        for l in listings:
            l.setdefault("portal", portal)
        all_listings.extend(listings)
    return all_listings


def merged_id_for(sources):
    members = sorted(f"{s['portal']}:{s['id']}" for s in sources)
    digest = hashlib.sha256(",".join(members).encode("utf-8")).hexdigest()
    return "m_" + digest[:16]


# Every field a listing_sources/merged_listings row copies straight from a
# leads_*.json entry, confirmed against the real union of keys actually
# present across all 8 committed files (not guessed from scraper source).
# "id" and "portal" are handled separately (source_id / portal columns).
SOURCE_FIELDS = [
    "url", "photo", "photos", "price_eur", "sqm", "area", "title", "description",
    "category", "lat", "lng", "price_per_sqm", "price_history", "price_drop_count",
    "drop_pct", "days_on_market", "score", "source_status", "removed_at",
    "area_avg_price_per_sqm", "pct_vs_area_avg", "site_updated_at", "site_posted_at",
]


def build_rows(all_listings):
    groups = group_listings(all_listings)

    listing_source_rows = []
    merged_rows = []

    for sources in groups:
        sorted_sources = sorted(sources, key=lambda s: s.get("score") or 0, reverse=True)
        status = "sold" if all(s.get("source_status") == "removed" for s in sorted_sources) else "available"
        mid = merged_id_for(sorted_sources)

        for s in sorted_sources:
            row = {"portal": s["portal"], "source_id": s["id"], "merged_id": mid}
            for f in SOURCE_FIELDS:
                row[f] = s.get(f)
            row["type_bucket"] = type_filter_bucket(s)
            row["city_key"] = listing_city_key(s)
            listing_source_rows.append(row)

        best = sorted_sources[0]
        merged = {
            "id": mid,
            "portal": best["portal"],
            "status": status,
            "member_count": len(sorted_sources),
            "member_portals": sorted({s["portal"] for s in sorted_sources}),
        }
        for f in SOURCE_FIELDS:
            merged[f] = best.get(f)
        merged["type_bucket"] = type_filter_bucket(best)
        merged["city_key"] = listing_city_key(best)
        merged_rows.append(merged)

    return listing_source_rows, merged_rows


# --- Supabase REST upsert ---------------------------------------------------

BATCH_SIZE = 500


def upsert(base_url, headers, table, rows, on_conflict):
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        resp = requests.post(
            f"{base_url}/rest/v1/{table}?on_conflict={on_conflict}",
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=batch,
            timeout=60,
        )
        if not resp.ok:
            print(f"ERROR upserting into {table} (batch starting at {i}): {resp.status_code} {resp.text[:500]}")
            resp.raise_for_status()
        print(f"  upserted {len(batch)} rows into {table} ({min(i + len(batch), len(rows))}/{len(rows)})")


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not secret_key:
        print("SUPABASE_URL and SUPABASE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)

    headers = {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }

    all_listings = load_all_listings()
    print(f"Loaded {len(all_listings)} raw listings across {len(PORTAL_FILES)} portals")

    listing_source_rows, merged_rows = build_rows(all_listings)
    print(f"Computed {len(merged_rows)} merged listings from {len(listing_source_rows)} sources")

    upsert(supabase_url.rstrip("/"), headers, "listing_sources", listing_source_rows, on_conflict="portal,source_id")
    upsert(supabase_url.rstrip("/"), headers, "merged_listings", merged_rows, on_conflict="id")

    print("Sync complete")


if __name__ == "__main__":
    main()
