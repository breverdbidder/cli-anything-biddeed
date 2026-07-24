-- Gold Standard shard-1, seminole, 2nd firing (dispatch ecb6f64b-26ab-4147-86a9-8b5baedd69cc).
--
-- CONTEXT: the 2026-07-18 session raised seminole C/D to 105/105 matched_clean
-- and I to 102/105 card_complete via a live PATCH-only fix. That fix's DATA was
-- real and survived, but its commit/migration claim was fabricated (invalid
-- commit SHA not on origin/main, migration file never existed in the repo).
-- auctions_total has since grown 105->111 (6 new rows arrived, same
-- AJAX-coverage-gap failure shape as before -- not a reversion). This migration
-- is the honest persistence record this session's live data fixes, closing the
-- gap flagged by the audit refuter.
--
-- WHAT THIS SESSION ACTUALLY DID (all steps executed live via REST/Management
-- API BEFORE this file was written; see accompanying session report for full
-- curl/query transcripts):
--
-- 1. C/D: re-baselined live via pencil_dod_evaluate_county('seminole') and a
--    direct parity_status/parity_source GROUP BY query. Found exactly 6 rows
--    with parity_status IS NULL (case_number 2023CA003414, 2025CA002000,
--    2024CC004907, 2023CC005751, 2025CA000344, 20260057/2024-003818),
--    auction_date range 2026-07-23 to 2026-09-10, matching the 105->111 growth
--    exactly. Ran scripts/shard1_seminole_run_ecb6f64b_cd_i_fix.py, which
--    reuses the proven AJAX RealAuction/RealTaxDeed harvester
--    (scripts/shard2_run2450_ajax_realforeclose_harvest.py) to pull the live
--    seminole.realforeclose.com / seminole.realtaxdeed.com calendar for each
--    (sale_type, auction_date) pair, exact-matched all 6 case numbers, and
--    PATCHed parity_status='matched_clean',
--    parity_source='tier1:shard1_ecb6f64b_seminole_ajax_harvest:<sale_type>:<date>'.
--    Result: matched_clean/matched_any both 111 of 111 (100.0%), C and D now
--    PASS. Re-queried the exact 6 rows immediately after to confirm the PATCH
--    persisted (not just a 2xx response) -- confirmed live.
--
-- 2. I: re-baselined the card_complete gap (100 of 111, 11 failing rows).
--    3 of the 11 are the SAME genuinely-blocked placeholder rows flagged by
--    the 2026-07-18 audit (2025CA000629 SYN- placeholder parcel_id,
--    2025CA002115 parcel_id literal "ALCOHOLIC LICENSE", 2025CA000060
--    parcel_id literal "MULTIPLE PARCELS") -- confirmed unchanged, left alone
--    per the campaign's residual-not-a-bug rule.
--    2 of the 11 (2024CA001701, 2024CA002404) were NOT new rows -- their
--    multi_county_auctions.parcel_id had regressed to the literal placeholder
--    text "Property Appraiser" even though the 2026-07-11 firing had already
--    discovered their real parcel_id and inserted real parcel_zones rows
--    (22-21-30-502-0N00-0030 -> PD, jurisdiction 636; 16-21-29-501-0000-1760
--    -> IL, jurisdiction 944) under those real parcel_ids. This was a
--    join-key mismatch, not missing data: the auction row's own parcel_id
--    column never got backfilled with the real value in that prior session.
--    Fixed via a straight UPDATE of multi_county_auctions.parcel_id to the
--    real, already-verified value (addresses cross-checked byte-for-byte
--    against the parcel_zones source citation: 250 RAINTREE DR / 1007
--    SUNSHINE LN, both exact matches).
--    The remaining 6 of 11 are the same 6 new C/D rows above -- all were
--    missing latitude/longitude (required by the I gate) and had no
--    parcel_zones row (zone_code join). Fetched real centroid lat/lon for
--    all 6 parcels from the FL DOR Statewide Cadastral FeatureServer
--    (services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0,
--    CO_NO=69 confirmed = Seminole for all 6, PARCEL_ID exact match,
--    returnCentroid=true&outSR=4326 for WGS84 lat/lon) and real zone_code +
--    jurisdiction from Seminole County's own InformationKiosk GIS layer
--    (utility.arcgis.com/.../InformationKiosk/MapServer/1, ParcelNumber exact
--    match, CityName + TaxDistrict + Zoning fields):
--      21-20-30-507-0000-0240  Lake Mary (jinvolved 928)        TaxDistrict M1  Zoning R-1AA
--      02-21-30-5JF-0A00-0210  Winter Springs (jurisdiction 921) TaxDistrict W1  Zoning PUD
--      33-19-31-517-0000-3560  Unincorporated (jurisdiction 636) TaxDistrict 01  Zoning PD (Cameron Heights, Ord 2013-014)
--      21-21-32-506-0000-0110  Unincorporated (jurisdiction 636) TaxDistrict 01  Zoning PD (Seminole Oaks, Ord 2013-014)
--      23-21-31-512-0000-0700  Oviedo (jurisdiction 862)         TaxDistrict V1  Zoning PUD
--      23-21-29-516-0000-048K  Altamonte Springs (jurisdiction 944) TaxDistrict A1  Zoning R-4
--    CityName matched the postal address for all 6 (no divergence this round,
--    unlike the 2026-07-18 firing where 3/6 diverged). Zone codes R-1AA, PD,
--    PUD already exist in zoning_districts for their respective jurisdictions
--    (verified before insert, no new district fabricated) and already carry
--    explicit v_zoning_district_applicability rows marking far/pk1000 (and
--    for 3 of 4, density too) as NOT applicable for PD/PUD-style districts --
--    so adding these 5 parcel_zones rows had zero negative effect on G.
--
--    R-4 for Altamonte Springs (jurisdiction 944) does NOT exist in
--    zoning_districts. It IS a real, GIS-confirmed code (spot-checked: dozens
--    of other Altamonte Springs parcels share it in the live GIS layer) --
--    but inserting a parcel_zones row for it with no matching zoning_districts
--    row caused a live, VERIFIED regression: G (density/far/pk1000) dropped
--    from PASS 97.1 to FAIL 83.3 because v_zoning_district_applicability has
--    nothing to key off for a district-less zone_code, so
--    v_zoning_gold_standard_kpi_v3's COALESCE(a.*, true) default marked this
--    parcel "applicable" for all 3 metrics with zero standards ever able to
--    fill them in -- a real side effect of this session's own write, not a
--    pre-existing issue. Rather than guess this jurisdiction's ordinance
--    category/far_regulated/density_regulated values to force a fabricated
--    zoning_districts row (out of scope: would require the actual Altamonte
--    Springs Land Development Code text, not just a GIS zone-code label),
--    this parcel_zones row was DELETED again after the regression was caught
--    live via a fresh pencil_dod_evaluate_county call. Case 20260057/2024-
--    003818 (parcel 23-21-29-516-0000-048K) therefore remains a genuine,
--    honestly-reported I residual (lat/lon backfilled, zone_code NOT
--    inserted) rather than a half-fix that silently broke G to help I.
--
--    Applied via REST PATCH (multi_county_auctions.latitude/longitude for 6
--    rows, 2 parcel_id corrections) and REST POST (5 new parcel_zones rows,
--    not 6 -- the 6th was inserted then deleted after the G regression was
--    caught, per above). All re-queried live immediately after write to
--    confirm persistence; pencil_dod_evaluate_county re-run after the delete
--    confirmed G restored to PASS 97.2 and I still PASS 96.4 (107 of 111).
--
-- This file is written and committed as the historical record per the
-- campaign's ship-gate rule, even though the actual data changes were applied
-- live via REST/Management API rather than via `supabase db push` (no schema
-- change was needed -- existing columns/tables only). The commit SHA for this
-- file is verified against origin/main in the session report before being
-- cited anywhere, closing the exact fabrication gap the 2026-07-18 audit
-- flagged.

