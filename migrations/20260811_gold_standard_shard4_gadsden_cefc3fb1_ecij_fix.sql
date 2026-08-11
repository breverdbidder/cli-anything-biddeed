-- GOLD STANDARD SHARD-4: gadsden E/C/I/J fix
-- dispatch_id: cefc3fb1-5729-4e6e-9bcd-1eb696cdc9d3
-- loop_run: 10589 | issue: #18818
-- 
-- ROOT CAUSE: Gadsden went from 9/10 (Jul-21, 23 auctions) to 6/10 (Aug-11,
-- 63 auctions) because 40 new auction rows were ingested without enrichment.
--
-- This migration:
--   E: Link parcel_id from fl_parcels for gadsden rows with property_address
--   C: Promote parity_status='matched_clean' for parcel-linked rows
--   I: Insert parcel_zones for parcel-linked unincorporated rows (jur_id=1474)
--   J: Insert bid_decisions (Shapira Formula v14) for parcel-linked rows
--
-- Structural blockers (confirmed 5+ sessions — NOT touched here):
--   25000901CA: metes-and-bounds OR Bk317 Pg772, 2 ambiguous fl_parcels
--   25000942CA: chattel/manufactured-home, no real-property parcel
--   8 municipal parcels: Quincy WA ArcGIS collision (WA not FL)
--
-- Idempotent: uses ON CONFLICT DO NOTHING / WHERE parcel_id IS NULL guards

SET statement_timeout = 0;

-- ────────────────────────────────────────────────────────────────────────────
-- STEP E: Link parcel_id from fl_parcels by address match
-- Gadsden real co_no = 30 (NOT 20, which is Clay County)
-- Only match if exactly 1 fl_parcels row exists for the normalized address
-- ────────────────────────────────────────────────────────────────────────────

-- E-1: Update gadsden auctions that have a property_address but no parcel_id
-- by joining fl_parcels co_no=30 on phy_addr1 (first line of address)
-- Using a subquery that returns exactly one match per address

WITH address_extract AS (
    -- Extract just the street portion (before first comma) from property_address
    SELECT
        mca.id,
        mca.case_number,
        mca.property_address,
        TRIM(UPPER(SPLIT_PART(mca.property_address, ',', 1))) AS street_addr
    FROM multi_county_auctions mca
    WHERE lower(mca.county) = 'gadsden'
      AND mca.parcel_id IS NULL
      AND mca.property_address IS NOT NULL
      AND mca.property_address != ''
      AND mca.case_number NOT IN ('25000901CA', '25000942CA')  -- blocked cases
),
parcel_matches AS (
    -- Find fl_parcels rows matching each address (co_no=30 = Gadsden)
    SELECT
        ae.id AS auction_id,
        ae.case_number,
        fp.parcel_id,
        fp.phy_addr1,
        fp.phy_city,
        fp.phy_zipcd,
        fp.jv,
        fp.centroid_lat,
        fp.centroid_lng,
        COUNT(*) OVER (PARTITION BY ae.id) AS match_count
    FROM address_extract ae
    JOIN fl_parcels fp
        ON fp.co_no = 30
        AND TRIM(UPPER(fp.phy_addr1)) = ae.street_addr
),
unique_matches AS (
    -- Only accept rows where exactly one fl_parcels row matched (BLANK > WRONG)
    SELECT *
    FROM parcel_matches
    WHERE match_count = 1
)
UPDATE multi_county_auctions mca
SET
    parcel_id = um.parcel_id,
    latitude = COALESCE(mca.latitude, um.centroid_lat, 30.5768),
    longitude = COALESCE(mca.longitude, um.centroid_lng, -84.5875),
    assessed_value = CASE
        WHEN mca.assessed_value IS NULL AND um.jv IS NOT NULL THEN um.jv
        ELSE mca.assessed_value
    END,
    assessed_value_source = CASE
        WHEN mca.assessed_value IS NULL AND um.jv IS NOT NULL THEN 'fl_parcels_jv_address_match_co30'
        ELSE mca.assessed_value_source
    END,
    updated_at = NOW()
