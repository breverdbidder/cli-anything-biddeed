-- CI Agent Memory + Self-Behavior Tracker: persistent cross-session memory
-- for the competitive intelligence pipeline (2 tables). Non-goal: does not
-- touch gold_standard_*, insights, multi_county_auctions, or taxi_meter_*.
begin;

-- ============================================================
-- Table 1 — persistent cross-session observations
-- ============================================================

create table if not exists public.ci_agent_memory (
  id              uuid primary key default gen_random_uuid(),
  competitor      text not null,
  memory_type     text not null check (memory_type in ('update_pattern','noise_signal','alert_threshold','source_quality','competitive_moat','monitoring_rule')),
  observation     text not null,
  confidence      numeric(3,2) default 0.5 check (confidence >= 0 and confidence <= 1),
  confirmed_at    timestamptz[] default array[]::timestamptz[],
  contradicted_at timestamptz[] default array[]::timestamptz[],
  source_url      text,
  first_seen      timestamptz default now(),
  last_evaluated  timestamptz default now(),
  is_active       boolean default true,
  created_by      text default 'ci_agent' check (created_by in ('ci_agent','ariel_correction'))
);

create index if not exists ci_agent_memory_competitor_idx on public.ci_agent_memory(competitor, memory_type);
create index if not exists ci_agent_memory_active_idx on public.ci_agent_memory(is_active) where is_active = true;

alter table public.ci_agent_memory enable row level security;
alter table public.ci_agent_memory force row level security;

revoke all on public.ci_agent_memory from anon, authenticated;

drop policy if exists ci_agent_memory_service_all on public.ci_agent_memory;
create policy ci_agent_memory_service_all
  on public.ci_agent_memory
  for all
  to service_role
  using (true)
  with check (true);

-- ============================================================
-- Table 2 — run log + human feedback
-- ============================================================

create table if not exists public.ci_agent_runs (
  id                 uuid primary key default gen_random_uuid(),
  run_at             timestamptz default now(),
  competitor         text not null,
  triggered_by       text default 'schedule' check (triggered_by in ('schedule','manual','threshold_alert')),
  changes_detected   boolean default false,
  change_magnitude   text check (change_magnitude in ('none','minor','moderate','major')),
  raw_findings       jsonb,
  report_generated   boolean default false,
  report_url         text,
  alert_sent         boolean default false,
  ariel_reviewed     boolean default false,
  ariel_verdict      text check (ariel_verdict in ('accurate','partially_accurate','wrong')),
  ariel_correction   text,
  correction_applied boolean default false,
  agent_confidence   numeric(3,2) check (agent_confidence >= 0 and agent_confidence <= 1),
  memories_used      text[] default array[]::text[],
  memories_updated   text[] default array[]::text[]
);

alter table public.ci_agent_runs enable row level security;
alter table public.ci_agent_runs force row level security;

revoke all on public.ci_agent_runs from anon, authenticated;

drop policy if exists ci_agent_runs_service_all on public.ci_agent_runs;
create policy ci_agent_runs_service_all
  on public.ci_agent_runs
  for all
  to service_role
  using (true)
  with check (true);

commit;
