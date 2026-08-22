import json

for name in ["leads_homes.json", "leads_olx.json"]:
    data = json.load(open("data/" + name, encoding="utf-8"))
    print(f"=== {name}: {len(data)} leads ===")
    for l in data[:5]:
        print(
            f"  id={l['id']} days_on_market={l.get('days_on_market')} "
            f"score={l.get('score')} site_updated_at={l.get('site_updated_at')} "
            f"photos={len(l.get('photos') or [])} has_description={bool(l.get('description'))}"
        )
    zero_days = sum(1 for l in data if l.get("days_on_market") == 0)
    print(f"  listings with days_on_market == 0: {zero_days}/{len(data)}")
