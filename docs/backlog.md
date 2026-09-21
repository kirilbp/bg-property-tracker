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

## 2. Login broken - IN PROGRESS, blocked on the user

Valid credentials rejected on imotenradar.com. Confirmed so far (see
session history / `docs/decisions.md`): `index.html` and the GitHub
Actions secrets point at the same `SUPABASE_URL`
(`eoufgmmgwczixfajebhc.supabase.co`); that project's REST API returns
real listing data fine; but its Auth admin API (`/auth/v1/admin/users`)
reports **0 registered accounts**, both before and after the Supabase
Pro upgrade - strong evidence the user's real account lives in a
different Supabase project (they specifically flagged a "Paris" project
in another organisation as a candidate). Cannot be resolved further from
here: needs the user to open their Supabase dashboard, confirm which
project owns Project Reference `eoufgmmgwczixfajebhc`, and check
Authentication -> Users there directly. Do not change any auth wiring
until the user confirms which project is correct - this is an auth
change, which the standing rules require asking about anyway.

## 3. Supabase Pro plan - PENDING

Free-tier limits are gone, daily backups are running. Revisit anything
designed around the old 500 MB limit (retry/backoff tuned for storage-
related 500s, any code that assumed a small dataset for cost reasons).

## 4. Motivation score rework - DONE

Shipped in PR #162: 5-component formula (relisted, distinct reductions,
size of drop, days on market, below area average), rescale option A when
area-average is unavailable, Hot/Warm thresholds recalibrated to 40/15
against real data distribution. Confirmed live.

## 5. Stats panel redesign - BLOCKED

Blocked until Nosy's `docs/property-filter-spec.md` exists.

## 6. Everything from Nosy's spec - PENDING

Prioritise by value to a paying investor once the spec lands. Turn each
replicable feature into its own backlog item here.

## Parked - do not start

- **Rental scraping.** Investigated: under 400 usable listings nationwide
  (imoti.bg ~394, bazar.bg ~444 but those are flatshares/rooms, not whole
  properties) - not enough for reliable yield. Revisit only if imoti.net's
  or imot.bg's real listing counts become readable (their rental sections
  exist but the count couldn't be extracted last time).
