-- Gold Standard shard-4 (dispatch 6284f4fc-ce46-4f84-bb14-a92199aa0dcf): nassau E/I backlog enrichment
-- Session date: 2026-09-01
--
-- Context: nassau reached a fully-verified 10/10 on 2026-08-11 (dispatch 14cdfac9)
-- with auctions_total=47. Since then, 9 new rows were ingested by the calendar-sweep
-- pipeline. 3 of them (26TD000019AXYX, 26TD000020AXYX, 26TD000021AXYX) still carried
-- parcel_id=NULL, property_address=NULL, and a repeated identical
-- assessed_value=320000/market_value=336000 placeholder pair across all 3 rows --
-- the exact same fabrication signature purged once before in this county
-- (scripts/shard2_nassau_run14cdfac9_fabricated_value_purge.py, Aug 11 session).
--
-- This migration:
--   1. Nulls the fabricated assessed_value/market_value placeholder pair on all 3 rows
--      (BLANK > WRONG -- do not propagate a value that cannot be sourced).
--   2. Writes REAL parcel_id + property_address + latitude/longitude, sourced live from
--      https://nassau.realtaxdeed.com PREVIEW pages (case matched via the embedded
--      6-digit TD sequence number, same proven mechanism as
--      scripts/shard2_bay_nassau_run14cdfac9_e_backfill.py) cross-referenced against
--      the Nassau County PA ArcGIS layer
--      (maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/TaxMap4_CitrixV2/MapServer/144,
--      outSR=4326 for true WGS84 centroid).
--   3. For 26TD000021AXYX only, writes a real assessed_value (FASMP_ASSD_VALUE_NS=100758)
--      -- 26TD000019AXYX/26TD000020AXYX are individual condo units under a shared master
--      PIN (Tennis Villas) whose JUSTVAL/FASMP_ASSD_VALUE_NS are genuinely 0 in this GIS
--      layer; left NULL rather than fabricated.
--   4. Inserts parcel_zones rows for all 3 parcels (zone codes PUD x2, R-1 x1) --
--      pre-verified that zoning_districts already has matching PUD/R-1 rows for the
--      correct Nassau jurisdictions (1508 = Unincorporated Nassau County, 865 =
--      Fernandina Beach), so this does NOT trigger the documented G-regression trap
--      (orphan zone code with no zone_standards row).
--
-- Source data (VERIFIED live 2026-09-01):
--   nassau.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=11/03/2026
--     -> 452026XX000019TDAXYX: parcel 01-6N-29-V28T-2511-0000, "2511 BOXWOOD LN FERNANDINA BEA"
--     -> 452026XX000020TDAXYX: parcel 01-6N-29-V28T-2530-0000, "2530 BOXWOOD LN FERNANDINA BEA"
--   nassau.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=11/17/2026
--     -> 452026XX000021TDAXYX: parcel 00-00-31-150F-0008-0050, "404 S 17TH ST FERNANDINA BEACH"
--   maps.ncpafl.com ArcGIS layer 144, PIN_DSP/PIN lookup, outSR=4326:
--     -> 2511/2530: Municipality=Unincorporated Nassau County, ZoningDistrict=PUD,
--        JUSTVAL=0, FASMP_ASSD_VALUE_NS=0, centroid lat=30.560836588835446 lon=-81.45069940730482
--     -> 150F-0008-0050: Municipality=City of Fernandina Beach, ZoningDistrict=R-1,
--        JUSTVAL=296798, FASMP_ASSD_VALUE_NS=100758, centroid lat=30.6637321123341 lon=-81.44809937430234
--
-- Applied live via PostgREST PATCH + Supabase Management API. This file documents the
-- SQL-equivalent for audit trail per repo guardrail #6.
--
-- ADDENDUM (same session): the C/D gap (48/56, need 54/56) decomposed into 8 rows:
--   - 26TD000009AXYX, 26TD000013AXYX: carried parity_status='PHANTOM_NOT_ON_CLERK' from
--     an earlier auto-classification. Live re-verified on
--     nassau.realtaxdeed.com PREVIEW pages for their exact auction dates (2026-09-01,
--     2026-10-13) -- both ARE listed live with parcel_id exactly matching the DB. This was
--     a mislabel (same bug pattern documented 2026-07-04), not a real phantom. Corrected
--     to parity_status='PARITY_OK'.
--   - 452025CA000317CAAXYX, 452025CA000437CAAXYX, 452025CC000274CCAXYX,
--     452025CC000614CCAXYX, 452026CA000074CAAXYX: 5 foreclosure rows ingested
--     2026-08-28, never parity-checked (parity_status was NULL). Live re-verified on
--     nassauclerk.realforeclose.com / nassau.realforeclose.com PREVIEW pages for their
--     auction dates (2026-09-03, 2026-09-10) -- all 5 exact parcel_id matches.
--     Corrected to parity_status='PARITY_OK'.
--   - 452026XX000010TDAXYX: 1 tax_deed row ingested 2026-09-01, never parity-checked.
--     Live re-verified on the same-date nassau.realtaxdeed.com PREVIEW page -- exact
--     parcel_id match. Corrected to parity_status='PARITY_OK'.
-- All 8 corrections are PARITY writes only (no parcel_id/address/value changed on these
-- 8 rows) -- applied via PostgREST PATCH, confirmed via return=representation.

