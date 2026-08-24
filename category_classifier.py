"""
Shared 6-category classifier for the nationwide scrapers (imoti.net, alo.bg,
homes.bg, imot.bg, olx.bg, bazar.bg, imoti.bg). Every listing must end up in
exactly one of the 6 categories the frontend already uses as its type-filter
buckets (index.html's TYPE_FILTER_BUCKETS / sync_to_supabase.py's
CATEGORY_TO_BUCKET) - flat, house, land, garage, shop, business - with no
"uncategorized" bucket in scraper output. sales.bcpea.org already achieves
this via an exact controlled vocabulary (BCPEA_RAW_TYPES in
sync_to_supabase.py), since that portal's own listings carry a precise,
fixed Bulgarian type string. The other 7 portals don't expose a type field
that reliably, so this scores keyword matches across three independent
signals - title, description, and URL - instead of trusting any one alone
(a title might just be an address, a description might mention a nearby
garage without the listing itself being one; agreement across two or more
signals is real evidence, a single stray word in one field is not).

Extends geo_utils.CATEGORY_KEYWORDS (4 rough buckets, apartment-default,
built for Sofia-only apartment-search URLs where that default was accurate)
and BCPEA_RAW_TYPES (6 precise buckets, but an exact-match vocabulary that
only bcpea.org's own controlled type field can use) into one shared
keyword-scoring vocabulary usable against any portal's free-text fields,
now that nationwide, multi-category scraping means "default to apartment"
is no longer a safe assumption.
"""

import re

# Longest/most specific phrases first within each category isn't needed
# here (unlike BCPEA_TYPE_LOOKUP's startswith-prefix matching) since these
# are substring searches against free text, not a single controlled-
# vocabulary string - "апартамент" and "тристаен апартамент" both just
# need to match "flat" once, not compete for the longest prefix.
CATEGORY_KEYWORDS = {
    "garage": [
        "гараж", "паркомясто", "паркоместа", "паркинг място", "гаражна клетка",
        "garazh", "parkomyasto", "parkomesta", "garage",
    ],
    "shop": [
        "магазин", "заведение", "ресторант", "кафене", "витрина за", "търговски обект",
        "магазини", "magazin", "zavedenie", "shop", "store",
    ],
    "business": [
        "офис", "склад", "хале", "производствен", "производство", "фабрика",
        "хотел", "бензиностанция", "газстанция", "автомивка", "индустриален имот",
        "бизнес имот", "търговски имот", "инвестиционен имот", "сграда за офиси",
        "ofis", "sklad", "hotel", "office", "warehouse",
    ],
    "land": [
        "парцел", "земеделска земя", "земеделски имот", "урегулиран поземлен имот",
        " упи ", "упи,", "имот за строеж", "терен", "нива", "дворно място",
        "парцел с къща", "parcel", "teren", "niva", "plot",
    ],
    "house": [
        "къща", "вила", "етаж от къща", "таунхаус", "еднофамилна къща",
        "жилищна сграда", "къща с двор", "селска къща",
        "kashta", "kyshta", "vila", "taunhaus", "house", "villa",
    ],
    "flat": [
        "апартамент", "едностаен", "двустаен", "тристаен", "четиристаен",
        "многостаен", "мезонет", "гарсониера", "ателие таван", "студио",
        "апартаменти", "стаи",
        "apartament", "apartamenti", "ednostaen", "dvustaen", "tristaen",
        "mezonet", "garsoniera", "studio", "flat", "apartment",
    ],
}

# Digit-prefixed room-count shorthand ("2-стаен", "3 стаен", "1-стаен
# апартамент") is an extremely common way Bulgarian listings state "flat"
# without ever spelling out "едно/дву/три/четиристаен" or the word
# "апартамент" itself - a plain substring list can't express this, so it's
# handled as its own regex rather than a CATEGORY_KEYWORDS entry.
_ROOM_COUNT_RE = re.compile(r"\d\s*-?\s*стаен")

# Tiebreak order only (when two categories score exactly equal) - most
# specific/least-ambiguous categories first, "flat" last since it's also
# the no-match fallback and shouldn't win a tie against a real signal.
CATEGORY_ORDER = ["garage", "shop", "business", "land", "house", "flat"]

_KEYWORD_RE_CACHE = {
    cat: [re.compile(re.escape(kw)) for kw in kws]
    for cat, kws in CATEGORY_KEYWORDS.items()
}

# Each signal's contribution to a category's score. The URL often encodes
# the portal's own category cleanly in a path segment (e.g. a search or
# listing URL containing ".../garazhi-parkomesta/...") so it counts for
# more than one stray word inside a long free-text description, but less
# than the title, which is short and purpose-written to describe exactly
# what's for sale.
SIGNAL_WEIGHTS = {"title": 3, "url": 2, "description": 1}


def _score_signal(signal_name, text, scores, matched_signals):
    if not text:
        return
    text = text.lower()
    weight = SIGNAL_WEIGHTS[signal_name]
    for cat, patterns in _KEYWORD_RE_CACHE.items():
        if any(p.search(text) for p in patterns):
            scores[cat] = scores.get(cat, 0) + weight
            matched_signals.setdefault(cat, set()).add(signal_name)
    if _ROOM_COUNT_RE.search(text):
        scores["flat"] = scores.get("flat", 0) + weight
        matched_signals.setdefault("flat", set()).add(signal_name)


def classify_listing(title=None, description=None, url=None):
    """Classifies one listing from its title, description, and URL.

    Returns (category, confidence, reason):
      category   - always one of CATEGORY_KEYWORDS' 6 keys, never None/other.
      confidence - "high" or "low".
      reason     - short machine-readable string explaining a "low" verdict
                   (None when confidence is "high") - accumulate these to
                   answer "how many listings needed the low-confidence
                   fallback, and why."
    """
    scores = {}
    matched_signals = {}
    _score_signal("title", title, scores, matched_signals)
    _score_signal("url", url, scores, matched_signals)
    _score_signal("description", description, scores, matched_signals)

    if not scores:
        return "flat", "low", "no_keyword_match"

    best_score = max(scores.values())
    winners = [cat for cat in CATEGORY_ORDER if scores.get(cat) == best_score]
    winner = winners[0]

    if len(winners) > 1:
        return winner, "low", "tied_categories:" + ",".join(winners)

    # High confidence requires agreement across more than one independent
    # signal - repeated keyword hits within a single field (e.g. a
    # description that says "апартамент" three times) shouldn't count as
    # stronger evidence than one field alone actually is.
    if len(matched_signals[winner]) < 2:
        return winner, "low", "single_signal_only"

    return winner, "high", None
