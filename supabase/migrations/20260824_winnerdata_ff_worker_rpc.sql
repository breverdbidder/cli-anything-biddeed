-- Winner Data FF Worker v1 -- part 2: public RPC accessors.
--
-- WHY THIS EXISTS (live-verified 2026-08-24, do not remove without re-checking):
-- The prior migration (20260824_winnerdata_ff_worker_rls.sql) tried the
-- architecture the issue spec assumed: expose `summitleads` via PostgREST
-- (Management API PATCH /postgrest db_schema) and gate it with RLS, same as
-- worker-biddeed-staging does for `public`. That PATCH succeeds and reads
-- back correctly from the Management API, but the live PostgREST gateway
-- never picks it up -- verified across 3 separate mechanisms (plain wait,
-- explicit project restart, NOTIFY pgrst reload) over several minutes, and
-- matches what scripts/summitleads_pipeline.py and
-- pipelines/winnerdata/momentum_delivery.py already say in their own
-- docstrings: "PostgREST does not expose the summitleads schema." This is a
-- pre-existing, already-documented platform limitation, not something this
-- session broke. The db_schema PATCH was reverted back to
-- "public,graphql_public" so no half-applied config is left live.
--
-- Fix: the same pattern src/worker.js already uses for every
-- sensitive/gated read (check_s5_report_access, upsert_lead_full,
-- get_all_counties_with_status, chat_rate_check_v2, log_worker_error) --
-- SECURITY DEFINER functions living in `public` (which IS exposed), called
-- via /rest/v1/rpc/<fn> with the same embedded anon key. The function body,
-- not a PostgREST-generated table filter, is the access boundary: search_path
-- is pinned, org_id is validated inside the function against the single live
-- tenant before touching summitleads.*, and a mismatched org_id returns an
-- empty result -- the literal "wrong org_id -> 0 rows" proof the issue's
-- DEFINITION OF DONE asks for. This makes the RLS policies from the prior
-- migration defense-in-depth for a future direct-exposure path, not the
-- active boundary today; they are left in place because they cost nothing
-- and are correct if that path is ever fixed.
--
-- Single-tenant constant matches the prior migration and the one live row in
-- summitleads.organizations (Protection Partners).

create or replace function public.ff_healthz()
returns jsonb
language sql
security definer
set search_path = public, summitleads
as $$
  select jsonb_build_object(
    'status', 'ok',
    'leads', (select count(*) from summitleads.leads),
    'quote_drafts', (select count(*) from summitleads.quote_drafts),
    'binds', (select count(*) from summitleads.binds),
    'ff_responses', (select count(*) from summitleads.ff_responses),
    'checked_at', now()
  );
$$;

revoke all on function public.ff_healthz() from public;
grant execute on function public.ff_healthz() to anon;

-- GET /portal -- agency lead list. p_org_id must match the caller's tenant;
-- a wrong/unknown org_id yields zero rows (RETURN QUERY simply never runs).
create or replace function public.ff_portal_leads(p_org_id uuid)
returns table (
  lead_id uuid,
  entity_name text,
  contact_name text,
  contact_phone text,
  contact_email text,
  property_address text,
  county text,
  sale_type text,
  auction_date date,
  sold_amount numeric,
  case_number text,
  consent_status text,
  days_since_auction int,
  is_bound boolean
)
language plpgsql
security definer
set search_path = public, summitleads
as $$
begin
  if p_org_id is null or p_org_id <> '032f4717-545f-4a18-b48b-28ea4257699d'::uuid then
    return;
  end if;

  return query
  select
    l.lead_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email,
    v.property_address, v.county, v.sale_type, v.auction_date, v.sold_amount, v.case_number,
    l.consent_status::text,
    case when v.auction_date is not null then (current_date - v.auction_date)::int else null end,
    exists (select 1 from summitleads.binds b where b.lead_id = l.lead_id)
  from summitleads.leads l
  left join summitleads.v_producer_intake v on v.lead_id = l.lead_id
  where l.org_id = p_org_id
  order by v.auction_date desc nulls last;
end;
$$;

revoke all on function public.ff_portal_leads(uuid) from public;
grant execute on function public.ff_portal_leads(uuid) to anon;

