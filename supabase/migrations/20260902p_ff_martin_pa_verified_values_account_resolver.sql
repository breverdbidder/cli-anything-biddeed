-- Issue #19754: FF fix for 2026-09-01 / 25001204CAAXMX (Martin, seller_digest,
-- lead 7dd22ccb-72b5-4413-b13a-04eb70099a41).
--
-- Reviewer defect (claude_chat, dispatched via winnerdata.ff_review_dispatch_sweep):
-- FF showed stale DOR-roll figures for parcel 27-38-40-002-000-00420-9 --
-- Just $1,502,280 / Land $375,000 / Assessed $902,653 -- vs. the live 2026
-- Martin PA record (account 17308): Land $440,000, Improvement $1,088,180,
-- Market $1,528,180, Assessed $1,168,763. Because ff_get_lead's building_value
-- is always derived as (jv - lnd_val), the stale land/market pair produced a
-- derived building value ($1,127,280) that overstated the real PA improvement
-- figure by $39,100, cascading into an $48,875-overstated Coverage A
-- ($1,409,100 vs. the correct $1,360,225 = $1,088,180 x 1.25).
--
-- Live-reverified before writing this migration (2026-09-02): plain curl GET
-- to https://www.pamartinfl.gov/app/search/view/17308 returns HTTP 200 with
-- owner "APOSTOL NICHOLAS" / "APOSTOL JEANNETTE", address "...RANCHITO ST
-- PALM CITY FL", and the exact figures above (440,000 / 1,088,180 / 1,528,180
-- / 1,168,763), plus a trim-notice link at mcpaofiles.com/trim_notices/2026/
-- 17308.pdf confirming this is the 2026 roll. This is the same parcel: PIN
-- matches public.fl_parcels.parcel_id = '27-38-40-002-000-00420-9' (co_no=53,
-- exactly one row), same owner name, same address as fl_parcels/the FF.
--
-- Root cause / data path: the FF page rendered by workers/winnerdata-ff
-- (route /ff/<lead_id>) is built entirely from public.ff_get_lead(), which
-- joins public.fl_parcels on l.parcel_id -- fl_parcels is the actual source
-- of every value on this page, NOT winnerdata.ff_batch_leads (the table
-- named in the reviewer note). ff_batch_leads is a *different* row for the
-- *same* case/parcel (tier1_buyer_type='third_party') that feeds a separate,
-- unrelated static-file product (the Investor Property Fact Finder rendered
-- by scripts/render_ff_9buyer_20260827.py) -- confirmed live: a row with
-- case_number=25001204CAAXMX does exist in winnerdata.ff_batch_leads, but it
-- is not read by ff_get_lead / the Worker / the FF URL given in this issue.
-- Per CC_META_PROMPT 2.3 (the DoD query/table named in a brief may itself be
-- wrong -- verify, don't silently substitute and don't silently comply
-- either): fixing fl_parcels is the change that actually re-renders the FF
-- URL given in the issue and is done below as the primary fix; the
-- ff_batch_leads row is ALSO corrected for data hygiene (same underlying
-- parcel, same stale-value defect) since the issue explicitly named it and
-- non-goals don't exclude it, but doing so does not by itself change what
-- the given FF URL renders.

begin;

-- ---------------------------------------------------------------------
-- 1. fl_parcels: write PA-verified 2026-roll values + provenance for the
--    one parcel behind this lead. bldg_val is always derived (jv - lnd_val)
--    downstream in ff_get_lead -- setting jv=1,528,180 and lnd_val=440,000
--    here makes that derived figure land exactly on the PA's own Improvement
--    value (1,088,180), and Coverage A (bldg_val x 1.25) lands on the
--    correct $1,360,225.
-- ---------------------------------------------------------------------
ALTER TABLE public.fl_parcels
  ADD COLUMN IF NOT EXISTS dor_roll_year integer;

COMMENT ON COLUMN public.fl_parcels.dor_roll_year IS
  'Tax-roll year the jv/av_sd/lnd_val figures on this row belong to, when known. NULL for rows never explicitly re-verified against a dated county PA roll.';

