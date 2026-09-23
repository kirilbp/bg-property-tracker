# Backlog

Owned by Bossy. Ordered list; work top to bottom unless a standing rule
(see `.claude/agents/bossy.md`) says otherwise. Update status here in the
same change that ships or resolves an item.

## 1. Audit fixes - DONE

Finding 1 (sanity guard: a portal returning near-zero results must never
delete its live listings) shipped in PR #167. Finding 2 (`detail_checked`/
`_detail_fetched` flags set only after a successful fetch, across
`scraper.py`, `scraper_imot.py`, `scraper_olx.py`, `scraper_bcpea.py`)
shipped in PR #168. Both verified with real unit tests before merge and
confirmed live on `main`. Nothing further needed unless a regression
turns up.

## 2. Login removed entirely - DONE (2026-09-22)

Not fixed - removed, per the user's explicit direct decision ("I want
login removed completely"), which does not need further confirmation.
This supersedes all the login-repair investigation below (kept for
history, not as an open problem anymore).

Shipped: the entire Supabase-Auth-gated login system added by the old
backlog #62 (login modal, `CURRENT_USER`/`applyAuthState`/
`onAuthStateChange`, the two "log in to use this" gate cards on Lead
Generators and Dashboard, and the sidebar account/logout UI) is gone
from `index.html`. Saved listings, Lead Generators, and Reminders are
back to a plain, no-login, this-browser-only `localStorage`
implementation - functionally equivalent to how they worked before
backlog #62, not byte-identical to the old code. No Supabase backend
schema/RLS/data was touched or dropped - see `docs/decisions.md`'s
2026-09-22 entry for the full reasoning, what's left dormant on the
backend as a flagged future cleanup candidate (in particular
`check_reminders.py`'s daily "open a GitHub issue for an overdue
reminder" job, which now has nothing new to read since reminders no
longer write to Supabase), and how it was reviewed - this session had
no subagent-spawning tool available, so it was self-reviewed directly
against Missy's own rubric rather than skipped; flagged there as a real
gap, not a shortcut taken lightly.

<details>
<summary>Prior investigation (kept for history only - not an open problem)</summary>

Valid credentials rejected on imotenradar.com. Confirmed so far (see
session history / `docs/decisions.md`): `index.html` and the GitHub
Actions secrets point at the same `SUPABASE_URL`
(`eoufgmmgwczixfajebhc.supabase.co`); that project's REST API returns
real listing data fine; but its Auth admin API (`/auth/v1/admin/users`)
reports **0 registered accounts**, both before and after the Supabase
Pro upgrade.

**Correction (2026-09-22):** an earlier version of this entry claimed
the user had "flagged a Paris project in another organisation as a
candidate" for where their real account might live. The user has since
stated plainly they never said this and no such project exists -
that claim was wrong and should not have been written here; apologies
for the confusion it caused. The user then confirmed directly from the
Supabase dashboard: `eoufgmmgwczixfajebhc` genuinely is imotenradar.com's
own project (matches by name and URL in the dashboard header), and the
account has exactly one Supabase project total, across all 3 orgs on the
account (imotenradar, imotenradar.com, and the personal "Kiril Petrov"
org) - "All Organizations" view shows a single project card. There is no
other project this could be.

The Authentication -> Users screen for this project shows "No users in
your project" with zero rows rendered, but a footer count of "Total: 10
users (estimated)" - the mismatch between an empty rendered table and a
non-zero "(estimated)" count is consistent with a stale Postgres
statistic (`pg_class.reltuples`-style estimate that hasn't been
re-analyzed since rows were deleted), not real hidden users - i.e. the
table is most likely genuinely empty now, matching the Auth API's "0
registered accounts" result, not contradicting it.

Reframed problem (now moot): this was not a wrong-project routing
issue, it was that no real user account existed in imotenradar.com's
own Supabase project. The user has since decided the answer isn't to
debug or recreate that account - it's to remove the login requirement
entirely, which is what shipped above.

</details>

## 3. alo.bg grid crawl silently dead since 2026-09-16 - mismarking ~88k listings "removed", some already showing as "Sold" live - DONE (2026-09-22)

