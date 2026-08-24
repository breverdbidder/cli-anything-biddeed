-- Gold Standard shard-4 (dispatch 691cd31e-21e3-40ce-9d73-3b05482763b6, this session):
-- okaloosa letters C/D/E/I
--
-- BEFORE (pencil_dod_evaluate_county('okaloosa'), LIVE-VERIFIED this session):
--   C: matched_clean=72 of 82 (87.8%) -- FAIL
--   D: matched_any=72 of 82 (87.8%) -- FAIL
--   E: parcel_linked=73 of 82 (89.0%) -- FAIL
--   I: card_complete=72 of 82 (87.8%) -- FAIL
--   All other letters (A,B,F,G,H,J) PASS. G=95.8% (Destin ROI-TD fix from 08-14
--   session held, no regression).
--
-- ROOT CAUSE (re-confirmed live this session, matches the 2026-08-12 dispatch
-- 7be9b60b diagnosis exactly): okaloosa-bid4assets-harvest.yml (daily cron) adds
-- new foreclosure/tax-deed rows but NEVER runs scripts/okaloosa_parcel_gis_enrich.py
-- afterward. Denominator grew 75 (as of the 2026-08-14 session) -> 82 today, with
-- 7 of 9 currently-unlinked rows created 2026-08-20/21 by that cron and never
-- enriched. This is the same durability gap flagged unresolved in 3+ prior session
-- reports (dispatch 7be9b60b, f3702b8e, shard9 run6080) -- the workflow-file fix
-- itself remains out of reach for a CC session (GH App token lacks `workflows`
-- scope, documented since architect triage 18472 on 2026-08-09).
--
-- DIAGNOSIS PER ROW (live queries against multi_county_auctions + okgis.myokaloosa.com
-- ArcGIS REST, this session):
--
-- FIXED (3 rows, real GIS-sourced parcel_id + geo + value + zoning, all three
-- addresses resolved via okgis.myokaloosa.com Land-Ownership/Parcels_with_Addressing
-- MapServer/121, exact SITE_ADDR match, then zoned via LocalGovernment/EnerGov_Basemap
-- MapServer/9 (county zoning layer -- validated this session by re-querying the
-- already-confirmed 2024CA002521F point and getting the expected R-2, so layer
-- choice is cross-checked against a known-good prior result) for the unincorporated
-- parcel, and Crestview's own ArcGIS Online zoning service
-- (services9.arcgis.com/zvdDL6ILvlkPNTg8/.../Zoning_and_FLU/FeatureServer/0, the
-- same service cited by 3 prior sessions for other Crestview parcels in this DB)
-- for the two Crestview-incorporated parcels, since okgis's countywide zoning
-- layer only labels incorporated areas by city name, not a real zone code):
--   1. 2024CA003322C   (FC, created 2026-08-20) -- addr "1050B S WILSON ST,
--      CRESTVIEW FL 32536" exact-matched PIN 20-3N-23-1090-0003-0050
--      (TOTALAPPR=ASSEDVAL=219961). Point falls inside Crestview city limits
--      (ICLPY_CITY_CODE=CRESTVIEW); Crestview Zoning_and_FLU FeatureServer
--      returns ZONE=MU for this exact PIN (cross-verified match).
--   2. 2025CA000141C   (FC, created 2026-08-21) -- addr "4250 ANTIOCH ROAD,
--      CRESTVIEW FL 32536" exact-matched PIN 05-2N-23-2324-000A-0080
--      (TOTALAPPR=ASSEDVAL=221723). Also inside Crestview city limits;
--      Crestview Zoning_and_FLU FeatureServer returns ZONE=R-2 for this PIN.
--   3. 2025-CA-003550-C (FC, created 2026-08-20) -- addr "3675 East Plympton
--      Rd., LAUREL HILL FL 32567" exact-matched PIN 19-5N-22-0000-0007-0050
--      (TOTALAPPR=ASSEDVAL=127053). Point falls OUTSIDE all incorporated city
--      limits (ICLPY_CITY_CODE=UNINCORPORATED); county zoning layer (EnerGov_
--      Basemap/MapServer/9) returns ZNGPY_ZONE=AA at this point.
--   All three zone codes (MU/jurisdiction 871, R-2/jurisdiction 871,
--   AA/jurisdiction 1407) already have pre-existing zoning_districts rows in
--   this DB from prior sessions -- no new zoning_districts/zone_standards rows
--   needed, so this fix carries NO letter-G regression risk (unlike the
--   2026-08-14 session's Destin ROI-TD situation, where a brand-new district
--   had to be created and briefly broke G).
--
-- FIXED (1 row, parity_status completion only -- no new sourcing needed):
--   4. 2025-CA-003304-C -- already has parcel_id/geo/value/zoning from the
--      2026-08-14 session's Destin ROI-TD fix (already PASSES letter I today),
--      but that session never set parity_status/parity_source, so it still
--      fails C/D. Completing parity_status using the exact same GIS match
--      already on record (Destin, PIN 00-2S-22-1125-0000-0490, exact SITE_ADDR
--      match) -- this is not a new fabricated fact, just finishing the marking
--      of a fact already sourced and committed in a prior migration.
--
-- NOT FIXED -- genuine structural/data-availability gaps (evidence below,
-- BLANK > WRONG, no value guessed):
--   - 2024-CA-000470 (FC) / 2024-TDD-000089 (TD): zero address, zero geo, zero
--     value fields since creation 2026-07-05. Documented dead legacy placeholder
--     stub rows across 6+ prior sessions (SHARD3_ORANGE_HERNANDO_MIAMIDADE_
--     OKALOOSA, SHARD5_OKALOOSA f3702b8e, SHARD7_OKALOOSA_HOLMES, shard9 run6080,
--     dispatch 7be9b60b, and this session). No new data source located.
--   - 2025-CA-002286-F2 ("Lot 12, Block 3, GREY MOSS POINT"), -F3 ("Condominium
--     Unit D-311, SUMMER BREEZE"), -F4 ("Lot 24 of UNRECORDED DELAWARE
--     PLANTATION SUBDIVISION PHASE TWO"), -F5 ("SECTION 8, TOWNSHIP 3 NORTH,
--     RANGE 21 WEST, WALTON COUNTY, FLORIDA") -- 4 legal-description-only rows
--     from a multi-parcel foreclosure bundle (case 2025-CA-002286), created
--     2026-08-20. Investigated this session: "SUMMER BREEZE" and "DELAWARE"
--     do not appear in okgis.myokaloosa.com's LEGL1 field at all (an unrecorded
--     subdivision plat, per F4's own text, would not carry an official platted
--     legal description). F5's own address text names Walton County, not
--     Okaloosa -- may be a genuinely different-county parcel within the same
--     court case, which this county's GIS would never resolve. F2's "Lot 12
--     Block 3 Grey Moss Point" DOES exist in the GIS (PIN 07-1S-22-1080-0003-0120,
--     owner AYERS RHONDA L) -- but that exact PIN is *already* the parcel_id
--     recorded against the case's own base row (2025-CA-002286-F, matched via
--     owner-name-match in the 2026-08-12 dispatch 7be9b60b session), and F's
--     own property_address text ("Lot 50 Delaware Plantations Subdivision")
--     does not match that PIN's real legal description ("Lot 12 Blk 3 Grey Moss
--     Point") either. This is an unresolved discrepancy in a PRIOR session's
--     owner-name match, not a gap this session introduced -- assigning the same
--     PIN to F2 would create a duplicate-parcel assignment across two case rows
--     in the same suit, which is not a real, distinct fact. Left unfixed rather
--     than compounding a possibly-wrong prior match with a second one.
--   - B4A-1299799 (TD, Mary Esther, 37 MARY ESTHER DR) -- has a real parcel_id
--     and already PASSES C/D (matched_clean via bid4assets tier1 source), fails
--     ONLY letter I. Re-confirmed this session: LocalGovernment/Mary_Esther_
--     EnerGov/MapServer has no "Zoning" layer (only Site Address, Parcels,
--     Subdivisions, Platted-Lots, flood/admin layers) -- this incorporated
--     jurisdiction has no zoning GIS coverage published anywhere on
--     okgis.myokaloosa.com. Documented unresolved since the 2026-08-14 session;
--     re-probed and still absent today.
--
-- EXPECTED RESULT (honest projection, NOT yet re-verified live -- see Round 3
-- for the actual post-fix pencil_dod_evaluate_county call):
--   C/D: 72 -> 76 of 82 (92.7%) -- STILL FAIL (need >=78/82)
--   E:   73 -> 76 of 82 (92.7%) -- STILL FAIL (need >=78/82)
--   I:   72 -> 75 of 82 (91.5%) -- STILL FAIL (need >=78/82)
-- This session narrows the gap by 3-4 rows per letter but does NOT close it.
-- The 7-row residual (2 dead stubs + 4 multi-parcel-bundle rows + 1 Mary
-- Esther zoning gap) is a genuine structural ceiling given real, sourced data
-- available today -- consistent with the extensive multi-session failure
-- history on this exact letter set.
--
-- Env used: SUPABASE_ACCESS_TOKEN (Management API SQL endpoint) +
-- SUPABASE_SERVICE_ROLE_KEY (PostgREST). County scope: okaloosa ONLY.

