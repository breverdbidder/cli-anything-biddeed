-- Gold Standard shard-3 (dispatch b57474e3-1a2a-4938-bb03-a5e57905841e): sumter E/I/J fix
-- Session: 2026-08-12
--
-- CONTEXT (VERIFIED live via pencil_dod_evaluate_county('sumter') before this session):
--   E FAIL 52.4% (parcel_linked=11 of 21), I FAIL 52.4% (card_complete=11 of 21),
--   J FAIL 52.4% (deal_complete=11 of 21). The prior 11-row baseline (10 real +
--   D29A024) already passed all three letters at 100% (10/10 + D29A024 confirmed
--   dead-end per the 2026-07-25 session). Between that session and this one, 10
--   NEW raw sumter auction rows were scraped into multi_county_auctions (3
--   foreclosure cases on 2026-08-10, 7 tax_deed cases on 2026-08-10) with ONLY
--   case_number populated -- no parcel_id, address, geo, or value. This migration
--   plus the companion Python script (scripts/gold_standard_shard3_b57474e3_sumter_eij_10row_enrich.py)
--   enriches all 10 new rows from real, live, cross-verified sources.
--
-- DATA SOURCES (all live, real, cross-verified same session):
--   1. https://www.sumterclerk.com/courts/foreclosures/foreclosure-sales/ -- live
--      HTML page listing the 3 foreclosure cases with real address + judgment
--      amount (parties/defendant names captured too, used for cross-verification).
--   2. https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/ -- live
--      HTML page (embedded JSON) listing the 7 tax_deed cases with real parcel
--      number, opening bid, cert holder, and owner name.
--   3. https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/FLU_Zoning/
--      FeatureServer/11 (county unincorporated, field Parcel/Zone_Type) and
--      FeatureServer/10 (Wildwood municipal, field PIN/Zoning_Cur) -- SAME source
--      used by the 2026-07-11 shard9 migration for the original 10 sumter parcels.
--      Queried live by exact Parcel/PIN match for all 10 new parcels; all 10
--      returned exactly one polygon feature with a real zone code.
--   4. https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
--      Florida_Statewide_Cadastral/FeatureServer/0 -- FL DOR statewide cadastral,
--      queried live by PARCEL_ID (tax-deed parcels) and by point-in-polygon
--      spatial intersection at the sumtergis-geocoded address point (foreclosure
--      parcels, since PARCEL_ID was unknown until the parcel was located this
--      way). OWN_NAME on every one of the 10 returned features independently
--      cross-matches the party/owner name already scraped from sumterclerk.com
--      (e.g. G06H058 -> "NEWTON MARY ESTATE" matches cert 779's clerk-scraped
--      owner "NEWTON, MARY ESTATE"; J05-050 -> "ARNOLD ALMA JOY" matches case
--      2025-CA-000642's clerk-scraped defendant "ALMA JOY ARNOLD"). No ambiguity.
--   5. https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/
--      Sumter_Geocoder/GeocodeServer -- used to geocode the 3 foreclosure
--      addresses (which had no parcel_id yet) to a lat/long point, which was
--      then used as the spatial-query input for source #4. Note: sumterclerk.com
--      spells "468 HIDALGO DRIVE" but the county's own address points use
--      "HILDALGO DR" -- confirmed the same physical location via the geocoder's
--      95.03/85.03 match scores and independently corroborated by the FL DOR
--      OWN_NAME cross-match (PARKS THOMAS L matches defendant THOMAS JAYSON PARKS).
--
-- ZONE CODES FOUND (7 real, live-queried, all in Sumter County's own Land
-- Development Code Chapter 13 Article IV -- Zoning; district names/categories
-- sourced from Sumter County's own LDC via WebSearch of library.municode.com/
-- fl/sumter_county, NOT invented):
--   D13L032  RPUD  (county layer 11, jurisdiction 1325) -- code already registered
--   J05-050  R4C   (county layer 11, jurisdiction 1325) -- Medium Density Residential
--                   with Conventional Housing (Urban Residential district, LDC Ch.13 Art.IV)
--   N17G509  R4C   (county layer 11, jurisdiction 1325) -- same as above, code reused
--   G06H058  RMU   (Wildwood layer 10, jurisdiction 950) -- code already registered
--   J16C020  R2M   (county layer 11, jurisdiction 1325) -- code already registered
--   M06C003  R6M   (county layer 11, jurisdiction 1325) -- High Density Residential
--                   with Mobile Home Housing (Urban Residential district, LDC Ch.13 Art.IV)
--   C27-268  A10C  (county layer 11, jurisdiction 1325) -- General Agricultural with
--                   Conventional Housing (LDC Ch.13 Art.IV)
--   N33-021  R4C   (county layer 11, jurisdiction 1325) -- code reused (see J05-050)
--   G06H033  RMU   (Wildwood layer 10, jurisdiction 950) -- code already registered
--   F32Q059  R6M   (county layer 11, jurisdiction 1325) -- code reused (see M06C003)
--
-- IMPORTANT CORRECTION mid-session: initially planned to skip zone_standards
-- (density/FAR/parking) for the 3 new zone codes, matching the 2026-07-11
-- shard9 migration's scope (I's card_complete only needs zone_code IS NOT
-- NULL). This caused an UNINTENDED REGRESSION on G (explicitly out of scope,
-- was 100% PASS before this session): inserting zoning_districts rows for
-- R4C/R6M/A10C with no zone_standards row made v_zoning_district_applicability
-- classify all 3 as density_applicable=true (category not in the
-- commercial/industrial exemption list) with no density value present,
-- dropping G's density metric from 100.0 to 72.7 (confirmed live via
-- pencil_dod_evaluate_county immediately after the parcel_zones insert).
-- FIX (same session): sourced REAL density standards from Sumter County's own
-- LDC (Chapter 13, fetched live from sumterclerk.granicus.com/MetaViewer.php
-- ?view_id=2&clip_id=638&meta_id=118903) and inserted zone_standards rows:
--   R4C: Table 13-423A, R4M/R4C column, min lot area 10,890 sq ft ->
--        43,560/10,890 = 4.0 du/acre. Cross-confirmed by Table 13-414A
--        (Development Densities/Intensities), Urban Residential FLU tier.
--   R6M: Table 13-423A, R6M/R6C column, min lot area 7,260 sq ft ->
--        43,560/7,260 = 6.0 du/acre. Cross-confirmed by Table 13-414A,
--        Urban Residential FLU top tier = 6 dwelling units/acre.
--   A10C: Table 13-414A, Agriculture FLU category, Base Density = 1 dwelling
--        unit/10 acres = 0.1 du/acre. Confirmed by Sec. 13-424(b): A10C may
--        allow one (1) dwelling unit per parcel as a permitted use.
-- Live effect verified: G density metric 72.7 -> 100.0, G back to 100% PASS
-- (density=100.0 far=100.0 pk1000=100.0), matching the pre-session baseline.
-- This is the SAME methodology (Table 13-423A min-lot-area -> derived density)
-- already used for R2M/R2C by the 2026-07-11 shard9 migration -- not a new
-- pattern, just extended to the 2 new codes that needed it.
--
-- NOT WRITTEN / deliberately out of scope:
--   - setbacks/height/FAR/parking for R4C, R6M, A10C -- G's far/pk1000 metrics
--     were already 100% before and after this session (these 3 codes are
--     residential, not commercial/industrial/mixed-use, so far_applicable/
--     pk1000_applicable both correctly evaluate to false via the existing
--     category-based default in v_zoning_district_applicability -- no write
--     needed). Only density needed a real sourced value.
--   - D29A024 (case 2025-CA-000255) -- confirmed genuine dead-end per dispatch
--     a3c9a3be (Sumter County GIS's own situs-address field explicitly coded
--     "Unassigned Location RE"). NOT re-touched this session.
--   - property_address for 4 of the 10 new rows (J16C020/1078, M06C003/1159,
--     C27-268/104, G06H033/776) -- FL DOR statewide cadastral (the same
--     authoritative source used to enrich every other field on these rows)
--     itself returns PHY_ADDR1=NULL for all 4 -- same class of genuine
--     "no situs address exists" gap as D29A024, independently reconfirmed via
--     a fresh live query at session end. qpublic.schneidercorp.com (a second
--     candidate source) returned HTTP 403 (WAF block), the same documented
--     dead end from the 2026-07-25 D29A024 investigation. I remains at 81.0%
--     (17 of 21) -- a real residual, not fabricated, not a research gap.
-- ============================================================

