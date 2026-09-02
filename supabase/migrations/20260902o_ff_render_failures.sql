-- issue #19751: 1101 "Worker threw exception" on /ff/<lead_id> (Cloudflare
-- Error 1101) when the Supabase fetch inside workers/winnerdata-ff fails
-- (observed live during the 2026-09-01 20:20/20:30 UTC Postgres restart
-- events). The Worker now catches that failure and renders a branded 503
-- instead of crashing -- this migration adds where it logs the failure.
--
-- winnerdata.ff_render_failures: RLS enabled, deliberately ZERO anon
-- policies (same deny-all-by-default pattern as every other winnerdata
-- table -- see 20260824_winnerdata_ff_worker_rls.sql's header note). The
-- Worker holds no secrets (wrangler.toml: "No [vars] -- this Worker holds
-- no secrets") and the codebase's own documented architecture (index.js
-- "DB ACCESS" header comment) already rejected embedding a service-role key
-- in this Worker's bundled source in favor of narrow SECURITY DEFINER RPC
-- functions called with the anon key -- ff_log_render_failure() below is
-- that same pattern applied to this write, not a literal service-role key
-- as the issue body's wording suggested. See docs/spec/19751.md for the
-- explicit deviation note.

create table if not exists winnerdata.ff_render_failures (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid,
  error text not null,
  status int not null default 503,
  created_at timestamptz not null default now()
);

create index if not exists ff_render_failures_lead_id_idx on winnerdata.ff_render_failures(lead_id);
create index if not exists ff_render_failures_created_at_idx on winnerdata.ff_render_failures(created_at);

alter table winnerdata.ff_render_failures enable row level security;
-- No anon/authenticated policies -- deny-all at the table. Reads are an
-- operator/service_role concern (dashboard, ops query), never the Worker.

-- SECURITY DEFINER accessor: the Worker's only write path to this table.
-- Takes no org_id -- this is an ops/reliability log, not tenant data, and
-- the Worker is single-tenant (ORG_ID hardcoded to Protection Partners)
-- so there is nothing to scope against. error text is always a message this
-- Worker itself generated (fetch/render exception .message), never raw
-- user input, so no additional sanitization boundary is needed here beyond
-- what index.js already does before calling this.
create or replace function public.ff_log_render_failure(
  p_lead_id uuid, p_error text, p_status int default 503
)
returns void
language sql
security definer
set search_path = public, winnerdata
as $$
  insert into winnerdata.ff_render_failures (lead_id, error, status)
  values (p_lead_id, p_error, coalesce(p_status, 503));
$$;

revoke all on function public.ff_log_render_failure(uuid, text, int) from public;
grant execute on function public.ff_log_render_failure(uuid, text, int) to anon;