**Status: all 4 tasks implemented, reviewed by Missy (she independently
reconstructed the git-rebase-conflict semantics in a scratch repo and
verified them herself rather than trusting the PR's claim, and re-ran
`merge_history_conflict.py` against a real reconstructed conflict - no
blocking problems found), and merged in
[PR #197](https://github.com/kirilbp/bg-property-tracker/pull/197).**
A real `scrape-large.yml` run was dispatched immediately after merge to
confirm the fix works live and alo.bg's listing counts actually recover
- see the top of this file / ask for current status, this needs
confirming against the real completed run, not assumed from the code
fix alone. Full investigation and what was actually done is in
`docs/decisions.md`'s 2026-09-22 entry ("Backlog items 3 and 4
implemented..."); summary:

- **Task 1 (why the crawl "died") - root cause found, and it was NOT
  `fetch_listings()`.** The grid crawl itself was working every single
  day (77,625-89,324 real listings found per run, confirmed from GitHub
  Actions job logs for 2026-09-16 through 2026-09-19). The real bug was
  in `scrape-large.yml`'s commit step: `git checkout --ours` during a
  `git pull --rebase` conflict keeps the *upstream* (main's) version, not
  the local run's - backwards from what its own comment claimed - and a
  real conflict against `backfill-detail-alo.yml`'s *hourly* commits to
  the exact same files happens near-daily, not rarely (that workflow's
  own header comment claiming these files were "disjoint from... any
  hourly backfill" was wrong). Fixed via `merge_history_conflict.py`, a
  real per-listing merge for conflicted `data/history*.json` files, wired
  into both workflows' conflict fallback in place of blind
  `checkout --ours` for those specific files.
- **Task 2 (fail loud)**: `check_scrape_freshness.py`, a new
  non-`continue-on-error` step at the end of `scrape-large.yml` - fails
  the whole run if the freshest committed snapshot is stale (>30h) or a
  portal's active-listing share collapses (<40%, every portal's healthy
  range is 72-91%). Confirmed it correctly fails loud against the
  currently-still-corrupted real data in the repo right now.
- **Task 3 (remediate corrupted status data)**: deliberately not a
  revert script - `source_status`/`"sold"` both recompute fresh from
  `history_alo.json`'s own snapshot recency every run, so a real
  successful crawl self-heals it. A `scrape-large.yml` run was manually
  dispatched right after merge to confirm this live - check its result
  (run started ~2026-09-22T14:59 UTC) before considering this task
  fully closed.
- **Task 4 (git-log-hygiene)**: turned out to be entangled with task 1
  after all (not just possibly, per the original task wording) - same
  `checkout --ours` bug, same fix.

## 4. "Browse by Council" province matching: ~90%+ of the 9,247 "Others" bucket is a real bug, not genuinely non-Bulgarian data - DONE (2026-09-22)

From the user directly reporting the live site, then confirmed by Missy
sampling ~8,787 raw listings that fail the same matching logic (see
`docs/decisions.md` 2026-09-22 entry for her full report). The user's
own framing: Bulgaria's 28 oblasts cover 100% of its territory, so a
large "Others" bucket in the province browse section is inherently
suspicious, not expected. Confirmed: it's real - two distinct,
well-isolated root causes account for essentially all of it, only
~5-6% is legitimately foreign/unparseable data.

**Confirmed facts:**
- ~49% of the sampled bucket: an **alo.bg scraper bug**, not a lookup-
  table gap. `scraper_alo.py` line 281 writes a literal
  `area, city = "Bulgaria", None` placeholder whenever its `LOCATION_RE`
  regex (lines 147-150) fails to match a listing card's text (happens on
  14% of alo.bg's 87,979 raw listings). Compounding it: line 314's title
  fallback (`title = a.get_text(...) or text[:100]`) stores the raw,
  100-char-truncated container text (agency name + "преди N дни" +
  garbled text) instead of the real listing title, cutting the text off
  *before* the location words that would otherwise let the existing
  oblast-matching fallback recover it. Real example: `alo_11149326`
  (https://www.alo.bg/dvustaen-apartament-v-centara-na-slanchev-bryag-11149326)
  stores `city=None, area="Bulgaria"` with its title truncated mid-word
  right before "Слънчев бряг ... Бургас" would have appeared. Manual
  review of a random sample of the non-explicitly-foreign listings in
  this bucket found them essentially all genuinely Bulgarian (Sunny
  Beach, Golden Sands, Sofia/Plovdiv/Stara Zagora neighborhoods).
- ~51% of the sampled bucket: a genuine **`BG_MUNICIPALITY_TO_OBLAST`
  coverage gap** in `sync_to_supabase.py` (lines 522-645) - but
  structural, not "a few cities missing." The table covers Bulgaria's
  265 official municipality *seat* names, not its ~5,300 actual
  settlements; a village whose municipality has a different name (the
  common case) is invisible to it. 1,545 distinct real Bulgarian
  settlement names were found unmatched (722 appearing only once) -
  e.g. Типченица, Изворово, Илинденци, Цалапица. A real fix needs a
  full settlement -> municipality -> oblast table (thousands of
  entries, an authoritative gazetteer), with the same per-name ambiguity
  discipline already shown for "Бяла" (correctly excluded - a real,
  different municipality in both Varna and Ruse oblasts) - Missy found
  at least one more name needing that same care ("Средец": both a real
  Burgas-oblast town and a central Sofia-grad district).
- One small, safe, purely mechanical fix already identified: "Вълчи Дол"
  (Valchi Dol, a real unambiguous Varna-oblast municipality) is missing
  from the Varna section of `BG_MUNICIPALITY_TO_OBLAST` even though its
  sibling municipalities are all listed.
- One more small, separate issue worth a look: a cluster of olx.bg
  listings near Близнаци (Varna coast, real in-Bulgaria coordinates)
  falls inside Varna oblast's bounding box but `oblast_key_from_latlng()`
  (`sync_to_supabase.py` lines 471-499)'s point-in-ring test still
  returns `None` for them - the polygon check itself is failing on
  legitimate in-Bulgaria points, not just missing a name mapping.
- Legitimately NOT a bug, confirmed correct: "Бяла" (~1% of the sample,
  already deliberately excluded, see above) and ~92 homes.bg listings
  (~1%) with genuinely empty address data captured by the scraper (no
  location text anywhere to match against - a separate scraper gap, not
  a matching-logic bug).

**Tasks (independently-shippable, different fix shapes - do not conflate):**
1. Fix `scraper_alo.py`: diagnose why `LOCATION_RE` fails on ~14% of
   cards, stop writing the `"Bulgaria"` placeholder (leave the field
   empty/null instead so downstream matching can still try), and fix the
   title extraction to capture the real listing title instead of
   truncated raw container text. This is the ~49% piece - no amount of
   lookup-table expansion fixes it, the source fields are corrupted
   before matching ever runs.
2. Build a real Bulgaria-wide settlement -> municipality -> oblast
   table to replace/extend `BG_MUNICIPALITY_TO_OBLAST`'s municipality-
   seat-only coverage - the ~51% piece. Needs an authoritative source
   (NSI or similar gazetteer), and explicit handling for every
   settlement name that collides with a different oblast's name or
   district (flag and exclude, per the existing "Бяла" precedent, don't
   guess).
3. Small mechanical fix: add "Вълчи Дол" to the Varna section of
   `BG_MUNICIPALITY_TO_OBLAST`.
4. Investigate the `oblast_key_from_latlng()` point-in-ring failure on
   real in-Bulgaria coordinates (Близнаци/Varna coast cluster) - lower
   volume than tasks 1-2 but worth understanding since it's supposed to
   be the authoritative signal when present.
5. Fix homes.bg's empty-address capture gap (scraper-side, separate from
   this bug's matching logic) if it turns out to be cheap alongside
   task 1-2's work; file separately otherwise.

**Status (2026-09-22): tasks 1, 3, 4 implemented and verified; task 2
implemented and verified with a measured real impact; task 5
investigated, not fixed. Reviewed by Missy - she independently
re-derived the entire settlement table from the original source data
and reproduced every claimed number exactly (4,513 resolvable names,
521 ambiguous exclusions, the 2.9%->1.8% Others-bucket drop) rather than
trusting the PR's arithmetic, and found one non-blocking issue (a
misleading comment in `check_scrape_freshness.py` about other portals'
healthy activity range) that was corrected before merge. Merged in
[PR #197](https://github.com/kirilbp/bg-property-tracker/pull/197).
Full detail in `docs/decisions.md`'s 2026-09-22 entry ("Backlog items 3
and 4 implemented..."); summary per task:**
1. **Done.** `LOCATION_RE`'s own miss rate wasn't touched (that needs live
   alo.bg samples this sandbox's egress proxy blocks - same block Missy
   hit), but both compounding bugs are fixed: the `"Bulgaria"` placeholder
   is now `None`/`None` (confirmed it was leaking into the frontend's own
   neighborhood filter dropdown as a literal value), and the title
   fallback now keeps the text immediately before the price marker
   (where the location phrase actually lives) instead of blindly the
   first 100 characters. Verified end-to-end against the project's own
   unmodified `listing_oblast_key()` with a realistic reproduction: old
   behavior -> unresolved, new behavior -> correctly resolves to `burgas`.
2. **Done, different approach than originally scoped.** Rather than a
   hand-built table, sourced `yurukov/Bulgaria-geocoding`'s
   `settlements.csv`/`municipalities.csv` - the same dataset already
   backing `data/bg_oblast_boundaries.json` - and derived
   `data/bg_settlements_to_oblast.json` (3,784 new names, purely
   additive to the existing table) with automated ambiguous-name exclusion
   (521 of 4,513 names excluded for spanning >1 oblast - this
   independently rediscovered both "Бяла" and "Средец" with no special-
   casing, a good sign the rule generalizes). Cross-validated with zero
   contradictions against every name already in `BG_MUNICIPALITY_TO_
   OBLAST`. Measured real impact against the actual committed data: the
   "Others" bucket across all 8 portals drops from 8,763/304,988 (2.9%)
   to 5,633/304,988 (1.8%) - 3,130 listings newly resolved by this table
   alone, before task 1's alo.bg fix even gets a fresh crawl.
3. **Done.** Added to `BG_MUNICIPALITY_TO_OBLAST`'s Varna section.
4. **Done - real cause found, conservative fix shipped.** Not a bug in
   the point-in-ring algorithm itself (verified correct by hand-tracing
   real ring-edge crossings against the actual Близнаци coordinates) - the
   real point sits ~8m outside Varna's own simplified boundary polygon,
   ordinary coastline-simplification/GPS noise. Added a tested, tolerance-
   based fallback (`NEAR_BOUNDARY_TOLERANCE_DEG`, ~200-330m) that only
   resolves when exactly one oblast is within tolerance - two-or-more (a
   real shared border) stays unresolved rather than guessed. 34 of the
   real 36 Близнаци-cluster listings now resolve.
5. **Investigated, not fixed - filed as its own follow-up.** Confirmed
   Missy's exact numbers against real data (94 correctly-excluded "Бяла",
   92 genuinely empty). Traced the cause: `scraper_homes.py` reads
   `location` straight from homes.bg's own structured per-listing data
   object with no HTML parsing involved, so this isn't a parsing bug -
   homes.bg's own data genuinely has nothing for these listings on
   whatever endpoint this scraper reads. A real fix needs live network
   access to homes.bg (to check whether the detail page has more) - this
   sandbox's egress proxy blocks it, same block Missy hit. Left open.

## 5. imoti.net: 100% of listings mislabeled `category: "apartment"` - DONE (2026-09-22)

From Missy's 2026-09-22 daily audit (`docs/missy-findings/2026-09-22.md`,
filed as [issue #194](https://github.com/kirilbp/bg-property-tracker/issues/194)).
Originally folded in below items 3/4 while those were still in flight;
**moved to the top of the active backlog per the user's explicit
instruction (2026-09-22), once items 3/4 shipped** - it corrupts
category filters, Comparables, and area averages for ~26,804 listings,
a bigger blast radius than either of the two items it now follows.

**Confirmed facts:** `scraper.py` crawls imoti.net's `/en/` (English)
search URL and calls `classify_category(title)` on the scraped *English*
title. `classify_category()`'s keyword table (`geo_utils.py:55-65`) is
Bulgarian-only, so an English title can never match anything and every
single imoti.net listing (26,804 of 26,804) silently falls through to
the function's own documented default, `"apartment"` - even though
imoti.net's own search isn't apartment-scoped (scraped URLs carry 20+
distinct property-type path segments: `garaj` 279, `parcel` 1932,
`kashta` 938, `zemedelski-imot` 119, `magazin` 431, `ofis` 408, etc). At
minimum 4,916/26,804 (18.3%) carry a non-apartment type word in their own
scraped title/URL and are nonetheless bucketed "apartment" on the live
site - never showing under "Houses"/"Land"/"Garages"/"Shops"/"Business"
filters. Not the same as the already-documented bcpea.org case (that
portal's own apartment-only search URL makes the "apartment" default
correct there); imoti.net has no such workaround.

**Status (2026-09-22): root-caused, fixed, verified against real data,
already-committed data remediated, reviewed by Missy (verdict: safe to
merge - independently re-ran the backfill from the pre-fix data and
reproduced the committed result byte-for-byte, independently re-
classified all 26,881 records with zero mismatches against the stored
fields, and checked the new keywords against the full alo.bg/imoti.bg
datasets rather than just the PR's own sample), and merged in
[PR #199](https://github.com/kirilbp/bg-property-tracker/pull/199).**
Full investigation, the real regression caught and fixed
before shipping (a keyword collision with a common Bulgarian district
name), the regression check against the portals already on this
classifier, and a second related bug found and fixed in the same change
(Lead Generator saved-search filtering) are all in `docs/decisions.md`'s
2026-09-22 entry ("imoti.net 100%-'apartment' miscategorization... root-
caused and fixed"). Summary:

- **Real fix**: `scraper.py` migrated from `geo_utils.classify_category()`
  (Bulgarian-keyword-only) to `category_classifier.classify_listing()` -
  the shared classifier `scraper_alo.py`/`scraper_imoti_bg.py` already use
  for this exact reason - passing both the scraped title and the listing's
  own URL (which embeds a reliable Bulgarian-language type slug, e.g.
  `.../kashta/1234/`) as independent signals. Chose this over switching
  the whole scraper to crawl imoti.net's Bulgarian-language pages (the
  bigger, riskier option) since price/sqm/date extraction there doesn't
  depend on title language at all.
- Added a handful of English/Latin keywords to `category_classifier.py`
  for gaps confirmed live in imoti.net's own English titles/URLs
  (agricultural/development land, industrial/commercial property,
  restaurant, etc.) - scoped to the exact phrases observed, after an
  initial broader version caused a real false positive against a common
  Bulgarian district name ("Industrial Zone") and was tightened.
  Regression-checked with zero category changes against a 5,000-listing
  alo.bg sample and the full imoti.bg dataset.
- **Already-committed data remediated**, not just fixed forward:
  `backfill_category_imoti_net.py` reclassified all 26,881 existing
  `data/history.json`/`data/leads.json` records locally (title/url already
  stored, no re-crawl needed). Result: 21,399 flat, 2,360 land, 1,436
  house, 750 business, 603 shop, 333 garage (was 100% "apartment").
  **Corrected by Missy's PR review (2026-09-22)**: confidence breakdown is
  actually 91.73% high confidence (24,659) / 8.27% low confidence (2,222),
  not the "92.6%/0.26%" originally claimed here - that 0.26% figure
  (71/26,881) only covered the `no_keyword_match` subset and omitted
  2,150 records (8.0%) that are low-confidence for a separate reason,
  `single_signal_only`. Missy hand-checked 15 `single_signal_only`
  records and found all correctly categorized - traced to a real but
  pre-existing gap in `category_classifier.py`'s `flat` keyword list
  (has "ednostaen"/"dvustaen"/"tristaen" but is missing "chetiristaen"
  4-room and "mnogostaen" multi-room), which silently fails the URL-slug
  signal on those listings even though the title signal still matches -
  a scoring artifact, not a misclassification risk, and not introduced by
  this PR. Worth its own small follow-up to add the missing keywords.
- **Second bug found and fixed in the same change**: `index.html`'s
  `matchesLeadGenerator()` compared raw `category` against the Lead
  Generator modal's old-vocabulary checkboxes, which this fix would have
  made meaningfully worse (26,881 more listings changing vocabulary).
  Fixed to normalize through `typeFilterBucket()` like `findComparables()`
  already does.

**Two small follow-ups filed from Missy's review, neither blocking, both
still open:**
- Add the missing "chetiristaen" (4-room) and "mnogostaen" (multi-room)
  Latin-transliteration keywords to `category_classifier.py`'s `flat`
  list - closes the `single_signal_only` confidence gap above. Small,
  low-risk, mechanical.
- `scraper_imot.py` and `scraper_olx.py` still call
  `geo_utils.classify_category()` - the same Bulgarian-only-keyword
  function that caused this exact bug on imoti.net. Missy did not check
  whether either portal is crawled via an English-language URL the way
  imoti.net was; if either is, the same bug class could exist there.
  Needs its own investigation pass before assuming it's fine.

## 6. Site is very slow to load/refresh - slice 1 DONE, MERGED - two small slice-2-adjacent fixes DONE, MERGED - core slice 2 (server-side pagination) DONE, pending review - URGENT

From the user directly, unprompted (2026-09-22) - the live site
(imotenradar.com) refreshes/loads very slowly and needs to be made as
fast as possible.

**Root cause, confirmed by reading the real code (`index.html`), not
guessed:** every single page load calls `loadData()` ->
`fetchAllRows('merged_listings')`, which does
`sb.from('merged_listings').select('*').order('id').limit(1000)` in a
sequential keyset-pagination loop until it has pulled the **entire**
`merged_listings` table into the browser - on every refresh, for every
visitor, regardless of what they're actually looking at. `merged_listings`
is in the hundreds of thousands of rows (the same order of magnitude as
the ~304,988-raw-listing figure already measured for backlog item 4's
work, before cross-portal dedup) and each row is genuinely heavy - the
schema (`supabase/schema.sql`) includes a free-text `description`, a
`photos` jsonb array, and a `price_history` jsonb array per row, on top of
every numeric/text field, all pulled via `select('*')` (no column
narrowing at all). Batches are fetched **sequentially, not in parallel**
(a documented, deliberate tradeoff for keyset-pagination correctness - see
`fetchAllRows()`'s own comment), so total load time is roughly (row count
/ 1000) sequential round trips, each paying full network latency on top
of its own transfer time. **No caching layer at all** - confirmed via
grep, no `localStorage`/`IndexedDB` caching of `MERGED_LISTINGS` anywhere
- so this full fetch repeats from zero on every single refresh, not just
first visit.

**Not simply a missing-index problem** - `supabase/schema.sql` already
has indexes on `price_eur`, `sqm`, `area`, `city_key`, `type_bucket`,
`score`, `days_on_market`, `drop_pct`, `status`, and `oblast_key`, so the
schema is already reasonably well-prepared for real server-side filtered
queries; there's no `lat`/`lng` index yet, which will matter once
map/radius queries move server-side (see below). The real problem is
purely architectural: the client fetches everything, unfiltered, into an
in-memory `MERGED_LISTINGS` array, and essentially the whole SPA (listings
table/filters, home dashboard counts, map, per-listing lookups, area
dropdowns - confirmed via grep, `MERGED_LISTINGS` is referenced in 28
places across `index.html`) then operates against that in-memory copy.
That's a genuinely cross-cutting change, not a quick tweak.

**Connects to, but is not solved by, backlog item 15** (Supabase Pro
follow-ups): the code comment explaining why a full-table client load was
accepted in the first place cites free-tier connection-pool exhaustion as
the reason a fuller per-listing (`listing_sources`) load was cut back -
i.e. this design predates the Pro upgrade and was shaped around the old
500 MB/connection-pool constraints item 11 already flags for revisiting.
But even on Pro, shipping a multi-hundred-thousand-row, heavy-jsonb table
to every browser on every refresh is a real UX problem regardless of
backend capacity - this needs an actual query/architecture fix, not just
"now allowed since we're on Pro."

**One real complication already spotted, not yet resolved:** several
columns (`area_avg_price_per_sqm`, `pct_vs_area_avg`) are already
precomputed server-side per row by `sync_to_supabase.py`, so the area-
average/Comparables numbers shown on an individual listing do NOT need
the full dataset in browser memory - that's good news, it de-risks most of
the fix. But `findComparables()`'s own radius search does an in-memory
`MERGED_LISTINGS.filter()` scan by lat/lng distance against whatever's
currently loaded - moving that server-side properly would need a real
lat/lng index (PostGIS or a bounding-box index) that doesn't exist yet,
and is a legitimate open design question for whoever implements this, not
answered here.

**Not yet attempted - deliberately not touched this session.** Two real
blockers, not laziness: (1) this session has no `Agent` tool, so it can't
safely coordinate live with Dessy, who may be actively mid-edit on this
exact file (`index.html`) for backlog item 17's listing-detail redesign -
editing the same large file in parallel without a way to check her
current state risks a real collision, not a hypothetical one (confirmed
live during this session: another agent, Selly, pushed a commit to this
same shared branch while this session was working, so concurrent pushes
to this branch are a real, current condition, not a remote possibility);
(2) this sandbox's egress proxy blocks direct network access to Supabase
(confirmed live: a `curl` to `eoufgmmgwczixfajebhc.supabase.co` from this
session returned a 403 from the proxy), so a real "before" measurement
(actual payload size / row count / load time) needs either a live
browser/network-capable environment or a GitHub Actions dispatch to get
real numbers, neither of which this session can do itself.

**Recommended shape for whoever picks this up** (not a full design, real
judgment still needed by the implementer): move the primary listings
view (table/filters/map) to server-side filtered + paginated Supabase
queries driven by whatever the user is actually viewing (current filter
set, visible map viewport, current page), narrow `select()` to only the
columns each view actually needs (the heavy `description`/`photos`/
`price_history` jsonb columns almost certainly don't belong in a bulk
list-view fetch), add a real cache layer (localStorage/IndexedDB) so an
ordinary refresh doesn't always re-fetch from zero, and treat a genuine
full-dataset load (if anything still needs one) as a rare, background,
cached operation rather than something blocking every page load. Decide
the `findComparables()` radius-search question above as part of the same
pass rather than leaving it broken.

**Status (2026-09-22): slice 1 (narrowed bulk `select()` + a real
IndexedDB cache + lazy per-listing fetch of the three dropped columns)
implemented, self-verified with a real functional test, and re-verified
against a fresh live payload measurement - not yet reviewed by Missy (no
`Agent`/Task tool this session - see dispatch note below), not merged.**
Deliberately slice 1 only, per the explicit two-slice split this entry
itself proposed below: server-side filtered pagination and
`findComparables()`'s radius-search logic are NOT touched here - see the
"Slice 2, explicitly not attempted" note at the end of this entry.

Real numbers used below are from `measure_listings_payload.py`,
re-dispatched fresh today against this fix's own branch (not trusted
from PR #202's earlier same-day run) -
[run 35761063592](https://github.com/kirilbp/bg-property-tracker/actions/runs/35761063592),
completed successfully: `select(*)` (today's code) 1,256 bytes/row,
~257.4 MB / 215 sequential round trips; narrowed `select()` (this fix)
836 bytes/row, ~171.3 MB, same 215 round trips - **33.4% payload
reduction**, matching PR #202's number almost exactly (a useful
independent cross-check). Round-trip count is unchanged by narrowing
alone in either run - that's the caching layer's job, verified
separately (see below and the decisions.md entry for the exact
methodology).

**What shipped in `index.html`:**
1. **Narrowed the bulk `merged_listings` select()** (`fetchAllRows()` /
   `loadData()`) to `MERGED_LISTINGS_BULK_COLUMNS` - every column the
   filters/sort/cards/map/dashboards/comparables-area-average logic
   depends on, EXCEPT `description`/`photos`/`price_history`. Matches
   `measure_listings_payload.py`'s own `NARROW_COLUMNS` exactly (same
   already-measured 33.4% bytes/row reduction applies) and deliberately
   leaves `area_key` out, since it's still not live on the production
   table (backlog item 26) - `listingAreaKey()`'s existing
   `normalizeArea(l.area)` client-side fallback is unaffected and still
   covers this.
2. **Real caching layer**: IndexedDB (not localStorage - even narrowed,
   the full table is ~171MB, well past localStorage's ~5-10MB synchronous
   quota), its own database (`imotenradarListingsCache`), completely
   separate from the `savedListingIds`/`leadGenerators`/`reminders`
   localStorage keys, so nothing about this cache can affect those. TTL
   45 minutes (well under the 6-hour auto-update cadence) - a
   cache-fresh `loadData()` skips `fetchAllRows()` entirely, avoiding
   ~171MB and all ~215 sequential round trips on an ordinary refresh
   within that window. The cached record's own `columns` field doubles
   as a schema-version guard - a cache written under a different column
   list is treated as a miss, not fed into code expecting a different
   shape. Fire-and-forget write, wrapped so a private-browsing/
   quota/disabled-IndexedDB failure never blocks rendering.
3. **Lazy per-listing fetch of the 3 dropped columns**, extending
   `showListingDetail()`'s existing on-demand `listing_sources` fetch
   pattern rather than inventing a new one: a small `merged_listings`
   query by `id` for `description,photos,price_history`, fired
   unconditionally (not just for cross-posted listings) since a
   single-portal listing's synthesized source
   (`synthesizeSingleSource()`) reads these straight off the merged row
   and never gets them from `listing_sources` at all. Cached on the row
   (`_detailFieldsFetched`) so re-opening the same listing doesn't
   re-fetch; refreshes the synthesized source object too (it had
   shallow-copied the merged row before the fetch resolved) so the
   detail page's photo carousel/description/price chart pick up the real
   values on the same re-render pattern the `listing_sources` fetch
   already uses.
4. Every existing filter/search/Lead-Generator/comparables function is
   **unchanged** - same algorithms, same code paths, nothing rewritten.

**Known, deliberately-accepted trade-off, flagged plainly rather than
silently absorbed**: `buildBadgesHtml()`'s "Relisted" badge and the
"Most recently reduced" sort option both read `l.price_history`, and
`listingMatchesSearch()`'s description-substring match reads
`s.description` - straight off the bulk list, for every listing, not
just the one being viewed. Since those three columns are no longer in
the bulk fetch, until a listing's own detail page has been opened at
least once in the current session, these three behaviors see the same
"no history recorded" state they already handle gracefully for a
listing with no history at all (no crash - every one of these functions
already null-checks its input) - no badge, no sort signal, no
description match, rather than the always-current picture `select('*')`
used to give every listing unconditionally. This is a real, understood
consequence of not shipping heavy jsonb to every row on every refresh,
not an oversight - see the decisions.md entry for the alternatives
considered and why this was chosen over them. A precomputed
`last_reduction_at`/`relisted` column (small, server-side, avoiding the
jsonb payload entirely) would close this gap properly, but needs a
schema migration + a live sync run to actually exist on the production
table first - exactly the same landmine already flagged for `area_key`
(item 22) - so it's not attempted here; filed as a follow-up, not
solved.

**Verified, not assumed:**
- A Node `vm` harness loading the real, unmodified `index.html` script
  (same established pattern as the item 22 entry) confirmed: the bulk
  select's column list excludes all 3 heavy columns; a cold load
  fetches once and writes the cache; a second `loadData()` within TTL
  reads the cache and makes **zero** bulk network calls; an expired
  cache correctly triggers a live refetch; opening a listing detail page
  lazily fetches and merges `description`/`photos`/`price_history` and
  refreshes the synthesized single-source object; re-opening the same
  listing does not re-fetch; a multi-portal listing's existing
  `listing_sources` fetch is unaffected; `listingAreaKey()`'s
  `normalizeArea()` fallback still resolves correctly with no
  `area_key` column present.
- Real payload measurement re-run today (see decisions.md for the exact
  numbers/run link) to confirm the fix's premise still holds against
  live data, not just trusted from PR #202's earlier run.
- The caching layer cannot make a saved listing or a Lead Generator
  "disappear": those live entirely in their own, untouched
  `localStorage` keys with no network fetch behind them at all - the
  cache added here only ever affects how fresh `MERGED_LISTINGS` (the
  Supabase-backed listings data) is, bounded by the 45-minute TTL, same
  order of staleness risk any TTL cache carries and well inside the
  existing "auto-updates every 6 hours" promise already shown in the
  page's own subtitle.

**Slice 2, explicitly not attempted here (per this session's own
scoping)**: moving the primary listings view to real server-side
filtered/paginated Supabase queries, and `findComparables()`'s
in-memory radius-search logic. One concrete thought for whoever picks
that up, filed here rather than acted on: `Prefer: count=exact` against
`merged_listings` hits Postgres's `statement_timeout` live (confirmed,
error 57014) - any server-side pagination UI that wants a total result
count for its own use will need a different approach (an approximate
count, a capped/limited count query, or skipping total-count display
entirely), not `count=exact` as currently written in
`measure_listings_payload.py`'s own `get_total_count()` workaround.

Reviewed by Missy (verdict: approve, no blocking issues - verified the
IndexedDB cache is genuinely isolated from saved listings/Lead
Generators, the `synthesizeSingleSource()` race-condition fix is real
and correctly scoped, and the live measurement run) and merged in
[PR #203](https://github.com/kirilbp/bg-property-tracker/pull/203).

**Slice 2 status (2026-09-23, Bossy, PR #228, docs-only, merged):
design/scoping done. No `Agent`/Task tool that session either (confirmed
by checking, not assumed), so per this role's own operating rule for that
case, the non-trivial architecture change below was designed and handed
back as a dispatch list rather than self-implemented and self-approved.
Full design, the real-data investigation behind it, and a previously-
undocumented regression found along the way are in `docs/decisions.md`'s
2026-09-23 "Backlog item 6 slice 2" entry; summary:**

- **A real, previously-undocumented finding**: slice 1 already silently
  broke Lead Generator "new since last check" counts -
  `computeLeadGenCounts()` -> `listingFirstSeenDate()` reads
  `l.price_history[0].date`, one of the three heavy columns slice 1
  deliberately dropped from the bulk fetch. Nothing crashes, but every
  Lead Generator's orange "new" badge silently reads stale/zero until a
  listing's detail page has been opened this session. Not caught by
  slice 1's own writeup, which flagged the "Relisted" badge/"Most
  recently reduced" sort/description search but missed this fourth
  consumer. Needs its own small fix (see dispatch below) - ship this
  first, independent of the bigger piece.
- **Design decision (a real fork, taken directly per this role's standing
  rule)**: scope this pass to the primary listings grid/table only, not
  every `MERGED_LISTINGS` consumer. `findComparables()` (Comparables,
  item 11) and `marketAggregateRows()` (Market Data hub, item 12) both do
  genuine full-array aggregate/radius scans that a single paginated page
  can't answer - moving those server-side needs its own schema/RPC work
  (a `lat`/`lng` index at minimum) that can't be designed blind without
  live Supabase access (confirmed blocked again this session, same as
  every prior one). Filed as two separate, explicit follow-ups rather
  than attempted here.
- **The actual fix for "slow to load"**: decouple the grid's first paint
  from `loadData()`'s full bulk fetch rather than replacing it - fire a
  small server-side query for just the current page (predicates
  translated 1:1 from `render()`'s existing `.filter()` logic) and paint
  immediately, while the existing IndexedDB-cached bulk load keeps
  running in the background for every feature that still needs the full
  array (Comparables, Market Data hub, Lead Gen counts/dropdowns,
  dashboard, area filter) exactly as today.
- **Pagination**: a composite keyset cursor `(sortColumnValue, id)`,
  generalizing `fetchAllRows()`'s own existing `.gt('id', cursor)`
  pattern to arbitrary sort columns - not `OFFSET`/`.range()`, which
  degrades on deep pages regardless of the count problem (a second,
  separate risk this item hadn't flagged yet).
- **Total count**: never `count=exact` on a filtered query (confirmed
  live, error 57014, the already-documented landmine). Show an
  immediate optimistic figure, silently upgraded to an exact number once
  the background bulk load resolves and can compute it client-side the
  same way `render()` does today - never a blocking `count=exact` round
  trip. A one-time unfiltered `{ count: 'estimated' }` HEAD request can
  back a headline "~N listings tracked" stat, but is flagged as
  unverified against this project's actual PostgREST config - test it
  live before depending on it, not assumed.

**Dispatch needed, in this order (none executed this session):**
1. **DONE (2026-09-23)**: add a precomputed `first_seen_at` column
   (schema + `sync_to_supabase.py`, derived from `price_history[0].date`)
   to fix the Lead Generator regression above. Also fixed the Deal
   Pipeline's "Listed" label/CSV export, which read the exact same broken
   function against the same bulk-fetched rows - a fourth consumer
   Bossy's own writeup above didn't separately name. **Requires a live
   Supabase migration Kiril needs to run manually** (`upsert()`'s existing
   PGRST204 missing-column detection-and-strip-and-retry pattern - the
   same one item 22's `area_key` migration already exercises - makes the
   sync degrade gracefully until then, but the column stays empty/absent
   and the badge stays broken until it's actually applied):
   ```sql
   alter table listing_sources add column if not exists first_seen_at timestamptz;
   alter table merged_listings add column if not exists first_seen_at timestamptz;
   ```
2. **DONE (2026-09-23)**: Deal Pipeline's `resolvedPipelineDeals()` no
   longer maps the *entire* `MERGED_LISTINGS` array to look up the
   handful of ids a user actually pipelined - replaced with
   `PIPELINE_LISTINGS_CACHE`, an id-keyed cache backed by a targeted
   `select(...).in('id', dealIds)` query (`refreshPipelineListingsCache()`),
   fetched in parallel with `loadData()`'s bulk fetch and refreshed on
   `PIPELINE_DEALS` membership changes or when the Pipeline page opens.
   Deal Pipeline resolution no longer depends on the full bulk array at
   all.

   Both 1 and 2 shipped together in
   [PR #231](https://github.com/kirilbp/bg-property-tracker/pull/231) -
   merged.
3. **DONE, pending review** - the core piece: server-side filtered/
   paginated query for the primary grid per the design above. Built in an
   isolated worktree off a fresh `origin/main`. `render()` now fires a
   small server-side query for just the current page - predicates
   translated from its own `.filter()` chain (price/sqm/days/reduced/
   excludeSold/search/city/oblast, plus the 6 real type buckets + auction)
   - and paints the grid from it
   immediately, while `loadData()`'s existing IndexedDB-cached bulk fetch
   keeps running unchanged in the background for every other consumer
   (Comparables, Market Data hub, Lead Generator counts/dropdowns, home
   dashboard, area filter population). Composite `(sortColumnValue, id)`
   keyset pagination (never `OFFSET`/`.range()`), Prev/Next via a small
   cursor stack (no arbitrary-page jumping), never `count: 'exact'` or
   `'estimated'` (an honest "at least N" lower bound instead, silently
   upgraded to an exact figure once the background bulk load resolves and
   the existing full-array `render()` path takes over). Every fetched
   fast-path row is re-checked against the exact same `matchesAllFilters()`/
   `sortComparator()` the slow path uses before it's ever painted, which is
   what makes the server-side predicate translation safe to be best-effort
   rather than perfectly exact for a few predicates that have no safe
   server-side form at all (`rooms` - title-regex-derived, no DB column; a
   Lead Generator's radius/polygon geofencing; the "Most recently reduced"
   sort; `area` - see the Missy's-review correction below) - those are
   simply not fast-pathed (the client re-check still
   enforces them exactly), a documented, bounded "shorter preview page,
   never a wrong one" trade-off, not an oversight. Verified with a mocked-
   Supabase-REST Playwright harness (no live Supabase access in this
   sandbox) against a 350-row synthetic fixture with deliberate ties and
   nulls - first paint, pagination (including the exact last-page
   boundary and a rapid-double-click race), 9 filter/sort scenarios, and
   the handoff to the authoritative slow path once the bulk load resolves,
   21 assertions, all passing.
   [PR #239](https://github.com/kirilbp/bg-property-tracker/pull/239) -
   **not merged - needs Missy's re-review** (no auth/PII surface, so Revy's
   review isn't required). See
   `docs/decisions.md`'s matching entry for the full design, the real
   findings surfaced while building it, and what's deliberately still out
   of scope.

   **Correction (Missy's PR #239 review, fixed same-PR):** the original
   version of this piece sent `area` server-side as a bare
   `.eq('area_key', filters.area)`, justified as "forward-compatible" with
   item 26's still-pending `area_key` migration. Missy correctly flagged
   that as a real gap, not just a today-inert one: `area_key` only gets
   backfilled on a live row by the *next* `sync_to_supabase.py` run after
   that migration lands, so there's a real window (up to one full sync
   cycle) where a live row has `area_key IS NULL` while its raw `area`
   text is populated and would match via the client-side
   `listingAreaKey()`'s `l.area_key || normalizeArea(l.area)` fallback. A
   bare `eq()` would silently exclude that row during the window, and -
   unlike every other predicate here - the mandatory client-side re-check
   can't catch it, since it only ever re-filters rows the server already
   returned; a wrongly-excluded row never arrives to be re-checked. That
   directly contradicted this fix's own "can only ever return fewer rows,
   never a wrong page" safety claim. Fixed by simply not fast-pathing
   `area` at all - same treatment as `rooms`/Lead Generator radius/
   `recent-drop-desc` above, relying purely on the client-side re-check.
   Revisit once `area_key` has had a full backfill cycle after its
   migration lands.
4. Documented follow-up, do not dispatch blind: `findComparables()`'s
   server-side radius-search redesign - needs a live Supabase SQL-editor
   migration and a live-data test this sandbox can't perform. File as
   its own item once task 3 ships - **still open**.
5. Documented follow-up: Market Data hub (item 12) server-side
   aggregation - confirmed NOT broken by the design above (keeps reading
   the background-loaded full array, unaffected), just not improved;
   worth a real fix only if that tab's own load time becomes its own
   complaint - **still open, low priority**.

Note `Prefer: count=exact` against `merged_listings` hits Postgres's
`statement_timeout` live (confirmed, error 57014) - any pagination UI
needing a total result count will need a different approach (approximate
count, a capped query, or skipping total-count display), not
`count=exact`. See `docs/decisions.md`'s 2026-09-23 slice 2 entry for the
full composite-keyset-cursor / decoupled-first-paint design already
worked out for task 3.

## 7. Listing detail page: pin the price-history graph, shrink the map, place them side by side - DONE, MERGED (2026-09-23)

User's direct words: *"On each listing the graph with the price changes
needs to be pinned on the listing rather than popping out when the
button is clicked. Make the map smaller as it is taking too much space
and fit the graph next to it."* Confirmed live in the current
`index.html` (post item 13's redesign - this wasn't fixed by that pass):

- The price-history chart (`.price-history-chart-wrap`, 240px tall,
  canvas `#detailPriceChart`, ~line 6600) only renders/shows when the
  "Price History" tab is active - still gated behind `switchDetailTab()`
  (~line 5749) and the tab-button row at ~line 6576-6581 (which now has
  5 tabs: Details/Price History/Comparables/Area Data/BTL Stress Test,
  added by items 13/15). Matches the user's "pops out when clicked"
  complaint exactly.
- The radius-comparables map (`#radiusMap` / `.radius-map`, 260px tall,
  rendered inside `renderRadiusPanel()`, injected at ~line 6575 - just
  above the tab row) sits full-width in its own block, stacked above the
  tabs, not next to the price chart.

**Task (Dessy):**
- Make the price-history chart always visible on the page (no tab click
  required) - pin it into the main flow rather than gating it behind the
  Price History tab. The other 4 tabs (Details, Comparables, Area Data,
  BTL Stress Test) can stay tab-gated; only the graph itself needs to
  come out of the tab system per the user's explicit ask.
- Shrink the map and place it side by side with the (now pinned) price
  chart - a two-column row instead of two separate stacked full-width
  blocks. Keep the map genuinely usable at the smaller size, and check
  the result at both desktop and mobile widths (this is a real page, not
  an artifact, but the same "don't break at phone width" discipline
  applies).
- This touches the same section of the same page as item 13's recent
  redesign and item 9's design-guideline palette work - check
  `docs/design-guidelines.md` and keep the brass/sage/ink tokens item 13
  introduced rather than reintroducing the old blue palette.

**Status: shipped and merged.** PR #220 (`pin-price-chart-shrink-map-
2026-09-23`, commit `e2c4b04`) removed the tab-gated "Price History" tab
entirely (4 tabs remain: Details/Comparables/Area Data/BTL Stress Test)
and moved its content into an always-visible `.price-history-panel`,
paired side by side with the shrunk (260px -> 200px) radius/comparables
map in a new `.detail-history-row`. Missy's review of that PR caught a
real gap - the pairing only triggered above ~1380px, missing the common
1366px laptop width - fixed in a same-day follow-up (`df135d5`, floor
lowered so pairing triggers at ~1330px+). Reuses item 13's brass/sage/ink
tokens, no new colors. Independently re-verified live by Dessy
(2026-09-23, separate session/dispatch) against the real current
`index.html` via a Playwright harness with vendored CDN assets and a
real 6,000-row listings fixture: chart renders with zero tab clicks,
tabs read exactly `Details/Comparables/Area Data/BTL Stress Test`, map +
chart sit side by side at both 1440px and 1366px, both stack to one
column at 390px (mobile), no JS errors. Full detail in
`docs/decisions.md`'s 2026-09-23 entry ("Backlog items 7 and 8...found
already shipped"). No further action needed unless a regression turns
up.

## 8. "Compare nearby" button vs. the new Comparables tab - DONE, MERGED (2026-09-23)

User's direct words: *"The comparables button on each listing does not
do anything too. Fix this."*

**Important - the picture has changed since this feedback was likely
given.** Item 15 ("Comparables & Area Data analytics") shipped a full
Comparables *tab* (`data-tab="comparables"`, `renderComparablesTabHtml()`,
~line 6612-6613) on 2026-09-22, reviewed by Missy and merged. But the
**older** "⇄ Compare nearby" button (`id="compareBtn"`, ~line 6557) is
still also present, still wired to `openCompareModal(merged)` (opens a
separate modal, not the new tab) - so the page currently has two
different comparables entry points side by side. On a static code read
the old button's wiring (click handler, modal markup, CSS `.open` class,
`findComparables()`) still all looks intact, same as it did before
item 15 shipped - which means either:
(a) the user is clicking the old "Compare nearby" button specifically
    and it has a live-only bug (JS exception earlier in
    `renderListingDetail()` killing a later listener, a stacking/z-index
    issue hiding the opened modal, something that only shows up in a
    real browser), or
(b) the user is clicking (or means) the new "Comparables" tab and
    *that's* what's not working, or
(c) both exist and having two different "comparables" surfaces is
    itself confusing enough to read as "does nothing" (clicking the old
    button while expecting the new tab's richer behavior).

**Task (Dessy first, per her own standing instruction to start
frontend-looking bugs herself and flag rather than touch scraper/schema
files):**
- Reproduce live (run the app - see the `run` skill - and click both
  the "Compare nearby" button and the "Comparables" tab) before changing
  anything; don't guess from the static read above.
- If the old button is genuinely broken, either fix it or - likely the
  better product call now that the full Comparables tab exists - retire
  the old modal/button entirely and point that action at the new tab
  instead, so there's one comparables surface, not two. If going that
  route, treat it as a design-fork decision per the standing rule: take
  the recommended option (consolidate on the newer, fuller tab) and log
  the reasoning in `docs/decisions.md`, don't leave both.
- If the new tab itself has a bug, fix it there and leave the
  consolidation question for a follow-up.
- No auth/session/personal-data surface is touched here (read-only
  comparison over already-public listing data) - Revy's review is not
  expected to be needed, but flag her in if anything unexpected turns up.

**Status: shipped and merged.** Reproduced live first, per the task above
(not guessed): the old "Compare nearby" button was not actually broken
(its modal defaulted to a 1000m radius, so it always opened populated);
the real bug was in the newer Comparables tab, which shared
`detailRadiusM` with the pinned radius panel above it (item 7), and
`showListingDetail()` reset that to `null` on every listing open - so the
tab showed only a "pick a radius above" hint and nothing else until the
user found an unrelated-looking control elsewhere on the page, which is
exactly what read as "does nothing." Fixed in PR #221
(`fix-compare-button-2026-09-23`, commit `1b36b64`): (1) `detailRadiusM`
now defaults to 500m so both the radius panel and the Comparables tab
show real data immediately; (2) took the recommended design-fork option -
retired `openCompareModal()`/`closeCompareModal()`/`renderCompareModal()`
and the `#compareModalOverlay` markup entirely; `#compareBtn` stays as a
fast entry point but now switches to and scrolls to the Comparables tab
instead of opening a separate modal, so there's one comparables surface,
not two. Reasoning logged in `docs/decisions.md`'s 2026-09-23 "Retired
the old 'Compare nearby' modal" entry. No auth/PII surface touched, per
the task's own note - Revy's review was not sought. Independently
re-verified live by Dessy (2026-09-23, separate session/dispatch): real
Playwright run against the current `index.html` confirms
`#compareModalOverlay` no longer exists in the DOM at all, `#compareBtn`
switches to and populates the Comparables tab immediately, and the tab
shows real comparables data on first open with no empty "pick a radius"
state whether reached via the button or clicked directly. Full detail in
`docs/decisions.md`'s 2026-09-23 entry ("Backlog items 7 and 8...found
already shipped"). No further action needed unless a regression turns
up.

## 9. Listing descriptions missing or wrong on most listings across most portals - confirmed backend/scraper data bug, not frontend - user feedback 2026-09-23 - MOSTLY DONE (2026-09-23): homes.bg/9a/9b/9c/alo.bg all shipped and merged, imot.bg/olx.bg/bcpea.org investigation complete (no further code needed), imoti.net's `description` gap confirmed a genuine per-portal limitation. Only genuinely open pieces: alo.bg's real selector and imoti.net's untried Bulgarian-language page, both deferred pending live network access; bcpea.org's post-9a grid-crawl recovery worth a final re-check once that run lands.

User's direct words: *"the description is missing. There are just a few
words on most listings."* Independently re-verified directly against the
current committed `data/leads_*.json` files (not just repeating the
original report) - `index.html` already renders `l.description` in full
via `escapeHtml()` with an honest "not available" fallback when empty
(~line 6584-6587, plus a "See more" truncation-at-display only, not a
data problem) - the frontend is not the issue:

- **`data/leads.json` (imoti.net, `scraper.py`)**: 0 of 27,251 listings
  have a `description` key at all - the scraper never scrapes/writes one.
  Confirmed unchanged by the recent "Backfill imoti.net listing details"
  commit (`dbc304a`), which touched price/history data, not description.
- **`data/leads_homes.json` (homes.bg, `scraper_homes.py`)**: 67,705 of
  74,010 (91.5%) have a non-empty `description`, but it's construction-
  material/furnishing tags ("Тухла/Бетон, Полуобзаведен" - "Brick/
  Concrete, Semi-furnished"), not real descriptive text - a wrong-field/
  wrong-selector bug, not a missing-field bug.
- **`data/leads_imot.json`**: 4,510/26,285 (17.2%) non-empty, but
  substantial when present (avg 1,102 chars) - looks like a genuine
  detail-page-fetch coverage gap.
- **`data/leads_olx.json`**: 12,474/36,586 (34.1%) non-empty, avg 1,037
  chars when present - same coverage-gap pattern.
- **`data/leads_bcpea.json`**: 159/2,220 (7.2%) non-empty, but avg 1,488
  chars when present - same coverage-gap pattern, worth checking whether
  it's connected to bcpea's already-known low photo-coverage rate (43.6%,
  clean per Missy's 2026-09-22 audit) or a separate mechanism.
- **`data/leads_alo.json`**: 31,599/90,159 (35.0%) non-empty, but only
  **52 chars average** when present - much shorter than the other
  coverage-gap portals. Worth checking live whether this is a genuinely
  short source description (some portals just don't write much) or
  another wrong-selector bug like homes.bg's, before assuming it's the
  same "coverage gap" shape as imot.bg/olx.bg/bcpea.
- **`data/leads_bazar.json`**: 23,380/50,979 (45.9%) non-empty, avg 159
  chars - same "shorter than expected, check the selector" flag as
  alo.bg above.
- **`data/leads_imoti_bg.json` (imoti.bg)** is healthy: 863/910 (94.8%)
  non-empty, avg 764 chars - proof this is achievable today, and a
  working reference for whoever fixes the other portals.

**Tasks (backend/scraper work, not frontend - route to a general-purpose
builder; consider having Scrapy root-cause the coverage-gap/short-average
mechanics first for tasks 3-4, similar to how she'd audit a dead crawl,
since the picture is more varied than a single "coverage gap" pattern
across 5 portals):**
1. `scraper.py` (imoti.net): add a `description` field, scraped from the
   listing detail page, written the same way the other scrapers do.
2. **`scraper_homes.py`: DONE (2026-09-23).** Fixed the wrong-field/
   selector bug - homes.bg's construction-material/furnishing tag line was
   landing in `offer["description"]` instead of real free text. Shipped in
   [PR #217](https://github.com/kirilbp/bg-property-tracker/pull/217),
   merged to `main` as commit `7ad475a` (merge of `675b451`, "Stop showing
   homes.bg construction-material tags as listing descriptions"). Reviewed
   and approved by Missy - she independently re-verified the root cause,
   tested the fix, and confirmed no regressions before it shipped.
3. `scraper_imot.py`, `scraper_olx.py`, `scraper_bcpea.py`: investigate
   the detail-page-fetch coverage gap (53-93% of listings never got a
   description despite fetched ones being substantial).
4. `scraper_alo.py`, `scraper_bazar.py`: investigate the short-average
   pattern specifically (52/159 chars) - confirm live whether this is a
   real short source description or a wrong-selector bug before treating
   it as the same fix as task 3.
- Each task is independently shippable - don't block one portal's fix on
  another's investigation.
- No auth/session/personal-data surface involved (public listing
  descriptions only) - Revy's review is not expected to be needed.

**Update 2026-09-23: Scrapy-style investigation of tasks 3-4, dispatched
per the note above (a general-purpose agent standing in for Scrapy per her
own file's process, since she isn't directly invocable as a subagent type
from this session - report-only, no code touched). Findings restructure
the remaining scope below; task numbers above are kept for reference but
superseded by the reprioritized task list that follows.**

**9a. `update_history()` grid-crawl overwrite bug - NEW, repo-wide, HIGH
PRIORITY - promoted above tasks 3/4 below.** Bigger in scope than task
3/4's original "coverage gap" framing: `update_history()` in
`scraper_imot.py`, `scraper_olx.py`, `scraper_bcpea.py`, `scraper_alo.py`,
`scraper_bazar.py`, and `scraper.py` (imoti.net) - all six scrapers that
have this function - does `history[lid]["latest"] = l` unconditionally,
where `l` is that run's grid-only crawl data (no `description`/`photos`/
`detail_checked` keys). `scrape.yml` runs every 6 hours and re-touches any
listing still active in the grid, so this silently **wipes already-
backfilled detail-page data (description, photos, detail_checked) for
every still-active listing, every ~6 hours** - only a listing that goes
"removed" between being detail-checked and the next scrape keeps its
backfilled data permanently. Quantified directly from real GitHub Actions
job logs (not inferred) for bcpea/imot/olx: each portal's detail-backfill
queue was observed resetting by hundreds to over a thousand listings
across a single `scrape.yml` boundary, with net queue size sometimes
*growing* rather than shrinking.

Reprioritized above tasks 3/4 (and above the still-open task 1) because
this is live, ongoing, repo-wide data loss affecting 6 scrapers on a
6-hour cadence, not a one-time backlog to clear - every hour this stays
unfixed, more already-completed backfill work (including whatever ships
from tasks 3/4/6 below) gets silently undone again at the next scrape.
Fixing tasks 3/4's coverage gaps without fixing this first means the new
backfill work is itself at risk of being wiped on the next scrape cycle.

- **Task (general-purpose builder):** in each of the six scrapers, change
  `update_history()` so a fresh grid-crawl record only overwrites the
  fields the grid crawl actually provides (price, status, title, url,
  etc.) and preserves any existing `description`/`photos`/
  `detail_checked` (and any other detail-page-only fields) already present
  on `history[lid]["latest"]` when the fresh record doesn't carry them -
  merge, don't replace. Same fix pattern should be identical across all
  six files. Write a real regression test (or a focused unit test against
  sample data) proving a grid-only re-touch no longer clears previously
  backfilled fields, not just a manual read-through. No auth/session/
  personal-data surface - Revy's review not expected to be needed, Missy's
  review is required before merge as always.

**9a shipped:** merged as [PR #219](https://github.com/kirilbp/bg-property-tracker/pull/219)
to `main` (2026-09-23). Reviewed and approved by Missy - no auth/session/
personal-data surface, so Revy's review was correctly not sought. Her
review surfaced two real, verified, non-blocking findings, filed below as
9b (fast follow-up) and 9c (new, separately-scoped item) rather than
reopening 9a.

**9b shipped:** merged as [PR #223](https://github.com/kirilbp/bg-property-tracker/pull/223)
to `main` (2026-09-23). Reviewed and approved by Missy - she independently
confirmed the placeholder-photo grid behavior by reading the actual code
and reproduced the revert-test (bug present -> test fails with the exact
claimed assertion). No auth/session/personal-data surface, Revy's review
correctly not sought.

**9b. `scraper_bcpea.py`: `photo` wrongly excluded from
`_DETAIL_ONLY_FIELDS` - fast follow-up to 9a, one-line fix.** Missy's
review of PR #219 found `_DETAIL_ONLY_FIELDS`'s comment claims the merge
rule can't safely tell "grid's own value" apart from "the richer
detail-page value" for `area` and `photo` without guessing, since the grid
always supplies a real value for both. True for `area`. Factually wrong
for `photo`: the scraper's own grid crawl (`fetch_listings_page()`) can
and does produce `photo: None` whenever the card's image is a shared
placeholder ("very often", per the module's own docstring) - so the exact
same merge rule already applied to this portal's `lat`/`lng` would work
identically for `photo`, no guessing needed. Currently a bcpea listing
that already has a real detail-backfilled photo can still get silently
overwritten with `None` on a later grid re-touch that happens to show a
placeholder image - same bug class 9a fixed, still live for this one
field on this one portal.
- **Task (general-purpose builder):** in `scraper_bcpea.py`, add
  `"photo"` to `_DETAIL_ONLY_FIELDS` and correct the comment to note only
  `area` genuinely needs the deferral (not both). Add/update a regression
  test proving a grid re-touch with a placeholder photo no longer
  overwrites an existing real detail-backfilled photo.
- No auth/session/personal-data surface - Revy's review not expected to
  be needed. Missy's review required before merge.

**9c shipped:** merged as [PR #222](https://github.com/kirilbp/bg-property-tracker/pull/222)
to `main` (2026-09-23). Reviewed and approved by Missy - her first review
correctly caught unrelated bcpea test contamination accidentally picked
up onto this branch (a concurrent task's in-progress edits, snapshotted
mid-edit by the branch-creation method used); stripped and re-reviewed
clean before merge. No auth/session/personal-data surface, Revy's review
correctly not sought.

**9c. `scraper_imoti_bg.py`: same unconditional-replace `update_history()`
bug as 9a, missed by PR #219's scope - NEW, same priority class as 9a.**
Missy's review of PR #219 found the fix's own scope framing ("all six
scrapers that have this function") was wrong - two more scrapers also
define `update_history()`, and neither was touched:
  - `scraper_homes.py` - investigated, genuinely NOT at risk, no action
    needed: photos come straight off the grid-crawl JSON on every run (no
    separate detail-page photo enrichment to lose), and lat/lng self-heal
    via the persistent shared geocode cache. Correctly excluded.
  - `scraper_imoti_bg.py` - genuinely exposed to the same live bug,
    unfixed. `fetch_listings()` calls `fetch_listing_detail(url)` inline
    on every scrape run for every listing (a best-effort function whose
    own docstring says it "never raises... a missing description/date
    shouldn't drop a listing"), then does `l["description"] = description`
    / `l["site_posted_at"] = site_posted_at` unconditionally (not
    `if description:`), followed by this scraper's own still-unpatched
    `update_history()` doing the same wholesale
    `history[lid]["latest"] = l`. A single transient per-run failure
    (timeout, missing meta tag, render hiccup) on a listing that
    previously had a real description will silently overwrite it with
    `None` - the exact same bug class as 9a, still live.
- **Task (general-purpose builder):** in `scraper_imoti_bg.py`, give
  `update_history()` the identical merge-not-replace treatment 9a shipped
  for the other six scrapers, scoped to `description` and
  `site_posted_at` (the two fields `fetch_listing_detail()` can produce
  `None` for on a transient per-listing failure even though a prior run
  had a real value). Same regression-test requirement as 9a: prove a
  grid-only re-touch (or a simulated detail-fetch failure) no longer
  clears a previously-captured `description`/`site_posted_at`.
- No auth/session/personal-data surface - Revy's review not expected to
  be needed. Missy's review required before merge.

**Tasks 3/4, reframed per-portal with the investigation's findings (all
independently verified, not guessed):**
- **imot.bg, olx.bg (was task 3's "coverage gap" for these two) - task 3
  investigation now complete, sequencing precondition (9a) has shipped, no
  further scraper code needed.** Genuine coverage gap confirmed - real,
  succeeding backfill workflows (verified via actual log content, not just
  a green checkmark). No recurrence of the 2026-09-19
  detail_checked-on-failure bug (item 1) - all three scrapers checked for
  task 3 correctly only set `detail_checked` after a real successful
  fetch. **Re-derived directly against the real committed data on
  2026-09-23, after 9a/9b/9c all shipped** (not just re-quoting the
  original audit's numbers, per this repo's standing rule): `imot.bg` is
  now 5,009/26,285 (19.1%) non-empty description, up from the original
  audit's 17.2% - `olx.bg` is now 12,972/36,586 (35.5%), up from 34.1%.
  Both small but real upward moves, consistent with 9a's merge-not-replace
  fix letting backfill progress accumulate instead of resetting. `_DETAIL_
  ONLY_FIELDS` in both `scraper_imot.py`/`scraper_olx.py` already includes
  `description` (confirmed by reading the current code, not assumed).
- **bcpea.org (was task 3's "coverage gap" for this portal) - same
  status, with the clearest evidence of the three that 9a is actually
  working.** Walked `data/leads_bcpea.json`'s non-empty-description count
  through the real git history around 9a's merge time (2026-09-23
  06:53 UTC): 921 (pre-merge) -> **159** in the very next grid-crawl
  commit (`185ecc4`, 04:47 UTC - this one landed *before* 9a merged, and
  is the same reset-to-near-zero pattern task 3's original investigation
  already documented) -> **528** in the first backfill run after 9a
  merged (`8f82b45`, 07:04 UTC) - a real partial recovery in a single run,
  not another reset. Current real total: 528/2,220 (23.8%), well up from
  the original audit's 7.2% (159/2,220). **Caveat, stated plainly rather
  than assumed away: no `scrape.yml` grid-crawl has landed yet since 9a
  merged** (the next scheduled run was still pending as of this
  investigation) - so the specific claim "a fresh grid re-touch no longer
  wipes this portal's backfilled descriptions" is supported by 9a's code
  being present and reviewed (`_DETAIL_ONLY_FIELDS` includes
  `"description"`), not yet by an observed real post-fix grid-crawl commit
  for this portal. Worth re-checking `data/leads_bcpea.json`'s count after
  the next `scrape.yml` run lands, to close this out with full confidence.
  **Separately, its hit-rate-when-checked has also moved**: was cited as
  18% (vs 75-91% for imot/olx); recomputed now at 528/1,283 detail-checked
  = 41.2% - still well below imot.bg's 75.4%/olx.bg's 91.3%, consistent
  with (not proof of) the standing theory that sales.bcpea.org (a
  court-enforcement auction registry) genuinely often has no free-text
  "Описание" field to begin with. Still can't be confirmed live -
  `sales.bcpea.org` is still blocked from this sandbox (re-confirmed via
  curl on 2026-09-23) - so this remains a plausible read, not a confirmed
  fact. No further task filed for either question; worth a live check
  whenever someone has bcpea.org network access, not blocking.
- **alo.bg (was task 4's "short-average" portal) - DONE, partial fix
  shipped (2026-09-23), same shape as the already-fixed homes.bg bug (task
  2 above).** Confirmed with strong evidence (not just the 52-char
  average): sampled 200 real non-empty descriptions, 165/200 (82.5%) are
  literal substrings of that same listing's own title, not real prose -
  e.g. title "...Двустаен апартамент в к-с Суит хоум 2 Слънчев бряг,
  област Бургас" -> description "Двустаен апартамент в к-с Суит хоум 2".
  `extract_description_alo()` in `geo_utils.py` reads `.obqva-block`,
  very likely the wrong element (probably a heading/summary blurb, not the
  real ad body). Re-confirmed independently with a fresh 300-record sample
  (265/300 = 88.3%, same shape at a higher rate) while shipping the fix.
  alo.bg is unreachable from this sandbox - confirmed via both a plain
  `curl` and the `WebFetch` tool against a real listing URL (both return a
  hard block), so the real selector could not be found live. Shipped the
  same honest partial fix the homes.bg task took instead of guessing:
  `extract_description_alo()` now unconditionally returns `None` rather
  than the likely-wrong `.obqva-block` text - stops new writes going
  forward, does not retroactively scrub already-stored bad descriptions in
  `data/leads_alo.json`/`data/history_alo.json`. **The other half - find
  and use the real selector - is still genuinely open**, deferred pending
  live alo.bg access from whoever has it next. Reviewed and approved by
  Missy (independently re-sampled 300 records herself, seed 42, no reuse
  of the builder's sample, got the same 88.3%; confirmed no caller breaks
  on `None`; confirmed alo.bg is genuinely unreachable, not assumed).
  Merged as [PR #218](https://github.com/kirilbp/bg-property-tracker/pull/218)
  to `main`. No auth/session/personal-data surface, Revy's review
  correctly not sought.
- **bazar.bg (was task 4's other "short-average" portal) - investigated,
  likely NOT a bug, resolved (not an open coverage-gap task anymore).**
  82% of non-empty descriptions are exactly 160 characters (classic SEO
  meta-description truncation length), extracted via the same ld+json
  mechanism that gives olx.bg its healthy 1,037-char average. One open
  caveat, stated plainly rather than assumed away: can't rule out without
  live bazar.bg access (also blocked from this sandbox) that a longer
  description exists elsewhere on the page under a different selector -
  so this is "probably fine, low priority to double check" rather than
  fully closed. No task filed; revisit only if someone with live
  bazar.bg access has spare time, not prioritized.

**Task 1 (`scraper.py`/imoti.net: add a `description` field) - investigated
(2026-09-23), genuine per-portal limitation confirmed, no code fix
possible from here - not closing the door on it, but nothing to guess at
either.** Before writing any code, checked whether this had already been
looked at: `backfill_detail_imoti_net.py`'s own module docstring already
carries a live-confirmed finding that **predates this backlog item** -
"confirmed live via probe_descriptions.py that imoti.net's own detail
page carries no free-text description anywhere - neither in its meta
tags nor its ld+json block nor any labeled HTML block, only structured
price/sqm/floor/broker-contact info." That detail page is the *only* one
`scraper.py` ever fetches (the site's `/en/` English-language path - see
that module's own docstring on why, from the item 5 investigation). Tried
to independently re-verify this claim live rather than just trust it (per
this repo's standing rule) - both a plain `curl` and the `WebFetch` tool
against `www.imoti.net` return a hard egress block from this sandbox, the
same block already documented elsewhere in this file for imoti.net. So
this can't be freshly confirmed or overturned from here; taken as the
best available evidence rather than re-guessed. Given a genuine absence
of the field on the only page fetched, "written the same way the other
scrapers do it" isn't achievable without a different data source -
selected a selector to scrape would be guessing at data that isn't there,
the same anti-pattern this backlog explicitly avoids elsewhere (alo.bg
above, homes.bg's PR #217). Only change made: corrected a stale comment
in `scraper.py`'s `_DETAIL_ONLY_FIELDS` block that said description would
be "added here too once that ships" - it now records the investigated
conclusion instead, so a future reader doesn't re-open this expecting a
different outcome without new information. **Genuinely open follow-up,
not attempted here**: imoti.net likely has a Bulgarian-language version of
each listing page (this scraper only ever visits the English one) that
was never probed for a free-text description - worth a live check by
whoever next has imoti.net network access, same "deferred pending live
access" framing as the alo.bg selector search above. No auth/session/
personal-data surface either way - Revy's review not expected to be
needed for this task.

## 10. Overall design/luxuriousness still not landing site-wide - user feedback 2026-09-23, elevates item 21's priority - DONE (2026-09-23)

User's direct words: *"The overall design and appearance of the website
does not come as luxurious and stylish."* This lands **after** item 13's
listing-detail redesign already shipped real design-guideline work
(Playfair Display + Inter, warm ivory/brass/ink palette - see item 13's
"Design-scope note") - so this isn't a request to start from zero, it's
confirmation that item 13's own documented scope limit is now a real gap
the user is feeling: that redesign was **deliberately scoped to
`#section-listing` only** ("the rest of the site - sidebar nav, listing
cards, modals - intentionally keeps its current look... a full site-wide
reskin against the same palette is item 21's scope, not redone piecemeal
here"). Item 21 ("Visual/premium design refresh") already exists for
exactly this - this entry elevates its priority rather than duplicating
it: move it up to be worked next after items 7-9 above, instead of
sitting at its current position after the full items 13-20 feature
build-out.

**Task (Dessy):** pick up item 21 now rather than later - a site-wide
pass reusing the CSS variables/palette item 13 already defined globally
(per item 13's note: "defined as global CSS variables for later reuse"),
applied to the listing grid/cards, sidebar nav, search/filter panel, and
modals (save/reminder/lead-generator/compare) that item 13 explicitly
left untouched. Also fold in the "one primary action per view" restraint
principle from `docs/design-guidelines.md` where the detail page (and
elsewhere) currently shows several equal-weight buttons (Save, Compare
nearby, Remind me, pipeline actions all styled the same). If this
surfaces a need for non-frontend changes, stop and flag per Dessy's
standing instruction rather than touching backend/scraper files herself.

**Status: done, in two passes.** The bulk of the site-wide pass (sidebar,
listing grid/cards, search/filter panel, home/help pages, pagination, and
the shared modal CSS used by Lead Generator/Reminder/Pipeline-config
modals) shipped directly to `main` on 2026-09-23 ("Site-wide design pass:
extend brass/ivory/ink palette beyond listing detail" + a same-day follow-
up fix, both already merged via PR #224 before this entry was written up -
verified live in the actual `index.html` on `main`, not just from the
commit message). See item 21 below for the full inventory of what that
pass covered. This entry's own remaining work was a **verification +
consistency pass** on top of that already-merged work (real Playwright
screenshots at 1440px and 390px across every page - Home, Leads grid,
listing detail + Reminder modal, Lead Generators + its modal, Pipeline +
its config modal, Comparables, Dashboard, Market Data, Help - zero page
errors), which found and fixed 4 small leftover inconsistencies the
original pass missed:
- The listing detail page's own radius/comparables Leaflet map was the
  one place still drawing comparable-listing markers in saturated red
  (`#dc2626`) instead of the brass used for the exact same "comparable
  listing" concept everywhere else in the app (Comparables tab, Lead
  Generator radius map, Market Data heat map) - a real, if small,
  violation of section 4/9's "reserve red strictly for functional errors."
  Recolored to match.
- Two `.danger`-hover icon-button states (Lead Generator card delete
  icon, Pipeline card remove icon) used an ad-hoc one-off hex pair
  (`#b08d3f`/`#7a3b2e`) instead of the `--error` CSS variable already
  defined for exactly this "muted danger, not stock red" purpose -
  switched both to `var(--error)`.
- Every native checkbox site-wide (property-type filters, neighborhood
  pickers, "Exclude sold," tag pickers) rendered with the browser's
  default blue tick - an uncontrolled second accent hue on every page
  with a checkbox. Fixed with one global rule,
  `input[type="checkbox"] { accent-color: var(--brass); }` - no
  per-checkbox markup changes needed.
- Every Leaflet map's "subject point" marker (detail page radius map,
  detail page Comparables-tab map, Lead Generator radius-picker map) used
  Leaflet's own default blue pin icon, another uncontrolled second accent
  hue. Replaced with a small CSS-only brass teardrop (`brassPinIcon()` /
  `.brass-pin`, no new image asset) reused across all three call sites.

**Explicitly still open, flagged rather than attempted here** (both
already named as deliberate scope cuts by the original pass, confirmed
still real by this pass's own mobile screenshots): the search/filter
panel still shows all 9 filters at once instead of a progressive-
disclosure "3-4 primary + More filters" pattern, and - the more visible
one - **the sidebar does not collapse at mobile widths**: real 390px-wide
screenshots of every page (Home, Market Data, Help, Pipeline, etc.) show
the fixed 220px dark sidebar eating well over half the viewport, squeezing
body text into an unreadably narrow column and wrapping data tables one
cell per line. This is a real, visible defect on mobile, not a nitpick -
but fixing it means a real interaction pattern (hamburger/off-canvas nav
with open/close state), a meaningfully different kind of change than a
palette/hierarchy pass, so it's deliberately left as its own follow-up
rather than bolted on here. Recommend it as the next design-related
backlog item given how much it undercuts the "luxurious" read on mobile
specifically.

**Follow-up: sidebar mobile collapse - DONE (2026-09-23, Dessy), AWAITING
MISSY'S REVIEW.** Built a real off-canvas nav pattern in `index.html`: a
small hamburger toggle (`#sidebarToggle`, brass/ink palette, no new blue,
no icon library - three plain CSS bars, consistent with the rest of the
site not using a stock icon set) appears only at `max-width: 768px`
(close to, though not the exact midpoint of, this file's two existing
two-column-to-single-column stacking breakpoints - 700px for `.btl-grid`
and 800px for `.detail-grid`, whose true midpoint is 750px - there was no
single pre-existing "mobile nav" breakpoint to match exactly, so 768px was
picked as the de facto industry-standard mobile/tablet split instead).
Below that
width the sidebar (`#appSidebar`) becomes `position: fixed`, off-screen
via `transform: translateX(-100%)`, and slides in as a 220px overlay
above a dimmed backdrop (`#sidebarBackdrop`) when toggled; the main
content takes the full viewport width when it's closed. All 7 existing
nav items and active-section highlighting are untouched - purely a
presentation/layout change, no content or JS routing logic changed beyond
opening/closing the panel (clicking a nav item still calls the existing
`showSection()` and also now closes the panel; backdrop click and Escape
close it too). Above 768px the new CSS rules don't apply at all, so
desktop is pixel-identical to before. Verified with a real Playwright
harness (local vendored Chart.js/Leaflet/Supabase-js, realistic
`merged_listings` fixture, zero new console errors at both 390px and
1440px - the one console error present is a pre-existing Google Fonts
network failure reproduced identically on unmodified `main`, unrelated to
this change). See `docs/decisions.md`'s matching 2026-09-23 entry for
full screenshot-by-screenshot detail.

## 11. Supabase Pro plan follow-ups - AUDIT DONE (2026-09-23), one code
comment updated, nothing else changed, one dashboard setting flagged

Free-tier limits are gone, daily backups are running. Revisit anything
designed around the old 500 MB limit (retry/backoff tuned for storage-
related 500s, any code that assumed a small dataset for cost reasons).

**Status (2026-09-23): full audit done** across `sync_to_supabase.py`,
every `scraper*.py`/`backfill_*.py`, `index.html`, and
`measure_listings_payload.py`/`audit_cross_city_merges.py`. Searched for
every explicit free-tier/cost/500MB/connection-pool/statement-timeout
reference (`grep -i "free.?tier|500 ?MB|connection.?pool|backoff|retry|
statement_timeout|57014"` across the whole repo, not just a guess at
likely files) and read each hit's surrounding code to judge whether it
was cost-motivated or serving a second, still-valid purpose. Full
per-finding reasoning in `docs/decisions.md`'s 2026-09-23 "Backlog item
11" entry. Summary:

- **Only one place in the whole codebase explicitly cites the free tier
  as its reason for existing**: `index.html`'s `loadData()` comment,
  explaining why `listing_sources` isn't bulk-loaded (only
  `merged_listings` is) - originally written to say the sustained
  request volume "exhaust[ed] something on the free-tier project (a
  connection pool, most likely)". **Not reverted** - backlog item 6
  already independently re-examined this exact design after the Pro
  upgrade and concluded the underlying problem (shipping every raw
  per-portal row's heavy jsonb columns to every browser on every visit)
  is a client-payload/UX problem, not just backend capacity, so it holds
  regardless of plan tier. The comment itself was stale/misleading
  though (still framed as purely a free-tier workaround) - **updated**
  to state plainly that this was re-audited post-Pro-upgrade and
  deliberately kept, with a pointer to item 6's fuller reasoning. Comment
  only, no logic changed.
- **`sync_to_supabase.py`'s `request_with_retries()`** (`BATCH_SIZE=500`,
  `MAX_HTTP_RETRIES=4`, `RETRY_BACKOFF_SECONDS=5`) - **not free-tier
  motivated at all**, and left unchanged. Its own comment explains it
  exists because a real production sync once crashed outright on a
  single transient Postgres 57014 (statement timeout) with zero retry
  logic anywhere - this protects against genuine transient errors on any
  tier, not a cost workaround. `BATCH_SIZE=500` has no free-tier-related
  comment anywhere and isn't a payload-size cost throttle; it's sized to
  keep individual upsert batches comfortably clear of the same
  statement-timeout wall documented elsewhere in this file (a bigger
  batch is a *higher*-risk change on this specific axis, not a safe
  relaxation) - left as-is.
- **`scraper.py`/`scraper_alo.py`/every other scraper's own
  `fetch_with_retries()`-style retry/backoff** - these retry HTTP
  fetches against the *external portals* (imoti.net, alo.bg, etc.), not
  Supabase. Unrelated to Supabase's plan tier; out of scope for this
  item, left unchanged.
- **Keyset pagination** (`fetchAllRows()` in `index.html`,
  `delete_stale_merged_listings()` in `sync_to_supabase.py`,
  `audit_cross_city_merges.py`) replacing `OFFSET`-based paging - this
  was a fix for a genuine Postgres query-plan cost problem (`OFFSET`'s
  scan-and-discard cost growing with page depth, eventually exceeding
  the statement timeout), not a free-tier-specific limit. Would still be
  necessary on Pro (the underlying cost-scaling is inherent to `OFFSET`,
  not a tier setting) - left unchanged.
- **No deliberate row-count/payload-size throttling or "keep it small
  because free tier" comments found anywhere** - `prune_snapshots()`
  (`geo_utils.py`) shrinks redundant same-price history snapshots, but
  that's genuine deduplication (never drops a real price change or the
  most recent snapshot), not a cost-driven cap, and is worth keeping on
  any tier.
- **"Free tier" mentions in `docs/strategy/marketing-strategy.md` and
  `subscription-strategy.md` are a false-positive match** - those
  describe imotenradar.com's own future *product* subscription tiers
  (a business-model doc), unrelated to Supabase's infrastructure tier.
  Not touched.

**Live Supabase dashboard setting flagged, not applied (this sandbox has
no live Supabase access)**: several places in this codebase
(`measure_listings_payload.py`'s `count=exact` fallback,
`audit_cross_city_merges.py`'s deep-OFFSET failures,
`sync_to_supabase.py`'s `delete_stale_merged_listings()` comment) document
hitting Postgres error 57014 (`statement_timeout`) on expensive queries
against `merged_listings`. All of these are already worked around
gracefully in code (keyset pagination, a documented fallback row count),
so nothing is broken today - but the Postgres **`statement_timeout` for
the API roles (`anon`/`authenticated`) is itself a project-level Supabase
setting that is only configurable on paid plans** (Free tier can't raise
it at all). Now that the project is on Pro, Kiril could raise it via the
Supabase dashboard (Project Settings -> Database -> Configuration/Roles,
or `alter role authenticator set statement_timeout = '...'` in the SQL
editor) if a future feature needs a genuinely expensive query (e.g. a
real `count=exact` for pagination totals, per item 6 slice 2's own open
question). **Not required** - purely optional headroom, since every
current caller already degrades gracefully without it - flagging it here
so it isn't lost, not because anything is currently broken.

## 12. Motivation score rework - DONE

Shipped in PR #162: 5-component formula (relisted, distinct reductions,
size of drop, days on market, below area average), rescale option A when
area-average is unavailable, Hot/Warm thresholds recalibrated to 40/15
against real data distribution. Confirmed live.

## 13. Listing detail page redesign: multi-portal badge, price/status history, keyword tags - Nosy spec, highest investor value - CORE SCOPE DONE, MERGED (2026-09-22, Dessy)

Reviewed by Missy (verdict: no blocking findings, all claims independently
verified against real committed data) and merged in
[PR #200](https://github.com/kirilbp/bg-property-tracker/pull/200).

Supersedes the old "Stats panel redesign - BLOCKED" item now that
`docs/property-filter-spec.md` exists. Prioritized first among the
Nosy-derived work because Nosy's own spec calls this "arguably the single
highest-value feature to prioritize" and "one of the better features" -
both build entirely on data imotenradar already scrapes, turning existing
background work into a visible, differentiating feature rather than new
data acquisition. All items below are marked **fully Bulgarian-replicable**
in the spec (section 5, "Advert Details" tab) unless noted.

- **Multi-portal badge row - DONE.** The existing source-switcher
  (`merged.sources`, from `listing_sources`/`sync_to_supabase.py`'s
  `group_listings()` cross-portal dedup) rebuilt as a proper badge row:
  portal name, price, and a "Listed [site_posted_at]" line when the portal
  exposes a posting date, falling back to "Tracked since [first
  price_history date]" when it doesn't (worded to not overclaim - most
  committed listings lack `site_posted_at`) - plus "Removed [date]" for a
  no-longer-live source. Currently-viewed source highlighted with the
  brass accent; clicking a badge switches sources exactly like the old
  switcher did.
- **Price & Status History step-chart - DONE.** Existing Chart.js step
  chart kept, recolored to the restrained brass/sage/ink palette (was
  blue/red/purple), plus a new background-shaded band (custom Chart.js
  `beforeDraw` plugin, no extra CDN dependency) over the period the
  *currently-viewed source* was off-market (`removed_at` to today) - a
  deliberately understated single ink tint, not a green/yellow/pink
  traffic light (that's Property Filter's own named anti-pattern per
  `docs/design-guidelines.md`). Caveat for follow-up: `removed_at` is only
  synced to `listing_sources`, not `merged_listings` (see
  `sync_to_supabase.py`'s `MERGED_FIELDS`), so the band only renders once
  a listing's real per-source rows have loaded (member_count > 1 case) -
  a single-portal "sold" listing has no per-source removal date to shade
  with under the current schema.
- **Property Details & Keywords panel - DONE.** New `extractKeywordTags()`
  does substring/pattern matching across every cross-posted source's
  description + title (BG keyword table for Sale features / Property
  features / Close by, plus a Property Type pill from the existing
  `typeFilterBucket()`) - pure client-side JS, no new data. Tenure
  (UK leasehold concept) deliberately excluded per the "Confirmed drops"
  list below. Two false-positive keyword collisions found and fixed
  during testing (`търг` "auction" was matching inside `търговия` "trade";
  `парк` "park" was matching inside `паркинг` "parking") - both now use a
  Unicode-aware whole-word boundary check instead of a bare substring.
- **Supporting pieces - DONE except Agent panel (see below):**
  - Prev/Next paging through the current filtered+sorted result set -
    DONE (new `CURRENT_RESULT_IDS`, refreshed on every `render()`).
  - Description panel with "See more" - DONE (truncates past ~420 chars
    at a word boundary).
  - Small embedded map - already existed (the radius-comparables panel's
    Leaflet map), left as-is.
  - Photo carousel - already existed (hero + thumbnail strip, prev/next,
    keyboard arrows), left as-is.
  - **Agent panel - NOT built, blocked on missing data.** Checked the
    full field union across all 8 `data/leads_*.json` files: there is no
    agent/agency name, phone, or contact field scraped anywhere. This
    needs new scraper work (a detail-page field none of the 8 scrapers
    currently extract) before an Agent panel can show anything real -
    flagging per this repo's standing rule rather than building a
    fake/empty panel. Floorplan: skipped too, per the spec's own note
    that it's rare in scraped BG data and no scraper stores one - both
    correctly out of a frontend-only builder's scope.
  - "Copy Data for AI", "Create Share Link", "Report a bug for this
    advert" - not built; these weren't in the explicit dispatch for this
    pass (see PR description) and remain open, low-effort follow-ups.
- Nearby amenities list (distance to town centre/station/supermarket/
  hospital/school): still open - needs a mapping/POI API integration,
  not attempted here.

**Design-scope note:** implemented as a scoped redesign of the listing
detail view only (`#section-listing` and its own elements) - typography
(Playfair Display + Inter), warm ivory/brass/ink palette, and generous
spacing per `docs/design-guidelines.md` are applied there, plus defined
as global CSS variables for later reuse, but the rest of the site
(sidebar nav, listing cards, modals) intentionally keeps its current
look. A full site-wide reskin against the same palette is item 21's
scope, not redone piecemeal here.

**Not included here (see "Confirmed drops" below):** CT Band, Owner
(Land Registry), Registered Lease/Restrictive covenant/Title number,
"Last building use known", HMO Article 4 flag, EPC badge (until/unless a
Bulgarian energy-certificate data source is confirmed - see "Open
questions").

## 14. Saved searches ("Lead Generators") + home dashboard + Deal Pipeline (kanban) - DONE, MERGED (2026-09-22, Dessy)

Reviewed by Missy (verdict: approve - independently verified every data-gap
claim against the real committed data, confirmed the localStorage schema
has no key collisions, and caught one real minor bug: `pipelineStatusLabel()`'s
"Removed" branch checked a field, `source_status`, that merged-listing rows
never carry - the branch could never fire. Fixed before merge.) and merged
in [PR #207](https://github.com/kirilbp/bg-property-tracker/pull/207).

The core recurring-workflow loop: a paying investor's day-to-day use of
the tool. Fully Bulgarian-replicable per spec sections 1-3 - workflow
patterns, not data-dependent.

- **Lead Generators list**: saved-search cards with a map thumbnail of
  the search's geographic boundary, green "total matches" / orange "new
  since last check" badge pair, filter summary, duplicate/edit/share/
  delete actions, sort + For Sale/To Rent tabs. The "duplicate a saved
  search to tweak it" action is called out in the spec as small but
  load-bearing - keep it.
- **Home dashboard**: "Start Here" onboarding checklist, Lead Generators
  inbox card, Pipeline Actions summary card (per-stage live counts).
- **Deal Pipeline (kanban)**: stage tabs with live counts; cards showing
  status/price-change ribbons, listing date, photo, price, price/m²,
  address, beds, floor area, floor level, distance. Card/Table/Map/
  Export view toggle. Filter by tag/generator/agent.
- **Important build detail from spec section 9**: pipeline stages
  (names + icons) and the tag system (name/icon/color) must be
  user-configurable, arbitrary length - do not hardcode a fixed stage
  count.
- Excludes the EPC icon and "yield-like %" stat on pipeline cards until
  their respective data/formula questions below are resolved.

**Status (2026-09-22): implemented in `index.html` (frontend/JS only, no
scraper/schema changes), self-verified end to end in a real headless
Chromium via Playwright against realistic fake data (this sandbox's egress
proxy blocks live Supabase/CDN access, same documented limitation prior
sessions hit - `sb`/`Chart`/CDN calls were stubbed, the app's own JS was not
modified for testing), not yet reviewed by Missy. Built on a separate branch
(`dessy/pipeline-lead-gen-dashboard`, off a fresh `origin/main` worktree) to
avoid colliding with Placy's concurrent `geo_utils.py`/data-file work in the
shared checkout - PR to follow. Summary:

- **Lead Generators list**: existing map-thumbnail/edit/duplicate/delete
  infrastructure kept as-is; added the green "N matches"/orange "N new"
  badge pair (`computeLeadGenCounts()` - "new" = matches first seen, via
  `price_history[0].date`, since a new `gen.lastCheckedAt` timestamp set
  every time "Check Leads" is clicked), a working **Share** action
  (`shareLeadGenerator()`/`maybeImportSharedLeadGenerator()` - encodes the
  search into a `#/import-leadgen/<data>` URL, no backend involved, same
  no-login localStorage architecture as everything else here; a duplicate
  correctly starts unchecked with a fresh "N new" count rather than
  inheriting the original's), a sort dropdown (most matches / most new /
  recently created / name), and All/For Sale/To Rent/For Sale & To Rent
  tabs. **Real data gap, flagged rather than faked**: no scraped listing
  anywhere carries a rent-vs-sale field - rental scraping is separately
  Parked (under 400 usable listings nationwide) - so the sale-type tabs
  filter the *generators* by a new `gen.saleType` tag (defaults to `sale`)
  rather than pretending to filter real listing data that doesn't exist;
  picking "To Rent" honestly shows an empty state explaining why, right in
  the UI, instead of silently showing zero results with no explanation.
- **Home dashboard**: added to the existing `section-dashboard` page (kept
  the existing Reminders/Saved/Hottest-deals cards below it rather than
  reorganizing nav - see design-scope note below) - a "Start Here"
  checklist whose 5 items reflect real app state (has a Lead Generator, has
  a pipeline deal, has a saved listing/reminder, has checked a Lead
  Generator, has customized stages/tags) rather than a separately-tracked
  flag, a Lead Generators inbox card (top 5 by current sort, click-through
  to `checkLeads()`), and a Pipeline Actions card (one live-counted row per
  configured stage, click-through to that stage in the Pipeline board).
- **Deal Pipeline (kanban)**: new "Pipeline" nav item/section. Stages
  (`PIPELINE_STAGES`, default 5, seeded from the spec's own arrow-flow
  names) and tags (`PIPELINE_TAGS`, name/icon/color, empty by default) are
  both fully arbitrary-length and user-editable via a "Manage stages &
  tags" modal (add/rename/re-icon/recolor/delete) - every stage/tag loop in
  the code iterates the array rather than assuming a fixed count, per the
  spec's own explicit warning. Deals (`PIPELINE_DEALS`, keyed by listing
  id) persist stage + tags + which Lead Generator surfaced the listing, all
  in localStorage, same no-login pattern as Lead Generators/saved
  listings/reminders. Stage tabs show live counts; toolbar has search + tag
  filter + Lead Generator filter + Card/Table/Map/Export view toggle
  (Export is a real client-side CSV download). Cards show status ("Active
  · Nd"/"Removed"/"Sold"), a price-change label ("Reduced N% · N drops")
  when relevant, listing date, photo, price, price/m², address, rooms,
  floor area (m²), and distance-from-search-point when the deal came from
  a radius-mode Lead Generator (the only case with an unambiguous "distance
  from what" answer in a login-free app - omitted otherwise rather than
  measured from an arbitrary point). Entry points: a "+ Add to Pipeline"
  control (becomes a stage `<select>` + "Remove from Pipeline" once added)
  on the listing detail page, and a quick ＋/✓ toggle button on every
  listing card everywhere cards render (results grid, Saved listings,
  Hottest deals).
  - **Two spec fields flagged, not built - real data gaps, not
    oversights**: "floor level" isn't scraped by any of the 8 portals
    (checked the full field union across `data/leads_*.json`) - omitted
    from cards rather than faked. "Filter by Agent" isn't buildable either
    - same already-flagged gap as item 13's Agent panel (no scraped listing
    carries an agent/agency name or contact field) - the toolbar says so
    explicitly instead of showing a control that can't do anything.
  - **Design-guidelines judgment call**: the spec's own card description
    calls for colored status/price-change *ribbons* and a dense 2x3
    icon-grid of stats - both are `docs/design-guidelines.md` section 9's
    explicitly named anti-patterns (items 1-2). Built the same *content*
    the spec asks for, presented as small-caps muted text labels and plain
    inline facts instead, matching the restrained treatment item 13 already
    established for the listing detail page - not a silent improvisation,
    the guidelines document directly instructs this substitution.
- **Design-scope note**: the new/redesigned surfaces (Lead Generators
  gallery, the three new dashboard widgets, the whole Pipeline board) draw
  on `docs/design-guidelines.md`'s warm ivory/brass palette and Playfair/
  Inter type pairing - the same CSS variables item 13 introduced. Shared
  chrome those surfaces still reuse (the generic `.modal-*` classes, the
  sidebar nav) intentionally keeps its existing blue-accented look, same
  scoping call item 13 made - a full site-wide reskin is item 19's Pipeline
  sub-item name aside, really item 21's job, not repeated piecemeal here.
- **Storage**: `pipelineStages`/`pipelineTags`/`pipelineDeals` are three
  new plain localStorage keys, following the existing no-login,
  this-browser-only pattern used by `leadGenerators`/`savedListingIds`/
  `reminders` - not flagged as a concern, this is what the dispatch asked
  for by default, but noting it plainly per the standing instruction to
  flag rather than silently decide if a stronger reason existed (none did).
- **Not done**: Missy's review, and a real PR to `main` (branch is pushed,
  PR still to be opened as part of this same pass).

## 15. Comparables & Area Data analytics (own-data market stats + BTL stress test) - DONE, MERGED (2026-09-22, Dessy)

Reviewed by Missy (verdict: blocked on one real bug, fixed and re-verified
before merge - `areaDataMatches()` matched on area name alone, and common
Bulgarian area names like "Център" are real in dozens of unrelated towns/
cities, so it would have silently pooled prices across them, e.g. Sofia
city-center with a small town's; confirmed with 5 real listings named
"Център" across 5 different cities. `runComparablesSearch()` already
AND'd city into its own match filter for exactly this reason -
`areaDataMatches()` now does too, verified against that exact real-data
scenario. Everything else - the BTL math, the "no rent field anywhere"
data-gap claims, the lazy/bounded trend-chart fetch not reintroducing
item 6's bulk-load problem, design-guideline compliance - checked out.)
and merged in [PR #209](https://github.com/kirilbp/bg-property-tracker/pull/209).

Aggregate analytics built entirely from imotenradar's own already-scraped
listing history - no new data source required. Spec sections 4 and 5
(Area Data / Comparables tabs).

- **Comparables tool**: city/quarter (кв.) + radius-in-km search
  replacing UK postcode-radius search (direct substitute per spec);
  property-type/bedroom/price/size filters; running averages (avg
  price, avg surface area, avg price/m²); distance-from-subject per
  card; Card/Table/Map/Export views.
- **Area Data "Market Live Data" panel**: est. yield gauge, For Sale vs.
  To Rent comparison (avg asking price, avg days on market), historical
  trend chart - all against imotenradar's own listings for the area.
  Needs a graceful "not enough data" empty state for thin areas (spec
  explicitly notes Property Filter itself shows this state).
- **"Last Sold Data" histograms (asking-price version)**: price / £/m²-
  equivalent / size distributions with the subject property marked as a
  pointer, built against imotenradar's own asking-price data. Ship this
  version first; a true "last sold" (actual transaction price) version
  is a stretch goal - see "Open questions" below.
- **Buy-To-Let Stress Test calculator**: generic mortgage-affordability
  math (LTV, interest rate, rent-cover ratio) is not UK-specific: ship
  with Bulgarian-market default assumptions (BG mortgage rates, typical
  LTV terms) in place of Property Filter's UK defaults.

**Status (2026-09-22): all four sub-items implemented in `index.html`,
self-tested against real committed data via a headless-browser harness
(no `Agent`/subagent-spawning tool available this session to hand off to
Missy directly - same documented gap as item 22's dispatch), not yet
reviewed by her.** Summary:

- **Comparables tool - built as two surfaces, not one**, reusing the
  existing `findComparables()`/radius-search logic already in `index.html`
  as the base per the dispatch, rather than starting from scratch:
  - A new standalone top-level nav section (`#section-comparables`,
    "Comparables" in the sidebar) - the spec's own separate section-4
    "postcode-search-first tool, independent of any single listing." City
    + quarter (кв.) dropdowns (quarter deliberately disabled until a city
    is picked - see below) + radius-in-km input + property-type/bedroom/
    price/size filters + a "Search" button, running averages bar, and a
    Card/Table/Map/Export view toggle reusing item 14's own `.pl-*`
    component classes (card grid, table, map, view toggle) rather than a
    new visual language.
  - The listing detail page's existing radius-average panel and Compare
    modal (spec's section-5 "Tab: Comparables," pre-scoped to one listing)
    upgraded into a proper **Comparables tab** alongside Details/Price
    History, with the same Card/Table/Map/Export treatment - matching the
    spec's tab-based design more closely than the old popup-modal pattern
    while leaving the modal itself untouched (still reachable, not
    removed, to avoid a bigger-than-asked-for refactor of working code).
  - A real, non-hypothetical bug caught and fixed during this work: an
    area-only match (no city AND-ed in) would have matched a same-named
    area/quarter across every Bulgarian city sharing that name (e.g.
    "Център" exists in dozens of towns) - the exact collision class item
    18 already documented and guarded against elsewhere in this codebase.
    Fixed by requiring a city before the quarter dropdown becomes
    selectable at all (populateComparablesAreaSelect()), and by AND-ing
    city+area in the actual match filter, not just the UI.
  - Bedrooms filter reuses the existing title-derived `l.rooms` field
    (`extractRoomCount()`), already used by the main Leads filter - no new
    field invented. "Distance from subject" doesn't apply to the
    standalone tool (it has no single subject listing) - distance is
    computed from the searched city/quarter's own geocoded centroid
    instead, which is what the spec's postcode-radius-search concept
    actually maps to at this section's (non-listing-scoped) level.
- **Area Data tab** (new, on the listing detail page): Market Live Data
  stats (avg asking price, avg €/m², avg days on market) for the
  listing's own area+type, a real historical €/m² trend line chart, and
  three "Last Sold Data (asking-price version)" histograms (price, €/m²,
  size) with the subject listing's own bucket highlighted in brass - all
  computed from imotenradar's own already-scraped data, with an explicit
  `AREA_DATA_MIN_SAMPLE = 5` graceful empty state for thin areas (tested
  against a real sparse-area listing in the harness). **Deliberately NOT
  built, flagged rather than faked: the Est. Yield gauge and the For Sale
  vs. To Rent comparison** - both need a rental-listing dataset to compare
  against, and imotenradar doesn't have one; this repo's own "Parked"
  section already investigated rental scraping directly and found under
  ~400 usable whole-property rental listings nationwide, not enough for a
  reliable per-area rent/yield figure. A visible gap-note explains this in
  the UI itself rather than silently omitting the panel or faking numbers.
  The trend chart needed one real architectural judgment call: `MERGED_
  LISTINGS`'s bulk load (backlog item 6) deliberately excludes
  `price_history` for performance, so building a genuine historical trend
  needed a small, explicitly bounded, chunked `id`-list-scoped fetch
  (capped at 200 listings, same lazy-fetch shape as the existing
  listing_sources/description fetches) rather than either reintroducing a
  bulk load or faking a trend from non-historical data.
- **Last Sold Data histograms**: shipped as the asking-price version only,
  per the spec's own recommended sequencing - labeled honestly in the UI
  ("asking-price version... not Registry Agency transaction data") rather
  than implying it's real sold-price data. True last-sold data remains an
  open question (Имотен регистър/Кадастър scrapability unconfirmed) per
  this file's "Open questions" section, unchanged by this work.
- **BTL Stress Test tab** (new, on the listing detail page): a live,
  reactive calculator (LTV %, interest rate %, Interest Cover Ratio %,
  purchase price defaulting to the listing's own price) computing
  "Minimum rental income per month to pass" and "Maximum price offer to
  pass," with illustrative Bulgarian-market default assumptions (70% LTV,
  4.0% interest, 125% ICR - all editable, explicitly labeled as
  illustrative defaults, not live rates) replacing Property Filter's UK
  defaults. Monthly rent is a **required user input, never defaulted or
  estimated** - imotenradar has no Bulgarian rental dataset to estimate it
  from (same gap as the Area Data tab's own note, and the same gap item
  10 already flagged for its own "yield-like %" pipeline-card stat), so
  the calculator asks the user for their own rent research rather than
  fabricating one. The underlying math is pure and UK-non-specific (LTV ×
  interest rate × interest-cover ratio), verified by hand in the test
  harness against known inputs.
- **Verification**: syntax-checked (`node --check`), then exercised
  end-to-end with Playwright against a headless Chromium, driven by a
  ~130-row fixture sampled from the real committed `data/leads_imot.json`/
  `data/history_imot.json` (this sandbox's egress proxy blocks the live
  Supabase project directly, same documented limitation prior sessions
  hit - Supabase-js/Chart.js/Leaflet were served from local npm-installed
  copies of the exact same pinned CDN versions rather than skipped, since
  cdnjs.cloudflare.com/unpkg.com are also proxy-blocked). Covered: standalone
  Comparables search + all three view modes + CSV export + the
  city-before-area guard; the listing detail page's new Comparables/Area
  Data/BTL tabs including a genuinely sparse area's empty state; a real
  bug found and fixed in the process (a `type="number"` input threw on
  `selectionStart`/`selectionEnd` assignment in the BTL tab's keystroke-
  preserving refocus logic - fixed by dropping cursor-position restoration
  for number inputs). Checked responsively at 1440px/900px/390px - the
  new sections inherit the same non-collapsing-sidebar limitation the
  entire rest of the site already has at phone width (confirmed identical
  on the pre-existing Home page, not a regression introduced here; a real
  gap, but a site-wide one already flagged as unaddressed in the spec's
  "Gaps in Nosy's spec" section, not something to fix piecemeal in this
  pass).
- **Design-guideline judgment calls made, not covered explicitly by
  `docs/design-guidelines.md`**: reused item 14's `.pl-*` component
  classes (card grid/table/map/view-toggle) for both new Comparables
  surfaces rather than inventing new markup for the same visual pattern;
  histogram "subject bucket" highlighting uses a single brass bar against
  muted taupe bars (no second accent color, no traffic-light coding);
  BTL pass/fail uses the sage signal color for "pass" and the ink-soft
  tone for "fail" rather than green/red, per the design guidelines'
  explicit red-reads-as-alarm rule.
- **Not done**: Missy's review, and a live check against the real
  Supabase project (blocked from this sandbox, same as every other recent
  item).

## 16. Market Data hub (portfolio-level aggregate tiles) - DONE, MERGED (2026-09-22, Dessy)

Reviewed by Missy (verdict: one real bug found and fixed before merge -
the Adverts Evolution chart's "newly tracked" series sampled the OLDEST
200 listings in scope, not a representative set, since `MERGED_LISTINGS`
loads ascending by id and is never re-sorted - for any real portfolio-
wide scope this meant the chart was built almost entirely from ancient
months and typically showed nothing recent. Fixed to sample the most
recent 200 instead, and stopped needlessly capping the "marked sold"
series, which costs no extra fetch. Also caught and corrected an
invented mechanism in this entry's own item-22 cross-reference - this
codebase has no lat/lng-based city resolution anywhere; the stale
"Bulgaria" rows actually resolve via ordinary title-text matching.
The city-vs-area collision risk this line of work has hit twice before -
Area Performance's nationwide-by-city / drilled-into-quarters grouping,
the new `.market-tab-btn` CSS-class separation from item 13's tabs to
avoid state cross-talk - were both independently verified correct, not
just trusted.) and merged in
[PR #211](https://github.com/kirilbp/bg-property-tracker/pull/211).

Reuses item 15's aggregation work at a broader, cross-listing scope. Spec
section 7. Fully replicable, built purely from imotenradar's own scraped
listing history (price, status, time-on-market, agent) aggregated by
area: Strategy Heat Map, Postcode Performance -> city/quarter Performance,
Market Live Map (Yield/Asking Prices/Time On Market/Demand), Adverts
Evolution (stock changes: Available/STC-equivalent/Removed over time),
Agent Properties (all listings by a given agent). Sequence after item 15
since it's the same underlying aggregation, wider lens.

**Status (2026-09-22): 4 of the backlog's own 5 named tiles built and
self-verified against real committed data; the 5th (Agent Properties)
confirmed not buildable and flagged rather than faked. PR open, not yet
merged - Missy's review still needed (see gap note below).**

Built in `index.html`'s existing "Market Data" nav section (the old static
HPI card kept as-is; its legacy raw-`l.area`-string "Avg €/m² by area" bar
chart - the exact pre-item-18 collision bug, e.g. pooling every city's
"Център" together - was removed and replaced by the new hub below, not left
alongside it):

- **Area Performance** (Postcode Performance's city/quarter substitute):
  a sortable table, nationwide by city (BG_CITIES' ~29 known-safe keys) or
  drilled into one city's own quarters (`areaKeyGroupsForCity()`) once a
  city is picked - listings/active/sold counts, avg price, avg €/m², avg
  days on market, % with a price drop, each row requiring a same 5-listing
  floor `AREA_DATA_MIN_SAMPLE` already used for.
- **Strategy Heat Map**: same rows, ranked by a selectable own-data metric
  (motivated-seller share = % with a price drop, avg days on market, avg
  €/m²) - "yield" is not offered as a metric, no Bulgarian rental dataset
  exists to compute it from (same gap item 15's Area Data tab already
  documents). Heat is shown as varying opacity of the single brass accent
  color, never a hue change - design-guidelines.md's ban on red/yellow/
  green status treatments applies here as much as anywhere else.
- **Market Live Map**: a Leaflet map (reusing the Comparables tool's own
  map-init pattern) plotting one marker per area/city at its listings'
  average lat/lng, sized and shaded (not hued) by a selectable metric
  (asking €/m², avg days on market, demand = tracked listing count).
  "Yield" excluded from the metric list for the same reason as the heat map.
- **Adverts Evolution**: a monthly bar chart of "newly tracked" (derived
  from each listing's own earliest `price_history` entry, fetched via the
  same bounded/on-demand/ID-capped pattern - max 200 ids, 100/chunk - the
  Area Data tab's own trend chart already uses, never a bulk load, per
  backlog item 6's lesson) vs. "marked sold" (derived from `removed_at`,
  already present on loaded rows, no extra fetch). **Explicitly flagged in
  the UI**: no STC-equivalent shown - `merged_listings.status` is binary
  (Active/Sold only, sold once every cross-posted source's own
  `removed_at` agrees it's gone), there's no tracked interim "under offer/
  reserved" state the way Property Filter's UK-market Available/STC/
  Removed has one.
- **Agent Properties - NOT built, confirmed not possible with current
  data.** Re-checked the full field union across every `data/leads_*.json`
  file directly (not just trusted item 13's earlier finding): no agent/
  agency name, phone, or contact field exists anywhere in imotenradar's
  scraped data. Flagged plainly in the UI (a `.market-gap-note` under the
  hub) rather than a fake/empty tile. Needs new scraper work (a detail-page
  field none of the 8 scrapers currently extract) before this tile can show
  anything real - a backend/scraper change, out of this frontend-only
  builder's scope to add.
- **Not built, correctly out of this item's own explicit scope**: Postcode
  Prices Trend (not in this backlog item's own named tile list, and marked
  "Soon" even in Property Filter itself), Last Sold Map / Price vs Income /
  Title Boundaries / Planning Applications / Census Data / Planning
  Constraint Map (spec section 7's other two "Sold Prices Data"/"Due
  Diligence" groups - all separately flagged UK-only-or-uncertain in the
  spec itself and not part of this backlog item's own tile list).

Verified locally end-to-end: JS syntax-checked (`new Function()` on the
extracted `<script>` body), then driven in a real headless Chromium via
Playwright against a 6,000-listing fixture sampled from real committed
`data/leads_imot.json`/`leads_alo.json`/`leads_homes.json`/`leads_olx.json`
(CDN/Supabase network calls stubbed with local npm-installed pinned
Chart.js/Leaflet/supabase-js copies and a route-intercepted REST fixture
server, since this sandbox's egress proxy blocks the live Supabase project
and every CDN this app loads from - same approach item 15 used). Confirmed:
all 4 tabs render with zero page errors nationwide and drilled into Sofia;
city/type filter state persists correctly across tab switches; the heat
map/live map re-render correctly when their own metric dropdown changes;
the Adverts Evolution chart correctly fetches and buckets by month; the
existing listing-detail page's own tabs (Details/Price History/
Comparables/Area Data/BTL Stress Test) still default and switch correctly
with no cross-talk from the new hub's own tab state (a real risk flagged
and designed around up front - see the `.market-tab-btn`/`.market-tab-
content` code comment on why they're distinct classes from `.detail-tab-
btn`/`.detail-tab-content` rather than reused); checked reflow at a 768px
mobile viewport with no layout breakage.

**One real, already-known data-quality issue surfaced (not caused) by this
work, worth flagging again since it's now visible in a new place**: backlog
item 26's stale alo.bg `area == "Bulgaria"` placeholder rows (still
uncleaned in committed data as of this writing) show up as a bogus
"Bulgaria" row in the Sofia-scoped Area Performance table.

**Correction (Missy's PR #211 review):** the mechanism above was
described wrong in an earlier version of this entry, which claimed a
"backfilled lat/lng" resolves these rows to `sofia`. Checked directly:
this codebase has no lat/lng-based city or oblast resolution anywhere
(`geo_utils.py` does no reverse-geocoding or point-in-polygon lookup) -
these rows actually resolve to `city_key: "sofia"` via the ordinary
title-text-matching fallback both `listing_city_key()` (server) and
`listingCityKey()` (client) already use whenever a listing's `city`
field is null, because their titles happen to literally contain "София"
(e.g. "...в зона Б-19 Зона Б19, София..."). The "excluded by the
existing `listingAreaKey()` guard" line was also wrong - that guard is
`if (!l.area) return`, and `"Bulgaria"` is a truthy non-empty string, so
it does nothing for this specific placeholder value. The bottom-line
conclusion is still accurate (real, pre-existing, not caused by this
item, self-resolves once item 26's cleanup lands) - only the stated
mechanism was invented rather than checked; corrected here rather than
left standing.

**One design-scope judgment call**: the hub's own tabs reuse the `.pl-*`/
`.cmp-*` design tokens/components item 15 already established (cards,
tables, view toggle, brass accent) rather than a new visual language, but
are NOT wired through the listing-detail page's `.detail-tab-btn`/
`.detail-tab-content` classes despite being visually identical - see the
code comment above `.market-tab-btn` for why (switchDetailTab() toggles
*every* `.detail-tab-btn`/`-content` element in the document by `data-tab`
value with no scoping, which risked an accidental cross-page tab-state
collision once both existed in the same DOM).

**Not done - real gap, not a shortcut taken lightly**: no `Agent`/Task tool
available this session to dispatch to Missy directly for real review (the
same recurring limitation prior entries in this file and `docs/
decisions.md` have already flagged). This PR is open on `main`, **not
self-merged**, specifically so Missy's real review happens before it ships,
per this repo's standing rule.

## 17. Send Letters / motivated-seller outreach campaigns - BUILT, PARKED PER USER DECISION - DO NOT RESUME WITHOUT ASKING (2026-09-23)

**Built end-to-end and reviewed (PR #214, closed unmerged 2026-09-23)** -
both Missy's and Revy's technical review passed clean (client-side only,
no leak paths, no backend/RLS exposure, no auth reintroduced). But
Revy's review raised a real product/legal question, not a code bug: this
feature stores real third parties' PII (seller names, addresses, phone
numbers, emails) indefinitely, unencrypted, with no deletion mechanism,
for unsolicited outreach to people who never signed up for anything -
in an EU/GDPR jurisdiction, with real legal-basis/data-minimization
questions and no retention/deletion path. Escalated to Kiril rather than
decided by the team, per Revy's own standing "escalate rather than
guess" rule.

**Kiril's decision**: "Ignore the letters for the moment. We can
integrate them later." Parked, not abandoned - the built branch
(`dessy/send-letters-campaigns`) still exists if this gets picked back
up. **Do not resume building or re-open this without asking Kiril
first** - this is exactly the kind of legal/privacy-risk product
decision that needs his explicit call, not autonomous team judgment,
unlike the routine implementation design forks elsewhere in this
backlog.

Direct-mail-to-owner outreach workflow (spec sections 5's "Send Letter"
tab and section 6's full campaign manager). Flagged by Nosy as "fully
Bulgarian-replicable, high-value workflow" and a genuinely portable
feature if imotenradar wants to pursue a deal-sourcing angle, not just an
aggregator - but it's a materially bigger scope than items 13-16 (mail-merge
templating, a reverse address lookup, and an actual physical-mail send
integration/partner, none of which imotenradar has any of today), so it
sits after the smaller, faster-to-ship analytics items despite the high
value rating.

**Design fork resolved (2026-09-22), see `docs/decisions.md` for full
reasoning:** the "real physical-mail send path" dependency is resolved as
a clearly-stubbed, pluggable `mailProvider` interface (typical
Bulgarian/EU direct-mail API request shape: recipient address, letter
content, sender return address, batch reference) with a documented
`TODO(mail-provider)` for a human to pick a real vendor, sign up, and add
an API key - not a real paid integration. Chosen over integrating a real
vendor because that would be a new recurring paid external commitment
(a different category than items 13-16's frontend/data work) that this
session cannot itself sign up for or pay for, and because "anything that
costs money" is one of the few categories this project's standing rules
require real human sign-off on rather than an autonomous call. Everything
else below is built for real against real data; only the literal outbound
send call is stubbed.

**A second real finding also resolved into scope (see decisions.md):**
imotenradar's scraped data has no street-level postal address anywhere
(checked the real field union of every `data/leads_*.json` file and
`supabase/schema.sql` - only `area`/`city`/`oblast_key`/`lat`/`lng`
exist, and sampled real `description` text confirms Bulgarian listings
deliberately omit exact addresses). "Property Lookup" itself is unaffected
(it's a reverse lookup against imotenradar's own data, not an address
generator). But a campaign's per-letter delivery address must be built as
an **editable, human-completed field**, pre-filled from best-available
scraped text (area + city + description excerpt) and never presented as a
verified postal address, before a letter can be marked ready to send.

**No `Agent` tool available this session (confirmed via `ToolSearch`)** -
per the platform-constraint section of `.claude/agents/bossy.md`, this
pass is planning/breakdown only. The dispatch list below is for whoever
picks this item up next to execute as their own `Agent` calls (a builder
per task, Dessy for the Letter Designs UI, Missy + Revy before merge -
Revy because outbound mail batches carry seller PII, personal names and
addresses, even though no auth/login is involved).

**Dispatch list (independently shippable, serialize any two that touch
`index.html`'s Send Letters section rather than parallelizing them):**

1. **Campaign management (general-purpose builder).** `localStorage`
   state, same pattern as `LEAD_GENERATORS`/`ALL_REMINDERS`
   (`SEND_LETTERS_CAMPAIGNS_KEY` or similar, JSON array, load/save
   helpers mirroring `loadLeadGenerators()`/`saveLeadGenerators()`).
   Draft campaigns table (addresses count, letter design used, batch
   cost estimate, "Review & Send" action) and an Active campaigns table
   (adds batch-delivered progress e.g. "1/4", a response-tracking count
   the user can increment/log manually since there's no inbound-mail API
   to detect responses automatically, last/next delivery dates). "Create
   a new campaign" flow: pick a Letter Design, pick addresses (from
   saved listings, a Lead Generator, or the Deal Pipeline - reuse
   whichever selection pattern items 13/14 already established). No
   design-guidelines-only work here (Dessy not needed), but style with
   the existing brass/sage/ink CSS variables from item 13's redesign
   rather than introducing new ones.
2. **Letter Designs template bank + editor (Dessy).** Situation-keyed
   template pills: General, Back on Market, Price Reduced, Withdrawn,
   Long Time On Market, Multiple Agents, plus free-form "Create your
   own." Each built-in template's default copy should reference the real
   signal it's keyed to using fields that already exist and are verified
   live in `index.html`: Back on Market -> `relistingEventsFromHistory(l.price_history)`
   (already powers the existing "Relisted" badge), Price Reduced ->
   `price_drop_count`/`drop_pct`, Withdrawn -> `source_status === 'removed'`
   with no relisting yet, Long Time On Market -> `days_on_market`,
   Multiple Agents -> `member_count`/`member_portals` (cross-posted on
   multiple portals - the closest real Bulgarian analog to "listed with
   multiple agents"). Rich-text editor with insertable tokens
  (`{property_address}`, `{phone_number}`, `{email_address}`,
  `{homeowner_name}` - default "The Homeowner" per spec, since no
  verified owner name exists in scraped data either) and a line-count
  indicator. Do NOT build "Low EPC"/"Short Lease"/"R2R guaranteed rent"/
  "Long time sold STC" situation types (UK-only or reliant on a BG
  transaction-status this project doesn't track - see "Confirmed drops").
  If this task turns up a need to touch a scraper/schema/workflow file,
  stop and split it back to Bossy per Dessy's own standing instruction.
3. **Reverse address lookup / "Property Lookup" (general-purpose
   builder).** Pure client-side search against imotenradar's own already-
   loaded listing data (`MERGED_LISTINGS`) plus the campaign/letter
   records from task 1: given a typed address/area/phone, find which
   campaign(s) and letter(s) targeted that listing. No external API
   needed - confirmed, this is the one piece of the feature that doesn't
   depend on the address-data gap above, since it only needs to match
   against whatever partial address text a campaign was actually built
   with, not a verified postal address.
4. **Stubbed `mailProvider` send interface (general-purpose builder,
   same task as #1 or immediately after it).** `sendBatch()` stub per
   the decisions.md entry, wired into "Send batch" in the UI: runs
   address-completeness validation (rejects/flags any letter whose
   address field was never manually completed per the finding above),
   renders the letter, creates the batch record, then marks it "Not sent
   - no mail provider configured" rather than silently no-op'ing. Include
   the `TODO(mail-provider)` comment with the exact human steps (pick a
   Bulgarian/EU direct-mail API provider, sign up, add API key, replace
   the stub's HTTP call).

**After each task lands (real unit/dry-run tests against real listing
data, not just visual):** send straight to Missy, and to Revy alongside
her since this handles seller PII (names/addresses) even without login.
Don't batch multiple tasks' review together - each goes the moment it's
locally verified, per this project's standing "nothing ships without
Missy, and she sees it immediately" rule.

## 18. Deal Calculator (investment strategy modeling) - formula work DONE, ready to build except 2 open items (2026-09-23)

Spec section 8. The overall mechanism (pick a strategy -> get a
strategy-specific calculator -> save as a reusable template or link to a
property) is a strong, fully replicable pattern. The formula-work
blocker is now resolved: `docs/deal-calculator-formulas.md` gives real,
BG-market-adapted input fields and math for every strategy below,
sourced against standard real-estate-investment formulas (cash-on-cash
return, cap rate, BRRR "cash left in deal", GDV/residual development
appraisal, etc.) plus researched Bulgarian defaults (transfer tax,
mortgage LTV/rates, STR licensing). **Note: that doc also corrects an
outdated assumption - Bulgaria adopted the euro on 1 January 2026, so
all figures/fields are EUR, not BGN** (matching `index.html`'s existing
`price_eur` fields).

- **Ready to build with real formulas:** BTL (extends the shipped BTL
  Stress Test from item 15 - `computeBtlStressTest()` in `index.html`),
  BRRR, BTSA, BRSAR, FLIP, R2R, R2SA, COM2RESI-TOSELL, Assisted Sale.
- **Still a business call, not a technical blocker** (per
  `deal-calculator-formulas.md` section 8): R2R (long-term subletting)
  is legal in Bulgaria by default for a *part*-property sublet (e.g.
  room-by-room/co-living); a *whole*-property sublet needs the head
  landlord's explicit consent instead (corrected per Missy's review -
  see `deal-calculator-formulas.md` section 7 for the Art. 234 ZZD
  distinction).
  R2SA/BTSA/BRSAR (short-term/serviced accommodation) are also legal but
  *regulated* - they require Tourism Act categorization/registration as
  an accommodation place, with a real per-bed fee and platform-enforced
  compliance. Whether that regulatory overhead makes these strategies
  worth building is still the user's call to make when this item is
  picked up.
- **Drop, confirmed (not just UK-only-and-unresolved):** Title Split -
  Hold/Sell. Research now explains *why* there's no BG equivalent to
  build instead: Bulgaria's condominium ownership regime (етажна
  собственост) already gives every apartment its own title at
  construction, so the UK problem title-splitting solves doesn't exist
  here; converting an *undivided* building is the change-of-designation
  process already covered under COM2RESI-TOSELL.
- **Still genuinely open - needs a Bulgarian real-estate lawyer, not
  more research:** PLO (Purchase Lease Option). See "Open questions"
  below - no formula was written for it, on purpose, since a
  lease-option structure's Bulgarian enforceability is unconfirmed and
  a fabricated formula for an unconfirmed legal structure would be worse
  than not offering the strategy.

## 19. Preferences / settings to support items 13-18

Spec section 9. Mostly small, fully-replicable settings screens that
exist to back the features above rather than stand alone - sequence each
sub-tab alongside the feature it configures rather than building all of
Preferences as one block:
- Display (surface/distance units - note Bulgaria already uses metric
  natively, so the UK mile/km toggle complexity isn't even needed),
  Search Results (motivation-indicator thresholds - already a close
  match to imotenradar's own motivation-score fields), Lead Generator
  defaults, Pipeline (stage + tag configuration - ship with item 14),
  Notifications (new-lead-generator-count / status-change mechanics -
  ship with item 14), Deal Stacker defaults (BG mortgage-rate defaults -
  ship with item 15's Stress Test), Calendar integration, Letters defaults
  (ship with item 17), Deal Calculator Templates defaults (replace UK
  Stamp Duty default with a Bulgarian transfer-tax % default - ship with
  item 18).

## 20. Map tab additions - Satellite + Amenities SHIPPED (2026-09-23, Dessy), Street View BLOCKED, Cadastral OUT OF SCOPE

Spec sections 4 and 5's Maps tab. Street View, Satellite, and Amenities
(POI) layers are fully replicable generic map layers - low effort, can
ship alongside item 13. The one genuinely good UK-concept-with-a-real-BG-
substitute is worth calling out on its own: **cadastral map integration**
("Title Plans"/"Title Boundaries" substitute) - Bulgaria's Кадастрална
карта (Agency of Geodesy, Cartography and Cadastre) provides parcel
boundaries and is publicly viewable; worth prioritizing if imotenradar
can integrate it, but scoped as its own task since it's a new external
data source, unlike the rest of this backlog - **deliberately not
attempted in this pass, still open.**

**Shipped 2026-09-23** (built on the existing listing-detail radius map,
`index.html`'s `updateRadiusMap()`/`renderRadiusPanel()` - the same
Leaflet integration item 13 already uses, not a new separate "Maps tab"
with the spec's full 7-icon rail, which would be a materially bigger
scope than "low effort, ship alongside item 13" calls for):

- **Satellite layer - DONE.** A Street/Satellite toggle (two small
  buttons above the map, styled like the existing radius-btn/brass
  palette, no new blue) switches the map's base tile layer between the
  existing OpenStreetMap street tiles and Esri World Imagery
  (`server.arcgisonline.com/.../World_Imagery/...`) - a free, keyless
  aerial-imagery tile service (no account or billing needed, unlike
  Google's satellite tiles), the standard choice the Leaflet ecosystem
  uses for exactly this reason (`leaflet-extras/leaflet-providers`'
  `Esri.WorldImagery` entry).
- **Amenities (POI) layer - DONE.** An "Amenities" toggle button queries
  the Overpass API (`overpass-api.de`) - OpenStreetMap's free, keyless,
  CORS-open live-query service, no account needed (unlike Google
  Places) - for schools, hospitals, pharmacies, kindergartens, banks,
  supermarkets, restaurants/cafes, bus stops, and train stations within
  800m of the listing, and plots them as small hollow (unfilled) brass
  rings - distinct from the existing solid brass comparable-listing dots
  by shape, not a second fill color (see docs/decisions.md's 2026-09-23
  PR #238 review-fix entry: the original sage-filled version violated
  design-guidelines.md's "sage is text-only, never a filled marker/badge"
  rule). Results
  are cached per-listing so re-rendering the map (radius/layer clicks)
  doesn't re-query. Fails gracefully: a blocked/slow/erroring request or
  a listing with none nearby shows a small inline note instead of
  breaking the map.
- **Street View - NOT built, correctly blocked, not faked.** Checked for
  a genuinely free/keyless option per this dispatch's instruction before
  building anything: Google Street View needs a paid/billed API key
  (already known, out of scope). The realistic open alternatives
  (Mapillary, KartaView) are not truly keyless either - both require
  registering for a free API/client token, a credential this sandbox
  doesn't have and the user would need to supply, and neither has known
  reliable coverage in Bulgaria the way Google's does. No Bulgarian
  government or open equivalent is known. **Needs the user to decide
  whether to supply a Mapillary (or similar) API token, or a Google
  Street View billing key, before this sub-feature can be built at all**
  - left undone rather than shipping a broken/empty panel.

**Verification caveat, flagged rather than assumed:** this sandbox's
egress proxy blocks all external hosts, including ones the live site
already depends on today (`unpkg.com`, `cdn.jsdelivr.net`, and the
already-shipped `tile.openstreetmap.org`) - confirmed via direct `curl`
(403 from the proxy on every one) and via the proxy's own status log.
So neither the new Esri satellite tiles nor a real Overpass response
could be fetched live from this session to visually confirm real tile
pixels/POI data render correctly - this is a sandbox-only limitation,
not evidence the integrations don't work (the app already relies on
the same class of external host working in production). Verified
instead with a real Playwright harness against the actual `index.html`
(vendored Leaflet/Chart/Supabase locally, reusing a prior session's
harness pattern in scratchpad) with the two new endpoints stubbed with
realistic responses (Overpass's own long-documented, stable
`{elements: [{type, id, lat, lon, tags}]}` JSON shape): confirmed the
Street/Satellite toggle correctly swaps the active tile layer and
requests satellite tiles, the Amenities toggle correctly fetches once,
caches, and plots markers on the map (2/2 stub POIs rendered), the
graceful-failure note renders correctly when the POI fetch is made to
fail, an empty-result note renders correctly on a mobile (390px)
viewport with no layout overflow, and the whole page still loads with
zero *new* console/page errors (one pre-existing `_leaflet_pos`
Leaflet-internal warning was independently reproduced against
unmodified `main` too, confirming it predates this change and isn't a
regression). **Whoever reviews this should still confirm the real Esri
tile and Overpass responses render correctly against the live
deployed site** (this session cannot, being sandboxed) before
considering the visual/data-accuracy side fully confirmed - the toggle
mechanics and error-handling are the part this session could verify
directly.

## 21. Visual/premium design refresh - DONE (2026-09-23, Dessy)

**Priority elevated by item 10** (user feedback, 2026-09-23: the live
site still doesn't read as luxurious/stylish, since item 13's redesign
was deliberately scoped to the listing detail page only) - work this
next, after items 7-9, rather than waiting for items 13-16 to fully
build out.

Spec's closing "Design direction" section, not a feature but a directive
that should land as part of items 13-16's builds rather than a standalone
pass: richer typography (serif/high-contrast display face for headings),
more generous whitespace between listing-card elements, a refined
restrained palette (deep neutral tones + one considered accent) in place
of a bright SaaS-blue palette, subtle elevation/shadow and rounded card
surfaces. Explicitly: match Property Filter's *workflow and information
density*, not its visual skin - imotenradar should read as more premium.

**Status: done.** Shipped in two pieces, both against `docs/design-
guidelines.md`'s already-established (item 13) Playfair Display + Inter /
warm ivory-brass-ink-sage CSS variables - no new palette invented:

1. **The main pass** (merged straight to `main`, 2026-09-23, before this
   write-up): recolored/re-typeset every remaining surface item 13 had
   left untouched - the sidebar (warm ink canvas, brass active state with
   a left-border accent instead of a solid fill, understated no-fill
   hover), the main listing grid/cards (photo-dominant cards kept, but
   badges rebuilt as small-caps muted pills - one brass "Hot deal" accent,
   one sage signal color for every buyer-favorable price fact, neutral
   ink/taupe for everything else - replacing the old saturated red/green/
   blue/purple ribbon system per section 6/9's explicit "status labels,
   not ribbons" rule), the search/filter panel, pagination, Home page
   (stat tiles, portal chips, type/city pills), Help page, the Reminders
   list, and the shared modal CSS used by the Lead Generator/Reminder/
   Pipeline-config modals. Also applied "one primary action per view"
   (section 5/6): the Home page's second solid CTA was demoted to an
   outline `.cta-btn-secondary`, and the listing detail page's Save/
   Compare/Remind/Pipeline row already had this from item 13 (one solid
   brass Save, everything else outline) - confirmed still correct, not
   re-touched.
2. **A verification + consistency follow-up** (this entry, same day):
   real Playwright screenshots at 1440px and 390px across every page -
   Home, Leads grid, listing detail + Reminder modal, Lead Generators +
   its modal, Pipeline + its config modal, Comparables, Dashboard, Market
   Data, Help - confirmed the main pass's coverage claims against the
   actual rendered `index.html` (zero page errors) rather than trusting
   the commit message, and found/fixed 4 small leftover inconsistencies
   the main pass missed: a saturated-red (`#dc2626`) comparable-listing
   marker on the listing detail page's own radius map (every other
   comparable-marker map in the app was already brass); two `.danger`-
   hover icon buttons (Lead Generator delete, Pipeline remove) using an
   ad-hoc hex pair instead of the existing `--error` variable; every
   native checkbox site-wide rendering with the browser's default blue
   tick (fixed with one global `accent-color: var(--brass)` rule); and
   every Leaflet map's "subject point" marker using Leaflet's default
   blue pin icon (replaced with a small CSS-only brass teardrop,
   `brassPinIcon()`, reused across all three call sites - no new image
   asset). Full detail of both pieces and what's still explicitly open
   (progressive-disclosure filters, no mobile sidebar collapse) is under
   item 10 above.

## 22. Area/neighborhood filter and Lead Generators use exact raw-string matching against un-normalized portal text - undercounts every settlement, not just Cherven Bryag - DONE, MERGED (2026-09-22)

**Numbered last but work this immediately after item 6/7 - do not let its
position at the end of this list imply low priority.** From the user
directly reporting the live site (Cherven Bryag Lead Generator showing
only 7 listings, implausibly low), confirmed and scoped by Missy sampling
the committed data.

`populateAreaFilter()`/`populateLeadGenNeighborhoods()` (`index.html`
~2685, ~2794) build their dropdown/checkbox options straight from raw
`l.area` strings with no normalization; the actual filters (`render()`
line 3599, `matchesLeadGenerator()` line 2783) do exact string
comparison. Since the same real settlement/neighborhood is formatted
differently per portal (кв./жк. prefixes, Cyrillic vs. transliterated
Latin, capitalization), it silently splits across multiple dropdown
entries and selecting one excludes real listings genuinely in that area.

**Confirmed facts:**
- Cherven Bryag itself: 28 raw listings across 5 portals genuinely in the
  town (verified by real-world coordinates), split 26/2 between
  "Червен бряг" and "Cherven Bryag" - selecting either dropdown entry
  misses the other. (Missy couldn't reproduce the exact "7" figure
  without live `merged_listings` access, but the mechanism is real and
  consistent with an undercount landing this low after cross-portal
  dedup.)
- **Platform-wide, this is large, not a one-town edge case**: of 305,065
  listings with a non-empty `area` across the 8 committed leads files,
  481 of 8,507 distinct normalized area keys have more than one
  raw-string variant, affecting **179,061 listings (58.7%)**. Several
  high-traffic real neighborhoods (Малинова Долина, Тракия, Кършияка,
  Христо Смирненски, Остромила, Виница, Изгрев, Широк център, Кайсиева
  градина, Бриз, Възраждане, Овча Купел, Сарафово, Беломорски) split
  their listings roughly evenly across 3-5 variants, so picking any one
  dropdown entry shows ~20-30% of the area's true count.
- `listing_city_key()`/`city_key` already exists server-side but only
  resolves against `BG_CITIES`' 29 major cities - Cherven Bryag isn't on
  that list, wrong granularity for this bug regardless.
- `normalize_area()`/`areas_match()` already exist in
  `sync_to_supabase.py` (lines 64-90) but are only used internally to
  decide merge-group membership - never stored as a column, never
  exposed to the frontend. The JS equivalent (`normalizeArea`/
  `areasMatch`/`groupListings`) that used to exist client-side per
  `sync_to_supabase.py`'s own "ported 1:1 from index.html" header comment
  has since been deleted from `index.html` entirely (confirmed, zero
  matches) - this needs a real (if smaller-than-from-scratch) fix,
  reusing the trusted Python function, not a bigger design.
- **Related, same code path**: `matchesLeadGenerator()`'s neighborhood
  mode never checks `gen.area.city` against a listing at all - the Lead
  Generator modal's City field is free text that does nothing in the
  actual match, and the neighborhood checkbox list is built from every
  `l.area` nationwide, not scoped to the typed city. The modal's own hint
  text ("Only Sofia has live listing data right now") is stale - the
  platform is nationwide now (8 portals, 305k+ listings, most outside
  Sofia).

**Recommended fix**: add an `area_key` column (schema + sync script,
reusing `normalize_area()` verbatim) to `listing_sources`/
`merged_listings`, backfill, switch the area dropdown/Lead Generator
neighborhood picker and both match sites to compare `area_key` instead of
raw `l.area`, displaying one representative raw label per group (same
"pick by score/frequency" precedent `best.get()` already uses elsewhere).
Separately, wire `gen.area.city` into the actual match logic (or remove
it and its stale hint honestly) rather than leaving it decorative.

Full investigation detail (exact sample data, file/line references):
`docs/decisions.md`'s 2026-09-22 entry.

**Status (2026-09-22): implemented and self-verified against real data,
not yet reviewed by Missy (no `Agent` tool this session - see
`docs/decisions.md`'s matching entry for the full detail and the exact
dispatch needed).** Summary:
- `area_key` column added to `listing_sources`/`merged_listings`
  (`supabase/schema.sql`), computed via the existing `normalize_area()`
  in `sync_to_supabase.py`'s `build_rows()`. No separate backfill script
  needed - the next real `sync_to_supabase.py` run (both scrape workflows
  already call it) backfills every row automatically once the schema
  migration is applied in the Supabase SQL editor.
- `index.html`: also ported `normalize_area()` to JS (`normalizeArea()`,
  verified byte-for-byte identical against all 9,246 real distinct raw
  area strings) so the fix is effective immediately, independent of the
  backend migration's timing - `listingAreaKey(l)` prefers the server
  `area_key` column when present, falls back to computing it client-side
  otherwise. `populateAreaFilter()`/`populateLeadGenNeighborhoods()` now
  group by normalized key and show one representative (most frequent raw
  string) label per group; `render()` and `matchesLeadGenerator()` compare
  normalized keys, with the match normalizing both sides so an older saved
  Lead Generator's raw-string `neighborhoods` array still matches
  correctly with no data migration needed. Found and fixed the same bug
  in a third spot while tracing this: the Lead Generator gallery's own
  mini-map preview had the identical exact-match issue.
- `gen.area.city` wired into the real match logic (not just relabeled):
  resolves to a `city_key` when it's one of `BG_CITIES`' ~29 major cities
  (verified this correctly prevents a same-named-area cross-city false
  positive, e.g. Sofia's "Център" vs. Dobrich's), left unconstrained
  otherwise so a smaller town like Cherven Bryag still matches correctly
  by area key alone. Stale "Only Sofia..." hint text replaced.
- Verified against real data throughout: reproduced Missy's exact
  platform-wide figures independently (8,507 keys, 481 multi-variant,
  179,061/58.7% affected), ran the real `build_rows()` against the full
  305,065-listing dataset, and functionally tested the real `index.html`
  JS (not a rewritten copy) via a Node `vm` harness against realistic
  fake data and the full real 214,889-row merged dataset.
- Reviewed by Missy (verdict: safe to merge - independently reproduced
  every numeric claim against real data) and merged in
  [PR #200](https://github.com/kirilbp/bg-property-tracker/pull/200).

**One open item, not a code defect, needs a human:** the
`supabase/schema.sql` migration (new `area_key` column + index) has not
been confirmed applied to the live Supabase table - no session this far
has had console access. The site works correctly today regardless, via
the client-side `normalizeArea()` fallback in `index.html` (verified);
the server-side column is a performance optimization for later, not a
correctness blocker. **Action needed from Kiril**: run the migration in
the Supabase SQL editor. The exact statement (idempotent, additive only,
matches the existing `city_key`/`oblast_key` pattern):

```sql
alter table listing_sources add column if not exists area_key text;
alter table merged_listings add column if not exists area_key text;
create index if not exists merged_listings_area_key_idx on merged_listings (area_key);
```

After running it, the next scheduled sync (or a manual dispatch of
`sync-supabase.yml`) backfills every row automatically - no separate
backfill script needed.

**Real production consequence of this migration still being pending
(found and fixed 2026-09-22, [PR #205](https://github.com/kirilbp/bg-property-tracker/pull/205)):**
every `sync_to_supabase.py` run started crashing outright the moment this
item's code shipped, on Postgres/PostgREST's own "PGRST204: Could not
find the 'area_key' column... in the schema cache" - since `upsert()` had
zero handling for a column the code sends but the live table doesn't
have yet, and this happened before `main()`'s cleanup step ever ran, a
pending manual migration was silently taking down the entire sync, not
just failing to populate one column. `upsert()` now detects this specific
error, strips the missing column from every row for that table, and
retries - the sync stays fully functional whether or not the migration
has landed, and the moment it has, this stops triggering with no further
code change needed. This was caught from a real user-reported
`scrape-large.yml` failure (run 35744137997) - the scraping/git-merge
pipeline underneath was fine throughout (alo.bg's history grew from
87,979 to 90,159 listings with zero data loss); only the Supabase sync
step was broken.

## 23. homes.bg listing `homes_208381` (and possibly others): price oscillates wildly between two exact values across scrape history - FIX APPLIED (2026-09-23) - backfill for 2 of 3 known-corrupted IDs done, 1 left open pending live verification

Found by Dessy while testing backlog item 17's price/status history chart,
confirmed and reproduced independently by Missy during PR #200's review -
not a one-off glitch.

**Confirmed facts:** `homes_208381` ("Къща, 480m², с.Богдан, Пловдив",
https://www.homes.bg/offer/kyshta-za-prodazhba/kyshta-480m2-plovdiv-s.bogdan/hs208381)
has 23 `price_history` entries (2026-08-25 through 2026-09-21+) that
alternate almost every single scrape between exactly **€233,000** and
**€1,227,520** - 22 of 22 transitions are flips between those two exact
values, not a gradual drift or a single bad read. The current
`price_eur`/`price_per_sqm` (233000 / 485) are internally consistent with
the listing's own 480m², so €233,000 looks like the real figure;
€1,227,520 doesn't correspond to any clean unit-conversion or
decimal-shift of €233,000 (ratio ≈5.27 - not a BGN/EUR mixup or a stray
decimal).

**Not yet investigated further** - needs live network access to
homes.bg's actual listing page (blocked from this sandbox's egress
proxy, same documented limitation as Missy's daily audit routine) to
determine whether: (a) this is a scraper-side bug (e.g. occasionally
grabbing a neighboring card's price off the search-results grid instead
of this listing's own), or (b) homes.bg's own page genuinely alternates
between two displayed prices (e.g. cash vs. financed, with/without VAT)
and the scraper is faithfully capturing both. Whoever picks this up
should check the real live page first before assuming either explanation.
Likely a `scraper_homes.py` bug given the pattern (a clean, repeated
2-value flip looks more like "reading the wrong DOM element on
alternating scrapes" than a real site behavior), but not confirmed.

**UPDATE 2026-09-23 (Scrapy) - root cause confirmed, it's (a) not (b).**
`scraper_homes.py`'s `parse_offer()` builds the tracking ID as
`"homes_" + str(offer["id"])`, dropping the two-letter type prefix
(`hs`/`as`/`lp`/`la`) that homes.bg's own URL scheme uses to scope its
numeric IDs - those IDs are only unique **within** a type, not globally.
Two entirely unrelated listings of different types (e.g. an `hs` house
and an `lp` land parcel) can share the same numeric ID and collapse onto
one tracking key, silently overwriting each other's **entire record**
(not just price) on alternating scrape runs whenever the scraper happens
to see one type's listing then the other's under the same collapsed ID.

Confirmed directly via git history for `homes_208381`: commits
`4102c12`/`cf815b1` -> `1a2bbef` show a real flip between a Varna land
parcel and the Plovdiv house described above - not a price-only glitch,
the whole record (title, location, sqm) flips too. A full-dataset scan
found 2 more confirmed cases with the same signature: `homes_209031`,
`homes_205536`. Broader currently-invisible collisions across the 4 type
sequences (`hs`/`as`/`lp`/`la`) were flagged as a risk but not fully
audited - only these 3 have been directly confirmed.

**Fix recommended (not yet applied):** incorporate the type prefix into
`parse_offer()`'s tracking ID (e.g. `"homes_" + offer["type_prefix"] +
str(offer["id"])`) so IDs are scoped the same way homes.bg itself scopes
them. This is a go-forward fix only - it does **not** repair the already-
corrupted history for `homes_208381`/`homes_209031`/`homes_205536` (and
any undetected others), which will need a separate one-time backfill/
split pass to separate the interleaved records back into two distinct
listings per collided ID, once the new ID scheme exists to split them
under.

**FIX APPLIED (2026-09-23).** `scraper_homes.py` now builds the tracking
ID via `build_tracking_id()`, which reads the real 2-letter type prefix
straight off the offer's own `viewHref` (ground truth, not guessed from
our `category`/`type_id` bucketing, which can't tell `LandParcel` from
`LandAgro` since both map to the same `"land"` bucket) - both places that
built an id had the bug and both are fixed (`parse_offer()` and the
pre-parse "already seen this run" dedup check in `scrape_slice()`, which
would otherwise still cross-type-collide within a single run). Checked
the rest of the codebase for anything assuming the old unprefixed
`homes_<digits>` shape (`sync_to_supabase.py`, `index.html`,
`detect_relistings.py`, `merge_history_conflict.py`) - none parse or
regex the tracking id itself, all treat it as an opaque string, confirmed
by running `sync_to_supabase.py`'s row-building against the fixed+split
data with no crash. Full evidence, the exact commits behind each split,
and why `homes_209031` was deliberately left unsplit are in
`docs/decisions.md`'s 2026-09-23 entry.

**Backfill: DONE for `homes_208381`/`homes_205536`, still open for
`homes_209031`.** The first two had unambiguous, mechanically-confirmed
dual full-record evidence in `main`'s real git history (two cleanly
distinguishable records each, with their accumulated `price_history`
splitting perfectly and losslessly between the two records' exact,
non-overlapping prices) and were split into `homes_hs208381`/
`homes_lp208381` and `homes_hs205536`/`homes_lp205536` via
`backfill_split_homes_id_collision.py` (kept in the repo, run once).
Post-split, both listings show zero real price drops - the "oscillation"
was entirely a collision artifact. `homes_209031` has no second
full-record variant anywhere in local history to split against (only a
second price value, with nothing showing what listing it belonged to) -
left untouched rather than guessed; needs live homes.bg access to check
`as209031`/`lp209031`/`la209031` directly before it's safe to split.
Supabase itself isn't touched by this backfill (no DB credentials in this
environment) - the next real `sync_to_supabase.py` run will pick up the
id change and should clean up the 2 stale rows via its existing
delete-stale logic; whoever runs it next should verify that.

**Correction (Missy's PR #234 review, 2026-09-23):** the split above had
silently dropped `homes_208381`'s most recent real snapshot and mistagged
`homes_hs208381` as `"removed"` when it's actually `"active"` -
`backfill_split_homes_id_collision.py` was sourcing both files' new
entries from `leads_homes.json`'s shorter, already-deduped
`price_history` instead of `history_homes.json`'s own complete
`snapshots` list. Fixed and re-verified losslessly against the real
`history_homes.json` snapshot counts (24 for `homes_208381`, 8 for
`homes_205536`, both now fully accounted for); `homes_205536`'s split was
unaffected (its two source lists were already identical). Full detail in
`docs/decisions.md`'s matching correction entry.

---

## 24. imot.bg: `city` field wrongly wins over a listing's own area text when a settlement imot.bg's own site groups under a different city hasn't been geocoded yet - RESOLVED (2026-09-23)

Found by Placy while checking whether the Cherven Bryag/"град Ловеч"
oddity Missy flagged (item 22's investigation) is a systemic pattern.
Full detail, evidence and methodology: `docs/decisions.md`'s 2026-09-22
and 2026-09-23 entries.

**Status: resolved.** The general "trust `area` over `city_key` when
`area` resolves via `BG_MUNICIPALITY_TO_OBLAST`" fix originally floated
as the cheaper option was checked against real data and rejected - it
would have flipped 166 currently-ungeocoded imot.bg listings to a wrong
oblast (imot.bg's own URLs prove several, e.g. `grad-vratsa-samuil` and
`grad-sliven-novo-selo`, are real in-city quarters coincidentally named
after distant municipality seats, not misfilings). Shipped instead: a
single, exact, two-sided-confirmed `(city, area)` override
(`IMOT_CITY_AREA_OBLAST_OVERRIDE` in `sync_to_supabase.py`) for only
`("Ловеч", "Червен бряг") -> "pleven"`, the one case with both real-
coordinate confirmation and imot.bg's own URL text agreeing. On branch
`placy/location-allocation-fixes` (pushed, not yet merged/reviewed).

**Confirmed, narrow, currently self-healing but order-dependent:**
`scraper_imot.py` tags every listing's `city` field from which of its 25
`CITY_SLUGS` query pages produced it, not from the card's own text -  but
imot.bg's own `grad-lovech` page itself returns listings physically in
Червен бряг (Pleven oblast, ~55km from Lovech; pre-1999 okrug legacy,
one listing's own URL literally encodes `obshtina-lovech`, imot.bg's own
site data, not a scraper misread). `listing_oblast_key()` checks
`lat`/`lng` first, then `city_key` (always resolves for imot.bg since
`city` is always one of the 25 known-good names) - the listing's own
`area` text is never reached as a fallback. A simulated *ungeocoded*
Cherven Bryag/Ловеч listing run through the real, unmodified
`listing_oblast_key()` resolves to `lovech` (wrong) instead of `pleven`.
All 13 currently-committed Cherven Bryag/Ловеч listings already have real
lat/lng (from `backfill_geocode_imot.py` having run), so they currently
show correctly - but a freshly-scraped one would show wrong until the
geocode backfill catches up.

**Scope beyond Cherven Bryag: checked, mostly not the same bug.**
Cross-referencing every (queried city, area text) pair across
`data/leads_imot.json` against `oblast_key_from_municipality()` found 54
pairs / 1,641 listings where the area text resolves to a different
oblast than the queried city - but sampling showed most are false
positives from ordinary Bulgarian neighborhood-name collisions (e.g.
"Гоце Делчев" under Sofia-queried listings is a real Sofia жк
coincidentally sharing a name with the actual town in Blagoevgrad oblast,
confirmed by its own real coordinates landing 2.1km from central Sofia,
not 130km away). Only Cherven Bryag/Ловеч had both real-coordinate
confirmation and imot.bg's own URL-text claim agreeing as genuine
misfiling.

**Recommended fix, not yet implemented (needs `sync_to_supabase.py`, left
for whoever picks it up after item 22 settles to avoid the same-file
collision):** don't let `city_key` win over `area`-derived resolution
unconditionally for imot.bg specifically when the two disagree and
`area` resolves via the hand-verified `BG_MUNICIPALITY_TO_OBLAST` (not
the larger generated table, to limit false-positive risk) - or, cheaper
and lower-risk, just prioritize closing the geocoding backfill gap so
`lat`/`lng` (which is already correct and already wins) covers these
listings sooner. A blind area-text override is **not** safe without
per-listing geocoding to rule out same-city name collisions like Гоце
Делчев above - demonstrated concretely, not just a theoretical risk.

## 25. Two small settlement/gazetteer gaps found incidentally in `sync_to_supabase.py` - DONE (2026-09-23)

Found by Placy while auditing `sales.bcpea.org`'s unresolved listings
(see item below and `docs/decisions.md`'s 2026-09-22 entry for the full
per-portal audit these came out of). Both fixed - see
`docs/decisions.md`'s 2026-09-23 entry. On branch
`placy/location-allocation-fixes` (pushed, not yet merged/reviewed).

1. **`Гълъбово` missing from both settlement tables.** A real, notable
   municipality-seat town (Stara Zagora oblast, the Maritsa Iztok power
   complex) resolves to `None` from both `BG_MUNICIPALITY_TO_OBLAST` and
   the generated `BG_SETTLEMENT_TO_OBLAST`/
   `data/bg_settlements_to_oblast.json` - a genuine gap, not a documented
   ambiguous-name exclusion (`oblast_key_from_municipality("Гълъбово")`
   returns `None` outright). At least one real `sales.bcpea.org` listing
   ("Парцел, Гълъбово") is left unresolved because of this.
2. **`bcpea_settlement_from_title()` doesn't handle the "Други" category
   label.** `bcpea_settlement_from_title("Други, Брезово")` returns
   `None`, even though "Брезово" itself resolves fine
   (`oblast_key_from_municipality("Брезово")` -> `plovdiv`) once
   extracted - the function's category-prefix handling just doesn't cover
   that one label.

Both fixed 2026-09-23: `Гълъбово` added to `BG_MUNICIPALITY_TO_OBLAST`'s
Stara Zagora section; `bcpea_settlement_from_title()` now strips the
"Други" category label the same way it strips every real type label,
without changing `bcpea_type_match()`'s own (already-correct) "other"
category output for these listings. Verified:
`sales.bcpea.org`'s unresolved-to-oblast count dropped from 281 to 242.

## 26. alo.bg: stale `"Bulgaria"` placeholder area value still in committed data (12,501 rows), scraper code already fixed - DONE (2026-09-23)

Found by Placy during the platform-wide allocation-gap census (see
`docs/decisions.md`'s 2026-09-22 entry for full methodology).

`scraper_alo.py` used to write `area, city = "Bulgaria", None` when its
`LOCATION_RE` missed a card - already fixed in the scraper's own code
(now writes `None`/`None`, per the function's own inline comment; not
this item). What's left is **stale data from before that fix**: 12,501
rows in the currently-committed `data/leads_alo.json` (and the matching
`"latest"` records in `data/history_alo.json`) still carry the literal
string `"Bulgaria"` as `area`, all with `city` exactly `None` - the old
code's exact signature, confirmed not a new instance of the bug. Checked
for a look-alike first: 15 separate rows have `area == "България"`
(Cyrillic) with a real `city` set - sampling confirmed these are a
genuine street name (`бул. България`, Bulgaria Boulevard, Veliko
Tarnovo) correctly parsed, not the bug; excluded from scope.

Of the 12,501: 5,009 already have real lat/lng from a coordinate backfill
and resolve to the correct oblast today despite the stale text (only the
user-visible `area` label/filter value is wrong - this is exactly the
kind of junk value that would show up as a bogus entry in item 22's new
`area_key`-grouped dropdown); 4,327 still have no lat/lng and are
counted in item 24-adjacent audit's "alo.bg 4,394 unresolved" figure.

**Fix applied 2026-09-23**: for every record where `area == "Bulgaria"`
(Latin spelling, exact) AND `city is None`, set `area` to `None` (nothing
else touched - does not change oblast/city resolution logic, just
removes a known-false raw string). Exactly 12,501 records fixed in both
`data/leads_alo.json` and `data/history_alo.json`, matching the
documented count exactly; verified zero remaining stale placeholders
afterward. Two prior sessions had this fix written and dry-run-verified
but were blocked by this sandbox's own permission system on the write;
this session's writes to both files succeeded on the first attempt (see
`docs/decisions.md`'s 2026-09-23 entry for this session's broader
experience with that classifier's intermittent, non-deterministic
blocking). On branch `placy/location-allocation-fixes` (pushed, not yet
merged/reviewed).

## 27. Full-platform "resolved but wrong" allocation audit: 1,358 listings had a confidently-wrong oblast (not just an unresolved one), two root causes found and fixed - REVIEWED BY MISSY, ONE REGRESSION FOUND AND FIXED - DONE (2026-09-23)

**Reviewed by Missy before merge - found one real regression and one
missed cluster, both corrected (see docs/decisions.md's 2026-09-23
"Missy's review" entry for full detail):** 13 alo.bg listings
(Божурище/Самоков/Сливница, real Sofia Province municipality seats) had
genuinely-correct coordinates wrongly nulled by this pass's own
correction rule, which should have excluded them the same way
Боровец/Обзор/Бенковски were - restored their real pre-correction
coordinates. A separate 4-listing homes.bg cluster
(Сопот/Банско/two-Бяла-records sharing one bad coordinate resolving to
Varna) met this item's own correction criteria but was missed - now
corrected. Also fixed a pre-existing "29 vs 30" `BG_CITIES` count
inaccuracy repeated in this item's own writeup, and a misattributed
"166" figure in `sync_to_supabase.py`'s `IMOT_CITY_AREA_OBLAST_OVERRIDE`
comment. Everything else Missy checked (items 24, 25, 26, and the bulk
of this item and item 28) verified cleanly against real committed data -
no further changes needed there.

Direct escalation from the user: the unresolved-to-oblast count (item 4's
5,628/305,065) only catches listings that fail to resolve at all, not
ones that resolve *confidently to the wrong place*. Full detail, every
cluster, exact numbers, and the exclusions checked individually (Cherven
Bryag, Боровец, Обзор, Бенковски) are in `docs/decisions.md`'s 2026-09-23
entry - summary:

**Method**: for every listing with both `lat`/`lng` and a `city` field
that's an exact match to one of the 30 hand-verified `BG_CITIES`, compared
that city's real oblast against `oblast_key_from_latlng(lat, lng)`.
Found 1,358 disagreements, clustering into large groups sharing one
near-identical coordinate - the fingerprint of a shared bad value, not
noise.

**Two confirmed root causes, both fixed:**
1. `backfill_geocode_homes.py` built its geocode query as `f"{area},
   България"` - dropping city entirely, despite its own comment claiming
   it matched `scraper_homes.py`'s query shape (false - that one includes
   the full "area, city" text). Real-world ambiguous names duplicated
   across multiple Bulgarian towns (Широк център, жк. Тракия, жк. Христо
   Ботев, к.к.Слънчев Бряг) were geocoded with no disambiguating context.
   Fixed to reconstruct `area, city` before querying.
2. `city_key_from_name()`/`city_key_from_name_prefix()` stripped a
   trailing "област" suffix and matched what's left against the 30 city
   names - wrong specifically for "София област" (Sofia Province, a real,
   separate oblast), which was collapsing into Sofia city itself. Every
   other `BG_CITIES` name's own oblast shares that city's exact name, so
   this collision is Sofia-only. Confirmed 67 imoti.bg listings tagged
   `city="София област"` were affected. Fixed with a Sofia-specific
   guard.
3. A third, larger cluster (imoti.net, 654 listings, `extract_coords_
   imoti_net()`'s HTML coordinate extraction) and a fourth (Братя
   Миладинови/Родина 2, wrong even when the geocode query is city-
   qualified - a genuine external-geocoder mismatch, not a query-
   construction bug) were found and the affected data corrected, but
   their own root cause was NOT fixed at the code level this session -
   see item 28 below.

**Data correction**: nulled `lat`/`lng` for 1,253 of the 1,358 listings
(city/area left untouched, so the existing city-text fallback resolves
them correctly) across all 6 affected portals' `leads_*.json`/
`history_*.json` files. Excluded and individually verified, not blindly
filtered: the 13 Cherven Bryag/Ловеч imot.bg listings (already correct
via item 24's fix - nulling would have regressed it), "Боровец" (9,
opposite direction - the coordinate is likely right, the loose `city`
text is the imprecise one), "Обзор" (4, a boundary-polygon edge case, not
a bad geocode - see item 28), "Бенковски" (10, genuinely ambiguous
nationwide - left unresolved per the existing "Бяла"/"Средец"
precedent).

**Verified impact**: per-portal city-vs-coordinate mismatches (using the
strict "city is one of the 29 majors" check) dropped imoti.net 663->9,
homes.bg 286->18, imot.bg 245->13 (all correctly-excluded Cherven Bryag),
olx.bg 245->10 after a same-day follow-up pass (see item 28 - 3 more
corrected individually: 2 more Цветница, 1 Сарая), alo.bg roughly flat.
On branch `placy/location-allocation-fixes` (pushed, not yet merged/
reviewed).

**Note on methodology**: an earlier, looser check (comparing the *full*
text-based `listing_oblast_key()` resolution, including `area`-derived
matches, against the coordinate) initially suggested 169 remaining olx.bg
mismatches - that number was misleading, an artifact of the looser
check's own false-positive rate (the same "real quarter name coincides
with a distant municipality seat" pattern already demonstrated for item
20's Гоце Delchev/Самуил/Ново село cases, where the *coordinate* is
actually right and the area-text match is the misleading signal). The
strict city-field-only check found only 10 genuine remaining candidates
for olx.bg, not 169 - worth remembering before trusting the looser
check's count on any future portal without doing the same individual
verification.

## 28. Follow-ups from item 27

Dispatch for whoever (Placy or otherwise) picks up what's left:

1. **`extract_coords_imoti_net()`'s real root cause** (`geo_utils.py`) -
   **still open, deliberately skipped per explicit direction** (2026-09-23):
   654 imoti.net listings' bad coordinates were corrected as data, but the
   extraction regex itself (a bare first-match `.search()` for
   `"latitude"/"longitude"` anywhere in a detail page's HTML, not scoped
   to the listing's own coordinate block) was not fixed - needs live
   network access to imoti.net's real page HTML (blocked by this
   sandbox's egress proxy, confirmed again via both `WebFetch` and
   `curl`) to see what's actually being matched before touching it
   safely. Do not guess a fix without that.
2. **olx.bg's remaining mismatches - DONE (2026-09-23).** The initial
   "169 remaining" figure was itself a measurement artifact (see item
   23's methodology note above) - the real, strict count was only 10,
   of which 3 were corrected individually (2 more "Цветница" sharing the
   exact already-confirmed-wrong coordinate, 1 "Сарая" independently
   confirmed via web search against its real ~43.835N/25.942E Ruse
   location), and the remaining 7 (5 "Бенковски", genuinely ambiguous;
   2 Ловеч/Червен бряг, correctly excluded) are not bugs.
3. **`data/geocode_cache.json` cleanup - DONE (2026-09-23).** Removed all
   18 confirmed-wrong entries this session's data corrections had already
   found (Братя Миладинови, Родина 2/3, Цветница, Бизнес хотел, Люлин 7,
   Сарая - wrong even city-qualified; Широк център/к.к.Слънчев Бряг/
   Тракия/кв. Каменица/Христо Ботев - the bare no-city queries the now-
   fixed `backfill_geocode_homes.py` bug produced). Chose deletion over a
   manual override table for simplicity and because most of these entries
   don't have an authoritative "correct" replacement value this session
   could verify live to hardcode instead - a future live geocode attempt
   at least has a chance now instead of a guaranteed-wrong cached hit.
4. **imoti.bg regression check - DONE (2026-09-23), confirmed legitimate,
   not a regression.** The 4->6 unresolved-count change after the "София
   област" fix: 4 of the 6 (`city="Ателие"`, a genuine unrelated pre-
   existing scraper data-quality issue - a property-type word landing in
   the city field, not a location bug) were already unresolved before
   this session's fix. The other 2 are new and expected:
   `city="София област"`/`area="с.Злокучене"` and .../`"с.Василовци"` -
   both real Sofia-Province villages (confirmed via web search: Злокучене
   is in Samokov municipality, Василовци in Dragoman municipality) that
   simply aren't in either settlement gazetteer yet (a genuine, pre-
   existing item-4-task-2-class coverage gap, not new) - and, for
   Василовци specifically, a genuinely ambiguous name (a second, distinct
   "Василовци" also exists in Montana oblast per Wikipedia's own
   disambiguation), so it should NOT be mechanically added to
   `BG_MUNICIPALITY_TO_OBLAST` without the same per-name ambiguity care
   as "Бяла"/"Средец" - correctly left unresolved rather than guessed.
   Net effect of the Sofia fix: these 2 listings moved from confidently
   WRONG (`sofia_grad`) to honestly UNRESOLVED - the right direction.
5. **"Обзор" (Burgas coastal town) resolving to Varna oblast - DONE
   (2026-09-23, Placy), on branch `placy/obzor-oblast-fix`, not yet
   merged/reviewed.** Confirmed the real cause and the real count against
   current committed data: exactly 4 alo.bg listings
   (`alo_11340310`/`alo_11030238`/`alo_11027413`/`alo_11040886`, all
   `city="Бургас"`, `area="Обзор"`) still resolve to `varna` today - the
   backlog's original "4 listings" estimate held. Same underlying root
   cause as the already-fixed Близнаци case (item 4 task 4) - ordinary
   coastline-simplification of `data/bg_oblast_boundaries.json`'s Varna/
   Burgas border near Обзор - but the opposite failure shape: Близнаци's
   real point fell just *outside* the correct oblast's simplified polygon
   and came back unresolved (fixed by `NEAR_BOUNDARY_TOLERANCE_DEG`'s
   fallback, which only runs when the strict test finds nothing); here
   the real point (e.g. 42.8445, 27.882196 - confirmed correct via the
   listing's own title text, "...директен достъп до плажа Обзор, област
   Бургас") falls just *inside* Varna's own simplified polygon by the
   strict point-in-ring test, so that fallback never gets a chance to run
   - the strict test already "succeeds", just for the wrong oblast.
   Hand-verified the point sits ~0.0038deg inside Varna's polygon edge
   but only ~0.0062deg outside Burgas's - both well within ordinary
   simplification/GPS noise range, and both the listing's own `city`
   ("Бургас", one of the 30 hand-verified `BG_CITIES`) and `area`
   ("Обзор", a real, unambiguous Burgas-oblast settlement) independently
   agree it's Burgas. Fixed with a narrow, coordinate-keyed
   `GEO_OBLAST_OVERRIDE` dict in `sync_to_supabase.py` (checked first
   thing in `oblast_key_from_latlng()`), matching the same "small,
   evidence-confirmed, not a general rule" discipline already established
   for `IMOT_CITY_AREA_OBLAST_OVERRIDE` - not a general "prefer text over
   geo near borders" rule, which would risk regressing every other
   correctly-resolved near-border geo match project-wide. No raw listing
   data needed correcting (lat/lng/city/area were already all correct -
   only the derived oblast resolution was wrong, computed fresh at sync
   time, not stored in `data/leads_*.json`/`data/history_*.json`).
   Verified: all 4 listings now resolve to `burgas`; re-ran the fix
   against every "Обзор" listing across all 8 portals' committed data
   (354 total, 102 correctly resolving to `burgas` via geo, the rest via
   city/area text as before) with zero remaining `varna` mismatches;
   confirmed no regression to the Близнаци cluster or Varna/Sofia city-
   center points; `python3 -m pytest tests/` passes (11 passed, none of
   which cover this path directly - no existing test suite for
   `sync_to_supabase.py`'s geo-resolution functions).

---
---

## Open questions - uncertain Bulgarian-data substitutes, do not build until resolved

Flagged by Nosy as genuinely open, not confirmed either way. Each blocks
only the specific sub-feature named, not the whole item it belongs to:

- **Last Sold / transaction-price data** (real, not asking, prices) -
  would come from Имотен регистър (Registry Agency) / Кадастър, but
  unlike UK Land Registry it's not known whether transaction-price data
  is openly scrapable in Bulgaria. Blocks: the *true* "Last Sold Data"
  histogram in item 15 (asking-price version ships regardless), the
  "Last sold(Land reg)" count pill in item 15's Comparables view, and the
  Market Data hub's "Last Sold Map" tile in item 16.
- **Price vs Income tile** (item 16) - Bulgaria's NSI does publish
  regional income data publicly, but granularity match to this tile's
  needs is unverified.
- **Census Data overlay** (item 20) - NSI publishes census data; unknown
  whether it's available at fine enough geocoded granularity/overlay
  form.
- **Crime data map** (item 20) - no known equivalent to UK police.uk's
  public, fine-grained geocoded crime dataset for Bulgaria.
- **Planning Applications** (items 15/16) - no known equivalent to the UK's
  standardized, often API-accessible per-council planning-application
  data in Bulgaria.
- **Bulgarian energy-efficiency certificate as an EPC substitute** (items
  6, 7, 8's filters) - Bulgaria has its own mandatory energy-certificate
  scheme (A-G-ish bands), but whether imotenradar's scraped source
  portals actually expose it is unknown. Omit the field entirely until
  confirmed rather than faking it.
- **PLO (Purchase Lease Option) strategy** (item 18) - relies on a UK
  leasehold/option-contract convention; unclear applicability under
  Bulgarian contract law, needs legal confirmation before a keep/drop
  call. 2026-09-23 research (`docs/deal-calculator-formulas.md` section
  11): Bulgaria's closest native mechanism, the preliminary contract
  (предварителен договор), is a promise to complete a sale, not a
  lease-with-a-purchase-option - it doesn't grant the buyer occupation
  or income rights the way a PLO's lease component does. No established
  Bulgarian equivalent to the UK PLO structure was found, and this
  research couldn't confirm how enforceable a standalone lease+option
  contract would be if a seller tried to walk away mid-option. Still
  needs an actual Bulgarian real-estate lawyer's confirmation, not more
  desk research - no formula has been written for this strategy.

## Confirmed drops - no Bulgarian substitute, not backlog items

Explicitly not being built, per Nosy's spec: CT Band (Council Tax Band),
Owner/ownership-history lookup (UK Land Registry / Companies House),
Registered Lease years remaining, Restrictive covenant, Title number
lookup (UK Land Registry concepts - Bulgarian property is overwhelmingly
freehold-equivalent), "Last building use known", HMO Article 4
flag/layer/tile (UK planning-law specific), LHA Rates panel (UK
benefits/rent-cap scheme), Title Split - Hold/Sell strategy,
Freehold/Leasehold tenure toggle (Bulgarian tenure is effectively always
freehold-equivalent), "Low EPC"/"Short Lease" letter-campaign situation
types, Stamp Duty as a field (replaced by a Bulgarian transfer-tax %
default instead, see item 19), and the UK-broker-specific "Get Finance"
partner tab (lowest priority of all 7 listing-detail tabs per spec;
revisit only as a monetization feature if a Bulgarian mortgage-broker
partnership is ever pursued - not part of the current build).

## Gaps in Nosy's spec - would need a follow-up capture, not blocking

Noted so nothing is silently assumed later: the public marketing/pricing
page, the sign-up/onboarding flow, any mobile/responsive view (all 34
source screenshots were desktop), alert-email behavior (vs. in-app
notifications), exact export file contents (CSV/PDF/etc.), validation/
error-state screens beyond the two captured, and any expanded
Due-Diligence chevron panel were all requested but not supplied. None of
these block starting items 13-21; revisit if/when they turn out to matter
for a specific item.

## Parked - do not start

- **Rental scraping.** Investigated: under 400 usable listings nationwide
  (imoti.bg ~394, bazar.bg ~444 but those are flatshares/rooms, not whole
  properties) - not enough for reliable yield. Revisit only if imoti.net's
  or imot.bg's real listing counts become readable (their rental sections
  exist but the count couldn't be extracted last time).