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
        # "restaurant"/"tyrgovski obekt": imoti.net's own English listing
        # text for these (e.g. title "Restaurant", URL slug
        # "tyrgovski-obekt") - confirmed live against real committed data
        # (docs/backlog.md item 5) that neither matched anything here
        # before, since every other shop keyword is Bulgarian/Cyrillic or a
        # different Latin transliteration. "tyrgovski" (not the full
        # phrase) also catches the URL's hyphenated "tyrgovski-obekt" form.
        "restaurant", "tyrgovski",
    ],
    "business": [
        "офис", "склад", "хале", "производствен", "производство", "фабрика",
        "хотел", "бензиностанция", "газстанция", "автомивка", "индустриален имот",
        "бизнес имот", "търговски имот", "инвестиционен имот", "сграда за офиси",
        "ofis", "sklad", "hotel", "office", "warehouse",
        # "industrial property"/"commercial property": imoti.net's own
        # English titles for these - confirmed live these didn't match any
        # existing keyword (all Cyrillic-only for this nuance, or
        # "промишлен"/"promishlen" wasn't listed either). Deliberately the
        # full phrase, not a bare "industrial"/"commercial" - a real,
        # confirmed-live false positive: "Industrial Zone"/"Промишлена
        # зона" ("Industrialna Zona"/"Promishlena Zona") is a genuinely
        # common Bulgarian district name (Burgas, Haskovo, Yambol, Vratsa,
        # Plovdiv all have one), so a bare "industrial"/"promishlen"
        # keyword wrongly matched ordinary flats/houses/studios located IN
        # that district as if "industrial" described the property itself
        # (e.g. "House, 21 м2 ... Industrial zone - South" is a real
        # house, not a business property) - see docs/backlog.md item 5.
        # "promishlen-imot" (the real URL slug, hyphenated) is similarly
        # exact rather than bare "promishlen", which is a substring of
        # "promishlena" (the district-name spelling) and would have the
        # same collision via the URL signal.
        "industrial property", "commercial property", "promishlen-imot",
    ],
    "land": [
        "парцел", "земеделска земя", "земеделски земи", "земеделски имот", "урегулиран поземлен имот",
        "имот за строеж", "терен", "нива", "дворно място",
        "парцел с къща", "parcel", "teren", "niva", "plot",
        # "упи" (a common abbreviation for "урегулиран поземлен имот" -
        # "regulated land plot") is handled by _UPI_RE below, not as a plain
        # substring here - see that regex's own comment for why.
        # "agricultural land"/"development land": imoti.net's own English
        # titles for these; "zemedelski" catches its URL slug
        # ("zemedelski-imot") the same way "parcel" already catches
        # imoti.net's "parcel" URL slug - confirmed live neither matched
        # before (docs/backlog.md item 5).
        "agricultural land", "development land", "zemedelski",
    ],
    "house": [
        "къща", "къщи", "вила", "вили", "етаж от къща", "таунхаус", "еднофамилна къща",
        "жилищна сграда", "къща с двор", "селска къща",
        # "къщи"/"вили" (plural of "къща"/"вила") - Bulgarian feminine nouns
        # ending in "-а" often pluralize by replacing the final letter with
        # "-и" rather than appending a suffix, so (unlike most of this
        # list's other plurals, e.g. "апартамент"/"апартаменти",
        # "офис"/"офиси" - already covered for free since the singular is a
        # literal prefix of the plural) the singular substring alone never
        # matches the plural form at all. Confirmed live: 191 olx.bg + 14
        # alo.bg listings ("Две къщи с голям двор за продажба", "продавам 2
        # къщи в Катуница") were missing this and defaulting to "flat" (the
        # no-match fallback) or another tied category instead.
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

# "упи" ("урегулиран поземлен имот" - "regulated land plot"), a real, very
# common Bulgarian land-listing title word (confirmed live: olx.bg alone had
# 154+ genuine land listings misclassified over this, e.g. "УПИ до къщи в
# Първенец", "УПИ в село Мезек"). Previously a plain CATEGORY_KEYWORDS
# substring padded with a leading+trailing space (" упи ") to avoid a false
# substring match inside an unrelated longer word (e.g. "групи",
# "принципи") - but that padding requires a character before "упи" too,
# which a title OPENING with "УПИ" (extremely common - it's often the very
# first word of a land listing's title) never has, so the padded keyword
# silently never matched the single most common real-world phrasing. A
# proper \b word-boundary regex (confirmed live to still correctly reject
# "групи"/"принцип" while matching "УПИ" at the very start of a string,
# mid-title, or followed by a comma) fixes this the same way _ROOM_COUNT_RE
# already handles "flat"'s own similar shape below.
_UPI_RE = re.compile(r"\bупи\b", re.IGNORECASE)

# Tiebreak order only (when two categories score exactly equal) - most
# specific/least-ambiguous categories first, "flat" last since it's also
# the no-match fallback and shouldn't win a tie against a real signal.
CATEGORY_ORDER = ["garage", "shop", "business", "land", "house", "flat"]

_KEYWORD_RE_CACHE = {
    cat: [re.compile(re.escape(kw)) for kw in kws]
    for cat, kws in CATEGORY_KEYWORDS.items()
}

# garage/<anything> tiebreak fix (docs/decisions.md 2026-09-23 "Ready" entry,
# .claude/agents/ready.md): CATEGORY_ORDER puts "garage" first, so it used to
# win every tie unconditionally - including the dominant real-world case,
# confirmed against a random sample of the affected pool, where "гараж"/
# "паркомясто" (garage/parking space) is mentioned as an attached AMENITY
# inside a flat/house/shop/business listing's own title ("Тристаен
# апартамент ... с ПАРКОМЯСТО", "Етаж от къща с гараж и паркомясто"), not the
# listing's own subject. A genuine garage-for-sale listing's title is instead
# templated to OPEN with the word itself ("Garage, 14 м2 Sofia, ...") - the
# garage keyword is the very first thing mentioned, nothing precedes it.
#
# Bulgarian listing titles are conventionally subject-first, amenities-
# appended, so whichever tied category's own keyword appears LEFTMOST in the
# title is its real subject; this resolves a garage/X tie by that position
# instead of by CATEGORY_ORDER, but only when every tied category actually
# has its own match inside the title (the strongest, purpose-written signal -
# see SIGNAL_WEIGHTS - so a positional comparison across categories is
# apples-to-apples) and only when garage itself isn't the leftmost (i.e.
# doesn't override anything when garage genuinely is the subject, e.g. a real
# garage listing that happens to also mention "near the apartments" later -
# "гараж" still precedes "апартаменти" there, so garage still wins). Anywhere
# this can't be determined (title missing, or a tied category's score came
# only from url/description) falls through to the original CATEGORY_ORDER
# behavior unchanged.
#
# Deliberately scoped to ties that include "garage" specifically - the one
# root-caused, quantified pattern (2,049 of 2,516 low-confidence
# garage-tagged listings as of 2026-09-23; see backfill_garage_tiebreak.py) -
# rather than rewriting the tiebreak for every category combination, most of
# which haven't been individually audited against real data.
def _title_match_positions(categories, title):
    """Maps each of `categories` to the character index of its earliest own
    keyword match inside `title` (case-insensitive), leaving out any
    category that has no match in `title` itself (only url/description
    contributed to its share of the tied score)."""
    if not title:
        return {}
    text = title.lower()
    positions = {}
    for cat in categories:
        idxs = [m.start() for m in (p.search(text) for p in _KEYWORD_RE_CACHE[cat]) if m]
        if cat == "flat":
            room_count_match = _ROOM_COUNT_RE.search(text)
            if room_count_match:
                idxs.append(room_count_match.start())
        if cat == "land":
            upi_match = _UPI_RE.search(text)
            if upi_match:
                idxs.append(upi_match.start())
        if idxs:
            positions[cat] = min(idxs)
    return positions


def _resolve_garage_tie(winners, title):
    """Given a set of tied `winners` that includes "garage", returns the
    category that should actually win (see the module comment above this
    function), or None to leave CATEGORY_ORDER's existing fallback alone."""
    positions = _title_match_positions(winners, title)
    if len(positions) != len(winners):
        return None
    leftmost = min(positions, key=positions.get)
    if positions[leftmost] == positions["garage"]:
        # Exact tie in title position (or garage genuinely is leftmost) -
        # inconclusive either way, so don't override.
        return None
    return leftmost


# Second root-caused pattern (docs/decisions.md 2026-09-23 "Ready's second
# assignment" entry), generalizing the garage-tie fix above rather than
# duplicating it: the tiebreak fix above only fires on an exact score TIE,
# but the same "amenity word mentioned after the real subject" shape also
# produces an outright (non-tied) win for the wrong category whenever the
# SAME amenity word appears in both the title AND the url - e.g. a listing
# whose url is portal-generated as a transliterated copy of its own title
# (confirmed live for olx.bg/alo.bg: "-s-garazh-" in the url is just
# "с гараж" from the title, not independent taxonomy evidence the way
# imoti.net's own category-path url segments are). That double-counts the
# SAME piece of real-world evidence as if it were two independent signals
# (title weight 3 + url weight 2 = 5), letting an attached-amenity category
# outscore the listing's real, title-leading subject (weight 3 alone)
# outright - no tie ever occurs, so _resolve_garage_tie above never even
# runs. Confirmed live, e.g. a real olx.bg house listing "Продавам
# двуетажна къща ... с гараж в с.Тополово" (subject "къща" leads the title,
# "гараж" is an appended amenity) scored business... er, garage=5 (title +
# url) outright beating house=3 (title only, since olx.bg's url spells
# "къща" as "kascha", not a spelling already in CATEGORY_KEYWORDS["house"]),
# with "high" confidence (title+url did genuinely "agree" - just on the
# wrong, amenity word, not the listing's real subject).
#
# Generalizes (rather than just patching the one missing "kascha" spelling,
# which would leave the same shape of bug for the next missing
# transliteration) the exact same "Bulgarian titles are subject-first,
# amenities-appended" position reasoning the garage tiebreak already
# established and validated against real data - just applied to WINNER vs.
# the title's own leftmost SUBJECT-class match, regardless of whether the
# raw scores happened to land on an exact tie:
#   - AMENITY_CATEGORIES = {"garage", "shop", "business"} - categories this
#     project's own real-data sampling (both the original tiebreak fix and
#     this one) has repeatedly found mentioned as an attached amenity of a
#     listing whose real subject is something else, never the reverse.
#   - SUBJECT_CATEGORIES = {"flat", "house", "land"} - the categories real
#     listings are titled AS, leading the sentence.
# Only overrides when the raw winner is itself amenity-class, and only when
# that winner ALSO has its own match inside the title (an apples-to-apples
# comparison, same discipline as _resolve_garage_tie - if the winner's
# whole score came from url/description alone, there's no title position to
# compare a subject match against, so this leaves the existing tie/
# CATEGORY_ORDER fallback alone rather than guessing).
AMENITY_CATEGORIES = {"garage", "shop", "business"}
SUBJECT_CATEGORIES = {"flat", "house", "land"}


def _resolve_subject_over_amenity(winner, title):
    """Returns the real-subject category that should win instead of an
    amenity-class `winner`, when the title's own leftmost SUBJECT-class
    keyword precedes `winner`'s own title match - or None to leave the
    existing winner (tie-resolved or not) alone."""
    if winner not in AMENITY_CATEGORIES:
        return None
    positions = _title_match_positions(SUBJECT_CATEGORIES | {winner}, title)
    if winner not in positions:
        return None
    subject_positions = {cat: pos for cat, pos in positions.items() if cat in SUBJECT_CATEGORIES}
    if not subject_positions:
        return None
    leftmost_subject = min(subject_positions, key=subject_positions.get)
    if subject_positions[leftmost_subject] < positions[winner]:
        return leftmost_subject
    return None

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
    if _UPI_RE.search(text):
        scores["land"] = scores.get("land", 0) + weight
        matched_signals.setdefault("land", set()).add(signal_name)


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

    # Checked first, ahead of both the tie logic and the single-signal/high-
    # confidence logic below, since it can override either shape of result
    # (an outright amenity-class win OR an amenity-involving tie) - see the
    # module comment above _resolve_subject_over_amenity for why this is
    # checked independently of whether the raw scores happen to tie.
    subject_override = _resolve_subject_over_amenity(winner, title)
    if subject_override is not None:
        reason = "title_subject_override:" + winner + "->" + subject_override
        if len(winners) > 1:
            reason += ",tied_with:" + ",".join(w for w in winners if w != winner)
        return subject_override, "low", reason

    if len(winners) > 1:
        if "garage" in winners:
            resolved = _resolve_garage_tie(winners, title)
            if resolved is not None:
                return resolved, "low", "tied_categories_by_title_position:" + ",".join(winners)
        return winner, "low", "tied_categories:" + ",".join(winners)

    # High confidence requires agreement across more than one independent
    # signal - repeated keyword hits within a single field (e.g. a
    # description that says "апартамент" three times) shouldn't count as
    # stronger evidence than one field alone actually is.
    if len(matched_signals[winner]) < 2:
        return winner, "low", "single_signal_only"

    return winner, "high", None
