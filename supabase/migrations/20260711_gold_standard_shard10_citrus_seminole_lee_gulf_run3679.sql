-- GOLD STANDARD shard10 (citrus/seminole/lee/gulf), run3679, 2026-07-11
-- Documents the live data backfills applied via the Supabase Management API during this session.
-- All idempotent (safe to re-run): guarded by IS NULL / NOT EXISTS checks.
-- See issue #11633 for the full before/after pencil_dod_evaluate_county evidence and root-cause writeups.

-- ============================================================
-- CITRUS: letter I fix (94.7% -> 95.2%, 179/189 -> 180/189)
-- case 2025 CA 000651 A: real fl_parcels(co_no=19) address match.
-- lat/lng computed from the real FL GIO ArcGIS parcel polygon centroid
-- (Census/Nominatim geocoders had zero coverage for this street segment).
-- ============================================================
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, created_at)
SELECT '17E18S220020        2050', NULL, 1327, 'LDR', 'Low Density Residential District', 'inferred_residential_default_dor_crosswalk', now()
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='17E18S220020        2050');

UPDATE multi_county_auctions
SET parcel_id='17E18S220020        2050',
    latitude=28.89543534789819,
    longitude=-82.58105249355381,
    assessed_value=142485
WHERE lower(county)='citrus' AND case_number='2025 CA 000651 A' AND parcel_id IS DISTINCT FROM '17E18S220020        2050';

-- ============================================================
-- SEMINOLE: letter E fix (92.9% -> 97.0%, 92/99 -> 96/99)
-- 4 rows: real fl_parcels(co_no=69) address-match parcel_id backfill.
-- ============================================================
UPDATE multi_county_auctions SET parcel_id = '2520315BA0000142D' WHERE case_number = '2009CA006707' AND lower(county) = 'seminole' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '2221305020N000030' WHERE case_number = '2024CA001701' AND lower(county) = 'seminole' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '16212950100001760' WHERE case_number = '2024CA002404' AND lower(county) = 'seminole' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '2519305AG090E010A' WHERE case_number = '2025CA000767' AND lower(county) = 'seminole' AND parcel_id IS NULL;

UPDATE multi_county_auctions SET assessed_value = 239027 WHERE case_number = '2024CA001701' AND lower(county) = 'seminole' AND assessed_value IS NULL;
UPDATE multi_county_auctions SET assessed_value = 1220781 WHERE case_number = '2024CA002404' AND lower(county) = 'seminole' AND assessed_value IS NULL;

