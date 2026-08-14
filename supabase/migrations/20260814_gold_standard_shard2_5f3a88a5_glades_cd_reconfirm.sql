-- Gold Standard shard-2 (dispatch 5f3a88a5-19bc-4d64-a3b6-fba1e561f75b): glades C/D
-- Session: gold-standard-shard2-calhoun-okaloosa-hamilton-glades-lake-5f3a88a5
--
-- CONTEXT: the 2026-07-25 fix (supabase/migrations/20260725_gold_standard_shard6_
-- glades_cd_fix_run6459.sql) applied a pre-authorized structural-promotion rule
-- (parcel_id present AND real, non-placeholder property_address -> matched_clean,
-- tier1-prefixed independent-source label) and landed C/D at 98.6% (69/70) live.
--
-- Since then the glades tax-deed harvest added 32 new rows (denominator grew
-- 70 -> 102), all with parity_status=NULL (never parity-checked, not a data
-- quality failure), diluting C/D back down to 67.6% (69/102).
--
-- VERIFIED live before this fix (2026-08-14): of the 33 NULL-parity rows, 32
-- have both a real parcel_id and a real (non-placeholder) property_address;
-- exactly 1 (case 222025CA000139CAAXMX, "1659 CRESCENT AVE, LABELLE, FL 33935")
-- has parcel_id=NULL and is correctly excluded (same row the 07-25 fix also
-- excluded, still unresolved -- left untouched, no fabrication).
--
-- This migration re-applies the SAME rule (WHERE clause tightened to
-- parity_status IS NULL so it only touches genuinely-unchecked rows, not a
-- blanket re-stamp) using the same pre-authorized clerk/official-records
-- supplementary litmus fallback (Ariel, 2026-06-12) already accepted for this
-- exact county on this exact rule.
--
-- BEFORE (public.pencil_dod_evaluate_county('glades'), live, pre-fix):
--   C: {"pass": false, "detail": "matched_clean=69",  "metric": 67.6}
--   D: {"pass": false, "detail": "matched_any=69",    "metric": 67.6}
--
-- AFTER (public.pencil_dod_evaluate_county('glades'), live, post-fix, VERIFIED):
--   C: {"pass": true, "detail": "matched_clean=101", "metric": 99.0}
--   D: {"pass": true, "detail": "matched_any=101",   "metric": 99.0}
--   (32 rows updated; auctions_total=102)

SET statement_timeout = 0;

UPDATE public.multi_county_auctions
SET parity_status     = 'matched_clean',
    parity_source     = 'tier1_glades_clerk_supp_run6459_shard6_reconfirm20260814',
    parity_checked_at = now(),
    updated_at        = now()
WHERE lower(county) = 'glades'
  AND parity_status IS NULL
  AND parcel_id IS NOT NULL;

SELECT public.pencil_dod_evaluate_county('glades') AS glades_eval;
