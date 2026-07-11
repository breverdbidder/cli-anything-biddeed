-- SHARD-6 (marion): C/D real tax-deed parity + I address/value/geo backfill +
-- SYN- fabrication residue purge.
-- dispatch_id: fb80bb9c-7d7d-469f-b3c0-493b5e4f9b3f
-- Session: architect-20260711T080000, loop run 3713
--
-- ROOT CAUSE (VERIFIED live via Supabase Management API, 2026-07-11): marion's
-- denominator grew from ~310 (2026-07-03, last certified 10/10) to 552 auctions,
-- almost entirely via 243 calendar_sweep_mca_v3 rows that were never parity-checked.
-- Of the 552-row canon-scoped set, 306 are foreclosure (289 already matched_clean
-- against realforeclose_aids, 17 residual) and 246 are tax_deed, ALL upcoming, with
-- only 10 matched (realforeclose_aids had only 10 TAXDEED rows for marion before
-- this session -- the tax-deed lane genuinely lacked an independent tier1 source,
-- same structural gap already documented fleet-wide in
-- 20260702_shard3_bay_gulf_marion_seminole_lee_cd_parity.sql).
--
-- pipeline.counties.taxdeed_platform for marion says 'realauction'/
-- marion.realtaxdeed.com, but public.realauction_subdomains (the verified registry,
-- last_verified 2026-07-10) confirms marion.realtaxdeed.com IS live (HTTP 200) --
-- the config is NOT stale, it just had never been harvested for these 3 upcoming
-- sale dates. A separate registry row also lists marion.realtdm.com (RealTDM tax
-- deed case-management portal, different product) as an alternative; live-probed
-- this session and it returned "NO CASES FOUND" for every date range tried
-- (blank, 05/27/2026-09/09/2026, 01/01/2020-12/31/2027) -- correctly NOT used as a
-- source; documented as a dead end, not silently retried or faked.
--
-- FIX: the GHA scrape-realauction-county.yml path is currently blocked fleet-wide
-- by Firecrawl HTTP 402 (out of credits, confirmed live via 2 failed dispatch runs
-- this session: 29145711128, 29145709368). Used the existing Firecrawl-free direct
-- AJAX harvester instead (scripts/shard2_run2450_ajax_realforeclose_harvest.py,
-- already documented to support platform_domain='realtaxdeed.com') against
-- marion.realtaxdeed.com for the 3 real upcoming tax_deed auction dates already
-- present in our own data (2026-07-15 n=89, 2026-07-22 n=37, 2026-08-19 n=100,
-- taken directly from the unmatched rows' own auction_date column -- not guessed):
--   marion 07/15/2026: parsed=62 inserted_or_merged=62
--   marion 07/22/2026: parsed=33 inserted_or_merged=33
--   marion 08/19/2026: parsed=50 inserted_or_merged=50
--   TOTAL: parsed=145 inserted_or_merged=145 (realforeclose_aids TAXDEED rows for
--   marion: 10 -> 155)
--
-- Then applied the SAME guarded cross-source match pattern already proven for
-- marion's foreclosure lane (digit-guard on parcel_id rejects sentinel values;
-- exact case_number match OR substring match OR exact-digit parcel_id match).
-- Sample-verified 15 of the 127 resulting matches by hand before applying live:
-- every one had EXACT case_number AND EXACT parcel_id agreement between our row
-- and the independently-scraped realtaxdeed row (e.g. case 173012021 / parcel
-- 4219-257-010, both sides identical) -- no sentinel/placeholder values, no
-- forced matches.
--
-- 100 tax_deed rows (across the same 3 dates) remain unmatched after this harvest
-- -- most likely cases already pulled/resolved/redeemed before this session's live
-- scrape (the PREVIEW page reflects current state, not historical), not a matcher
-- gap. NOT forced. Flagged for the next marion session to re-diff against a fresh
-- scrape closer to each sale date.
--
-- VERIFIED before/after (pencil_dod_evaluate_county, 2026-07-11):
--   C: 54.2% (matched_clean=299 of 552) -> 77.0% (matched_clean=425 of 552)  FAIL->FAIL (real gain, still below 95%)
--   D: 54.2% -> 77.0% (matched_any tracks matched_clean 1:1 here, no divergent rows) FAIL->FAIL
--   A/B/E/F/G/H: unchanged, no regression.
--
-- I CRITERION BACKFILL (same session, same trusted independent source):
-- 126 of the 127 newly-matched rows were missing property_address and/or
-- assessed_value on the multi_county_auctions side -- backfilled from the SAME
-- already-cross-validated realtaxdeed match (not a new/separate claim; identical
-- provenance to the C/D fix). missing_value dropped 243 -> 117, missing_address
-- dropped to 2.
--
-- Separately, 18 of the newly-address-backfilled rows had real street addresses
-- (not "NO SITUS" vacant-land placeholders) and were missing lat/lon. Forward-
-- geocoded via the free US Census Geocoder (geocoding.geo.census.gov, no API key,
-- same free-geocoding class already used for the calhoun reverse-geocode fix
-- 2026-07-11 same day). 17 of 18 matched with real Marion-County-plausible
-- coordinates (~29.0-29.3 N, -82.2--81.7 W); 1 address had no Census TIGER match
-- and was left NULL, not guessed. Applied live via PostgREST PATCH.
--
-- The remaining 113 of 131 "ready" rows are "NO SITUS" vacant-land tax-deed
-- parcels with no street address to geocode -- these need a real Marion County
-- Property Appraiser parcel-centroid pull (same category of build as the
-- G/I zoning-ingestion gap already flagged fleet-wide), NOT attempted this
-- session. Flagged, not faked.
--
-- I only moved 53.8% -> 54.0% (card_complete 297 -> 298 of 552) because I ALSO
-- requires the parcel_id to resolve in v_zoning_gold_standard_card (zone_code
-- present) -- marion's zoning coverage (parcel_zones) is only 295 real parcels
-- (see below), so 16 of the 17 geocoded rows still fail I on the zoning-linkage
-- leg even though address+geo+value are now all real and present. This is a
-- genuine, disclosed structural ceiling (zoning ingestion breadth), not a bug in
-- this migration -- consistent with the CLAUDE.md finding that "G and I are NOT
-- auction scraping problems ... the fleet-wide G/I fix is loading ZoneWise zoning
-- layers per county."
--
-- SYN- FABRICATION RESIDUE PURGE (hygiene, zero metric impact):
-- Found 5 parcel_zones rows (source='shard7_g_i_fix/marion_syn_parcel',
-- parcel_id IN SYN-MAR-FC-001..004, SYN-MAR-TD-001, zone_code='R-1') left behind
-- after the 2026-07-02 fabrication purge deleted the CORRESPONDING fake
-- multi_county_auctions rows (20260702_shard7_marion_syn_fabrication_cleanup.sql)
-- but never touched the zoning-side residue. VERIFIED live these 5 parcel_ids
-- have ZERO matching rows in multi_county_auctions for marion (already deleted),
-- so they contribute nothing to any current metric -- pure dead fabricated data.
-- Deleted for hygiene per HARD GUARDRAILS ("never invent numbers" extends to not
-- leaving orphaned fabricated rows sitting in the schema). zone_standards rows
-- exclusively owned by these zoning_districts were cleaned in the same pass;
-- zoning_districts rows themselves were left alone (shared/ambiguous ownership,
-- out of scope for a zero-impact hygiene pass).
--
-- Applied live 2026-07-11 via Supabase Management API (service role) before this
-- file was committed -- this migration documents and reproduces those changes.
-- Idempotent: all UPDATE/DELETE statements are guarded by IS DISTINCT FROM /
-- specific-source checks and are safe to re-run.

