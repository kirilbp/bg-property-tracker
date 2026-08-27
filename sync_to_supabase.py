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
import math
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
    # A flat 1 EUR tolerance was missing real cross-posted duplicates: BGN
    # (Bulgaria's currency, pegged to EUR at a fixed rate) to EUR display
    # conversion rounds slightly differently portal to portal, and a
    # listing scraped a few hours apart can catch one portal just before a
    # price update and another just after - both produce the exact same
    # real listing showing two slightly different EUR prices. Live-sampled:
    # cross-portal pairs that already match on area+sqm have a median price
    # gap of 0.75% when they differ at all - 0.5% is a conservative cut
    # that catches genuine rounding/timing drift without reaching into the
    # long tail (some pairs differ by 10-20%) that's more likely two
    # actually-different apartments coincidentally sharing an area+sqm.
    tolerance = max(1, round(max(p1, p2) * 0.005))
    return abs(p1 - p2) <= tolerance


# prices_match()'s tolerance is now relative (0.5% of price), so a fixed
# +/-1-whole-euro bucket search radius no longer covers it at any real
# price (0.5% of EUR200,000 is EUR1,000) - bucketing by price directly and
# scanning a wider absolute radius would need a radius that scales per
# listing, which is expensive to search efficiently. Bucketing in LOG space
# instead makes tolerance-width constant regardless of price magnitude: a
# 0.5% price change is *always* the same fixed distance in log space, so
# checking the same fixed handful of neighboring buckets (dk in a small
# fixed range) finds every match at every price level in one pass.
_PRICE_LOG_BUCKET_WIDTH = math.log(1 + 0.005)


def price_bucket_key(price):
    return round(math.log(max(price or 0, 1)) / _PRICE_LOG_BUCKET_WIDTH)


