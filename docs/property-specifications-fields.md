# Listing "Specifications" section - field list, display format, and per-portal extractability

Compiled by Nosy, in response to the user's direct request: *"Specifications
on every listing still missing. They need to be built in a section (same
size and next to the map section). Every listing must include
specifications from the original listing."*

## Erratum (2026-09-27, Missy's review of this doc's original PR #309 - NOT APPROVED)

**This doc's central premise was wrong, and has been corrected in place
rather than left standing.** The original version below claimed a
Specifications section was "genuinely new scope, not a regression" and
that no scraper extracted any of these fields. Both claims were false:

- **A Specifications panel (and an Agency panel) already existed and
  already shipped live for 3 of the 8 portals** before this doc's research
  pass ever ran - `geo_utils.extract_specs_alo()`,
  `extract_specs_bazar()`, and `extract_specs_imoti_bg()` (wired into
  `scraper_alo.py`, `backfill_detail_bazar.py`/`scraper_bazar.py`, and
  `scraper_imoti_bg.py` respectively), synced as real columns via
  `sync_to_supabase.py`'s `SOURCE_FIELDS`, and rendered by `index.html`'s
  `renderSpecsPanel()`/`renderAgencyPanel()`. The original research pass
  grepped for field names it invented itself (`year_built`, `elevator`,
  `furnishing`) instead of the real ones, missed all of the above, and
  concluded there was nothing there.
