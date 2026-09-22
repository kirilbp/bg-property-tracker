# Decisions log

Owned by Bossy. Newest entry at the bottom. Every autonomous call made on
a design fork belongs here, with the reasoning, not just the outcome.

### 2026-09-18 - Shared `compute_motivation_score()` lives in `geo_utils.py`

Put the new 5-component motivation-score formula in `geo_utils.py` as one
shared implementation across all 8 scrapers, rather than duplicating it
into each scraper's own file the way small scraper-loop-specific tweaks
are duplicated elsewhere in this codebase. Reasoning: the existing
duplication pattern is justified for small, scraper-loop-specific tweaks
where scrapers can't import each other (a top-level Playwright dependency
in some of them) - this is different, a self-contained pure function with
plain inputs and no scraper-specific state, exactly matching why
`listing_city_key()` already lives in `geo_utils.py` instead of being
copied 8 times. All 8 scrapers already import from it, so this added no
new import risk.

### 2026-09-18 - `detect_relistings.py`'s own area-average bug, fixed in the same change

While wiring the new score formula into `detect_relistings.py`, found its
duplicated `compute_leads()` had never received the "city-blind area
average" fix the real scrapers got earlier (task #49) - it grouped area
averages by raw area name alone, not `(city, area)`, the same cross-city
"Center" collision bug already fixed everywhere else. Fixed it in the
same change rather than leaving a known-wrong input feeding the new
score formula.

### 2026-09-19 - Reminder-owner backfill: switched from the Auth admin API to reading an existing row's `user_id`

`backfill_reminder_owner.py` originally used the Supabase Auth admin API
to find the sole account to assign orphaned reminders to. A real run
returned "0 users found" despite the account genuinely existing and
already owning migrated `saved_listings` rows. Rather than debug why the
separate GoTrue admin surface didn't accept the current key format,
switched to the same reliable path `sync_to_supabase.py` already uses:
read the `user_id` off an existing `saved_listings` (or `lead_generators`)
row via the ordinary REST API. Still refuses to guess if it finds zero or
more than one distinct owner.

**Note (2026-09-21):** this "0 users" result recurred on a direct re-test
of the Auth admin API, post the Supabase Pro upgrade - see backlog item 2.
It's now suspected this project genuinely has 0 real accounts (the user's
account may be in a different Supabase project entirely), not just an
API-compatibility quirk. Unresolved pending the user's own dashboard check.

### 2026-09-19 - Data-loss guard: abort ALL deletion (not just the affected portal) when any portal's count looks broken

`sync_to_supabase.py`'s stale-row cleanup could delete a portal's entire
live listing set in one run if that portal's scraper silently returned
near-zero results (no exception, just a broken parser). Chose to abort
deletion for both `merged_listings` and `listing_sources` entirely when
ANY portal fails its own per-portal sanity check (below 50% of its
previous count, or under an absolute near-zero floor), rather than only
skipping the one affected portal - `merged_listings`' own staleness
detection isn't portal-scoped, so a partial skip couldn't cleanly protect
it anyway, and "stale data one cycle longer" is always the safer failure
than a partial, hard-to-reason-about cleanup.

### 2026-09-19 - `detail_checked` flag fix: didn't add `PermanentlyGone`-style short-circuiting to all 4 scrapers

