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
