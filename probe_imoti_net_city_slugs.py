"""
Diagnostic-only: round 3 for the imoti.net nationwide conversion. No
server-rendered location list was found (round 2) - the location picker
is JS-driven, not something readable from the static HTML. But round 1
already confirmed "plovdiv" works as a direct lowercase-transliterated
guess alongside "sofia", so this tests the same transliterated-slug
pattern against all 30 cities already tracked elsewhere in this project
(index.html's BG_CITIES) - if most/all resolve with real content, that's
a solid, verifiable nationwide city list without needing to reverse-
engineer the JS location widget the way homes.bg's typeId needed.

Also fixes the previous round's listing-count bug: matching the raw regex
against the whole HTML text (with a ^ anchor) only ever matched at
position 0, undercounting. This checks each <a href> individually, same
approach the real scraper.py uses.

Read-only, no commit step - deleted once the question is answered.
"""

import re
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
BASE = "https://www.imoti.net/en/obiavi/r/prodava"
LISTING_LINK_RE = re.compile(r'^/en/obiava/prodava[^"\'#]*?/(\d+)/')

# Same 30 cities as index.html's BG_CITIES, with a plausible transliterated
# slug guess for each (lowercase, spaces -> hyphens, common BG->EN mapping).
CITY_SLUGS = [
    ("sofia", "Sofia"), ("plovdiv", "Plovdiv"), ("varna", "Varna"), ("burgas", "Burgas"),
    ("ruse", "Ruse"), ("stara-zagora", "Stara Zagora"), ("pleven", "Pleven"), ("sliven", "Sliven"),
    ("dobrich", "Dobrich"), ("shumen", "Shumen"), ("pernik", "Pernik"), ("haskovo", "Haskovo"),
    ("yambol", "Yambol"), ("pazardzhik", "Pazardzhik"), ("blagoevgrad", "Blagoevgrad"),
    ("veliko-tarnovo", "Veliko Tarnovo"), ("vratsa", "Vratsa"), ("gabrovo", "Gabrovo"),
    ("vidin", "Vidin"), ("asenovgrad", "Asenovgrad"), ("kazanlak", "Kazanlak"),
    ("kyustendil", "Kyustendil"), ("kardzhali", "Kardzhali"), ("montana", "Montana"),
    ("dimitrovgrad", "Dimitrovgrad"), ("targovishte", "Targovishte"), ("lovech", "Lovech"),
    ("silistra", "Silistra"), ("dupnitsa", "Dupnitsa"), ("svishtov", "Svishtov"),
]

session = requests.Session()
working = []
for slug, label in CITY_SLUGS:
    url = f"{BASE}/{slug}"
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = [a for a in soup.find_all("a", href=True) if LISTING_LINK_RE.search(a["href"])]
        print(f"  {label} ({slug}): status={resp.status_code} listing_links={len(links)} len={len(resp.text)}")
        if resp.status_code == 200 and links:
            working.append((slug, label, len(links)))
    except requests.RequestException as e:
        print(f"  {label} ({slug}): REQUEST FAILED: {e}")
    time.sleep(0.6)

print(f"\n=== {len(working)}/{len(CITY_SLUGS)} city slugs resolved with real listings ===")
for slug, label, n in working:
    print(f"  {label}: {n} listings on page 1")

print("\ndone")
