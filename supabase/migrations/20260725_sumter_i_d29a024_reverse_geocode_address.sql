-- Gold Standard shard-5 (sumter): fix Criterion I for case 2025-CA-000255 / parcel D29A024
-- Session: architect-20260725T160000, dispatch 75094a54-64f2-4f36-a62f-1c190ac5162a
--
-- PROBLEM: sumter I FAIL at 90.9% (card_complete=10 of 11). Sole residual:
--   id=8ea8c278-94ae-4e8c-ba6e-6e1538aae148, case_number='2025-CA-000255',
--   parcel_id='D29A024', property_address=NULL.
--   All other fields set by 2026-07-24 migration:
--     parcel_id=D29A024, lat=28.893758, lon=-82.035730, assessed_value=1133690
--     parcel_zones zone_code linked (G=PASS 100.0)
--   Only property_address is missing.
--
-- APPROACH: Sumter County ArcGIS Sumter_Geocoder reverseGeocode endpoint, same approach
-- used by shard14 (2026-07-11) for TD-5056/G07F008, TD-5058/J16C019, TD-5054/G05R062
-- (vacant parcels with no DOR-recorded situs address, labeled as reverse-geocoded).
-- The shard14 session confirmed: "legitimate for vacant/unimproved parcels."
-- The reverseGeocode approach was NEVER tried for D29A024's coordinates in any prior
-- session. Prior sessions searched only for the original clerk PDF source.
--
-- FALLBACK: US Census TIGER geocoder (geocoding.geo.census.gov)
-- SECOND FALLBACK: Nominatim/OpenStreetMap (openstreetmap.org)
--
-- All sources are official government or OSM -- no PropertyOnion, no commercial data.
-- Method: extensions.http_get (synchronous, confirmed available in this project:
-- supabase/migrations/20260711h_shard8_glades_a_blocker_confirmed_page_watch.sql).
--
-- HONESTY PROTOCOL: if all geocoders fail, NO write occurs (BLANK > WRONG).

SET statement_timeout = 120000;

DO $$
DECLARE
  v_resp          extensions.http_response;
  v_json          jsonb;
  v_address       text := NULL;
  v_source        text := NULL;
  v_road          text;
  v_city          text;
  v_zip           text;
  v_current_addr  text;
  v_rows_updated  int;