-- ============================================================
-- SEMINOLE: letter I fix (78.8% -> 96.0%, 78/99 -> 95/99)
-- 18 rows geocoded via the free US Census TIGER geocoder (real exact
-- matches against the already-stored property_address). parcel_zones
-- inserts corrected to use the single real precedented R-1 code for
-- jurisdiction 810 (the automated proposal initially suggested
-- AG-OTHER/VAC-RES/MFR-CONDO codes with no zoning_districts row --
-- would have silently broken letter G; not applied).
-- ============================================================
UPDATE multi_county_auctions SET latitude = 28.68749005981, longitude = -81.188092004572 WHERE case_number = '2009CA006707' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.652447454337, longitude = -81.306917336264 WHERE case_number = '2024CA001701' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.655554958833, longitude = -81.422614121075 WHERE case_number = '2024CA002404' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.806103166334, longitude = -81.260715530025 WHERE case_number = '2025CA000767' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.675848276379, longitude = -81.422813932489 WHERE case_number = '2021CA002064' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.744724505634, longitude = -81.369693581087 WHERE case_number = '2023CA002908' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.790759469613, longitude = -81.384056091944 WHERE case_number = '2024CA001031' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.765873327658, longitude = -81.275985296906 WHERE case_number = '2024CA002345' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.620608984239, longitude = -81.305591885183 WHERE case_number = '2025CA000273' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.683100521716, longitude = -81.359403608162 WHERE case_number = '2025CA000399' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.742409979703, longitude = -81.310266484594 WHERE case_number = '2025CA000414' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.771119623455, longitude = -81.268257187294 WHERE case_number = '2025CA002025' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.645561419835, longitude = -81.314706149571 WHERE case_number = '2025CA002164' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.690154535167, longitude = -81.402182889307 WHERE case_number = '2025CA002188' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.669650158836, longitude = -81.400823810784 WHERE case_number = '2025CA002236' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.686045974915, longitude = -81.219801768828 WHERE case_number = '2025CC005985' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.789033266718, longitude = -81.279306927775 WHERE case_number = '20260060/2024-006462' AND lower(county) = 'seminole' AND latitude IS NULL;
UPDATE multi_county_auctions SET assessed_value = 131246 WHERE lower(county)='seminole' AND case_number='20260060/2024-006462' AND assessed_value IS NULL;

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, created_at)
SELECT v.parcel_id, v.parcel_id, 810, 'R-1', 'Single Family Residential', 'inferred_residential_default_dor_crosswalk', NOW()
FROM (VALUES
 ('2520315BA0000142D'),('2221305020N000030'),('16212950100001760'),('2519305AG090E010A'),
 ('09-21-29-513-0000-0360'),('13-20-29-515-0000-0290'),('10-21-31-514-0000-0240'),('35-19-29-502-0000-0620'),
 ('12-20-30-515-0000-2590'),('34-21-30-517-0B00-0140'),('01-21-29-5CK-730H-0090'),('15-20-30-503-0000-0580'),
 ('12-20-30-501-0000-0460'),('21-21-30-511-0000-0620'),('03-21-29-519-0300-102D'),('10-21-29-515-0000-1300'),
 ('04-21-31-502-0000-0920'),('36-19-30-524-0400-0170')
) AS v(parcel_id)
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id);

-- ============================================================
-- LEE: letter I improvement (86.4% -> 89.7%, 236/273 -> 245/273; still FAIL, below 95% gate)
-- 9 rows: real fl_parcels(co_no=46) parcel_id matches -> property_address
-- backfill + parcel_zones insert. Corrected from the automated proposal,
-- which (a) used a punctuation-stripped parcel_id that would not have
-- matched multi_county_auctions.parcel_id's dashed/dotted format (silent
-- no-op), and (b) used a non-existent 'SFR' zone code that would have
-- broken letter G. Fixed to exact-dashed parcel_id + precedented RS-1/R1.
-- ============================================================
UPDATE multi_county_auctions SET property_address = '8020 BANYAN BREEZE WAY, FORT MYERS, FL 33908', updated_at = NOW() WHERE case_number = '25-CC-008900' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '10-46-24-12-00000.1170';
UPDATE multi_county_auctions SET property_address = '11436 CANOPY LOOP, FORT MYERS, FL 33913', updated_at = NOW() WHERE case_number = '25-CA-002365' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '08-45-26-L3-29013.0260';
UPDATE multi_county_auctions SET property_address = '112 NW 35TH PL, CAPE CORAL, FL 33993', updated_at = NOW() WHERE case_number = '25-CA-004460' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '07-44-23-C3-04171.0310';
UPDATE multi_county_auctions SET property_address = '703 WILDWOOD PKWY, CAPE CORAL, FL 33904', updated_at = NOW() WHERE case_number = '25-CA-004484' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '01-45-23-C3-00463.0210';
UPDATE multi_county_auctions SET property_address = '3426 MENORES WAY, FORT MYERS, FL 33905', updated_at = NOW() WHERE case_number = '25-CA-005377' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '34-43-26-L3-10000.7930';
UPDATE multi_county_auctions SET property_address = '2935 WINONA DR, NORTH FORT MYERS, FL 33917', updated_at = NOW() WHERE case_number = '25-CA-006555' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '26-43-24-02-00026.0000';
UPDATE multi_county_auctions SET property_address = '1807 SW 21ST LN, CAPE CORAL, FL 33991', updated_at = NOW() WHERE case_number = '25-CA-007067' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '28-44-23-C3-04843.0300';
UPDATE multi_county_auctions SET property_address = '1022 SE 20TH ST, CAPE CORAL, FL 33990', updated_at = NOW() WHERE case_number = '25-CA-000391' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '30-44-24-C4-00698.0790';
UPDATE multi_county_auctions SET property_address = '126 PARISH DR, LEHIGH ACRES, FL 33974', updated_at = NOW() WHERE case_number = '25-CA-006479' AND lower(county)='lee' AND property_address IS NULL AND parcel_id = '18-45-27-L4-18061.0060';

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, created_at)
SELECT v.parcel_id, NULL, v.jurisdiction_id, v.zone_code, v.zone_name, 'inferred_residential_default_dor_crosswalk', NOW()
FROM (VALUES
 ('10-46-24-12-00000.1170', 929, 'RS-1', 'Single Family Residential'),
 ('08-45-26-L3-29013.0260', 929, 'RS-1', 'Single Family Residential'),
 ('07-44-23-C3-04171.0310', 815, 'R1',   'Single Family Residential'),
 ('01-45-23-C3-00463.0210', 815, 'R1',   'Single Family Residential'),
 ('34-43-26-L3-10000.7930', 929, 'RS-1', 'Single Family Residential'),
 ('26-43-24-02-00026.0000', 630, 'RS-1', 'Single Family Residential'),
 ('28-44-23-C3-04843.0300', 815, 'R1',   'Single Family Residential'),
 ('30-44-24-C4-00698.0790', 815, 'R1',   'Single Family Residential'),
 ('18-45-27-L4-18061.0060', 630, 'RS-1', 'Single Family Residential')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name)
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id);

