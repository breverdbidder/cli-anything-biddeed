-- Gold Standard: lake county, letter C (parity: matched_clean/tier1% >= 95%)
-- Session: 2026-08-09
--
-- BACKGROUND: baseline matched_clean=108/118 (91.5%), need >=112/118 (95%).
-- Grouped lake's scoped rows by parity_status/parity_source:
--   108 matched_clean (tier1%)          -- passing
--     6 matched_divergent (tier1_po_mca_match_lake_20260703)
--     1 mca_only (e_match:...)
--     3 parity_status/parity_source IS NULL  <-- new rows, never parity-checked
--
-- ROOT CAUSE of the 3 NULL rows: case_number IN (2026CA000589, 2025CA000930,
-- 2026CA000425), all created_at=2026-08-07 (created AFTER the prior
-- 2026-08-03 shard-2 parity-recheck session closed). They simply never had a
-- parity pass run against them -- not a data quality problem.
--
-- The 6 matched_divergent + 1 mca_only rows are a KNOWN, already-investigated
-- ceiling documented in supabase/migrations/20260803_gold_standard_shard2_lake_c_status_recheck.sql:
-- their auction dates have passed and Lake Clerk's interactive case search
-- (courtrecords.lakecountyclerk.org/showcaseweb/, equivant ShowCaseWeb v4.2.21,
-- AngularJS SPA) is unreachable via curl/WebFetch in this environment
-- (re-confirmed live this session: static query-string GET returns
-- "Error: No records found" regardless of case number). LEFT UNCHANGED --
-- no independent verification possible this session, no write performed.
--
-- FIX: live-fetched the official Lake County Clerk foreclosure sales
-- calendar (https://foreclosurecalendar.lakecountyclerkfl.gov/default.aspx,
-- plain server-rendered HTML, no auth/JS, verified HTTP 200 live 2026-08-09)
-- and cross-checked all 3 NULL-parity case numbers by exact string match on
-- the raw calendar HTML:
--   2026CA000589: CROSSCOUNTRY MORTGAGE LLC vs CHRISTOPHER GARRY, ET AL -- present, no cancel marker
--   2026CA000425: UNITED SOUTHERN BANK vs POWELL'S CAMPGROUND INC., ET AL -- present, no cancel marker
--   2025CA000930: LAKEVIEW LOAN SERVICING LLC vs UNKNOWN HEIRS OF SCOTT R. MONK, ET AL -- present, no cancel marker
-- All 3 independently corroborated as live/active on the tier1 official
-- Clerk source (not PropertyOnion -- PO is litmus-only per repo HARD
-- GUARDRAILS and was not consulted for this fix).
--
-- EXPECTED IMPACT: matched_clean 108 -> 111 of 118, C metric 91.5% -> 94.1%.
-- NOTE: still short of the 95% (112/118) threshold -- the 7 residual rows
-- remain a genuine, previously-documented ceiling (JS-only Clerk search
-- unreachable in this environment). This fix is real forward progress, not
-- a full close of the gap -- reported plainly per BLANK > WRONG.

SET statement_timeout = 0;

BEGIN;

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_clerk_casenum_crosscheck_lake_20260809',
    parity_checked_at = now(),
    last_parity_check = now(),
    updated_at = now()
WHERE lower(county) = 'lake'
  AND case_number IN ('2026CA000589','2025CA000930','2026CA000425')
  AND parity_status IS NULL;

COMMIT;
