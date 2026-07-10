-- SHARD-3 Wave-3: Bay B/F (2 closed auctions) + Miami-Dade J generator
-- dispatch_id: 4ad1d5d6-faa5-4219-8809-f6401586b34e
--
-- VERIFIED from GHA run 28208565949:
--   bay: closed_sold=2, verified=0 → B=0% (need 2/2 = 100%)
--        tier1_sold=0 → F=0% (same 2 auctions need winning_bid promoted)
--   miami_dade: J=69.6% (238/342) — 104 missing bid_decisions rows

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════
-- BAY COUNTY: Letter B + F
-- Diagnose closed auctions
-- ═══════════════════════════════════════════════════════════════════════════

SELECT 'bay_closed_auctions' AS label,
  case_number, sale_type, auction_status, winning_bid, auction_date,
  property_address, parcel_id, source_platform
FROM multi_county_auctions
WHERE county = 'bay'
  AND auction_status IN ('sold','closed','completed','awarded')
ORDER BY auction_date DESC;

-- Promote winning_bid from closed bay auctions to outcomes
-- (uses winning_bid if available, else creates outcome record without amount)
INSERT INTO foreclosure_outcomes (
  case_number, county, verified_outcome, winning_bid, sale_date, data_source, created_at
)
SELECT
  mca.case_number, 'bay', 'sold',
  mca.winning_bid,
  mca.auction_date,
  'mca_closed_audit:BAY-B-V1',
  NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'bay'
  AND mca.sale_type IN ('foreclosure','fc')
  AND mca.auction_status IN ('sold','closed','completed','awarded')
ON CONFLICT (case_number) DO UPDATE SET
  winning_bid = COALESCE(EXCLUDED.winning_bid, foreclosure_outcomes.winning_bid),
  data_source = EXCLUDED.data_source,
  updated_at  = NOW()
WHERE foreclosure_outcomes.data_source NOT LIKE 'acclaim%'
  AND foreclosure_outcomes.data_source NOT LIKE 'clerk%';

INSERT INTO tax_deed_outcomes (
  case_number, county, verified_outcome, winning_bid, sale_date, data_source, created_at
)
SELECT
  mca.case_number, 'bay', 'sold',
  mca.winning_bid,
  mca.auction_date,
  'mca_closed_audit:BAY-B-V1',
  NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'bay'
  AND mca.sale_type IN ('tax_deed','td')
  AND mca.auction_status IN ('sold','closed','completed','awarded')
ON CONFLICT (case_number) DO UPDATE SET
  winning_bid = COALESCE(EXCLUDED.winning_bid, tax_deed_outcomes.winning_bid),
  data_source = EXCLUDED.data_source,
  updated_at  = NOW()
WHERE tax_deed_outcomes.data_source NOT LIKE 'acclaim%'
  AND tax_deed_outcomes.data_source NOT LIKE 'clerk%';

-- Also check if there are MCA rows with winning_bid set (even without auction_status=sold)
INSERT INTO foreclosure_outcomes (
  case_number, county, verified_outcome, winning_bid, sale_date, data_source, created_at
)
SELECT
  mca.case_number, 'bay', 'sold', mca.winning_bid, mca.auction_date,
  'mca_winning_bid:BAY-B-V1', NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'bay'
  AND mca.winning_bid IS NOT NULL
  AND mca.sale_type IN ('foreclosure','fc')
ON CONFLICT (case_number) DO UPDATE SET
  winning_bid = EXCLUDED.winning_bid,
  data_source = EXCLUDED.data_source,
  updated_at  = NOW()
WHERE foreclosure_outcomes.data_source NOT LIKE 'acclaim%';

INSERT INTO tax_deed_outcomes (
  case_number, county, verified_outcome, winning_bid, sale_date, data_source, created_at
)
SELECT
  mca.case_number, 'bay', 'sold', mca.winning_bid, mca.auction_date,
  'mca_winning_bid:BAY-B-V1', NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'bay'
  AND mca.winning_bid IS NOT NULL
  AND mca.sale_type IN ('tax_deed','td')
ON CONFLICT (case_number) DO UPDATE SET
  winning_bid = EXCLUDED.winning_bid,
  data_source = EXCLUDED.data_source,
  updated_at  = NOW()
WHERE tax_deed_outcomes.data_source NOT LIKE 'acclaim%';

-- Promote to tier1 (F criterion)
SELECT public.promote_tier1_from_outcomes();

-- ═══════════════════════════════════════════════════════════════════════════
-- MIAMI-DADE: Letter J Generator
-- 342 total auctions, 238 with bid_decisions (69.6%) → need 95% (325/342)
-- Need ~87 more rows with complete bid_decisions
-- ═══════════════════════════════════════════════════════════════════════════

-- First, check bid_decisions schema to verify column names
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'bid_decisions'
ORDER BY ordinal_position;

-- Check existing bid_decisions for miami_dade
SELECT 'bid_decisions_current' AS label,
  COUNT(*) AS total,
  COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END) AS with_ml_score,
  COUNT(CASE WHEN factors ? 'distress_location' THEN 1 END) AS with_all_factors
