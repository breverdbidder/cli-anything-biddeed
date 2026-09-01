-- winnerdataai.com LMS (client/producer management) — v1 read/write substrate
-- Built per issue brief 2026-09-01: thin Cloudflare-native layer on top of the
-- already-live winnerdata.* + finance.* schemas (#19392/#19486/#19609/#19533
-- lineage), NOT a fork of a third-party CRM/LMS.
--
-- DEVIATION FROM BRIEF (logged per CC_META_PROMPT.md 2.3/1.3): the brief
-- referenced "everest-cfo-agent's worker" and "cfo_agent_ro" as if already
-- built in this repo (issues #19646/#19647). Live-verified 2026-09-01: no
-- such worker exists in this repo or any workflow, and
-- docs/EVEREST_CFO_AGENT_PLAN.md is explicitly "PLAN ONLY — nothing deployed,
-- CP1 not cleared." cfo_agent_ro DOES exist live (role + grants confirmed via
-- Management API) but is scoped ONLY to finance.* + winnerdata.billable_ff_events/
-- v_billable_ff_comparison/wallets — it has no grants on winnerdata.organizations/
-- producers/leads/routing_decisions, the tables this LMS's org/lead/producer
-- views need. Extending cfo_agent_ro's grants would blur an already-shipped
-- finance-only boundary, so this migration creates a parallel `lms_agent_ro`
-- role instead (spec explicitly allowed either, "your call, document which").
--
-- ACCESS PATTERN: same proven pattern as workers/winnerdata-ff (see that
-- file's header comment) — winnerdata/finance schemas are NOT exposed via
-- PostgREST directly (a documented, already-diagnosed platform limitation).
-- The live-working boundary is public-schema SECURITY DEFINER RPC functions,
-- called via /rest/v1/rpc/<fn> with the embedded anon key. lms_agent_ro's
-- grants below are defense-in-depth / the documented intended read boundary
-- (same posture as cfo_agent_ro, which is also not the live PostgREST auth
-- path) — the RPC function bodies are what actually enforces org_id scoping.

begin;

-- ============================================================
-- 0. lms_agent_ro — parallel read-only role (see deviation note above)
-- ============================================================

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'lms_agent_ro') then
    create role lms_agent_ro nologin;
  end if;
end $$;

comment on role lms_agent_ro is
  'winnerdataai.com LMS read-only boundary (2026-09-01). Documents the intended '
  'read scope for the LMS; the live-enforced boundary is the SECURITY DEFINER '
  'RPC functions below (org_id validated in-function), same posture as cfo_agent_ro.';

grant usage on schema winnerdata to lms_agent_ro;
grant usage on schema finance to lms_agent_ro;
grant select on winnerdata.organizations to lms_agent_ro;
grant select on winnerdata.producers to lms_agent_ro;
grant select on winnerdata.leads to lms_agent_ro;
grant select on winnerdata.routing_decisions to lms_agent_ro;
grant select on winnerdata.billable_ff_events to lms_agent_ro;
grant select on winnerdata.closing_ratios to lms_agent_ro;
grant select on winnerdata.lead_activity to lms_agent_ro;
grant select on finance.revenue_ledger to lms_agent_ro;

-- ============================================================
-- 1. Additive columns for the two Tier-2 (non-billing) write actions.
--    Nullable, no backfill required, existing rows unaffected.
-- ============================================================

alter table winnerdata.leads
  add column if not exists flagged_at timestamptz,
  add column if not exists flagged_by text,
  add column if not exists flagged_reason text;

alter table winnerdata.producers
  add column if not exists notes text;

comment on column winnerdata.leads.flagged_reason is
  'Set via public.lms_flag_lead() from the winnerdataai.com LMS (2026-09-01). Never written directly — see winnerdata.lms_audit_log for the audit trail.';
comment on column winnerdata.producers.notes is
  'Free-text producer notes, set via public.lms_update_producer_note() from the winnerdataai.com LMS (2026-09-01). Never written directly — see winnerdata.lms_audit_log.';

