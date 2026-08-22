import re
import requests

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

CANDIDATES = {
    "imoti.net": "https://www.imoti.net/en/obiavi/r/prodava",
    "alo.bg": "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/",
    "bazar.bg": "https://bazar.bg/obiavi/prodazhba-apartamenti",
    "imoti.bg": "https://imoti.bg/продажби/cu:BGN",
    "homes.bg": "https://www.homes.bg/",
}

for name, url in CANDIDATES.items():
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"=== {name} === {url}")
        print(f"status={r.status_code} len={len(r.text)}")
        for m in re.finditer(r'([\d\s,\.]{2,10})\s*(обяви|resultat|results|listings|imota|imoti|обявени)', r.text, re.IGNORECASE):
            print("  match:", m.group(0)[:60])
        for m in re.finditer(r'(намерени|открихме|found)[^\d]{0,20}([\d\s,\.]{2,10})', r.text, re.IGNORECASE):
            print("  match2:", m.group(0)[:60])
        if name == "homes.bg":
            m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", r.text, re.DOTALL)
            if m:
                import json
                state = json.loads(m.group(1))
                offers = state.get("data", {}).get("offers", {})
                print("  searchCriteria:", state.get("data", {}).get("searchCriteria"))
                print("  offers keys:", list(offers.keys()))
                print("  totalCount-ish:", {k: v for k, v in offers.items() if isinstance(v, (int, str)) and k != "result"})
    except Exception as e:
        print(f"=== {name} === FAILED: {e}")
    print()
