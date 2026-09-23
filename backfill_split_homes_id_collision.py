"""
One-time, targeted backfill: splits the 2 homes.bg tracking IDs whose
interleaved price_history/full-record data was mechanically confirmed (via
`git log origin/main -- data/leads_homes.json data/history_homes.json`) to
be two entirely different listings collapsed onto one id by the type-prefix
bug fixed in scraper_homes.py's build_tracking_id().

Deliberately narrow: only touches homes_208381 and homes_205536 (the two
IDs with confirmed, unambiguous dual-record evidence - two cleanly
distinguishable full records with two cleanly distinguishable, non-
overlapping price values, observed directly in git history). homes_209031
is intentionally left untouched - see docs/decisions.md for why: no second
full-record variant was ever found for it in main's real history, unlike
the other two, so splitting it would mean guessing which of its price
points belongs to which listing rather than reading that off local
evidence - exactly the case this task says to leave to a human decision.

Rewrites ONLY the entries for these 2 ids in leads_homes.json/
history_homes.json - every other entry in both files is left byte-for-byte
untouched (deliberately not a full compute_leads() regeneration of the
whole dataset, which would also shift every other listing's now-relative
fields like days_on_market/source_status/score for reasons unrelated to
this bug).
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from geo_utils import compute_motivation_score

DATA_DIR = Path(__file__).parent / "data"
LEADS_FILE = DATA_DIR / "leads_homes.json"
HISTORY_FILE = DATA_DIR / "history_homes.json"
GONE_AFTER = timedelta(hours=20)
NOW = datetime.now(timezone.utc)

# (old collided id, [(new id, non-price fields, the one price value that
# belongs to this listing), ...]) - non-price fields and the confirmed
# price value for each side come straight from real git history (see
# docs/decisions.md's 2026-09-23 entry for the exact commits/evidence).
SPLITS = {
    "homes_208381": [
        (
            "homes_hs208381",
            233000,
            {
                "url": "https://www.homes.bg/offer/kyshta-za-prodazhba/kyshta-480m2-plovdiv-s.bogdan/hs208381",
                "photo": "https://g1.homes.bg/2025-09-26_2/115815834b.jpg",
                "photos": [
                    "https://g1.homes.bg/2025-09-26_2/115815834b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815836b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815837b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815839b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815841b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815843b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815845b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815846b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815848b.jpg",
                    "https://g1.homes.bg/2025-09-26_2/115815850b.jpg",
                ],
                "description": None,
                "sqm": 480,
                "area": "с.Богдан",
                "city": "Пловдив",
                "title": "Къща, 480m², с.Богдан, Пловдив",
                "portal": "homes.bg",
                "lat": None,
                "lng": None,
                "category": "house",
                "category_confidence": "high",
                "area_avg_price_per_sqm": 485,
                "pct_vs_area_avg": 0.0,
            },
        ),
        (
            "homes_lp208381",
            1227520,
            {
                "url": "https://www.homes.bg/offer/parcel-za-prodazhba/parcel-17536m2-varna-m-t-alen-mak/lp208381",
                "photo": "https://g1.homes.bg/2026-07-18_2/120134210b.jpg",
                "photos": [
                    "https://g1.homes.bg/2026-07-18_2/120134210b.jpg",
                    "https://g1.homes.bg/2026-07-18_2/120134211b.jpg",
                ],
                "description": "В регулация",
                "sqm": 17536,
                "area": "м-т Ален Мак",
                "city": "Варна",
                "title": "Парцел, 17536m², м-т Ален Мак, Варна",
                "portal": "homes.bg",
                "lat": None,
                "lng": None,
                "category": "land",
                "category_confidence": "high",
                "area_avg_price_per_sqm": 1619,
                "pct_vs_area_avg": -95.7,
            },
        ),
    ],
    "homes_205536": [
        (
            "homes_hs205536",
            210000,
            {
                "url": "https://www.homes.bg/offer/kyshta-za-prodazhba/kyshta-180m2-dobrich-gr.balchik/hs205536",
                "photo": "https://g1.homes.bg/2025-02-11_2/113005285b.jpg",
                "photos": [
                    "https://g1.homes.bg/2025-02-11_2/113005285b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005287b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005289b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005291b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005293b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005296b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005298b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005300b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005302b.jpg",
                    "https://g1.homes.bg/2025-02-11_2/113005304b.jpg",
                ],
                "description": None,
                "sqm": 180,
                "area": "гр.Балчик",
                "city": "Добрич",
                "title": "Къща, 180m², гр.Балчик, Добрич",
                "portal": "homes.bg",
                "lat": None,
                "lng": None,
                "category": "house",
                "category_confidence": "high",
                "area_avg_price_per_sqm": 1066,
                "pct_vs_area_avg": 9.5,
            },
        ),
        (
            "homes_lp205536",
            10500,
            {
                "url": "https://www.homes.bg/offer/parcel-za-prodazhba/parcel-1090m2-sofiya---grad-sofiya/lp205536",
                "photo": "https://g1.homes.bg/2026-01-30_1/117459057b.jpg",
                "photos": ["https://g1.homes.bg/2026-01-30_1/117459057b.jpg"],
                "description": None,
                "sqm": 1090,
                "area": "София",
                "city": "София - град",
                "title": "Парцел, 1090m², София, София - град",
                "portal": "homes.bg",
                "lat": None,
                "lng": None,
                "category": "land",
                "category_confidence": "high",
                "area_avg_price_per_sqm": 2530,
                "pct_vs_area_avg": -99.6,
            },
        ),
    ],
}


def split_snapshots(full_snapshots, price_value):
    return [s for s in full_snapshots if s.get("price_eur") == price_value]


# Mirrors scraper_homes.py's compute_leads() price_history derivation
# exactly (see that function for the full rationale) - price_history only
# ever gets an entry when the price actually changes from the previous
# snapshot, every other raw snapshot is a same-price re-observation and is
# collapsed away. history_homes.json's `snapshots`, by contrast, keeps
# every observation (post prune_snapshots(): first, every real change, and
# the single most recent one, unconditionally) - the two lists are NOT
# interchangeable, which is exactly the bug this rework fixes. A snapshot
# tagged source="relisted_from" is never emitted for these split ids (that
# tag only exists on live-tracked ids that detect_relistings.py/
# detect_relistings_by_photo.py have matched, not on this one-time split's
# frozen historical data) but the handling is kept anyway for parity with
# the real derivation logic rather than shipping a partial copy of it.
def dedup_price_history(snapshots):
    price_history = []
    last_price = None
    for s in snapshots:
        p = s.get("price_eur")
        is_relisting = s.get("source") == "relisted_from"
        if not p or (p == last_price and not is_relisting):
            continue
        entry = {"date": s["seen_at"], "price_eur": p}
        if is_relisting:
            entry["source"] = "relisted_from"
            entry["relisted_from"] = s["relisted_from"]
            if s.get("came_back_at"):
                entry["came_back_at"] = s["came_back_at"]
            if s.get("came_back_price") is not None:
                entry["came_back_price"] = s["came_back_price"]
        price_history.append(entry)
        last_price = p
    return price_history


def build_split_lead(new_id, price_value, fields, full_snapshots):
    snaps = split_snapshots(full_snapshots, price_value)
    if not snaps:
        raise ValueError(f"{new_id}: no snapshots match price {price_value}")
    first_seen = datetime.fromisoformat(snaps[0]["seen_at"])
    last_seen = datetime.fromisoformat(snaps[-1]["seen_at"])
    source_status = "active" if (NOW - last_seen) <= GONE_AFTER else "removed"
    effective_now = last_seen if source_status == "removed" else NOW
    days_on_market = (effective_now - first_seen).days
    # Same-price-per-split-group by construction (split_snapshots() filters
    # to one exact price value), so first/last price here are always equal
    # and drop_pct/price_drop_count are always 0 - real finding (see
    # docs/decisions.md), not a bug: neither underlying listing's price
    # ever actually changed, the "price oscillates wildly" symptom that
    # opened backlog item 23 was 100% the id-collision artifact.
    first_price, last_price = snaps[0]["price_eur"], snaps[-1]["price_eur"]
    drop_pct = round((first_price - last_price) / first_price * 100, 1) if first_price else 0
    ph = dedup_price_history(snaps)
    price_drop_count = sum(
        1 for i in range(1, len(ph)) if ph[i]["price_eur"] < ph[i - 1]["price_eur"]
    )
    sqm = fields["sqm"]
    price_per_sqm = round(last_price / sqm) if sqm else None
    pct_vs_area_avg = fields["pct_vs_area_avg"]

    lead = {
        "id": new_id,
        "url": fields["url"],
        "photo": fields["photo"],
        "photos": fields["photos"],
        "description": fields["description"],
        "price_eur": last_price,
        "sqm": sqm,
        "area": fields["area"],
        "city": fields["city"],
        "title": fields["title"],
        "portal": fields["portal"],
        "lat": fields["lat"],
        "lng": fields["lng"],
        "category": fields["category"],
        "category_confidence": fields["category_confidence"],
        "price_per_sqm": price_per_sqm,
        "price_history": ph,
        "price_drop_count": price_drop_count,
        "drop_pct": drop_pct,
        "days_on_market": days_on_market,
        "source_status": source_status,
        "removed_at": last_seen.isoformat() if source_status == "removed" else None,
        "area_avg_price_per_sqm": fields["area_avg_price_per_sqm"],
        "pct_vs_area_avg": pct_vs_area_avg,
    }
    lead["score"] = compute_motivation_score(
        drop_pct, price_drop_count, days_on_market, pct_vs_area_avg, ph
    )
    return lead, {"first_seen": first_seen.isoformat(), "snapshots": snaps, "latest": {
        "id": new_id,
        "url": fields["url"],
        "photo": fields["photo"],
        "photos": fields["photos"],
        "description": fields["description"],
        "price_eur": last_price,
        "sqm": sqm,
        "area": fields["area"],
        "city": fields["city"],
        "title": fields["title"],
        "portal": fields["portal"],
        "lat": fields["lat"],
        "lng": fields["lng"],
        "category": fields["category"],
        "category_confidence": fields["category_confidence"],
    }}


def main():
    leads = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
    history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))

    leads_by_id = {l["id"]: i for i, l in enumerate(leads)}

    for old_id, splits in SPLITS.items():
        if old_id not in leads_by_id:
            raise SystemExit(f"{old_id} not found in {LEADS_FILE} - nothing to split, aborting")
        if old_id not in history:
            raise SystemExit(f"{old_id} not found in {HISTORY_FILE} - nothing to split, aborting")
        # Source of truth for the split is history_homes.json's OWN
        # pre-split `snapshots` list, not leads_homes.json's `price_history`.
        # The two diverge whenever a listing was re-scraped at an unchanged
        # price: `price_history` only appends on a real price change, while
        # `snapshots` logs every scrape observation. Splitting off the
        # shorter, already-deduped `price_history` here would silently drop
        # real snapshots (confirmed for homes_208381: 24 real snapshots vs.
        # only 23 price_history entries - the missing one was homes_208381's
        # most recent observation, which flipped its correct source_status
        # from "active" to a wrongly stale "removed"). See docs/decisions.md
        # for the full re-verification.
        full_snapshots = history[old_id]["snapshots"]

        new_leads = []
        new_history_entries = {}
        covered = 0
        for new_id, price_value, fields in splits:
            lead, hist_entry = build_split_lead(new_id, price_value, fields, full_snapshots)
            covered += len(hist_entry["snapshots"])
            new_leads.append(lead)
            new_history_entries[new_id] = hist_entry

        if covered != len(full_snapshots):
            raise SystemExit(
                f"{old_id}: split snapshots ({covered}) don't add up to the "
                f"original history_homes.json snapshot count ({len(full_snapshots)}) - "
                f"refusing to write a lossy split"
            )

        # Remove the old collided lead, insert the split ones.
        idx = leads_by_id[old_id]
        del leads[idx]
        leads.extend(new_leads)

        # Same for history_homes.json.
        del history[old_id]
        history.update(new_history_entries)

        print(f"Split {old_id} -> {[l['id'] for l in new_leads]} "
              f"(snapshots: {[len(h['snapshots']) for h in new_history_entries.values()]}, "
              f"deduped price_history: {[len(l['price_history']) for l in new_leads]}, "
              f"{covered}/{len(full_snapshots)} snapshots accounted for)")

    LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
