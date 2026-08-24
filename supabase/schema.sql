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
