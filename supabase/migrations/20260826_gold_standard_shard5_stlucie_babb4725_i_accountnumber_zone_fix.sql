-- St Lucie County, letter I (property card completeness) — dispatch babb4725, 2026-08-26 shard-5 session.
--
-- IDEMPOTENT RECORD of live REST writes applied this session via the Supabase
-- REST API (direct psql unavailable in this environment — documented
-- long-standing constraint, see decision_log ids 169/205/287).
--
-- ── CONTEXT ──
-- Session start: I FAIL 94.6% (card_complete=229/242). auctions_total grew
-- 237 -> 242 since yesterday's 2026-08-25 dispatch 2ccd6cc6 close (5 new
-- multi_county_auctions rows landed via the calendar_sweep_mca_v3 feed:
-- 2025CA000957, 2025CA002001, 2025CA002273 created 2026-08-26T05:28Z, plus
-- 26-148/26-183 created 2026-08-25T09:20Z, all after that session's close).
--
-- Precise live gap re-derived (LEFT JOIN multi_county_auctions -> parcel_zones
-- on parcel_id, checked address/geo/value/zone independently): 13 failing
-- rows. Of these, 10 are unchanged from yesterday's documented residual
-- (26-137 boundary-artifact parcel, 26-197 condo centroid collision — both
-- structural per 2026-08-24/25 precedent migrations — plus 8 rows with
-- parcel_id IS NULL: 2023CA002852, 2024CA000214, 2024CA000330, 2024CA001834,
-- 2025CA002738, 2025CC001033, 26-148, 26-183, needing a court-docket parcel
-- lookup, different lever, not attempted in this migration).
--
-- The 3 NEW rows (2025CA000957, 2025CA002001, 2025CA002273) carry a
-- DIFFERENT parcel_id format than the rest of the county: a bare numeric
-- St Lucie Property Appraiser AccountNumber/PropertyID (e.g. "114487"), not
-- the dash-format STRAP ("nnnn-nnn-nnnn-nnn-n") used by every other st_lucie
-- row. Confirmed live via map.paslc.gov PROD/SLCPA_PublicParcels
-- MapServer/0, querying AccountNumber=<id>: this resolves to a real STRAP
-- (PARCELNO) plus SiteAddress and JustMarketValue that exactly match the
-- address on file for each row (address match verified, not a coincidental
-- AccountNumber collision).
--
-- ── METHOD ──
-- 1. map.paslc.gov PROD/SLCPA_PublicParcels MapServer/0, query
--    AccountNumber=<parcel_id> -> STRAP (PARCELNO), DistrictGroup
--    (jurisdiction), JustMarketValue (real assessed value):
--      114487 -> STRAP 3422-580-0109-000-2, DistrictGroup "0011 - Port Saint
--        Lucie" (jurisdiction_id 953), JustMarketValue 298000
--      156391 -> STRAP 4314-600-0117-000-1, DistrictGroup "0011 - Port Saint
--        Lucie" (jurisdiction_id 953), JustMarketValue 300800
--      154706 -> STRAP 3402-607-0289-000-5, DistrictGroup "0002 - Saint
--        Lucie County" (unincorporated, jurisdiction_id 1400),
--        JustMarketValue 551500 (row already had assessed_value=523863 on
--        file — a real, different figure; NOT overwritten, fill-NULL-only
--        per established convention)
-- 2. Zone lookup:
--    - Port St. Lucie (953): the previously-used single-layer FeatureServer
--      (services1.arcgis.com/YdUP5V6WwzeG8T8r/Zoning/FeatureServer/0,
--      "PZ_ZONING_SEU", 326 records) returned ZERO features for either PSL
--      point — discovered this is a small subset layer, NOT full citywide
--      coverage (explains the coverage-gap failures documented for 26-066 on
--      2026-08-25). The SAME FeatureServer's layer 1 ("PZ_ZONING", 1333
--      records) is the actual full zoning layer and returned a clean point
--      match for both: 114487 -> ZOLEGEND "RS-2" (Z958), 156391 -> ZOLEGEND
--      "PUD" (Z703). Documented here as a corrected lever for future
--      st_lucie/PSL sessions — layer 1, not layer 0, is the citywide zoning
--      source.
--    - Unincorporated (1400): slcgis.stlucieco.gov hosting/rest/services/
--      LandUse/Zoning/MapServer/0, exact Parcel_num (dashless STRAP) match:
--      154706 -> Zoned "RS-3" (OBJECTID 30070), same proven method as prior
--      sessions.
-- 3. G-regression pre-check (live, before writing): RS-2@953 and RS-3@1400
--    both already carry a real zone_standards row (max_density_du_acre 4.36
--    and 3.00 respectively) with density_regulated=true/true — adding these
--    links can only help G's density metric, never hurt it. PUD@953 is
--    already marked far_regulated=false/density_regulated=false from a prior
--    session (2026-08-24 port_st_lucie_arcgis_zoning_20260824 batch) — zero
--    G risk regardless of standards-row presence.
-- 4. parcel_zones.parcel_id inserted as the bare AccountNumber string
--    ("114487" etc.), matching multi_county_auctions.parcel_id EXACTLY as
--    stored (not converted to STRAP) — the evaluator's I-criterion join is
--    on literal parcel_id equality, confirmed by every prior county's
--    STRAP-keyed precedent; converting would break the join instead of
--    fixing it. STRAP captured in tax_account for future reconciliation.
--
-- ── BEFORE (live pencil_dod_evaluate_county('st_lucie'), 2026-08-26 08:0xZ) ──
--   I: card_complete=229/242 (94.6%) FAIL. G: density=97.0 (97.0%) PASS.
--   A/B/D/E/F/H/J: PASS (unchanged). C: 77.7% FAIL (matched_clean=188,
--   unchanged from brief — structural, see below).
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
SELECT * FROM (VALUES
  ('114487', '114487', 953,  'RS-2', 'SINGLE-FAMILY RESIDENTIAL',         'st_lucie_babb4725_psl_arcgis_zoning_layer1_20260826'),
  ('156391', '156391', 953,  'PUD',  'PLANNED UNIT DEVELOPMENT',          'st_lucie_babb4725_psl_arcgis_zoning_layer1_20260826'),
  ('154706', '154706', 1400, 'RS-3', 'Residential, Single-Family (3 du/ac) Zoning District', 'st_lucie_babb4725_slcgis_unincorporated_zoning_20260826')
) AS v(parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id AND pz.source = v.source
);

