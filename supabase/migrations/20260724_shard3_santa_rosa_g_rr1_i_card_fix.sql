-- GOLD STANDARD shard-3 santa_rosa (dispatch cc621572-35e9-41fd-a901-e5719416b834)
-- Letter G fix: "RR1" zone code (Unincorporated Santa Rosa Cty) had no zoning_districts
--   catalog row, so v_zoning_district_applicability defaulted it to
--   far_applicable=true/pk1000_applicable=true with no zone_standards -> the ONLY
--   far/pk1000-applicable parcel in the county, dragging G to 0.0 (far=0.0, pk1000=50.0).
--   RR1 = "Rural Residential Single Family" -- VERIFIED real, current, non-deprecated
--   district (Santa Rosa County LDC rev. 11/10/2025, Ord. 2025-25), distinct from R1.
--   Source: https://www.santarosa.fl.gov/DocumentCenter/View/5820/Santa-Rosa-County-Land-Development-Code-
--   Sec 2.02.01(B)(1)/2.02.04(B) purpose (p.68); Table 2.04.02.a density (p.95, RR1=2 du/acre,
--   corroborated independently by Table 2.06.01.a min lot 21,780sf = 0.5ac, matching the
--   "1/2 acre or greater" purpose text); Table 2.04.02.a max building footprint = "--" for
--   RR1 (FAR not applicable, matches every other residential district AG-RR..HR2);
--   Sec 4.06.02 parking table regulates single-family by per-unit count (2 spaces/unit),
--   not per-1000sf (per-1000sf ratios apply only to non-residential uses in that table).

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description,
                               ordinance_section, far_regulated, pk1000_regulated,
                               density_regulated, effective_date)
VALUES (
  1398, 'RR1', 'Rural Residential Single Family', 'Residential',
  'Low density residential development on parcels one half (1/2) acre or greater, characterized by single family detached structures.',
  'Santa Rosa County LDC Sec 2.02.01(B)(1), 2.02.04(B), Table 2.04.02.a, Table 2.06.01.a',
  false, false, true, '2025-11-10'
)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url,
                             ordinance_section, confidence_score)
SELECT d.id, 2.00,
       'https://www.santarosa.fl.gov/DocumentCenter/View/5820/Santa-Rosa-County-Land-Development-Code-',
       'Table 2.04.02.a (Density and Intensity Standards for Residential Zoning Districts), p.95',
       1.0
FROM zoning_districts d
WHERE d.jurisdiction_id = 1398 AND d.code = 'RR1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- Letter I fix: link 2 real Santa Rosa tax-deed parcels (real STRAP, real address, real
-- SRCPA-sourced value+zoning already confirmed live via county ArcGIS at the parcel
-- centroid) into parcel_zones so v_zoning_gold_standard_card recognizes them, and
-- backfill the multi_county_auctions geo/value fields with the same VERIFIED source data
-- (Santa Rosa County Property Appraiser record cards, parcelview.srcpa.gov).

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '10-1N-28-5690-00000-0115', 1398, 'R1M', 'Mixed Residential Subdivision District',
       'shard3_santa_rosa_g_i_fix_arcgis_zoning_2026-07-24'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '10-1N-28-5690-00000-0115' AND jurisdiction_id = 1398
);

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '07-1N-27-0000-00502-0000', 1398, 'AG-RR', 'Rural Residential Agriculture District',
       'shard3_santa_rosa_g_i_fix_arcgis_zoning_2026-07-24'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '07-1N-27-0000-00502-0000' AND jurisdiction_id = 1398
);

-- 6737 Jackson Ln, Milton FL -- STRAP 10-1N-28-5690-00000-0115
-- ArcGIS ParcelsOpenData centroid (Eg4L1xEv2R3abuQd org, FeatureServer/0, PAR_NUM query).
-- SRCPA 2025 certified just/assessed/taxable value $41,739 (parcelview.srcpa.gov/?parcel=10-1N-28-5690-00000-0115).
UPDATE multi_county_auctions
SET latitude = 30.61388096451452,
    longitude = -87.04178964406384,
    assessed_value = 41739
WHERE id = '7976c366-33c8-47b7-9a61-f0e939b00970'
  AND parcel_id = '10-1N-28-5690-00000-0115';

-- 4877 Persimmon Hollow Rd, Milton FL -- STRAP 07-1N-27-0000-00502-0000
-- ArcGIS ParcelsOpenData centroid. SRCPA 2025 certified just value $71,620,
-- assessed value $57,542 (Save Our Homes cap; parcelview.srcpa.gov/?parcel=07-1N-27-0000-00502-0000).
UPDATE multi_county_auctions
SET latitude = 30.612477051444422,
    longitude = -86.98076206351172,
    assessed_value = 57542,
    market_value = 71620
WHERE id = '59933533-914e-4d75-b407-9384b5d54664'
  AND parcel_id = '07-1N-27-0000-00502-0000';