Fixed `scraper.py`, `scraper_imot.py`, `scraper_olx.py`, `scraper_bcpea.py`
so the "already checked" flag is only set after a confirmed successful
fetch, matching `scraper_alo.py`'s already-correct pattern. Did not also
add `scraper_alo.py`/`scraper_bazar.py`'s extra `PermanentlyGone`
short-circuit (marking a confirmed 404/410 as permanently done without
retrying) to the other four, since their underlying fetch helpers don't
distinguish "permanently gone" from "transient failure" at all yet -
adding that would mean changing those helpers' return contracts more
broadly than the bug needed. Net effect: a genuinely dead (410'd) listing
on those four portals gets retried forever instead of being marked done -
wasteful, never data-lossy. Flagged as a smaller follow-up, not bundled
into the fix.

### 2026-09-20 - `audit_cross_city_merges.py`: per-portal pagination instead of a cross-portal OR-based cursor

The workflow failed on the exact same row across multiple separate days
with a genuine Postgres `57014` (statement timeout), not corrupted data -
its keyset pagination used PostgREST's `or=(portal.gt.X,and(portal.eq.X,
source_id.gt.Y))` to emulate a composite-key cursor across all 8 portals,
which isn't guaranteed to use the `(portal, source_id)` primary key index
as tightly as a real tuple comparison, and `alo.bg` (the largest portal)
is exactly where a bad plan would show up. Switched to paginating one
portal at a time - every page becomes `portal=eq.<X> AND source_id>Y`, a
plain single-column range scan with no OR left for the planner to
mishandle. Verified against production: all 301,596 rows load cleanly,
0 cross-city groups found.

### 2026-09-21 - Missy's daily routine: commits a findings file instead of filing issues directly; a separate push-triggered workflow opens the issue

Confirmed (by test-firing it) that a Routine created with
`create_new_session_on_fire: true` spawns a session with no
`mcp__github__*` tools at all - it does not inherit the calling session's
GitHub access. That broke the original design, where Missy's own daily
routine invocation would sample live Supabase data and open a GitHub
issue herself. Two constraints stack here: this sandbox's egress proxy
also blocks `*.supabase.co` outright, so even sampling couldn't happen
live from this environment regardless of GitHub access.

Chose (user-approved) to keep the routine self-contained rather than try
to grant it GitHub tools: the fired session invokes Missy scoped to the
repo's own committed `data/leads_*.json`/`data/history_*.json` files
(refreshed every 6 hours by the scrapers already), writes her returned
findings to `docs/missy-findings/<date>.md`, and pushes it with
`scripts/commit_and_push.sh` (Bash + git credentials, no GitHub API
needed). A separate workflow, `.github/workflows/missy-findings-issue.yml`,
triggers on that push and opens the GitHub issue itself using its own
ambient `GITHUB_TOKEN` - the same pattern `check_reminders.py` already
uses, so the repo owner gets GitHub's normal notification email with no
new email service. `open_findings_issue.py` diffs against the push
event's `before` SHA (not `HEAD~1`) specifically because
`commit_and_push.sh`'s own "residual commit" fallback can turn one
logical push into two commits - `HEAD~1` would silently miss the findings
file if it landed in the earlier of the two.

Accepted limitation: the daily audit now checks committed data, not the
live Supabase table, so it can't catch corruption introduced purely
inside `sync_to_supabase.py` or via a manual Supabase edit after sync.
Not treated as a full gap: `audit-cross-city-merges.yml` already runs
daily directly against the live table and covers the most serious version
of that bug class (cross-city merge corruption). Bossy now also reads
`docs/missy-findings/` at the start of every session, so a finding
surfaces even if the user doesn't look at the emailed issue right away.

### 2026-09-21 - Routine test-fires: subagent delegation silently dropped the persistence step; fixed by removing the handoff, not by warning harder

End-to-end test-firing the new Missy routine (above) surfaced a real
failure: a routine session that invoked the `missy` subagent via the
Agent tool, got a complete findings report back, then ended its turn
without ever writing or pushing the file - real cost was incurred
(subagent ran to completion) but nothing landed in git. Adding an
explicit "your turn isn't done until the push lands" warning to the same
subagent-delegation structure didn't get a conclusive re-test (interrupted
once a cleaner fix was ready), so the structure itself was changed instead
of just warning harder: the routine no longer calls the Agent tool at all.
It reads `missy.md` and does the sampling/verification/writing/pushing
itself in one continuous turn, removing the handoff boundary where a
polished subagent report reads like a finished answer and invites the
model to summarize-and-stop instead of treating persistence as mandatory.

Had a general-purpose agent run Missy's own fault-finding process against
this failure (the `missy` subagent type had become unavailable in the
orchestrating session after an unrelated branch-reset side effect, so it
adopted her role/rules from `missy.md` directly rather than via the
registered subagent type). It confirmed tool availability wasn't the
constraint (Bash/Write/Edit/Agent were all present in the routine
session - only `mcp__github__*` tools are actually missing, per the entry
above) and flagged a second, independent bug while reviewing the pipeline:
`scripts/commit_and_push.sh`'s conflict-resolution path kept main's
already-pushed version of every conflicted file, including whatever the
current call was trying to add - so two same-day firings (exactly what
today's repeated test-fires produced) could silently discard the later
run's findings while still reporting success. Fixed separately (see
scripts/commit_and_push.sh's own inline comment) and verified with a real
two-clone push race in a throwaway repo.

**Superseded (2026-09-21, later same day):** the "remove the Agent-tool
handoff" fix above was the wrong diagnosis. A follow-up test-fire using
that exact no-subagent structure *also* failed to push anything, which
ruled out prompt structure entirely. The real cause, found by firing
minimal diagnostics instead of further prompt variants: (1) a Routine
created with `create_new_session_on_fire: true` spawns a session with no
MCP connectors at all - not just GitHub's, all of them - so `mcp__github__*`
tools were never available to any of these routine-fired sessions,
confirming the very first finding at the top of this section was correct;
and, independently, (2) this repo's `main` branch has push protection that
a non-owner session's git credentials can't bypass - even a bare
`git commit --allow-empty && git push origin main` from a routine session
got a 403, while pushing a *new* branch from that same session succeeded
fine. Both facts were verified with disposable diagnostic firings that
left observable evidence (a branch that did or didn't appear, an issue
that did or didn't get filed) rather than trusting any session's own
self-report, since there's no tool available to read a Claude Code Remote
session's actual response text - only status metadata.

Fix: stopped using `create_new_session_on_fire` for this Routine entirely.
It now fires into a dedicated persistent session ("Missy daily audit
runner", created via `create_session`) using `persistent_session_id`. That
session type has normal MCP connector access confirmed working (it opened
a real GitHub issue directly, see issue #182/#183) and can push new
branches, so the design simplified back down: the routine now opens the
`missy-finding` GitHub issue *directly* via `mcp__github__issue_write` -
no committed file or separate push-triggered workflow needed for the
notification path to work. The `docs/missy-findings/<date>.md` +
`missy-findings-issue.yml` pipeline built earlier today is kept as a
secondary, best-effort record only (pushed on its own branch + a PR,
since direct-to-main is still blocked) - useful for Bossy's start-of-
session check, but the emailed notification no longer depends on it.
Verified end to end for real on the first live run: issue #183 (a genuine
finding - alo.bg's grid crawl silently dead since 2026-09-16) plus PR #184
carrying the committed record, both landed from a single firing.

### 2026-09-22 - Login removed entirely, per the user's explicit direct decision

The user gave direct, explicit authorization for this exact change ("I
want login removed completely") - not a design fork Bossy resolved on
its own, so this entry is a record of what shipped and why, not a
default-option justification.

**What was removed from `index.html`:** the entire Supabase-Auth-gated
login system backlog #62 added - the login modal (HTML/CSS/JS),
`CURRENT_USER`, `openLoginModal`/`closeLoginModal`/`submitLogin`/
`logout`, `applyAuthState`, the `sb.auth.getSession()`/
`onAuthStateChange()` wiring, the one-time `migrateLocalDataIfNeeded()`
migration block, the two "log in to use this" gate cards on Lead
Generators and the Dashboard, and the sidebar account/logout UI. Every
`if (!CURRENT_USER) { openLoginModal(); return; }` gate on
`toggleSavedListing()`/`openReminderModal()` is gone too.

**What replaced it:** Saved listings, Lead Generators, and Reminders are
back to a plain, synchronous, this-browser-only `localStorage`
implementation (`savedListingIds`/`leadGenerators`/`reminders` keys) -
no accounts, no server round-trip, no shared/public data exposure. This
is deliberately the same architecture the app used before backlog #62,
reconstructed functionally rather than restored byte-for-byte (backlog
#62's own code comments described the old localStorage keys/shapes
clearly enough to rebuild them faithfully - confirmed against the
`migrateLocalDataIfNeeded()` block's own reads of the OLD keys before it
was deleted). Caught and fixed one real bug introduced while doing this:
the listing detail page's reminders block originally ran its
(now-synchronous) load *after* the page's first render, so a reminder
set on a listing wouldn't show up until some unrelated re-render
happened - moved the load before the first `renderListingDetail()` call
in `showListingDetail()` so the first render already has it, verified
with a Playwright test asserting the reminder note appears in the
rendered detail-page HTML.

**Backend left untouched, on purpose:** per the user's own instruction
and the standing rule against unnecessary destructive changes,
`supabase/schema.sql`'s `auth.users`-based tables/RLS policies
(`saved_listings`, `lead_generators`, `reminders`'s per-user policies)
were NOT dropped or reverted - they're simply unused by the frontend
now. Flagged here as a candidate for later cleanup, not urgent: nothing
references them anymore, they cost nothing beyond a little schema
clutter, and dropping RLS/columns is real, one-way risk for a change
that was scoped as frontend-only.

**One real behavior loss, called out rather than papered over:**
`check_reminders.py` (the daily job that opens a GitHub issue as a
backup nudge for an overdue reminder, `.github/workflows/
check-reminders.yml`) reads the Supabase `reminders` table with a
service-role key. Since reminders now live only in each browser's
`localStorage`, no new reminder ever reaches that table again - the job
is not broken (it will keep running, keep exiting 0, and correctly find
nothing new) but it is now permanently a no-op for anything created
after this change. Chose not to try to keep it alive (e.g. by also
writing reminders to Supabase via the anon key) rather than silently
reintroduce a server dependency the user just asked to remove - updated
the Dashboard's Reminders card copy to stop promising the GitHub-issue
nudge, so the UI doesn't claim a capability that no longer exists (same
"fail loud, not silent" reasoning applied to misleading copy, not just
code). If cross-device/backup reminder notifications matter enough to
rebuild, that's a fresh, explicitly-scoped feature request, not
something to half-preserve here.

Verified locally: JS syntax-checked (`new Function()` on the extracted
`<script>` body), then driven end to end in a real headless Chromium via
Playwright (CDN/Supabase network calls stubbed, since this sandbox's
egress proxy blocks `unpkg.com`/`cdn.jsdelivr.net`/`cdnjs.cloudflare.com`/
`*.supabase.co` outright, consistent with Missy's own 2026-09-21 finding
about the same proxy policy) - confirmed no login DOM elements or
globals remain, save/unsave a listing persists and reverses correctly
in `localStorage`, lead generator add/duplicate/delete all persist,
reminder create/dismiss both persist with the right `dismissed` flag,
`openReminderModal()` opens with no login check, and the Lead
Generators/Dashboard pages render their real content directly (no gate,
no empty state waiting on a session). Zero uncaught page errors in any
of these runs. Also grepped the whole repo for every removed identifier
(`CURRENT_USER`, `openLoginModal`, `applyAuthState`, the login-gate
element ids, etc.) - the only hits left are this file, the backlog, and
index.html's own explanatory comments, confirmed none of them are live
code paths.

**Review note:** this session had no `Agent`/Task tool available to
spawn the `missy` subagent the "nothing ships without Missy" standing
rule normally means (same gap the 2026-09-21 routine-firing entry above
hit once already) - flagging this plainly rather than silently skipping
the review or silently claiming a subagent sign-off that didn't happen.
Followed the same fallback used then: reviewed this change directly
against `.claude/agents/missy.md`'s own rubric for "reviewing a finished
piece of work" (scope to the diff, verify locally, give a clear sign-off
or a list of blocking problems) rather than her data-accuracy sampling
process, which doesn't apply to a pure frontend-logic change with no
listing data involved. No blocking problems found under that rubric.
This is a real, load-bearing gap in this session specifically (not a
one-off) - worth the user's attention if they want every future Bossy
session to reliably have subagent-spawning access for exactly this
reason.

### 2026-09-22 - "Others" province bucket: Missy's investigation (backlog item 4)

The user reported the live "Browse by Council" section's "Others"
bucket (9,247 listings) as inherently suspicious, since Bulgaria's 28
oblasts cover 100% of its territory. Dispatched Missy directly to
investigate (not through Bossy, given the just-documented Agent-tool
gap above - this session did the dispatching itself as the reliable
path). Full findings are in `docs/backlog.md` item 4; summary here for
the decision log: confirmed real, not a false alarm - sampling ~8,787
raw listings that fail the live matching logic found only ~5-6% is
legitimately foreign/unparseable, the rest splits roughly evenly
between an `scraper_alo.py` bug (a `"Bulgaria"` placeholder written
whenever its location regex fails, compounded by a title-extraction
fallback that truncates listing text before the recoverable location
words) and a structural `BG_MUNICIPALITY_TO_OBLAST` coverage gap (the
table only covers municipality *seat* names, not Bulgaria's ~5,300
actual settlements).

Verification method worth recording: this sandbox still can't reach
alo.bg/olx.bg/homes.bg/bcpea.org directly (same egress-proxy block
noted in the 2026-09-21 entry above), so Missy verified by running the
project's own real functions (`listing_city_key()`/`listing_oblast_key()`,
imported unmodified from `geo_utils.py`/`sync_to_supabase.py`, not
reimplemented) against the committed `data/leads_*.json` files, then
manually checked a sample of the results against her own knowledge of
Bulgarian geography rather than live portal pages. Flagged plainly in
her own report as the reason this is "verified against the project's
own logic" rather than "verified against live source pages" - the
usual standard when live network access isn't blocked.

While characterizing the settlement-name gap, also found a genuinely
ambiguous name the eventual gazetteer-table fix will need to handle
carefully: "Средец" is both a real Burgas-oblast town/municipality and
a central Sofia-grad district name - the same class of collision
`BG_MUNICIPALITY_TO_OBLAST` already excludes "Бяла" for (real, different
municipality in both Varna and Ruse oblasts). Flag-and-exclude on
collision, don't guess, is the established precedent to follow when
this gets built.

### 2026-09-22 - Backlog items 3 and 4 implemented; no Agent-tool access this
session, so Missy/Revy review is still pending on a dispatch list

Worked both items per the user's explicit request. **No `Agent` tool was
available in this session** (confirmed by checking, per `.claude/agents/
bossy.md`'s own standing instruction for this - it did not assume either
way). Everything below was implemented and verified directly by this
session, as thoroughly as tooling allowed, but **none of it has been
reviewed by Missy, and none of it has shipped/merged** - see the
hand-back message for the exact dispatch list. This entry records the
real findings and calls made along the way.

**Item 3 root cause - the "dead crawl" was never actually dead.** Before
touching anything, pulled the real GitHub Actions job logs for
`scrape-large.yml`'s runs on 2026-09-16 through 2026-09-19 (the ones
covering the window Missy flagged). `scraper_alo.py`'s `fetch_listings()`
succeeded on every single one of them - 77,625 to 89,324 real listings
found per run, no crash, no early stop. The actual failure was one level
up: the commit step's `git pull --rebase origin main` hit a real content
conflict against `backfill-detail-alo.yml` (which runs *hourly* and
writes to the exact same `data/history_alo.json`/`data/leads_alo.json`
files - the workflow's own header comment claiming these files were
"disjoint from... any hourly backfill" was simply wrong, confirmed by
reading `backfill-detail-alo.yml` directly) on 2026-09-16, -18, and -19
(checked; didn't check every single day, the pattern was already
unambiguous). The conflict fallback then ran `git checkout --ours`,
which - during an active `git rebase` - keeps the *upstream* (main's)
side, not the local run's, the opposite of what its own comment claimed
("keeping main's version" is what it does, but that's backwards when
main's version is the stale one). On 2026-09-18/19 this conflict hit
`data/history_alo.json` itself (not just the derived `leads_alo.json`),
so the entire day's freshly-scraped data was discarded, every single
day - which is exactly why every listing's last real snapshot froze at
2026-09-16T07:57:07Z regardless of how many "successful" runs followed.

Real fix shipped (not yet merged): `merge_history_conflict.py`, a real
per-listing merge (union of snapshots, min first_seen, shallow-merged
"latest") for any conflicted `data/history*.json`, wired into both
`scrape-large.yml` and `backfill-detail-alo.yml`'s conflict fallback in
place of `checkout --ours` for those specific files (anything else still
falls back to the old behavior, now logged loudly via `::warning::`
instead of silently). Tested against a real simulated git rebase conflict
(not just unit-level dict merging) - built a scratch git repo, reproduced
the exact conflict shape from the real logs (`CONFLICT (content): Merge
conflict in data/history_alo.json`), ran the resolver, confirmed
`git rebase --continue` completes and the merged file has zero data loss
from either side (both listings' fresh snapshots kept, backfill's
enrichment fields on `"latest"` survived the merge). `data/leads_*.json`
deliberately gets no custom merger - it's a fully-derived file every
scraper's own `compute_leads()` rebuilds from `history*.json` on its next
run, so it self-heals within one cycle once the real source-of-truth file
stops losing data; writing a bespoke merger for an unkeyed array would be
real added risk for no lasting benefit.

Task 2 ("fail loud"): added `check_scrape_freshness.py` as a new,
non-`continue-on-error` step at the end of `scrape-large.yml`, checking
(a) the freshest snapshot across the whole committed history file isn't
older than 30h and (b) the computed leads file's active-listing share
isn't below 40% (every portal's own healthy range is 72-91% active per
Missy's 2026-09-21 sampling, so this floor has real margin without being
loose enough to miss a real incident). Ran it against the actual,
currently-still-corrupted `data/history_alo.json`/`leads_alo.json` in the
repo right now - it correctly fails loud (`::error::` on both checks, 0%
active). This is the generic, reusable version of the class of guard
Finding 1 already established in `sync_to_supabase.py` (near-zero-count
guard) - same principle, different failure shape (total staleness with a
healthy count, not a collapsed count).

Task 3 (remediate corrupted status data): deliberately did NOT write any
script to revert/patch existing `"removed"`/`"sold"` flags. Per the
backlog's own explicit instruction (5.6+ days of real removals are
genuinely mixed into that window - a blind revert would be as wrong as
the bug), the fix is letting the crawl and commit pipeline work correctly
again and re-run for real: `source_status`/`"sold"` are both computed
fresh from `history_alo.json`'s own snapshot recency on every run, so
once a real crawl's data lands on `main` without being discarded, every
listing's status recomputes correctly on its own - no separate
remediation script needed, just an actual successful run. **This still
needs to happen post-merge** - either the next scheduled 03:00 UTC run or
a manual `workflow_dispatch`, and someone should watch that first
post-merge run's commit-step log to confirm a conflict resolves via the
real merge (near-certain given the hourly backfill's cadence) rather than
falling through to the old behavior. Left for the dispatch list, not run
from here - this session doesn't merge its own unreviewed PR to main and
trigger a production run against it.

**Item 3/4 overlap, resolved:** the task brief asked whether item 3 task 1
(why the crawl "died") and item 4 task 1 (`scraper_alo.py`'s `"Bulgaria"`
placeholder/title-truncation bug) might be the same root cause, since
both live in `scraper_alo.py`. They are **not** - confirmed independently
verified: item 3's actual cause is entirely in the git-commit workflow
layer (above), nothing to do with `fetch_listings_page()`'s own parsing;
item 4's bug is a genuine, separate content-extraction issue inside
`fetch_listings_page()` itself (`LOCATION_RE` missing a card's location
text, independent of whether that data ever successfully reaches disk).
Pure coincidence of living in the same file.

**Item 4 task 1** (scraper_alo.py placeholder/title bug): changed
`area, city = "Bulgaria", None` to `None, None` on a `LOCATION_RE` miss -
confirmed via `index.html` (line ~2553/2635) that `l.area` feeds directly
into the frontend's own neighborhood-filter dropdown, so `"Bulgaria"` was
literally a user-visible value, not just an internal placeholder.
Confirmed via `backfill_others_alo_detail.py` that no existing script
keys off the literal string `"Bulgaria"` for its own targeting logic (it
already selects by "`listing_oblast_key()` returns None", not by field
value), so this change doesn't break that script. Fixed the title
fallback to keep the text immediately *before* the price marker (where
this project's own `LOCATION_RE` docstring already says the location
phrase lives) instead of blindly keeping the first 100 characters of
container text (agency name/"преди N дни" boilerplate) - verified with a
synthetic-but-realistic card reproduction that this changes a real
`oblast_key_from_latlng`-style outcome from `None` to a correct resolved
oblast (`burgas`), using the project's own unmodified `listing_oblast_key()`.

**Item 4 task 2** (settlement gazetteer): the backlog flagged this as
needing "an authoritative source (NSI or similar gazetteer)". This
sandbox's egress proxy blocks every property-portal domain but does
**not** block `raw.githubusercontent.com`/`github.com` - confirmed live.
Used `yurukov/Bulgaria-geocoding`'s `settlements.csv` +
`municipalities.csv` - **the same maintained public dataset this project
already uses** for `data/bg_oblast_boundaries.json` (see that file's own
comment in `sync_to_supabase.py`), not a new/unvetted source. Cross-
validated the derived municipality-code-prefix -> oblast mapping against
every name already in `BG_MUNICIPALITY_TO_OBLAST`: 27 of 28 prefixes
derived with **zero contradictions** against this project's own
hand-verified entries; the 28th ("SOF" = Столична, Sofia-grad's single
municipality) is unambiguous by construction. Applied the same
ambiguous-name discipline as the existing table's own "Бяла" exclusion,
but automatically: any settlement name appearing under more than one
oblast anywhere in the raw 5,284-settlement dataset is excluded outright
(521 of 4,513 distinct names, ~11.5%). That automatic rule independently
rediscovered both names already flagged by hand - "Бяла" (turns out to
span 3 oblasts at the full settlement level, not just the 2 known from
municipality seats) and "Средец" (spans 3 oblasts on its own, before even
counting the separate Sofia-grad-district collision Missy flagged) - with
no special-casing needed, which is a real signal the rule generalizes
correctly rather than just covering the two cases already known. Wrote
the result to `data/bg_settlements_to_oblast.json` (3,784 names, purely
additive - never overrides an existing `BG_MUNICIPALITY_TO_OBLAST` entry,
checked second in `oblast_key_from_municipality()`) and measured the real
impact against the actual committed `data/leads_*.json` files (all 8
portals, using the project's own unmodified `listing_oblast_key()`, not a
reimplementation): the "Others" bucket drops from 8,763/304,988 (2.9%) to
5,633/304,988 (1.8%) - **3,130 listings newly resolved** by this table
alone, before even counting item 4 task 1's alo.bg fix's own impact
(alo.bg's committed data hasn't been re-crawled with that fix yet). Full
304,988-listing set processed with zero exceptions and no meaningful
performance cost (~7s).

**Item 4 task 3** (Вълчи Дол): added to the Varna section of
`BG_MUNICIPALITY_TO_OBLAST`, matching the capitalization convention every
other multi-word entry in that table already uses.

**Item 4 task 4** (`oblast_key_from_latlng` point-in-ring investigation):
found a real, reproducible cause using the actual committed coordinates
of the Близнаци cluster Missy flagged (e.g. `43.1032247, 27.9233784`,
real olx.bg data already in `data/leads_olx.json`) - `_point_in_ring`'s
own ray-casting algorithm is correct (verified by hand-tracing the real
ring-edge crossings), but this specific point sits about 8 meters outside
Varna oblast's own simplified boundary polygon (`yurukov/Bulgaria-
geocoding`'s data is intentionally simplified for file size) - ordinary
coastline-simplification + GPS/geocoding precision noise, not a wrong-
oblast bug. Added a conservative, tested fallback:
`NEAR_BOUNDARY_TOLERANCE_DEG = 0.003` (~200-330m across Bulgaria's own
latitude range) - if the strict point-in-ring test finds nothing, checks
distance-to-boundary for every oblast and returns a match only when
exactly one oblast is within tolerance (two-or-more within tolerance - a
real shared border - stays unresolved, same "don't guess" discipline as
everywhere else in this matching logic). Tested against: the real
Близнаци point (now resolves to `varna`; 34 of the actual 36 committed
listings in that cluster now resolve), Sofia/Varna city centers (still
resolve via the strict test, unaffected), a point in Istanbul (correctly
stays unresolved, no false-positive risk demonstrated), and two synthetic
adjacent-polygon tests specifically built to exercise the new fallback's
own near-single-oblast and ambiguous-shared-border code paths (both
behaved correctly - one non-guessed exact match, one correctly withheld).

**Item 4 task 5** (homes.bg empty-address gap): investigated, not fixed.
Confirmed the exact number from Missy's report against real data: of
homes.bg's 221 "Others"-bucket listings, 94 are the already-correctly-
excluded "Бяла" case and 92 have completely empty location signal
(`city: null`, `area: ","` or blank, and no location words anywhere in
`title` either - e.g. `homes_296683`'s title is just `"Къща, 64m²"`).
Traced `scraper_homes.py`'s own extraction: `location = offer.get(
"location", "")` reads directly from homes.bg's own structured per-
listing data object, with no further HTML text-parsing involved - so this
isn't a parsing bug to fix, it's homes.bg's own data genuinely carrying
nothing for these specific listings on whatever page/endpoint this
scraper reads. A real fix would mean checking whether homes.bg's own
listing *detail* page (not the list/API response this scraper currently
reads) carries better location data - that needs live network access to
homes.bg to verify, which this sandbox's egress proxy blocks (same block
Missy hit on 2026-09-21/22). Left open, filed as its own follow-up rather
than guessed at.

**Not done, explicitly deferred to the dispatch list:** Missy's own
review (and this repo's own "nothing ships without Missy" rule) - no
`Agent` tool access this session means none of the above has had a real
second set of eyes yet. This is not auth/security/credentials/personal-
data work, so Revy's narrower gate doesn't apply here by this session's
own read of the standing rule - but that's this session's own judgment,
not a substitute for Missy actually looking at it. See the hand-back
message for the exact dispatch list (repo, PR link, and what each
reviewer needs to check).

**Also folded into the backlog per the standing rule** (a real Missy
finding gets added even when not the thing currently being worked):
Missy's 2026-09-22 finding #2 (imoti.net: 100% of listings mislabeled
`category: "apartment"` because `classify_category()`'s Bulgarian-keyword
table is fed the *English* `/en/` version of imoti.net's own scraped
titles) - added as backlog item 4.5, below items 3/4 since those were the
ones explicitly requested this session, above the rest since it's a real,
scale-confirmed (at minimum 4,916/26,804 listings, 18.3%) live-site
correctness bug, not speculative.

### 2026-09-22 - imoti.net 100%-"apartment" miscategorization (backlog item 5): root-caused and fixed

**Root cause, confirmed against real committed data, not guessed:**
`scraper.py` (imoti.net's own scraper) crawls the site's `/en/` (English)
path and still called `geo_utils.classify_category(title)`, whose keyword
table is Bulgarian-only - so the scraped English title could never match
anything and every listing fell through to that function's own documented
`"apartment"` default. Confirmed live in `data/history.json`: all 26,881
imoti.net records had `category: "apartment"` before this fix, with zero
exceptions (matches Missy's 2026-09-22 finding almost exactly - the small
gap between her cited 26,804 and this session's 26,881 turned out to be
pre-existing staleness in the committed `data/leads.json`, unrelated to
category, self-corrected as a side effect of this fix - see below).

Also confirmed, not assumed: `category_classifier.py`'s
`classify_listing()` - the shared nationwide-expansion classifier already
adopted by `scraper_alo.py` and `scraper_imoti_bg.py` for this exact class
of bug - scores three independent signals (title/description/url) and
already includes several English keywords, so migrating `scraper.py` onto
it (instead of hand-rolling an imoti.net-specific classifier, or switching
the whole scraper to crawl imoti.net's Bulgarian-language URL/title, the
two options the backlog entry left open) was both the smaller change and
the one consistent with how the other two already-migrated portals handle
it. imoti.net's own listing URL turned out to already embed a fully
reliable Bulgarian-language type slug right before the numeric ID (e.g.
`.../kashta/1234567/`, `.../garaj/.../`, `.../parcel/.../`) - a closed,
site-controlled vocabulary, so passing both `title=` and `url=` into
`classify_listing()` gives two independent, largely-agreeing signals with
no network call needed (both were already scraped). Re-verified live that
imoti.net's price/sqm/date extraction (`BGN_RE`/`SQM_RE`/`DATE_POSTED_RE`)
doesn't depend on title language at all, so switching the crawl to
Bulgarian URLs would have been the strictly bigger, riskier change for no
extra benefit here.

**A real regression caught and fixed before shipping, not just assumed
safe:** the first version of this fix added bare `"industrial"` and
`"promishlen"` keywords to `category_classifier.py`'s `business` category
(imoti.net's own English titles literally say "Industrial property"/
"Commercial property" for these). Running the new classifier against the
*entire* real `data/history.json` (not just a sample) surfaced 308 tied-
category results, and inspecting them found a real false positive: "Индус-
триална зона"/"Промишлена зона" ("Industrial Zone"/"Industrialna Zona"/
"Promishlena Zona") is a genuinely common Bulgarian district name (Burgas,
Haskovo, Yambol, Vratsa, Plovdiv, Gabrovo, Lovech all have one) - so the
bare keyword wrongly flagged ordinary flats/houses/studios *located in*
that district as "business", e.g. `"House, 21 м2 ... Industrial zone -
South"` (a real house) tying/losing against its own location text. Fixed
by using the full phrases actually present in imoti.net's titles
("industrial property"/"commercial property") and the exact hyphenated URL
slug ("promishlen-imot") instead of the bare words, which don't collide
with the district-name spelling ("promishlena"/"industrialna"). Re-ran
against the full dataset after the fix: ties dropped from 308 to 1 (a
single genuine, unavoidable edge case - a Pleven district literally named
"Hotel Balkan" colliding with the pre-existing "hotel" keyword, not
introduced by this change, one listing out of 26,881).