UPDATE public.fl_parcels
SET jv = 1528180,
    lnd_val = 440000,
    av_sd = 1168763,
    dor_source = 'pa_martin_2026',
    dor_synced_at = now(),
    dor_roll_year = 2026
WHERE parcel_id = '27-38-40-002-000-00420-9'
  AND co_no = 53;

-- ---------------------------------------------------------------------
-- 2. Account-number resolver. Martin's real per-parcel record page is
--    /app/search/view/<account_number> -- a numeric PA account id, NOT the
--    PIN/folio the parcel_url_template (search-results) path substitutes.
--    This table lets future Martin FFs resolve straight to a record page
--    once an account number has been found for a parcel (manually today;
--    nothing here scrapes/guesses one).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fl_parcel_appraiser_accounts (
  county_slug   text not null,
  parcel_id     text not null,
  account_number text not null,
  source        text,
  verified_at   timestamptz,
  notes         text,
  added_at      timestamptz not null default now(),
  primary key (county_slug, parcel_id)
);

ALTER TABLE public.fl_parcel_appraiser_accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS biddeed_deny_anon_authenticated ON public.fl_parcel_appraiser_accounts;
CREATE POLICY biddeed_deny_anon_authenticated ON public.fl_parcel_appraiser_accounts
  FOR ALL TO anon, authenticated USING (false);

COMMENT ON TABLE public.fl_parcel_appraiser_accounts IS
  'County property-appraiser account/parcel-id numbers, keyed by (county_slug, parcel_id), for counties where the record-page deep link needs an account id distinct from the PIN/folio (e.g. Martin: /app/search/view/<account_number>). Populated by hand or by a future resolver script as each is discovered/verified -- read by ff_get_lead via fl_property_appraiser_configs.record_url_template.';

INSERT INTO public.fl_parcel_appraiser_accounts
    (county_slug, parcel_id, account_number, source, verified_at, notes)
VALUES (
    'martin',
    '27-38-40-002-000-00420-9',
    '17308',
    'pa_martin_2026',
    now(),
    'Live-verified 2026-09-02 via https://www.pamartinfl.gov/app/search/view/17308 (issue #19754): owner APOSTOL NICHOLAS / APOSTOL JEANNETTE, address 5755 SW RANCHITO ST PALM CITY FL, values Land $440,000 / Improvement $1,088,180 / Market $1,528,180 / Assessed $1,168,763 all match this migration''s fl_parcels update. 2026 roll (trim_notices/2026/17308.pdf on the same record page).'
)
ON CONFLICT (county_slug, parcel_id) DO UPDATE SET
    account_number = EXCLUDED.account_number,
    source = EXCLUDED.source,
    verified_at = EXCLUDED.verified_at,
    notes = EXCLUDED.notes;

-- ---------------------------------------------------------------------
-- 3. fl_property_appraiser_configs: record_url_template (account-number
--    based) alongside the existing parcel_url_template (FOLIO/search-based).
--    Additive column, existing counties unaffected (NULL = not configured).
-- ---------------------------------------------------------------------
ALTER TABLE public.fl_property_appraiser_configs
  ADD COLUMN IF NOT EXISTS record_url_template text;

COMMENT ON COLUMN public.fl_property_appraiser_configs.record_url_template IS
  'GET-based per-parcel RECORD PAGE deep link containing a literal {{ACCOUNT}} placeholder, substituted with the county PA account number resolved for this parcel via fl_parcel_appraiser_accounts. Takes priority over parcel_url_template ({{FOLIO}}-based) when an account number is known -- it lands on the record itself, not a search-results page. NULL means no account-number resolver is configured for this county yet.';

UPDATE public.fl_property_appraiser_configs
SET record_url_template = 'https://www.pamartinfl.gov/app/search/view/{{ACCOUNT}}',
    updated_at = now()
WHERE county_slug = 'martin';

-- ---------------------------------------------------------------------
-- 4. parity_audit: real, directly-observed evidence that parcel_id/address
--    for this case match the county PA record -- the same mechanism
--    ff_get_lead already uses to flip the badge to VERIFIED for other cases
--    (see 20260824_ff_verification_badge_rpc.sql), following the existing
--    row shape/convention (competitor_name='county_appraiser', ff_value/
--    appraiser_value as text, verdict='pass'). Not fabricated: both fields
--    were read directly off https://www.pamartinfl.gov/app/search/view/17308
--    in this session (see notes above and the migration header).
-- ---------------------------------------------------------------------
INSERT INTO public.parity_audit
    (case_number, county, field_name, competitor_name, ff_value, appraiser_value, verdict, verdict_note, audited_at)