-- Step 1+2+3: null the fabricated pair, write real parcel_id/address/geo/(assessed_value)
UPDATE public.multi_county_auctions
SET parcel_id = '01-6N-29-V28T-2511-0000',
    property_address = '2511 BOXWOOD LN, FERNANDINA BEACH, FL',
    latitude = 30.560836588835446,
    longitude = -81.45069940730482,
    assessed_value = NULL,
    market_value = NULL
WHERE county = 'nassau' AND case_number = '26TD000019AXYX';

UPDATE public.multi_county_auctions
SET parcel_id = '01-6N-29-V28T-2530-0000',
    property_address = '2530 BOXWOOD LN, FERNANDINA BEACH, FL',
    latitude = 30.560836588835446,
    longitude = -81.45069940730482,
    assessed_value = NULL,
    market_value = NULL
WHERE county = 'nassau' AND case_number = '26TD000020AXYX';

UPDATE public.multi_county_auctions
SET parcel_id = '00-00-31-150F-0008-0050',
    property_address = '404 S 17TH ST, FERNANDINA BEACH, FL',
    latitude = 30.6637321123341,
    longitude = -81.44809937430234,
    assessed_value = 100758,
    market_value = NULL
WHERE county = 'nassau' AND case_number = '26TD000021AXYX';

-- Step 4: zone-link the 3 parcels (idempotent -- SELECT-before-INSERT pattern in the
-- Python apply script; this SQL form uses ON CONFLICT DO NOTHING equivalent via NOT EXISTS)
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
SELECT '01-6N-29-V28T-2511-0000', '01-6N-29-V28T-2511-0000', 1508, 'PUD', 'Planned Unit Development',
       'gold_standard_shard4_6284f4fc_nassau_ncpa_gis_20260901'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '01-6N-29-V28T-2511-0000');

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
SELECT '01-6N-29-V28T-2530-0000', '01-6N-29-V28T-2530-0000', 1508, 'PUD', 'Planned Unit Development',
       'gold_standard_shard4_6284f4fc_nassau_ncpa_gis_20260901'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '01-6N-29-V28T-2530-0000');

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
SELECT '00-00-31-150F-0008-0050', '00-00-31-150F-0008-0050', 865, 'R-1', 'Low Density Residential',
       'gold_standard_shard4_6284f4fc_nassau_ncpa_gis_20260901'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '00-00-31-150F-0008-0050');

-- Step 5 (addendum): correct 8 mislabeled/never-checked parity rows to PARITY_OK,
-- each independently live-verified on the county's own PREVIEW grid (see addendum note
-- above for exact sources/dates per row).
UPDATE public.multi_county_auctions
SET parity_status = 'PARITY_OK',
    parity_source = 'nassau_clerk_tax_deed:live_recheck_20260901_shard4_6284f4fc_realtaxdeed_preview_confirmed'
WHERE county = 'nassau' AND case_number IN ('26TD000009AXYX', '26TD000013AXYX');

UPDATE public.multi_county_auctions
SET parity_status = 'PARITY_OK',
    parity_source = 'nassau_clerk_foreclosure:live_check_20260901_shard4_6284f4fc_realforeclose_preview_confirmed'
WHERE county = 'nassau' AND case_number IN (
    '452025CA000317CAAXYX', '452025CA000437CAAXYX', '452025CC000274CCAXYX',
    '452025CC000614CCAXYX', '452026CA000074CAAXYX');

UPDATE public.multi_county_auctions
SET parity_status = 'PARITY_OK',
    parity_source = 'nassau_clerk_tax_deed:live_check_20260901_shard4_6284f4fc_realtaxdeed_preview_confirmed'
WHERE county = 'nassau' AND case_number = '452026XX000010TDAXYX';
