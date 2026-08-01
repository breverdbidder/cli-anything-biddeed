-- GOLD STANDARD shard-3 run 7858 (dispatch 6cace789) — flagler I fix.
-- ULTRALOOP: diagnosed + independently spot-checked live against
-- PalmCoastFL_Zoning and Flagler Unincorporated_Zoning ArcGIS FeatureServers
-- (point-in-polygon at real, freshly-geocoded coordinates) and the US Census
-- geocoder. Adversarial verify reproduced the same coordinates and the same
-- zone codes independently before this was applied. Survived=true, logged to
-- gold_standard_ultraloop_audit below.
--
-- Baseline (VERIFIED, live, 2026-08-01): flagler I = 94.8% (146/154).

-- 1. New zoning district for Unincorporated Flagler (jurisdiction 1184):
--    ZONECODE=MH-1 / ZONENAME='RURAL MOBILE HOME' — confirmed via exact
--    point-in-polygon hit against Flagler County's own open-data GIS
--    (services3.arcgis.com/hSKL9bYjhP4rHxSD/.../Unincorporated_Zoning) at
--    29.463012141804,-81.418372541697 (6255 Cherry Ln, Bunnell — case
--    2024 CA 000290). No numeric dimensional standards found/written this
--    session — density_regulated intentionally left NULL rather than
--    guessed (matches the campaign's no-fabrication precedent).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category)
SELECT 1184, 'MH-1', 'RURAL MOBILE HOME', 'Residential'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1184 AND code = 'MH-1');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '13-12-28-1800-00150-0010', 1184, 'MH-1',
       'gold_standard_shard3_run7858_flagler_i_20260801_arcgis_unincorp_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '13-12-28-1800-00150-0010' AND jurisdiction_id = 1184
);

-- 2. Palm Coast MPD district already exists (jurisdiction 966) — confirmed
--    via exact point-in-polygon hit against PalmCoastFL_Zoning FeatureServer
--    at 29.500612353752,-81.153575931875 (42 Del Palma Dr — case
--    2025 CA 000602).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '35-11-31-4075-00000-0210', 966, 'MPD',
       'gold_standard_shard3_run7858_flagler_i_20260801_arcgis_palmcoast_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '35-11-31-4075-00000-0210' AND jurisdiction_id = 966
);

-- 3. Real geocode (US Census Bureau geocoder, Public_AR_Current benchmark)
--    for case 2024 CA 000396 (1 Windsor Pl, Palm Coast), which had no
--    lat/lon at all. Zoning for this parcel was NOT written — ArcGIS
--    point-in-polygon returned no exact hit and a 10m buffer was mixed
--    (SFR-3/PSP/SFR-2), not clean enough to assert without a tighter check.
UPDATE multi_county_auctions
SET latitude = 29.539993604664, longitude = -81.23330205074
WHERE lower(county) = 'flagler' AND case_number = '2024 CA 000396' AND latitude IS NULL;

-- 4. Data-quality correction for case 2022 CA 000405: the stored lat/lon
--    (29.6469,-81.2088) is a known-fake constant placeholder shared across
--    multiple unrelated rows, not a real geocode. Replaced with the real
--    US Census geocode of the row's own address (1911 County Rd 75,
--    Bunnell). parcel_id for this row is the garbage value 'Property
--    Appraiser' (upstream scrape artifact) so it still cannot be
--    zone-linked and this update does NOT flip card_complete for this row
--    — it only removes fake data, tracked separately from the I metric.
UPDATE multi_county_auctions
SET latitude = 29.441248761051, longitude = -81.338171262963
WHERE lower(county) = 'flagler' AND case_number = '2022 CA 000405'
  AND latitude = 29.6469 AND longitude = -81.2088;

-- 5. Diagnostic + ULTRALOOP audit log.
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('flagler') INTO v_after;
  RAISE NOTICE 'Flagler I AFTER: %', v_after->'I';
  RAISE NOTICE 'Flagler G AFTER (regression check): %', v_after->'G';

  INSERT INTO gold_standard_ultraloop_audit
    (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
  VALUES (
    '6cace789-2a45-46e3-ac05-a1a65f1e1efb', 'fallback', 'flagler', 'I',
    'Linked 2 real parcels (13-12-28-1800-00150-0010 -> MH-1/Unincorporated, 35-11-31-4075-00000-0210 -> MPD/Palm Coast) via live ArcGIS point-in-polygon, plus 1 real Census geocode fill (2024 CA 000396) and 1 fake-placeholder-lat/lon correction (2022 CA 000405). Moves I from 146/154 toward 148/154.',
    jsonb_build_object(
      'refuted', false,
      'method', 'independent live curl re-fetch of the exact cited ArcGIS FeatureServer endpoints and the Census geocoder, reproducing identical coordinates and zone codes from scratch',
      'note', 'DB-row-count claim itself could not be checked by the refuter (no direct psql access in its sandbox); orchestrator re-verified row state via Management API before writing this migration'
    ),
    true
  );
END $$;
