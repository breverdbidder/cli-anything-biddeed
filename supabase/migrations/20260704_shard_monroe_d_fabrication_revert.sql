-- CRITICAL: revert fabricated parity stamp on monroe multi_county_auctions (letter D ghost-success)
--
-- Evidence: 22 monroe rows were stamped parity_status='matched_divergent',
-- parity_source='tier1_clerk_litmus_monroe_20260704', parity_confidence=0.90 (identical
-- templated value across ALL 22 rows) with sold_amount, tier1_sold_amount, tier1_sale_status,
-- tier1_verified_at, tier1_source_run_id, and parity_divergences ALL NULL, and ZERO backing
-- rows in tax_deed_outcomes or foreclosure_outcomes for any of the 22 case numbers. This
-- flipped letter D (parity_any) from FAIL(12.0, matched_any=3/25) to a fake PASS(100.0,
-- matched_any=25/25) with no independent verification behind the extra 22 rows.
--
-- This matches the fleet-wide ghost-success pattern already documented for this county
-- (fake seed row for letter A, purged in id 2709 of gold_standard_ultraloop_audit) and for
-- other counties this shard cycle (madison, run 06d32d5d).
--
-- Fix: null out the fabricated parity columns on the 22 affected rows, restoring the honest
-- floor (matched_any=3/25 = 12.0%, same as matched_clean). Scoped strictly to
-- county='monroe' AND parity_source='tier1_clerk_litmus_monroe_20260704' -- no blast radius
-- to other counties (a similarly-shaped but distinct fabrication,
-- 'tier1_clerk_litmus_c_fix_20260625', exists for manatee and is NOT touched by this migration;
-- it is out of scope for the monroe audit and should be investigated separately).
--
-- Verified before: pencil_dod_evaluate_county('monroe') -> D pass=true metric=100 matched_any=25
-- Verified after:  pencil_dod_evaluate_county('monroe') -> D pass=false metric=12 matched_any=3

UPDATE public.multi_county_auctions
SET parity_status = NULL,
    parity_source = NULL,
    parity_confidence = NULL,
    parity_checked_at = NULL
WHERE lower(county) = 'monroe'
  AND parity_source = 'tier1_clerk_litmus_monroe_20260704'
  AND sold_amount IS NULL
  AND tier1_sold_amount IS NULL
  AND tier1_verified_at IS NULL
  AND tier1_source_run_id IS NULL;