-- Idempotent backfill: only touch multi_county_auctions.parcel_id where it is
-- still the literal placeholder text (guards against re-running this file
-- clobbering a value fixed by any later session).
UPDATE public.multi_county_auctions
SET parcel_id = '22-21-30-502-0N00-0030'
WHERE lower(county) = 'seminole'
  AND case_number = '2024CA001701'
  AND parcel_id = 'Property Appraiser';

UPDATE public.multi_county_auctions
SET parcel_id = '16-21-29-501-0000-1760'
WHERE lower(county) = 'seminole'
  AND case_number = '2024CA002404'
  AND parcel_id = 'Property Appraiser';

-- Lat/lon backfill for the 6 new C/D rows, guarded to only fill NULLs.
UPDATE public.multi_county_auctions
SET latitude = 28.739804417749173, longitude = -81.31644333573928
WHERE lower(county) = 'seminole' AND case_number = '2023CA003414'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 28.696204830486277, longitude = -81.29599035011856
WHERE lower(county) = 'seminole' AND case_number = '2025CA002000'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 28.792529102981756, longitude = -81.2224123599196
WHERE lower(county) = 'seminole' AND case_number = '2024CC004907'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 28.648602265032604, longitude = -81.12506191555879
WHERE lower(county) = 'seminole' AND case_number = '2023CC005751'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 28.652026194144685, longitude = -81.18474564246728
WHERE lower(county) = 'seminole' AND case_number = '2025CA000344'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 28.6478065191255, longitude = -81.38291837918219
WHERE lower(county) = 'seminole' AND case_number = '20260057/2024-003818'
  AND latitude IS NULL AND longitude IS NULL;

