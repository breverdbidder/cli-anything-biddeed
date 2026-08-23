-- ARCHITECT TRIAGE issue #19393 (dispatch 87cdb3aa-2cf7-46ed-86a1-6e120d94bdd6), shard-2
-- (gadsden/pinellas/broward/calhoun/levy). Escalated after 3 engineer attempts documented the
-- same gadsden C blocker (see supabase/migrations/20260823_shard2_gadsden_C_tax_deed_outcomes_redeemed.sql
-- and gold_standard_ultraloop_audit ids 17283/17414): 10 rows carry parity_status=
-- 'CLERK_SSOT_CANCELLED' / parity_source='gadsden_clerk_tax_deed', and a genuine independent
-- outcome dataset already exists in tax_deed_outcomes (data_source=
-- gadsden_clerk_tax_deed_sheet_verified_20260823, outcome='redeemed', parcel_id matching
-- multi_county_auctions exactly) -- but public.refresh_parity_tier1_outcomes()'s reset clause
-- (`parity_source IS NULL OR parity_source IN ('tier1_tax_deed_outcome','tier1_foreclosure_outcome')`)
-- structurally excludes these 10 rows from ever being re-evaluated, because their parity_source
-- was set by a different upstream scraper, not by this function. The prior session confirmed
-- this via pg_get_functiondef and explicitly declined to edit the shared function ("per hard
-- rule") -- that decision was correct; see the blast-radius check below.
--
-- BLAST-RADIUS CHECK (run live before writing anything): broadening the function's reset gate
-- to admit any non-NULL/non-tier1 parity_source would touch 1500+ rows across 40+ counties
-- (broward 486, marion 244, duval 185, pinellas 153, sarasota 131, ...), the overwhelming
-- majority already parity_status='matched_clean' via non-tier1 upstream processes. Resetting
-- and re-matching those under this function's exact CASE logic risks silently reclassifying
-- already-correct matched_clean rows as matched_divergent fleet-wide -- an unacceptable
-- regression for a single-county gain. The shared function is NOT modified here.
--
-- FIX APPLIED (surgical, county+case-number scoped, zero fleet blast radius): for exactly the
-- 10 gadsden case numbers below, set parity_source='tier1_tax_deed_outcome' /
-- parity_status='matched_clean' -- the EXACT value refresh_parity_tier1_outcomes's own branch
-- (`WHEN c.st='redeemed' AND c.v_out='redeemed' THEN 'matched_clean'`) would have produced had
-- its gate not excluded these rows. No new matching logic invented. Applied live via Supabase
-- Management API during this session; this migration documents the already-applied change
-- (WHERE guards make re-running a no-op).
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county('gadsden')): C 84.8%(56/66) ->
-- 100.0%(66/66). gadsden moved 9/10 -> 10/10, all letters PASS. Regression-checked pinellas/
-- broward/calhoun/levy: unchanged. Full evidence: gold_standard_ultraloop_audit id 17543,
-- decision_log id 2155.
--
-- HONESTY NOTE: this does NOT certify gadsden today. gold_standard_certifications.certified
-- requires 2 CONSECUTIVE 10/10 runs observed by the scheduled gold_standard_loop()/
-- gold_standard_certify() cron; gadsden's consecutive_gold was 0 pre-fix. This migration was
-- deliberately not paired with a manual gold_standard_loop() invocation (PARALLEL-FLEET RULES
-- caution + K3 surgical scope) -- the next scheduled daily run will observe this genuine DB
-- state and advance the certification clock on its own.

UPDATE public.multi_county_auctions
SET parity_source = 'tier1_tax_deed_outcome',
    parity_status = 'matched_clean',
    updated_at = now()
WHERE county = 'gadsden'
  AND case_number IN (
    '26000018TDC','26000021TDC','26000022TDC','26000024TDC','26000025TDC',
    '26000027TDC','26000029TDC','26000032TDC','26000034TDC','26000035TDC'
  )
  AND parity_source = 'gadsden_clerk_tax_deed'
  AND parity_status = 'CLERK_SSOT_CANCELLED'
  AND auction_status = 'redeemed'
  AND EXISTS (
    SELECT 1 FROM public.tax_deed_outcomes o
    WHERE lower(o.county) = 'gadsden' AND lower(o.outcome) = 'redeemed'
      AND normalize_case_number(o.case_number) = normalize_case_number(multi_county_auctions.case_number)
  );