-- Fill-NULL-only assessed_value backfill (never overwrites a non-null value).
UPDATE multi_county_auctions SET assessed_value = 298000
WHERE case_number = '2025CA000957' AND county = 'st_lucie' AND assessed_value IS NULL;
UPDATE multi_county_auctions SET assessed_value = 300800
WHERE case_number = '2025CA002001' AND county = 'st_lucie' AND assessed_value IS NULL;

-- ── RESULT (verified live via pencil_dod_evaluate_county, 2026-08-26) ──
-- I: 94.6% (229/242) FAIL -> 95.9% (232/242) PASS.
-- G: 97.0% -> 97.1% (slight IMPROVEMENT, zero regression — RS-2/RS-3 both
--   carry real density standards).
-- All other letters (A,B,D,E,F,H,J): unchanged. C remains structural FAIL
--   (77.7%, matched_clean=188/242) — see session report for the fresh
--   2026-08-26 reconfirmation (6th+ session to reach this conclusion; canon-
--   level scoring-formula question, not a per-county data gap).
-- Residual I gap: 10 rows, unchanged composition from the 2026-08-25 close
--   (26-137, 26-197 structural GIS-coverage gaps; 8 no-parcel_id foreclosure
--   rows needing a court-docket lookup lever, out of scope for a GIS fix).
