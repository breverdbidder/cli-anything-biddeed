-- HERNANDO I: real zone_code + geo/value backfill for 26 card-incomplete tax_deed parcels
-- dispatch_id: 99c86730-5ebb-48fb-920e-6957770e0007
-- Applied live via Supabase REST API (PATCH/POST) during this session; this migration is the
-- durable record so the fix survives a fresh restore.
--
-- CONTEXT: hernando I (property card completeness) was FAIL at 46.9% (23/49 card_complete).
-- Diagnosed live: 26 of 49 in-scope rows (all auction_type=tax_deed, data_source=
-- calendar_sweep_mca_v3) were missing card fields. 21 were missing ONLY zone_code (real
-- Hernando-format parcel_ids already present, just no parcel_zones row). 5 were missing
-- geo (lat/lon) + market_value + zone_code together.
--
-- ROOT CAUSE: Hernando's zoning substrate was thin -- only 24 parcel_zones rows existed for
-- the county before this session (seeded 2026-06-24 and 2026-07-02/07-11 across prior shards),
-- covering R1A, R1C, AR2, PDP(SF) districts under jurisdiction_id=1330 (Hernando County
-- Unincorporated). None of our 26 gap parcels overlapped those existing rows.
--
-- FIX METHOD:
--   1. Queried Hernando Property Appraiser ArcGIS FeatureServer Parcels layer 0
--      (services2.arcgis.com/x5zvhhxfUuRDntRe/.../Parcels/FeatureServer/0) by PARCEL_NUMBER
--      to get SITUS_ADDRESS/SITUS_CITY/SITUS_ZIP5/CER_JUST_VALUE and polygon geometry.
--   2. Computed each parcel's centroid from the polygon geometry (mean of ring vertices).
--   3. Point-in-polygon queried the same server's Zoning_Flu FeatureServer layer 75 (Zoning)
--      at each centroid to get the real ZONING attribute.
--   4. All 26 parcels resolved a real zone_code: R1A(11), PDP(SF)(4), R1B(3), CITY(2),
--      AR2(2), AG(1), AR(1), CPDP(1), R1C(1).
--   5. Created new zoning_districts + zone_standards for R1B, AG, AR (real values sourced
--      from official Hernando County LDR PDFs -- residential-dimension-requirements.pdf for
--      R1B, agricultural-dimensional-requirements.pdf for AG, agriculturalresidential-
--      district-dimensional-requirements.pdf for AR). CPDP got a district row only (no
--      generic dimensional table exists for case-specific Planned Developments -- standards
--      are set per individual ordinance case, e.g. H-19-16 for the one CPDP parcel here).
--   6. Backfilled 7 auction rows (the 5 originally-flagged geo/value gaps + 2 more surfaced
--      once lat/long was checked directly) with real city/zip/market_value/latitude/longitude
--      from the ArcGIS Parcels layer response.
--
-- RESIDUAL GAP (left undone, no guessing): 2 parcels (2026-058TD, 2026-056TD) -- the county
-- GIS Zoning_Flu layer tags them zone_code='CITY' with ZONE_NOTES='CITY ANNEXATION WITHIN
-- CITY BOUNDARIES', meaning they were annexed into Brooksville and are no longer governed by
-- county zoning, but no queryable Brooksville-specific parcel-level zoning FeatureServer
-- exists on the same ArcGIS org to resolve the real municipal zone code. Brooksville's own
-- zoning is only available as a PDF map viewer (hernandocountygis-fl.us/CentralGIS, BROOKSMAPS
-- page), not an attribute-queryable API. Left NULL rather than guessed.
--
-- VERIFIED via pencil_dod_evaluate_county('hernando'):
--   BEFORE: I fail, card_complete=23 of 49, metric=46.9
--   AFTER:  I pass,  card_complete=47 of 49, metric=95.9
--   Independently recomputed the exact RPC SQL logic in Python against live REST data --
--   matches exactly (47/49, same 2 residual case numbers). No denominator mismatch.
--
-- SIDE EFFECT (honestly disclosed, not a regression): G (zoning FAR/density coverage) metric
-- shifted from 100.0 to 97.2 (still PASS, threshold >=95) because expanding real zone coverage
-- surfaced 1 new density_applicable parcel (the CPDP zone, case 2026-064TD) that has no sourced
-- max_density_du_acre (case-specific PD, no generic standard exists). Not fabricated.