-- Real zone codes for 5 of the 6 parcels, sourced from Seminole County
-- InformationKiosk GIS (ParcelNumber exact match, Zoning field verbatim).
-- Guarded with a NOT EXISTS check for idempotency. The 6th parcel
-- (23-21-29-516-0000-048K, Altamonte Springs, zone_code R-4) is deliberately
-- NOT inserted here -- see comment block above: inserting it caused a live,
-- verified G regression (no matching zoning_districts row for jurisdiction
-- 944 code R-4 to key applicability off), and this session chose to leave it
-- as an honest I residual rather than fabricate a zoning_districts row to
-- paper over the gap.
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT * FROM (VALUES
  ('21-20-30-507-0000-0240', 928, 'R-1AA', 'Single-Family Dwelling District (R-1AA)',
   'seminole_county_gis_information_kiosk (utility.arcgis.com InformationKiosk/MapServer/1, ParcelNumber exact match, CityName=Lake Mary TaxDistrict=M1, shard1_ecb6f64b_2nd_firing 2026-07-24)'),
  ('02-21-30-5JF-0A00-0210', 921, 'PUD', 'Planned Unit Development District',
   'seminole_county_gis_information_kiosk (utility.arcgis.com InformationKiosk/MapServer/1, ParcelNumber exact match, CityName=Winter Springs TaxDistrict=W1, shard1_ecb6f64b_2nd_firing 2026-07-24)'),
  ('33-19-31-517-0000-3560', 636, 'PD', 'Cameron Heights (Ordinance 2013-014)',
   'seminole_county_gis_information_kiosk (utility.arcgis.com InformationKiosk/MapServer/1, ParcelNumber exact match, CityName=County TaxDistrict=01, shard1_ecb6f64b_2nd_firing 2026-07-24)'),
  ('21-21-32-506-0000-0110', 636, 'PD', 'Seminole Oaks (Ordinance 2013-014)',
   'seminole_county_gis_information_kiosk (utility.arcgis.com InformationKiosk/MapServer/1, ParcelNumber exact match, CityName=County TaxDistrict=01, shard1_ecb6f64b_2nd_firing 2026-07-24)'),
  ('23-21-31-512-0000-0700', 862, 'PUD', 'Planned Unit Development',
   'seminole_county_gis_information_kiosk (utility.arcgis.com InformationKiosk/MapServer/1, ParcelNumber exact match, CityName=Oviedo TaxDistrict=V1, shard1_ecb6f64b_2nd_firing 2026-07-24)')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);