-- ============================================================
-- GULF: letter A fix (FAIL fc=5/td=0 -> PASS fc=5/td=9)
-- 9 real tax-deed sale records scraped from gulfclerk.com's live
-- "Tax Deed Sales and Surplus Funds" page, cross-verified against
-- fl_parcels(co_no=33) for real parcel_id/address/value/centroid.
-- ============================================================
INSERT INTO multi_county_auctions (county, case_number, sale_type, parcel_id, property_address, city, state, assessed_value, latitude, longitude, auction_date, data_source, tier1_authoritative, created_at, last_seen_at)
SELECT 'gulf', v.case_number, 'tax_deed', v.parcel_id,
       NULLIF(fp.phy_addr1,'N/A'), fp.phy_city, 'FL', fp.jv::numeric, fp.centroid_lat, fp.centroid_lng,
       v.sale_date::date, 'gulfclerk_taxdeed_surplus_v1', true, now(), now()
FROM (VALUES
 ('2025-001','02513000R','2025-08-27'),
 ('2025-003','02154001R','2025-08-27'),
 ('2025-010','05762000R','2025-11-19'),
 ('2025-011','02722200R','2025-11-19'),
 ('2025-017','03426604R','2025-12-17'),
 ('2025-018','05004050R','2026-01-07'),
 ('2025-021','00629010R','2026-01-21'),
 ('2025-022','00627000R','2026-03-04'),
 ('2025-023','00469000R','2026-03-18')
) AS v(case_number, parcel_id, sale_date)
JOIN fl_parcels fp ON fp.co_no=33 AND fp.parcel_id=v.parcel_id
ON CONFLICT (county, case_number, sale_type) DO NOTHING;

-- Zone only the 4 Port-St-Joe parcels using the real precedented R-1 code
-- (jurisdiction 952, verified zone_standards). Deliberately NOT zoning the
-- 5 Wewahitchka parcels (jurisdiction 1010) -- that jurisdiction has zero
-- real zoning_districts rows in this DB; an earlier attempt to crosswalk
-- them via DOR_UC caused a live regression on letter G (100%->50%) and was
-- reverted. Real Wewahitchka zoning data is a follow-up item, not fabricated here.
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, created_at)
SELECT v.parcel_id, NULL, v.jurisdiction_id, v.zone_code, v.zone_name, 'inferred_residential_default_dor_crosswalk_r1_match', now()
FROM (VALUES
 ('05004050R', 952, 'R-1', 'Single Family Residential'),
 ('05762000R', 952, 'R-1', 'Single Family Residential'),
 ('06051008R', 952, 'R-1', 'Single Family Residential'),
 ('06248410R', 952, 'R-1', 'Single Family Residential')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name)
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id);
