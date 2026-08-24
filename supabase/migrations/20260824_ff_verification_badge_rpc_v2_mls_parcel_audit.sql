-- Issue #19435: MLS-track property appraiser verification.
--
-- Filename note: #19434's completion comment flagged a latent replay-order
-- bug -- 20260824_winnerdata_ff_worker_rpc.sql (an older, pre-verification
-- version of ff_get_lead) sorts AFTER 20260824_ff_verification_badge_rpc.sql
-- alphabetically, so a from-empty `supabase db push` replay would silently
-- clobber the working function. This file replaces ff_get_lead again, so it
-- has the identical hazard against ff_verification_badge_rpc.sql unless its
-- name is chosen to sort after it -- which is why this file is named
-- ff_verification_badge_rpc_v2_... rather than something alphabetically
-- earlier (confirmed by listing: mls_parcel_completeness_audit.sql would
-- have sorted BEFORE verification_badge_rpc.sql and reintroduced the same
-- bug for this function). The broader systemic issue (same-date migrations
-- ordered alphabetically, not chronologically) is still open and unfixed
-- beyond this one instance -- see #19434's finding.
--
-- #19434 confirmed the seller FF verify badge can NEVER show VERIFIED for an
-- MLS-sourced lead (active/pending listing) -- the only existing audit source,
-- public.parity_audit, is keyed by court case_number, and an MLS-sourced lead
-- has no case (it is a private real estate transaction, not a foreclosure).
--
-- This migration adds a second, honest audit path for the MLS track. It does
-- NOT touch parity_audit or the auction-track badge logic -- both paths
-- coexist in ff_get_lead's verification object (either can independently
-- produce VERIFIED=true).
--
-- Design confirmed live before writing this (per CC_META_PROMPT 1.3, inspect
-- before assume):
--   1. "Address resolves to exactly one fl_parcels row" is NOT already
--      computed/persisted anywhere upstream. Checked scripts/summitleads_pipeline.py
--      and 20260824_summitleads_mls_sale_close_wiring.sql (the HomeHarvest
--      MLS-sale-close matcher): its address match uses
--      `DISTINCT ON (c.id) ... ORDER BY c.id, fp.parcel_id NULLS LAST` --
--      i.e. when a street address collides across multiple fl_parcels rows
--      (multi-unit buildings), it silently picks one deterministically and
--      records only the winning parcel_id, never an ambiguity flag. So the
--      issue's assumption ("likely already computed... confirm and reuse")
--      does not hold -- there is nothing to reuse. This migration re-derives
--      it fresh: (co_no, phy_addr1, phy_zipcd) is NOT globally unique in
--      fl_parcels (that's the whole multi-unit-collision problem), so ambiguity
--      is checked at audit time by counting how many fl_parcels rows in the
--      same county share the resolved parcel's exact street address.
--      fl_parcels.(co_no, parcel_id) itself IS unique (constraint
--      fl_parcels_co_no_parcel_id_key) -- once a single parcel_id is on the
--      lead, that part can never be ambiguous; the address-collision risk is
--      upstream of that, in how the parcel_id got chosen in the first place.
--   2. Completeness fields checked live for schema fit: fl_parcels has
--      act_yr_blt/eff_yr_blt (year built), lnd_val (land value), jv (just
--      value; building value is computed elsewhere as jv - lnd_val, same as
--      ff_get_lead already does). All three are real, populated columns.
--   3. Freshness: fl_parcels DOES carry both scraped_at and updated_at
--      (100% populated for brevard/duval/orange/duval, checked live). But the
--      ingestion pattern is a periodic full-county-batch refresh, not
--      per-parcel -- e.g. every co_no=15 (Brevard) row shares updated_at
--      2026-06-2x (one batch), and the whole DB shows exactly two refresh
--      waves this year (2026-02, 2026-06), ~4 months apart, both fully
--      populated. So a per-parcel staleness check is really a per-batch
--      staleness signal, not individual-parcel data quality -- documented
--      honestly here rather than presented as more granular than it is.
--      Chose 180 days (matches the observed ~4-month cadence plus margin) --
--      tight enough to be a real ceiling (an abandoned county would trip it),
--      loose enough not to fail the entire DB on the very day this ships
--      (current worst case, checked live: 63 days stale).

create or replace function public.ff_mls_parcel_audit(p_parcel_id text, p_co_no integer)
returns jsonb
language plpgsql
stable
as $$
declare
  fp record;
  addr_match_count integer;
  missing_fields text[] := '{}';
  freshness_days integer;
  result jsonb;
begin
  select * into fp
  from public.fl_parcels
  where parcel_id = p_parcel_id and co_no = p_co_no;

  if not found then
    return jsonb_build_object(
      'verdict', 'fail',
      'verdict_note', 'No county property appraiser record found for this parcel -- cannot verify.',
      'checks', jsonb_build_object('parcel_found', false),
      'audited_at', now()
    );
  end if;

  if fp.phy_addr1 is null or fp.phy_zipcd is null then
    addr_match_count := null;
  else
    select count(*) into addr_match_count
    from public.fl_parcels fp2
    where fp2.co_no = fp.co_no
      and fp2.phy_addr1 = fp.phy_addr1
      and fp2.phy_zipcd = fp.phy_zipcd;
  end if;

  if fp.act_yr_blt is null and fp.eff_yr_blt is null then
    missing_fields := array_append(missing_fields, 'year_built');
  end if;
  if fp.lnd_val is null then
    missing_fields := array_append(missing_fields, 'land_value');
  end if;
  if fp.jv is null then
    missing_fields := array_append(missing_fields, 'just_value');
  end if;

  freshness_days := floor(extract(epoch from (now() - fp.updated_at)) / 86400);

  result := jsonb_build_object(
    'checks', jsonb_build_object(
      'parcel_found', true,
      'address_match_count', addr_match_count,
      'address_unambiguous', addr_match_count = 1,
      'missing_fields', to_jsonb(missing_fields),
      'complete', array_length(missing_fields, 1) is null,
      'freshness_days', freshness_days,
      'fresh_enough', fp.updated_at is not null and fp.updated_at > now() - interval '180 days'
    ),
    'audited_at', now()
  );

  if addr_match_count is null or addr_match_count = 0 then
    result := result || jsonb_build_object(
      'verdict', 'fail',
      'verdict_note', 'This property''s address is not on file in county property appraiser records -- cannot confirm a single parcel match.'
    );
  elsif addr_match_count > 1 then
    result := result || jsonb_build_object(
      'verdict', 'fail',
      'verdict_note', format(
        'This property''s address matches %s separate parcel records in the county property appraiser data (e.g. a multi-unit building) -- cannot confirm a single unambiguous parcel match.',
        addr_match_count
      )
    );
  elsif array_length(missing_fields, 1) is not null then
    result := result || jsonb_build_object(
      'verdict', 'fail',
      'verdict_note', format(
        'County property appraiser record for this parcel is missing required appraisal data (%s) -- cannot verify a complete record.',
        array_to_string(missing_fields, ', ')
      )
    );
  elsif fp.updated_at is null or fp.updated_at <= now() - interval '180 days' then
    result := result || jsonb_build_object(
      'verdict', 'fail',
      'verdict_note', format(
        'County property appraiser record for this parcel was last refreshed %s days ago, beyond the 180-day freshness threshold for cross-verification.',
        freshness_days
      )
    );
  else
    result := result || jsonb_build_object(
      'verdict', 'pass',
      'verdict_note', 'Verified against county property appraiser records: single confirmed parcel match with complete appraisal data.'
    );
  end if;

  return result;
end;
$$;

revoke all on function public.ff_mls_parcel_audit(text, integer) from public;
grant execute on function public.ff_mls_parcel_audit(text, integer) to anon, authenticated, service_role;

-- Extend ff_get_lead: badge can now be VERIFIED via EITHER path --
--   court_record        -- existing, unchanged: parity_audit verdict='pass' for this case_number
--   parcel_completeness  -- new: ff_mls_parcel_audit verdict='pass' for this parcel, only
--                           considered when the lead has no case_number (MLS track). An
--                           auction-track lead (case_number present) never falls through to
--                           this branch, so parity_audit remains the sole authority there --
--                           this migration adds a path, it does not replace or weaken the
--                           existing one.
-- verify_reason now honestly names which path ran and what it means, per issue requirement 3
-- (never presents the two as equivalent).
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
  from summitleads.leads l
  left join summitleads.v_producer_intake v on v.lead_id = l.lead_id
  left join public.fl_parcels fp on fp.parcel_id = l.parcel_id
  where l.lead_id = p_lead_id and l.org_id = p_org_id;

  return result;
end;
$$;

revoke all on function public.ff_get_lead(uuid, uuid) from public;
grant execute on function public.ff_get_lead(uuid, uuid) to anon;
