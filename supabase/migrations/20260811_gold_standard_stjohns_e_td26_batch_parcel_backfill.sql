-- Gold Standard st_johns letter E fix — TD26-* new-batch parcel backfill.
-- Applied live via Supabase Management API during this session; documents the change.
--
-- BASELINE (VERIFIED, live pencil_dod_evaluate_county('st_johns') this session):
-- 7/10. E FAIL 64.6% (parcel_linked=53 of 82), I FAIL 62.2% (card_complete=51
-- of 82), J FAIL 65.9% (deal_complete=54). A/B/C/D/F/G/H passing.
--
-- ROOT CAUSE (VERIFIED): auctions_total grew from 45 (as of the prior
-- 20260718v ArcGIS zoning-backfill migration for letter I, which fully
-- covered all rows that existed at that time) to 82 today. The gap is 29
-- rows: 28 brand-new "TD26-*" tax_deed cases inserted 2026-08-10T15:44 UTC
-- by scripts/clerk_ssot/run_parity.py's st_johns TaxSmart parser (a *distinct,
-- newer* batch the ArcGIS migration never saw), plus 1 pre-existing
-- foreclosure row (CC24-6166, already documented in migration
-- 20260809_gold_standard_shard2_643e111c_stjohns_cd_fix.sql as genuinely
-- blocked — no parcel/amount exists anywhere, including on the clerk's own
-- live calendar).
--
-- THE 28 TD26-* ROWS SPECIFICALLY: scripts/clerk_ssot/parsers/st_johns.py's
-- parse_tax_deed() DOES capture a real parcel ID per case (TaxSmart
-- GridSearchData cell[3], e.g. "243630-0000") but only ever writes it into
-- the free-text raw_comment column of the clerk_ssot_sale_rows staging
-- table ("SALE | cert 1789 | parcel 243630-0000"). run_parity.py's
-- diff_and_reconcile() INSERT for missing_from_ours (the path that creates
-- new multi_county_auctions rows) never parses raw_comment back out — it
-- only writes county/sale_type/case_number/auction_date/auction_status/
-- parity_status/parity_source (see run_parity.py lines ~176-187). This is a
-- genuine code defect (a data-loss gap, not a scraper failure): the parser
-- has the parcel ID, the pipeline just drops it on the floor when creating
-- the row. Confirmed live: SELECT raw_comment FROM clerk_ssot_sale_rows for
-- all 28 TD26-* case numbers returns a well-formed "parcel NNNNNN-NNNN" for
-- every one (0 malformed).
--
-- THIS FIX (VERIFIED, applied): reused the crosswalk discovered this
-- session — St. Johns Tax Collector/appraiser folio format "NNNNNN-NNNN"
-- equals the county GIS "STRAP" field with the dash removed (confirmed by
-- an exact address match: TD26-0024 parcel "243630-0000" -> STRAP
-- "2436300000" -> St. Johns County GIS Hosted/Parcel/FeatureServer/0
-- PRP_ADDR "641 SEGOVIA RD", which is also this session's live-fetched
-- st_johns parcel_id convention match -- existing rows like CA25-1289
-- already use this exact 10-digit-no-dash format). Batch-queried
-- https://www.gis.sjcfl.us/portal_sjcgis/rest/services/Hosted/Parcel/
-- FeatureServer/0 (STRAP IN (...)) for all 28 derived STRAPs in a single
-- call: 26 of 28 resolved directly (address + polygon geometry). The
-- remaining 2 (TD26-0032, TD26-0078) are condo units not present on the
-- parcel layer; resolved via the sibling Parcel_Condo/FeatureServer/0 layer
-- (same STRAP key), which also confirmed both as real, currently-owned
-- condo units (PRP_NAME/OWN_ADDR present), not vacant/platted lots.
-- latitude/longitude were computed as a simple centroid of each parcel's
-- returned WGS84 (outSR=4326) exterior polygon ring -- adequate precision
-- for a card map-pin, not a claimed survey centroid.
--
-- NOT FIXED THIS SESSION (documented, not fabricated):
--   Letter I (card_complete) additionally requires assessed_value (or
--   market_value) AND a parcel_zones/zoning_gold_standard_card link for
--   every row. Neither is obtainable from this GIS service -- the
--   St. Johns County GIS ArcGIS platform (probed live, full service list
--   enumerated) has zero CAMA/tax-roll/assessed-value layer; only parcel
--   geometry, zoning, and infrastructure layers. The county Property
--   Appraiser's own site (sjcpa.gov, live HTTP 200) and qPublic
--   (qpublic.schneidercorp.com, live HTTP 403) are Cloudflare/WAF-fronted
--   with no confirmed open per-parcel API in this sandbox -- scraping 28
--   individual parcel pages through that gate is new scraping infra, out of
--   this session's ~40-call budget and NOT attempted (no fabricated
--   assessed_value written for any row). Letter I therefore stays FAIL this
--   session; unaffected by this migration (card_complete=51 of 82 before
--   and after -- these 28 rows were never counted toward card_complete
--   either way since assessed_value was already the blocking field, not
--   parcel_id/address/lat-lng alone).
--   Letter J (deal_complete) requires a bid_decisions row with real
--   arv/max_bid/ml_score + 5 distress/CMA factor keys per case -- a
--   downstream deal-analysis pipeline output, not obtainable from a GIS
--   parcel lookup. Not attempted; would require real ARV/comp analysis,
--   fabricating it would violate NEVER-LIE.
--
-- Live effect (VERIFIED via public.pencil_dod_evaluate_county('st_johns'),
-- this session, live re-query after apply):
--   E: FAIL 64.6% (parcel_linked=53 of 82) -> PASS 98.8% (parcel_linked=81
--      of 82). st_johns moves from 7/10 to 8/10 canon letters.
--   Residual on E: CC24-6166 (1 row) remains genuinely blocked, already
--      documented in the 20260809 migration -- no parcel exists anywhere,
--      including the clerk's own live calendar.
--   I/J: unchanged (62.2% / 65.9%), as predicted above -- not claimed as
--      fixed.
--   A/B/C/D/F/G/H: unchanged, confirmed no regression (this migration only
--      writes parcel_id/property_address/latitude/longitude on rows that
--      were 100% NULL beforehand, guarded by "parcel_id IS NULL").
--
-- HARD GUARDRAILS RESPECTED:
--   - No fabricated assessed_value, bid_decisions, or zoning link for any
--     row -- I and J left honestly FAIL.
--   - Every parcel_id/address/lat-lng value traces to a live ArcGIS
--     FeatureServer response captured this session (26 via Parcel layer, 2
--     via Parcel_Condo layer), cross-checked once via exact address match
--     against the clerk-derived STRAP crosswalk before trusting the pattern
--     for the remaining 27.
--   - Idempotent: every UPDATE guarded by case_number + sale_type='tax_deed'
--     + parcel_id IS NULL, safe to re-run without side effects.
--   - No DELETE/TRUNCATE; no rows outside the 28 TD26-* st_johns tax_deed
--     cases touched.
--
-- SQL VERIFICATION (already run live this session; paste-in below is the
-- actual output, not a re-simulation):
--   SELECT public.pencil_dod_evaluate_county('st_johns');
--   -> {"A":{"pass":true,"metric":31},"B":{"pass":true,"metric":100.0},
--       "C":{"pass":true,"metric":96.3},"D":{"pass":true,"metric":100.0},
--       "E":{"pass":true,"metric":98.8,"detail":"parcel_linked=81"},
--       "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":97.1},
--       "H":{"pass":true,"metric":0.0},
--       "I":{"pass":false,"metric":62.2,"detail":"card_complete=51 of 82"},
--       "J":{"pass":false,"metric":65.9,"detail":"deal_complete=54 ..."},
--       "county":"st_johns","auctions_total":82}
--   Timestamp: 2026-08-11T08:15Z (approx, this session).

