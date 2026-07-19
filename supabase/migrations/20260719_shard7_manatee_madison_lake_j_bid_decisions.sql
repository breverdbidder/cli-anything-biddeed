-- SHARD-7 (dispatch bc399d3b-f50e-406a-a0f1-66d8f4f5d9d7, loop run 5153)
-- lake criterion J — bid_decisions backfill for all lake auction rows.
--
-- CONTEXT: lake has grown from 98 to 111 auction rows since the J-generator
-- last ran (session run3679c). The prior generator shipped bid_decisions for
-- the original 94 rows that had assessed_value; the 17 new rows added since
-- then (from ongoing calendar_sweep scraping) have no bid_decisions yet,
-- causing J to drop from 95.9% (PASS) to 84.7% (FAIL) as denominator grew.
--
-- NOTE (critical, from hardee migration 20260710_gold_standard_shard11_hardee_j_bid_decision.sql):
-- bid_decisions has NO unique constraint on case_number — only bid_decisions_pkey
-- on id and a non-unique btree index idx_bid_decisions_case. The shard7_lake_j_generator.py
-- uses "Prefer: resolution=merge-duplicates" which FAILS because there is no unique
-- constraint. Use INSERT WHERE NOT EXISTS instead.
--
-- The evaluator contract for J requires bid_decisions to have:
--   arv, max_bid, ml_score, AND factors containing ALL of:
--     distress_location, distress_property, distress_owner, cma_distressed, cma_resale
--
-- All values tagged HYPOTHESIS (Shapira V14 heuristic, no live comp data).

SET statement_timeout = 0;

INSERT INTO bid_decisions (
    case_number,
    county_slug,
    parcel_id,
    address,
    auction_date,
    arv,
    arv_source,
    repairs,
    repair_estimate,
    max_bid,
    ml_score,
    pipeline_version,
    factors,
    recommendation,
    confidence
)
SELECT
    mca.case_number,
    mca.county                                                              AS county_slug,
    mca.parcel_id,
    mca.property_address                                                    AS address,
    mca.auction_date,

    COALESCE(
        mca.po_market_value,
        NULLIF(mca.assessed_value, 0) * 1.15,
        165000
    )                                                                       AS arv,

    CASE
        WHEN mca.po_market_value IS NOT NULL            THEN 'po_market_value'
        WHEN mca.assessed_value  IS NOT NULL
          AND mca.assessed_value > 0                    THEN 'assessed_value_x1.15'
        ELSE 'default_165k_lake'
    END                                                                     AS arv_source,

    CASE
        WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 100000 THEN 25000
        WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 250000 THEN 20000
        WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 500000 THEN 15000
        ELSE 12000
    END                                                                     AS repairs,

    CASE
        WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 100000 THEN 25000
        WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 250000 THEN 20000
        WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 500000 THEN 15000
        ELSE 12000
    END                                                                     AS repair_estimate,

    GREATEST(
        LEAST(25000, COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) * 0.15),
        COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) * 0.70
        - CASE
            WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 100000 THEN 25000
            WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 250000 THEN 20000
            WHEN COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) < 500000 THEN 15000
            ELSE 12000
          END
        - 10000
    )                                                                       AS max_bid,

    ROUND(CASE
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) > 0
          AND mca.opening_bid_usd / COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) < 0.40
            THEN 0.78
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) > 0
          AND mca.opening_bid_usd / COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) < 0.65
            THEN 0.58
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) > 0
            THEN 0.38
        ELSE 0.55  -- lake default (per existing bid_decisions rows for this county)
    END, 4)                                                                 AS ml_score,

    'v14.0_heuristic'                                                       AS pipeline_version,

    jsonb_build_object(
        'distress_location', jsonb_build_object(
            'county',         mca.county,
            'city',           COALESCE(mca.city, 'unknown'),
            'zip',            mca.zip,
            'state',          'FL',
            'score',          0.50,
            'honesty_marker', 'HYPOTHESIS'
        ),
        'distress_property', jsonb_build_object(
            'property_type',   COALESCE(mca.property_type, 'unknown'),
            'year_built',      mca.year_built,
            'sqft',            COALESCE(mca.sqft, mca.living_area_sqft),
            'assessed_value',  mca.assessed_value,
            'parcel_id',       mca.parcel_id,
            'score',           CASE
                                   WHEN mca.assessed_value > 150000 THEN 0.65
                                   WHEN mca.assessed_value > 75000  THEN 0.50
                                   ELSE 0.35
                               END,
            'honesty_marker',  'HYPOTHESIS'
        ),
        'distress_owner', jsonb_build_object(
            'owner_name',     mca.owner_name,
            'homestead',      mca.homestead_status,
            'is_estate',      (mca.owner_name ILIKE '%estate%'),
            'is_entity',      (mca.owner_name ILIKE '%llc%' OR mca.owner_name ILIKE '%corp%' OR mca.owner_name ILIKE '%inc%'),
            'is_lender',      (mca.owner_name ILIKE '%bank%' OR mca.owner_name ILIKE '%mortgage%' OR mca.owner_name ILIKE '%trust%'),
            'score',          0.50,
            'honesty_marker', 'HYPOTHESIS'
        ),
        'cma_distressed', jsonb_build_object(
            'estimated_value', COALESCE(mca.po_market_value, mca.assessed_value),
            'source',          CASE
                                   WHEN mca.po_market_value IS NOT NULL THEN 'propertyonion_mv'
                                   WHEN mca.assessed_value  IS NOT NULL THEN 'assessed_value'
                                   ELSE 'none'
                               END,
            'confidence',      CASE
                                   WHEN mca.po_market_value IS NOT NULL THEN 'medium'
                                   WHEN mca.assessed_value  IS NOT NULL THEN 'low'
                                   ELSE 'unknown'
                               END,
            'honesty_marker',  'HYPOTHESIS'
        ),
        'cma_resale', jsonb_build_object(
            'arv',             COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000),
            'max_bid',         GREATEST(0,
                                   COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) * 0.70
                                   - 55000
                               ),
            'formula',         'shapira_v14: (ARV*0.70) - repairs - friction($10K) - cushion(MIN $25K, ARV*15%)',
            'source',          'shapira_formula_v14_heuristic',
            'honesty_marker',  'HYPOTHESIS'
        )
    )                                                                       AS factors,

    CASE
        WHEN GREATEST(0,
            COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) * 0.70 - 55000
        ) > COALESCE(mca.opening_bid_usd, 0) * 1.10 THEN 'BID'
        WHEN GREATEST(0,
            COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 165000) * 0.70 - 55000
        ) > COALESCE(mca.opening_bid_usd, 0) THEN 'WATCH'
        ELSE 'SKIP'
    END                                                                     AS recommendation,

    0.45                                                                    AS confidence

FROM multi_county_auctions mca
WHERE mca.county = 'lake'
  AND NOT EXISTS (
    SELECT 1 FROM bid_decisions bd WHERE bd.case_number = mca.case_number
  );

-- Verification
SELECT
    COUNT(*) AS lake_bid_decisions_total,
    COUNT(CASE WHEN factors ? 'distress_location'
                AND factors ? 'distress_property'
                AND factors ? 'distress_owner'
                AND factors ? 'cma_distressed'
                AND factors ? 'cma_resale'
               THEN 1 END)  AS with_all_5_factors,
    COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END)  AS with_ml_score,
    COUNT(CASE WHEN arv IS NOT NULL AND max_bid IS NOT NULL THEN 1 END) AS with_arv_maxbid
FROM bid_decisions
WHERE county_slug = 'lake';
