-- Schema for the Supabase migration (see sync_to_supabase.py and index.html's
-- data layer). Run this once in the Supabase SQL editor for the project -
-- there is no automated path to run it from CI, since applying DDL needs
-- direct database access this project's sandbox has no network route to.
--
-- Two tables:
--   listing_sources  - one row per raw scraped listing per portal. Same
--     shape as today's data/leads_*.json entries, written fresh on every
--     scrape by sync_to_supabase.py (never edited by hand).
--   merged_listings  - the cross-portal-deduped view the frontend actually
--     queries. Primary key is a deterministic hash of the sorted set of
--     member (portal, source_id) pairs, NOT "whichever source scores
--     highest" (today's client-side approach) - a group's identity only
--     changes when its actual membership changes, so bookmarked
--     #/listing/<id> links stay stable as scores drift day to day.
--
-- Both tables are public-read (SELECT) via the anon/publishable key with
-- Row Level Security; only the secret/service-role key (used solely by
-- sync_to_supabase.py in GitHub Actions, never shipped to the browser) can
-- write, since it bypasses RLS entirely.

create table if not exists listing_sources (
  portal                  text not null,
  source_id               text not null,
  url                     text,
  photo                   text,
  price_eur               integer,
  sqm                     integer,
  area                    text,
  title                   text,
  description             text,
  category                text,
  category_confidence     text,
  type_bucket             text,
  city_key                text,
  lat                     double precision,
  lng                     double precision,
  price_per_sqm           integer,
  price_history           jsonb,
  photos                  jsonb,
  price_drop_count        integer,
  drop_pct                numeric,
  days_on_market          integer,
  score                   integer,
  source_status           text,
  removed_at              timestamptz,
  area_avg_price_per_sqm  integer,
  pct_vs_area_avg         numeric,
  site_updated_at         timestamptz,
  site_posted_at          timestamptz,
  merged_id               text,
  updated_at              timestamptz not null default now(),
  primary key (portal, source_id)
);

create index if not exists listing_sources_merged_id_idx on listing_sources (merged_id);

create table if not exists merged_listings (
  id                      text primary key,
  portal                  text not null,
  url                     text,
  photo                   text,
  photos                  jsonb,
  price_eur               integer,
  sqm                     integer,
  area                    text,
  title                   text,
  description             text,
  category                text,
  category_confidence     text,
  type_bucket             text,
  city_key                text,
  lat                     double precision,
  lng                     double precision,
  price_per_sqm           integer,
  price_history           jsonb,
  price_drop_count        integer,
  drop_pct                numeric,
  days_on_market          integer,
  score                   integer,
  status                  text not null,
  member_count            integer not null default 1,
  member_portals          text[] not null default '{}',
  area_avg_price_per_sqm  integer,
  pct_vs_area_avg         numeric,
  site_updated_at         timestamptz,
  site_posted_at          timestamptz,
  updated_at              timestamptz not null default now()
);

create index if not exists merged_listings_price_eur_idx on merged_listings (price_eur);
create index if not exists merged_listings_sqm_idx on merged_listings (sqm);
create index if not exists merged_listings_area_idx on merged_listings (area);
create index if not exists merged_listings_city_key_idx on merged_listings (city_key);
create index if not exists merged_listings_type_bucket_idx on merged_listings (type_bucket);
create index if not exists merged_listings_score_idx on merged_listings (score desc);
create index if not exists merged_listings_days_on_market_idx on merged_listings (days_on_market desc);
create index if not exists merged_listings_drop_pct_idx on merged_listings (drop_pct desc);
create index if not exists merged_listings_status_idx on merged_listings (status);

alter table listing_sources enable row level security;
alter table merged_listings enable row level security;

drop policy if exists "public read" on listing_sources;
create policy "public read" on listing_sources for select using (true);

drop policy if exists "public read" on merged_listings;
create policy "public read" on merged_listings for select using (true);

-- No insert/update/delete policies for anon/authenticated on purpose: only
-- the secret key (used server-side by sync_to_supabase.py) can write, and
-- it bypasses RLS entirely, so it needs no policy of its own.

