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

## 3. alo.bg grid crawl silently dead since 2026-09-16 - mismarking ~88k listings "removed", some already showing as "Sold" live - IMPLEMENTED, NOT YET MERGED/REVIEWED (2026-09-22)

**Status: all 4 tasks implemented and locally verified; PR open, not
merged. No `Agent` tool access this session (confirmed by checking, per
the standing note in `.claude/agents/bossy.md`), so Missy has not
reviewed this yet - see the hand-back message / PR description for the
exact dispatch list.** Full investigation and what was actually done is
in `docs/decisions.md`'s 2026-09-22 entry ("Backlog items 3 and 4
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
  successful crawl self-heals it. **Still needs an actual post-merge run**
  (next scheduled 03:00 UTC, or a manual dispatch) - flagged for whoever
  picks up the dispatch list, not run from here.
- **Task 4 (git-log-hygiene)**: turned out to be entangled with task 1
  after all (not just possibly, per the original task wording) - same
  `checkout --ours` bug, same fix.

## 4. "Browse by Council" province matching: ~90%+ of the 9,247 "Others" bucket is a real bug, not genuinely non-Bulgarian data - MOSTLY IMPLEMENTED, NOT YET MERGED/REVIEWED (2026-09-22)

From Missy's 2026-09-21 daily audit (`docs/missy-findings/2026-09-21.md`),
filed as [issue #183](https://github.com/kirilbp/bg-property-tracker/issues/183),
still open, no PR against it yet. Placed above everything below that isn't
already in flight per the standing rule that a real Missy finding gets
folded into the backlog proactively - and because the impact is live,
investor-visible data corruption (incorrect "Sold" badges on the actual
site), not a latent risk.

**Confirmed facts:**
- `scraper_alo.py`'s grid crawl (`fetch_listings()`, run daily via
  `scrape-large.yml`'s `0 3 * * *` cron) has not completed successfully
  since 2026-09-16T07:57:07Z - 5.6+ days as of the finding.
- `GONE_AFTER = timedelta(hours=48)` (line 481) has since flipped 100% of
  alo.bg's 87,979 tracked listings to `source_status: "removed"` (0%
  `"active"`), vs. every other portal's healthy 8-27% removed-share.
- `sync_to_supabase.py:773` marks a merged listing `"sold"` once *all* its
  sources read `"removed"` - so any listing whose only tracked source is
  alo.bg is now showing **"Sold"** on imotenradar.com and dropping out of
  "available" filters/sort, with no real evidence it actually sold.
- Silent because `scrape-large.yml`'s `scraper_alo.py` step has
  `continue-on-error: true` and the commit step runs `if: always()` - a
  dead crawl still yields a green workflow run.

**Tasks (split into independently-shippable pieces for builders):**
1. Diagnose and fix why `fetch_listings()` has been failing/producing
   nothing since 2026-09-16 (start at `scraper_alo.py` lines 467-531 and
   the `scrape-large.yml` logs for that step across the dead window).
2. Make the failure loud going forward: the workflow must not report
   green when a portal's crawl produces zero new snapshots or flips an
   entire portal to `"removed"` in one pass - this is the same class of
   gap "fail loud, never silent" already exists to catch, and pairs with
   the existing near-zero-results sanity guard from item 1's Finding 1
   (same file, same spirit, different failure shape: total staleness
   instead of a parser returning nothing).
3. Remediate the already-corrupted data once the crawl is restored: do
   not blindly revert alo.bg's `"removed"` flags (5.6 days of *real*
   removals are genuinely mixed into that window) - re-run a real fresh
   crawl pass and let it re-establish ground truth per-listing, then
   re-run `sync_to_supabase.py`'s status computation for any listing that
   was wrongly flipped to "Sold" off a single stale alo.bg source.
4. Lower priority, same item: the git-log-hygiene wrinkle Missy flagged
   (the workflow's rebase-conflict fallback does `git checkout --ours`
   during an active rebase, keeping upstream instead of the local run's
   changes, burying real alo.bg updates under unrelated commit messages)
   - fix if it turns out to be entangled with task 1's diagnosis, file
   separately otherwise.

## 4. "Browse by Council" province matching: ~90%+ of the 9,247 "Others" bucket is a real bug, not genuinely non-Bulgarian data - URGENT

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

**Status (2026-09-22): tasks 1, 3, 4 implemented and locally verified;
task 2 implemented and locally verified with a measured real impact; task
5 investigated, not fixed. PR open, not merged - no Missy review yet (no
`Agent` tool access this session). Full detail in `docs/decisions.md`'s
2026-09-22 entry ("Backlog items 3 and 4 implemented..."); summary per
task:**
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

