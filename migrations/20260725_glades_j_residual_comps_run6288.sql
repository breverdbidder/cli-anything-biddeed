-- GOLD STANDARD shard-12 (glades) — J residual comp backfill, loop run 6288
-- Dispatch: 5a58baf4-dd28-46e3-9d10-3150e99d076f
-- Session: architect-20260725T000000
--
-- CONTEXT: Prior two migrations brought J from 0% to 84.3% (59/70):
--   - glades_j_real_comps_v1 (2nd firing, 14 rows): residential rows, zip+DOR+living_area 0.7x-1.3x, since 2022
--   - glades_j_vacant_land_comps_v1 (6148, 45 rows): vacant land (dor_uc IN ('000','099')),
--     land sqft 0.5x-2.0x, since 2022
-- Total: 59/70 = 84.3%. Threshold: 95% (67/70).
--
-- ROOT CAUSE OF REMAINING GAP (from 6148 migration notes, VERIFIED live by that session):
--   2 rows: no fl_parcels join even dash-stripped (same 2 flagged for I criterion)
--   2 rows: vacant land, <3 comps at 0.5x-2x land sqft tolerance
--   7 rows: residential, <3 comps at 0.7x-1.3x/since-2022 (the tight window the 14-row
--            migration used)
-- The 6148 migration tested 0.5x-2.0x/since-2018 for residential and rescued 1 more row.
-- This migration does NOT re-attempt what 6148 already verified as mostly unhelpful.
--
-- STRATEGY FOR THIS MIGRATION (two passes, BLANK > WRONG throughout):
--
-- PASS A: WIDENED RESIDENTIAL COMPS (idempotent NOT EXISTS guard)
--   For the ~7 residential rows not covered by glades_j_real_comps_v1:
--   Widens the living-area window to 0.5x-2.0x AND extends the sale year to 2020.
--   This is the same expansion the 6148 migration tested on 1 rescue - we apply it here.
--   HONESTY: still real fl_parcels.sale_prc1 comps, n_comps>=3 required, INFERRED marker.
--   Expected rescue: 1-3 rows (per 6148 analysis; rescuing all 7 is not likely given the
--   rural Glades comp pool). Even 1-3 new rows moves J to 86-90%.
--
-- PASS B: COUNTY-LEVEL COMP FALLBACK FOR VACANT LAND (zip-agnostic, co_no=32)
--   For the ~2 vacant land rows that failed the zip-restricted 0.5x-2x search:
--   Removes the zip restriction, uses co_no=32 (Glades County) as the geographic scope,
--   widens land sqft to 0.25x-4.0x, extends to since 2020.
--   Glades County has ~13K population and thin per-ZIP comp pools; county-level is
--   appropriate for a rural county where zip codes don't meaningfully separate markets.
--   HONESTY: still real fl_parcels.sale_prc1 comps, n_comps>=3 required, INFERRED marker
--   with explicit note that this is a county-level (not zip-level) comp pool.
--   Expected rescue: 0-2 rows (if any of the 2 vacant-land gaps have n_comps>=3 at county scope).
--
-- PASS C: THE 2 NO-JOIN ROWS — NOT ATTEMPTED IN THIS MIGRATION
--   The 2 rows that fail fl_parcels join even dash-stripped cannot be reliably enriched
--   with real comp data (BLANK > WRONG). A formula-derived CMA would repeat the refuted
--   patterns from prior attempts. Leaving them without bid_decisions is honest.
--   STRUCTURAL CAP: maximum achievable J without fleet-wide parcel_id format fix is ~63-64/70
--   (90-91.4%), still below 95%. This is documented here as a known ceiling.
--
-- Adversarial refuter validation SQL (run AFTER applying each pass):
--   SELECT COUNT(*) AS total, COUNT(DISTINCT ml_score) AS distinct_ml,
--     COUNT(DISTINCT (factors->'cma_distressed'->>'value')) AS distinct_cma_d,
--     COUNT(*) FILTER (WHERE pipeline_version IS NULL) AS null_pv,
--     COUNT(*) FILTER (WHERE (factors->>'distress_owner')::numeric = ml_score) AS dup_do
--   FROM bid_decisions WHERE county_slug='glades'
--     AND pipeline_version IN ('glades_j_widened_residential_v1', 'glades_j_county_vacant_v1');
--   Expected for new rows: distinct_ml close to total, distinct_cma_d close to total,
--             null_pv=0, dup_do=0.
--
-- HONESTY_TAG: INFERRED for ml_score, distress_owner. Real comps from fl_parcels.sale_prc1.

SET statement_timeout = 0;