- **The real, most likely root cause of the user's complaint was never
  identified.** The panel existed but was buried inside the click-gated
  "Details" tab rather than visible next to the map, and real data is
  only populated for 3 of 8 portals - so most listings genuinely showed
  nothing there even though the code path existed. Section 1 below now
  describes this correctly; the fix (moving the panel next to the map,
  per the user's literal, twice-repeated request) shipped in the same
  change that corrected this doc - see `renderSpecsHistoryPanel()` in
  `index.html` and `docs/decisions.md`'s entry for this date.
- **The proposed field names collided with the real, already-shipped
  schema** (`year_built` vs. the real `built_year`; a boolean-style
  `elevator` vs. the real `has_elevator`; a tri-state `furnishing` vs. the
  real boolean `furnished`). Section 2 below is corrected to build against
  the real names for anything that overlaps, and only proposes genuinely
  new keys for fields nothing shipped extracts yet.
- **The per-portal ease ranking had it backwards** for the portals that
  matter most: alo.bg and bazar.bg were rated "Uncertain - verify live
  before committing" when they are in fact the two portals with the LEAST
  uncertainty of any of the 8 - real, shipped, tested extraction, not a
  guess. imoti.bg was rated a blanket "Easy" when its real gap is
  specific and structural (see below), not a general confidence rating.
  homes.bg was rated "Easy, and de-risked" without flagging that it needs
  a real new capability (a detail-page fetch) it does not have today.
  Section 4 below is corrected.
- **The homes.bg "confirmed" data point was mischaracterized.** Backlog
  item 9 / PR #217 found ONE combined string
  ("Тухла/Бетон, Полуобзаведен" - construction material AND furnishing
  status joined together in a single field), sourced from the
  **search-results JSON**, not the detail page (`scraper_homes.py` never
  fetches homes.bg's detail page at all). This doc's table implied two
  independently structured fields in a fixed order - not verified, and
  not what the evidence actually shows. Corrected below; splitting this
  string safely, if it's even the same fixed order on every listing, is
  explicitly flagged as unverified.
- A stale line-number citation for `KEYWORD_DICTIONARY` is fixed.
- The `syncHistoryPanelHeights()` dependency the frontend placement
  recommendation didn't know to flag (added after this doc's original
  research pass, specifically to fix a real live height-desync bug) is
  now noted in section 3.

Everything below has been re-verified against the real code at the
current `origin/main` HEAD as of this correction, not just patched
around the errors above.

---

## 1. What already exists today - don't duplicate it, and don't miss it

Before adding new fields, two things already exist and the new/expanded
work must be positioned as a complement to both, not a duplicate of
either:

**A. The free-text keyword panel** - `index.html`'s `KEYWORD_DICTIONARY` /
`extractKeywordTags()` / `renderKeywordsPanel()` (~line 9938-10018) mines
each listing's free-text `description` + `title` for keyword matches and
renders them as tag pills, grouped into "Sale features", **"Property
features"**, and "Close by". The "Property features" group covers, as
**boolean detected/not-detected tags, not structured values**: Parking,
Garage, Elevator, Balcony / terrace, Furnished, Renovated, Brick
construction, Air conditioning, High ceilings. This is presence-only (no
slot for "3rd floor of 8" or "built 1998") and depends on `description`
text, which backlog item 9 already found is missing or badly wrong for
most listings on most portals. This panel is unaffected by anything below
and should not be touched.

**B. The real Specifications + Agency panel - already shipped for 3 of 8
portals, this is what this doc originally missed.** `geo_utils.py` has
three real detail-page extractors:

- `extract_specs_alo()` (~line 689) - alo.bg, wired into `scraper_alo.py`
  (~line 535).
- `extract_specs_bazar()` (~line 1205) - bazar.bg, wired into
  `backfill_detail_bazar.py` (a detail-page backfill pass, not the main
  grid scraper) and preserved on subsequent grid re-scrapes via
  `scraper_bazar.py`'s `_DETAIL_ONLY_FIELDS` merge (~line 570).
- `extract_specs_imoti_bg()` (~line 1068) - imoti.bg, wired into
  `scraper_imoti_bg.py` (~line 267, 432-440), **but only for
  `property_type_raw`/`features`/`has_elevator`/`furnished`/
  `has_central_heating`** - see part C below for why the rest is missing
  on this portal specifically, not just "not built yet."

These write real columns - `property_type_raw`, `construction_type`,
`built_year`, `completion_status`, `floor_number`, `floor_qualifier`,
`features[]`, `has_elevator` (boolean), `furnished` (boolean),
`has_central_heating` (boolean), `agency_name`, `agency_website` - synced
to Supabase via `sync_to_supabase.py`'s `SOURCE_FIELDS` (~line 1101-1107).
`agency_phone` is rendered by the frontend (`renderAgencyPanel()`) but is
**never actually populated by any scraper** - alo.bg's own
`extract_contact_alo()` deliberately skips it (masked/JS-reveal phone
numbers, see that function's own comment) and no other portal's contact
extractor was ever given a phone field either; it is dead-but-harmless in
`sync_to_supabase.py`'s field list terms (it isn't in `SOURCE_FIELDS` at
all) and the frontend already reads it defensively (`undefined` renders
as absent, not a crash).

`index.html` already renders this via `renderSpecsPanel()`
(~line 10043) and `renderAgencyPanel()` (~line 10067) - "Property type /
Construction type / Built year / Completion status / Floor" plus feature
tags and agency info, using exactly the real column names above (an
earlier bug had this reading a made-up `l.property_type` instead of the
real `property_type_raw`; already fixed, see that function's own
"Correction (2026-09-24)" comment).

**Until this correction, both panels only rendered inside the click-gated
"Details" tab** (`renderListingDetail()`, called right after
`renderKeywordsPanel()`), never visible next to the map the way the user's
twice-repeated request describes. **This is now fixed as part of the same
change that corrected this doc**: both are relocated into
`.detail-history-row` as a third panel via a new `renderSpecsHistoryPanel(l)`
wrapper (index.html, next to `renderSpecsPanel()`/`renderAgencyPanel()`)
that reuses both functions' output completely unchanged, adds a shared
empty state for the (still common, 3-of-8-portals) case where a listing
has neither, and is no longer duplicated inside the Details tab. See
section 3 for the concrete markup/CSS and section 4/5 for what's still
genuinely missing per portal.

**C. Why imoti.bg is a partial case, not a missing one.**
`extract_specs_imoti_bg()`'s own comment (geo_utils.py, ~line 955-968) is
explicit and worth quoting rather than re-summarizing loosely: schema.org
(the `application/ld+json` vocabulary this extractor reads) has no core
term for `construction_type`, `built_year`, `completion_status`,
`floor_number`, or `floor_qualifier` - only `floorSize`, `amenityFeature`,
and the Accommodation subtype names are real, documented schema.org
properties, which is why only `property_type_raw`/`features`/
`has_elevator`/`furnished`/`has_central_heating` are extracted for this
portal. The comment names the concrete next step for anyone extending
this: check a candidate's `additionalProperty` array (schema.org's
generic name/value escape hatch) once live access is available. This is
a **real, specific, structural gap** (no vocabulary term exists, not "not
gotten to yet") and should not be rated a blanket "Easy" the way the
original version of this doc did (see section 4).

---

## 2. Field list - real schema first, proposed additions second

**Do not invent new field names or a second schema for fields that
already ship.** Any new extraction work for an already-covered field
(construction type, built year, completion status, floor, elevator,
furnished, central heating, property type, features) must write into the
existing real columns listed in section 1(B) - `property_type_raw`,
`construction_type`, `built_year`, `completion_status`, `floor_number`,
`floor_qualifier`, `features[]`, `has_elevator`, `furnished`,
`has_central_heating`, `agency_name`, `agency_website` - not a
parallel `year_built`/`elevator`/`furnishing`-style set. The table below
is corrected to show the mapping explicitly, and only proposes genuinely
new keys where nothing shipped touches the concept at all.

### Already real (ship for alo.bg + bazar.bg fully, imoti.bg partially - see 1C)

| Real column | UI label (`renderSpecsPanel()`) | Value format | Note |
|---|---|---|---|
| `property_type_raw` | "Property type" | free string, portal's own wording (e.g. "2-стаен") | Not normalized across portals today - a `spec_normalizer.py`-style shared mapping (see the old section 2's vocabulary note) is still a reasonable future improvement, not required for this fix |
| `construction_type` | "Construction type" | free string (e.g. "Тухла", "ЕПК") | imoti.bg: not extracted, no schema.org term (1C) |
| `built_year` | "Built year" | 4-digit int | imoti.bg: not extracted (1C) |
| `completion_status` | "Completion status" | free string | imoti.bg: not extracted (1C) |
| `floor_number` + `floor_qualifier` | "Floor" (combined: `"4 (Непоследен)"`) | int + optional qualifier string | alo.bg's `floor_qualifier` is a qualifier word ("Непоследен" - "not top floor"), NOT a total-floor-count; bazar.bg only ever sets `floor_number`, no qualifier. imoti.bg: neither extracted (1C) |
| `features[]` | feature tag pills | array of free strings | All 3 portals |
| `has_elevator` | folded into feature tags upstream, not its own row | boolean | Derived from a matched feature string, all 3 portals |
| `furnished` | folded into feature tags upstream, not its own row | boolean | All 3 portals |
| `has_central_heating` | folded into feature tags upstream, not its own row | boolean | All 3 portals |
| `agency_name` / `agency_website` | "Agency" panel | strings | alo.bg + imoti.bg (bazar.bg's own extractor doesn't collect agency contact) |
| `agency_phone` | "Agency" panel (📞 link) | string | **Never populated by any scraper** - alo.bg's masked/JS-reveal number is deliberately not extracted (`extract_contact_alo()`'s own comment); frontend already handles its absence gracefully |