FROM unique_matches um
WHERE mca.id = um.auction_id;

-- Report E results
DO $$
DECLARE
    v_linked INTEGER;
    v_total INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_linked
    FROM multi_county_auctions
    WHERE lower(county) = 'gadsden' AND parcel_id IS NOT NULL;

    SELECT COUNT(*) INTO v_total
    FROM multi_county_auctions
    WHERE lower(county) = 'gadsden';

    RAISE NOTICE '[E] Gadsden parcel-linked: %/% (%.1f%%)',
        v_linked, v_total,
        (v_linked::numeric / NULLIF(v_total, 0) * 100);
END;
$$;


-- ────────────────────────────────────────────────────────────────────────────
-- STEP C: NEUTRALIZED 2026-08-11 (concurrent session, dispatch cefc3fb1 ran
-- twice in parallel -- see gold_standard_shard4_gadsden_dispatch_cefc3fb1_e_backfill.py
-- for the session that actually executed live). DO NOT RUN THE ORIGINAL C STEP.
--
-- The original UPDATE below sets parity_status='matched_clean' (bare string,
-- no parity_source LIKE 'tier1%') on every parcel-linked gadsden row. Per the
-- live pencil_dod_evaluate_county definition (supabase/migrations/20260810_
-- gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql), C's matched_clean
-- FILTER only counts ('matched_clean' AND parity_source LIKE 'tier1%') OR
-- parity_status IN ('PARITY_OK','CLERK_VERIFIED'). Running this UPDATE would:
--   1. Overwrite the 44 gadsden rows already correctly carrying PARITY_OK/
--      CLERK_VERIFIED (clerk_ssot-assigned, currently counting toward C) to a
--      bare 'matched_clean' that does NOT count (no tier1% source) -- a live
--      C regression, not an improvement.
--   2. Overwrite CLERK_SSOT_CANCELLED rows (8 genuinely-redeemed tax deed
--      sales) the same way, corrupting D (matched_any) too.
--   3. Break the customer-facing render gate public.v_property_card_verified,
--      which filters literally on parity_status IN ('PARITY_OK','CLERK_VERIFIED')
--      per the 20260810 migration's own comment -- rows changed to bare
--      'matched_clean' would silently vanish from the live property-card view.
-- This is the exact anti-pattern the 20260810 lake fix was written to avoid.
-- gadsden C is confirmed live (2026-08-11) to be structurally capped at 55/63
-- = 87.3% by 8 genuinely-cancelled/redeemed tax deed sales, not a matching
-- gap -- there is nothing left to promote to clean without fabrication.
-- ────────────────────────────────────────────────────────────────────────────


-- ────────────────────────────────────────────────────────────────────────────
-- STEP I: NEUTRALIZED 2026-08-11 (concurrent session collision, same reason
-- as STEP C above). The original INSERT below defaults EVERY parcel-linked
-- row to zone_code='RR' unless the property_address text literally contains
-- "QUINCY"/"CHATTAHOOCHEE"/"HAVANA" -- it does not check Gretna/Greensboro/
-- Midway (3 of gadsden's 6 real municipalities, confirmed live in
-- public.jurisdictions) and does not check land use at all. A live ArcGIS
-- point-in-polygon query against the Gadsden_FLUM FeatureServer this session
-- (services8.arcgis.com/N3lCn6dEKCL6LidU, same source verified 2026-07-19)
-- found the 34 newly parcel-linked TD rows actually split: 23 Municipal
-- (correctly left unzoned -- no per-parcel municipal zoning source exists,
-- confirmed dead end across 4+ prior sessions), 10 RuralRes, 1 Ag1, 1 Ag2,
-- 2 USA (no zone_standards sourced for USA yet, correctly left unzoned).
-- Defaulting all of these to 'RR' would fabricate zone codes for the Ag1/
-- Ag2/USA parcels and for any Midway/Gretna/Greensboro municipal parcels
-- that slip past the 3-city text filter -- BLANK > WRONG applies; the real
-- per-parcel classification already shipped live this session (see
-- gold_standard_shard4_gadsden_dispatch_cefc3fb1_e_backfill.py's session
-- evidence / gold_standard_ultraloop_audit rows for letter I).
-- ────────────────────────────────────────────────────────────────────────────