-- Individual scoped UPDATEs for the 28 TD26-* st_johns tax_deed rows.
-- Idempotent: guarded by parcel_id IS NULL so safe to re-run.
UPDATE public.multi_county_auctions
SET parcel_id = '2436300000',
    property_address = '641 SEGOVIA RD',
    latitude = 29.831399,
    longitude = -81.316217,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0024'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0263310300',
    property_address = '372 ALVAR CIR',
    latitude = 30.069018,
    longitude = -81.512455,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0031'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0525250623',
    property_address = '600 IRONWOOD DR',
    latitude = 30.22513,
    longitude = -81.389974,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0032'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0614310170',
    property_address = '553 ROBLES LN',
    latitude = 30.220494,
    longitude = -81.383673,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0033'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0702911960',
    property_address = '66 CAPE SAN BLAS WAY',
    latitude = 30.086779,
    longitude = -81.412882,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0034'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0819200170',
    property_address = '4616 SARTILLO RD',
    latitude = 29.943823,
    longitude = -81.343515,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0035'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '1940900000',
    property_address = '900 N PONCE DE LEON BLVD',
    latitude = 29.899855,
    longitude = -81.319688,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0038'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '1289300000',
    property_address = '181 S NASSAU ST',
    latitude = 29.888743,
    longitude = -81.339202,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0041'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '1629313130',
    property_address = '2252 COMMODORES CLUB BLVD',
    latitude = 29.852893,
    longitude = -81.282056,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0043'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '2368103679',
    property_address = '603 SAN JOSE RD',
    latitude = 29.83957,
    longitude = -81.31519,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0046'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0265733780',
    property_address = '518 COASTLINE WAY',
    latitude = 30.022674,
    longitude = -81.529884,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0051'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0506631220',
    property_address = '10740 W DEEP CREEK BLVD',
    latitude = 29.623915,
    longitude = -81.457879,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0053'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '2040600000',
    property_address = '58 CARRERA ST',
    latitude = 29.894548,
    longitude = -81.319809,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0059'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '1368051000',
    property_address = '3313 KINGS RD S',
    latitude = 29.829482,
    longitude = -81.338311,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0061'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '1828910270',
    property_address = '6336 GOMEZ RD',
    latitude = 29.780604,
    longitude = -81.263348,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0062'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0468100000',
    property_address = '214 W HOLTZ ST',
    latitude = 29.722618,
    longitude = -81.512031,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0063'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '1484900000',
    property_address = '43 FERROL RD',
    latitude = 29.915428,
    longitude = -81.291946,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0064'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0098500010',
    property_address = '2690 SENECA DR',
    latitude = 30.062686,
    longitude = -81.542702,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0066'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0359300020',
    property_address = '300 DON MANUEL RD',
    latitude = 29.770215,
    longitude = -81.456648,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0071'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0331800000',
    property_address = '6055 WINIFRED MASTERS RD',
    latitude = 29.77326,
    longitude = -81.47582,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0073'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0165200090',
    property_address = '6890 COUNTY ROAD 208',
    latitude = 29.92037,
    longitude = -81.542106,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0074'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0306920010',
    property_address = '5361 COUNTY ROAD 208',
    latitude = 29.905329,
    longitude = -81.501536,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0075'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0338600000',
    property_address = '6090 ARMSTRONG RD',
    latitude = 29.765941,
    longitude = -81.451546,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0076'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '1829430450',
    property_address = '6300 A1A S',
    latitude = 29.776883,
    longitude = -81.256008,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0078'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0621812220',
    property_address = '174 OCEAN POND CT',
    latitude = 30.208451,
    longitude = -81.374061,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0079'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0248700170',
    property_address = '354 VAN GOGH CIR',
    latitude = 30.075287,
    longitude = -81.446559,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0081'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0349700000',
    property_address = '5020 RAILROAD AVE',
    latitude = 29.761734,
    longitude = -81.448791,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0082'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '0123800010',
    property_address = 'STATE ROAD 13 N',
    latitude = 29.98346,
    longitude = -81.572298,
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'TD26-0083'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

-- SQL VERIFICATION (run after applying, this was run live this session):
-- SELECT case_number, parcel_id, property_address, latitude, longitude
--   FROM public.multi_county_auctions
--   WHERE lower(county)='st_johns' AND case_number LIKE 'TD26-%'
--   ORDER BY case_number;
-- SELECT public.pencil_dod_evaluate_county('st_johns');
