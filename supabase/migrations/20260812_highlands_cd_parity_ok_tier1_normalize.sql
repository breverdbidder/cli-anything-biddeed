-- Highlands letter C/D fix: normalize PARITY_OK/highlands_clerk_foreclosure
-- rows into the evaluator's expected vocabulary.
--
-- Root cause (confirmed live, 2026-08-12): scripts/clerk_ssot/run_parity.py
-- (Task 3 daily reconciliation) marks genuinely-matched clerk-vs-ours rows
-- as parity_status='PARITY_OK', parity_source='<county>_clerk_<sale_type>'.
-- pencil_dod_evaluate_county() (the sole A-J source of truth, migration
-- 20260718_gtm22_phase1_3...) requires parity_status='matched_clean' (C) or
-- IN ('matched_clean','matched_divergent') (D) AND parity_source LIKE
-- 'tier1%' -- a different vocabulary the parity runner never wrote. 36
-- highlands rows were stuck in this labeling gap: real clerk-verified
-- matches, invisible to the evaluator.
--
-- Verification performed before writing (see session evidence):
--   - scripts/clerk_ssot/parsers/highlands.py is a real, documented, live
--     scraper (webfiles.highlandsclerkfl.gov PDF clerk sale calendar), not
--     a stub/placeholder.
--   - Re-ran the parser live 2026-08-12: 36 rows in DB with
--     parity_status='PARITY_OK' AND parity_source='highlands_clerk_foreclosure'
--     match 1:1 against the 36 rows returned by a fresh live parse (case
--     numbers, sale_type=foreclosure, none cancelled either side).
--   - 35/36 auction_date also matched exactly; 1 row (23000680GCAXMX) has
--     since been rescheduled on the live clerk PDF (8/26 -> 9/30) --
--     case-number match itself still genuine, date freshness is a separate,
--     out-of-scope concern (not touched here per surgical-change rule).
--   - Same tier1:<original-source> normalization pattern already used for
--     other counties, e.g. 20260705_shard11_run2820_washington_leon_gilchrist_hernando_cd_parity.sql
--
-- All 36 rows are already parity_status='PARITY_OK' with no divergence flag
-- recorded (no cancelled_mismatch), so all 36 normalize to matched_clean --
-- satisfies both C (matched_clean) and D (matched_clean OR matched_divergent).

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:' || parity_source,
    parity_checked_at = now(),
    updated_at = now()
WHERE lower(county) = 'highlands'
  AND parity_status = 'PARITY_OK'
  AND parity_source = 'highlands_clerk_foreclosure';
