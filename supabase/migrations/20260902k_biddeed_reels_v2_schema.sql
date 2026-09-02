-- BidDeed Reels v2 (issue #19752): parcel-outline imagery + landing page /
-- short-link / QR click path + v2 edit tracking columns.
--
-- Additive-only on top of v1 (#19736)'s winnerdata.biddeed_reels. New table
-- winnerdata.reel_links for the short-link/QR/UTM click path (T3). Three
-- columns added to the EXISTING public.lead_profiles table (found per the
-- issue's explicit "find it; don't create a parallel one" instruction for
-- the reel lead-capture write) -- no parallel leads table created.
--
-- RLS: winnerdata.reel_links follows the same deny-all posture as v1's
-- winnerdata.biddeed_reels (enable RLS, zero policies; access goes through
-- the SECURITY DEFINER RPCs in the companion migration
-- 20260902l_biddeed_reels_v2_rpc.sql). public.lead_profiles already has
-- anon-writable grants/RLS from the existing biddeed.ai lead-capture flow
-- (upsert_lead_full) -- additive columns only, no grant/RLS change needed.

begin;

alter table winnerdata.biddeed_reels
  add column if not exists zw_parcel_id     bigint,
  add column if not exists parcel_geojson   jsonb,
  add column if not exists parcel_outline   boolean,
  add column if not exists aerial_wide_url  text,
  add column if not exists aerial_tight_url text,
  add column if not exists short_code       text,
  add column if not exists short_url        text,
  add column if not exists qr_url           text,
  add column if not exists landing_url      text,
  add column if not exists video_v2_url     text,
  add column if not exists edit_version     integer not null default 2;

create unique index if not exists biddeed_reels_short_code_uidx
  on winnerdata.biddeed_reels(short_code) where short_code is not null;

create table if not exists winnerdata.reel_links (
  id            uuid primary key default gen_random_uuid(),
  code          text not null unique,
  reel_id       uuid not null references winnerdata.biddeed_reels(id),
  target        text not null,
  utm_source    text,
  utm_medium    text,
  utm_campaign  text,
  clicks        integer not null default 0,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

alter table winnerdata.reel_links enable row level security;

comment on table winnerdata.reel_links is
  'BidDeed Reels v2 (issue #19752) short-link table. biddeed.ai/r/{code} '
  '302s to target with utm_* appended and increments clicks. No policies -- '
  'deny-all for anon/authenticated; access goes through '
  'public.resolve_reel_link() (SECURITY DEFINER).';

alter table public.lead_profiles
  add column if not exists case_number  text,
  add column if not exists utm_source   text,
  add column if not exists utm_medium   text,
  add column if not exists utm_campaign text;

commit;
