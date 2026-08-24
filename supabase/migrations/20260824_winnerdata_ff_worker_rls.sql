-- Winner Data FF Worker v1 (issue #19392, comments 5390376020 / 5390411245)
--
-- Live-verified before writing this (2026-08-24): the schema rename
-- summitleads -> winnerdata never landed (grep of pipelines/winnerdata +
-- scripts/summitleads_pipeline.py, both hardcode `summitleads.*`; live
-- `select ... from summitleads.leads` returns 39 rows, `winnerdata.leads`
-- errors "Invalid schema"). This migration targets the REAL schema name,
-- summitleads, not the winnerdata name used in the issue's prose.
--
-- Also live-verified: `summitleads.lead_properties` does not exist anywhere
-- in information_schema. The real per-lead property/auction enrichment path
-- is the view summitleads.v_producer_intake (added 2026-08-23, joins leads
-- -> multi_county_auctions -> fl_parcels). The FF Worker reads that view,
-- not a lead_properties table.
--
-- Schema-change approval in the issue was granted for exactly one new
-- object: ff_responses. This migration creates only that table, plus RLS
-- policies (also explicitly autonomous per CLAUDE.md never_ask_ariel) on
-- ff_responses and on the two existing tables the Worker must read/write
-- (leads, binds). No other schema object is touched.
--
-- Every summitleads table currently has relrowsecurity=true with ZERO
-- policies (verified via pg_policies) -- i.e. deny-all for anon/authenticated
-- today. This migration adds narrow, single-tenant-scoped SELECT/INSERT/
-- UPDATE policies for the anon role (the Worker embeds the anon key in
-- source, matching worker-biddeed-staging's existing pattern at
-- src/worker.js:37 -- RLS is what turns that shared key into a safe
-- per-tenant boundary). org_id is hardcoded to the single live org
-- (Protection Partners, 032f4717-545f-4a18-b48b-28ea4257699d) because v1 is
-- explicitly single-tenant scope (issue body: "SCOPED, not the multi-tenant
-- spec") -- there is no second org row to scope against yet, and the Worker
-- never accepts org_id from the client, so this is not a placeholder that
-- silently breaks multi-tenant later; it is deliberately the tightest policy
-- that satisfies today's actual tenant count. Generalizing to a claims-based
-- org_id is explicit follow-up work for the (out-of-scope) multi-tenant spec.

-- ── ff_responses ────────────────────────────────────────────────────────────
-- Columns per the issue spec: lead_id, property_id, field, value, updated_by,
-- updated_at. org_id is an addition beyond the spec's literal column list --
-- required to make the org-scoped RLS the issue's SECURITY section demands
-- enforceable at the row level without a join-based policy. Documented here
-- as the one deviation from the spec's exact column list.
create table if not exists summitleads.ff_responses (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references summitleads.organizations(org_id),
  lead_id uuid not null references summitleads.leads(lead_id),
  property_id text,
  field text not null,
  value text,
  updated_by text,
  updated_at timestamptz not null default now()
);

create index if not exists ff_responses_lead_id_idx on summitleads.ff_responses(lead_id);
create index if not exists ff_responses_org_id_idx on summitleads.ff_responses(org_id);

alter table summitleads.ff_responses enable row level security;

-- ── grants (GRANT is necessary but not sufficient -- RLS policies below are
--    the actual gate; every other summitleads table already carries broad
--    anon GRANTs with zero policies, i.e. dead-but-inert grants, so matching
--    that existing pattern rather than introducing a new grant shape) ──────
grant usage on schema summitleads to anon, authenticated;
grant select on summitleads.leads to anon;
grant select on summitleads.v_producer_intake to anon;
grant select, insert on summitleads.binds to anon;
grant select, insert, update on summitleads.ff_responses to anon;

-- ── RLS: leads (SELECT only -- the Worker never writes leads) ─────────────
drop policy if exists ff_worker_anon_select on summitleads.leads;
create policy ff_worker_anon_select on summitleads.leads
  for select
  to anon
  using (org_id = '032f4717-545f-4a18-b48b-28ea4257699d'::uuid);

-- ── RLS: binds (portal bind-outcome recording, POST /portal/bind) ─────────
drop policy if exists ff_worker_anon_select on summitleads.binds;
create policy ff_worker_anon_select on summitleads.binds
  for select
  to anon
  using (org_id = '032f4717-545f-4a18-b48b-28ea4257699d'::uuid);

drop policy if exists ff_worker_anon_insert on summitleads.binds;
create policy ff_worker_anon_insert on summitleads.binds
  for insert
  to anon
  with check (org_id = '032f4717-545f-4a18-b48b-28ea4257699d'::uuid);

-- ── RLS: ff_responses (POST /ff/:lead_id persists producer-entered fields) ─
drop policy if exists ff_worker_anon_select on summitleads.ff_responses;
create policy ff_worker_anon_select on summitleads.ff_responses
  for select
  to anon
  using (org_id = '032f4717-545f-4a18-b48b-28ea4257699d'::uuid);

drop policy if exists ff_worker_anon_insert on summitleads.ff_responses;
create policy ff_worker_anon_insert on summitleads.ff_responses
  for insert
  to anon
  with check (org_id = '032f4717-545f-4a18-b48b-28ea4257699d'::uuid);

drop policy if exists ff_worker_anon_update on summitleads.ff_responses;
create policy ff_worker_anon_update on summitleads.ff_responses
  for update
  to anon
  using (org_id = '032f4717-545f-4a18-b48b-28ea4257699d'::uuid)
  with check (org_id = '032f4717-545f-4a18-b48b-28ea4257699d'::uuid);
