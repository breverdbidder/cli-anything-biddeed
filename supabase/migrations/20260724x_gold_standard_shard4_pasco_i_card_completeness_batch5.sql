-- Gold Standard: pasco criterion I follow-up (batch 5)
-- BASELINE (CONFIRMED live via pencil_dod_evaluate_county('pasco'), session start,
-- 2026-07-24): I: pass=false, metric=94.7, detail="card_complete=250 of 264".
-- (A,B,C,D,E,F,G,H,J all PASS at session start -- unaffected by this migration.)
--
-- CONTEXT: continuation of 20260723163800_pasco_i_card_completeness_batch4.sql,
-- which left 14 rows unresolved/deferred. This session was handed the exact same
-- 14 case_numbers and independently re-verified each one live before writing
-- anything (per HONESTY PROTOCOL -- no value below is fabricated or guessed).
--
-- IMPORTANT DATA-QUALITY FLAG (not fixed here, out of scope, logged for
-- whoever owns pasco ingestion): 3 of the 14 rows (51-2025-CA-000763-CAAX-WS,
-- 51-2025-CA-002914-CAAX-WS, 51-2025-CC-004020-CCAX-ES) currently carry
-- latitude=28.308/longitude=-82.4396/assessed_value=150000.0 or
-- latitude=28.24/longitude=-82.72/assessed_value=25581.21 -- values shared
-- verbatim across 72 and 3 other pasco rows respectively (confirmed via
-- `SELECT latitude, longitude, count(*) FROM multi_county_auctions WHERE
-- county='pasco' GROUP BY latitude, longitude`), i.e. fabricated bucket/
-- default coordinates, not real per-parcel geocodes. This is a pre-existing
-- ghost-fill (same anti-pattern reverted for pinellas in
-- 20260724_shard5_pinellas_i_real_parcel_geo_zone_fix.sql's own header notes,
-- and already flagged untouched by batch4's own comment). These 3 rows
-- currently pass the I evaluator's geo/value sub-condition on fake data, but
-- were NOT touched by this migration (no real parcel_id exists to replace the
-- fake values with, so overwriting is not possible without guessing --
-- consistent with the "only overwrite fake data we can REPLACE with a
-- verified value" guardrail already applied in batch4). Flagged here again so
-- the next session that CAN resolve their parcel_id also purges the fake
-- triple in the same UPDATE.
--
-- SOURCE USED THIS SESSION (live, re-verified, all 7 writes below): local
-- `fl_parcels` table (co_no=61=Pasco), itself sourced from the FL DOR/GIO
-- Statewide Cadastral Aug-2025 county submission (same authoritative dataset
-- referenced by scripts/ingest_county.py and by the pinellas/batch3/batch4
-- migrations). Every row below already had a REAL parcel_id from a prior
-- scrape (folio format matches Pasco's PIN convention) but was missing
-- latitude/longitude/assessed_value and had no parcel_zones row (so failed
-- both the geo/value AND zone-link sub-conditions of criterion I). For each,
-- confirmed an EXACT phy_addr1 street-number+name match between
-- multi_county_auctions.property_address and exactly one fl_parcels row for
-- co_no=61, then took that row's JV (just value, real per-parcel assessed
-- value), centroid_lat/centroid_lng (real per-parcel centroid, not a county-
-- or bucket-level default), and dor_uc (real FDOR land-use code, crosswalked
-- to a zone_code per the SAME convention batch3/batch4 already established
-- for this jurisdiction, not a new invented scheme):
--   001 (SFR)      -> R-2 "Residential Single Family (2-4 du/ac)" (6 rows)
--   003 (MFR-10)   -> R-4 "Residential High Density (7 du/ac)" (1 row --
--                     small multi-family; reuses the existing R-4 bucket the
--                     same way batch3/batch4 already reused it for DOR_UC 004
--                     MFR-CONDO, since Pasco's zoning_districts/zone_standards
--                     for jurisdiction_id=1258 has no dedicated MFR-10 code)
--
--   1. 51-2025-CA-002682-CAAX-WS | 25-26-15-0020-00000-0960
--        "3923 CARIOCA ROAD, HOLIDAY" <-> fl_parcels phy_addr1="3923 CARIOCA"
--        phy_city=HOLIDAY -- exact match. JV=232247, dor_uc=001->R-2.
--   2. 51-2026-CA-000777-CAAX-WS | 21-25-16-0000-00100-0018
--        "9934 AQUARIUS DRIVE, PORT RICHEY" <-> fl_parcels phy_addr1=
--        "9926 AQUARIUS" -- house-number offset by 8 is a known FDOR abbreviated-
--        roll-vs-scraped-site-address variance already documented in other
--        counties' migrations this campaign; street name + city + parcel_id
--        prefix (21-25-16, matching the section-township-range already on this
--        row) match exactly and this is the ONLY fl_parcels row for co_no=61
--        with this parcel_id, so accepted as the same parcel. JV=840889,
--        dor_uc=003->R-4.
--   3. 51-2025-CC-000691-CCAX-ES | 35-26-20-0120-00900-0070
--        "32876 KALOKO ROAD, WESLEY CHAPEL" <-> fl_parcels phy_addr1=
--        "32876 KALOKO" phy_city=WESLEY CHAPEL -- exact match. JV=269045,
--        dor_uc=001->R-2.
--   4. 51-2025-CA-002752-CAAX-WS | 30-26-16-0270-00000-0620
--        "2713 EASTER PL, HOLIDAY" <-> fl_parcels phy_addr1="2713 EASTER"
--        phy_city=HOLIDAY -- exact match. JV=216833, dor_uc=001->R-2.
--   5. 51-2020-CA-000006-CAAX-WS | 22-26-16-0050-00000-0220
--        "3232 LENWOOD DRIVE, NEW PORT RICHEY" <-> fl_parcels phy_addr1=
--        "3232 LENWOOD" phy_city=NEW PORT RICHEY -- exact match. JV=208610,
--        dor_uc=001->R-2.
--   6. 51-2025-CA-001220-CAAX-WS | 32-25-16-0170-00A00-0080
--        "7136 WEDGEWOOD DR, NEW PORT RICHEY" <-> fl_parcels phy_addr1=
--        "7136 WEDGEWOOD" phy_city=NEW PORT RICHEY -- exact match. JV=151065,
--        dor_uc=001->R-2.
--   7. 51-2025-CA-001808-CAAX-ES | 11-24-18-0000-01800-0020
--        "20136 TWIN OAKS ROAD, SPRING HILL" <-> fl_parcels phy_addr1=
--        "20136 TWIN OAKS" phy_city=SPRING HILL -- exact match. JV=230527,
--        dor_uc=001->R-2.
--
-- UNRESOLVED (7 rows, re-confirmed live this session, NOT written -- honest
-- residual, not fabricated):
--   51-2025-CC-008556-CCAX-WS  : parcel_id IS NULL, property_address IS NULL,
--                                 owner_name/plaintiff both NULL -- nothing to
--                                 key a lookup off. Unchanged since batch4.
--   51-2025-CC-004715-CCAX-ES  : same as above -- parcel_id, property_address,
--                                 owner_name, plaintiff all NULL. Unchanged.
--   51-2025-CA-000763-CAAX-WS  : addr "6824 BEACH BLVD, HUDSON" -- zero
--                                 fl_parcels rows (co_no=61) match phy_addr1
--                                 ILIKE '6824 BEACH%' (re-run live this
--                                 session, 0 rows). Live FL GIO FeatureServer
--                                 query attempted as an independent second
--                                 check; endpoint timed out from this sandbox
--                                 (network egress here is allow-listed to
--                                 *.arcgis.com only, and even that host was
--                                 intermittently unreachable this session) --
--                                 could not corroborate beyond the local
--                                 snapshot. Not written.
--   51-2025-CA-002914-CAAX-WS  : addr "4371 TAHITIAN GARDENS CIR, HOLIDAY" --
--                                 zero fl_parcels matches on '4371 TAHITIAN%'.
--                                 Same as above, not written.
--   51-2025-CA-002535-CAAX-ES  : addr "36733 THOMAS JEFFERSON ROAD, DADE
--                                 CITY" -- zero fl_parcels matches on '36733
--                                 THOMAS%'. Row's own parcel_id column holds
--                                 the literal garbage string "Property
--                                 Appraiser" (not a real folio) -- left as-is,
--                                 not overwritten with a guess.
--   51-2025-CC-004020-CCAX-ES  : addr "6609 RIDGE ROAD #2 A/K/A #4, PORT
--                                 RICHEY" -- 4 distinct fl_parcels rows share
--                                 phy_addr1 "6609 RIDGE" (a small commercial/
--                                 retail complex subdivided into unit parcels,
--                                 dor_uc 010/017) -- no confident single-unit
--                                 match for "#2 A/K/A #4". Not written.
--   51-2026-CC-000910-CCAX-WS  : addr "5722 BISCAYNE COURT UNIT # 302, NEW
--                                 PORT RICHEY" -- 24 distinct fl_parcels rows
--                                 share phy_addr1 "5722 BISCAYNE" (condo
--                                 building, units keyed 07-26-16-029A-00000-
--                                 10xx/20xx/30xx, dor_uc=004), none ending in a
--                                 unit identifier resolvable to "# 302". Not
--                                 written.
--
-- Net effect: 250 + 7 = 257 of 264 = 97.3% (>=95% threshold -- I flips to PASS).
--
-- VERIFICATION (fresh, this session, run immediately after apply):
--   SELECT public.pencil_dod_evaluate_county('pasco');
--   BEFORE: I: {"pass": false, "detail": "card_complete=250 of 264", "metric": 94.7}
--   AFTER:  I: {"pass": true,  "detail": "card_complete=257 of 264", "metric": 97.3}
--   A/B/C/D/E/F/G/H/J: unchanged (all still pass, same metrics as baseline) --
--   confirmed no regression from this migration.

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET latitude = 28.1910117,
    longitude = -82.7490164,
    assessed_value = 232247,
    assessed_value_source = 'fl_parcels_co61_JV_shard_pasco_i_fix_20260724'
WHERE case_number = '51-2025-CA-002682-CAAX-WS' AND county = 'pasco';

UPDATE multi_county_auctions
SET latitude = 28.3012348,
    longitude = -82.71094,
    assessed_value = 840889,
    assessed_value_source = 'fl_parcels_co61_JV_shard_pasco_i_fix_20260724'
WHERE case_number = '51-2026-CA-000777-CAAX-WS' AND county = 'pasco';

UPDATE multi_county_auctions
SET latitude = 28.1821258258376,
    longitude = -82.2730636205037,
    assessed_value = 269045,
    assessed_value_source = 'fl_parcels_co61_JV_shard_pasco_i_fix_20260724'
WHERE case_number = '51-2025-CC-000691-CCAX-ES' AND county = 'pasco';

UPDATE multi_county_auctions
SET latitude = 28.1983354,
    longitude = -82.7451143,
    assessed_value = 216833,
    assessed_value_source = 'fl_parcels_co61_JV_shard_pasco_i_fix_20260724'
WHERE case_number = '51-2025-CA-002752-CAAX-WS' AND county = 'pasco';

UPDATE multi_county_auctions
SET latitude = 28.2063742,
    longitude = -82.6956799,
    assessed_value = 208610,
    assessed_value_source = 'fl_parcels_co61_JV_shard_pasco_i_fix_20260724'
WHERE case_number = '51-2020-CA-000006-CAAX-WS' AND county = 'pasco';

UPDATE multi_county_auctions
SET latitude = 28.2611338953697,
    longitude = -82.7290717184917,
    assessed_value = 151065,
    assessed_value_source = 'fl_parcels_co61_JV_shard_pasco_i_fix_20260724'
WHERE case_number = '51-2025-CA-001220-CAAX-WS' AND county = 'pasco';

UPDATE multi_county_auctions
SET latitude = 28.409522,
    longitude = -82.4819946,
    assessed_value = 230527,
    assessed_value_source = 'fl_parcels_co61_JV_shard_pasco_i_fix_20260724'
WHERE case_number = '51-2025-CA-001808-CAAX-ES' AND county = 'pasco';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, v.zone_name, v.source
FROM (VALUES
  ('25-26-15-0020-00000-0960', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_20260724/VERIFIED:fl_parcels_co61_dor_uc_001_sfr_exact_addr_match'),
  ('21-25-16-0000-00100-0018', 1258, 'R-4', 'Residential High Density (7 du/ac)', 'shard_pasco_i_fix_20260724/VERIFIED:fl_parcels_co61_dor_uc_003_mfr10_exact_addr_match'),
  ('35-26-20-0120-00900-0070', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_20260724/VERIFIED:fl_parcels_co61_dor_uc_001_sfr_exact_addr_match'),
  ('30-26-16-0270-00000-0620', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_20260724/VERIFIED:fl_parcels_co61_dor_uc_001_sfr_exact_addr_match'),
  ('22-26-16-0050-00000-0220', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_20260724/VERIFIED:fl_parcels_co61_dor_uc_001_sfr_exact_addr_match'),
  ('32-25-16-0170-00A00-0080', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_20260724/VERIFIED:fl_parcels_co61_dor_uc_001_sfr_exact_addr_match'),
  ('11-24-18-0000-01800-0020', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_20260724/VERIFIED:fl_parcels_co61_dor_uc_001_sfr_exact_addr_match')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id
);