-- Columns added after the tables already existed in the live project -
-- "create table if not exists" above only creates from scratch, it can't
-- retroactively add a column to a table that's already there. Kept here
-- (not folded into the create table statements) so this whole file stays
-- safe to paste again in the SQL editor at any point: a fresh project gets
-- these columns from the create table statements directly, an existing one
-- picks them up here, idempotently either way.
alter table listing_sources add column if not exists category_confidence text;
alter table merged_listings add column if not exists category_confidence text;

-- Oblast (province) key, computed server-side by sync_to_supabase.py's
-- listing_oblast_key() the same way city_key is - see that function's
-- comment for the fallback chain (city->oblast mapping first, then
-- oblast-name text matching for listings with no city match at all).
alter table listing_sources add column if not exists oblast_key text;
alter table merged_listings add column if not exists oblast_key text;
create index if not exists merged_listings_oblast_key_idx on merged_listings (oblast_key);

-- Normalized area/neighborhood key, computed server-side by sync_to_
-- supabase.py's normalize_area() (backlog item 18). The area filter and
-- Lead Generator neighborhood picker used to compare raw, unnormalized
-- per-portal l.area strings directly - the same real settlement or
-- neighborhood is formatted differently portal to portal (кв./жк. prefix,
-- Cyrillic vs. transliterated Latin, capitalization), so it silently split
-- across multiple dropdown entries and picking one excluded real listings
-- genuinely in that area (confirmed platform-wide: 481 of 8,507 distinct
-- normalized area keys had >1 raw-string variant, affecting 58.7% of all
-- listings with a non-empty area). normalize_area() already existed and
-- was already trustworthy - it's load-bearing for group_listings()'s own
-- merge-group matching above - just never stored as a column before.
alter table listing_sources add column if not exists area_key text;
alter table merged_listings add column if not exists area_key text;
create index if not exists merged_listings_area_key_idx on merged_listings (area_key);

-- Manual reminders (backlog stage 8): a user-set note + date attached to a
-- listing, checked once daily by check_reminders.py (see that script and
-- .github/workflows/check-reminders.yml) and surfaced on the Dashboard.
-- listing_title/listing_portal are a snapshot taken when the reminder is
-- created, not a foreign key - merged_listings rows get deleted outright
-- when a group's membership changes or a listing drops out entirely (see
-- sync_to_supabase.py's delete_stale_merged_listings()), and a reminder
-- for a listing that's since vanished should still show something
-- meaningful rather than a broken reference or silently disappearing.
--
-- Unlike listing_sources/merged_listings above, this table IS writable by
-- the anon/publishable key - insert (create a reminder) and a full update
-- (dismiss it, from the browser, with no login system to scope it to a
-- single user). That's a real, deliberate exception to this file's normal
-- read-only-anon rule, accepted for now because the stakes are low - a
-- personal date+note, not the saved-listings pipeline the user explicitly
-- drew the line at (see backlog #62: saved listings/lead generators move
-- to Supabase Auth with per-user RLS specifically BECAUSE that data is
-- higher-stakes and multi-user-relevant). Anyone who finds the public anon
-- key could create, read, or dismiss rows here today; reminders should
-- move under the same per-user auth once #62 lands, not stay exposed
-- indefinitely. notified_at is only ever written by check_reminders.py's
-- service-role key (bypasses RLS, like sync_to_supabase.py), so it needs
-- no browser-facing policy - the anon update policy touching it too is a
-- known, accepted gap (worst case: someone suppresses or re-triggers their
-- own already-low-stakes notification), not column-scoped for the sake of
-- keeping this migration simple.
create table if not exists reminders (
  id             bigint generated always as identity primary key,
  listing_id     text,
  listing_title  text,
  listing_portal text,
  note           text not null,
  remind_at      timestamptz not null,
  dismissed      boolean not null default false,
  notified_at    timestamptz,
  created_at     timestamptz not null default now()
);

create index if not exists reminders_remind_at_idx on reminders (remind_at) where not dismissed;
create index if not exists reminders_listing_id_idx on reminders (listing_id) where not dismissed;

alter table reminders enable row level security;

drop policy if exists "public read" on reminders;
create policy "public read" on reminders for select using (true);