-- GET /ff/:lead_id -- single fact-finder render source. Returns null (not a
-- row) on org mismatch or unknown lead_id -- Worker maps null -> 403/404.
create or replace function public.ff_get_lead(p_org_id uuid, p_lead_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, summitleads
as $$
declare
  result jsonb;
begin
  if p_org_id is null or p_org_id <> '032f4717-545f-4a18-b48b-28ea4257699d'::uuid then
    return null;
  end if;

  select jsonb_build_object(
    'lead_id', l.lead_id,
    'org_id', l.org_id,
    'entity_name', l.entity_name,
    'contact_name', l.contact_name,
    'contact_phone', l.contact_phone,
    'contact_email', l.contact_email,
    'parcel_id', l.parcel_id,
    'product_line', l.product_line,
    'consent_status', l.consent_status,
    'auction', jsonb_build_object(
      'property_address', v.property_address,
      'county', v.county,
      'sale_type', v.sale_type,
      'auction_date', v.auction_date,
      'sold_amount', v.sold_amount,
      'case_number', v.case_number
    ),
    'parcel', jsonb_build_object(
      'act_yr_blt', fp.act_yr_blt,
      'eff_yr_blt', fp.eff_yr_blt,
      'tot_lvg_ar', fp.tot_lvg_ar,
      'no_res_unt', fp.no_res_unt,
      'const_clas', fp.const_clas,
      'jv', fp.jv,
      'lnd_val', fp.lnd_val,
      'bldg_val', (fp.jv - fp.lnd_val),
      'dor_uc', fp.dor_uc,
      'own_name', fp.own_name,
      'own_addr1', fp.own_addr1,
      'phy_addr1', fp.phy_addr1,
      'phy_city', fp.phy_city
    ),
    'responses', coalesce((
      select jsonb_object_agg(r.field, r.value)
      from summitleads.ff_responses r
      where r.lead_id = l.lead_id and r.org_id = p_org_id
    ), '{}'::jsonb)
  )
  into result
  from summitleads.leads l
  left join summitleads.v_producer_intake v on v.lead_id = l.lead_id
  left join public.fl_parcels fp on fp.parcel_id = l.parcel_id
  where l.lead_id = p_lead_id and l.org_id = p_org_id;

  return result;
end;
$$;

revoke all on function public.ff_get_lead(uuid, uuid) from public;
grant execute on function public.ff_get_lead(uuid, uuid) to anon;

-- POST /ff/:lead_id -- persist one producer-entered field.
create or replace function public.ff_upsert_response(
  p_org_id uuid, p_lead_id uuid, p_property_id text, p_field text, p_value text, p_updated_by text
)
returns jsonb
language plpgsql
security definer
set search_path = public, summitleads
as $$
begin
  if p_org_id is null or p_org_id <> '032f4717-545f-4a18-b48b-28ea4257699d'::uuid then
    return jsonb_build_object('ok', false, 'error', 'org_mismatch');
  end if;

  if not exists (select 1 from summitleads.leads where lead_id = p_lead_id and org_id = p_org_id) then
    return jsonb_build_object('ok', false, 'error', 'lead_not_found');
  end if;

  insert into summitleads.ff_responses (org_id, lead_id, property_id, field, value, updated_by, updated_at)
  values (p_org_id, p_lead_id, p_property_id, p_field, p_value, p_updated_by, now());

  return jsonb_build_object('ok', true);
end;
$$;

revoke all on function public.ff_upsert_response(uuid, uuid, text, text, text, text) from public;
grant execute on function public.ff_upsert_response(uuid, uuid, text, text, text, text) to anon;

-- POST /portal/bind -- record a bind outcome (Stage 0 exit metric).
create or replace function public.ff_record_bind(
  p_org_id uuid, p_lead_id uuid, p_premium_cents int, p_product_line text
)
returns jsonb
language plpgsql
security definer
set search_path = public, summitleads
as $$
declare
  new_bind_id uuid;
begin
  if p_org_id is null or p_org_id <> '032f4717-545f-4a18-b48b-28ea4257699d'::uuid then
    return jsonb_build_object('ok', false, 'error', 'org_mismatch');
  end if;

  if not exists (select 1 from summitleads.leads where lead_id = p_lead_id and org_id = p_org_id) then
    return jsonb_build_object('ok', false, 'error', 'lead_not_found');
  end if;

  insert into summitleads.binds (bind_id, lead_id, org_id, product_line, premium_cents, bound_at)
  values (gen_random_uuid(), p_lead_id, p_org_id, p_product_line::summitleads.product_line, p_premium_cents, now())
  returning bind_id into new_bind_id;

  return jsonb_build_object('ok', true, 'bind_id', new_bind_id);
end;
$$;

revoke all on function public.ff_record_bind(uuid, uuid, int, text) from public;
grant execute on function public.ff_record_bind(uuid, uuid, int, text) to anon;
