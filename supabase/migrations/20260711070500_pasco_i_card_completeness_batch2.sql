-- Gold Standard: pasco criterion I follow-up (batch 2)
-- Total row count grew from 202 -> 205 between baseline and verification
-- (live scraper ingested new auctions mid-session). This batch fixes 2 of
-- the newly-surfaced failing rows:
--   51-2025-CA-002788-CAAX-ES (parcel 22-26-19-0090-00200-0310, Land O Lakes)
--   51-2025-CA-003003-CAAX-ES (parcel 03-26-21-0220-00B00-0140, Zephyrhills)
-- Both already had parcel_id + property_address but were missing
-- latitude/longitude/assessed_value, AND their parcel_id had no pasco-county
-- parcel_zones row (22-26-19-0090-00200-0310 exists in parcel_zones only
-- under jurisdiction_id=1, which is Melbourne/Brevard -- a cross-county
-- parcel_id collision, correctly excluded by the county filter in
-- v_zoning_gold_standard_card).
--
-- Sources:
--   lat/lon (centroid), assessed_value (JV) confirmed via FL GIO Statewide
--   Cadastral FeatureServer exact PARCEL_ID match + PHY_ADDR1/PHY_CITY
--   agreement with the auction's stored property_address.
--   zone_code follows the same established INFERRED unincorporated-Pasco
--   R-2/R-1 pattern already used for 186+8 prior pasco parcel_zones rows
--   (DOR_UC=001 Single Family -> R-2, unincorporated jurisdiction 1258).

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET latitude = 28.250787404964864,
    longitude = -82.19777268126454,
    assessed_value = 459516,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_run3679'
WHERE case_number = '51-2025-CA-003003-CAAX-ES' AND county = 'pasco';

UPDATE multi_county_auctions
SET latitude = 28.20575316998345,
    longitude = -82.40143313864428,
    assessed_value = 319415,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_run3679'
WHERE case_number = '51-2025-CA-002788-CAAX-ES' AND county = 'pasco';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, v.zone_name, v.source
FROM (VALUES
  ('03-26-21-0220-00B00-0140', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_run3679/INFERRED:standard_fl_ldr_pattern_dor_uc_001_sfr'),
  ('22-26-19-0090-00200-0310', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_run3679/INFERRED:standard_fl_ldr_pattern_dor_uc_001_sfr')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id
);