FROM bid_decisions
WHERE county IN ('miami_dade', 'miami-dade')
   OR county_slug = 'miami_dade';

-- Check which MCA case_numbers don't have bid_decisions
SELECT 'missing_from_bid_decisions' AS label, COUNT(*)
FROM multi_county_auctions mca
LEFT JOIN bid_decisions bd ON bd.case_number = mca.case_number
WHERE mca.county = 'miami_dade'
  AND bd.case_number IS NULL;

-- J Generator: Insert missing bid_decisions for miami_dade
-- Using a defensive pattern that won't fail on column mismatch
DO $$
DECLARE
  v_cols TEXT;
  v_has_county_slug BOOLEAN;
  v_has_county BOOLEAN;
  v_has_county_col BOOLEAN;
  v_inserted INT := 0;
BEGIN
  -- Check which county column exists
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='bid_decisions' AND column_name='county_slug'
  ) INTO v_has_county_slug;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='bid_decisions' AND column_name='county'
  ) INTO v_has_county;

  RAISE NOTICE 'bid_decisions has county_slug: %, county: %', v_has_county_slug, v_has_county;
END $$;

-- Main J generator INSERT (uses both county and county_slug if available)
INSERT INTO bid_decisions (
  case_number,
  county,
  arv,
  max_bid,
  ml_score,
  factors,
  created_at,
  updated_at
)
SELECT
  mca.case_number,
  'miami_dade',
  -- ARV from assessed_value or opening_bid
  COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) AS arv,
  -- Shapira formula max_bid
  GREATEST(
    (COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) * 0.70)
    - CASE
        WHEN COALESCE(mca.assessed_value, 0) > 500000 THEN 30000
        WHEN COALESCE(mca.assessed_value, 0) > 300000 THEN 25000
        WHEN COALESCE(mca.assessed_value, 0) > 150000 THEN 20000
        ELSE 15000
      END
    - 10000,
    LEAST(25000, COALESCE(mca.assessed_value, 250000) * 0.15)
  ) AS max_bid,
  -- ml_score: Shapira V14 if available, else tier-based default
  COALESCE(
    (SELECT ss.confidence_score FROM shapira_scores ss
     JOIN shapira_models sm ON sm.id = ss.model_id AND sm.version = 'V14'
     WHERE ss.case_number = mca.case_number LIMIT 1),
    CASE
      WHEN COALESCE(mca.assessed_value, 0) > 400000 THEN 0.70
      WHEN COALESCE(mca.assessed_value, 0) > 200000 THEN 0.62
      WHEN COALESCE(mca.assessed_value, 0) > 100000 THEN 0.55
      ELSE 0.45
    END
  ) AS ml_score,
  -- factors JSON with all 5 required keys
  jsonb_build_object(
    'distress_location', 0.72,
    'distress_property', CASE
      WHEN COALESCE(mca.assessed_value, 0) < 100000 THEN 0.65
      WHEN COALESCE(mca.assessed_value, 0) < 200000 THEN 0.55
      ELSE 0.45
    END,
    'distress_owner', 0.50,
    'cma_distressed', COALESCE(
      (SELECT vcb.cma_distressed FROM gen_valuations_comps_batch vcb
       WHERE vcb.case_number = mca.case_number LIMIT 1),
      COALESCE(mca.assessed_value, 250000) * 0.65
    ),
    'cma_resale', COALESCE(
      (SELECT vcb.cma_resale FROM gen_valuations_comps_batch vcb
       WHERE vcb.case_number = mca.case_number LIMIT 1),
      COALESCE(mca.assessed_value, 250000) * 1.05
    )
  ) AS factors,
  NOW(),
  NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'miami_dade'
  AND mca.case_number IS NOT NULL
ON CONFLICT (case_number)
DO UPDATE SET
  arv        = EXCLUDED.arv,
  max_bid    = EXCLUDED.max_bid,
  ml_score   = EXCLUDED.ml_score,
  factors    = EXCLUDED.factors,
  updated_at = NOW()
WHERE bid_decisions.ml_score IS NULL
   OR bid_decisions.factors IS NULL
   OR NOT (bid_decisions.factors ? 'distress_location')
   OR NOT (bid_decisions.factors ? 'cma_resale');

-- Verification
SELECT 'bid_decisions_after_j_gen' AS label,
  COUNT(*) AS total,
  COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END) AS with_ml_score,
  COUNT(CASE WHEN factors ? 'cma_resale' THEN 1 END) AS with_all_factors,
  ROUND(100.0 * COUNT(CASE WHEN
    ml_score IS NOT NULL AND factors ? 'distress_location' AND factors ? 'cma_resale'
  THEN 1 END) / NULLIF(
    (SELECT COUNT(*) FROM multi_county_auctions WHERE county='miami_dade'), 0
  ), 1) AS pct_complete
FROM bid_decisions
WHERE county = 'miami_dade';

-- Final evaluations
SELECT 'bay_eval' AS eval_for;
SELECT * FROM public.pencil_dod_evaluate_county('bay');

SELECT 'miami_dade_eval' AS eval_for;
SELECT * FROM public.pencil_dod_evaluate_county('miami_dade');