BEGIN;

-- New zoning_districts for Hernando County Unincorporated (jurisdiction_id=1330)
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description) VALUES
  (1330, 'R1B', 'Residential (County) R1B', 'Residential', 'Hernando County unincorporated single-family residential district'),
  (1330, 'AG', 'Agricultural (County) AG', 'Agricultural', 'Hernando County unincorporated agricultural district, min 10-acre parcel'),
  (1330, 'AR', 'Agricultural/Residential (County) AR', 'Agricultural', 'Hernando County unincorporated agricultural/residential district, min 1-acre parcel'),
  (1330, 'CPDP', 'Combined Planned Development Project', 'Planned Development', 'Case-specific combined PD (SF/MF/commercial mix per ordinance case), standards set by individual case ordinance not a generic table')
ON CONFLICT DO NOTHING;
-- Applied live: R1B->id=11882, AG->id=11883, AR->id=11884, CPDP->id=11885

-- zone_standards for R1B, AG, AR (real sourced values; CPDP intentionally has none)
INSERT INTO zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, front_setback_ft, side_setback_ft,
  rear_setback_ft, max_height_ft, max_stories, max_lot_coverage_pct, max_density_du_acre,
  parking_per_unit, source_url, confidence_score, ordinance_section
) VALUES
  (11882, 7500, 75.0, 25.0, 10.0, 20.0, 35, 2, 35.0, 5.81, 2.0,
   'https://hernandocounty.us/media/p54a0efr/residential-dimension-requirements.pdf', 0.75,
   'Hernando County LDR Zoning Districts and Dimensional Requirements - R1B row; max_density_du_acre derived from min_lot_sqft (43560/7500), not directly quoted; parking_per_unit is FL-typical SF default per existing R1A precedent (2026-07-02)'),
  (11883, 435600, 150.0, 75.0, 35.0, 50.0, 45, NULL, NULL, 0.1, 2.0,
   'https://www.hernandocounty.us/media/lxqgf2fi/agricultural-dimensional-requirements.pdf', 0.75,
   'Hernando County LDR Zoning Districts and Dimensional Requirements - Rural Districts - AG row (Primary Single-Family); min_lot_sqft = 10 acres x 43560; max_density_du_acre derived (1/10), not directly quoted; front yard row used is the general (non-Collector/Arterial) 75 ft figure; parking_per_unit is FL-typical SF default'),
  (11884, 43560, 100.0, 50.0, 10.0, 35.0, 45, NULL, NULL, 1.0, 2.0,
   'https://www.hernandocounty.us/media/4uphiglk/agriculturalresidential-district-dimensional-requirements.pdf', 0.8,
   'Hernando County LDR Zoning Districts and Dimensional Requirements - Agricultural/Residential Districts - blanket table applies to All Agricultural/Residential Districts (AR, AR1, AR2); identical source+values as the existing AR2 row (zoning_district_id=11558); max_density_du_acre derived (1/1), not directly quoted; parking_per_unit is FL-typical SF default');

-- Backfill parking_per_unit on the pre-existing AR2 row (zoning_district_id=11558) which was
-- missing this field from an earlier session (2026-07-11), same FL-typical default applied
UPDATE zone_standards SET parking_per_unit = 2.0 WHERE zoning_district_id = 11558 AND parking_per_unit IS NULL;