def group_listings(all_listings):
    with_sqm = [l for l in all_listings if l.get("sqm")]
    without_sqm = [l for l in all_listings if not l.get("sqm")]

    # Bucketing by price alone puts every listing near a common round price
    # (e.g. exactly 100,000 EUR - very common in this market) into one
    # enormous bucket regardless of area, since the 0.5% tolerance band
    # covers a lot of listings at popular price points - live-measured,
    # some single price buckets held 1,000+ listings, making the O(bucket²)
    # pairwise comparison pass effectively hang. areas_match() already
    # requires an exact normalized-string match, not a fuzzy one, so
    # co-bucketing by (price bucket, normalized area) loses no matches
    # a plain price bucket would have found - it only pre-applies a filter
    # every surviving pair already had to pass anyway, and area names are
    # far more differentiating than price, keeping real buckets small.
    price_buckets = {}
    for l in with_sqm:
        na = normalize_area(l.get("area"))
        if not na:
            continue
        key = (price_bucket_key(l.get("price_eur")), na)
        price_buckets.setdefault(key, []).append(l)

    parent = {id(l): l for l in with_sqm}
    # Tracks each group's current [min_sqm, max_sqm] span, keyed by the
    # current root's id - a candidate union is only allowed if it keeps the
    # group's overall span within the same +/-1 sqm tolerance every
    # individual pairwise match already enforces. Without this, a chain of
    # listings each 1 sqm apart from a neighbor (95-96, 96-97, 97-98)
    # transitively unions into one group spanning 3 sqm - a real, live-
    # found false-merge bug: a Varna new-construction development selling
    # ~39 distinct units at the same round price with sqm varying by a
    # couple square meters was collapsing into a single "merged" listing.
    sqm_range = {id(l): (l["sqm"], l["sqm"]) for l in with_sqm}
    # Same transitive-drift risk as sqm, same fix: without tracking the
    # group's own price span, a chain of pairwise-tolerable price hops
    # (each within prices_match() of a neighbor) can drift the group's
    # overall min-to-max price spread well past that same tolerance.
    price_range = {id(l): (l["price_eur"], l["price_eur"]) for l in with_sqm}

    def find(x):
        while parent[id(x)] is not x:
            parent[id(x)] = parent[id(parent[id(x)])]
            x = parent[id(x)]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra is rb:
            return
        lo_sqm = min(sqm_range[id(ra)][0], sqm_range[id(rb)][0])
        hi_sqm = max(sqm_range[id(ra)][1], sqm_range[id(rb)][1])
        if hi_sqm - lo_sqm > 1:
            return
        lo_price = min(price_range[id(ra)][0], price_range[id(rb)][0])
        hi_price = max(price_range[id(ra)][1], price_range[id(rb)][1])
        if not prices_match(lo_price, hi_price):
            return
        parent[id(ra)] = rb
        sqm_range[id(rb)] = (lo_sqm, hi_sqm)
        price_range[id(rb)] = (lo_price, hi_price)

    for l in with_sqm:
        na = normalize_area(l.get("area"))
        if not na:
            continue
        key = price_bucket_key(l.get("price_eur"))
        # +/-2 buckets of margin around the 1-bucket-wide tolerance itself,
        # to absorb rounding at a bucket edge (two prices genuinely within
        # tolerance can still land in adjacent buckets if one rounds down
        # and the other rounds up right at the boundary).
        for dk in range(-2, 3):
            bucket = price_buckets.get((key + dk, na))
            if not bucket:
                continue
            for other in bucket:
                if other is l or l["portal"] == other["portal"]:
                    continue
                if (
                    prices_match(l.get("price_eur"), other.get("price_eur"))
                    and abs(l["sqm"] - other["sqm"]) <= 1
                ):
                    union(l, other)

    groups_by_root = {}
    for l in with_sqm:
        root = find(l)
        groups_by_root.setdefault(id(root), []).append(l)
    groups = list(groups_by_root.values())

    # Same (price bucket, area) co-partitioning as above, and for the same
    # reason - a plain price bucket collects every group near a popular
    # round price regardless of area, which is both slow and pointless
    # since areas_match() (called below via the group's representative
    # member) requires an exact area match anyway.
    group_buckets = {}
    # Same transitive-drift risk as the with_sqm union step, same fix:
    # checking a new sqm-less listing against only the group's first
    # member (not the group's actual current price range) let a group's
    # overall spread creep past prices_match()'s own tolerance one
    # attachment at a time - live-found, a 7-member group reached a 0.995%
    # spread (should be ~0.5%) this way.
    group_price_range = {}
    for g in groups:
        na = normalize_area(g[0].get("area"))
        if not na:
            continue
        key = (price_bucket_key(g[0].get("price_eur")), na)
        group_buckets.setdefault(key, []).append(g)
        prices = [m["price_eur"] for m in g if m.get("price_eur")]
        group_price_range[id(g)] = (min(prices), max(prices))

    solo_sqmless = []
    for l in without_sqm:
        na = normalize_area(l.get("area"))
        key = price_bucket_key(l.get("price_eur"))
        attached = False
        if na and l.get("price_eur"):
            for dk in range(-2, 3):
                candidates = group_buckets.get((key + dk, na))
                if not candidates:
                    continue
                for group in candidates:
                    if any(m["portal"] == l["portal"] for m in group):
                        continue
                    lo, hi = group_price_range[id(group)]
                    new_lo, new_hi = min(lo, l["price_eur"]), max(hi, l["price_eur"])
                    if prices_match(new_lo, new_hi):
                        group.append(l)
                        group_price_range[id(group)] = (new_lo, new_hi)
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

# "apartment"/"commercial" are classify_category()'s old 4-value output
# (geo_utils.py), still produced by portals not yet migrated to the
# nationwide expansion's category_classifier.py, which outputs bucket
# names directly (flat/garage/shop/business already match a bucket key,
# hence the identity entries) - both resolve through this one lookup
# during the portal-by-portal migration.
CATEGORY_TO_BUCKET = {
    "apartment": "flat", "house": "house", "land": "land", "commercial": "business",
    "flat": "flat", "garage": "garage", "shop": "shop", "business": "business",
}


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


def city_key_from_name(name):
    if not name:
        return None
    # Strips a trailing settlement-type suffix a portal's own title text can
    # tack on after the real city name - "област" (region), or homes.bg's
    # own "<City> - град"/"- село" (town/village) convention, live-sampled
    # from real currently-active homes.bg titles like "София, София - град"
    # (the second "София" is the last comma segment the title fallback
    # reads, but " - град" made it fail to match "София" exactly).
    normalized = re.sub(r"\s*(?:област|-\s*град|-\s*село)$", "", name.strip(), flags=re.IGNORECASE).strip()
    return BG_CITY_BY_NAME.get(normalized)