drop policy if exists "public insert" on reminders;
create policy "public insert" on reminders for insert with check (true);

drop policy if exists "public dismiss" on reminders;
create policy "public dismiss" on reminders for update using (true) with check (true);

-- Per-user data (backlog #62): saved listings, lead generators, and
-- reminders (see the migration below) all move here from localStorage or
-- the open, login-less anon policies above, behind Supabase Auth + row-
-- level security scoped to auth.uid(). One real account exists today, but
-- every policy is written as genuine per-user isolation from the start -
-- auth.uid() = user_id, never a shared/open table - so adding a second
-- (paying) subscriber later needs no RLS rework, just a second row in
-- auth.users. "for all" covers select/insert/update/delete with one
-- policy per table rather than four near-identical ones.
--
-- user_id defaults to auth.uid() so an authenticated insert doesn't need
-- to name it explicitly (index.html's inserts below rely on this) - and
-- because that default expression evaluates server-side against the
-- request's own verified JWT, a client can never override it to claim a
-- row as belonging to a different user.
create table if not exists saved_listings (
  id          bigint generated always as identity primary key,
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  listing_id  text not null,
  created_at  timestamptz not null default now(),
  unique (user_id, listing_id)
);

create index if not exists saved_listings_user_id_idx on saved_listings (user_id);

alter table saved_listings enable row level security;

drop policy if exists "own rows only" on saved_listings;
create policy "own rows only" on saved_listings for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- The whole lead-generator object (filters + whichever area-mode config it
-- uses - neighborhoods, or center+radius, or a drawn polygon) is stored
-- as-is in `data`, mirroring exactly what saveLeadGenFromModal() already
-- builds client-side today - one flexible jsonb column rather than
-- exploding a shape-varying, still-evolving structure into many nullable
-- columns. `id` keeps the same client-generated "lg_<timestamp>_<random>"
-- string the app has always used (not a fresh server-generated key), so
-- migrating existing localStorage generators is a straight insert with no
-- id remapping.
create table if not exists lead_generators (
  id          text primary key,
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name        text not null,
  data        jsonb not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists lead_generators_user_id_idx on lead_generators (user_id);

alter table lead_generators enable row level security;

drop policy if exists "own rows only" on lead_generators;
create policy "own rows only" on lead_generators for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Precomputed "first seen" timestamp (backlog item 6 slice-1 regression
-- fix), populated server-side by sync_to_supabase.py's build_rows() from
-- the same best-source price_history[0].date the frontend's own
-- listingFirstSeenDate() already reads - just moved server-side and
-- stored as a real column instead of derived client-side from
-- price_history, which slice 1 (PR #203) dropped from the bulk
-- merged_listings list-view fetch (MERGED_LISTINGS_BULK_COLUMNS). Without
-- this column, every Lead Generator's "new since last check" badge
-- (computeLeadGenCounts() -> listingFirstSeenDate()) has silently read
-- stale/zero since slice 1 shipped, since l.price_history is undefined in
-- that fetch. listing_sources also gets the column (same derivation, off
-- that row's own price_history) for consistency, though the frontend only
-- reads it off merged_listings today.
alter table listing_sources add column if not exists first_seen_at timestamptz;
alter table merged_listings add column if not exists first_seen_at timestamptz;

-- reminders moves under the same per-user auth, for the same reason - see
-- the anon policies above being dropped. user_id is nullable (a reminder
-- created before this migration ran has none yet, until the one-time
-- migration in index.html backfills it for the account that owns it) but
-- every policy below still requires auth.uid() = user_id, so a null-owner
-- row is simply invisible and unreachable to everyone rather than cross-
-- user-visible once the old public policies are gone - a safe failure
-- mode, not a hole. check_reminders.py's service-role key bypasses RLS
-- entirely (like sync_to_supabase.py), so none of this affects it.
alter table reminders add column if not exists user_id uuid references auth.users(id) on delete cascade default auth.uid();
create index if not exists reminders_user_id_idx on reminders (user_id);

drop policy if exists "public read" on reminders;
drop policy if exists "public insert" on reminders;
drop policy if exists "public dismiss" on reminders;
drop policy if exists "own rows only" on reminders;
create policy "own rows only" on reminders for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