BEGIN;

-- Row 1: 2024CA003322C -- parcel_id + geo + value + parity backfill (Crestview,
-- GIS exact-address match).
UPDATE multi_county_auctions
SET parcel_id = '20-3N-23-1090-0003-0050',
    latitude = 30.749562066740243,
    longitude = -86.56532053244906,
    assessed_value = 219961.0,
    market_value = 219961.0,
    parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard4_691cd31e_okaloosa'
WHERE county = 'okaloosa' AND case_number = '2024CA003322C';

-- Row 2: 2025CA000141C -- parcel_id + geo + value + parity backfill (Crestview,
-- GIS exact-address match).
UPDATE multi_county_auctions
SET parcel_id = '05-2N-23-2324-000A-0080',
    latitude = 30.699941210304733,
    longitude = -86.57351796091758,
    assessed_value = 221723.0,
    market_value = 221723.0,
    parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard4_691cd31e_okaloosa'
WHERE county = 'okaloosa' AND case_number = '2025CA000141C';

-- Row 3: 2025-CA-003550-C -- parcel_id + geo + value + parity backfill
-- (unincorporated county, GIS exact-address match).
UPDATE multi_county_auctions
SET parcel_id = '19-5N-22-0000-0007-0050',
    latitude = 30.910956748733778,
    longitude = -86.48346081797484,
    assessed_value = 127053.0,
    market_value = 127053.0,
    parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard4_691cd31e_okaloosa'
