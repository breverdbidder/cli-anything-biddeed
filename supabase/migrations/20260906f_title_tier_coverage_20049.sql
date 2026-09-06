-- Issue #20049 — Title Tiers 1-2 STATEWIDE (lane A): per-county readiness tracker.
--
-- One row per FL county tracking Official Records platform + Title Tier
-- 1/2 harvest coverage, so the statewide rollout has a durable, queryable
-- record of what's been attempted, what worked, and what didn't (never a
-- silent skip — a county with a real blocker gets a row with notes, not no
-- row at all).
create table if not exists public.title_tier_coverage (
  id                   bigint generated always as identity primary key,
  county               text not null unique,
  or_platform          text,
  tier1_status         text not null default 'not_started',
  tier2_status         text not null default 'not_started',
  cases_with_tier1     integer not null default 0,
  instruments_total    integer not null default 0,
  last_run             timestamptz,
  notes                text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);

create index if not exists title_tier_coverage_county_idx on public.title_tier_coverage (county);

-- RLS enabled, no anon/authenticated policy (M2) — service_role only, same
-- pattern as title_tier1_results.
alter table public.title_tier_coverage enable row level security;
