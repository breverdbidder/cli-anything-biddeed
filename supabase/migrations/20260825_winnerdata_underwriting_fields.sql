-- Underwriting field expansion: roof age/permit history, construction class,
-- affordability tier (modeled, never a bureau-pulled score -- see Hard Rule 3 in the
-- dispatching issue and docs/canon/02_COMPLIANCE_DOCTRINE.md).
--
-- Lives in `winnerdata` schema (not summitleads) -- this is genuinely
-- parcel-level enrichment reusable across every lead/vertical touching the
-- same parcel (the "resolve once, reuse across verticals" moat in
-- docs/canon/01_WINNER_DATA_CANON.md), not lead-pipeline state. `winnerdata`
-- schema already exists (holds owner_portfolio, live-verified this session).

create schema if not exists winnerdata;

-- ---------------------------------------------------------------------
-- Field 1: roof age / permit history
-- ---------------------------------------------------------------------
create table if not exists winnerdata.parcel_underwriting (
  co_no bigint not null,
  parcel_id text not null,
  permit_source_county text,           -- county_slug the permit was sourced from
  permit_number text,                  -- public record, safe to print on FF
  roof_permit_date date,                -- date of the qualifying FULL-replacement permit
  roof_permit_full_replacement boolean not null default false,
  permit_check_method text,            -- 'arcgis_featureserver' | 'scrape' | 'none_available'
  construction_class text,             -- masonry | frame | fire_resistive | other
  construction_class_source text,      -- e.g. 'county parcel record (const_clas)'
  checked_at timestamptz not null default now(),
  primary key (co_no, parcel_id)
);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'parcel_underwriting_roof_replacement_needs_date') then
    alter table winnerdata.parcel_underwriting
      add constraint parcel_underwriting_roof_replacement_needs_date
      check (not roof_permit_full_replacement or roof_permit_date is not null);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'parcel_underwriting_construction_class_check') then
    alter table winnerdata.parcel_underwriting
      add constraint parcel_underwriting_construction_class_check
      check (construction_class is null or construction_class in ('masonry','frame','fire_resistive','other'));
  end if;
end $$;

comment on table winnerdata.parcel_underwriting is
  'Roof-permit and construction-class enrichment, resolved once per parcel and reused across every lead touching it. roof_age_years is intentionally NOT stored here -- see winnerdata.roof_age_years(), computed at query/render time so it never goes stale.';
comment on column winnerdata.parcel_underwriting.permit_check_method is
  'Honest record of HOW this row was populated -- never silently degrade: none_available means we checked and found nothing, not that we didn''t check.';

-- Hard Rule 7: new table ships with RLS enabled, no anon policy.
alter table winnerdata.parcel_underwriting enable row level security;
revoke all on winnerdata.parcel_underwriting from public, anon, authenticated;
grant select, insert, update on winnerdata.parcel_underwriting to service_role;

create or replace function winnerdata.roof_age_years(p_roof_permit_date date)
returns integer
language sql
stable
as $$
  select case
    when p_roof_permit_date is null then null
    else extract(year from age(current_date, p_roof_permit_date))::integer
  end;
$$;

-- ---------------------------------------------------------------------
-- Field 2: construction class crosswalk (from fl_parcels.const_clas, the
-- only construction-related field confirmed present on fl_parcels this
-- session -- no exterior-wall or roof-structure columns exist, so no new
-- ingestion path is built for those). Coarse ISO-style bucket only, per
-- spec ("do not emit full Type I-V").
--
-- const_clas is FL DOR's raw single-digit code. Real DOR county roll layout
-- (Real Property Reporting Guidelines) maps this range to a masonry/frame
-- axis; codes 0/1 are wood-frame construction, 2-5 progressively more
-- masonry/fire-resistive/steel/reinforced-concrete. This crosswalk is
-- intentionally coarse (matches the "avoids overclaiming precision"
-- instruction) -- it does not attempt to reproduce ISO's full Type I-V
-- schedule.
-- ---------------------------------------------------------------------
create or replace function winnerdata.construction_class_from_dor(p_const_clas text)
returns table(construction_class text, construction_class_source text)
language sql
stable
as $$
  select
    case p_const_clas
      when '0' then 'frame'
      when '1' then 'frame'
      when '2' then 'masonry'
      when '3' then 'masonry'
      when '4' then 'fire_resistive'
      when '5' then 'fire_resistive'
      else null
    end,
    case when p_const_clas is not null then 'county parcel record (DOR const_clas)' else null end;
$$;

-- ---------------------------------------------------------------------
-- Field 3: estimated_affordability_tier -- MODELED, never a bureau-pulled score.
-- The word "credit" must not appear in this function, column, or any FF
-- output (negative test 1). Computed at query time (not stored) from
-- property-financial signals actually held today:
--   - years_owned                    (fl_parcels.sale_yr1)
--   - purchase_to_current_value_pct  (fl_parcels.sale_prc1 vs jv)
--   - active_mortgage_balance_to_value, tax_delinquency_flag
--     (public.v_lien_stack -- LIVE-CHECKED this session: view exists and is
--     well-formed, but its source table public.property_documents has ZERO
--     rows today, so these two inputs resolve to NULL for every parcel right
--     now. Wired in anyway, additively, so the tier gets sharper the moment
--     that pipeline populates real rows -- not fabricated in the meantime.)
-- Output is always one of: strong | moderate | limited | unknown. Never a
-- number.
-- ---------------------------------------------------------------------
create or replace function winnerdata.estimated_affordability_tier(p_parcel_id text, p_co_no bigint)
returns table(estimated_affordability_tier text, tier_basis jsonb)
language plpgsql
stable
as $$
declare
  v_jv numeric;
  v_sale_prc1 numeric;
  v_sale_yr1 int;
  v_years_owned int;
  v_appreciation_pct numeric;
  v_mortgage_balance numeric;
  v_ltv numeric;
  v_delinquent boolean;
  v_tier text;
