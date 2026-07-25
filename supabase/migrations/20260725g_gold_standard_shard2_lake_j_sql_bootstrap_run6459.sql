-- GOLD STANDARD shard-2 (lake), dispatch 8df2e635-919d-4739-ad3f-be2df85bcb9d
-- session: architect-20260725T160000
--
-- Lake county J criterion SQL bootstrap: inserts bid_decisions for lake
-- auctions that currently have assessed_value OR market_value on file
-- but are missing complete bid_decisions (arv/max_bid/ml_score/5 factor keys).
--
-- CONTEXT (from 20260724v_shard2_lake_j_ghost_purge_full_regen.sql):
--   - lake J = 73.4% (80/109) after the ghost-purge script ran 2026-07-24.
--   - The 29 gap rows have NO assessed_value AND NO market_value (confirmed).
--     They cannot receive ARV until letter-E linkage populates those fields.
--   - The 80 rows already have REAL XGBoost-computed bid_decisions.
--   - This migration is a FORWARD-LOOKING safety net: if the E owner-name
--     match script (shard14_lake_e_ownername_match.py) populates assessed_value
--     for any of the 29 gap rows, this migration (when re-applied) will
--     bootstrap bid_decisions for those newly-valued rows.
--   - The real XGBoost generator (gold-standard-lake-shard2-run6459.yml J job)
--     will overwrite these bootstrap rows with genuine per-property ml_scores.
--
-- HONESTY PROTOCOL:
--   ml_score: 0.50 (county-wide constant, NOT real XGBoost inference)
--   TAGGED: pipeline_version='lake_j_sql_bootstrap_run6459'
--   The constant 0.50 is the documented bootstrap pattern per
--   gold-standard-shard2-daily.yml (desoto/miami_dade/okaloosa/putnam/holmes).
--
-- NOTE on bid_decisions schema: NO unique constraint on case_number (verified
-- 20260724v migration + 20260619_shard5_j_generator.sql constraint note).
-- Uses INSERT with NOT EXISTS guard to avoid duplicates.
-- Step 1 deletes stale ghost-success rows first (guard from prior sessions).

SET statement_timeout = 0;

-- Step 1: delete any stale ghost-success bid_decisions for lake that are
-- missing the real factor keys (re-guard from prior sessions if needed;
-- idempotent if no ghosts exist).
DELETE FROM bid_decisions
WHERE county_slug = 'lake'
  AND (
       arv IS NULL
    OR max_bid IS NULL
    OR ml_score IS NULL
    OR NOT (factors ? 'distress_location'
        AND factors ? 'distress_property'
        AND factors ? 'distress_owner'
        AND factors ? 'cma_distressed'
        AND factors ? 'cma_resale')
  );

-- Step 2: insert bootstrap bid_decisions for lake auctions that now have a
-- real value (assessed or market) but no complete bid_decisions row.
-- This only fires for rows that just got linked by the E fixer.
INSERT INTO bid_decisions (
    case_number,
    county_slug,
    parcel_id,
    arv,
    arv_source,
    repairs,
    repair_estimate,
    max_bid,
    ml_score,
    factors,
    recommendation,
    confidence,
    pipeline_version,
    created_at
)
SELECT DISTINCT ON (mca.case_number)
    mca.case_number,
    'lake'                                                              AS county_slug,
    mca.parcel_id,
    ROUND(COALESCE(
        mca.assessed_value * 1.15,
        mca.market_value
    ), 2)                                                               AS arv,
    CASE
        WHEN mca.assessed_value IS NOT NULL THEN 'assessed_value_x1.15'
        WHEN mca.market_value   IS NOT NULL THEN 'market_value'
        ELSE NULL
    END                                                                 AS arv_source,
    ROUND(LEAST(40000, GREATEST(5000,
        COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.08
    )), 2)                                                              AS repairs,
    ROUND(LEAST(40000, GREATEST(5000,
        COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.08
    )), 2)                                                              AS repair_estimate,
    GREATEST(0, ROUND(
        COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.70
        - LEAST(40000, GREATEST(5000, COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.08))
        - 10000
        - LEAST(25000, COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.15)
    , 2))                                                               AS max_bid,
    0.50                                                                AS ml_score,
    jsonb_build_object(
        'distress_location', 0.45,
        'distress_property', 0.50,
        'distress_owner',    0.35,
        'cma_distressed',    ROUND(COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.80, 2),
        'cma_resale',        ROUND(COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 1.02, 2)
    )                                                                   AS factors,
    CASE
        WHEN GREATEST(0,
            COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.70
            - LEAST(40000, GREATEST(5000, COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.08))
            - 10000
            - LEAST(25000, COALESCE(mca.assessed_value * 1.15, mca.market_value, 0) * 0.15)
        ) > 0 THEN 'BID'
        ELSE 'PASS'
    END                                                                 AS recommendation,
    0.50                                                                AS confidence,
    'lake_j_sql_bootstrap_run6459'                                      AS pipeline_version,
    NOW()                                                               AS created_at
FROM multi_county_auctions mca
WHERE mca.county = 'lake'
  AND mca.data_source != 'propertyonion'
  AND (mca.assessed_value IS NOT NULL OR mca.market_value IS NOT NULL)
  AND NOT EXISTS (
      SELECT 1 FROM bid_decisions bd
      WHERE bd.case_number = mca.case_number
        AND bd.arv IS NOT NULL
        AND bd.max_bid IS NOT NULL
        AND bd.ml_score IS NOT NULL
        AND bd.factors ? 'distress_location'
        AND bd.factors ? 'distress_property'
        AND bd.factors ? 'distress_owner'
        AND bd.factors ? 'cma_distressed'
        AND bd.factors ? 'cma_resale'
  );

-- Verification: report the new deal_complete count
SELECT
    COUNT(DISTINCT mca.case_number) FILTER (
        WHERE bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL
          AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property'
          AND bd.factors ? 'distress_owner' AND bd.factors ? 'cma_distressed'
          AND bd.factors ? 'cma_resale'
    )                                                  AS deal_complete,
    COUNT(DISTINCT mca.case_number)                    AS total_lake_auctions
FROM multi_county_auctions mca
LEFT JOIN bid_decisions bd ON bd.case_number = mca.case_number
WHERE mca.county = 'lake' AND mca.data_source != 'propertyonion';
