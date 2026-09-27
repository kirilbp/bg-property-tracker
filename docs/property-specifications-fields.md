# Listing "Specifications" section - field list, display format, and per-portal extractability

Compiled by Nosy, in response to the user's direct request: *"Specifications
on every listing still missing. They need to be built in a section (same
size and next to the map section). Every listing must include
specifications from the original listing."*

This is a **focused doc, not a section inside `docs/property-filter-spec.md`**,
following the exact precedent that doc already set for
`docs/deal-calculator-formulas.md` (see that doc's own section 8: a UK
screenshot alone couldn't answer the question, so independent research was
split into its own file and cross-referenced). The same applies here: the
UK reference material (`property-filter-spec.md` section 5's Due Diligence
panel: *"Bed/bath/garage icons, floor area: replicable"*, *"'Existing
Extension' tag, Construction age (date range): replicable if source data
includes build year/renovation info"*) told us this kind of field belongs on
imotenradar, but it can't tell us what a **Bulgarian** listing actually
publishes - that required its own research, done here. A one-line
cross-reference has been added to `property-filter-spec.md` section 5
pointing here; nothing else in that document was changed.

**Confirmed before starting:** grepped all 8 scrapers
(`scraper.py`, `scraper_alo.py`, `scraper_bazar.py`, `scraper_bcpea.py`,
`scraper_homes.py`, `scraper_imot.py`, `scraper_imoti_bg.py`,
`scraper_olx.py`) - none extract floor level, total floors, construction
type, year built, heating, elevator, or furnishing status today. This is
genuinely new scope, not a regression.

---

## 0. Sourcing note - read this before trusting any specific field claim below

**Live access to all 8 portals was attempted and blocked.** A real, current
listing URL was pulled from this repo's own committed data
(`data/leads*.json`) for every portal and fetched via `WebFetch`:

| Portal | URL attempted | Result |
|---|---|---|
| imoti.net | `imoti.net/en/obiava/.../tristaen/6272314/...` | `EGRESS_BLOCKED` |
| homes.bg | `homes.bg/offer/kyshta-za-prodazhba/.../hs296609` | `EGRESS_BLOCKED` |
| imot.bg | `imot.bg/obiava-1b175093643714011-...` | `EGRESS_BLOCKED` |
| olx.bg | `olx.bg/d/ad/mnogostaen-apartament-...` | `EGRESS_BLOCKED` |
| bazar.bg | `bazar.bg/obiava-56169327/...` | `EGRESS_BLOCKED` |
| alo.bg | `alo.bg/prodavam-apartament-11243706` | `EGRESS_BLOCKED` |
| sales.bcpea.org | `sales.bcpea.org/properties/90481` | `EGRESS_BLOCKED` |
| imoti.bg | `imoti.bg/продажби/.../515376.htm` | `EGRESS_BLOCKED` |

Every one was blocked by this sandbox's network egress proxy - the same
block `docs/design-guidelines.md` already documented for imot.bg/imoti.net
and that Missy and Scrapy have both independently hit in prior sessions
(backlog items 4, 6, 9). **Nothing below is a pixel-level live audit.**
A handful of `WebSearch` queries were run as a secondary check and are cited
where they add anything, but search snippets are not a substitute for
seeing a real rendered page either.

Given that, the field list below is built from three tiers of evidence,
labeled per field/portal so nothing is silently presented as more solid
than it is:

1. **CONFIRMED, from this codebase's own data** - the strongest evidence
   available this session, not from Property Filter or general knowledge.
   One concrete example anchors this whole doc: `docs/backlog.md` item 9
   documents that `scraper_homes.py` was writing homes.bg's
   **construction-material/furnishing tag line** ("Тухла/Бетон,
   Полуобзаведен" - "Brick/Concrete, Semi-furnished") into the
   `description` field by mistake, fixed in PR #217. That bug is direct,
   confirmed proof that homes.bg's listing pages carry a distinct,
   separately-rendered construction-type + furnishing-status field
   *outside* the free-text description - not a guess, an artifact of a
   real scraper bug already found and documented in this repo.
2. **General knowledge of the Bulgarian real-estate-portal genre** - Nosy's
   own training knowledge of imot.bg, imoti.net, imoti.bg, homes.bg, olx.bg,
   bazar.bg, alo.bg and BG judicial-auction listings as a category. This is
   knowledge of a well-established, long-running national market, not a
   guess extrapolated from unrelated markets - but it is still **not** a
   confirmed live audit, and portal UIs change over time. Flagged
   **GENERAL KNOWLEDGE** per field/portal below.
3. **WebSearch snippets** - a handful of search results (Bulgarian-language
   queries about each portal's field labels) that corroborate the
   general-knowledge claims without being a full page view. Flagged
   **SEARCH-CORROBORATED** where used.

**Recommendation to whoever picks up the per-portal extraction work:**
before writing a single selector, do one live fetch per portal from a
network-capable environment (this sandbox cannot) and sanity-check the
field list below against the real current page - this doc is a strong
starting point, not a substitute for that five-minute check.

---

## 1. What already exists today - don't duplicate it

Before adding new fields, it matters that **imotenradar already has a
partial answer to "specifications" today**, and the new section must be
positioned as a complement to it, not a duplicate:

`index.html`'s `KEYWORD_DICTIONARY` / `extractKeywordTags()` /
`renderKeywordsPanel()` (already shipped, ~line 6104-6166) mines each
listing's free-text `description` + `title` for keyword matches and
renders them as tag pills, grouped into "Sale features", **"Property
features"**, and "Close by". The "Property features" group already
covers, as **boolean detected/not-detected tags, not structured values**:

- Parking, Garage, Elevator, Balcony / terrace, Furnished, Renovated,
  Brick construction, Air conditioning, High ceilings.

This is the exact feature `property-filter-spec.md` section 5 already
flagged as *"an NLP/keyword-extraction pattern... genuinely one of the
better features to prioritize"* - it's built, and it's good. But it has
two real limits worth naming plainly, because they're exactly what the new
Specifications section should fix:

1. **It's presence-only, not value-bearing.** It can say "Elevator" is
   mentioned, but not "3rd floor of 8" or "built 1998" or "gas heating" -
   there's no slot for an actual number or an enum value, only a yes/tag.
2. **It depends on `description` text, which backlog item 9 already found
   is missing or badly wrong for most listings on most portals** (0% for
   imoti.net, ~35% coverage with 52-char average on alo.bg, 92% coverage
   but wrong-field on homes.bg pre-fix, etc.). A field that only exists
   inside free text inherits every one of those data-quality problems.

**The new Specifications section's job is specifically the fields that are
usually published as their own labeled field on a source portal (a
"Основни данни" / "Характеристики" table, or a form-driven attribute list),
not fields that only ever appear as prose** - i.e. exactly the category of
field the homes.bg bug above proves exists separately from `description`.
Floor/total-floors, year built, heating type, and a real construction-type
enum are the new section's focus; Parking/Garage/Elevator/Balcony/
Furnished/Brick as *boolean tags* should stay exactly where they are in the
existing keywords panel - don't re-implement them as a second, competing
UI element. (Elevator specifically: if a portal *also* exposes it as a
structured yes/no field rather than only inline text, extracting it
structurally and feeding it into the new section as a real value alongside
Floor/Total Floors is a reasonable upgrade - but the boolean tag path
should keep working as the fallback for portals that don't.)

---

## 2. Recommended field list, priority order

Each field: normalized key (for the data layer / scraper schema), the
Bulgarian label(s) it's known/believed to appear under, a UI label, its
value format, which property types it applies to, and its evidence tier.

### Tier 1 - core structural specs, worth a guaranteed row slot in the section

| # | Normalized key | BG label(s) seen/expected | UI label | Value format | Applies to | Evidence |
|---|---|---|---|---|---|---|
| 1 | `floor` + `total_floors` | Етаж / Етажност | "Floor" | `"3 of 8"` (combine both into one row when both present; if only one is known, show just that one, never a fabricated other half) | Apartments (multi-unit buildings); N/A for standalone houses/plots | GENERAL KNOWLEDGE - this is the single most standard structured field across Bulgarian apartment listings |
| 2 | `construction_type` | Тип строителство / Конструкция: Тухла (brick), Панел (panel/precast), ЕПК (a specific Bulgarian large-panel system), Гредоред (older timber-beam), Стоманобетон/Монолитна (reinforced-concrete monolithic) | "Construction" | one of a fixed enum (see vocabulary note below) | Apartments and houses | GENERAL KNOWLEDGE, **CONFIRMED indirectly**: homes.bg bug (section 1) shows this exact category of field exists as a distinct source field, not just prose |
| 3 | `year_built` | Година на строеж / Строителна година | "Year built" | 4-digit year, or a decade range if that's all the source gives (e.g. "1980s") | Apartments and houses | GENERAL KNOWLEDGE |
| 4 | `heating` | Отопление: ТЕЦ (district/central heating), Климатик (A/C heat pump), Локално/Парно (local boiler), Печка (stove), без отопление | "Heating" | one of a fixed enum | Apartments and houses | GENERAL KNOWLEDGE |
| 5 | `furnishing` | Обзавеждане: Обзаведен / Полуобзаведен / Необзаведен | "Furnishing" | Furnished / Semi-furnished / Unfurnished | Apartments and houses (not land) | GENERAL KNOWLEDGE, **CONFIRMED indirectly** by the same homes.bg bug ("Полуобзаведен" was literally in the mis-scraped string) |

### Tier 2 - common, but keep as structured values only when the source gives a real one (not a text-mined guess); the boolean-tag fallback already covers "mentioned somewhere"

| # | Normalized key | BG label(s) | UI label | Value format | Applies to | Evidence |
|---|---|---|---|---|---|---|
| 6 | `exposure` | Изложение: Юг/Север/Изток/Запад, combinations (e.g. "Юг/Изток") | "Exposure" | one or two of N/E/S/W | Apartments mainly | GENERAL KNOWLEDGE |
| 7 | `elevator` | Асансьор: Да/Не | "Elevator" | Yes/No, only when the source gives it as a real field distinct from the keyword-tag text-mining path in section 1 | Apartments in multi-story buildings | GENERAL KNOWLEDGE - overlaps with the existing keyword tag, see section 1's note |

### Tier 3 - category-specific, conditional on property type, lower priority but cheap if already scraped

| # | Normalized key | BG label(s) | UI label | Value format | Applies to | Evidence |
|---|---|---|---|---|---|---|
| 8 | `yard_sqm` | Дворно място / Двор | "Yard" | m² | Houses only | GENERAL KNOWLEDGE |
| 9 | `regulation_status` | Регулация: В регулация / Извън регулация | "Zoning" | In zone / Out of zone | Plots/land only | GENERAL KNOWLEDGE, lower confidence |
| 10 | `cadastral_id` | Идентификатор по кадастъра | "Cadastral ID" | reference string, ties to the existing `property-filter-spec.md` section 5 note about a cadastral identifier as the weak BG substitute for a UK Land Registry title number | Any, but realistically only ever populated on sales.bcpea.org's legally-formatted auction listings | GENERAL KNOWLEDGE + property-filter-spec.md section 5 cross-reference |

**Deliberately excluded, do not build:**
- **Tenure/ownership type** - already ruled UK-only-mostly-inapplicable in
  `property-filter-spec.md` section 4 (Bulgarian property is
  overwhelmingly freehold-equivalent).
- **EPC / energy-efficiency rating** - already flagged in
  `property-filter-spec.md` sections 3/4/5 as a real Bulgarian scheme that
  *may* exist (сертификат за енергийна ефективност) but with no confirmed
  scrapable source found yet; don't add a slot for it until that's
  resolved, to avoid a permanently-empty row.
- **Rooms/total area/price/price-per-m²** - already exist as their own
  fields elsewhere on the page (title strip, `detail-stats`); don't
  duplicate them inside the new Specifications section.

**Vocabulary normalization note (for the scraper-side builder):** each BG
source site will phrase these differently (e.g. "тухла" vs "тухлена
конструкция" vs "Brick" on imoti.net's English pages, similar to the exact
English/Bulgarian keyword-matching problem `category_classifier.py` already
solves for property type - see `docs/backlog.md` item 5). Recommend a small
shared `normalize_specifications()` helper (new module, e.g.
`spec_normalizer.py`), mirroring the already-working precedent of
`category_classifier.classify_listing()` being shared across
`scraper_alo.py`/`scraper_imoti_bg.py`/`scraper.py` - one place owns the
BG-term-to-canonical-enum mapping so all 8 scrapers write the same
normalized values instead of each inventing its own strings.

---

## 3. Display format and placement

### Placement - "same size and next to the map section"

The current listing detail page already has exactly the row this request
describes: `.detail-history-row` (in `renderListingDetail()`, `index.html`
~line 6852), a CSS grid (`grid-template-columns: repeat(auto-fit,
minmax(240px, 1fr))`, `gap: 24px`) currently holding two same-styled panels
side by side - `renderRadiusPanel(l)` (the map) and `.price-history-panel`.
It already collapses to one column at narrow widths with no extra work.

**Recommendation:** add the new Specifications panel as a third child of
this same grid (`renderSpecificationsPanel(l)`, called right alongside
`renderRadiusPanel(l)` and the price-history panel), reusing the exact same
panel styling already defined for `.price-history-panel` (`background:
var(--ivory-deep); border: 1px solid var(--taupe-light); border-radius:
6px; padding: 16px 18px;`). This satisfies "same size, next to the map"
literally, requires no new CSS grid work (the row is already `auto-fit`),
and keeps the map/price-chart/specifications trio visually consistent.
**This exact placement (third grid cell vs. its own separate row) is a
judgment call, not something the user specified pixel-for-pixel** - flagged
so whoever builds it can adjust if a three-way row reads too cramped once
real content is in it; the styling reuse is the load-bearing
recommendation, the exact grid slot is a reasonable default.

### Row format - reuse the existing `.detail-stats` / `.detail-stat` convention, not a new icon grid

`index.html` already has an established label+value convention used for
the top summary stats and the price-history stats
(`.detail-stats`/`.detail-stat`, ~line 374-377): a grid of cells, each with
a small-caps uppercase label (`font-size: 11px`, `letter-spacing: 0.03em`,
taupe color) above a plain-text value (`16px`, `600` weight, ink color) -
**no icons**. This already matches `docs/design-guidelines.md`'s explicit
anti-pattern #1 and #7 (avoid dense icon-grid stat blocks; prefer text
labels over icon-only elements). The new Specifications panel should reuse
this exact `.detail-stats`/`.detail-stat` markup pattern - one cell per
field from section 2 above (label = "Floor", value = "3 of 8", etc.) -
rather than inventing a new icon-plus-label row style. This also means no
new CSS is needed for the fields themselves, only the outer panel wrapper.

### Missing-data handling - this needs to be graceful, since it will be common

Every scraper currently writes **zero** of these fields, so on day one
every single listing will have an empty (or near-empty) Specifications
panel. Two existing precedents in this codebase already solve this shape of
problem and should both be reused rather than inventing a third pattern:

1. **Omit the row, don't show a placeholder dash, for a single missing
   field.** The existing `.detail-stat` cells elsewhere on the page use a
   `?? '–'` fallback (e.g. `l.score ?? '–'`) because those cells are always
   meaningful stats the platform itself computes. Specifications are
   different: most will be simply absent per-listing, and rendering five
   "–" cells in a row reads as broken, not "not specified". **Recommend:
   only render a `.detail-stat` cell for a field if the value is
   non-null** - i.e. a listing with only `floor`/`total_floors` known
   renders a one-cell panel, not a five-cell panel with four dashes.
2. **If literally zero fields are known for a listing, show one graceful
   sentence instead of an empty-looking panel** - directly mirroring the
   existing `renderKeywordsPanel()`'s own empty state (*"No description
   available to extract keywords from yet."*) and the plain-text fallback
   already used for missing descriptions (*"No description available from
   {portal} yet — this portal doesn't expose one on its listing grid."*,
   ~line 6884) and for missing photos (`.listing-photo-placeholder`, icon +
   "No photo available", ~line 5041/5527/5549). Recommended wording,
   matching that tone: *"No structural specifications available from
   {portal} yet — this portal doesn't expose them on its listing page."*
   This also gives a natural place to be honest that the gap is
   per-portal, not a platform bug, exactly like the description fallback
   already does.
3. This same "omit the row" principle already has a precedent one level up
   too: `docs/backlog.md`'s Area Data work has an
   `AREA_DATA_MIN_SAMPLE = 5` graceful "not enough data" empty state for
   thin areas, and the spec for that panel explicitly notes Property
   Filter itself shows a "Not Enough Data" state rather than faking
   numbers (`property-filter-spec.md` section 5, Area Data tab). Same
   philosophy applies here: never fabricate a value, never show a
   full-looking panel of dashes.

---

## 4. Per-portal extractability assessment

**All rows below are GENERAL KNOWLEDGE / SEARCH-CORROBORATED, not a live
audit - see section 0.** "Structure" describes how the field is believed to
appear on the listing page; "Ease" is a rough read on whether this looks
like a clean structured-extraction job (a labeled key-value table/list
already on the page) or a harder text-mining job (only ever in free
prose), for whoever scopes the per-portal work.

| Portal | Believed structure | Ease | Notes |
|---|---|---|---|
| **imot.bg** | Dedicated "characteristics" table/list on the listing page (labeled key-value pairs: Етаж, Етажност, Конструкция, Отопление, etc.) | **Easy** | One of Bulgaria's two largest dedicated real-estate portals (with imoti.net); WebSearch snippets (section 0) corroborate a structured characteristics block exists. Highest-confidence portal in this list. |
| **imoti.net** | Same category of dedicated portal as imot.bg; an "Property information" style block with labeled fields is expected on both the Bulgarian and English (`/en/`) pages | **Easy, with a caveat** | `docs/backlog.md` item 5 already found this scraper crawls the **English** `/en/` pages for category classification, and the English pages' Bulgarian-only category keywords caused a real, shipped bug - the same English-page risk applies here: labels/enum values will likely be in English on this scraper's crawled pages, not Bulgarian, and need their own vocabulary mapping (or a switch to the Bulgarian-language pages, the "bigger, riskier option" that same backlog item explicitly declined to take for the category-classification bug). |
| **imoti.bg** | Dedicated real-estate portal, same tier as imot.bg/imoti.net; expected labeled characteristics table | **Easy** | `docs/backlog.md` item 5's fix references `scraper_imoti_bg.py` as already sharing the good `category_classifier` pattern - a reasonable sign this scraper's existing code is already handling this portal carefully; worth using as the reference implementation once a first portal is picked for this feature, per that item's own note that imoti.bg is "a working reference for whoever fixes the other portals" (in the description-coverage context, but the same portal-maturity signal applies here). |
| **homes.bg** | Structured field(s) confirmed to exist separately from `description` - **the one portal with direct proof in this codebase**, not just general knowledge (section 1's construction-material/furnishing bug) | **Easy, and de-risked** | This is the strongest starting point of all 8 portals: we already know from a real, fixed bug exactly what a construction-type+furnishing string looks like in this portal's raw data ("Тухла/Бетон, Полуобзаведен"), so the "does this field exist at all" question is already answered here - recommend building/testing this portal's extraction first. |
| **sales.bcpea.org** | Judicial/private-enforcement-agent auction listings are a legally-formatted announcement, typically carrying an appraisal-report-derived technical description (construction type, year, floor/floors) plus a cadastral identifier and tax-assessment value, as a matter of legal form, not marketing copy | **Likely easy, but format may differ from the other 7** | GENERAL KNOWLEDGE, lower direct-experience confidence than imot.bg/imoti.net since this is a narrower/more specialized site category. `docs/backlog.md` items 4/9 already treat this portal as structurally different from the marketing portals (categorical "Auction" tag applied portal-wide regardless of text, low photo coverage 43.6%) - the same "different animal" pattern likely applies to specifications: expect a denser, more legalistic single block of text/table rather than a marketing-style icon row. Worth a dedicated look, not an afterthought. |
| **olx.bg** | OLX's real-estate posting form is, in Nosy's general knowledge of the OLX product across markets, dropdown/select-driven for several attributes (floor, construction type), which usually produces a structured "Details" panel on the resulting ad page - **but this is the single least-confirmed structural claim in this table** | **Uncertain - verify live before committing** | GENERAL KNOWLEDGE ONLY, not corroborated by search or codebase evidence the way homes.bg/imot.bg are. OLX is a general classifieds marketplace, not a real-estate-specific portal, and individual sellers can skip optional form fields - even if the panel exists structurally, per-listing fill rates may be much lower than on imot.bg/imoti.net. Flag for a live check before assuming this is a clean structured job. |
| **bazar.bg** | Similar general-classifieds-with-category-specific-fields pattern to olx.bg, plausibly with its own "Детайли" attribute panel for real estate | **Uncertain - verify live before committing** | Same confidence caveat as olx.bg - general knowledge only, not corroborated. `docs/backlog.md` item 9 already found bazar.bg's descriptions are short (avg 159 chars, "shorter than expected, check the selector" flag) - worth checking, while investigating that existing flag, whether some of that "missing" description text is actually specification data sitting in a separate structured panel the current scraper doesn't read at all (the same shape of thing the homes.bg bug turned out to be). |
| **alo.bg** | Same general-classifieds pattern as olx.bg/bazar.bg | **Uncertain - verify live before committing, same suspicion as bazar.bg** | `docs/backlog.md` item 9 found alo.bg's description average is only **52 characters** - unusually short even among the "coverage gap" portals, flagged there as needing a live check for "genuinely short source description... or another wrong-selector bug like homes.bg's". That open question and this doc's question are plausibly the same root cause: alo.bg may render specifications (floor, construction type, etc.) as their own labeled fields/icon row separate from a genuinely short free-text description, the same shape as the already-fixed homes.bg bug. **Recommend investigating this alongside backlog item 9's still-open alo.bg task, not as a separate blind effort** - same portal, likely same underlying page structure question. |

**Overall read:** imot.bg, imoti.net, imoti.bg, and homes.bg (the four
dedicated real-estate portals) are the highest-confidence, likely-easiest
targets - build and verify the extraction there first. sales.bcpea.org is a
plausible fifth easy target but structurally different (legal-document
style) and deserves its own dedicated look rather than reusing a
real-estate-portal template. olx.bg, bazar.bg, and alo.bg (general
classifieds platforms) are the least certain - alo.bg in particular is
worth investigating jointly with the already-open backlog item 9 short-
description question, since both may share the same root cause.

---

## 5. Handoff notes for the two builders

**Frontend builder** (adds the section to `index.html`):
- Expects a `specs` object per listing (or flat fields directly on the
  listing row, matching how `sqm`/`price_eur`/etc. already sit flat on
  `l`) with the normalized keys from section 2 - `floor`, `total_floors`,
  `construction_type`, `year_built`, `heating`, `furnishing`, `exposure`,
  `elevator`, `yard_sqm`, `regulation_status`, `cadastral_id`. All
  optional/nullable; render logic per section 3 (omit missing rows, omit/
  message the whole panel if none present).
- New function `renderSpecificationsPanel(l)`, called from
  `renderListingDetail()` inside `.detail-history-row` alongside
  `renderRadiusPanel(l)` and the price-history panel (section 3).
- Reuse `.detail-stats`/`.detail-stat` CSS as-is; no icons, matching
  `docs/design-guidelines.md`.
- Do not touch or duplicate `KEYWORD_DICTIONARY`/`extractKeywordTags()`/
  `renderKeywordsPanel()` - that panel stays exactly as-is (section 1).

**Per-portal extraction builder(s)** (scraper-side, likely one task per
portal or per portal-tier, independently shippable like backlog item 9's
per-portal description tasks):
- Start with homes.bg (already de-risked, section 4) and the three other
  dedicated real-estate portals (imot.bg, imoti.net, imoti.bg) before the
  three general-classifieds portals (olx.bg, bazar.bg, alo.bg) and the
  auction portal (sales.bcpea.org), per the confidence ordering in
  section 4.
- Do one live fetch per portal before writing selectors (this sandbox
  couldn't - see section 0) - don't build blind off this doc's
  general-knowledge field list alone.
- Write to a shared normalized schema (section 2's keys and enums), via a
  new shared `spec_normalizer.py`-style module rather than each scraper
  inventing its own strings, mirroring the existing
  `category_classifier.py` precedent (`docs/backlog.md` item 5).
- Investigate alo.bg's and bazar.bg's short-description questions
  (`docs/backlog.md` item 9, still open) jointly with this work, not
  separately - flagged in section 4 as plausibly the same underlying
  cause.

---

## 6. Process note - no code changed, docs-only

**This session made no changes to any scraper, schema, or frontend code** -
only this new doc and a one-line cross-reference added to
`property-filter-spec.md` section 5. This repo has a standing precedent for
shipping a pure research/design/scoping pass as its own docs-only PR rather
than bundling it with implementation (`docs/backlog.md` item 6 slice 2:
*"DONE (2026-09-23, Bossy, PR #228, docs-only, merged): design/scoping
done"*) - the same shape applies here. Recommend the same treatment: a
docs-only PR for this file (and the one-line cross-reference), reviewed and
merged on its own, with the frontend and per-portal scraper implementation
work filed as separate backlog items referencing it (Bossy's call, not this
doc's).

**A real limitation of this session, stated plainly:** no shell/git tool
was available, so this file was written directly into the working tree
rather than via an isolated worktree/branch/PR the way
`CLAUDE.md`'s shared-working-directory guidance recommends for anything
beyond a trivial docs edit. Before this is treated as ready to merge,
whoever has git access should run `git status`/`git log --oneline -5`
first to confirm nothing else is concurrently touching
`property-filter-spec.md` or this new file, then commit this addition (and
only this addition) on a branch and open the docs-only PR described above -
per `CLAUDE.md`, this should not be self-merged.
