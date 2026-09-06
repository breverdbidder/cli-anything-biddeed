-- Issue #20049/#20050 — SIGNAL$ section 16 Title Tiers 1-2 STATEWIDE rollout.
--
-- Per-county readiness ledger. The `ship_status` gate from #20045 stays
-- untouched (county content still flows through the internal preview path
-- until Ariel/Steve flip it per county) -- this table is the evidence trail
-- that informs that future decision, not a switch itself.
--
-- Created here (lane B, #20050) with IF NOT EXISTS since lane A (#20049)
-- may create this same table concurrently -- whichever run lands first
-- wins, the other's IF NOT EXISTS is a no-op. One row per county, upserted
-- on every harvest run (last_run advances, cases_with_tier1/instruments_total
-- reflect the latest real count, never a running total that could drift
-- from truth).
create table if not exists public.title_tier_coverage (
  id                bigint generated always as identity primary key,
  county            text not null unique,
  or_platform       text not null,
  tier1_status      text not null default 'blocked',
  tier2_status      text not null default 'blocked',
  cases_with_tier1  integer not null default 0,
  instruments_total integer not null default 0,
  last_run          timestamptz,
  notes             text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists title_tier_coverage_or_platform_idx on public.title_tier_coverage (or_platform);

-- RLS enabled, no anon/authenticated policy (M2) -- service_role only, same
-- pattern as title_tier1_results. Reads happen through the report composer
-- (gate text for uncovered counties) and internal coverage dashboards, both
-- via the service-role Supabase client.
alter table public.title_tier_coverage enable row level security;
