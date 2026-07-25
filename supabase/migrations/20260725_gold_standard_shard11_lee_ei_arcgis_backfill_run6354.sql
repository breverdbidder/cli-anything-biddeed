-- Gold Standard shard-11 lee E/I fix, dispatch 03ff9ae3-9a64-4179-8345-d6b129a0ed83
-- loop run 6354, chat_session architect-20260725T080000
--
-- Live-verified via Lee County Parcels ArcGIS FeatureServer
-- (services2.arcgis.com/LvWGAAhHwbCJ2GMP/.../Lee_County_Parcels/FeatureServer/0/query),
-- the same proven endpoint used by prior lee sessions
-- (scripts/gold_standard_shard5_lee_ei_arcgis_backfill.py).
--
-- 4 auction rows fixed, all zone codes matched to EXISTING zoning_districts +
-- zone_standards rows with real max_density_du_acre values (815/R1=4.00,
-- 929/RS-7=7.00) and far_applicable=false / pk1000_applicable=false per the
-- live v_zoning_district_applicability view -- zero G-regression risk, no
-- new zoning_districts rows created.
--
-- 25-CA-002593 and 25-CA-003385: same underlying parcel (STRAP
--   244322C3054250330, 3312 Old Burnt Store Rd N, Cape Coral, same
--   auction_date 2026-08-06) surfaced under two different case numbers --
--   confirmed via identical ArcGIS match, not a bug. The live
--   uq_mca_county_sale_date_parcel constraint (county, sale_type,
--   auction_date, parcel_id) forbids assigning the same parcel_id to both
--   rows on the same date, so only 25-CA-003385 (older row, already carries
--   a real data_source='calendar_sweep_mca_v3' vs 002593's NULL) gets the
--   parcel_id write. 25-CA-002593 is left untouched -- a genuine duplicate-
--   case-number data-quality anomaly, not something this fix should paper
--   over by picking an arbitrary parcel_id assignment.
--
-- Residual (documented, NOT fabricated): 32 of the 37 E-gap rows have no
-- property_address at all (case_number only), and 4 of the 5 addressed rows
-- (1067 Danpark Loop, 16300 Pine Ridge Rd Lot X18, 98 Sable Dr Lot 98, 14454
-- Cantabria Dr) returned zero ArcGIS matches even on loosened LIKE patterns --
-- consistent with mobile-home-park lot addresses that don't carry their own
-- STRAP in this layer. 10 of the 16 I zone-gap rows resolved to a real
-- ArcGIS zoning code with NO existing zoning_districts precedent in that
-- jurisdiction (Fort Myers CPD, Bonita Springs MH-1, Fort Myers Beach RS-1,
-- unincorporated CS) -- per this campaign's established caution
-- (GOLD_STANDARD_SHARD5_SEMINOLE_HIGHLANDS_LEE continuation report), these
-- are deliberately NOT linked without real ordinance-verified standards, to
-- avoid the exact G regression documented in that report and the hillsborough
-- SHARD4 incident. 3 more (Fort Myers/N Fort Myers/Cape Coral) had NULL/empty
-- ZONING at the ArcGIS source itself. 1 row (25-CA-004116, parcel_id
-- literally 'TIMESHARE') and 1 row (24-CA-007460, parcel_id 'Property
-- Appraiser', no address) are garbage placeholder values with no resolvable
-- identity.

SET statement_timeout = 0;

-- STEP 1: backfill real parcel_id + geo + assessed_value onto
-- multi_county_auctions (overwrites placeholder text 'Property Appraiser'
-- with the real STRAP where applicable).

UPDATE multi_county_auctions
SET parcel_id = '24-43-22-C3-05425.0330',
    latitude = 26.715909,
    longitude = -82.055733,
    assessed_value = 147641
WHERE lower(county) = 'lee' AND case_number = '25-CA-003385';

UPDATE multi_county_auctions
SET latitude = 26.568847,
    longitude = -82.032751,
    assessed_value = 445468
WHERE lower(county) = 'lee' AND case_number = '25-CA-003297'
  AND parcel_id = '08-45-23-C4-00200.0020';

UPDATE multi_county_auctions
SET latitude = 26.562449,
    longitude = -81.984811,
    assessed_value = 600414
WHERE lower(county) = 'lee' AND case_number = '25-CA-002748'
  AND parcel_id = '14-45-23-C1-04544.0050';

UPDATE multi_county_auctions
SET parcel_id = '17-44-25-P4-00400.0910',
    latitude = 26.644214,
    longitude = -81.833704,
    assessed_value = 150444
WHERE lower(county) = 'lee' AND case_number = '24-CA-005519';

-- STEP 2: link parcel_zones for the 3 distinct parcels touched above, using
-- the zone code the live ArcGIS layer returned, into jurisdictions that
-- already carry a real zone_standards row for that exact code.

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('24-43-22-C3-05425.0330', 815, 'R1',   'R1 Zone',                       'lee_shard11_run6354_arcgis_20260725'),
  ('08-45-23-C4-00200.0020', 815, 'R1',   'R1 Zone',                       'lee_shard11_run6354_arcgis_20260725'),
  ('14-45-23-C1-04544.0050', 815, 'R1',   'R1 Zone',                       'lee_shard11_run6354_arcgis_20260725'),
  ('17-44-25-P4-00400.0910', 929, 'RS-7', 'Residential Single-Family - 7', 'lee_shard11_run6354_arcgis_20260725')
ON CONFLICT DO NOTHING;
