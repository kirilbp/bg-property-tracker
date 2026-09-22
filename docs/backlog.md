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

## 6. Site is very slow to load/refresh - slice 1 DONE, MERGED - slice 2 open - URGENT

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

**Connects to, but is not solved by, backlog item 7** (Supabase Pro
follow-ups): the code comment explaining why a full-table client load was
accepted in the first place cites free-tier connection-pool exhaustion as
the reason a fuller per-listing (`listing_sources`) load was cut back -
i.e. this design predates the Pro upgrade and was shaped around the old
500 MB/connection-pool constraints item 7 already flags for revisiting.
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
exact file (`index.html`) for backlog item 9's listing-detail redesign -
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
   table (backlog item 18) - `listingAreaKey()`'s existing
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
(item 18) - so it's not attempted here; filed as a follow-up, not
solved.

**Verified, not assumed:**
- A Node `vm` harness loading the real, unmodified `index.html` script
  (same established pattern as the item 18 entry) confirmed: the bulk
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

**Slice 2 remains open**: real server-side filtered/paginated Supabase
queries and `findComparables()`'s in-memory radius-search redesign - not
attempted, deliberately scoped out of slice 1. Whoever picks it up should
note `Prefer: count=exact` against `merged_listings` hits Postgres's
statement_timeout live (confirmed, error 57014) - any pagination UI
needing a total result count will need a different approach (approximate
count, a capped query, or skipping total-count display), not
`count=exact`.

## 7. Supabase Pro plan follow-ups - PENDING

Free-tier limits are gone, daily backups are running. Revisit anything
designed around the old 500 MB limit (retry/backoff tuned for storage-
related 500s, any code that assumed a small dataset for cost reasons).

## 8. Motivation score rework - DONE

Shipped in PR #162: 5-component formula (relisted, distinct reductions,
size of drop, days on market, below area average), rescale option A when
area-average is unavailable, Hot/Warm thresholds recalibrated to 40/15
against real data distribution. Confirmed live.

## 9. Listing detail page redesign: multi-portal badge, price/status history, keyword tags - Nosy spec, highest investor value - CORE SCOPE DONE, MERGED (2026-09-22, Dessy)

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
look. A full site-wide reskin against the same palette is item 17's
scope, not redone piecemeal here.

**Not included here (see "Confirmed drops" below):** CT Band, Owner
(Land Registry), Registered Lease/Restrictive covenant/Title number,
"Last building use known", HMO Article 4 flag, EPC badge (until/unless a
Bulgarian energy-certificate data source is confirmed - see "Open
questions").

## 10. Saved searches ("Lead Generators") + home dashboard + Deal Pipeline (kanban) - DONE, MERGED (2026-09-22, Dessy)

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
    - same already-flagged gap as item 9's Agent panel (no scraped listing
    carries an agent/agency name or contact field) - the toolbar says so
    explicitly instead of showing a control that can't do anything.
  - **Design-guidelines judgment call**: the spec's own card description
    calls for colored status/price-change *ribbons* and a dense 2x3
    icon-grid of stats - both are `docs/design-guidelines.md` section 9's
    explicitly named anti-patterns (items 1-2). Built the same *content*
    the spec asks for, presented as small-caps muted text labels and plain
    inline facts instead, matching the restrained treatment item 9 already
    established for the listing detail page - not a silent improvisation,
    the guidelines document directly instructs this substitution.
- **Design-scope note**: the new/redesigned surfaces (Lead Generators
  gallery, the three new dashboard widgets, the whole Pipeline board) draw
  on `docs/design-guidelines.md`'s warm ivory/brass palette and Playfair/
  Inter type pairing - the same CSS variables item 9 introduced. Shared
  chrome those surfaces still reuse (the generic `.modal-*` classes, the
  sidebar nav) intentionally keeps its existing blue-accented look, same
  scoping call item 9 made - a full site-wide reskin is item 15's Pipeline
  sub-item name aside, really item 17's job, not repeated piecemeal here.
