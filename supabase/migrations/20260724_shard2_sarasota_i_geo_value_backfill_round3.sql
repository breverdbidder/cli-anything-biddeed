-- Gold Standard shard-2 (sarasota): letter I (property card completeness), 3rd backfill pass.
-- Session date 2026-07-24. Ran AFTER a parallel agent in this same session landed
-- 20260724_shard2_sarasota_g_zone_standards_pk1000_gap.sql (letter G zoning_districts fix).
--
-- BASELINE (VERIFIED live this session, via pencil_dod_evaluate_county('sarasota'), taken
-- AFTER the sibling G migration had already applied):
--   I: card_complete=314 of 350 (89.7%), FAIL (threshold 95%). Target >=333/350 (95%).
--
-- DIAGNOSIS (fresh live query this session, exact card_complete predicate from
-- pencil_dod_evaluate_county's own SQL text): 27 of 350 rows in multi_county_auctions for
-- lower(county)='sarasota' fail the card_complete predicate (property_address IS NOT NULL AND
-- geo present AND assessed/market value present AND parcel_id resolves to a zoned parcel in
-- v_zoning_gold_standard_card). Bucketed by which field is missing:
--   5  rows: property_address IS NULL, parcel_id IS NULL -- pure calendar_sweep_mca_v3 stub
--            rows (only case_number/judgment_amount/sale_type/auction_date populated, zero
--            plaintiff/owner_name/clerk_url/seo_url on any of them). Case numbers: 2024 CA
--            006290/006304/006330/006332 NC, 2025 CA 005184 NC. Sarasota Clerk of Court public
--            case search (sarasotaclerk.com) returned HTTP 403 on direct fetch this session
--            (WAF-blocked, requires an interactive/authenticated session) -- no address, no
--            owner, no plaintiff to key a Property Appraiser lookup off of. Left completely
--            untouched. BLANK > WRONG -- out of scope for a geo/value backfill without a real
--            source; flagged for a future session with clerk-portal access.
--   14 rows: have a real parcel_id AND a real property_address, but are condominium-unit
--            parcels (addresses carry unit suffixes: '#2107', '#318 BLD 3', '101', '#33',
--            '306 BLD', '#103 SAILF', etc.) whose 10-digit tax-account number was queried
--            individually (not just in the batch OR-chunk) against
--            ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0 this
--            session and returned ZERO features every time. Prefix search (first 6 digits of
--            the account) confirms the layer *does* carry other parcels in the same
--            subdivision/plat -- the layer is real and live -- but not these specific
--            condo-unit account numbers, meaning this hosted layer's roll does not carry
--            per-unit condo records at this account precision. Four of these
--            (0104132007, 0175041024, 2022011063, 2027034007) were already flagged as
--            no-match in the prior migration
--            20260721_gold_standard_shard6_run5361_sarasota_i_geo_value_backfill.sql; the
--            other 10 (0012042111, 0020011231, 0044142019, 0061121113, 0101092001,
--            0106154035, 0129072068, 0157032147, 0441074012, 0791061733's sibling
--            1131210006 is NOT in this bucket -- see below) are newly-confirmed no-match this
--            session. Left completely untouched -- no fabricated/borrowed geometry, no
--            fl_parcels substitution, no county-centroid placeholder.
--            NOTE: parcel_id=0441074012 additionally carries a pre-existing bogus non-Sarasota
--            geocode (lat=30.4576288, lon=-84.3313005 -- a Tallahassee-area coordinate, clearly
--            wrong for a Sarasota county record) already present in the DB before this session.
--            Not touched/corrected here (out of scope -- this migration only fills genuinely-
--            NULL cells via COALESCE and does not overwrite pre-existing non-NULL values, per
--            this shard's established COALESCE-only convention); flagged for a future data-
--            quality pass.
--   7  rows: real, non-condo, non-unit parcel_id + property_address, confirmed via direct
--            single-account query against the same ags3.scgov.net ParcelProperty FeatureServer
--            already proven working in migrations 20260721_..._sarasota_i_geo_value_backfill.sql
--            and 20260721_..._sarasota_i_zone_extend.sql. THESE ARE THE TARGET OF THIS
--            MIGRATION.
--
-- FIELD-MAPPING VERIFICATION (done BEFORE the batch, all 7 targeted accounts spot-checked on
-- house-number + street-name match against our existing property_address column):
--   0144010003 -> '132 OSPREY POINT DR OSPREY FL, 34229'   (ours: '132 OSPREY POINT DR, OSPREY, FL- 34229')
--   0170090035 -> '700 FOREST ST NOKOMIS FL, 34275'         (ours: '700 FOREST ST, NOKOMIS , 34275')
--   0212050001 -> '1115 WAGON WHEEL DR SARASOTA FL, 34240'  (ours: '1115 WAGON WHEEL DR, SARASOTA, 34240')
--   0384150005 -> '205 PORTIA ST S NOKOMIS FL, 34275'       (ours: '205 PORTIA ST S, NOKOMIS, 34275')
--   0402020022 -> '569 MISTY PINE DR VENICE FL, 34292'      (ours: '569 MISTY PINE DR, VENICE, FL- 34292')
--   0791061733 -> '516 MADONNA NORTH PORT FL, 34287'        (ours: '516 MADONNA, NORTH PORT, FL- 34287')
--   1131210006 -> 'DALEWOOD CIR NORTH PORT FL, 34288'       (ours: 'DALEWOOD CIR, NORTH PORT, 34288')
-- All 7: 0 house-number/street mismatches. All 7 centroids fall inside the Sarasota County FL
-- bounding box (26.8-27.5 lat / -82.7..-82.0 lon) used as the sanity check in the prior I
-- migration.
--
-- METHOD: queried ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0
-- with where=account IN (<22 targeted accounts>), outFields=account,fulladdress,assd,just,txbl,
-- returnGeometry=true, outSR=4326 (WGS84 lon/lat). 7 of 22 matched; centroid computed via the
-- same standard shoelace-formula area-weighted-centroid method as the prior migration (largest
-- ring by |signed area|). UPDATE ... SET column = COALESCE(column, <new value>) for latitude,
-- longitude, assessed_value (from assd), market_value (from just), and source_url -- COALESCE
-- ensures only genuinely-NULL cells are filled; two of the 7 rows already had a real
-- assessed_value from a prior pipeline and retain it unchanged (0170090035, 0212050001,
-- 0384150005, 1131210006 -- market_value was NULL on all of these and is newly filled from
-- `just`).
--
-- EXPECTED EFFECT: these 7 rows already had real property_address values; two
-- (0170090035, 1131210006) were already zoning_linked (per v_zoning_gold_standard_card) and
-- were failing card_complete purely on missing geo/value -- this migration closes those two
-- completely. The other 5 (0144010003, 0212050001, 0384150005, 0402020022, 0791061733) were
-- ALSO missing the zoning-crosswalk link (parcel_id not present in v_zoning_gold_standard_card
-- for this county) -- filling geo/value alone will NOT flip card_complete for those 5 without a
-- separate parcel_zones INSERT, which requires a verified per-parcel zoning source query (out
-- of scope for this geo/value-only migration; not fabricated here). Net expected card_complete
-- gain from this migration alone: +2 (316 of 350, 90.3%) -- reported honestly below, not
-- rounded up to a false 95% claim.
--
-- Dispatch: this shard-2 sarasota session, letter I 3rd backfill attempt. Applied live via
-- mgmt_sql.py against project mocerqjnksmhcjzxrewo, then this file committed for the record.

BEGIN;

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.209783),
  longitude = COALESCE(longitude, -82.499085),
  assessed_value = COALESCE(assessed_value, 596300),
  market_value = COALESCE(market_value, 596300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270144010003%27&f=json')
WHERE id = '0b803cb5-63ea-44ee-a5be-4c630f7eaec6';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.133522),
  longitude = COALESCE(longitude, -82.451507),
  assessed_value = COALESCE(assessed_value, 169800),
  market_value = COALESCE(market_value, 169800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270170090035%27&f=json')
WHERE id = 'fe3e1747-93e0-4d0b-889a-eb7100406fe9';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.346055),
  longitude = COALESCE(longitude, -82.430372),
  assessed_value = COALESCE(assessed_value, 751773),
  market_value = COALESCE(market_value, 921200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270212050001%27&f=json')
WHERE id = '4ad94005-d226-4644-b3e5-b8ad25e7101c';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.12353),
  longitude = COALESCE(longitude, -82.43785),
  assessed_value = COALESCE(assessed_value, 135100),
  market_value = COALESCE(market_value, 135100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270384150005%27&f=json')
WHERE id = '2f5ed663-16b6-4e85-8e50-7a54d645246b';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.115019),
  longitude = COALESCE(longitude, -82.406911),
  assessed_value = COALESCE(assessed_value, 378700),
  market_value = COALESCE(market_value, 378700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270402020022%27&f=json')
WHERE id = 'f314ed43-6b6b-4378-9e27-38c7422d5800';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.036435),
  longitude = COALESCE(longitude, -82.262792),
  assessed_value = COALESCE(assessed_value, 77800),
  market_value = COALESCE(market_value, 77800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270791061733%27&f=json')
WHERE id = 'a90010c2-fa3a-4a3c-88c7-94ef91718838';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.056863),
  longitude = COALESCE(longitude, -82.084888),
  assessed_value = COALESCE(assessed_value, 3543),
  market_value = COALESCE(market_value, 6500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271131210006%27&f=json')
WHERE id = 'a9e1c987-cd18-4383-a2c5-5dd82bc370ba';

COMMIT;

-- ============================================================
-- VERIFICATION (run live after apply):
--   SELECT public.pencil_dod_evaluate_county('sarasota');  -- letter I before/after pasted in
--   session report.
-- ============================================================