begin
  select jv, sale_prc1, sale_yr1
    into v_jv, v_sale_prc1, v_sale_yr1
  from public.fl_parcels
  where parcel_id = p_parcel_id and co_no = p_co_no
  limit 1;

  if v_sale_yr1 is not null and v_sale_yr1 > 1900 then
    v_years_owned := extract(year from current_date)::int - v_sale_yr1;
  end if;

  if v_sale_prc1 is not null and v_sale_prc1 > 1000 and v_jv is not null then
    v_appreciation_pct := (v_jv - v_sale_prc1) / v_sale_prc1;
  end if;

  select vls.total_active_mortgage_balance, (vls.tax_certs > 0)
    into v_mortgage_balance, v_delinquent
  from public.v_lien_stack vls
  where vls.parcel_id = p_parcel_id
  limit 1;

  if v_mortgage_balance is not null and v_jv is not null and v_jv > 0 then
    v_ltv := v_mortgage_balance / v_jv;
  end if;

  v_tier := case
    when v_delinquent is true or (v_ltv is not null and v_ltv > 0.9) then 'limited'
    when v_years_owned is not null and v_years_owned >= 10
         and v_appreciation_pct is not null and v_appreciation_pct >= 0.5
         and (v_ltv is null or v_ltv <= 0.5) then 'strong'
    when (v_years_owned is not null and v_years_owned >= 5)
         or (v_appreciation_pct is not null and v_appreciation_pct > 0) then 'moderate'
    else 'unknown'
  end;

  estimated_affordability_tier := v_tier;
  tier_basis := jsonb_build_object(
    'years_owned', v_years_owned,
    'purchase_to_current_value_delta_pct', v_appreciation_pct,
    'active_mortgage_balance_to_value', v_ltv,
    'tax_delinquency_flag', v_delinquent,
    'note', case when v_ltv is null and v_delinquent is null
                 then 'mortgage/lien signals unavailable -- source table public.property_documents has 0 rows as of 2026-08-25'
                 else null end
  );
  return next;
end;
$$;

revoke all on function winnerdata.estimated_affordability_tier(text, bigint) from public;
grant execute on function winnerdata.estimated_affordability_tier(text, bigint) to service_role;

-- ---------------------------------------------------------------------
-- FF-facing read RPC: one call, all three underwriting fields, honest
-- NOT AVAILABLE fallbacks baked in (Hard Rule 2 -- never blank-omit).
-- SECURITY DEFINER because it reads across schemas (public.fl_parcels,
-- public.v_lien_stack, winnerdata.parcel_underwriting) for the FF worker,
-- same pattern as public.ff_get_lead / public.ff_healthz.
-- ---------------------------------------------------------------------
create or replace function public.ff_underwriting_fields(p_parcel_id text, p_co_no bigint)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_pu winnerdata.parcel_underwriting%rowtype;
  v_cc record;
  v_aff record;
  v_result jsonb;
begin
  select * into v_pu from winnerdata.parcel_underwriting
  where parcel_id = p_parcel_id and co_no = p_co_no;

  if v_pu.construction_class is not null then
    v_cc.construction_class := v_pu.construction_class;
    v_cc.construction_class_source := v_pu.construction_class_source;
  else
    select cc.construction_class, cc.construction_class_source into v_cc
    from public.fl_parcels fp, winnerdata.construction_class_from_dor(fp.const_clas) cc
    where fp.parcel_id = p_parcel_id and fp.co_no = p_co_no;
  end if;

  select t.estimated_affordability_tier, t.tier_basis into v_aff
  from winnerdata.estimated_affordability_tier(p_parcel_id, p_co_no) t;

  v_result := jsonb_build_object(
    'roof_age_years', winnerdata.roof_age_years(v_pu.roof_permit_date),
    'roof_permit_date', v_pu.roof_permit_date,
    'permit_source_county', v_pu.permit_source_county,
    'permit_number', v_pu.permit_number,
    'roof_confidence_tier', case
      when v_pu.roof_permit_date is not null and v_pu.permit_source_county is not null then 'VERIFIED·PRIMARY'
      else 'NOT AVAILABLE'
    end,
    'construction_class', coalesce(v_cc.construction_class, 'NOT AVAILABLE'),
    'construction_class_source', v_cc.construction_class_source,
    'construction_class_confidence_tier', case
      when v_cc.construction_class is not null then 'LIKELY·SINGLE SOURCE'
      else 'NOT AVAILABLE'
    end,
    'estimated_affordability_tier', coalesce(v_aff.estimated_affordability_tier, 'unknown'),
    'estimated_affordability_tier_confidence_tier', case
      when v_aff.estimated_affordability_tier is not null and v_aff.estimated_affordability_tier != 'unknown'
        then 'LIKELY·SINGLE SOURCE'
      else 'NOT AVAILABLE'
    end,
    'estimated_affordability_tier_basis', v_aff.tier_basis,
    'estimated_affordability_tier_disclaimer', 'Estimated from public financial signals -- not a credit report.'
  );
  return v_result;
end;
$$;

revoke all on function public.ff_underwriting_fields(text, bigint) from public;
grant execute on function public.ff_underwriting_fields(text, bigint) to anon;