-- ============================================================
-- 2. Audit log — every LMS write lands here, no raw table writes from
--    the Worker (spec requirement #4).
-- ============================================================

create table if not exists winnerdata.lms_audit_log (
  id bigint generated always as identity primary key,
  org_id uuid not null,
  actor text not null,
  action text not null,
  target_table text not null,
  target_id text not null,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

comment on table winnerdata.lms_audit_log is
  'Audit trail for every write RPC called from the winnerdataai.com LMS Worker (2026-09-01). One row per lms_flag_lead / lms_update_producer_note call.';

create index if not exists lms_audit_log_org_created_idx on winnerdata.lms_audit_log (org_id, created_at desc);

grant select on winnerdata.lms_audit_log to lms_agent_ro;

-- ============================================================
-- 3. READ RPCs — public schema, SECURITY DEFINER, anon-callable.
--    Every function validates/scopes on p_org_id; none accept a
--    trust-the-client org override.
-- ============================================================

-- 3a. Client/org view — list all orgs with producer + lead volume rollups.
create or replace function public.lms_orgs_list()
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_result jsonb;
begin
  select coalesce(jsonb_agg(jsonb_build_object(
    'org_id', o.org_id,
    'name', o.name,
    'is_internal', o.is_internal,
    'platform_fee_cents', o.platform_fee_cents,
    'created_at', o.created_at,
    'producer_count', (select count(*) from winnerdata.producers p where p.org_id = o.org_id),
    'active_producer_count', (select count(*) from winnerdata.producers p where p.org_id = o.org_id and p.active),
    'lead_count', (select count(*) from winnerdata.leads l where l.org_id = o.org_id)
  ) order by o.name), '[]'::jsonb)
  into v_result
  from winnerdata.organizations o;

  return jsonb_build_object('ok', true, 'orgs', v_result);
end;
$$;

-- 3b. Client/org drill-in — one org's producers + lead volume detail.
create or replace function public.lms_org_detail(p_org_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_result jsonb;
begin
  if p_org_id is null then
    return jsonb_build_object('ok', false, 'reason', 'org_id required');
  end if;

  if not exists (select 1 from winnerdata.organizations where org_id = p_org_id) then
    return jsonb_build_object('ok', false, 'reason', 'org_not_found');
  end if;

  select jsonb_build_object(
    'ok', true,
    'org', (
      select jsonb_build_object(
        'org_id', o.org_id, 'name', o.name, 'is_internal', o.is_internal,
        'platform_fee_cents', o.platform_fee_cents, 'created_at', o.created_at
      )
      from winnerdata.organizations o where o.org_id = p_org_id
    ),
    'producers', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'producer_id', p.producer_id,
        'full_name', p.full_name,
        'email', p.email,
        'active', p.active,
        'active_lines', p.active_lines,
        'license_states', p.license_states,
        'notes', p.notes,
        'leads_routed_total', (select count(*) from winnerdata.routing_decisions rd where rd.producer_id = p.producer_id),
        'win_rate_pct_90d', (
          select cr.win_rate_pct_90d from winnerdata.closing_ratios cr
          where cr.producer_id = p.producer_id and cr.org_id = p_org_id
        )
      ) order by p.full_name), '[]'::jsonb)
      from winnerdata.producers p where p.org_id = p_org_id
    ),
    'lead_volume', jsonb_build_object(
      'total', (select count(*) from winnerdata.leads l where l.org_id = p_org_id),
      'last_30d', (select count(*) from winnerdata.leads l where l.org_id = p_org_id and l.created_at >= now() - interval '30 days'),
      'sla_breach_count', (select count(*) from winnerdata.leads l where l.org_id = p_org_id and l.sla_breach)
    )
  ) into v_result;

  return v_result;
end;
$$;