### Genuinely new - not shipped anywhere, real candidates for a fast-follow

Kept from the original research pass, since nothing here overlaps a real
column - but every new key should still land inside the same flat
per-listing shape (`l.<key>`, matching `sqm`/`price_eur`/the fields
above), not a nested `specs` object, for consistency with how the shipped
fields already sit.

| Proposed key | BG label(s) seen/expected | UI label | Value format | Notes |
|---|---|---|---|---|
| `total_floors` | Етажност | "Floor" (combine with `floor_number` when both known: `"4 of 8"`) | int | Distinct from the real `floor_qualifier` above - nothing shipped captures a building's total floor count today on any portal |
| `heating_type` | Отопление: ТЕЦ / Климатик / Локално / Парно / Печка | "Heating" | enum string | `has_central_heating` (real, shipped) already covers the ТЕЦ/central-heating yes-no case as a boolean; this would be a richer enum covering the other heating types, not a replacement |
| `exposure` | Изложение: Юг/Север/Изток/Запад | "Exposure" | 1-2 of N/E/S/W | Apartments mainly |
| `yard_sqm` | Дворно място / Двор | "Yard" | m² | Houses only |
| `regulation_status` | Регулация: В регулация / Извън регулация | "Zoning" | In zone / Out of zone | Plots/land only, lower confidence |
| `cadastral_id` | Идентификатор по кадастъра | "Cadastral ID" | reference string | Realistically only sales.bcpea.org's legally-formatted auction listings |