- **Storage**: `pipelineStages`/`pipelineTags`/`pipelineDeals` are three
  new plain localStorage keys, following the existing no-login,
  this-browser-only pattern used by `leadGenerators`/`savedListingIds`/
  `reminders` - not flagged as a concern, this is what the dispatch asked
  for by default, but noting it plainly per the standing instruction to
  flag rather than silently decide if a stronger reason existed (none did).
- **Not done**: Missy's review, and a real PR to `main` (branch is pushed,
  PR still to be opened as part of this same pass).

## 11. Comparables & Area Data analytics (own-data market stats + BTL stress test) - DONE, MERGED (2026-09-22, Dessy)

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
Missy directly - same documented gap as item 18's dispatch), not yet
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
    Card/Table/Map/Export view toggle reusing item 10's own `.pl-*`
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
  `docs/design-guidelines.md`**: reused item 10's `.pl-*` component
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

## 12. Market Data hub (portfolio-level aggregate tiles) - IMPLEMENTED, AWAITING MISSY'S REVIEW (2026-09-22, Dessy)

Reuses item 11's aggregation work at a broader, cross-listing scope. Spec
section 7. Fully replicable, built purely from imotenradar's own scraped
listing history (price, status, time-on-market, agent) aggregated by
area: Strategy Heat Map, Postcode Performance -> city/quarter Performance,
Market Live Map (Yield/Asking Prices/Time On Market/Demand), Adverts
Evolution (stock changes: Available/STC-equivalent/Removed over time),
Agent Properties (all listings by a given agent). Sequence after item 11
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
  exists to compute it from (same gap item 11's Area Data tab already
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
  file directly (not just trusted item 9's earlier finding): no agent/
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
and every CDN this app loads from - same approach item 11 used). Confirmed:
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
item 22's stale alo.bg `area == "Bulgaria"` placeholder rows (still
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
item, self-resolves once item 22's cleanup lands) - only the stated
mechanism was invented rather than checked; corrected here rather than
left standing.

**One design-scope judgment call**: the hub's own tabs reuse the `.pl-*`/
`.cmp-*` design tokens/components item 11 already established (cards,
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

## 13. Send Letters / motivated-seller outreach campaigns

Direct-mail-to-owner outreach workflow (spec sections 5's "Send Letter"
tab and section 6's full campaign manager). Flagged by Nosy as "fully
Bulgarian-replicable, high-value workflow" and a genuinely portable
feature if imotenradar wants to pursue a deal-sourcing angle, not just an
aggregator - but it's a materially bigger scope than items 9-12 (mail-merge
templating, a reverse address lookup, and an actual physical-mail send
integration/partner, none of which imotenradar has any of today), so it
sits after the smaller, faster-to-ship analytics items despite the high
value rating.

- Campaign management: Draft/Active campaign tables, batch delivery
  tracking, response tracking.
- Letter Designs: situation-keyed template bank tied directly to signals
  imotenradar's scrapers already detect - Back on Market, Price Reduced,
  Withdrawn, Long Time On Market, Multiple Agents, plus General and a
  free-form "create your own". These should trigger off the same
  motivation-score signals already computed (item "Motivation score
  rework", done). Drop the "Low EPC" and "Short Lease" situation types
  (UK-only, no BG relevance - see "Confirmed drops").
- Reverse address lookup ("Property Lookup"): so an inbound call from a
  seller can be matched back to the letter/campaign that reached them.
- Requires deciding a real physical-mail send path (partner/API) before
  the "Active campaigns" half is buildable - flag this as a dependency
  to resolve (likely a design-fork decision) when this item is picked up.

## 14. Deal Calculator (investment strategy modeling) - needs formula work before building

Spec section 8. The overall mechanism (pick a strategy -> get a
strategy-specific calculator -> save as a reusable template or link to a
property) is a strong, fully replicable pattern. But per the spec itself,
the actual input fields and math behind every strategy's output metrics
were never shown/captured (INFERRED throughout) - this needs either a
further Nosy capture pass of a populated calculator or independent
financial-modeling work before a builder can implement it, so it's
sequenced after the items above rather than blocking on them.

- Replicable with Bulgarian-market defaults once formulas are known: BTL,
  BRRR, BTSA, BRSAR, FLIP, R2R, R2SA, COM2RESI-TOSELL, Assisted Sale.
  Whether R2R/serviced-accommodation strategies are common/legal enough
  in the Bulgarian market to be worth building is a business call for
  whenever this item is picked up, not a technical blocker.
- Drop: Title Split - Hold/Sell (relies on UK Land Registry's split-title
  registration, no known BG equivalent).
- Open question, needs Bulgarian legal confirmation before deciding:
  PLO (Purchase Lease Option) - see "Open questions" below.

## 15. Preferences / settings to support items 9-14

Spec section 9. Mostly small, fully-replicable settings screens that
exist to back the features above rather than stand alone - sequence each
sub-tab alongside the feature it configures rather than building all of
Preferences as one block:
- Display (surface/distance units - note Bulgaria already uses metric
  natively, so the UK mile/km toggle complexity isn't even needed),
  Search Results (motivation-indicator thresholds - already a close
  match to imotenradar's own motivation-score fields), Lead Generator
  defaults, Pipeline (stage + tag configuration - ship with item 10),
  Notifications (new-lead-generator-count / status-change mechanics -
  ship with item 10), Deal Stacker defaults (BG mortgage-rate defaults -
  ship with item 11's Stress Test), Calendar integration, Letters defaults
  (ship with item 13), Deal Calculator Templates defaults (replace UK
  Stamp Duty default with a Bulgarian transfer-tax % default - ship with
  item 14).

## 16. Map tab additions

Spec sections 4 and 5's Maps tab. Street View, Satellite, and Amenities
(POI) layers are fully replicable generic map layers - low effort, can
ship alongside item 9. The one genuinely good UK-concept-with-a-real-BG-
substitute is worth calling out on its own: **cadastral map integration**
("Title Plans"/"Title Boundaries" substitute) - Bulgaria's Кадастрална
карта (Agency of Geodesy, Cartography and Cadastre) provides parcel
boundaries and is publicly viewable; worth prioritizing if imotenradar
can integrate it, but scoped as its own task since it's a new external
data source, unlike the rest of this backlog.

## 17. Visual/premium design refresh

Spec's closing "Design direction" section, not a feature but a directive
that should land as part of items 9-12's builds rather than a standalone
pass: richer typography (serif/high-contrast display face for headings),
more generous whitespace between listing-card elements, a refined
restrained palette (deep neutral tones + one considered accent) in place
of a bright SaaS-blue palette, subtle elevation/shadow and rounded card
surfaces. Explicitly: match Property Filter's *workflow and information
density*, not its visual skin - imotenradar should read as more premium.

## 18. Area/neighborhood filter and Lead Generators use exact raw-string matching against un-normalized portal text - undercounts every settlement, not just Cherven Bryag - DONE, MERGED (2026-09-22)

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

## 19. homes.bg listing `homes_208381` (and possibly others): price oscillates wildly between two exact values across scrape history - not yet investigated

Found by Dessy while testing backlog item 9's price/status history chart,
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

---

## 20. imot.bg: `city` field wrongly wins over a listing's own area text when a settlement imot.bg's own site groups under a different city hasn't been geocoded yet

Found by Placy while checking whether the Cherven Bryag/"град Ловеч"
oddity Missy flagged (item 18's investigation) is a systemic pattern.
Full detail, evidence and methodology: `docs/decisions.md`'s 2026-09-22
entry.

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
for whoever picks it up after item 18 settles to avoid the same-file
collision):** don't let `city_key` win over `area`-derived resolution
unconditionally for imot.bg specifically when the two disagree and
`area` resolves via the hand-verified `BG_MUNICIPALITY_TO_OBLAST` (not
the larger generated table, to limit false-positive risk) - or, cheaper
and lower-risk, just prioritize closing the geocoding backfill gap so
`lat`/`lng` (which is already correct and already wins) covers these
listings sooner. A blind area-text override is **not** safe without
per-listing geocoding to rule out same-city name collisions like Гоце
Делчев above - demonstrated concretely, not just a theoretical risk.

## 21. Two small settlement/gazetteer gaps found incidentally in `sync_to_supabase.py` (not fixed, avoiding the file this pass)

Found by Placy while auditing `sales.bcpea.org`'s unresolved listings
(see item below and `docs/decisions.md`'s 2026-09-22 entry for the full
per-portal audit these came out of).

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

Both small, mechanical fixes once `sync_to_supabase.py` is next open for
item 18-adjacent work - bundling them in rather than a separate pass
through the same file.

## 22. alo.bg: stale `"Bulgaria"` placeholder area value still in committed data (12,501 rows), scraper code already fixed - needs a data cleanup someone/something with write access to `data/*.json` can apply

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
kind of junk value that would show up as a bogus entry in item 18's new
`area_key`-grouped dropdown); 4,327 still have no lat/lng and are
counted in item 20-adjacent audit's "alo.bg 4,394 unresolved" figure.

**Fix is a narrow, exact-match, already-written and dry-run-verified data
cleanup**: for any record where `area == "Bulgaria"` (Latin spelling,
exact) AND `city is None`, set `area` to `None` (nothing else touched -
does not change oblast/city resolution logic, just removes a
known-false raw string). **Could not apply it**: writing directly to
`data/leads_alo.json`/`data/history_alo.json` was blocked by this
sandbox's own permission system ("Modify Shared Resources" denial on the
write). The exact scope/logic is documented above and in
`docs/decisions.md`'s matching entry for whoever has write clearance for
the committed data files - or this resolves itself naturally the next
time these specific listings are re-visited by a live `scraper_alo.py`
run, since the scraper-side fix is already in place.

---

## Open questions - uncertain Bulgarian-data substitutes, do not build until resolved

Flagged by Nosy as genuinely open, not confirmed either way. Each blocks
only the specific sub-feature named, not the whole item it belongs to:

- **Last Sold / transaction-price data** (real, not asking, prices) -
  would come from Имотен регистър (Registry Agency) / Кадастър, but
  unlike UK Land Registry it's not known whether transaction-price data
  is openly scrapable in Bulgaria. Blocks: the *true* "Last Sold Data"
  histogram in item 11 (asking-price version ships regardless), the
  "Last sold(Land reg)" count pill in item 11's Comparables view, and the
  Market Data hub's "Last Sold Map" tile in item 12.
- **Price vs Income tile** (item 12) - Bulgaria's NSI does publish
  regional income data publicly, but granularity match to this tile's
  needs is unverified.
- **Census Data overlay** (item 16) - NSI publishes census data; unknown
  whether it's available at fine enough geocoded granularity/overlay
  form.
- **Crime data map** (item 16) - no known equivalent to UK police.uk's
  public, fine-grained geocoded crime dataset for Bulgaria.
- **Planning Applications** (items 11/12) - no known equivalent to the UK's
  standardized, often API-accessible per-council planning-application
  data in Bulgaria.
- **Bulgarian energy-efficiency certificate as an EPC substitute** (items
  6, 7, 8's filters) - Bulgaria has its own mandatory energy-certificate
  scheme (A-G-ish bands), but whether imotenradar's scraped source
  portals actually expose it is unknown. Omit the field entirely until
  confirmed rather than faking it.
- **PLO (Purchase Lease Option) strategy** (item 14) - relies on a UK
  leasehold/option-contract convention; unclear applicability under
  Bulgarian contract law, needs legal confirmation before a keep/drop
  call.

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
default instead, see item 15), and the UK-broker-specific "Get Finance"
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
these block starting items 9-17; revisit if/when they turn out to matter
for a specific item.

## Parked - do not start

- **Rental scraping.** Investigated: under 400 usable listings nationwide
  (imoti.bg ~394, bazar.bg ~444 but those are flatshares/rooms, not whole
  properties) - not enough for reliable yield. Revisit only if imoti.net's
  or imot.bg's real listing counts become readable (their rental sections
  exist but the count couldn't be extracted last time).
