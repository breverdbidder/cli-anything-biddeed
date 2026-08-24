-- Gold Standard wakulla (dispatch this session, county-owner task): E/I/J new-row backfill.
--
-- CONTEXT: wakulla previously reached documented 10/10 (migration
-- 20260725g_gold_standard_shard7_wakulla_ei_sherrell_resolution_10of10.sql, denominator=30)
-- via FL GIO Statewide Cadastral (services9.arcgis.com/Gh9awoU677aKree0/.../
-- Florida_Statewide_Cadastral/FeatureServer/0) + Wakulla's own Parcels/Zoning_Map ArcGIS
-- FeatureServers. The denominator has since grown to 44 (new auctions scraped since 07-25).
-- This migration re-applies the SAME proven method to the NEW gap rows, not a new method.
--
-- LIVE BASELINE this session (pencil_dod_evaluate_county('wakulla')):
--   C 84.1% (37/44) FAIL, D 100.0% (44/44) PASS, E 81.8% (36/44) FAIL,
--   I 72.7% (32/44) FAIL, J 72.7% (32/44) FAIL.
-- (C's 7-row gap is the 7 CLERK_SSOT_CANCELLED rows -- a genuinely-cancelled-sale class the
-- live evaluator [migration 20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql]
-- correctly excludes from matched_clean while including in matched_any. Not a bug, not
-- addressed here -- those are correctly-cancelled auctions, counting them as "clean matched"
-- would be dishonest.)
--
-- E-GAP INVESTIGATION (8 rows with parcel_id IS NULL, all blank shells -- no owner/address/
-- anything -- confirmed live via direct PostgREST read this session):
--   2026-TXD-097 -- PERMANENT gap, already documented in the 10/10 migration (redeemed tax
--     certificate, no deed ever issued, no assessed/market value on either prior migration).
--     Untouched here.
--   2026-TXD-117, -118, -120, -122 (parity_status='CLERK_SSOT_CANCELLED') -- re-checked live
--     this session against the current wakullaclerk.org tax_deed_sales.php table
--     (scripts/clerk_ssot/parsers/wakulla.py parse_tax_deed()): NONE of these 4 case numbers
--     appear on the live page anymore (current live listing is only 123/128/129/130/131/132).
--     Confirms genuinely cancelled/withdrawn sales with no property data ever populated before
--     removal -- a permanent gap of the same class as 097, not a data-collection failure.
--     Untouched here (BLANK > WRONG -- no source exists to backfill a cancelled sale's
--     property record).
--   25-CA-105 (parity_status='PARITY_OK', sale_type=foreclosure) -- re-checked live: this case
--     IS still active on wakullaclerk.org/courts/foreclosures.php ("To Be Sold", sale date
--     2026-08-27, Freedom Mortgage Corp. VS Ronald E. Reynolds Jr. ET AL, judgment
--     $404,253.57). Genuinely NOT cancelled, but no parcel/property data is available from any
--     channel reachable this session: (a) the clerk's foreclosures table carries no document
--     link/PDF for this row: (b) floridapublicnotices.com search and wakullaclerk.com/
--     landmarkweb are both JS-driven SPAs requiring interactive search-box fill+submit, and no
--     browser-automation tool was available in this session (the Sherrell precedent's working
--     channel); (c) FL DOR Statewide Cadastral OWN_NAME LIKE '%REYNOLDS%' for CO_NO=75 (Wakulla)
--     returned 0 rows -- the mortgagor's name does not appear in the current assessment-roll
--     owner field (common when the deed owner differs from the loan borrower, or the roll
--     hasn't been re-assessed since the original purchase). Logged honestly as a genuine
--     documentation-only gap this session, not fabricated. No write for this row.
--   2026-TXD-123, 2026-TXD-129 -- FIXED below. Both are live, active tax-deed sales (confirmed
--     "For Sale" on wakullaclerk.org/official_records/tax_deed_sales.php, sale date
--     2026-10-21). The clerk's site links each deed number to its own "NOTICE OF APPLICATION
--     FOR TAX DEED" PDF (root-relative URL under /Documents/Official Records/Tax Deed Sales/ --
--     the href in the table markup is page-relative and 404s; the working URL is
--     https://wakullaclerk.org/Documents/Official%20Records/Tax%20Deed%20Sales/<file>.pdf).
--     Each PDF states the Parcel # directly: 2026-TXD-123 = "33-2s-01e-189-04995-e02"
--     (Clarence Wilson/Lucy Johnson, Springwood Subd Phase 1 Lot 2 Block E); 2026-TXD-129 =
--     "00-00-075-141-10234-a10" (Billy A Godwin/Betty K Godwin Etal, The Pines Unit 1 Block A
--     Lot 10, "Homestead" per the site's own annotation).
--     Cross-verified against FL GIO Statewide Cadastral (CO_NO=75, PARCEL_ID = the same
--     parcel # dash-stripped and uppercased, per the exact crosswalk already established in
--     the Sherrell 10/10 migration): both parcels found, S_LEGAL fields match the PDF legal
--     descriptions exactly ("SPRINGWOOD SUBD. PHASE 1" / "THE PINES UNIT 1"), giving
--     JV/LND_VAL (assessed/market value proxy, this dataset has no separate market_value
--     field so JV is used for both per established wakulla convention) and PHY_ADDR1/
--     PHY_CITY/PHY_ZIPCD. Centroid geometry (WGS84) cross-checked against Wakulla's own
--     Parcels FeatureServer (services.arcgis.com/yghUoIoA2Cd2cWki/.../Wakulla_Parcels/
--     FeatureServer/0, PARCEL_ID field, dashed uppercase format) -- both sources agree to
--     6 decimal places on centroid lon/lat, confirming no crosswalk ambiguity.
--     Zoned via a point-in-polygon spatial query against Wakulla County's own zoning layer
--     (services9.arcgis.com/vAltLjtfYIJc7pDt/.../Zoning_Map/FeatureServer/30) using the true
--     parcel centroid: both parcels resolve to CUR_ZONING='RR1' (Rural Residential),
--     consistent with DOR_UC='002' (residential) on both.
--
-- I/J-GAP ADDITIONAL ROWS (4 rows that already HAD parcel_id -- correctly counted in E's
-- 36/44 -- but were missing property_address/lat-long/assessed_value/market_value, blocking
-- I's card-completeness and (via missing ARV input) J's bid_decisions generation):
-- 2026-TXD-128, -130, -131, -132, all parity_status='PARITY_OK', all live/active on the
-- current tax_deed_sales.php listing. Each parcel_id looked up directly against FL GIO
-- Statewide Cadastral (CO_NO=75, dash-stripped uppercase crosswalk) -- all 4 matched exactly
-- 1 feature each. 2026-TXD-130's DOR OWN_NAME ("FORBES BURTON MRS HEIRS OF") independently
-- cross-validates against the row's PRE-EXISTING owner_name value in multi_county_auctions
-- ("Heirs of Mrs Burton Forbes") -- same estate, same parcel, confirming this crosswalk did
-- not pick up a false match. Zoned via the same point-in-polygon method: TXD-128=RSU2
-- (Residential), TXD-130=AG (Agricultural), TXD-131=AG (Agricultural), TXD-132=R1
-- (Residential). RSU2 is a zone code not previously registered in zoning_districts for
-- jurisdiction 1402 (Unincorporated Wakulla) -- registered below as a structural placeholder
-- (VERIFIED zone_code from the county's own GIS layer; ZONE_TYPE='Residential' is the only
-- attribute this layer carries, no dimensional standards available from this source --
-- consistent with the existing R1/RMH1/RR1 rows in this jurisdiction, which carry the same
-- "VERIFIED zone_code ... dimensional standards NOT sourced" documentation pattern). AG and
-- R1 already exist in zoning_districts for this jurisdiction (no INSERT needed for those).
--
-- Idempotent: multi_county_auctions UPDATEs are keyed by case_number (single row each,
-- unconditional re-apply is safe/no-op on re-run since values are static real data).
-- parcel_zones INSERTs use NOT EXISTS guards. zoning_districts INSERT for RSU2 uses
-- ON CONFLICT DO NOTHING style guard via NOT EXISTS.

BEGIN;

-- 2026-TXD-123: Clarence Wilson/Lucy Johnson, Springwood Subd Phase 1 Lot 2 Block E
UPDATE public.multi_county_auctions
SET parcel_id = '33-2S-01E-189-04995-E02',
    property_address = '55 SUMMER LN, CRAWFORDVILLE, FL 32327',
    city = 'CRAWFORDVILLE',
    zip = '32327',
    latitude = 30.260840266983234,
    longitude = -84.24302179876973,
    assessed_value = 31666,
    market_value = 31666,
    legal_description = 'SPRINGWOOD SUBD. PHASE 1 Lot 2 Block E OR 105 P 131 OR 242 P 545 OR 285 P 379 OR 294 P 841 (DOR NAL S_LEGAL + full legal from clerk''s Notice of Application for Tax Deed 2026-TXD-123)',
    owner_name = 'Clarence Wilson/Lucy Johnson'
WHERE case_number = '2026-TXD-123' AND county = 'wakulla';

-- 2026-TXD-129: Billy A Godwin/Betty K Godwin Etal, The Pines Unit 1 Block A Lot 10 (Homestead)
UPDATE public.multi_county_auctions
SET parcel_id = '00-00-075-141-10234-A10',
    property_address = '169 BAY PINE DR, CRAWFORDVILLE, FL 32327',
    city = 'CRAWFORDVILLE',
    zip = '32327',
    latitude = 30.200774253327037,
    longitude = -84.37416157625904,
    assessed_value = 110662,
    market_value = 110662,
    legal_description = 'THE PINES UNIT 1 Block A Lot 10 OR 65 P 352 & OR 86 P 872 OR 130 P 373 & OR 131 P 113 OR 134 P 793 & OR 332 P 847 (DOR NAL S_LEGAL + full legal from clerk''s Notice of Application for Tax Deed 2026-TXD-129)',
    owner_name = 'Billy A Godwin/Betty K Godwin Etal'
WHERE case_number = '2026-TXD-129' AND county = 'wakulla';

-- 2026-TXD-128: parcel_id already present (00-00-056-430-09947-006); backfilling
-- address/geo/value from FL GIO Statewide Cadastral (CO_NO=75).
UPDATE public.multi_county_auctions
SET property_address = 'WAKULLA AARAN RD, CRAWFORDVILLE, FL 32327',
    city = 'CRAWFORDVILLE',
    zip = '32327',
    latitude = 30.204311521496322,
    longitude = -84.33639617055127,
    assessed_value = 50000,
    market_value = 50000,
    legal_description = 'LOT 6 MACY LEE ACRES (DOR NAL S_LEGAL)',
    owner_name = 'Cobb Leanne Roberts'
WHERE case_number = '2026-TXD-128' AND county = 'wakulla';

-- 2026-TXD-130: parcel_id already present (00-00-044-000-09819-000); owner_name
-- pre-existing value ("Heirs of Mrs Burton Forbes") independently cross-validated against
-- DOR OWN_NAME ("FORBES BURTON MRS HEIRS OF") -- not overwritten, left as-is.
UPDATE public.multi_county_auctions
SET property_address = '73 HENRY FORBES RD, CRAWFORDVILLE, FL 32327',
    city = 'CRAWFORDVILLE',
    zip = '32327',
    latitude = 30.15849631592454,
    longitude = -84.30752846514234,
    assessed_value = 114049,
    market_value = 114049,
    legal_description = 'LOT 44 HS P-6-M-11 (DOR NAL S_LEGAL)'
WHERE case_number = '2026-TXD-130' AND county = 'wakulla';

-- 2026-TXD-131: parcel_id already present (23-4S-02W-000-02013-000); backfilling
-- address/geo/value from FL GIO Statewide Cadastral (CO_NO=75).
UPDATE public.multi_county_auctions
SET property_address = '43 SHAWN WHALEY RD, CRAWFORDVILLE, FL 32327',
    city = 'CRAWFORDVILLE',
    zip = '32327',
    latitude = 30.127864426810678,
    longitude = -84.4118294386148,
    assessed_value = 242448,
    market_value = 242448,
    legal_description = '23-4S-2W P-1-M-50C (DOR NAL S_LEGAL)',
    owner_name = 'Johnson Steven H'
WHERE case_number = '2026-TXD-131' AND county = 'wakulla';

-- 2026-TXD-132: parcel_id already present (00-00-034-009-08568-000); backfilling
-- address/geo/value from FL GIO Statewide Cadastral (CO_NO=75).
UPDATE public.multi_county_auctions
SET property_address = 'BLACKFOOT RD, CRAWFORDVILLE, FL 32327',
    city = 'CRAWFORDVILLE',
    zip = '32327',
    latitude = 30.175045081321464,
    longitude = -84.30188543553506,
    assessed_value = 9250,
    market_value = 9250,
    legal_description = 'WAKULLA GARDENS UNIT 2 (DOR NAL S_LEGAL)',
    owner_name = 'Jones James R'
WHERE case_number = '2026-TXD-132' AND county = 'wakulla';

-- Register RSU2 zone code (jurisdiction 1402, Unincorporated Wakulla) -- not previously
-- present. Same documentation pattern as the existing R1/RMH1/RR1 rows in this jurisdiction:
-- VERIFIED zone_code from Wakulla County's own ZoningWakulla GIS layer (CUR_ZONING field),
-- dimensional standards not sourced from this layer (it carries no ordinance-level detail).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category)
SELECT 1402, 'RSU2', 'RSU2 Residential (Suburban) -- VERIFIED zone_code from Wakulla County GIS ZoningWakulla layer (CUR_ZONING field), dimensional standards NOT sourced this session (same documentation-gap class as this jurisdiction''s existing R1/RMH1/RR1 rows)', 'Residential'
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 1402 AND code = 'RSU2'
);

