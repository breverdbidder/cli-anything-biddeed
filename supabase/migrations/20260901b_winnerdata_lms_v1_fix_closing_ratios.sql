-- Fix for 20260901_winnerdata_lms_v1.sql: lms_org_detail and
-- lms_producer_performance were written against the winnerdata.closing_ratios
-- column names documented in 20260830_winnerdata_routing_engine_v1.sql
-- (producer_id, org_id, leads_routed, leads_bound, win_rate_pct_90d,
-- leads_routed_90d, binds_90d). Live-queried 2026-09-01: the view's real
-- columns are (org_id, producer_id, product_line, leads_routed, leads_bound,
-- closing_ratio) -- it was altered live after that migration file was
-- written and is one row per producer PER product_line, not one row per
-- producer. Caught via a live 400 (42703 column does not exist) on first
-- RPC test, not silently assumed -- CC_META_PROMPT.md 1.3/2.3.

begin;

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
        'win_rate_pct', (
          select case when sum(cr.leads_routed) > 0
            then round(sum(cr.leads_bound)::numeric / sum(cr.leads_routed) * 100, 2)
            else 0 end
          from winnerdata.closing_ratios cr
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
    'leads_routed_by_ratio_view', coalesce(cr.leads_routed_sum, 0),
    'leads_bound', coalesce(cr.leads_bound_sum, 0),
    'win_rate_pct', coalesce(cr.win_rate_pct, 0),
    'sla_breaches', (
      select count(*) from winnerdata.routing_decisions rd
      join winnerdata.leads l on l.lead_id = rd.lead_id
      where rd.producer_id = p.producer_id and l.sla_breach
    )
  ) order by coalesce(cr.win_rate_pct, 0) desc, p.full_name), '[]'::jsonb)
  into v_result
  from winnerdata.producers p
  left join (
    select
      producer_id,
      org_id,
      sum(leads_routed) as leads_routed_sum,
      sum(leads_bound) as leads_bound_sum,
      case when sum(leads_routed) > 0
        then round(sum(leads_bound)::numeric / sum(leads_routed) * 100, 2)
        else 0 end as win_rate_pct
    from winnerdata.closing_ratios
    group by producer_id, org_id
  ) cr on cr.producer_id = p.producer_id and cr.org_id = p.org_id
  where p.org_id = p_org_id;

  return jsonb_build_object('ok', true, 'producers', v_result);
end;
$$;

commit;
