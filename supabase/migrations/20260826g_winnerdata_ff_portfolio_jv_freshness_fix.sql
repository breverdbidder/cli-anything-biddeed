-- Follow-up to 20260826f_winnerdata_ff_portfolio_assessed_dor_source.sql,
-- found while live-verifying that migration's Gap 5 backfill
-- (scripts/property_appraiser/backfill_ff_parcels_from_doh.py) against a
-- real portfolio lead (LEINIER CASTILLO, parcel 0430120031251):
--
-- ff_get_lead's `portfolio` array showed jv=385290 (winnerdata.owner_portfolio's
-- snapshot, captured 2026-08-25 when the identity-cascade batch ran, BEFORE
-- the DOH backfill) alongside av_sd=86481 (public.fl_parcels.av_sd, freshly
-- confirmed via the DOH statewide layer moments earlier -- log shows this
-- parcel's real JV is 104122, not 385290). Same property, two different
-- vintages of "just value" sourced from two different tables -- exactly the
-- kind of silent inconsistency Gap 4 was supposed to close, just
-- reintroduced one field over by mixing a stale snapshot with a fresh join.
--
-- Confirmed live before writing this: every winnerdata.owner_portfolio row
-- has a matching public.fl_parcels row (0 orphans, checked via LEFT JOIN ...
-- WHERE fp.parcel_id IS NULL), so switching the portfolio array's `jv` to
-- read fp2.jv (same row av_sd already comes from) instead of op.jv loses no
-- coverage -- coalesce(fp2.jv, op.jv) is kept only as a defensive fallback,
-- not because it's currently reachable.
CREATE OR REPLACE FUNCTION public.ff_get_lead(p_org_id uuid, p_lead_id uuid)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
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
      'av_sd', fp.av_sd,
      'lnd_val', fp.lnd_val,
      'bldg_val', (fp.jv - fp.lnd_val),
      'dor_uc', fp.dor_uc,
      'dor_source', fp.dor_source,
      'dor_synced_at', fp.dor_synced_at,
      'own_name', fp.own_name,
      'own_addr1', fp.own_addr1,
      'phy_addr1', fp.phy_addr1,
      'phy_city', fp.phy_city
    ),
    'portfolio', coalesce((
      select jsonb_agg(jsonb_build_object(
        'parcel_id', op.parcel_id,
        'county', op.county,
        'address', op.address,
        'dor_uc', op.dor_uc,
        'no_buldng', op.no_buldng,
        'jv', coalesce(fp2.jv, op.jv),
        'av_sd', fp2.av_sd,
        'lnd_val', fp2.lnd_val,
        'acquisition_source', op.acquisition_source,
        'linked_via', op.linked_via,
        'linked_via_detail', op.linked_via_detail,
        'case_number', op.case_number
      ) order by op.county, op.address)
      from winnerdata.owner_portfolio op
      left join public.fl_parcels fp2 on fp2.co_no = op.co_no and fp2.parcel_id = op.parcel_id
      where op.owner_key = public.ff_normalize_name(l.entity_name)
    ), '[]'::jsonb),
    'responses', coalesce((
      select jsonb_object_agg(r.field, r.value)
      from winnerdata.ff_responses r
      where r.lead_id = l.lead_id and r.org_id = p_org_id
    ), '{}'::jsonb),
    'verification', (
      select jsonb_build_object(
        'badge', case
          when pa.verdict = 'pass' then 'VERIFIED'
          when v.case_number is null and mpa.verdict = 'pass' then 'VERIFIED'
          else 'NOT VERIFIED'
        end,
        'verified_via', case
          when pa.verdict = 'pass' then 'court_record'
          when v.case_number is null and mpa.verdict = 'pass' then 'parcel_completeness'
          else null
        end,
        'reason', coalesce(
          case
            when pa.verdict = 'pass' then
              'Verified against a court record: parcel ID/address matched the county property appraiser record for case ' || v.case_number || '.'
            when pa.verdict is not null then pa.verdict_note
            when v.case_number is null and mpa.verdict = 'pass' then
              'Verified against county property appraiser records: single confirmed parcel match with complete appraisal data.'
            when v.case_number is null and mpa.verdict is not null then mpa.verdict_note
            when cfg.blocked_by_waf then cfg.known_issues
            when cfg.appraiser_url is not null then 'Appraiser cross-verification is configured for this county but has not run for this parcel yet.'
            else 'No property appraiser cross-verification source is configured for this county yet.'
          end,
          'No property appraiser cross-verification source is configured for this county yet.'
        ),
        'appraiser_url', coalesce(cfg.appraiser_url, fc.appraiser_url),
        'audited_at', coalesce(pa.audited_at, mpa.audited_at)
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
      left join lateral (
        select (r ->> 'verdict') as verdict,
               (r ->> 'verdict_note') as verdict_note,
               (r ->> 'audited_at')::timestamptz as audited_at
        from public.ff_mls_parcel_audit(l.parcel_id, fp.co_no) r
      ) mpa on v.case_number is null and fp.parcel_id is not null
    )
  )
  into result
  from winnerdata.leads l
  left join winnerdata.v_producer_intake v on v.lead_id = l.lead_id
  left join public.fl_parcels fp on fp.parcel_id = l.parcel_id
  where l.lead_id = p_lead_id and l.org_id = p_org_id;

  return result;
end;
$func$;

REVOKE ALL ON FUNCTION public.ff_get_lead(uuid, uuid) FROM public;
GRANT EXECUTE ON FUNCTION public.ff_get_lead(uuid, uuid) TO anon;