**Regression-checked against the portals already on this classifier**,
not just assumed safe because the new keywords are English/Latin: re-ran
`classify_listing()` before/after this change against a 5,000-listing
random sample of `data/history_alo.json` (alo.bg) and the full 908-record
`data/history_imoti_bg.json` (imoti.bg) - zero category changes in either,
confirming the new keywords are specific enough not to catch anything in
those portals' Bulgarian-language text.

**Verified against real data, the way Missy's own audits do, not just
"the script ran without crashing":** sampled real records and checked the
classified category against the listing's own stored title/URL by hand
(e.g. `kashta` URL slug + `"House, ..."` title -> `house`; `garaj` +
`"Garage, ..."` -> `garage`; `magazin` + `"Shop, ..."` -> `shop`) across
dozens of listings, all correct. Full-dataset result after the fix:
21,399 flat, 2,360 land, 1,436 house, 750 business, 603 shop, 333 garage
(was 26,881/26,881 "apartment", 100%, before).

**Correction (Missy's PR #199 review, 2026-09-22):** this entry originally
claimed "92.6% high confidence, 0.26% low-confidence residual," implying
those two numbers accounted for the whole dataset. They don't - the real
breakdown, recomputed independently from the committed data, is 91.73%
high confidence (24,659) / 8.27% low confidence (2,222). The 0.26% figure
(71/26,881) is accurate but only covers the `no_keyword_match` subset
(things like "Building"/"Hall"/"Forest"/"Farm" with no recognizable
keyword in either signal - the same small, accepted-residual pattern
already established for backlog item 4's task 5). It silently omitted the
other 2,150 records (8.0%) that are low-confidence for a different,
previously-undocumented reason: `single_signal_only`. Missy hand-checked
15 of those and found all correctly categorized (e.g. "3 bedroom
apartment"/`chetiristaen` URL -> flat), so this isn't a misclassification
risk - it's a real but pre-existing gap in `category_classifier.py`'s
`flat` keyword list, which has "ednostaen"/"dvustaen"/"tristaen" but is
missing "chetiristaen" (4-room) and "mnogostaen" (multi-room), so the
URL-slug signal silently fails to match on those even though the title
signal still does. Not introduced by this PR (the diff never touched the
`flat` keyword list) - filed as its own small follow-up rather than
re-opening this fix. `category_confidence` is stored on every listing
precisely so a gap like this gets flagged accurately, not undersold.

**Remediated already-committed data, not just fixed forward:** wrote
`backfill_category_imoti_net.py`, a one-off, purely-local script (title
and url are already stored per listing - no network call needed) that
reclassifies every existing `data/history.json` record and regenerates
`data/leads.json` via `scraper.py`'s own `compute_leads()`. Chose this
over waiting for the next scheduled crawl to self-heal because a listing
that's since gone "removed" would never be re-visited by `fetch_listings()`
again and would stay permanently mislabeled otherwise. Diffed the full
before/after `leads.json` by id: same 26,881 ids, only
`category`/`category_confidence`/`score`/`area_avg_price_per_sqm`/
`pct_vs_area_avg` changed for any record (the last three are expected
downstream effects of category changing which area-average bucket a
listing falls into, not a bug) - no price/sqm/url/title/other field
touched.

**A second real, related bug found and fixed in the same change, not
deferred:** `index.html`'s `matchesLeadGenerator()` (the Lead Generators
feature already live on the site, predating the bigger Property Filter-
spec rebuild in backlog item 9) compared a listing's raw `category`
directly against the Lead Generator modal's 4 checkbox values (still the
*old* `classify_category()` vocabulary: apartment/house/land/commercial).
`findComparables()` elsewhere in `index.html` already documents exactly
this old-vs-new-vocabulary mismatch and normalizes through
`typeFilterBucket()` first - `matchesLeadGenerator()` never got the same
treatment. Left as-is, this fix would have made the live bug meaningfully
worse: every one of imoti.net's 26,881 listings, now correctly reporting
`"flat"/"house"/"land"/"garage"/"shop"/"business"` instead of always
`"apartment"`, would have silently stopped matching any saved Lead
Generator search filtered to "Apartment" or "Commercial" (`"flat" !==
"apartment"`), on top of alo.bg/imoti.bg listings already silently broken
this way today. Fixed by adding the same bucket-normalization
(`LEGACY_PROPERTY_TYPE_TO_BUCKETS`, mapping the 4 checkbox values onto
`typeFilterBucket()`'s 6 buckets, "Commercial" covering all of garage/
shop/business) `matchesLeadGenerator()` was missing. Verified with a
standalone Node harness against the extracted functions: both old-vocab
("apartment") and new-vocab ("flat") listings now correctly match the
"Apartment" filter, and garage/shop/business listings all correctly match
"Commercial".

**Not done, explicitly deferred to the dispatch list (this session had no
`Agent` tool access):** Missy's real review. Implemented, self-verified
against real data (not a self-review of the *design*, a real diff/sample/
regression check against the actual committed data and a Node-run
functional test of the JS change), but that is not a substitute for her
actually looking at it, per the standing "nothing ships without Missy"
rule. Opened as
[PR #199](https://github.com/kirilbp/bg-property-tracker/pull/199)
(`claude/bg-property-tracker-setup-30c2rp` -> `main`), not merged - the
PR itself asks for Missy's review before merge. Not auth/security/
credentials/personal-data, so Revy's narrower gate doesn't apply by this
session's own read of the standing rule. See the hand-back message for
the exact dispatch list.

### 2026-09-22 - Site performance (backlog item 6): root-caused, deliberately not implemented this session

The user raised this directly and unprompted, mid-session, while the
imoti.net category fix above was in flight: the live site is very slow to
load/refresh. Confirmed the coordinator's own quick diagnosis by reading
the real code rather than taking it on faith - `index.html`'s
`loadData()` -> `fetchAllRows('merged_listings')` does
`sb.from('merged_listings').select('*').order('id').limit(1000)` in a
sequential keyset-pagination loop, pulling the *entire* `merged_listings`
table into the browser on every single page load, for every visitor,
regardless of what they're viewing - hundreds of thousands of rows, each
one heavy (`description`, a `photos` jsonb array, and a `price_history`
jsonb array per row, per `supabase/schema.sql`, all pulled via
unrestricted `select('*')`). Confirmed no caching layer exists at all
(grepped for `localStorage`/`IndexedDB` usage against `MERGED_LISTINGS` -
none), so this repeats in full on every refresh, not just first visit.
Confirmed the schema already has 10 real indexes on `merged_listings`
(price/sqm/area/city_key/type_bucket/score/days_on_market/drop_pct/
status/oblast_key) - so this isn't a missing-index problem, it's purely
architectural (fetch-everything-then-filter-client-side). One real open
design question found and flagged, not resolved: `area_avg_price_per_sqm`/
`pct_vs_area_avg` are already precomputed server-side per row, so most of
the app doesn't actually need the full dataset in memory - but
`findComparables()`'s radius search does an in-memory scan by lat/lng
that would need a real geo index (none exists yet) to move server-side
properly.

**Deliberately not implemented this session, for two real reasons, not
laziness:**

1. **No `Agent` tool access**, and the coordinator's own message flagged
   that `index.html` may be under active concurrent edit by Dessy (backlog
   item 9's listing-detail redesign) - confirmed the underlying risk is
   real, not hypothetical: another agent (Selly) pushed a commit to this
   exact shared branch (`claude/bg-property-tracker-setup-30c2rp`) while
   this session was mid-task. Editing the same large file in parallel with
   an agent this session has no way to message or check the live state of
   risks a real collision. Rather than guess at sequencing blindly, this
   is left for the coordinator to resolve directly with Dessy (or by
   sequencing after her current PR ships) before any builder touches
   `index.html` for this.
2. **This sandbox's egress proxy blocks direct network access to
   Supabase** (confirmed live: a `curl` to `eoufgmmgwczixfajebhc.
   supabase.co` from this session returned a 403 from the proxy) - so a
   real "before" measurement (payload size/row count/load time), which
   the user explicitly asked to be verified against real measurements
   rather than assumed, needs a live browser/network-capable environment
   or a GitHub Actions dispatch to get real numbers. Estimated the order
   of magnitude from what's actually committed (the ~304,988-raw-listing
   figure already measured for backlog item 4) rather than fabricating a
   precise number, and said so plainly in the backlog entry.

Added as backlog item 6 (urgent, second in the active queue after item 5,
which is already fixed and awaiting only Missy's review/merge) with a
recommended fix direction (server-side filtered/paginated queries scoped
to what's actually being viewed, narrower `select()` columns, a real
cache layer, the `findComparables()` open question flagged for the
implementer) and an explicit dispatch order: (1) resolve the Dessy
sequencing question, (2) a general-purpose builder implements (Supabase
query/architecture work, not visual/layout, despite touching
`index.html`), (3) real before/after measurement, (4) Missy's review, (5)
PR to `main`. See the hand-back message for the exact dispatch list.

## Area/neighborhood filter and Lead Generators: exact raw-string matching bug (backlog item 18)

The user reported directly, with a screenshot, that the Cherven Bryag
Lead Generator on the live site shows only 7 listings - implausibly low
for a real Bulgarian town. Dispatched Missy to investigate before
assuming it was just this one town, the same rigor as backlog item 4's
"Others" province bucket audit.

**Confirmed real and scoped, not a one-town edge case.** Root cause:
`populateAreaFilter()`/`populateLeadGenNeighborhoods()` (`index.html`
~2685, ~2794) build their dropdown/checkbox options straight from raw,
unnormalized `l.area` strings scraped per-portal; the actual filters
(`render()` line 3599, `matchesLeadGenerator()` line 2783) do exact
string comparison. The same real settlement/neighborhood is formatted
differently across portals (кв./жк. prefixes, Cyrillic vs. transliterated
Latin, capitalization), so it silently splits across multiple dropdown
entries and selecting one excludes real listings genuinely in that area.

Cherven Bryag itself: 28 raw listings across 5 portals genuinely in the
town (verified against the town's real coordinates, 43.280635°N,
24.083301°E), split 26/2 between "Червен бряг" and "Cherven Bryag" -
selecting either dropdown entry misses the other. Missy could not
reproduce the exact "7" figure without live `merged_listings` access
(cross-portal dedup and the user's exact checkbox selections both matter,
and Supabase is blocked from this sandbox's egress proxy), but the
mechanism is real and consistent with an undercount landing that low.

**Platform-wide scope, computed against all 8 committed `data/leads_*.
json` files (305,065 listings with a non-empty `area`)**: 481 of 8,507
distinct normalized area keys have more than one raw-string variant,
affecting 179,061 listings (58.7%). Several high-traffic real
neighborhoods (Малинова Долина, Тракия, Кършияка, Христо Смирненски,
Остромила, Виница, Изгрев, Широк център, Кайсиева градина, Бриз,
Възраждане, Овча Купел, Сарафово, Беломорски) split their listings
roughly evenly across 3-5 variants - picking any one dropdown entry shows
only ~20-30% of the area's true count.

Checked whether a normalized key already exists server-side (the
hypothesis I gave Missy going in): partially, and not the piece that
would help here. `listing_city_key()`/`city_key` exists but only
resolves against `BG_CITIES`' 29 major cities - Cherven Bryag isn't on
that list, wrong granularity regardless. `normalize_area()`/
`areas_match()` do already exist in `sync_to_supabase.py` (lines 64-90)
and are trustworthy (already load-bearing for merge-group matching), but
are never stored as a column or exposed to the frontend - the JS
equivalent that used to exist client-side (per `sync_to_supabase.py`'s
own "ported 1:1 from index.html" header comment) was deleted from
`index.html` entirely when the merge step moved server-side. Real,
buildable, smaller-than-from-scratch fix, not a trivial wire-up.

Related bug in the same code path, found while tracing this: `matchesLead
Generator()`'s neighborhood mode never checks `gen.area.city` against a
listing at all - the Lead Generator modal's City field is free text that
does nothing in the actual match logic, and the neighborhood checkbox
list is built from every `l.area` nationwide, not scoped to the typed
city. The modal's stale hint text ("Only Sofia has live listing data
right now") actively misleads users about a still-broken mechanism on a
now-nationwide platform.

Filed as backlog item 18, deliberately numbered last (added at the end
of the list to avoid re-triggering the item-number-renumbering churn that
just required a pass across all six `docs/strategy/*.md` files) but
flagged URGENT with an explicit note to work it immediately after items
6/7, not by its position in the list. Missy (report-only, no Write/Edit
tools by design) could not file this herself - she returned the
suggested entry as response text and I added it. Recommended fix: add an
`area_key` column to `listing_sources`/`merged_listings` (schema + sync
script, reusing `normalize_area()` verbatim), backfill, switch the area
dropdown/Lead Generator neighborhood picker and both match sites to
compare `area_key` instead of raw `l.area`. Dispatched to Bossy.

### 2026-09-22 - Backlog item 18 implemented and self-verified against real data; Missy's actual review still needed (no `Agent` tool this session)

**No `Agent` tool available this session** (confirmed by trying it, per
the standing platform-constraint note in `.claude/agents/bossy.md`) - so
this was implemented directly rather than dispatched to a builder, and
self-verified rigorously (real data, a real functional test against the
actual file, not just "it runs") rather than skipped, following the same
precedent already set for backlog item 5's imoti.net fix in an earlier
no-`Agent` session. **This is explicitly not a substitute for Missy's own
review** - see the hand-back message for the exact dispatch (Missy only;
not auth/security/PII, so Revy's narrower gate doesn't apply).

**Sequencing with Dessy, resolved before touching `index.html`:** at
dispatch time `index.html` had a 554-line uncommitted diff from Dessy's
backlog item 9 listing-detail redesign. Checked git state before editing
rather than assuming either way - by the time backend work was done and
frontend work was about to start, that diff had been committed (locally,
not yet pushed) as `a2685e4`, and `git status` showed a clean working
tree. Built this fix directly on top of her commit rather than layering
in parallel, so no collision risk from working the same file concurrently.

**Backend (`supabase/schema.sql`, `sync_to_supabase.py`):** added an
`area_key` column to both `listing_sources` and `merged_listings`,
computed via `normalize_area()` (reused verbatim, unchanged) in
`build_rows()`, same pattern as `city_key`/`oblast_key`. No separate
backfill script needed - unlike backlog item 5's category fix (which
needed one because that data wasn't due for a fresh scrape/sync anytime
soon), both `scrape.yml` and `scrape-large.yml` already call
`sync_to_supabase.py` at the end of every run and its `upsert()` always
sends the full row payload with `resolution=merge-duplicates`, so the
very next real sync after this ships (scheduled, or a manual
`sync-supabase.yml` dispatch) backfills `area_key` on every row
automatically. Real caveat, same as `city_key`/`oblast_key` before it:
the `alter table` in `schema.sql` needs to actually be run in the
Supabase SQL editor first (this sandbox has no network route to run DDL
itself, per that file's own header) - flagging this plainly rather than
assuming it happens on its own.

Verified against the real committed data, not assumed: reproduced
Missy's exact platform-wide figures independently (8,507 distinct
normalized area keys, 481 with >1 raw variant, 179,061 affected listings,
58.7%) by running the real `normalize_area()` against all 9,246 distinct
raw `area` strings across all 8 `data/leads_*.json` files. Ran the real
`build_rows()` end-to-end against the full real dataset (305,065 raw
listings -> 214,889 merged) and confirmed: every row with a non-empty
`area` gets a non-null `area_key`; Cherven Bryag's 28 real raw listings
(6 portals, not quite Missy's estimated 5, but the same real town) all
resolve to the one shared key `"cherven bryag"` and collapse to 19
correctly-deduped merged listings - previously split 26/2 across two
dropdown entries, undercounting whichever one was picked.

**Frontend (`index.html`):** rather than only wiring the server column
in (which wouldn't take effect until the manual SQL migration + a fresh
sync run both happen, timing this session can't control or verify), also
ported `normalize_area()` to JS as `normalizeArea()` - verified
byte-for-byte identical output against all 9,246 real distinct raw area
strings (zero mismatches) before relying on it. `listingAreaKey(l)`
follows the same "prefer the precomputed server column, fall back to
computing it client-side" pattern `listingCityKey()` already established
for `city_key` - so the fix is effective immediately on page load,
independent of whether the backend migration has landed yet, and
automatically starts using the authoritative server value once it has.
`populateAreaFilter()`/`populateLeadGenNeighborhoods()` now group by
`normalizeArea(l.area)` and show one representative raw label per group -
the most frequent raw string in that group, the same frequency-based
"representative value" precedent `build_rows()`'s own `best.get()`
already follows, just applied to picking a label instead of a row.
`render()`'s area filter and `matchesLeadGenerator()`'s neighborhood
match both compare normalized keys now, not raw strings; the match
additionally normalizes *both* sides so an older saved Lead Generator
whose `neighborhoods` array still holds a pre-fix raw label keeps
matching correctly with no data migration needed. Found and fixed the
same raw-string bug in a third place while tracing this, not called out
by name in the backlog item: the Lead Generator gallery's own mini-map
preview (`renderLeadgenMiniMap()`) had the identical exact-match bug,
which would otherwise have kept showing the old, wrong preview even after
the real filter was fixed.

**Second bug (`gen.area.city` decorative, stale hint text) - wired in,
not just relabeled**, since a real, low-risk fix was reachable: typed
city text now resolves to a `city_key` via the existing Cyrillic
resolvers (`cityKeyFromName`/`cityKeyFromNamePrefix`) plus
`latinCityKeyFromText` (needed because the field's own default value,
"Sofia", is Latin script and the Cyrillic-only resolvers alone return
null for it - caught this with a real test, not assumed). When it
resolves to one of `BG_CITIES`' ~29 major cities, `matchesLeadGenerator()`
now requires that city match too, on top of the area-key match -
verified this prevents a real cross-city false positive (a Sofia-scoped
"Център" search no longer also matches a same-named "Център" area in
Dobrich, which the pre-fix code would have silently included). When it
doesn't resolve (any town outside those ~29, e.g. Cherven Bryag itself),
`cityKey` is left `null` and no city constraint is applied, deliberately -
verified requiring a city match unconditionally would have broken the
exact Cherven Bryag case that motivated this whole fix a second way.
Replaced the stale "Only Sofia has live listing data right now" hint text
with accurate wording.

**Verification method, not just "it runs":** wrote a Node `vm`-based
harness that loads the real `index.html`'s actual script content
(extracted, not hand-copied) into a sandboxed context with minimal
DOM/Supabase/Leaflet stubs, confirmed the whole file still parses and
loads without throwing, then exercised the real functions
(`normalizeArea`, `listingAreaKey`, `areaKeyGroups`, `matchesLeadGenerator`,
`cityKeyFromName`/`latinCityKeyFromText`) with realistic fake listing
data mirroring the actual Cherven Bryag/Sofia-Dobrich-Center scenarios,
and separately against the full real 214,889-row merged dataset (8,507
distinct area keys reproduced exactly, matching the pre-merge raw-level
count). All results matched hand-verified expectations.

**Dispatch, since this session has no `Agent` tool:** Missy's real review
is still needed before this merges - not done here, not claimed as done.
See the hand-back message for the exact ask. Not auth/security/
credentials/personal-data, so Revy's narrower gate doesn't apply by this
session's own read of the standing rule (same read as backlog item 5's
entry above). Opened as a PR (`claude/bg-property-tracker-setup-30c2rp`
-> `main`) for review before merge.
