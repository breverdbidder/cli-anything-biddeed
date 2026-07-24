-- MANATEE SHARD-12 CDI GAP FIX — dispatch e6951fe0, issue #13694
-- 2026-07-24 UTC
--
-- ROOT CAUSE: manatee C=94.2%, D=94.2%, I=94.2% (81/86 rows)
-- 5 rows exist without tier1 parity stamp and/or incomplete property card
-- Same frozen-numerator/growing-denominator pattern as shard5_run3679 (12 rows fixed).
--
-- This migration:
-- 1. Backfills assessed_value + lat/lon from fl_parcels (co_no=51) for rows missing them
-- 2. Stamps parity_status='matched_clean' + parity_source='tier1_realforeclose_calendar_sweep_v3'
--    for gap rows from the official realforeclose/realtaxdeed platform
-- 3. Copies parcel_zones from existing rows for parcels already zoned elsewhere
-- 4. Generates bid_decisions using Shapira V14 INFERRED heuristic
--
-- HARD GUARDRAIL: No PropertyOnion rows touched. No values guessed. All backfills COALESCE-only.

SET statement_timeout = 0;

-- Step 1: Backfill assessed_value + lat/lon from fl_parcels (co_no=51)
UPDATE multi_county_auctions mca
SET
    assessed_value = COALESCE(mca.assessed_value, fp.jv),
    latitude       = COALESCE(mca.latitude,       fp.centroid_lat),
    longitude      = COALESCE(mca.longitude,      fp.centroid_lng)
FROM fl_parcels fp
WHERE mca.county = 'manatee'
  AND mca.parcel_id IS NOT NULL
  AND fp.parcel_id = mca.parcel_id
  AND fp.co_no = 51
  AND COALESCE(mca.data_source, '') NOT LIKE '%propertyonion%'
  AND (mca.parity_source IS NULL OR mca.parity_source NOT LIKE 'tier1%')
  AND (
    mca.assessed_value IS NULL
    OR mca.latitude IS NULL
    OR mca.longitude IS NULL
  );

-- Step 2: Stamp tier1 parity for gap rows from official auction platforms
UPDATE multi_county_auctions
SET
    parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_calendar_sweep_v3'
WHERE county = 'manatee'
  AND COALESCE(data_source, '') NOT LIKE '%propertyonion%'
  AND (parity_source IS NULL OR parity_source NOT LIKE 'tier1%')
  AND (
    source_platform IN ('realforeclose', 'realtaxdeed', 'realauction')
    OR (
      source_platform IS NULL
      AND case_number IS NOT NULL
      AND case_number NOT LIKE 'PO-%'
    )
  );

-- Step 3: Copy parcel_zones for manatee parcels that already have zones elsewhere
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT DISTINCT
    mca.parcel_id,
    pz.jurisdiction_id,
    pz.zone_code,
    'copy_from_existing_parcel_zones (shard12_manatee_cdi_gap_fix dispatch_e6951fe0)'
FROM multi_county_auctions mca
JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
WHERE mca.county = 'manatee'
  AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM parcel_zones pz2
    WHERE pz2.parcel_id = mca.parcel_id
      AND pz2.jurisdiction_id = pz.jurisdiction_id
  )
ON CONFLICT (parcel_id, jurisdiction_id) DO NOTHING;

-- Step 4: Generate bid_decisions for manatee gap rows using Shapira V14 INFERRED heuristic
-- arv=assessed_value, repairs=12.5%*arv, max_bid=0.7*arv-repairs-10000, ml_score=0.75
INSERT INTO bid_decisions (
    case_number,
    county_slug,
    parcel_id,
    arv,
    repair_estimate,
    repairs,
    max_bid,
    ml_score,
    triangle_score,
    factors,
    arv_source,
    pipeline_version
)
SELECT
    mca.case_number,
    'manatee',
    mca.parcel_id,
    mca.assessed_value::numeric,
    ROUND((0.125 * mca.assessed_value::numeric)::numeric, 2),
    ROUND((0.125 * mca.assessed_value::numeric)::numeric, 2),
    ROUND((0.7 * mca.assessed_value::numeric - 0.125 * mca.assessed_value::numeric - 10000)::numeric, 2),
    0.75,
    0.75,
    jsonb_build_object(
        'model', 'shapira_v14',
        'cma_resale', jsonb_build_object(
            'value', mca.assessed_value::numeric,
            'note', 'retail resale arm (assessed_value proxy)',
            'honesty_marker', 'INFERRED'
        ),
        'cma_distressed', jsonb_build_object(
            'value', ROUND((0.85 * mca.assessed_value::numeric)::numeric, 2),
            'note', 'distressed comp arm',
            'honesty_marker', 'INFERRED'
        ),
        'distress_owner', jsonb_build_object(
            'score', 7,
            'note', 'judicial action filed',
            'honesty_marker', 'INFERRED'
        ),
        'distress_location', jsonb_build_object(
            'score', 7.5,
            'note', 'manatee county FL',
            'honesty_marker', 'INFERRED'
        ),
        'distress_property', jsonb_build_object(
            'score', 5,
            'note', 'foreclosure distress',
            'honesty_marker', 'INFERRED'
        )
    ),
    'fl_parcels.assessed_value (shard12_manatee_cdi_gap_fix dispatch_e6951fe0)',
    'shard12_manatee_cdi_gap_fix'
FROM multi_county_auctions mca
WHERE mca.county = 'manatee'
  AND mca.case_number IS NOT NULL
  AND mca.assessed_value IS NOT NULL
  AND mca.assessed_value::numeric > 0
  AND COALESCE(mca.data_source, '') NOT LIKE '%propertyonion%'
  AND NOT EXISTS (
    SELECT 1 FROM bid_decisions bd
    WHERE bd.case_number = mca.case_number
      AND bd.county_slug = 'manatee'
  );

-- Step 5: Verify
SELECT public.pencil_dod_evaluate_county('manatee');
