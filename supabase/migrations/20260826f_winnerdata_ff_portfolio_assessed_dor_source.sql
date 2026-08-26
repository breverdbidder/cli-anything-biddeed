-- Winner Data FF Worker: close 3 of the 5 real gaps found 2026-08-26 by
-- actually reading workers/winnerdata-ff/src/index.js against today's
-- chat-built portfolio FFs (Laxmi Land Investment LLC, Greenback Assets
-- Corp) -- see issue P0 "winnerdata-ff Worker -- 5 real gaps".
--
-- Gap 4 (assessed_value == county_just_value): ff_get_lead built both
-- fields from fp.jv. public.fl_parcels already carries a distinct AV_SD
-- column (confirmed live 2026-08-26, e.g. parcel 16 31 13 40968 000 0160:
-- jv=368359, av_sd=256384 -- genuinely different, not a data gap) -- this
-- was purely a wiring bug in the RPC, not a missing-data problem. Fixed by
-- exposing fp.av_sd as its own field; the Worker (separate commit) reads it
-- instead of re-using jv, and shows "Not established" rather than falsely
-- falling back to jv when av_sd is null.
--
-- Gap 5 (DOR statewide layer SSOT): decision recorded here per the issue's
-- "pick one and implement it" instruction -- INGEST job, not live
-- per-request query. fl_parcels is already the one table every FF read path
-- (ff_get_lead, ff_mls_parcel_audit, v_producer_intake) joins against, so
-- making it the target of a DOH-statewide backfill (companion script
-- scripts/property_appraiser/backfill_ff_parcels_from_doh.py, run
-- separately against the currently-referenced lead/portfolio parcels) needs
-- zero new read paths and keeps the Worker's request latency unchanged --
-- the alternative (Worker calls gis.floridahealth.gov per page view) would
-- add an uncached third-party HTTP round-trip to every /ff/:lead_id request
-- for a value that only changes on the source's own refresh cadence
-- (observed ~4 months for the existing fl_parcels batch loads, see
-- 20260824_ff_verification_badge_rpc_v2_mls_parcel_audit.sql's freshness
-- research). dor_source/dor_synced_at columns added below so ff_get_lead
-- (and eventually the template) can show which rows are DOH-confirmed vs.
-- the pre-existing FL GIO cadastral batch load, honestly -- not silently
-- claimed as SSOT-backed when they haven't been touched by that job yet.
--
-- Gap 2 (multi-parcel / portfolio): winnerdata.owner_portfolio already
-- exists (20260825_owner_portfolio.sql, built for issue "Identity cascade +
-- PORTFOLIO Fact Finder") and already enumerates a resolved owner's full
-- held book keyed by owner_key = normalize(entity_name) (see
-- scripts/identity_cascade.py's normalize() and
-- scripts/skiptrace_20260825_portfolio_batch.py). ff_get_lead never read
-- it. Fixed by adding a `portfolio` array (one element per
-- owner_portfolio row for this lead's normalized entity_name, each
-- enriched with fl_parcels.av_sd/lnd_val the same way the single-property
-- `parcel` object already is) alongside the existing single `parcel`/
-- `auction` fields -- this is additive, the single-property fields are
-- unchanged so any caller still reading only those keeps working exactly
-- as before. "One lead = one buyer NAME regardless of property count" (Aug
-- 23 2026, #19392 comment 5390376020) is satisfied by portfolio being
-- attached to the single existing lead_id/entity_name row, not by minting
-- new leads per property.
--
-- Live-verified before writing this (per CC_META_PROMPT 1.3): only 2
-- distinct owner_key values exist in owner_portfolio today -- "FRESH LEGAL
-- PERSPECTIVE PL" (14 properties) and "LEINIER CASTILLO" (1 property).
-- Only LEINIER CASTILLO has a matching row in winnerdata.leads right now,
-- so the multi-property (>=2) branch has no live lead_id to click through
-- end-to-end yet -- an honest data-coverage gap, not a defect in this
-- migration; the portfolio subquery itself is verified directly against
-- owner_key='FRESH LEGAL PERSPECTIVE PL' in the completion evidence.

-- ---------------------------------------------------------------------
-- fl_parcels: add DOR-statewide-layer provenance columns (nullable, no
-- backfill of the existing 10.5M rows -- metadata-only ALTER, safe on a
-- live table).
-- ---------------------------------------------------------------------
ALTER TABLE public.fl_parcels
  ADD COLUMN IF NOT EXISTS dor_source text,
  ADD COLUMN IF NOT EXISTS dor_synced_at timestamptz;

COMMENT ON COLUMN public.fl_parcels.dor_source IS
  'Provenance of this row''s DOR NAL fields (jv/av_sd/lnd_val/dor_uc/...). '
  'NULL = original FL GIO cadastral batch load (pre-2026-08-26). '
  '''doh_statewide'' = confirmed/refreshed live against '
  'gis.floridahealth.gov EHWATER/Parcels statewide layer (see '
  'scripts/property_appraiser/doh_statewide.py). Set only by '
  'scripts/property_appraiser/backfill_ff_parcels_from_doh.py.';
COMMENT ON COLUMN public.fl_parcels.dor_synced_at IS
  'When dor_source was last confirmed/refreshed. NULL if never run '
  'through the DOH-statewide backfill.';

-- ---------------------------------------------------------------------
-- Name normalization, shared with scripts/identity_cascade.py's
-- normalize(): uppercase, strip periods/commas, collapse whitespace
-- (incl. around '&'). Deliberately does NOT strip legal-suffix words
-- (LLC/INC/CORP) -- that distinction is what keeps real matches from
-- coincidental substring hits, same rationale as the Python original.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.ff_normalize_name(name text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT nullif(
    trim(
      regexp_replace(
        regexp_replace(
          regexp_replace(coalesce(upper(name), ''), '[.,]', '', 'g'),
          '\s*&\s*', '&', 'g'
        ),
        '\s+', ' ', 'g'
      )
    ),
    ''
  );
$$;

-- ---------------------------------------------------------------------
-- ff_get_lead v4: adds parcel.av_sd/dor_source/dor_synced_at (Gap 4 + 5)
-- and a top-level `portfolio` array (Gap 2). Everything else byte-identical
-- to the v3 body in 20260826d_rename_summitleads_to_winnerdata.sql.
-- ---------------------------------------------------------------------
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
        'jv', op.jv,
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