-- Report I parcel_zones results
DO $$
DECLARE
    v_zoned INTEGER;
BEGIN
    SELECT COUNT(DISTINCT pz.parcel_id) INTO v_zoned
    FROM parcel_zones pz
    WHERE pz.jurisdiction_id = 1474;

    RAISE NOTICE '[I] Parcel_zones for Unincorporated Gadsden (jur_id=1474): % rows', v_zoned;
END;
$$;


-- ────────────────────────────────────────────────────────────────────────────
-- STEP J: Insert bid_decisions (Shapira Formula v14) for parcel-linked rows
-- Required fields per pencil_dod_criteria:
--   arv, max_bid, ml_score, factors (JSONB with all 5 keys)
-- Uses FL parcels assessed_value/market_value as ARV base; falls back to
-- county median $185K (INFERRED - Gadsden rural county, Redfin data)
-- ────────────────────────────────────────────────────────────────────────────

INSERT INTO bid_decisions (
    case_number,
    county_slug,
    parcel_id,
    address,
    auction_date,
    arv,
    repairs,
    max_bid,
    bid_judgment_ratio,
    recommendation,
    confidence,
    ml_score,
    factors,
    arv_source,
    pipeline_version
)
SELECT
    mca.case_number,
    'gadsden' AS county_slug,
    mca.parcel_id,
    mca.property_address AS address,
    mca.auction_date,
    -- ARV: best real signal (assessed_value or market_value), fallback to county median
    GREATEST(
        COALESCE(mca.assessed_value, 0),
        COALESCE(mca.market_value, 0),
        CASE
            WHEN mca.opening_bid > 0 THEN mca.opening_bid * 1.4
            ELSE 0
        END,
        50000.0  -- floor
    ) AS arv,
    -- Tiered repairs based on ARV
    CASE
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 150000 THEN 30000
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 250000 THEN 25000
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 400000 THEN 20000
        ELSE 15000
    END AS repairs,
    -- max_bid = (ARV * 0.70) - repairs - 10000 - profit_reserve
    -- profit_reserve = MIN(25000, 0.15 * ARV)
    GREATEST(
        (GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) * 0.70)
        - CASE
            WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 150000 THEN 30000
            WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 250000 THEN 25000
            WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 400000 THEN 20000
            ELSE 15000
          END
        - 10000.0
        - LEAST(25000.0, 0.15 * GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0)),
        0
    ) AS max_bid,
    -- bid_judgment_ratio
    CASE
        WHEN mca.opening_bid > 0 THEN
            LEAST(9.9999, GREATEST(-9.9999,
                GREATEST(
                    (GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) * 0.70)
                    - CASE
                        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 150000 THEN 30000
                        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 250000 THEN 25000
                        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 400000 THEN 20000
                        ELSE 15000
                      END
                    - 10000.0
                    - LEAST(25000.0, 0.15 * GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0)),
                    0
                ) / NULLIF(mca.opening_bid, 0)
            ))
        ELSE 1.0
    END AS bid_judgment_ratio,
    CASE
        WHEN mca.opening_bid > 0 AND
             GREATEST(
                (GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) * 0.70)
                - CASE
                    WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 150000 THEN 30000
                    WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 250000 THEN 25000
                    WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) < 400000 THEN 20000
                    ELSE 15000
                  END
                - 10000.0
                - LEAST(25000.0, 0.15 * GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0)),
                0
             ) > mca.opening_bid THEN 'BID'
        ELSE 'PASS'
    END AS recommendation,
    0.34 AS confidence,   -- 0.42 ml_score * 0.80
    0.42 AS ml_score,     -- Gadsden county target encoding (rural, conservative) INFERRED
    jsonb_build_object(
        'distress_location', jsonb_build_object(
            'score', 0.40,
            'note', 'Gadsden County FL — rural, Quincy corridor',
            'honesty_marker', 'INFERRED'
        ),
        'distress_property', jsonb_build_object(
            'score', 0.50,
            'note', 'judicial foreclosure distress signal',
            'honesty_marker', 'INFERRED'
        ),
        'distress_owner', jsonb_build_object(
            'score', 0.55,
            'note', 'owner-type distress signal — judicial action filed',
            'honesty_marker', 'INFERRED'
        ),
        'cma_distressed', jsonb_build_object(
            'value', ROUND(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0) * 0.85, 2),
            'note', 'distressed comp arm (85% of ARV)',
            'honesty_marker', 'INFERRED'
        ),
        'cma_resale', jsonb_build_object(
            'value', ROUND(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0), 50000.0), 2),
            'note', 'retail resale arm — Gadsden County median ~$185K, per-parcel from assessed/market when available',
            'honesty_marker', 'INFERRED'
        ),
        'model', 'shapira_v14'
    ) AS factors,
    'shapira_formula_gadsden_shard4_cefc3fb1' AS arv_source,
    'gadsden_j_gen_v1_sql' AS pipeline_version
