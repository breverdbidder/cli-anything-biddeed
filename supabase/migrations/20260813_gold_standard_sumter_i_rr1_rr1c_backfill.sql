-- Gold Standard sumter I fix (dispatch 10bc7bc6-eefb-4073-8d69-18a6a83788a0)
-- Session: 2026-08-13
--
-- CONTEXT (VERIFIED live via pencil_dod_evaluate_county('sumter') before this
-- session): I FAIL 70.8% (card_complete=17 of 24). Denominator grew from the
-- prior 21-row baseline (dispatch b57474e3, 2026-08-12: I FAIL 81.0%,
-- 17 of 21) to 24 rows -- one new auction row (case 2025-CC-000033, sumter
-- foreclosure, scraped 2026-08-13T10:10:14Z) landed with ONLY case_number
-- populated. The 17/21 -> 17/24 numerator held flat while denominator grew,
-- dropping the pass rate from 81.0% to 70.8%.
--
-- ROOT CAUSE (live query against multi_county_auctions + v_auction_property_card,
-- 2026-08-13): 7 incomplete cards, three distinct gaps:
--   1. 4 rows missing property_address only (parcel_id/geo/value/zone all
--      present): J16C020 (case 1078), M06C003 (case 1159), C27-268 (case 104),
--      G06H033 (case 776). CONFIRMED genuine dead-end, re-verified this
--      session against fl_parcels (phy_addr1 IS NULL for all 4) -- same class
--      of gap already documented twice (D29A024 2026-07-25, and this exact
--      set of 4 in the shard3 b57474e3 2026-08-12 session). NOT re-touched.
--   2. 2 rows missing zoning_code only (address/geo/value all present):
--      G14A030 (case 2025-CA-000405, THE VILLAGES) and F31E015 (case
--      2025-CA-000488, LAKE PANASOFFKEE). FIXED this migration.
--   3. 1 row missing everything (case 2025-CC-000033, sumter foreclosure,
--      PETER RESNICK vs JOHNATHAN L. GIBSON, judgment $57,834.41): no
--      parcel_id at all on the raw scrape. FIXED this migration + companion
--      Python enrichment (see scripts/gold_standard_sumter_i_2025cc000033_enrich.py).
--
-- DATA SOURCES (all live, real, this session):
--   1. https://www.sumterclerk.com/courts/foreclosures/foreclosure-sales/ --
--      live HTML: case 2025-CC-000033, plaintiff "PETER RESNICK", defendant
--      "JOHNATHAN L. GIBSON", judgment $57,834.41, sale rescheduled from
--      07/30/2026 (cancelled) to 09/03/2026 (scheduled). Page does NOT list
--      address/parcel for this case (confirmed live, unlike most other rows
--      on the same page).
--   2. fl_parcels (co_no=70, same Supabase FL DOR extract used by the prior
--      2026-08-12 session) -- searched by owner-name pattern
--      'GIBSON JOHNATHAN L' -> exactly ONE match: parcel N17F007, owner
--      "GIBSON JOHNATHAN L & LILES BRI", phy_addr1 "6300 SW 14TH DR",
--      phy_city "BUSHNELL", phy_zipcd 33513, jv $41,210, dor_uc 002 (mobile
--      home), municipality "BUSHNELL". No ambiguity -- exact first+last name
--      match against the clerk-scraped defendant name.
--   3. https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/
--      Sumter_Geocoder/GeocodeServer -- geocoded "6300 SW 14TH DR, BUSHNELL,
--      FL 33513" (fl_parcels had no centroid_lat/lng) -> lat 28.664268,
--      lng -82.128574, match score 93.79/100 (AddressPoint type).
--   4. https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/
--      FLU_Zoning/FeatureServer/11 (county unincorporated layer, field
--      Parcel/Zone_Type) -- SAME source used by the 2026-07-11 shard9 and
--      2026-08-12 shard3-b57474e3 sumter migrations. Queried live by exact
--      Parcel match for all 3 parcels needing zoning:
--        N17F007  -> Zone_Type = RR1
--        F31E015  -> Zone_Type = RR1C
--        G14A030  -> Zone_Type = RPUD  (code already registered, jurisdiction
--                    1325, from the 2026-08-12 session -- just needs
--                    parcel_zones linkage, no new zoning_districts row)
--
-- ZONE CODES FOUND (2 genuinely new to jurisdiction 1325 -- RR1, RR1C; RPUD
-- already exists from the prior session):
--   Sumter County LDC Chapter 13, Article IV, Table 13-420 (District
--   Abbreviations): RR1 = "High Density Rural Residential with Optional
--   Housing", RR1C = "High Density Rural Residential with Conventional
--   Housing" (fetched live from sumterclerk.granicus.com/MetaViewer.php
--   ?view_id=2&clip_id=638&meta_id=118903, the SAME LDC PDF cited by the
--   2026-08-12 shard3-b57474e3 migration for R4C/R6M/A10C).
--
-- DIMENSIONAL STANDARDS (Table 13-423A: Residential zoning districts
-- dimensional standards, RR1/RR1C column, read directly off the fetched PDF):
--   Min. lot area: 1 acre (43,560 sq ft)
--   Min. lot width: 100 ft
--   Side and Rear setback: 15 ft
--   Building height (all uses by right): 35 ft
-- DENSITY (Table 13-414A: Development densities/intensities, Rural
-- Residential FLU category):
--   1 dwelling unit/acre -- Outside UDA or Inside UDA with NO central water
--     or sewer services (base/default absent contrary evidence -- these are
--     unincorporated rural Bushnell-area parcels, no indication of central
--     water/sewer service; conservative choice matching Table 13-414A's
--     "outside UDA" default row).
--   2 dwelling units/acre -- Inside UDA WITH central water and sewer
--     services (not used here -- no evidence these parcels have central
--     service).
-- Same methodology as the 2026-08-12 shard3-b57474e3 migration's R4C/R6M/A10C
-- density sourcing (min-lot-area / Table 13-414A cross-confirmation), applied
-- to the 2 new RR1/RR1C codes. This closes the exact G-regression risk that
-- migration documented (inserting zoning_districts with no zone_standards
-- density value flips v_zoning_district_applicability's density_applicable
-- flag to true with a null value, dropping G's density metric).
--
-- NOT WRITTEN / deliberately out of scope:
--   - property_address for J16C020/M06C003/C27-268/G06H033 -- re-confirmed
--     genuine dead-end this session (fl_parcels phy_addr1 IS NULL for all 4,
--     qpublic.schneidercorp.com 403 WAF), NOT re-touched. I settles at a real
--     residual, not fabricated.
--   - setbacks/height/FAR/parking beyond what's needed for G's density metric
--     (far_applicable/pk1000_applicable both correctly evaluate false for
--     residential-only categories per the existing category-based default).
-- ============================================================

SET statement_timeout = 0;

-- ── Step 1: zoning_districts — register the 2 genuinely new zone codes ────────
-- (RPUD already exists for jurisdiction 1325 from the 2026-08-12 session.)

INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
VALUES
    ('RR1', 'High Density Rural Residential with Optional Housing', 1325, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 11 (Zone_Type=RR1), queried live by exact Parcel match 2026-08-13. Rural Residential district per Sumter County LDC Chapter 13 Article IV (library.municode.com/fl/sumter_county via sumterclerk.granicus.com MetaViewer PDF).'),
    ('RR1C', 'High Density Rural Residential with Conventional Housing', 1325, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 11 (Zone_Type=RR1C), queried live by exact Parcel match 2026-08-13. Rural Residential district per Sumter County LDC Chapter 13 Article IV.')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ── Step 2: parcel_zones — link the 3 parcels to their real zone ──────────────

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
    ('N17F007', 'N17F007', 1325, 'RR1', 'High Density Rural Residential with Optional Housing',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=N17F007:2026-08-13'),
    ('F31E015', 'F31E015', 1325, 'RR1C', 'High Density Rural Residential with Conventional Housing',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=F31E015:2026-08-13'),
    ('G14A030', 'G14A030', 1325, 'RPUD', 'Residential Planned Unit Development',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=G14A030:2026-08-13')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET
    zone_code = EXCLUDED.zone_code,
    zone_name = EXCLUDED.zone_name,
    source    = EXCLUDED.source;

-- ── Step 3: zone_standards — real dimensional/density for RR1/RR1C ────────────
-- (G regression-avoidance, same methodology as the 2026-08-12 R4C/R6M/A10C fix)

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft,
    side_setback_ft, rear_setback_ft, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT id, 43560, 100, 35, 15, 15, 1.0,
       'https://sumterclerk.granicus.com/MetaViewer.php?view_id=2&clip_id=638&meta_id=118903',
       'Sumter County Code of Ordinances Sec. 13-423, Table 13-423A: Residential zoning districts dimensional standards -- RR1, RR1C column: Min. lot area = 1 ac (43,560 sq ft), Min. lot width = 100 ft, Side and Rear setback = 15 ft, Building height = 35 ft. Density per Sec. 13-414, Table 13-414A: Rural Residential FLU category, base density = 1 dwelling unit/acre outside UDA or inside UDA with no central water/sewer services.',
       0.9
FROM zoning_districts WHERE jurisdiction_id = 1325 AND code = 'RR1'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft,
    side_setback_ft, rear_setback_ft, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT id, 43560, 100, 35, 15, 15, 1.0,
       'https://sumterclerk.granicus.com/MetaViewer.php?view_id=2&clip_id=638&meta_id=118903',
       'Sumter County Code of Ordinances Sec. 13-423, Table 13-423A: Residential zoning districts dimensional standards -- RR1, RR1C column: Min. lot area = 1 ac (43,560 sq ft), Min. lot width = 100 ft, Side and Rear setback = 15 ft, Building height = 35 ft. Density per Sec. 13-414, Table 13-414A: Rural Residential FLU category, base density = 1 dwelling unit/acre outside UDA or inside UDA with no central water/sewer services.',
       0.9
FROM zoning_districts WHERE jurisdiction_id = 1325 AND code = 'RR1C'
ON CONFLICT DO NOTHING;

-- ── Verification ────────────────────────────────────────────────────────────

SELECT 'parcel_zones sumter I-fix' AS check_name, pz.parcel_id, pz.jurisdiction_id, pz.zone_code, pz.source
FROM parcel_zones pz
WHERE pz.parcel_id IN ('N17F007','F31E015','G14A030')
ORDER BY pz.parcel_id;
