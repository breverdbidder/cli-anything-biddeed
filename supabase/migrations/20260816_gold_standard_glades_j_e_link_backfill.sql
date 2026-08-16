-- GOLD STANDARD glades J/E: E-linkage backfill for the 6th (final blocking) J gap row,
-- flipping J from FAIL (96/102, 94.1%) to PASS (97/102, 95.1%).
--
-- CONTEXT: prior session (dispatch acde83ca-0ef2-4df1-b907-e6ae224b191a, 2026-08-15, see
-- GOLD_STANDARD_SHARD3_GLADES_STLUCIE_UNION_DISPATCH_ACDE83CA_SESSION_REPORT.md) got glades J to
-- 96/102 (94.1%) via the real countywide comps cascade, but left 6 rows genuinely BLANK:
--   (a) 2 rows with no fl_parcels join at all (structural E-linkage gap)
--   (b) 4 rows that join fl_parcels but have n_comps<3 at every tolerance tier
-- This migration resolves ONE of the (a) rows via a real, verifiable parcel lookup. The other (a)
-- row and all 4 (b) rows are confirmed (again, live) to still be genuinely unresolvable this
-- session and are left BLANK per this county's own hard-learned ghost-success lesson.
--
-- (a1) 222025CA000139CAAXMX -- RESOLVED THIS SESSION.
--   property_address = '1659 CRESCENT AVE, LABELLE, FL 33935', parcel_id was NULL.
--   multi_county_auctions already carried backfill_source='fl_parcels_address_match' with
--   backfill_living_area_sqft=2952, backfill_lot_size_sqft=210830 from a prior (never-completed)
--   address-match attempt -- those exact figures (tot_lvg_ar=2952, lnd_sqfoot=210830) match
--   EXACTLY ONE fl_parcels row county-wide (co_no=32): parcel_id='S36422800300000160',
--   phy_addr1='1659 CRESCENT AVE', phy_city='LABELLE', phy_zipcd='33935', dor_uc='001',
--   own_name='VIGIL MAURICIO ALBERTO', sale_prc1=510000 (2024). Exact street-address + structure
--   match, not an inference -- VERIFIED live via direct fl_parcels query before writing.
--   Backfilled multi_county_auctions.parcel_id, then ran the exact same tier-1 real-comps cascade
--   used in run_acde83ca (median/p25/p75 of fl_parcels.sale_prc1, same dor_uc, county-wide,
--   n_comps>=3 required). Tier 1 (living-area 0.7x-1.3x, sold since 2020) fired immediately with
--   a large pool: n=33 comps, p25=339700, med=363000, p75=440000 -- not a thin pool.
--
-- (a2) TD-2024-4-20240808 -- STILL UNRESOLVED, confirmed again live this session, left BLANK.
--   parcel_id='S31-42-30-102-0018-0070' (dash-stripped 'S31423010200180070') has ZERO match in
--   fl_parcels in ANY county (re-confirmed via both exact match and ILIKE '*0180070' wildcard
--   search). property_address='Zinnia Loop LaBelle, FL' (no house number). Enumerated the entire
--   'S314230102...0018...' lot-suffix block in fl_parcels co_no=32: 0010, 0020, 0030, 0040, 0050,
--   0060, 0080, 0090...0220 all exist; 0070 specifically does not -- a genuine single-lot gap in
--   the statewide cadastral extract for this subdivision, not a stripping/format bug. Unlike the
--   (a1) row, multi_county_auctions carries NO backfill_source for this case (never previously
--   address-matched), so there is no independent corroborating signal to disambiguate which real
--   parcel this cert number (193-2022) actually refers to. Left with NO bid_decisions row,
--   BLANK > WRONG, per this county's twice-purged fabrication history.
--
-- (b) TD-2022-6-20240118 (dor_uc=069 agricultural), TD-2024-36/37/33-20260604 (dor_uc=099) --
--   reconfirmed genuinely n_comps<3 at every tier per the prior session; not re-attempted here
--   without new source data (per task scope).
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county('glades') before/after):
--   BEFORE: J deal_complete=96/102 (94.1%), FAIL. E parcel_linked=101/102 (99.0%), PASS.
--   AFTER:  J deal_complete=97/102 (95.1%), PASS. E parcel_linked=102/102 (100.0%), PASS (side
--           effect of the parcel_id backfill). All other letters (A,B,C,D,F,G,H,I) unchanged.
--
-- Honesty check (self-verified, matches prior sessions' methodology):
--   SELECT COUNT(*) total, COUNT(DISTINCT ml_score) distinct_ml,
--     COUNT(DISTINCT (factors->'cma_distressed'->>'value')) distinct_cma_d,
--     COUNT(*) FILTER (WHERE pipeline_version IS NULL) null_pv,
--     COUNT(*) FILTER (WHERE (factors->>'distress_owner')::numeric = ml_score) dup_do
--   FROM bid_decisions WHERE county_slug='glades';
--   ACTUAL (full 97-row table, post-insert): total=97, distinct_ml=77, distinct_cma_d=49,
--   null_pv=0, dup_do=0. No flat-formula / constant-score / duplicate-field fabrication signature.
--
-- Applied live via the Supabase Management API (api.supabase.com/v1/projects/.../database/query,
-- SUPABASE_ACCESS_TOKEN bearer auth) per this repo's established apply_sql_direct.py pattern
-- (psql direct connection is a known-broken path in this environment). SQL below is the exact
-- statement executed live, reproduced here as the migration record for HARD GUARDRAIL #3.

SET statement_timeout = 0;

-- Step 1: backfill parcel_id for the confirmed exact address+living-area+lot-size match.
UPDATE multi_county_auctions
SET parcel_id = 'S36422800300000160'
WHERE county = 'glades' AND case_number = '222025CA000139CAAXMX' AND parcel_id IS NULL;

-- Step 2: run the exact same tiered real-comps cascade + insert shape as
-- glades_j_countywide_comps_v2_run_acde83ca, scoped via NOT EXISTS so it is idempotent and
-- cannot touch any pre-existing bid_decisions row.
WITH targets AS (
    SELECT mca.case_number, mca.parcel_id, mca.property_address, mca.auction_date,
           mca.assessed_value, mca.market_value, mca.opening_bid, mca.auction_type,
           'S36422800300000160' AS stripped
    FROM multi_county_auctions mca
    WHERE mca.county = 'glades' AND mca.case_number = '222025CA000139CAAXMX'
      AND NOT EXISTS (SELECT 1 FROM bid_decisions bd WHERE bd.case_number = mca.case_number)
),
joined AS (
    SELECT t.*, fp.phy_zipcd, fp.dor_uc, fp.tot_lvg_ar, fp.lnd_sqfoot, fp.co_no
    FROM targets t
    JOIN public.fl_parcels fp ON fp.parcel_id = t.stripped
    WHERE fp.dor_uc IS NOT NULL AND fp.co_no IS NOT NULL
),
tiers AS (
    SELECT j.*,
      (SELECT jsonb_build_object('med', percentile_cont(0.5) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'n', count(*))
       FROM public.fl_parcels fp2
       WHERE fp2.co_no = j.co_no AND fp2.dor_uc = j.dor_uc AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2020
         AND j.tot_lvg_ar > 0 AND fp2.tot_lvg_ar BETWEEN j.tot_lvg_ar * 0.7 AND j.tot_lvg_ar * 1.3
      ) AS t1,
      (SELECT jsonb_build_object('med', percentile_cont(0.5) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'n', count(*))
       FROM public.fl_parcels fp2
       WHERE fp2.co_no = j.co_no AND fp2.dor_uc = j.dor_uc AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2018
         AND j.tot_lvg_ar > 0 AND fp2.tot_lvg_ar BETWEEN j.tot_lvg_ar * 0.5 AND j.tot_lvg_ar * 2.0
      ) AS t2,
      (SELECT jsonb_build_object('med', percentile_cont(0.5) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'n', count(*))
       FROM public.fl_parcels fp2
       WHERE fp2.co_no = j.co_no AND fp2.dor_uc = j.dor_uc AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2018
         AND j.lnd_sqfoot > 0 AND fp2.lnd_sqfoot BETWEEN j.lnd_sqfoot * 0.5 AND j.lnd_sqfoot * 2.0
      ) AS t3,
      (SELECT jsonb_build_object('med', percentile_cont(0.5) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'n', count(*))
       FROM public.fl_parcels fp2
       WHERE fp2.co_no = j.co_no AND fp2.dor_uc = j.dor_uc AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2016
         AND j.lnd_sqfoot > 0 AND fp2.lnd_sqfoot BETWEEN j.lnd_sqfoot * 0.2 AND j.lnd_sqfoot * 5.0
      ) AS t4
    FROM joined j
),
picked AS (
    SELECT *,
      CASE
        WHEN (t1->>'n')::int >= 3 THEN 'tier1_living_0.7-1.3x_since2020'
        WHEN (t2->>'n')::int >= 3 THEN 'tier2_living_0.5-2.0x_since2018'
        WHEN (t3->>'n')::int >= 3 THEN 'tier3_land_0.5-2.0x_since2018'
        WHEN (t4->>'n')::int >= 3 THEN 'tier4_land_0.2-5.0x_since2016'
        ELSE NULL
      END AS tier_used,
      COALESCE(
        CASE WHEN (t1->>'n')::int >= 3 THEN t1 END,
        CASE WHEN (t2->>'n')::int >= 3 THEN t2 END,
        CASE WHEN (t3->>'n')::int >= 3 THEN t3 END,
        CASE WHEN (t4->>'n')::int >= 3 THEN t4 END
      ) AS comp
    FROM tiers
),
calc AS (
    SELECT
        case_number, parcel_id, property_address, auction_date, opening_bid, auction_type, tier_used,
        (comp->>'n')::int AS n_comps,
        round((comp->>'p25')::numeric, 2) AS cma_distressed_val,
        round((comp->>'p75')::numeric, 2) AS cma_resale_val,
        GREATEST(COALESCE(assessed_value, 0), COALESCE(market_value, 0), (comp->>'med')::numeric) AS arv,
        ROUND(LEAST(0.85, GREATEST(0.35,
            0.38 + LEAST((comp->>'n')::int, 100) / 100.0 * 0.30 +
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN (1 - LEAST(1, opening_bid / assessed_value)) * 0.15
                 ELSE 0.05 END
        ))::numeric, 4) AS ml_score,
        ROUND((
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN LEAST(0.90, 0.30 + (1 - LEAST(1, opening_bid / assessed_value)) * 0.50)
                 ELSE 0.52 END
        )::numeric, 4) AS distress_owner
    FROM picked
    WHERE tier_used IS NOT NULL
)
INSERT INTO bid_decisions (
    case_number, county_slug, parcel_id, address, auction_date,
    arv, repairs, final_judgment, max_bid, bid_judgment_ratio,
    recommendation, confidence, ml_score, factors, pipeline_version, arv_source
)
SELECT
    case_number, 'glades', parcel_id, property_address, auction_date,
    arv,
    CASE WHEN arv < 80000 THEN 22000 WHEN arv < 150000 THEN 25000 WHEN arv < 300000 THEN 20000 ELSE 15000 END AS repairs,
    opening_bid,
    GREATEST(
        (arv * 0.70)
        - (CASE WHEN arv < 80000 THEN 22000 WHEN arv < 150000 THEN 25000 WHEN arv < 300000 THEN 20000 ELSE 15000 END)
        - 10000
        - LEAST(25000, arv * 0.15),
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
             ELSE 0.30 END,
        'distress_property',
        ROUND((0.40 + CASE WHEN auction_type = 'foreclosure' THEN 0.15 ELSE 0 END)::numeric, 4),
        'distress_owner', distress_owner,
        'cma_distressed', jsonb_build_object(
            'value', cma_distressed_val,
            'note', 'p25 of ' || n_comps || ' real sold comps, county-wide same DOR use code (' || tier_used || ')',
            'honesty_marker', 'INFERRED'
        ),
        'cma_resale', jsonb_build_object(
            'value', cma_resale_val,
            'note', 'p75 of ' || n_comps || ' real sold comps, county-wide same DOR use code (' || tier_used || ')',
            'honesty_marker', 'INFERRED'
        )
    ),
    'glades_j_countywide_comps_v2_run_e_link_backfill',
    'fl_dor_cadastral_assessed_market_or_comp_median'
FROM calc;