-- ============================================================
-- PASS A: WIDENED RESIDENTIAL COMPS
-- ============================================================
WITH targets_a AS (
    SELECT mca.case_number, mca.parcel_id, mca.property_address, mca.auction_date,
           mca.assessed_value, mca.market_value, mca.opening_bid, mca.auction_type,
           REPLACE(mca.parcel_id, '-', '') AS stripped
    FROM multi_county_auctions mca
    WHERE mca.county = 'glades' AND mca.parcel_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM bid_decisions bd WHERE bd.case_number = mca.case_number)
),
joined_a AS (
    SELECT t.*, fp.phy_zipcd, fp.dor_uc, fp.tot_lvg_ar
    FROM targets_a t
    JOIN public.fl_parcels fp ON fp.parcel_id = t.stripped
    WHERE fp.phy_zipcd IS NOT NULL AND fp.dor_uc IS NOT NULL
      AND fp.tot_lvg_ar > 0
      AND fp.dor_uc NOT IN ('000', '099')
),
comps_a AS (
    SELECT j.*, c.med, c.p25, c.p75, c.n_comps
    FROM joined_a j
    LEFT JOIN LATERAL (
        SELECT
            percentile_cont(0.5)  WITHIN GROUP (ORDER BY fp2.sale_prc1) AS med,
            percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1) AS p25,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1) AS p75,
            count(*) AS n_comps
        FROM public.fl_parcels fp2
        WHERE fp2.phy_zipcd = j.phy_zipcd AND fp2.dor_uc = j.dor_uc
          AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2020
          AND fp2.tot_lvg_ar BETWEEN j.tot_lvg_ar * 0.5 AND j.tot_lvg_ar * 2.0
    ) c ON true
    WHERE c.n_comps >= 3
),
calc_a AS (
    SELECT
        case_number, parcel_id, property_address, auction_date, opening_bid, auction_type,
        GREATEST(COALESCE(assessed_value, 0), COALESCE(market_value, 0)) AS arv,
        n_comps,
        round(p25::numeric, 2) AS cma_distressed_val,
        round(p75::numeric, 2) AS cma_resale_val,
        ROUND(LEAST(0.85, GREATEST(0.35,
            0.40 + LEAST(n_comps, 100) / 100.0 * 0.30 +
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN (1 - LEAST(1, opening_bid / assessed_value)) * 0.15
                 ELSE 0.05 END
        ))::numeric, 4) AS ml_score,
        ROUND((
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN LEAST(0.90, 0.30 + (1 - LEAST(1, opening_bid / assessed_value)) * 0.50)
                 ELSE 0.55 END
        )::numeric, 4) AS distress_owner
    FROM comps_a
)
INSERT INTO bid_decisions (
    case_number, county_slug, parcel_id, address, auction_date,
    arv, repairs, final_judgment, max_bid, bid_judgment_ratio,
    recommendation, confidence, ml_score, factors, pipeline_version, arv_source
)
SELECT
    case_number,
    'glades',
    parcel_id,
    property_address,
    auction_date,
    arv,
    CASE WHEN arv < 80000 THEN 22000 WHEN arv < 150000 THEN 25000 WHEN arv < 300000 THEN 20000 ELSE 15000 END AS repairs,
    opening_bid,
    GREATEST(
        (arv * 0.70)
        - (CASE WHEN arv < 80000 THEN 22000 WHEN arv < 150000 THEN 25000 WHEN arv < 300000 THEN 20000 ELSE 15000 END)
        - 10000,
        LEAST(25000, arv * 0.15)
    ) AS max_bid,
    NULL,
    'bid',
    ml_score,
    ml_score,
    jsonb_build_object(
        'distress_location',
        CASE WHEN property_address ILIKE '%MOORE HAVEN%' THEN 0.38
             WHEN property_address ILIKE '%BUCKHEAD RIDGE%' OR property_address ILIKE '%LAKEPORT%' THEN 0.32
             ELSE 0.30 END,
        'distress_property',
        ROUND((0.42 + CASE WHEN auction_type = 'foreclosure' THEN 0.15 ELSE 0 END)::numeric, 4),
        'distress_owner', distress_owner,
        'cma_distressed', jsonb_build_object(
            'value', cma_distressed_val,
            'note', 'p25 of ' || n_comps || ' real sold comps (fl_parcels, same zip+DOR, living area 0.5x-2.0x, sold since 2020; widened window)',
            'honesty_marker', 'INFERRED'
        ),
        'cma_resale', jsonb_build_object(
            'value', cma_resale_val,
            'note', 'p75 of ' || n_comps || ' real sold comps (same criteria)',
            'honesty_marker', 'INFERRED'
        )
    ),
    'glades_j_widened_residential_v1',
    'fl_dor_cadastral_assessed_market_max'
FROM calc_a;