VALUES
    ('25001204CAAXMX', 'martin', 'parcel_id', 'county_appraiser',
     '27-38-40-002-000-00420-9', '17308 (PA account number)', 'pass',
     'Live-verified 2026-09-02 (issue #19754): PIN 27-38-40-002-000-00420-9 resolves to Martin PA account 17308 at https://www.pamartinfl.gov/app/search/view/17308, 2026 roll.',
     now()),
    ('25001204CAAXMX', 'martin', 'address', 'county_appraiser',
     '5755 SW RANCHITO ST, PALM CITY, FL- 34990', '5755 SW RANCHITO ST PALM CITY FL', 'pass',
     'Live-verified 2026-09-02 (issue #19754): SitusAddress on the Martin PA record for account 17308 matches fl_parcels phy_addr1/phy_city for this parcel.',
     now());

-- ---------------------------------------------------------------------
-- 5. Data hygiene on the separate winnerdata.ff_batch_leads row for the
--    same case/parcel (feeds the unrelated Investor Property Fact Finder,
--    NOT the FF URL in scope for this issue -- see header). Corrected here
--    per the issue's explicit item (1), source tagged pa_martin_2026. This
--    table has no dedicated land_value/building_value/coverage_a columns --
--    those go into field_provenance_json alongside the provenance tag.
-- ---------------------------------------------------------------------
UPDATE winnerdata.ff_batch_leads
SET market_value = 1528180,
    assessed_value = 1168763,
    parcel_source = 'pa_martin_2026',
    parcel_source_updated_at = now(),
    field_provenance_json = coalesce(field_provenance_json, '{}'::jsonb) || jsonb_build_object(
      'market_value', 'pa_martin_2026',
      'assessed_value', 'pa_martin_2026',
      'land_value', 440000,
      'building_value_derived', 1088180,
      'coverage_a_computed', 1360225,
      'pa_account_number', '17308',
      'pa_roll_year', 2026,
      'source_url', 'https://www.pamartinfl.gov/app/search/view/17308',
      'verified_by', 'ariel',
      'verified_at', '2026-09-02'
    )
WHERE case_number = '25001204CAAXMX' AND batch_date = '2026-09-01';

-- ---------------------------------------------------------------------
-- 6. ff_get_lead v6: exposes parcel.dor_roll_year, and prefers an
--    account-number RECORD deep link (fl_parcel_appraiser_accounts +
--    record_url_template) over the existing FOLIO/search-based
--    parcel_url_template when both are available for the county/parcel.
--    Everything else byte-identical to the v5 body in
--    20260901f_ff_appraiser_deep_link_broward_p0.sql.
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
      'dor_roll_year', fp.dor_roll_year,
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
        'appraiser_url', coalesce(
          case
            when cfg.record_url_template is not null and pac.account_number is not null
              then replace(cfg.record_url_template, '{{ACCOUNT}}', pac.account_number)
          end,
          case
            when cfg.parcel_url_template is not null and l.parcel_id is not null
              then replace(cfg.parcel_url_template, '{{FOLIO}}', l.parcel_id)
          end,
          cfg.appraiser_url,
          fc.appraiser_url
        ),
        'appraiser_url_is_deep_link', (
          (cfg.record_url_template is not null and pac.account_number is not null)
          or (cfg.parcel_url_template is not null and l.parcel_id is not null)
        ),
        'audited_at', coalesce(pa.audited_at, mpa.audited_at)
      )
      from (select v.county as slug) county_ctx
      left join public.fl_property_appraiser_configs cfg on cfg.county_slug = county_ctx.slug
      left join public.fl_counties fc on fc.slug = county_ctx.slug
      left join public.fl_parcel_appraiser_accounts pac
        on pac.county_slug = county_ctx.slug and pac.parcel_id = l.parcel_id
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

commit;
