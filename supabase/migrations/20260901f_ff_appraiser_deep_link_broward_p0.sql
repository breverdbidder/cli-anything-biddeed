-- P0 fix (issue: "county property appraiser link is a generic homepage, not a
-- parcel deep-link"). Live-verified 2026-09-01 on a real FF: case
-- CACE-25-003569, parcel 484307030140, Broward -- clicking "View county
-- property appraiser record" landed on web.bcpa.net's generic search
-- homepage, not that parcel's record page.
--
-- Root cause, confirmed live: ff_get_lead's verification.appraiser_url has
-- ALWAYS been a static string (coalesce(cfg.appraiser_url, fc.appraiser_url)
-- with zero substitution) -- so even the 8 counties already carrying rows in
-- fl_property_appraiser_configs (palm_beach, alachua, flagler, manatee,
-- marion, broward, lee, wakulla) never actually produced a per-parcel link.
-- Broward's own configured appraiser_url was itself the generic
-- "https://web.bcpa.net/bcpaclient/#/Record-Search" search page -- this was
-- never a Broward-specific gap, it's a missing substitution mechanism that
-- affects every county, configured or not.
--
-- Fix: add a `parcel_url_template` column holding a URL with a `{{FOLIO}}`
-- placeholder for counties where a real, live-verified GET-based per-parcel
-- deep link exists (no JS/form POST required), and wire ff_get_lead to
-- substitute the lead's parcel_id into that template. Populated for 3
-- counties this session, each independently live-verified via curl before
-- being written here:
--
--   broward:    https://bcpa.net/RecInfo.asp?URL_Folio={{FOLIO}}
--     Verified for folio 484307030140 (the exact case from this issue):
--     returns "4832 NE 19 TERRACE, POMPANO BEACH FL 33064" / owner
--     "POWELL, CHAD RUSSELL" -- exact match to public.fl_parcels
--     (phy_addr1='4832 NE 19 TER', phy_city='POMPANO BEACH',
--     own_name='POWELL,CHAD RUSSELL') and multi_county_auctions
--     (case CACE-25-003569, same parcel/address). Plain httpx/curl GET,
--     no cert bypass, no JS -- this is bcpa.net's legacy ASP record page,
--     distinct from the web.bcpa.net Angular SPA cfg.appraiser_url pointed
--     at (which is the search UI, not a record page).
--   palm_beach: https://pbcpao.gov/Property/Details?parcelId={{FOLIO}}
--     Template already sat in cfg.appraiser_url ending in "parcelId=" with
--     nothing ever appended after it (known_issues text from the 2026-08-24
--     dispatch already documented this as a working direct GET, it was just
--     never wired to append the parcel value) -- this migration is the
--     substitution mechanism that finally uses it as intended.
--   marion:     https://www.pa.marion.fl.us/PRC.aspx?key={{FOLIO}}&YR=2026&mName=False&mSitus=False
--     Per the same 2026-08-24 known_issues text: our Winner Data parcel_id
--     for Marion IS the site's own numeric PrimeKey, so no ID-translation
--     step is needed -- same substitution mechanism applies directly.
--
-- Live-probed and NOT wired this session (cost-discipline: one attempt per
-- approach, no fabricated templates):
--   - lee: leepa.org is ASP.NET WebForms with __doPostBack search
--     (confirmed via known_issues + a fresh probe of a guessed
--     Display/DisplayParcel.aspx GET path -> "Invalid Request"). No GET-based
--     deep link found. Left on generic-homepage fallback.
--   - manatee: manateepao.gov/parcel/?parid=<PARID> returns HTTP 200 but the
--     WordPress SPA does not server-render the record (confirmed live: the
--     known address/owner strings for a real test parcel do not appear in
--     the raw HTML, only client-side JS fetch would populate them). Left on
--     generic-homepage fallback.
--   - alachua, flagler, wakulla: already documented blocked_by_waf=true in
--     fl_property_appraiser_configs from the 2026-08-24 dispatch (Cloudflare
--     blocks the search-submit action). No new avenue found; left as-is.
--   - miami_dade (highest-volume unconfigured county, 31 leads): probed the
--     PropertySearch API + SPA hash-route guess for folio 1079150021380 --
--     API path 404'd, SPA route does not server-render. No deep link found
--     this session. Left on generic fl_counties fallback.
--   - pasco, polk, washington (next-highest volume, 31/16/15 leads): no
--     fl_parcels-matched sample row available to test against this session
--     (own_name null for available leads) -- deferred rather than guessing a
--     URL pattern with nothing to verify it against. Flagged for next
--     session's priority queue.

ALTER TABLE public.fl_property_appraiser_configs
    ADD COLUMN IF NOT EXISTS parcel_url_template text;

COMMENT ON COLUMN public.fl_property_appraiser_configs.parcel_url_template IS
    'GET-based per-parcel deep-link URL containing a literal {{FOLIO}} placeholder, substituted with the lead''s parcel_id by ff_get_lead. NULL means no live-verified deep-link GET pattern exists for this county yet -- appraiser_url (a search/homepage URL) is used as-is instead.';

UPDATE public.fl_property_appraiser_configs
SET parcel_url_template = 'https://bcpa.net/RecInfo.asp?URL_Folio={{FOLIO}}',
    updated_at = now()
WHERE county_slug = 'broward';

UPDATE public.fl_property_appraiser_configs
SET parcel_url_template = 'https://pbcpao.gov/Property/Details?parcelId={{FOLIO}}',
    updated_at = now()
WHERE county_slug = 'palm_beach';

UPDATE public.fl_property_appraiser_configs
SET parcel_url_template = 'https://www.pa.marion.fl.us/PRC.aspx?key={{FOLIO}}&YR=2026&mName=False&mSitus=False',
    updated_at = now()
WHERE county_slug = 'marion';

-- ff_get_lead v5: substitute parcel_url_template when present (real deep
-- link), else fall back to the existing static-URL behavior unchanged.
-- Also surfaces `appraiser_url_is_deep_link` so the Worker can render
-- honest link text -- "View ... record" only when it actually is one,
-- "Search ... records (folio X)" otherwise (issue scope item 5: the link
-- text must not overclaim for counties still on the generic fallback).
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
        'appraiser_url', coalesce(
          case
            when cfg.parcel_url_template is not null and l.parcel_id is not null
              then replace(cfg.parcel_url_template, '{{FOLIO}}', l.parcel_id)
          end,
          cfg.appraiser_url,
          fc.appraiser_url
        ),
        'appraiser_url_is_deep_link', (cfg.parcel_url_template is not null and l.parcel_id is not null),
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
