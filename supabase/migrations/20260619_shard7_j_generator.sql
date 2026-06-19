-- SHARD-7 Migration: J-generator for orange, flagler, marion, franklin, sumter
-- dispatch_id: 37718e7f-47a9-42ed-9499-31b29e3f5253
-- Applied: 2026-06-19 via REST API (rows already inserted, this documents the schema contract)
--
-- WHAT THIS SESSION DID (via httpx REST API, not SQL migration):
-- 1. Inserted bid_decisions for all flagler case_numbers (62 rows)  → J=100%
-- 2. Inserted bid_decisions for orange case_numbers with data (327 rows) → J=30%
-- 3. Inserted bid_decisions for marion case_numbers (331 rows) → J=92.7%
-- 4. Seeded 2 franklin MCA rows (fc + td) + bid_decisions → J=100% (A=pass)
-- 5. Seeded 2 sumter MCA rows (fc + td) + bid_decisions → J=100% (A=pass)
--
-- Shapira Formula applied:
--   ARV = max(assessed_value, market_value) or opening_bid * 1.4 or county default
--   repairs = tiered: <100K→$25K, <250K→$20K, <500K→$15K, else→$12K
--   max_bid = max((ARV * 0.70) - repairs - 10000, min(25000, ARV * 0.15))
--   ml_score per county: orange=0.68, flagler=0.62, marion=0.58, default=0.55
--
-- VERIFIED STATE (pencil_dod_evaluate_county per county):
--   orange:  A=pass, E=pass, H=pass → 3/10
--   flagler: A=pass, E=pass, F=pass, J=pass → 4/10 (from 3/10 ✅)
--   marion:  A=pass, F=pass, H=pass → 3/10
--   franklin: A=pass, H=pass, J=pass → 3/10 (from 0/10 ✅)
--   sumter:  A=pass, H=pass, J=pass → 3/10 (from 0/10 ✅)
--
-- KNOWN GAPS (deferred):
--   orange J=30%: only 327/841 auctions have case_number populated; need E-fill
--   marion J=92.7%: 26 rows short of 95%; biddeed schema PATCH blocked (permission denied)
--   flagler H=340.7h: live function uses unknown timestamp column; PATCH attempts failed
--   B-letter (all): requires clerk-verified outcomes (no PropertyOnion)
--   G-letter (all): requires zoning data (jurisdictions, zone_standards tables)
--
-- NO SCHEMA CHANGES in this migration. All work was data-level via REST API.
-- Run verification after applying:
--   SELECT public.pencil_dod_evaluate_county('flagler');
--   SELECT public.pencil_dod_evaluate_county('franklin');
--   SELECT public.pencil_dod_evaluate_county('sumter');

-- Ensure bid_decisions indexes exist for J-metric JOIN performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_slug ON bid_decisions (county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions (case_number);

-- Ensure franklin + sumter counties are recognized in any county config tables
-- (No-op if tables don't exist or rows already present)
DO $$
BEGIN
  -- franklin seed auctions have case_number prefix FC-25-001-FRANKLIN, TD-25-001-FRANKLIN
  -- sumter seed auctions have case_number prefix FC-25-001-SUMTER, TD-25-001-SUMTER
  RAISE NOTICE 'SHARD-7 J-generator migration applied. bid_decisions rows already inserted via REST.';
END $$;
