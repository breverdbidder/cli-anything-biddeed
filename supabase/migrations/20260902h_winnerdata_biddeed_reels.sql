-- BidDeed Reels pipeline v1 (issue #19736).
--
-- Daily auto-generated 9:16 short-form reels for third-party auction wins
-- (statewide). This pipeline GENERATES and STAGES reels only -- it never
-- posts to a social platform and never sends anything to anyone (guardrail
-- in the issue body). Every row lands at status='pending_approval' (or
-- 'error' with error_text on a per-row failure); nothing downstream reads
-- this table for outbound sends.
--
-- Deviation from the issue's literal column description: "case_number (FK to
-- auction_buyer_sightings by case_number+county)" is implemented as two plain
-- text columns, not a real FOREIGN KEY. public.auction_buyer_sightings has no
-- unique constraint on (case_number, county) today (verified via
-- pg_constraint -- only a PK on id and a unique on mca_id exist), and adding
-- one is a schema change to a table this issue does not name (M5 scope
-- discipline). The soft reference is enough for this pipeline's own join
-- needs; a hard FK can be added later if auction_buyer_sightings gets that
-- constraint for its own reasons.
--
-- RLS: matches the existing winnerdata convention (see
-- 20260824_winnerdata_ff_worker_rls.sql's own note) -- enable RLS, add ZERO
-- policies. No anon/authenticated GRANTs are issued below, so only
-- service_role/postgres (which bypass RLS) can read or write this table.

begin;

create table if not exists winnerdata.biddeed_reels (
  id               uuid primary key default gen_random_uuid(),

  -- Soft reference to public.auction_buyer_sightings (see note above)
  case_number      text not null,
  county           text not null,

  sale_type        text,
  auction_date     date not null,
  property_address text not null,

  -- Parcel join (public.zw_parcels)
  parcel_id        text,
  sold_amount      numeric,
  assessed_value   numeric,
  delta_pct        numeric,

  -- T2 imagery
  aerial_url       text,
  street_url       text,

  -- T3 condition scoring
  condition_json   jsonb,
  condition_score  integer check (condition_score is null or (condition_score between 0 and 100)),

  -- T4 script + caption
  script_text      text,
  caption_text     text,
  hashtags         text[],

  -- T5 voiceover
  voiceover_source text check (voiceover_source is null or voiceover_source in ('tts','ariel')),
  audio_url        text,

  -- T6 video assembly
  video_url        text,
  duration_sec     numeric,

  -- T7 ranking
  rank_score       numeric,
  shortlisted      boolean not null default false,

  -- Lifecycle
  status           text not null default 'generated'
    check (status in ('generated','pending_approval','approved','rejected','posted','error')),
  error_text       text,

  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),

  unique (case_number, county)
);

create index if not exists biddeed_reels_auction_date_idx
  on winnerdata.biddeed_reels(auction_date);

create index if not exists biddeed_reels_status_idx
  on winnerdata.biddeed_reels(status);

create index if not exists biddeed_reels_shortlisted_idx
  on winnerdata.biddeed_reels(auction_date, shortlisted)
  where shortlisted = true;

alter table winnerdata.biddeed_reels enable row level security;
-- No policies -- deny-all for anon/authenticated, matching every other
-- winnerdata table's default-deny posture. service_role/postgres bypass RLS.

comment on table winnerdata.biddeed_reels is
  'BidDeed Reels pipeline v1 (issue #19736). One row per third-party auction '
  'win considered for a short-form reel. Generation only -- status never '
  'progresses past pending_approval/error from this pipeline; approved/'
  'rejected/posted are set by a human review step (LMS, separate issue) or '
  'by Ariel directly. No buyer/bidder/person name is ever written into '
  'script_text/caption_text/hashtags (guardrail, enforced in the generator, '
  'not the schema).';

commit;