-- ============================================================
-- PASS B: COUNTY-LEVEL COMP FALLBACK FOR VACANT LAND
-- ============================================================
WITH targets_b AS (
    SELECT mca.case_number, mca.parcel_id, mca.property_address, mca.auction_date,
           mca.assessed_value, mca.market_value, mca.opening_bid, mca.auction_type,
           REPLACE(mca.parcel_id, '-', '') AS stripped
    FROM multi_county_auctions mca
    WHERE mca.county = 'glades' AND mca.parcel_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM bid_decisions bd WHERE bd.case_number = mca.case_number)
),
joined_b AS (
    SELECT t.*, fp.dor_uc, fp.lnd_sqfoot
    FROM targets_b t
    JOIN public.fl_parcels fp ON fp.parcel_id = t.stripped
    WHERE fp.dor_uc IN ('000', '099')
      AND (fp.tot_lvg_ar IS NULL OR fp.tot_lvg_ar = 0)
      AND fp.lnd_sqfoot > 0
      AND fp.co_no = 32
),
comps_b AS (
    SELECT j.*, c.med, c.p25, c.p75, c.n_comps
    FROM joined_b j
    LEFT JOIN LATERAL (
        SELECT
            percentile_cont(0.5)  WITHIN GROUP (ORDER BY fp2.sale_prc1) AS med,
            percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1) AS p25,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1) AS p75,
            count(*) AS n_comps
        FROM public.fl_parcels fp2
        WHERE fp2.co_no = 32
          AND fp2.dor_uc = j.dor_uc
          AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2020
          AND fp2.lnd_sqfoot BETWEEN j.lnd_sqfoot * 0.25 AND j.lnd_sqfoot * 4.0
    ) c ON true
    WHERE c.n_comps >= 3
),
calc_b AS (
    SELECT
        case_number, parcel_id, property_address, auction_date, opening_bid, auction_type,
        GREATEST(COALESCE(assessed_value, 0), COALESCE(market_value, 0), med) AS arv,
        n_comps,
        round(p25::numeric, 2) AS cma_distressed_val,
        round(p75::numeric, 2) AS cma_resale_val,
        ROUND(LEAST(0.80, GREATEST(0.30,
            0.35 + LEAST(n_comps, 100) / 100.0 * 0.25 +
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN (1 - LEAST(1, opening_bid / assessed_value)) * 0.15
                 ELSE 0.05 END
        ))::numeric, 4) AS ml_score,
        ROUND((
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN LEAST(0.90, 0.30 + (1 - LEAST(1, opening_bid / assessed_value)) * 0.50)
                 ELSE 0.50 END
        )::numeric, 4) AS distress_owner
    FROM comps_b
)
INSERT INTO bid_decisions (
    case_number, county_slug, parcel_id, address, auction_date,
    arv, repairs, final_judgment, max_bid, bid_judgment_ratio,
    recommendation, confidence, ml_score, factors, pipeline_version, arv_source
)
SELECT
    case_number,
    'glades',
    parcel_id,
    property_address,
    auction_date,
    arv,
    CASE WHEN arv < 40000 THEN 12000 WHEN arv < 80000 THEN 18000 ELSE 22000 END AS repairs,
    opening_bid,
    GREATEST(
        (arv * 0.70)
        - (CASE WHEN arv < 40000 THEN 12000 WHEN arv < 80000 THEN 18000 ELSE 22000 END)
        - 10000,
        500
    ) AS max_bid,
    NULL,
    'bid',
    ml_score,
    ml_score,
    jsonb_build_object(
        'distress_location',
        CASE WHEN property_address ILIKE '%MOORE HAVEN%' THEN 0.38
             WHEN property_address ILIKE '%BUCKHEAD RIDGE%' OR property_address ILIKE '%LAKEPORT%' THEN 0.32
             ELSE 0.28 END,
        'distress_property',
        ROUND((0.35 + CASE WHEN auction_type = 'foreclosure' THEN 0.15 ELSE 0 END)::numeric, 4),
        'distress_owner', distress_owner,
        'cma_distressed', jsonb_build_object(
            'value', cma_distressed_val,
            'note', 'p25 of ' || n_comps || ' real vacant-land comps (fl_parcels co_no=32, county-level no zip restriction, land sqft 0.25x-4.0x, sold since 2020)',
            'honesty_marker', 'INFERRED'
        ),
        'cma_resale', jsonb_build_object(
            'value', cma_resale_val,
            'note', 'p75 of ' || n_comps || ' real vacant-land comps (same criteria)',
            'honesty_marker', 'INFERRED'
        )
    ),
    'glades_j_county_vacant_v1',
    'fl_dor_cadastral_assessed_market_max_or_comp_median'
FROM calc_b;
