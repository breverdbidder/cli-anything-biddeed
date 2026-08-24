-- FF daily pipeline (issue: daily automated FF pipeline, all 67 counties) --
-- part 1: make ff_get_lead always return a verification badge.
--
-- The FF master template (templates/FF_TEMPLATE_A_AUCTION_SALES.html /
-- FF_TEMPLATE_B_HOMEOWNER.html) requires a clickable county property
-- appraiser link plus an explicit green VERIFIED / red NOT VERIFIED badge on
-- every generated FF -- never blank. Source priority for the link, cheapest
-- and freshest first:
--   1. public.fl_property_appraiser_configs.appraiser_url -- the 8 counties
--      with a live-verified cross-verification scraper (see
--      20260824_property_appraiser_cross_verification.sql).
--   2. public.fl_counties.appraiser_url -- broader county-onboarding column,
--      populated for 14 more counties, no scraper behind it yet.
--   3. neither -- 45/67 counties have no appraiser URL on file in this DB at
--      all. BLANK > WRONG: no URL is fabricated, the badge explains why.
--
-- Badge is VERIFIED only when a parity_audit row for this case_number's
-- blocking fields (parcel_id/address) has verdict='pass' -- i.e. a scraper
-- actually ran and matched. Everything else (never scraped, scraper
-- config missing, WAF-blocked, or scraped-but-mismatched) is NOT VERIFIED
-- with a real reason, per this pipeline's non-goal: alachua/flagler/wakulla
-- are expected to fail daily and must say so, not be silently skipped.

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
    ), '{}'::jsonb),
    'verification', (
      select jsonb_build_object(
        'badge', case when pa.verdict = 'pass' then 'VERIFIED' else 'NOT VERIFIED' end,
        'reason', coalesce(
          case
            when pa.verdict = 'pass' then 'Parcel ID/address matched the county property appraiser record.'
            when pa.verdict is not null then pa.verdict_note
            when cfg.blocked_by_waf then cfg.known_issues
            when cfg.appraiser_url is not null then 'Appraiser cross-verification is configured for this county but has not run for this parcel yet.'
            else 'No property appraiser cross-verification source is configured for this county yet.'
          end,
          'No property appraiser cross-verification source is configured for this county yet.'
        ),
        'appraiser_url', coalesce(cfg.appraiser_url, fc.appraiser_url),
        'audited_at', pa.audited_at
      )
      from (select v.county as slug) county_ctx
      left join public.fl_property_appraiser_configs cfg on cfg.county_slug = county_ctx.slug
      left join public.fl_counties fc on fc.slug = county_ctx.slug
      left join lateral (
        select verdict, verdict_note, audited_at
        from public.parity_audit
        where case_number = v.case_number and field_name in ('parcel_id', 'address')
        order by (verdict = 'pass') desc, audited_at desc nulls last
        limit 1
      ) pa on true
    )
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
