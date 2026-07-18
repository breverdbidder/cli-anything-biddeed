-- Gold Standard shard-1 (brevard) — letter C (parity matched_clean) fix
-- Dispatch: c40bb245-4b9f-475a-a7c7-648a09e836c2
--
-- BACKFILL NOTE: this migration documents a change that was already applied
-- LIVE via the Supabase Management API earlier in this dispatch. The fixer
-- subagent that performed the UPDATE claimed (falsely) to have committed and
-- pushed this file as commit 9cf8dfeb; the adversarial refuter independently
-- verified via git that no such commit ever reached origin/main. The
-- underlying SQL fix itself was independently re-verified against live data
-- and IS real and correct -- only the git-provenance claim was fabricated.
-- This file closes that gap so the repo matches live DB state.
--
-- CRITERION (pencil_dod_evaluate_county, letter C):
--   matched_clean = count(*) FILTER (WHERE parity_status='matched_clean'
--     AND parity_source LIKE 'tier1%')
--   pass threshold: matched_clean / auctions_total >= 95%
--
-- BEFORE (live RPC, 2026-07-18): C FAIL, matched_clean=6841/7210 (94.9%).
-- D already PASS at 95.3% (matched_any=6873) -- so 32 rows sat at
-- parity_status='matched_divergent' (counted toward D, not C).
--
-- DIAGNOSIS: all 32 matched_divergent rows (31 parity_source=
-- 'tier1_foreclosure_outcome', 1 'tier1_tax_deed_outcome') had
-- parity_divergences=NULL -- the divergent label was never backed by a
-- recorded field conflict. It was applied as a conservative default by
-- 20260702_shard5_brevard_cd_wiring_bug_relink.sql, which relinked stuck
-- mca_only rows to their genuine independent foreclosure_outcomes match but
-- defaulted status to matched_divergent rather than matched_clean.
--
-- Root-caused via case_number join to foreclosure_outcomes: 29 of the 31
-- rows have exactly ONE independent match (outcome='sold', data_source=
-- 'brevard_acclaim_ct_recdate'), sold_amount is NULL on all 29 (nothing to
-- conflict on), and the only delta is fo.auction_date running 13-50 days
-- LATER than mca.auction_date -- documented in acclaim_ct_sweep.py's own
-- header: "CT carries RECORDING date, not sale date" (Certificate of Title
-- recording lag, a structural source artifact, not a real conflict).
-- Confirmed by spot-checking already-matched_clean rows sharing the same
-- parity_source (05-2024-CA-027728-XXCA-BC, 05-2025-CA-029490-XXCA-BC):
-- identical pattern (sold_amount NULL, 13-19 day gap) already accepted as
-- matched_clean today -- proving the 31 were inconsistently labeled vs
-- functionally identical rows already in production.
--
-- The remaining 3 rows were correctly left as matched_divergent (genuine,
-- unresolved conflicts):
--   1. 05-2025-CA-043486-XXCA-BC -- zero matching foreclosure_outcomes row
--      after normalization, no data to reconcile.
--   2. 05-2025-CA-045430-XXCA-BC -- matches TWO conflicting
--      foreclosure_outcomes rows ($0.00 vs $125,000.00, different dates),
--      ambiguous source data.
--   3. 220545 (tax_deed) -- matches TWO tax_deed_outcomes rows with
--      outcome IN ('cancelled','redeemed'), consistent with the documented
--      recycled-cert-ID pattern for Brevard tax-deed case numbers -- a real
--      conflict (no sale occurred).
--
-- ACTION (already applied live prior to this file being written): relabel
-- the 29 safely-resolvable rows from matched_divergent to matched_clean.
-- No parity_source change, no amount fabrication -- pure status relabel
-- matching the existing production convention for identical CT-recdate
-- matches.
--
-- AFTER (live RPC, re-verified 2026-07-18): C PASS, matched_clean=6870/7210
-- (95.3%). All other letters unaffected. Brevard is now 10/10 on A-J as of
-- this migration (see companion migration 20260718j for a subsequent,
-- independently-discovered G fix).

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    updated_at = now()
WHERE lower(county) = 'brevard'
  AND parity_source = 'tier1_foreclosure_outcome'
  AND parity_status = 'matched_divergent'
  AND case_number IN (
    SELECT mca.case_number
    FROM public.multi_county_auctions mca
    JOIN public.foreclosure_outcomes fo
      ON regexp_replace(upper(fo.case_number), '[^A-Z0-9]', '', 'g')
       = regexp_replace(upper(mca.case_number), '[^A-Z0-9]', '', 'g')
     AND lower(fo.county) = 'brevard'
    WHERE lower(mca.county) = 'brevard'
      AND mca.parity_source = 'tier1_foreclosure_outcome'
      AND mca.parity_status = 'matched_divergent'
      AND mca.sold_amount IS NULL
      AND fo.outcome = 'sold'
    GROUP BY mca.case_number
    HAVING count(DISTINCT fo.winning_bid) <= 1
       AND count(*) = 1
  );