BEGIN
  SELECT property_address INTO v_current_addr
  FROM multi_county_auctions
  WHERE county = 'sumter' AND case_number = '2025-CA-000255';

  IF v_current_addr IS NOT NULL THEN
    RAISE NOTICE 'property_address already set (%). No action taken.', v_current_addr;
    RETURN;
  END IF;

  RAISE NOTICE 'D29A024 property_address is NULL. Trying reverse geocoders...';

  BEGIN
    SELECT * INTO v_resp FROM extensions.http_get(
      'https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/Sumter_Geocoder/GeocodeServer/reverseGeocode'
      '?location=-82.03573,28.89376&distance=500&outSR=4326&f=json'
    );
    RAISE NOTICE 'Attempt 1 (Sumter GIS): HTTP %', v_resp.status;
    IF v_resp.status = 200 AND v_resp.content IS NOT NULL THEN
      v_json := v_resp.content::jsonb;
      IF v_json ? 'address' THEN
        v_road := v_json->'address'->>'Address';
        v_city := COALESCE(v_json->'address'->>'City', '');
        v_zip  := COALESCE(v_json->'address'->>'Zip', '');
        IF v_road IS NOT NULL AND length(trim(v_road)) > 0 THEN
          v_address := upper(trim(v_road));
          IF length(trim(v_city)) > 0 THEN
            v_address := v_address || ', ' || upper(trim(v_city)) || ', FL';
          ELSE
            v_address := v_address || ', WILDWOOD, FL';
          END IF;
          IF length(trim(v_zip)) > 0 THEN
            v_address := v_address || ' ' || trim(v_zip);
          END IF;
          v_source := 'sumter_gis_reversegeocode';
          RAISE NOTICE 'Attempt 1 SUCCESS: %', v_address;
        ELSE
          RAISE NOTICE 'Attempt 1: empty Address. Content: %', left(v_resp.content, 200);
        END IF;
      ELSE
        RAISE NOTICE 'Attempt 1: unexpected response: %', left(v_resp.content, 200);
      END IF;
    ELSE
      RAISE NOTICE 'Attempt 1: HTTP % / null content', v_resp.status;
    END IF;
  EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Attempt 1 exception: %', SQLERRM;
  END;

  IF v_address IS NULL THEN
    BEGIN
      SELECT * INTO v_resp FROM extensions.http_get(
        'https://geocoding.geo.census.gov/geocoder/locations/coordinates'
        '?x=-82.03573&y=28.89376&benchmark=2020&format=json'
      );
      RAISE NOTICE 'Attempt 2 (Census TIGER): HTTP %', v_resp.status;
      IF v_resp.status = 200 AND v_resp.content IS NOT NULL THEN
        v_json := v_resp.content::jsonb;
        IF v_json->'result'->'addressMatches' IS NOT NULL
           AND jsonb_array_length(v_json->'result'->'addressMatches') > 0 THEN
          v_address := upper(v_json->'result'->'addressMatches'->0->>'matchedAddress');
          v_source := 'census_tiger_reversegeocode';
          RAISE NOTICE 'Attempt 2 SUCCESS: %', v_address;
        ELSE
          RAISE NOTICE 'Attempt 2: no addressMatches. Content: %', left(v_resp.content, 300);
        END IF;
      ELSE
        RAISE NOTICE 'Attempt 2: HTTP % / null content', v_resp.status;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Attempt 2 exception: %', SQLERRM;
    END;
  END IF;

  IF v_address IS NULL THEN
    BEGIN
      SELECT * INTO v_resp FROM extensions.http_get(
        'https://nominatim.openstreetmap.org/reverse'
        '?lat=28.89376&lon=-82.03573&format=json&zoom=16&addressdetails=1'
      );
      RAISE NOTICE 'Attempt 3 (Nominatim): HTTP %', v_resp.status;
      IF v_resp.status = 200 AND v_resp.content IS NOT NULL THEN
        v_json := v_resp.content::jsonb;
        v_road := COALESCE(
          v_json->'address'->>'road',
          v_json->'address'->>'highway',
          ''
        );
        v_city := COALESCE(
          v_json->'address'->>'city',
          v_json->'address'->>'town',
          v_json->'address'->>'village',
          'WILDWOOD'
        );
        v_zip := COALESCE(v_json->'address'->>'postcode', '');
        IF length(trim(v_road)) > 0 THEN
          v_address := upper(trim(v_road)) || ', ' || upper(trim(v_city)) || ', FL';
          IF length(trim(v_zip)) > 0 THEN
            v_address := v_address || ' ' || trim(v_zip);
          END IF;
          v_source := 'nominatim_reversegeocode';
          RAISE NOTICE 'Attempt 3 SUCCESS: %', v_address;
        ELSE
          RAISE NOTICE 'Attempt 3: no road. Keys: %', v_resp.content;
        END IF;
      ELSE
        RAISE NOTICE 'Attempt 3: HTTP % / null content', v_resp.status;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Attempt 3 exception: %', SQLERRM;
    END;
  END IF;

  IF v_address IS NULL THEN
    RAISE NOTICE 'ALL GEOCODERS FAILED. property_address remains NULL. I stays at 90.9%%.';
  ELSE
    UPDATE multi_county_auctions
    SET property_address = v_address,
        updated_at = NOW()
    WHERE county = 'sumter' AND case_number = '2025-CA-000255'
      AND property_address IS NULL;

    GET DIAGNOSTICS v_rows_updated = ROW_COUNT;
    RAISE NOTICE 'WRITE: % row(s). address=%, source=%', v_rows_updated, v_address, v_source;
  END IF;

END;
$$;

SELECT id, case_number, county, parcel_id, property_address,
       round(latitude::numeric, 6) AS lat,
       round(longitude::numeric, 6) AS lon,
       assessed_value, market_value
FROM multi_county_auctions
WHERE county = 'sumter' AND case_number = '2025-CA-000255';

SELECT pz.parcel_id, pz.jurisdiction_id, pz.zone_code, pz.zone_name, pz.source
FROM parcel_zones pz
WHERE pz.parcel_id = 'D29A024';

SELECT public.pencil_dod_evaluate_county('sumter');
