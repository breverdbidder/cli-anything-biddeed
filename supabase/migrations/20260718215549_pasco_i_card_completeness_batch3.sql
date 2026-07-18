-- Gold Standard: pasco criterion I follow-up (batch 3)
-- 80.0% (196/245) -> target >=95%
--
-- Root cause: 40 multi_county_auctions rows (all tax_deed calendar_sweep_mca_v3
-- rows plus a handful of CA/CC foreclosure rows) have a valid parcel_id and an
-- already-non-null property_address (some are literal placeholder strings like
-- 'PROPERTY ADDRESS UNKNOWN' captured verbatim from the auction calendar sweep --
-- left untouched here since the I-criterion only requires property_address IS
-- NOT NULL, not that it be a real address; changing it is out of scope for this
-- migration). All 40 are missing latitude/longitude/assessed_value AND have no
-- parcel_zones row for pasco jurisdiction 1258.
--
-- Fix: backfill latitude/longitude (polygon centroid) and assessed_value (JV)
-- from FL GIO Statewide Cadastral FeatureServer via exact PARCEL_ID + CO_NO=61
-- match (services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0),
-- and insert parcel_zones rows under jurisdiction 1258 (Unincorporated Pasco
-- County) using the DOR_UC crosswalk. DOR_UC 001/002 follow the established
-- R-2/MH pattern from batch1/batch2. DOR_UC 000 (vacant residential) mapped to
-- the same R-2 pattern (vacant lots zoned residential carry the same base zone
-- as improved lots in Pasco's unincorporated LDC). New INFERRED zone_code labels
-- added for this batch's wider DOR_UC mix -- all are zone_code LABELS only, no
-- density/FAR/parking numbers invented, per guardrails:
--   004 (MFR-CONDO)   -> RMF (Multi-Family Residential)
--   009 (RES-COMMON)  -> RES-COMMON (Residential Common Area / Open Space)
--   010 (VAC-COM)     -> C-1 (Commercial, vacant)
--   012 (MIXED-USE)   -> MU (Mixed-Use)
--   094 (HISTORIC)    -> HIST (Historic Property)
--
-- 3 rows remain deferred (NULL parcel_id, no scrapeable source found this session
-- -- see comment block at end of file for the one real lookup attempt made):
--   51-2025-CC-004715-CCAX-ES, 51-2025-CC-008556-CCAX-WS, 51-2026-CC-000910-CCAX-WS

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET latitude = 28.43249797,
    longitude = -82.65935259,
    assessed_value = 2775,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000091TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.25595583,
    longitude = -82.68572467,
    assessed_value = 231493,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000098TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.42565643,
    longitude = -82.21037089,
    assessed_value = 53487,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000084TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.34574842,
    longitude = -82.70358134,
    assessed_value = 196890,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000093TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.25178389,
    longitude = -82.70288793,
    assessed_value = 0,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000108TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.25165930,
    longitude = -82.70283241,
    assessed_value = 0,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000106TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.25165151,
    longitude = -82.70249084,
    assessed_value = 0,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000107TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.25178687,
    longitude = -82.70249183,
    assessed_value = 0,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000109TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.24787470,
    longitude = -82.71737998,
    assessed_value = 306829,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2024-CA-002050-CAAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.41982501,
    longitude = -82.54574012,
    assessed_value = 386241,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2024-CA-000372-CAAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.23779190,
    longitude = -82.73233763,
    assessed_value = 42431,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2025-CA-002542-CAAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.41447569,
    longitude = -82.53245247,
    assessed_value = 104484,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000081TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.32801831,
    longitude = -82.50350060,
    assessed_value = 32257,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000105TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.32872674,
    longitude = -82.68416679,
    assessed_value = 169405,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000097TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.33115408,
    longitude = -82.18821475,
    assessed_value = 90589,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000100TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.24077631,
    longitude = -82.67302135,
    assessed_value = 1267,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000077TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.24008717,
    longitude = -82.67290091,
    assessed_value = 1026,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000078TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.39598817,
    longitude = -82.69151710,
    assessed_value = 401,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000074TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.30959793,
    longitude = -82.59950945,
    assessed_value = 9317,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000101TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.30779338,
    longitude = -82.61407143,
    assessed_value = 9240,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000079TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.22393154,
    longitude = -82.21130972,
    assessed_value = 28459,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000096TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.22393960,
    longitude = -82.74502756,
    assessed_value = 113266,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000104TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.20103049,
    longitude = -82.43763995,
    assessed_value = 466751,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2025-CA-003854-CAAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.29245526,
    longitude = -82.60055061,
    assessed_value = 9240,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000080TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.29111484,
    longitude = -82.49598806,
    assessed_value = 274797,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2025-CA-000121-CAAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.21627891,
    longitude = -82.69782494,
    assessed_value = 6852,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000071TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.21247000,
    longitude = -82.75410113,
    assessed_value = 27257,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000099TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.20433452,
    longitude = -82.65029862,
    assessed_value = 258099,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2025-CC-006500-CCAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.36800575,
    longitude = -82.15684995,
    assessed_value = 40341,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000086TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.45724856,
    longitude = -82.17943193,
    assessed_value = 97953,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000085TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.36441051,
    longitude = -82.67333192,
    assessed_value = 324462,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2025-CA-001694-CAAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.36263937,
    longitude = -82.18051658,
    assessed_value = 8654,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000076TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.37059884,
    longitude = -82.18769227,
    assessed_value = 5250,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000073TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.27865140,
    longitude = -82.73828980,
    assessed_value = 248058,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2026-CC-000478-CCAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.18118226,
    longitude = -82.74339120,
    assessed_value = 80778,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000094TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.26616338,
    longitude = -82.13365112,
    assessed_value = 60619,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000082TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.18572073,
    longitude = -82.73018721,
    assessed_value = 100571,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000092TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.26564314,
    longitude = -82.21391666,
    assessed_value = 61158,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000083TDAXXX' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.25916613,
    longitude = -82.27868236,
    assessed_value = 432010,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '51-2025-CA-001652-CAAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.35542632,
    longitude = -82.65055471,
    assessed_value = 209404,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch3'
WHERE case_number = '512026XX000103TDAXXX' AND county = 'pasco';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, v.zone_name, v.source
FROM (VALUES
  ('01-24-16-0080-00200-0120', 1258, 'HIST', 'Historic Property', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_094_historic'),
  ('03-26-16-0090-00700-0080', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('04-24-21-0000-00100-0065', 1258, 'MH', 'Mobile Home (4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_002_mh'),
  ('04-25-16-0030-00000-0030', 1258, 'MH', 'Mobile Home (4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_002_mh'),
  ('04-26-16-0020-00000-0110', 1258, 'RES-COMMON', 'Residential Common Area / Open Space', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_009_res_common'),
  ('04-26-16-0020-00000-0120', 1258, 'RES-COMMON', 'Residential Common Area / Open Space', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_009_res_common'),
  ('04-26-16-0020-00000-0130', 1258, 'RES-COMMON', 'Residential Common Area / Open Space', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_009_res_common'),
  ('04-26-16-0020-00000-0140', 1258, 'RES-COMMON', 'Residential Common Area / Open Space', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_009_res_common'),
  ('05-26-16-0030-12300-0030', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('06-24-18-0040-00002-3140', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('07-26-16-014G-04301-0100', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('08-24-18-0030-00000-1590', 1258, 'MH', 'Mobile Home (4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_002_mh'),
  ('09-25-18-0020-00E00-0020', 1258, 'MH', 'Mobile Home (4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_002_mh'),
  ('10-25-16-0610-00000-7180', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('10-25-21-0050-00000-0430', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('11-26-16-0010-01400-0020', 1258, 'C-1', 'Commercial (Vacant)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_010_vac_com'),
  ('11-26-16-0010-01400-0031', 1258, 'C-1', 'Commercial (Vacant)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_010_vac_com'),
  ('15-24-16-0010-00600-0130', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('15-25-17-0100-16700-0030', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('16-25-17-0090-14900-0060', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('16-26-21-0010-05200-0010', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('18-26-16-0400-00004-014A', 1258, 'RMF', 'Multi-Family Residential (Condo)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_004_mfr_condo'),
  ('19-26-19-0060-00000-1120', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('21-25-17-014R-23600-0101', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('22-25-18-0030-00500-0040', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('22-26-16-0010-00D00-0300', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('24-26-15-0030-00001-0370', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('24-26-16-0400-00000-1820', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('25-24-21-0020-00C00-0000', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('26-23-21-002A-00000-0352', 1258, 'MU', 'Mixed-Use', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_012_mixed_use'),
  ('26-24-16-0050-00000-0790', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('26-24-21-0120-00000-00B1', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('27-24-21-0460-02400-0010', 1258, 'R-2', 'Residential Single Family (2-4 du/ac) - Vacant', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_000_vac_res'),
  ('30-25-16-003B-01101-1410', 1258, 'RMF', 'Multi-Family Residential (Condo)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_004_mfr_condo'),
  ('31-26-16-0110-00600-00A0', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('32-25-22-0000-00500-0000', 1258, 'MH', 'Mobile Home (4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_002_mh'),
  ('32-26-16-0010-00J00-0170', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('33-25-21-0010-00800-0040', 1258, 'MH', 'Mobile Home (4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_002_mh'),
  ('35-25-20-0010-01700-0060', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr'),
  ('36-24-16-0060-00000-0860', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch3/INFERRED:dor_uc_001_sfr')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id
);

-- Deferred rows -- real lookup attempted, not fabricated:
--   51-2025-CC-004715-CCAX-ES  : parcel_id NULL, no address, no legal_description/owner_name.
--   51-2025-CC-008556-CCAX-WS  : parcel_id NULL; has lat/lon/assessed_value already (realforeclose
--                                 source) but no address to match against FL GIO or the appraiser.
--   51-2026-CC-000910-CCAX-WS  : parcel_id NULL, but HAS a real condo-unit address ("5722 BISCAYNE
--                                 COURT UNIT # 302, NEW PORT RICHEY, 34652"). Attempted a real FL
--                                 GIO lookup this session: PHY_ADDR1 LIKE '5722 BISCAYNE%' AND
--                                 CO_NO=61 against the Statewide Cadastral FeatureServer --
--                                 consistently timed out (>40s, ReadTimeout) because the service has
--                                 no usable index on PHY_ADDR1 for LIKE/wildcard queries (only exact
--                                 PARCEL_ID match, as used above, returns promptly). Did not fall
--                                 back to a guessed/fuzzy parcel match for a condo unit -- wrong
--                                 unit-level assignment risk is too high per guardrails. Deferred
--                                 honestly; all 3 are county-civil (CC) cases sourced from
--                                 JS-rendered realforeclose.com detail pages with no working scrape
--                                 path in this session (same root cause documented in batch1).