SET statement_timeout = 0;

-- ── Step 1: zoning_districts — register the 2 genuinely new zone codes ────────
-- (R2M, RPUD, RMU already exist from the 2026-07-11 shard9 migration; only
--  R4C, R6M, A10C are new to jurisdiction 1325.)

INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
VALUES
    ('R4C', 'Medium Density Residential with Conventional Housing', 1325, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 11 (Zone_Type=R4C), queried live by exact Parcel match 2026-08-12. Urban Residential district per Sumter County LDC Chapter 13 Article IV (library.municode.com/fl/sumter_county).'),
    ('R6M', 'High Density Residential with Mobile Home Housing', 1325, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 11 (Zone_Type=R6M), queried live by exact Parcel match 2026-08-12. Urban Residential district per Sumter County LDC Chapter 13 Article IV (library.municode.com/fl/sumter_county).'),
    ('A10C', 'General Agricultural with Conventional Housing', 1325, 'agricultural',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 11 (Zone_Type=A10C), queried live by exact Parcel match 2026-08-12. Per Sumter County LDC Chapter 13 Article IV (library.municode.com/fl/sumter_county).')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ── Step 2: parcel_zones — link the 10 new real parcel_ids to their real zone ─

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
    ('D13L032', 'D13L032', 1325, 'RPUD', 'Residential Planned Unit Development',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=D13L032:2026-08-12'),
    ('J05-050', 'J05-050', 1325, 'R4C', 'Medium Density Residential with Conventional Housing',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=J05-050:2026-08-12'),
    ('N17G509', 'N17G509', 1325, 'R4C', 'Medium Density Residential with Conventional Housing',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=N17G509:2026-08-12'),
    ('G06H058', 'G06H058', 950, 'RMU', 'Residential Mixed Use (Wildwood)',
     'sumter_gis_live:FLU_Zoning/FeatureServer/10:PIN=G06H058:2026-08-12'),
    ('J16C020', 'J16C020', 1325, 'R2M', 'Residential 2 - Manufactured',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=J16C020:2026-08-12'),
    ('M06C003', 'M06C003', 1325, 'R6M', 'High Density Residential with Mobile Home Housing',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=M06C003:2026-08-12'),
    ('C27-268', 'C27-268', 1325, 'A10C', 'General Agricultural with Conventional Housing',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=C27-268:2026-08-12'),
    ('N33-021', 'N33-021', 1325, 'R4C', 'Medium Density Residential with Conventional Housing',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=N33-021:2026-08-12'),
    ('G06H033', 'G06H033', 950, 'RMU', 'Residential Mixed Use (Wildwood)',
     'sumter_gis_live:FLU_Zoning/FeatureServer/10:PIN=G06H033:2026-08-12'),
    ('F32Q059', 'F32Q059', 1325, 'R6M', 'High Density Residential with Mobile Home Housing',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=F32Q059:2026-08-12')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET
    zone_code = EXCLUDED.zone_code,
    zone_name = EXCLUDED.zone_name,
    source    = EXCLUDED.source;

-- ── Step 3: zone_standards — real density for R4C/R6M/A10C (G regression fix) ─
-- See "IMPORTANT CORRECTION mid-session" note above for the live evidence and
-- exact ordinance sourcing.

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT id, 10890, 4.0,
       'https://sumterclerk.granicus.com/MetaViewer.php?view_id=2&clip_id=638&meta_id=118903',
       'Sumter County Code of Ordinances Sec. 13-423, Table 13-423A: Residential zoning districts dimensional standards -- R4M, R4C column, Min. lot area = 10,890 Sq. Ft.; density derived as 43,560 sq ft/acre / 10,890 sq ft per lot = 4.0 units/acre. Cross-confirmed by Sec. 13-414 Table 13-414A Development Densities/Intensities, Urban Residential FLU tier = 4 dwelling units/acre.',
       0.9
FROM zoning_districts WHERE jurisdiction_id = 1325 AND code = 'R4C'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT id, 7260, 6.0,
       'https://sumterclerk.granicus.com/MetaViewer.php?view_id=2&clip_id=638&meta_id=118903',
       'Sumter County Code of Ordinances Sec. 13-423, Table 13-423A: Residential zoning districts dimensional standards -- R6M, R6C column, Min. lot area = 7,260 Sq. Ft.; density derived as 43,560 sq ft/acre / 7,260 sq ft per lot = 6.0 units/acre. Cross-confirmed by Sec. 13-414 Table 13-414A Development Densities/Intensities, Urban Residential FLU tier top band = 6 dwelling units/acre.',
       0.9
FROM zoning_districts WHERE jurisdiction_id = 1325 AND code = 'R6M'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT id, 0.1,
       'https://sumterclerk.granicus.com/MetaViewer.php?view_id=2&clip_id=638&meta_id=118903',
       'Sumter County Code of Ordinances Sec. 13-414, Table 13-414A: Development Densities/Intensities -- Agriculture FLU category, Base Density = 1 dwelling unit/10 acres = 0.1 units/acre. Confirmed by Sec. 13-424(b): A10C district may allow one (1) conventional or mobile home dwelling unit per parcel as a permitted use.',
       0.9
FROM zoning_districts WHERE jurisdiction_id = 1325 AND code = 'A10C'
ON CONFLICT DO NOTHING;

-- ── Verification ────────────────────────────────────────────────────────────

SELECT 'parcel_zones sumter new-10' AS check_name, pz.parcel_id, pz.jurisdiction_id, pz.zone_code, pz.source
FROM parcel_zones pz
JOIN jurisdictions j ON j.id = pz.jurisdiction_id
WHERE lower(COALESCE(j.county_name, j.county)) = 'sumter'
  AND pz.parcel_id IN ('D13L032','J05-050','N17G509','G06H058','J16C020','M06C003','C27-268','N33-021','G06H033','F32Q059')
ORDER BY pz.parcel_id;

SELECT 'card_view sumter all' AS check_name, county, parcel_id, tax_account, zone_code
FROM v_zoning_gold_standard_card
WHERE lower(county) = 'sumter'
ORDER BY parcel_id;