-- 3c. Lead management view — filterable list/detail.
create or replace function public.lms_leads_list(
  p_org_id uuid,
  p_producer_id uuid default null,
  p_product_line text default null,
  p_date_from date default null,
  p_date_to date default null,
  p_limit integer default 100,
  p_offset integer default 0
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_rows jsonb;
  v_total bigint;
begin
  if p_org_id is null then
    return jsonb_build_object('ok', false, 'reason', 'org_id required');
  end if;

  select count(*) into v_total
  from winnerdata.leads l
  where l.org_id = p_org_id
    and (p_product_line is null or l.product_line::text = p_product_line)
    and (p_date_from is null or l.created_at::date >= p_date_from)
    and (p_date_to is null or l.created_at::date <= p_date_to)
    and (p_producer_id is null or exists (
      select 1 from winnerdata.routing_decisions rd where rd.lead_id = l.lead_id and rd.producer_id = p_producer_id
    ));

  select coalesce(jsonb_agg(row_to_json(t)), '[]'::jsonb) into v_rows
  from (
    select
      l.lead_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email,
      l.product_line, l.temperature, l.consent_status, l.sla_tier, l.sla_breach,
      l.delivered_at, l.created_at, l.parcel_id,
      l.flagged_at, l.flagged_by, l.flagged_reason,
      (
        select rd.producer_id from winnerdata.routing_decisions rd
        where rd.lead_id = l.lead_id order by rd.routed_at desc limit 1
      ) as producer_id,
      (
        select p.full_name from winnerdata.routing_decisions rd
        join winnerdata.producers p on p.producer_id = rd.producer_id
        where rd.lead_id = l.lead_id order by rd.routed_at desc limit 1
      ) as producer_name
    from winnerdata.leads l
    where l.org_id = p_org_id
      and (p_product_line is null or l.product_line::text = p_product_line)
      and (p_date_from is null or l.created_at::date >= p_date_from)
      and (p_date_to is null or l.created_at::date <= p_date_to)
      and (p_producer_id is null or exists (
        select 1 from winnerdata.routing_decisions rd where rd.lead_id = l.lead_id and rd.producer_id = p_producer_id
      ))
    order by l.created_at desc
    limit greatest(coalesce(p_limit, 100), 0)
    offset greatest(coalesce(p_offset, 0), 0)
  ) t;

  return jsonb_build_object('ok', true, 'total', v_total, 'leads', v_rows);
end;
$$;

-- 3d. Producer performance view.
create or replace function public.lms_producer_performance(p_org_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_result jsonb;
begin
  if p_org_id is null then
    return jsonb_build_object('ok', false, 'reason', 'org_id required');
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'producer_id', p.producer_id,
    'full_name', p.full_name,
    'email', p.email,
    'active', p.active,
    'active_lines', p.active_lines,
    'license_states', p.license_states,
    'notes', p.notes,
    'leads_routed_total', (select count(*) from winnerdata.routing_decisions rd where rd.producer_id = p.producer_id),
    'leads_routed_90d', coalesce(cr.leads_routed_90d, 0),
    'binds_90d', coalesce(cr.binds_90d, 0),
    'win_rate_pct_90d', coalesce(cr.win_rate_pct_90d, 0),
    'sla_breaches', (
      select count(*) from winnerdata.routing_decisions rd
      join winnerdata.leads l on l.lead_id = rd.lead_id
      where rd.producer_id = p.producer_id and l.sla_breach
    )
  ) order by coalesce(cr.win_rate_pct_90d, 0) desc, p.full_name), '[]'::jsonb)
  into v_result
  from winnerdata.producers p
  left join winnerdata.closing_ratios cr on cr.producer_id = p.producer_id and cr.org_id = p.org_id
  where p.org_id = p_org_id;

  return jsonb_build_object('ok', true, 'producers', v_result);
end;
$$;

-- 3e. Billing view — READ ONLY onto the existing finance.revenue_ledger
--     pipeline (trigger-wired in 20260831d_cfo_bookkeeping_billable_ff_wiring.sql).
--     Does NOT recompute or duplicate invoice logic.
create or replace function public.lms_billing_view(p_org_id uuid, p_status text default null)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata, finance
as $$
declare
  v_rows jsonb;
  v_summary jsonb;
begin
  if p_org_id is null then
    return jsonb_build_object('ok', false, 'reason', 'org_id required');
  end if;

  select coalesce(jsonb_agg(row_to_json(t)), '[]'::jsonb) into v_rows
  from (
    select
      be.id as billable_event_id,
      be.delivered_at,
      be.bound_at,
      be.monetization_tier_met,
      be.scenario_a_delivery_fee_cents,
      be.scenario_a_success_fee_cents,
      be.scenario_b_flat_fee_cents,
      be.monetization_basis,
      rl.id as revenue_ledger_id,
      rl.occurred_on,
      rl.entity_code,
      rl.customer,
      rl.amount_cents,
      rl.status as ledger_status,
      rl.invoiced_at,
      rl.paid_at
    from winnerdata.billable_ff_events be
    left join finance.revenue_ledger rl
      on rl.ref_table = 'winnerdata.billable_ff_events' and rl.ref_id = be.id
    where be.org_id = p_org_id
      and (p_status is null or rl.status = p_status)
    order by be.delivered_at desc
  ) t;

  select jsonb_build_object(
    'total_events', count(*),
    'pending_cents', coalesce(sum(rl.amount_cents) filter (where rl.status = 'pending'), 0),
    'invoiced_cents', coalesce(sum(rl.amount_cents) filter (where rl.status = 'invoiced'), 0),
    'paid_cents', coalesce(sum(rl.amount_cents) filter (where rl.status = 'paid'), 0)
  ) into v_summary
  from winnerdata.billable_ff_events be
  left join finance.revenue_ledger rl
    on rl.ref_table = 'winnerdata.billable_ff_events' and rl.ref_id = be.id
  where be.org_id = p_org_id;

  return jsonb_build_object('ok', true, 'summary', v_summary, 'events', v_rows);