**Deliberately excluded, unchanged from the original research:**
Tenure/ownership type (Bulgarian property is overwhelmingly
freehold-equivalent, already ruled out in `property-filter-spec.md`
section 4); EPC/energy-efficiency rating (no confirmed scrapable source
yet, `property-filter-spec.md` sections 3/4/5); rooms/total area/
price/price-per-m² (already exist elsewhere on the page, don't duplicate).

---

## 3. Display format and placement - IMPLEMENTED as of this correction

### Placement - "same size and next to the map section"

`.detail-history-row` (in `renderListingDetail()`, `index.html`
~line 11464 as of this change - line numbers drift, search for the
literal class name rather than trusting any cited number including this
one) is a CSS grid (`grid-template-columns: repeat(auto-fit,
minmax(240px, 1fr))`, `gap: 24px`) that held two same-styled panels -
`renderRadiusPanel(l)` (the map) and `.price-history-panel`. **A third
panel has now been added**: `renderSpecsHistoryPanel(l)`, called right
alongside the other two, producing a `.specs-history-panel` box reusing
the exact same background/border/radius/padding as `.price-history-panel`
and wrapping `renderSpecsPanel(l)`'s + `renderAgencyPanel(l)`'s own,
completely unchanged output (their nested `margin-top`/`border-top`
divider styling, meant for stacking under other Details-tab content, is
reset to flush via a scoped `.specs-history-panel .specs-panel` /
`.agency-panel` override rather than editing those two functions). The
grid's existing `auto-fit` behavior handles 3 children the same way it
already handled 2 - no new breakpoint logic needed.

### Row format

Reuses `renderSpecsPanel()`'s own already-shipped `.specs-grid`/
`.specs-row` markup (small-caps uppercase label above a plain-text value,
matching `.detail-stats`/`.detail-stat`'s established convention) - not
rebuilt, not a new icon grid.

### Missing-data handling - now genuinely common (3 of 8 portals ship data), not hypothetical

`renderSpecsPanel()` already omits any single missing field (a listing
with only `floor_number` known renders a one-cell grid, not a five-cell
grid with four dashes) and returns `''` when nothing at all is known -
this part of the original design already matched section 3's "omit the
row" recommendation once real data existed to test it against. What was
missing, and is now fixed, is the **whole-panel** empty case: an empty
string collapsing a grid cell to nothing next to two full-height panels
reads as a broken layout, not "not specified" - especially now that this
sits outside the click-gated tab where a genuinely empty string was
easy to miss unnoticed. `renderSpecsHistoryPanel()` now reuses the
platform's shared `emptyStateHtml()` treatment (icon + title + message,
the same pattern already used for e.g. the Area Data tab's "Area data not
available" state) rather than rendering nothing, with copy naming the
per-portal cause plainly: *"{portal} doesn't publish property type,
construction, floor, or agency details for this listing yet - coverage
currently varies by portal and fills in as it becomes available."*

### `syncHistoryPanelHeights()` dependency - not known to the original doc, now handled

Added 2026-09-26 (before this doc's original research pass ran, but not
mentioned by it) specifically to fix a real live height-desync bug
between the map and price-history panels, `syncHistoryPanelHeights()`
(index.html, called from `renderListingDetail()`) hardcoded exactly two
selectors: `.radius-panel` and `.price-history-panel`. **Adding a third
`.detail-history-row` panel without updating this function would have
quietly reintroduced the exact bug it exists to prevent** - the two
original panels would keep equalizing with each other while the new one
sat at its own unmanaged height. Fixed as part of this same change, and further corrected in Missy's
re-review (an earlier version of this fix and this note claimed a
`.radius-panel, .price-history-panel, .specs-history-panel` selector
list was "generalized" - it wasn't, it was still a fixed 3-name list that
a genuine 4th panel would silently miss): `syncHistoryPanelHeights()` now
reads `row.children` directly rather than naming any panel class at all,
so it measures and equalizes however many direct children
`.detail-history-row` actually has - genuinely no future edit needed here
when a panel is added or removed, verified against the real markup that
each of the three current panel-producing functions emits exactly one
wrapping `<div>` as a direct child of the row (so `row.children`'s count
matches the panel count, not some other DOM structure).

---

## 4. Per-portal extractability assessment - corrected ranking

| Portal | Real status | Ease | Notes |
|---|---|---|---|
| **alo.bg** | **SHIPPED** - `extract_specs_alo()`, full field set (property_type_raw, construction_type, built_year, completion_status, floor_number, floor_qualifier, features, has_elevator, furnished, has_central_heating, agency_name, agency_website) | **Already done - least uncertain of any portal here** | The original doc rated this "Uncertain - verify live before committing" based on general-knowledge guessing; that was wrong even at the time it was written, since the real extractor already existed in this same codebase. Nothing further needed unless expanding beyond the current field set. |
| **bazar.bg** | **SHIPPED** - `extract_specs_bazar()`, same field set minus agency contact (this portal's extractor doesn't collect agency name/website) | **Already done - least uncertain, same as alo.bg** | Same correction as alo.bg: previously rated "Uncertain - verify live before committing," actually already shipped and working via `backfill_detail_bazar.py`. |
| **imoti.bg** | **PARTIALLY SHIPPED** - `extract_specs_imoti_bg()` gets `property_type_raw`/`features`/`has_elevator`/`furnished`/`has_central_heating` from real schema.org ld+json, but **cannot** get `construction_type`/`built_year`/`completion_status`/`floor_number`/`floor_qualifier` - no core schema.org vocabulary term exists for any of them (see section 1C, and that function's own comment for the concrete next step: check `additionalProperty` once live access exists) | **Not a blanket "Easy"** - the shipped subset is done; the missing subset is a specific, structural, unsolved gap, not a general confidence rating | The original doc rated this portal a flat "Easy" with no field-level distinction. Correcting: rate the shipped fields as done, and the missing fields as their own, harder, dedicated task (needs either live-page inspection for a real `additionalProperty` mapping, or a different extraction source than ld+json entirely). |
| **homes.bg** | **NOT SHIPPED - needs a new capability, not just a selector.** The one confirmed data point (backlog item 9 / PR #217) is a **single combined string** ("Тухла/Бетон, Полуобзаведен" - construction material AND furnishing status joined in one field), read from the **search-results JSON** (`offer["description"]`, despite the misleading key name) - `scraper_homes.py` never fetches homes.bg's detail page at all today (confirmed in that scraper's own code comment: "which this scraper never fetches, since it only ever calls the paginated search/listing endpoint"). Building out a real Specifications panel for this portal - floor, built year, completion status, etc., the fields most likely to only live on the detail page - requires adding that detail-page fetch first, the same new capability backlog item 9 already flags as the prerequisite for a real homes.bg description too. | **Prerequisite work needed before this is "Easy"** | The original doc rated this "Easy, and de-risked" and implied the one known string was proof the rest would be simple. Corrected: the one string is real, but (a) it's one field, not two independently structured ones - **do not assume a fixed split order without verifying it against real, current data first**, since a search-results tag line is exactly the kind of thing that could reorder or vary by category - and (b) it doesn't establish anything about whether floor/built-year/etc. exist anywhere accessible without the new detail-page-fetch capability this portal doesn't have. |
| **imot.bg** | Not shipped, general knowledge only | Believed easy (dedicated "characteristics" table expected) - unchanged from the original doc, not re-verified this session | Highest-confidence *unshipped* portal, per the original doc's WebSearch corroboration - still not a live audit. |
| **imoti.net** | Not shipped, general knowledge only | Believed easy with an English-page caveat (unchanged from the original doc) | `docs/backlog.md` item 5's English-page category-classification bug risk still applies to any future label/enum extraction here. |
| **sales.bcpea.org** | Not shipped, general knowledge only | Likely easy but format may differ (legal-document style) - unchanged from the original doc | Structurally different from the marketing portals per backlog items 4/9; worth its own dedicated look. |
| **olx.bg** | Not shipped, general knowledge only | Uncertain - verify live before committing (unchanged from the original doc - this uncertainty rating was always correctly placed here, just wrongly ALSO applied to alo.bg/bazar.bg) | Least-confirmed structural claim of the truly-unshipped portals. |

**Overall read, corrected:** alo.bg and bazar.bg need no further backend
work for the fields listed in section 2's "already real" table - they're
done. imoti.bg is half-done, with a specific named gap. homes.bg needs a
new fetch capability before any of this can be built there, not just a
selector. imot.bg, imoti.net, olx.bg, and sales.bcpea.org remain
completely unverified general-knowledge guesses, same confidence level as
the original doc left them - **this task deliberately did not extend
extraction coverage to any of them** (out of scope for the relocation fix
this correction shipped alongside; a reasonable fast-follow, not required
here).

---

## 5. Handoff notes - frontend done, backend scope corrected

**Frontend: DONE as of this correction.** `renderSpecsHistoryPanel(l)`
(index.html) wraps the existing `renderSpecsPanel(l)`/`renderAgencyPanel(l)`
completely unchanged, as a third `.detail-history-row` child, with a
graceful empty state and `syncHistoryPanelHeights()` updated to cover it.
No new field logic was added on the frontend - see section 3.

**Per-portal extraction builder(s), if picking up further work:**
- alo.bg and bazar.bg: nothing to do for the fields in section 2's
  "already real" table.
- imoti.bg: the real remaining task is narrow and specific - find a real
  `additionalProperty` (or other) source for
  `construction_type`/`built_year`/`completion_status`/`floor_number`/
  `floor_qualifier` on a live page; don't assume this is a general "easy"
  job the way the original doc did.
- homes.bg: the real remaining task starts with adding a detail-page
  fetch capability (the `backfill_detail_alo.py`/`backfill_detail_bazar.py`
  pattern this repo already uses for other large portals is the existing
  precedent to follow) - only after that exists does splitting or
  verifying the one known combined string become meaningful. Don't split
  it blind off this doc's assumed order without a real sample to check
  against.
- imot.bg, imoti.net, olx.bg, sales.bcpea.org: unchanged from the
  original doc's guidance - do one live fetch per portal before writing
  selectors, write to the real shared column names from section 2 (not a
  new parallel schema), and use `category_classifier.py`'s shared-module
  precedent (`docs/backlog.md` item 5) as the model if a normalization
  helper becomes worth building once more portals are involved.

---

## 6. Process note

**This correction's own session made real code and doc changes** (not a
docs-only pass): `renderSpecsHistoryPanel()`, its CSS, and the
`syncHistoryPanelHeights()` fix in `index.html`, plus this doc and the
`property-filter-spec.md` cross-reference, in an isolated git worktree off
a fresh `origin/main`, per `CLAUDE.md`'s shared-working-directory
guidance. No scraper, sync, or schema file was touched - the 3-portal
extraction described in section 1 already shipped in earlier commits
(`bd510274`, `f9272166`, `28b507c2`, `ac80d36e`, `1c5873f7`), independent
of this fix. Per `CLAUDE.md`, **not self-merged** - pushed for Missy's
re-review.