-- parcel_zones: real zone_code for 24 of the 26 gap parcels (2 CITY-tagged parcels excluded)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES
  ('R32 323 17 5080 0412 0240', 1330, 'PDP(SF)', 'PDP (Single-Family)', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R25 423 19 0000 0051 0010', 1330, 'AG', 'Agricultural (County) AG', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R16 223 17 3850 0180 0240', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R33 222 19 1500 0000 0260', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R34 222 17 4110 00Y0 0220', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R32 422 20 0000 0770 0000', 1330, 'AR2', 'AR2 Agricultural/Residential Districts', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R16 223 17 3860 0060 0160', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R14 423 21 0000 0180 0000', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R31 422 20 0000 0100 0000', 1330, 'AR', 'Agricultural/Residential (County) AR', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R12 223 16 1890 0190 0370', 1330, 'R1B', 'Residential (County) R1B', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R15 123 21 1060 00G0 0160', 1330, 'R1B', 'Residential (County) R1B', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R21 222 19 2590 0010 0160', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R21 222 19 4271 0000 0060', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R27 221 19 2635 0000 0310', 1330, 'AR2', 'AR2 Agricultural/Residential Districts', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R20 222 19 2740 00O0 0020', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R24 121 20 1320 0000 0180', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R32 323 17 5090 0550 0250', 1330, 'PDP(SF)', 'PDP (Single-Family)', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R26 122 19 0400 0000 0195', 1330, 'R1B', 'Residential (County) R1B', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R25 222 17 2460 00C0 0060', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R20 222 18 3025 0030 0140', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R32 323 17 5130 0832 0170', 1330, 'PDP(SF)', 'PDP (Single-Family)', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R30 422 18 0000 0020 0000', 1330, 'CPDP', 'Combined Planned Development Project', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R32 323 17 5250 1745 0070', 1330, 'PDP(SF)', 'PDP (Single-Family)', 'hernando_county_gis_zoning_flu_layer75-2026-07-12'),
  ('R26 122 19 0460 0020 0000', 1330, 'R1C', 'Residential (County) R1C', 'hernando_county_gis_zoning_flu_layer75-2026-07-12');

-- Geo/value/address backfill for the 7 rows also missing lat/lon + market_value
-- (5 originally flagged + 2 more surfaced once lat/long was checked directly)
UPDATE multi_county_auctions SET city='SPRING HILL', zip='34608', market_value=36500, latitude=28.45367098290885, longitude=-82.55828499422132
  WHERE county='hernando' AND case_number='2026-039TD';
UPDATE multi_county_auctions SET city='BROOKSVILLE', zip='34602', market_value=104015, latitude=28.46259185080492, longitude=-82.36183953910466
  WHERE county='hernando' AND case_number='2026-037TD';
UPDATE multi_county_auctions SET city='HERNANDO BEACH', zip='34607', market_value=178129, latitude=28.50132163963136, longitude=-82.65767743420652
  WHERE county='hernando' AND case_number='2026-055TD';
UPDATE multi_county_auctions SET city='DADE CITY', zip='33523', market_value=11220, latitude=28.481976801359316, longitude=-82.20037041170323
  WHERE county='hernando' AND case_number='2026-027TD';
UPDATE multi_county_auctions SET city='BROOKSVILLE', zip='34613', market_value=4322342, latitude=28.53228151550051, longitude=-82.5437997737953
  WHERE county='hernando' AND case_number='2026-064TD';
UPDATE multi_county_auctions SET city='SPRING HILL', zip='34608', market_value=44580, latitude=28.484278573239838, longitude=-82.56391520604569
  WHERE county='hernando' AND case_number='2026-035TD';
UPDATE multi_county_auctions SET city='BROOKSVILLE', zip='34601', market_value=41856, latitude=28.54162702196674, longitude=-82.38172265939012
  WHERE county='hernando' AND case_number='2026-044TD';

COMMIT;

-- VERIFICATION (run after apply):
-- SELECT public.pencil_dod_evaluate_county('hernando');
-- Expected: I metric 46.9 -> 95.9 (card_complete 23 -> 47 of 49), PASS
-- Note: G metric will shift 100.0 -> 97.2 (still PASS) as a disclosed side effect (see above)