## 4.5. imoti.net: 100% of listings mislabeled `category: "apartment"` - real, scale-confirmed bug, not yet worked - URGENT

From Missy's 2026-09-22 daily audit (`docs/missy-findings/2026-09-22.md`,
filed as [issue #194](https://github.com/kirilbp/bg-property-tracker/issues/194)).
Folded in per the standing rule (a real Missy finding gets added
proactively, not only when the user points at it) - placed below items
3/4 since those were the ones explicitly requested this session and are
already in flight, above everything else since it's a real, live-site
correctness bug at meaningful scale, not speculative.

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

**Not yet worked - no tasks defined this session.** A real fix likely
means either (a) crawling imoti.net's Bulgarian-language URL/title
instead of `/en/` (bigger change - re-verify whether other already-
working extraction, e.g. price/sqm parsing, assumes English text), or (b)
adding an English-keyword table to `classify_category()` alongside the
Bulgarian one. Needs its own diagnosis pass before a builder can start,
same as items 3/4 got before implementation.

## 5. Supabase Pro plan follow-ups - PENDING

Free-tier limits are gone, daily backups are running. Revisit anything
designed around the old 500 MB limit (retry/backoff tuned for storage-
related 500s, any code that assumed a small dataset for cost reasons).

## 6. Motivation score rework - DONE

Shipped in PR #162: 5-component formula (relisted, distinct reductions,
size of drop, days on market, below area average), rescale option A when
area-average is unavailable, Hot/Warm thresholds recalibrated to 40/15
against real data distribution. Confirmed live.

## 7. Listing detail page redesign: multi-portal badge, price/status history, keyword tags - Nosy spec, highest investor value

Supersedes the old "Stats panel redesign - BLOCKED" item now that
`docs/property-filter-spec.md` exists. Prioritized first among the
Nosy-derived work because Nosy's own spec calls this "arguably the single
highest-value feature to prioritize" and "one of the better features" -
both build entirely on data imotenradar already scrapes, turning existing
background work into a visible, differentiating feature rather than new
data acquisition. All items below are marked **fully Bulgarian-replicable**
in the spec (section 5, "Advert Details" tab) unless noted.

- **Multi-portal badge row**: surface the up to ~6 portals/agents a
  single physical property is cross-posted under, with each source's own
  "Listed on: [date]" and the currently-viewed source highlighted. This
  is imotenradar's existing cross-portal dedup, made visible.
- **Price & Status History step-chart**: price-over-time line,
  background color-coded by status band (Available/STC-equivalent/
  Removed). Visualizes data the scrapers already collect (relisting,
  price-drop history).
- **Property Details & Keywords panel**: auto-extracted keyword tags from
  the free-text listing description (sale features, property features,
  "close by" amenities) - pure NLP/keyword-extraction on data already
  present, no new data source.
- Supporting rail/header pieces, all workflow patterns with no data
  dependency: Prev/Next paging through the current result set, "Copy
  Data for AI" export, "Create Share Link", Agent panel (logo/name/
  phone/"see agent's other properties"), Description panel with
  see-more, small embedded map, "Report a bug for this advert".
- Photo carousel + "Download pictures": replicable. Floorplan panel:
  include only when the source portal provides one (rare in scraped BG
  data per spec) - conditional field, not guaranteed.
- Nearby amenities list (distance to town centre/station/supermarket/
  hospital/school): replicable via any mapping API against Bulgarian
  addresses.