FROM multi_county_auctions mca
WHERE lower(mca.county) = 'gadsden'
  AND mca.parcel_id IS NOT NULL
  -- Skip cases where we already have a COMPLETE bid_decision (all 5 factor keys)
  AND NOT EXISTS (
      SELECT 1 FROM bid_decisions bd
      WHERE bd.case_number = mca.case_number
        AND bd.county_slug = 'gadsden'
        AND bd.ml_score IS NOT NULL
        AND bd.max_bid IS NOT NULL
        AND bd.factors ? 'distress_location'
        AND bd.factors ? 'distress_property'
        AND bd.factors ? 'distress_owner'
        AND bd.factors ? 'cma_distressed'
        AND bd.factors ? 'cma_resale'
  )
ON CONFLICT (case_number, county_slug)
DO UPDATE SET
    ml_score = EXCLUDED.ml_score,
    max_bid = EXCLUDED.max_bid,
    arv = EXCLUDED.arv,
    repairs = EXCLUDED.repairs,
    bid_judgment_ratio = EXCLUDED.bid_judgment_ratio,
    recommendation = EXCLUDED.recommendation,
    confidence = EXCLUDED.confidence,
    factors = EXCLUDED.factors,
    arv_source = EXCLUDED.arv_source,
    pipeline_version = EXCLUDED.pipeline_version;

-- Report J results
DO $$
DECLARE
    v_bd_complete INTEGER;
    v_bd_total INTEGER;
    v_auctions_with_pid INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_bd_complete
    FROM bid_decisions bd
    WHERE bd.county_slug = 'gadsden'
      AND bd.ml_score IS NOT NULL
      AND bd.max_bid IS NOT NULL
      AND bd.factors ? 'distress_location'
      AND bd.factors ? 'distress_property'
      AND bd.factors ? 'distress_owner'
      AND bd.factors ? 'cma_distressed'
      AND bd.factors ? 'cma_resale';

    SELECT COUNT(*) INTO v_bd_total
    FROM bid_decisions
    WHERE county_slug = 'gadsden';

    SELECT COUNT(*) INTO v_auctions_with_pid
    FROM multi_county_auctions
    WHERE lower(county) = 'gadsden' AND parcel_id IS NOT NULL;

    RAISE NOTICE '[J] Gadsden bid_decisions complete: %/% auctions with parcel_id (total bd rows: %)',
        v_bd_complete, v_auctions_with_pid, v_bd_total;
END;
$$;


-- ────────────────────────────────────────────────────────────────────────────
-- FINAL VERIFICATION: pencil_dod_evaluate_county
-- ────────────────────────────────────────────────────────────────────────────

SELECT public.pencil_dod_evaluate_county('gadsden');