-- parcel_zones linkage for the 6 newly address/geo/value-complete parcels.
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '33-2S-01E-189-04995-E02', 1402, 'RR1', 'Rural Residential',
       'ZoningWakulla_ArcGIS_gold_standard_20260824_spatial_centroid_verified'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '33-2S-01E-189-04995-E02' AND jurisdiction_id = 1402);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '00-00-075-141-10234-A10', 1402, 'RR1', 'Rural Residential',
       'ZoningWakulla_ArcGIS_gold_standard_20260824_spatial_centroid_verified'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '00-00-075-141-10234-A10' AND jurisdiction_id = 1402);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '00-00-056-430-09947-006', 1402, 'RSU2', 'RSU2 Residential (Suburban)',
       'ZoningWakulla_ArcGIS_gold_standard_20260824_spatial_centroid_verified'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '00-00-056-430-09947-006' AND jurisdiction_id = 1402);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '00-00-044-000-09819-000', 1402, 'AG', 'AG Agricultural District',
       'ZoningWakulla_ArcGIS_gold_standard_20260824_spatial_centroid_verified'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '00-00-044-000-09819-000' AND jurisdiction_id = 1402);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '23-4S-02W-000-02013-000', 1402, 'AG', 'AG Agricultural District',
       'ZoningWakulla_ArcGIS_gold_standard_20260824_spatial_centroid_verified'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '23-4S-02W-000-02013-000' AND jurisdiction_id = 1402);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '00-00-034-009-08568-000', 1402, 'R1', 'Single Family Residential (Rural/Urban)',
       'ZoningWakulla_ArcGIS_gold_standard_20260824_spatial_centroid_verified'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '00-00-034-009-08568-000' AND jurisdiction_id = 1402);