-- 1) C/D: stamp matched_clean for genuinely cross-validated tax_deed rows
UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realtaxdeed_marion',
    parity_checked_at = now(),
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'marion'
  AND lower(mca.county) = 'marion'
  AND mca.sale_type = 'tax_deed'
  AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false)=true)
  AND mca.parity_status IS DISTINCT FROM 'matched_clean'
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (
      length(normalize_case_number(mca.case_number)) >= 10
      AND length(normalize_case_number(ra.case_number)) >= 8
      AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
    )
    OR (
      mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
      AND mca.parcel_id ~ '[0-9]' AND ra.parcel_id ~ '[0-9]'
    )
  )
  AND mca.parity_source IS DISTINCT FROM 'tier1_realtaxdeed_marion';

-- 2) I: backfill address/value from the same verified cross-source match
UPDATE public.multi_county_auctions mca
SET property_address = COALESCE(mca.property_address, ra.property_address),
    assessed_value = COALESCE(mca.assessed_value, ra.assessed_value),
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'marion'
  AND lower(mca.county) = 'marion'
  AND mca.parity_source = 'tier1_realtaxdeed_marion'
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id)
  )
  AND (mca.property_address IS NULL OR mca.assessed_value IS NULL);

-- 3) I: SYN- fabrication residue purge (zero live join, verified orphaned)
DELETE FROM public.zone_standards
WHERE zoning_district_id IN (
  SELECT DISTINCT zoning_district_id FROM public.parcel_zones
  WHERE source = 'shard7_g_i_fix/marion_syn_parcel'
)
AND zoning_district_id NOT IN (
  SELECT zoning_district_id FROM public.parcel_zones
  WHERE source <> 'shard7_g_i_fix/marion_syn_parcel'
);

DELETE FROM public.parcel_zones
WHERE source = 'shard7_g_i_fix/marion_syn_parcel';

-- ── VERIFICATION QUERIES (run after migration) ─────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('marion');
-- SELECT count(*) FROM realforeclose_aids WHERE county_slug='marion' AND auction_type='TAXDEED';
-- SELECT count(*) FROM parcel_zones WHERE parcel_id LIKE 'SYN-MAR-%';  -- expect 0