WHERE county = 'okaloosa' AND case_number = '2025-CA-003550-C';

-- Row 4: 2025-CA-003304-C -- parity_status completion only. parcel_id/geo/value
-- already set by the 2026-08-14 session (Destin ROI-TD fix); that session
-- populated I-relevant fields but never set parity_status/parity_source.
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:gold_standard_shard2_5f3a88a5'
WHERE county = 'okaloosa' AND case_number = '2025-CA-003304-C'
  AND parcel_id = '00-2S-22-1125-0000-0490';

-- parcel_zones inserts (rows 1-3 only): real primary-source GIS zoning, one
-- live point-in-polygon / PIN-match query per parcel this session. Both MU and
-- R-2 (Crestview, jurisdiction 871) and AA (Unincorporated Okaloosa County,
-- jurisdiction 1407) already have pre-existing zoning_districts rows -- ON
-- CONFLICT DO NOTHING guards against re-inserting existing parcel_zones links.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
VALUES
  ('20-3N-23-1090-0003-0050', 871,  'MU',  'crestview_gis:zoning_and_flu_featureserver:0:shard4_691cd31e_okaloosa'),
  ('05-2N-23-2324-000A-0080', 871,  'R-2', 'crestview_gis:zoning_and_flu_featureserver:0:shard4_691cd31e_okaloosa'),
  ('19-5N-22-0000-0007-0050', 1407, 'AA',  'okaloosa_gis:localgovernment/energov_basemap:9:shard4_691cd31e_okaloosa')
ON CONFLICT DO NOTHING;

COMMIT;