**Not included here (see "Confirmed drops" below):** CT Band, Owner
(Land Registry), Registered Lease/Restrictive covenant/Title number,
"Last building use known", HMO Article 4 flag, EPC badge (until/unless a
Bulgarian energy-certificate data source is confirmed - see "Open
questions").

## 8. Saved searches ("Lead Generators") + home dashboard + Deal Pipeline (kanban)

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

## 9. Comparables & Area Data analytics (own-data market stats + BTL stress test)

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

## 10. Market Data hub (portfolio-level aggregate tiles)

Reuses item 9's aggregation work at a broader, cross-listing scope. Spec
section 7. Fully replicable, built purely from imotenradar's own scraped
listing history (price, status, time-on-market, agent) aggregated by
area: Strategy Heat Map, Postcode Performance -> city/quarter Performance,
Market Live Map (Yield/Asking Prices/Time On Market/Demand), Adverts
Evolution (stock changes: Available/STC-equivalent/Removed over time),
Agent Properties (all listings by a given agent). Sequence after item 9
since it's the same underlying aggregation, wider lens.

## 11. Send Letters / motivated-seller outreach campaigns

Direct-mail-to-owner outreach workflow (spec sections 5's "Send Letter"
tab and section 6's full campaign manager). Flagged by Nosy as "fully
Bulgarian-replicable, high-value workflow" and a genuinely portable
feature if imotenradar wants to pursue a deal-sourcing angle, not just an
aggregator - but it's a materially bigger scope than items 7-10 (mail-merge
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

## 12. Deal Calculator (investment strategy modeling) - needs formula work before building

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

## 13. Preferences / settings to support items 7-12

Spec section 9. Mostly small, fully-replicable settings screens that
exist to back the features above rather than stand alone - sequence each
sub-tab alongside the feature it configures rather than building all of
Preferences as one block:
- Display (surface/distance units - note Bulgaria already uses metric
  natively, so the UK mile/km toggle complexity isn't even needed),
  Search Results (motivation-indicator thresholds - already a close
  match to imotenradar's own motivation-score fields), Lead Generator
  defaults, Pipeline (stage + tag configuration - ship with item 8),
  Notifications (new-lead-generator-count / status-change mechanics -
  ship with item 8), Deal Stacker defaults (BG mortgage-rate defaults -
  ship with item 9's Stress Test), Calendar integration, Letters defaults
  (ship with item 11), Deal Calculator Templates defaults (replace UK
  Stamp Duty default with a Bulgarian transfer-tax % default - ship with
  item 12).

## 14. Map tab additions

Spec sections 4 and 5's Maps tab. Street View, Satellite, and Amenities
(POI) layers are fully replicable generic map layers - low effort, can
ship alongside item 7. The one genuinely good UK-concept-with-a-real-BG-
substitute is worth calling out on its own: **cadastral map integration**
("Title Plans"/"Title Boundaries" substitute) - Bulgaria's Кадастрална
карта (Agency of Geodesy, Cartography and Cadastre) provides parcel
boundaries and is publicly viewable; worth prioritizing if imotenradar
can integrate it, but scoped as its own task since it's a new external
data source, unlike the rest of this backlog.

## 15. Visual/premium design refresh

Spec's closing "Design direction" section, not a feature but a directive
that should land as part of items 7-10's builds rather than a standalone
pass: richer typography (serif/high-contrast display face for headings),
more generous whitespace between listing-card elements, a refined
restrained palette (deep neutral tones + one considered accent) in place
of a bright SaaS-blue palette, subtle elevation/shadow and rounded card
surfaces. Explicitly: match Property Filter's *workflow and information
density*, not its visual skin - imotenradar should read as more premium.

---

## Open questions - uncertain Bulgarian-data substitutes, do not build until resolved

Flagged by Nosy as genuinely open, not confirmed either way. Each blocks
only the specific sub-feature named, not the whole item it belongs to:

- **Last Sold / transaction-price data** (real, not asking, prices) -
  would come from Имотен регистър (Registry Agency) / Кадастър, but
  unlike UK Land Registry it's not known whether transaction-price data
  is openly scrapable in Bulgaria. Blocks: the *true* "Last Sold Data"
  histogram in item 9 (asking-price version ships regardless), the
  "Last sold(Land reg)" count pill in item 9's Comparables view, and the
  Market Data hub's "Last Sold Map" tile in item 10.
- **Price vs Income tile** (item 10) - Bulgaria's NSI does publish
  regional income data publicly, but granularity match to this tile's
  needs is unverified.
- **Census Data overlay** (item 14) - NSI publishes census data; unknown
  whether it's available at fine enough geocoded granularity/overlay
  form.
- **Crime data map** (item 14) - no known equivalent to UK police.uk's
  public, fine-grained geocoded crime dataset for Bulgaria.
- **Planning Applications** (items 9/10) - no known equivalent to the UK's
  standardized, often API-accessible per-council planning-application
  data in Bulgaria.
- **Bulgarian energy-efficiency certificate as an EPC substitute** (items
  6, 7, 8's filters) - Bulgaria has its own mandatory energy-certificate
  scheme (A-G-ish bands), but whether imotenradar's scraped source
  portals actually expose it is unknown. Omit the field entirely until
  confirmed rather than faking it.
- **PLO (Purchase Lease Option) strategy** (item 12) - relies on a UK
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
default instead, see item 13), and the UK-broker-specific "Get Finance"
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
these block starting items 7-15; revisit if/when they turn out to matter
for a specific item.

## Parked - do not start

- **Rental scraping.** Investigated: under 400 usable listings nationwide
  (imoti.bg ~394, bazar.bg ~444 but those are flatshares/rooms, not whole
  properties) - not enough for reliable yield. Revisit only if imoti.net's
  or imot.bg's real listing counts become readable (their rental sections
  exist but the count couldn't be extracted last time).