# alo.bg's title has "<area>, <city>" but sometimes runs the price straight
# into the city with no separating comma - "...Дианабад, София Цена : 480
# 000 €" - so the last comma segment is "София Цена : 480 000 €", not
# "София" alone, and the exact match above fails even though the city name
# is right there. Live-sampled: every currently-active alo.bg listing with
# a null city_key that still had a comma in its title matched this shape.
# Longest names first so "Стара Загора" doesn't prefix-match as "Стара"
# alone (not a real entry, but keeps the general principle safe).
BG_CITY_PREFIX_RE = re.compile(
    r"^(" + "|".join(re.escape(name) for _, name in sorted(BG_CITIES, key=lambda c: -len(c[1]))) + r")\b"
)


def city_key_from_name_prefix(name):
    if not name:
        return None
    normalized = re.sub(r"\s*(?:област|-\s*град|-\s*село)$", "", name.strip(), flags=re.IGNORECASE).strip()
    match = BG_CITY_PREFIX_RE.match(normalized)
    return BG_CITY_BY_NAME.get(match.group(1)) if match else None


# imoti.net's own titles render the city in English/Latin script ("... Sofia,
# Lyulin Center" - the city is the SECOND-to-last comma segment there, not
# the last, so the generic last-comma fallback above can never recover it).
# This bit imoti.net hardest: a live sample of currently-active,
# freshly-scraped imoti.net listings with no "city" field found ~5,800 of
# them (28% of all active merged listings, and the single largest unmatched
# bucket of any portal) were genuinely Sofia listings whose title plainly
# says so in Latin script - e.g. "Shop, 44 m2 Sofia, Lyulin Center". Reuses
# the same slugs scraper.py's own CITY_SLUGS already live-verified against
# imoti.net's real city pages, just keyed by the natural-language spelling
# (space, not the URL slug's hyphen) since this searches free-form title
# text, not a URL.
LATIN_CITY_TO_KEY = {
    "sofia": "sofia", "plovdiv": "plovdiv", "varna": "varna", "burgas": "burgas", "bourgas": "burgas",
    "ruse": "ruse", "stara zagora": "stara_zagora", "pleven": "pleven", "sliven": "sliven",
    "dobrich": "dobrich", "shumen": "shumen", "pernik": "pernik", "haskovo": "haskovo",
    "yambol": "yambol", "pazardzhik": "pazardzhik", "blagoevgrad": "blagoevgrad",
    "veliko tarnovo": "veliko_tarnovo", "vratsa": "vratsa", "gabrovo": "gabrovo", "vidin": "vidin",
    "kardzhali": "kardzhali", "montana": "montana", "targovishte": "targovishte", "lovech": "lovech",
    "silistra": "silistra",
}
LATIN_CITY_RE = re.compile(
    r"\b(" + "|".join(sorted((k.replace(" ", r"\s+") for k in LATIN_CITY_TO_KEY), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def latin_city_key_from_text(text):
    if not text:
        return None
    match = LATIN_CITY_RE.search(text)
    if not match:
        return None
    normalized = re.sub(r"\s+", " ", match.group(1).lower())
    return LATIN_CITY_TO_KEY.get(normalized)


# bazar.bg's own title format has the same "city buried mid-string, not in
# the last comma segment" problem as imoti.net, just in Cyrillic: "Продава
# 3-СТАЕН, гр. София, Левски Г" - the city is the "гр. <City>" segment in
# the middle, area (last segment) is the neighborhood. A live sample of
# currently-active bazar.bg listings with no "city" field (stale rows
# scraped before bazar.bg's nationwide city-tagging merged today) confirmed
# this "гр. <City>," shape holds consistently, matching bazar.bg's own
# AREA_LINE_RE ("^гр\.\s*\S.*?,\s*(.+)$") which already relies on the same
# "гр. " prefix convention to find the area line at all.
CYR_CITY_TITLE_RE = re.compile(
    r"гр\.?\s*(" + "|".join(re.escape(name) for _, name in BG_CITIES) + r")"
)


def cyr_city_key_from_text(text):
    if not text:
        return None
    match = CYR_CITY_TITLE_RE.search(text)
    if not match:
        return None
    return BG_CITY_BY_NAME.get(match.group(1))


def listing_city_key(l):
    # Ported 1:1 from index.html's listingCityKey() - see that function's
    # comment for the full story (this used to unconditionally return
    # "sofia" for every non-bcpea portal, silently miscounting every real
    # non-Sofia listing from homes.bg/imoti.bg as Sofia).
    if l.get("portal") == "sales.bcpea.org":
        settlement = bcpea_settlement_from_title(l.get("title"))
        return city_key_from_name(settlement) if settlement else None
    city = l.get("city")
    if city:
        key = city_key_from_name(city)
        if key:
            return key
        key = city_key_from_name_prefix(city)
        if key:
            return key
    title = l.get("title")
    if title and "," in title:
        last_segment = title.rsplit(",", 1)[1].strip()
        key = city_key_from_name(last_segment)
        if key:
            return key
        key = city_key_from_name_prefix(last_segment)
        if key:
            return key
    key = latin_city_key_from_text(title)
    if key:
        return key
    key = cyr_city_key_from_text(title)
    if key:
        return key
    # No known city matched - leave unclassified rather than silently
    # defaulting to Sofia, which would inflate its count with every
    # listing this function couldn't actually place.
    return None


# --- Oblast (province) keys, mirrored 1:1 in index.html -------------------
# 28 official Bulgarian oblasts. Sofia city (the capital, a single-city
# oblast of its own) and Sofia Province (the separate oblast that surrounds
# but excludes the capital) are two different entries - a listing whose
# city_key is "sofia" belongs to "sofia_grad" below, never plain "sofia",
# which would be ambiguous between the two.
BG_OBLASTS = [
    ("sofia_grad", "София-град"), ("sofia", "Софийска област"), ("plovdiv", "Пловдив"),
    ("varna", "Варна"), ("burgas", "Бургас"), ("ruse", "Русе"), ("stara_zagora", "Стара Загора"),
    ("pleven", "Плевен"), ("sliven", "Сливен"), ("dobrich", "Добрич"), ("shumen", "Шумен"),
    ("pernik", "Перник"), ("haskovo", "Хасково"), ("yambol", "Ямбол"), ("pazardzhik", "Пазарджик"),
    ("blagoevgrad", "Благоевград"), ("veliko_tarnovo", "Велико Търново"), ("vratsa", "Враца"),
    ("gabrovo", "Габрово"), ("vidin", "Видин"), ("kyustendil", "Кюстендил"),
    ("kardzhali", "Кърджали"), ("montana", "Монтана"), ("lovech", "Ловеч"),
    ("silistra", "Силистра"), ("razgrad", "Разград"), ("smolyan", "Смолян"),
    ("targovishte", "Търговище"),
]
BG_OBLAST_BY_NAME = {name: key for key, name in BG_OBLASTS}

# Every one of the 30 BG_CITIES sits inside exactly one of the 28 oblasts -
# this is the primary, highest-confidence signal: a listing that already
# resolved to a city_key gets its oblast for free, no extra text matching
# needed. Asenovgrad/Dupnitsa/Kazanlak/Dimitrovgrad/Svishtov are towns
# within a larger city's own province, not oblast centers themselves.
CITY_KEY_TO_OBLAST = {
    "sofia": "sofia_grad", "plovdiv": "plovdiv", "varna": "varna", "burgas": "burgas",
    "ruse": "ruse", "stara_zagora": "stara_zagora", "pleven": "pleven", "sliven": "sliven",
    "dobrich": "dobrich", "shumen": "shumen", "pernik": "pernik", "haskovo": "haskovo",
    "yambol": "yambol", "pazardzhik": "pazardzhik", "blagoevgrad": "blagoevgrad",
    "veliko_tarnovo": "veliko_tarnovo", "vratsa": "vratsa", "gabrovo": "gabrovo",
    "vidin": "vidin", "asenovgrad": "plovdiv", "kazanlak": "stara_zagora",
    "kyustendil": "kyustendil", "kardzhali": "kardzhali", "montana": "montana",
    "dimitrovgrad": "haskovo", "targovishte": "targovishte", "lovech": "lovech",
    "silistra": "silistra", "dupnitsa": "kyustendil", "svishtov": "veliko_tarnovo",
}


def oblast_key_from_name(name):
    if not name:
        return None
    return BG_OBLAST_BY_NAME.get(name.strip())


# Longest names first so "Стара Загора" doesn't prefix-match as a shorter
# name that happens to also be a prefix (none currently are, but keeps the
# general principle safe as oblasts get added).
BG_OBLAST_PREFIX_RE = re.compile(
    r"^(" + "|".join(re.escape(name) for _, name in sorted(BG_OBLASTS, key=lambda o: -len(o[1]))) + r")\b"
)


def oblast_key_from_name_prefix(name):
    if not name:
        return None
    match = BG_OBLAST_PREFIX_RE.match(name.strip())
    return BG_OBLAST_BY_NAME.get(match.group(1)) if match else None


# olx.bg's own scraper (scraper_olx.py) slices its crawl by all 28 oblasts
# and falls back to writing the oblast's own display name straight into
# "city"/"area" whenever no more specific city/village line is found on a
# card - that fallback text is itself already an exact oblast name, so the
# same exact/prefix matching used for the city/area fields above recovers
# real oblast-level data other portals never supply at all.
LATIN_OBLAST_TO_KEY = {name: CITY_KEY_TO_OBLAST[ck] for name, ck in LATIN_CITY_TO_KEY.items() if ck in CITY_KEY_TO_OBLAST}
LATIN_OBLAST_TO_KEY["razgrad"] = "razgrad"
LATIN_OBLAST_TO_KEY["smolyan"] = "smolyan"
LATIN_OBLAST_RE = re.compile(
    r"\b(" + "|".join(sorted((k.replace(" ", r"\s+") for k in LATIN_OBLAST_TO_KEY), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def latin_oblast_key_from_text(text):
    if not text:
        return None
    match = LATIN_OBLAST_RE.search(text)
    if not match:
        return None
    normalized = re.sub(r"\s+", " ", match.group(1).lower())
    return LATIN_OBLAST_TO_KEY.get(normalized)


# Unlike the city version (which requires a "гр. " prefix to avoid matching
# a city name that's actually part of someone else's area/neighborhood
# name), oblast names are distinctive enough multi-syllable proper nouns
# that a plain whole-text search is safe - used as the last-resort fallback
# after every more specific signal above has failed.
CYR_OBLAST_ANY_RE = re.compile(
    r"\b(" + "|".join(re.escape(name) for _, name in sorted(BG_OBLASTS, key=lambda o: -len(o[1]))) + r")\b"
)


def cyr_oblast_key_from_text(text):
    if not text:
        return None
    match = CYR_OBLAST_ANY_RE.search(text)
    return BG_OBLAST_BY_NAME.get(match.group(1)) if match else None


# --- Geo (lat/lng) oblast lookup - the authoritative signal when present --
# Real oblast boundary polygons (28 features, NUTS3-coded, sourced from
# yurukov/Bulgaria-geocoding - a maintained public dataset already used for
# Bulgarian civic-tech dashboards). This is the only way to actually
# distinguish Sofia Province from Sofia-grad: they share the same name
# ("София") in every portal's own text, so no text-matching rule can ever
# tell them apart - only a point-in-polygon test against their real,
# very-differently-shaped boundaries can. Point-in-ring uses the standard
# ray-casting algorithm; GeoJSON winding order puts the first ring as the
# outer boundary and any further rings as holes (a handful of oblasts -
# Sliven, Gabrovo, Burgas, Stara Zagora, Pernik - have real enclave
# geometry, not a data artifact, confirmed against the source polygons).
_OBLAST_BOUNDARIES_PATH = Path(__file__).parent / "data" / "bg_oblast_boundaries.json"


def _bbox(ring):
    lngs = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lngs), min(lats), max(lngs), max(lats)


def _load_oblast_boundaries():
    if not _OBLAST_BOUNDARIES_PATH.exists():
        return []
    raw = json.loads(_OBLAST_BOUNDARIES_PATH.read_text(encoding="utf-8"))
    boundaries = []
    for entry in raw:
        polygons = []
        for poly in entry["polygons"]:
            polygons.append({
                "exterior": poly["exterior"],
                "exterior_bbox": _bbox(poly["exterior"]),
                "holes": poly["holes"],
            })
        boundaries.append({"key": entry["key"], "polygons": polygons})
    return boundaries


OBLAST_BOUNDARIES = _load_oblast_boundaries()


def _point_in_ring(lng, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x_intersect = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lng < x_intersect:
                inside = not inside
        j = i
    return inside


def oblast_key_from_latlng(lat, lng):
    if lat is None or lng is None:
        return None
    for entry in OBLAST_BOUNDARIES:
        for poly in entry["polygons"]:
            min_lng, min_lat, max_lng, max_lat = poly["exterior_bbox"]
            if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
                continue
            if not _point_in_ring(lng, lat, poly["exterior"]):
                continue
            if any(_point_in_ring(lng, lat, hole) for hole in poly["holes"]):
                continue
            return entry["key"]
    return None


def listing_oblast_key(l, city_key):
    geo_key = oblast_key_from_latlng(l.get("lat"), l.get("lng"))
    if geo_key:
        return geo_key
    if city_key:
        key = CITY_KEY_TO_OBLAST.get(city_key)
        if key:
            return key
    if l.get("portal") == "sales.bcpea.org":
        settlement = bcpea_settlement_from_title(l.get("title"))
        if settlement:
            key = oblast_key_from_name(settlement)
            if key:
                return key
            key = oblast_key_from_name_prefix(settlement)
            if key:
                return key
        return None
    for field in ("city", "area"):
        value = l.get(field)
        if value:
            key = oblast_key_from_name(value)
            if key:
                return key
            key = oblast_key_from_name_prefix(value)
            if key:
                return key
    title = l.get("title")
    if title and "," in title:
        last_segment = title.rsplit(",", 1)[1].strip()
        key = oblast_key_from_name(last_segment)
        if key:
            return key
        key = oblast_key_from_name_prefix(last_segment)
        if key:
            return key
    key = latin_oblast_key_from_text(title)
    if key:
        return key
    key = cyr_oblast_key_from_text(title)
    if key:
        return key
    # No known oblast matched (a small town/village not near any of the 30
    # cities, with no oblast name anywhere in its own text either) - left
    # unclassified rather than guessed; the frontend's "Others" bucket
    # covers it, same as an unclassified city_key.
    return None


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


# Every field a listing_sources row copies straight from a leads_*.json
# entry, confirmed against the real union of keys actually present across
# all 8 committed files (not guessed from scraper source). "id" and
# "portal" are handled separately (source_id / portal columns).
SOURCE_FIELDS = [
    "url", "photo", "photos", "price_eur", "sqm", "area", "title", "description",
    "category", "category_confidence", "lat", "lng", "price_per_sqm", "price_history",
    "price_drop_count", "drop_pct", "days_on_market", "score", "source_status", "removed_at",
    "area_avg_price_per_sqm", "pct_vs_area_avg", "site_updated_at", "site_posted_at",
]

# merged_listings has no source_status/removed_at columns - a merged group's
# equivalent is the "status" field computed separately (available/sold,
# only true once every member source agrees it's gone), not any one
# source's own status. Sending those two columns to merged_listings gets
# PostgREST's "could not find the column" error since there's no such
# column to write to.
MERGED_FIELDS = [f for f in SOURCE_FIELDS if f not in ("source_status", "removed_at")]


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
            city_key = listing_city_key(s)
            row["city_key"] = city_key
            row["oblast_key"] = listing_oblast_key(s, city_key)
            listing_source_rows.append(row)

        best = sorted_sources[0]
        merged = {
            "id": mid,
            "portal": best["portal"],
            "status": status,
            "member_count": len(sorted_sources),
            "member_portals": sorted({s["portal"] for s in sorted_sources}),
        }
        for f in MERGED_FIELDS:
            merged[f] = best.get(f)
        merged["type_bucket"] = type_filter_bucket(best)
        city_key = listing_city_key(best)
        merged["city_key"] = city_key
        merged["oblast_key"] = listing_oblast_key(best, city_key)
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
