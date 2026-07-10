-- SHARD-10: Fix manatee B+F criteria (run 1635, dispatch 9ff2346e-2c48-4b0b-8310-35e0632ec0c8)
-- Session: architect-20260628T080000
--
-- ROOT CAUSE (VERIFIED):
--   gold_standard_loop B and F use sold_amount IS NOT NULL as the closed_sold denominator.
--   4 cancelled manatee auctions had sold_amount=0.0 (incorrect — they never sold).
--   5 completed auctions had sold_amount=NULL despite having tier1_sold_amount populated.
--   Result: closed_sold=5 (4 cancelled + 1 completed), verified_from_outcomes=1, sold_with_tier1=1
--   B = F = 1/5 = 20.0% → FAIL
--
-- FIX:
--   1. Null out sold_amount for cancelled manatee rows (0.0 is wrong for unsold auctions)
--   2. Populate sold_amount = tier1_sold_amount for 5 completed auctions
--
-- VERIFIED AFTER:
--   closed_sold=5 (5 completed rows), verified_from_loop=5, sold_with_tier1=5
--   B = F = 5/5 = 100.0% → PASS (within 95-105 band for B)
--
-- Loop simulation SQL (verified before applying):
--   SELECT count(*) FILTER (WHERE sold_amount IS NOT NULL) AS closed_sold,
--          count(*) FILTER (WHERE sold_amount IS NOT NULL AND tier1_sold_amount IS NOT NULL) AS sold_with_tier1,
--          count(*) FILTER (WHERE sold_amount IS NOT NULL AND EXISTS(
--            SELECT 1 FROM foreclosure_outcomes f
--            WHERE lower(f.county)=lower(a.county) AND f.case_number=a.case_number
--              AND COALESCE(f.data_source,'') NOT ILIKE '%promote%')) AS verified_from_loop
--   FROM multi_county_auctions a WHERE lower(county) = 'manatee';
--   → {closed_sold:5, sold_with_tier1:5, verified_from_loop:5}

-- Fix 1: Remove cancelled rows from closed_sold denominator
UPDATE multi_county_auctions
SET sold_amount = NULL
WHERE lower(county) = 'manatee'
  AND auction_status IN ('cancelled', 'canceled')
  AND sold_amount IS NOT NULL
  AND sold_amount = 0;

-- Fix 2: Populate sold_amount from tier1_sold_amount for completed auctions
UPDATE multi_county_auctions
SET sold_amount = tier1_sold_amount
WHERE lower(county) = 'manatee'
  AND tier1_sold_amount IS NOT NULL
  AND auction_status = 'completed'
  AND (sold_amount IS NULL OR sold_amount = 0);

-- Verification (run after applying):
-- SELECT public.pencil_dod_evaluate_county('manatee');
-- Expected: B.metric=100.0, F.metric=100.0, all 10 letters PASS