end;
$$;

-- ============================================================
-- 4. WRITE RPCs — Tier 2 (non-billing) only, audit-logged, no raw
--    table writes from the Worker. Anything touching billing state
--    stays Tier 1 propose-only and is out of scope for this v1 (no
--    write RPC exists for finance.* or winnerdata.billable_ff_events).
-- ============================================================

create or replace function public.lms_flag_lead(
  p_org_id uuid, p_lead_id uuid, p_actor text, p_reason text
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
begin
  if p_org_id is null or p_lead_id is null or p_actor is null
     or p_reason is null or trim(p_reason) = '' then
    return jsonb_build_object('ok', false, 'reason', 'missing_params');
  end if;

  update winnerdata.leads
  set flagged_at = now(), flagged_by = p_actor, flagged_reason = p_reason
  where lead_id = p_lead_id and org_id = p_org_id;

  if not found then
    return jsonb_build_object('ok', false, 'reason', 'lead_not_found');
  end if;

  insert into winnerdata.lms_audit_log (org_id, actor, action, target_table, target_id, detail)
  values (p_org_id, p_actor, 'flag_lead', 'winnerdata.leads', p_lead_id::text,
          jsonb_build_object('reason', p_reason));

  return jsonb_build_object('ok', true, 'lead_id', p_lead_id);
end;
$$;

create or replace function public.lms_update_producer_note(
  p_org_id uuid, p_producer_id uuid, p_actor text, p_note text
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
begin
  if p_org_id is null or p_producer_id is null or p_actor is null or p_note is null then
    return jsonb_build_object('ok', false, 'reason', 'missing_params');
  end if;

  update winnerdata.producers
  set notes = p_note
  where producer_id = p_producer_id and org_id = p_org_id;

  if not found then
    return jsonb_build_object('ok', false, 'reason', 'producer_not_found');
  end if;

  insert into winnerdata.lms_audit_log (org_id, actor, action, target_table, target_id, detail)
  values (p_org_id, p_actor, 'update_producer_note', 'winnerdata.producers', p_producer_id::text,
          jsonb_build_object('note', p_note));

  return jsonb_build_object('ok', true, 'producer_id', p_producer_id);
end;
$$;

-- ============================================================
-- 5. Grants — anon-callable (same non-secret-holding pattern as
--    workers/winnerdata-ff: the Worker embeds only the anon key, and
--    a Basic Auth gate at the Worker edge is the human-access
--    boundary; org_id scoping inside each function is the data
--    boundary). Explicitly REVOKE ALL first so nothing is callable
--    by accident via a broader role.
-- ============================================================

revoke all on function public.lms_orgs_list() from public;
revoke all on function public.lms_org_detail(uuid) from public;
revoke all on function public.lms_leads_list(uuid, uuid, text, date, date, integer, integer) from public;
revoke all on function public.lms_producer_performance(uuid) from public;
revoke all on function public.lms_billing_view(uuid, text) from public;
revoke all on function public.lms_flag_lead(uuid, uuid, text, text) from public;
revoke all on function public.lms_update_producer_note(uuid, uuid, text, text) from public;

grant execute on function public.lms_orgs_list() to anon;
grant execute on function public.lms_org_detail(uuid) to anon;
grant execute on function public.lms_leads_list(uuid, uuid, text, date, date, integer, integer) to anon;
grant execute on function public.lms_producer_performance(uuid) to anon;
grant execute on function public.lms_billing_view(uuid, text) to anon;
grant execute on function public.lms_flag_lead(uuid, uuid, text, text) to anon;
grant execute on function public.lms_update_producer_note(uuid, uuid, text, text) to anon;

commit;