COMMIT;

-- J (deal_complete): after this migration's writes landed live, this session re-ran the
-- existing, audit-survived generator scripts/shard7_wakulla_j_generator_real.py (not
-- reimplemented, per HARNESS rule "ALWAYS fork from existing harness"). It selects ALL 44
-- wakulla auctions live and only skips rows where real_arv() (GREATEST(assessed_value,
-- market_value)) is null. Live run output this session:
--   auctions=44 existing_bid_decisions=32 skipped_no_real_value=6 rows_to_write=38
--   inserted=6 updated=32
-- skipped_no_real_value=6 is exactly {097, 117, 118, 120, 122, 25-CA-105} -- the same 6 rows
-- documented above as permanent/session-blocked gaps, confirmed by direct query
-- post-run (SELECT case_number FROM multi_county_auctions WHERE county='wakulla' AND
-- case_number NOT IN (SELECT case_number FROM bid_decisions WHERE county_slug='wakulla')).
-- The Shapira v14 XGBoost model (shapira_models.model_version='v14.0', storage bucket
-- shapira-models) was staged fresh to /tmp/shapira this session to run this script; it is
-- not vendored into this repo.
--
-- LIVE VERIFICATION (pencil_dod_evaluate_county('wakulla'), re-queried fresh after all
-- writes, hand-counted independently against raw table data with zero discrepancy):
--   E: 81.8% (36/44) FAIL -> 86.4% (38/44) FAIL  (+2 rows: 2026-TXD-123, 2026-TXD-129)
--   I: 72.7% (32/44) FAIL -> 86.4% (38/44) FAIL  (+6 rows: the 2 above + the 4
--     already-parcel-linked rows -128/-130/-131/-132 that gained address/geo/value/zone)
--   J: 72.7% (32/44) FAIL -> 86.4% (38/44) FAIL  (+6 rows, same set as I -- ARV inputs
--     landing unblocked the J generator for exactly those 6 case numbers)
--   C: 84.1% (37/44) FAIL, unchanged (out of scope -- its 7-row gap is the correctly-excluded
--     CLERK_SSOT_CANCELLED class per the live evaluator's own vocabulary, not a bug)
--   D/A/B/F/H: unchanged, still PASS (100.0/PASS/100.0/100.0/0.0h -- zero regression)
--   G: 100.0 -> 97.1, still PASS (>=95 threshold) -- honest side-effect of the 2 new AG
--     parcels changing the density-applicable pool denominator; not chased further, G was
--     already passing and is out of this task's scope.
--   Ceiling for E/I/J is 38/44=86.4% until 2026-TXD-097 (redeemed, permanent) and the 4
--   CLERK_SSOT_CANCELLED rows (confirmed removed from the live clerk site, permanent) and
--   25-CA-105 (active but no reachable parcel source this session, documented blocked) are
--   resolved by a future session with browser-automation tooling for 25-CA-105, or remain
--   permanent gaps for the other 5.
