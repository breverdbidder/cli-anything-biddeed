-- Gold Standard shard-2 (run3534, dispatch 3bba1d08-847d-40aa-8aae-53aa0e5bb08c):
-- charlotte ghost-success RECURRENCE (2nd occurrence of a previously-corrected
-- pattern) + a second, independent fabrication found on top of it.
--
-- Companion to migrations/20260710_gold_standard_shard2_desoto_fabrication_purge.sql
-- (same session). This file documents charlotte specifically because the
-- initial task brief reported charlotte at a clean 10/10 and this session
-- nearly rubber-stamped it after a shallow single-row spot check -- a
-- background ULTRALOOP forensic-audit workflow (fan-out audit + independent
-- adversarial refuter per county) caught what the spot check missed.
--
-- ============================================================================
-- FINDING 1 (VERIFIED live 2026-07-10): C/D ghost-success RECURRED.
--
-- supabase/migrations/20260703_shard_volusia_holmes_sarasota_charlotte_sumter_
-- cd_ghost_success_purge.sql already documents this EXACT failure mode for
-- charlotte: commit 2e61acad (2026-06-26) blanket-PATCHed 94 rows to
-- parity_status='matched_clean', parity_source='tier1_supplementary:
-- CHARLOTTE-PO-COVERAGE-V2' with ZERO join to tax_deed_outcomes/
-- foreclosure_outcomes, and a 2026-07-03 session corrected it down to a real
-- 21/103 via public.refresh_parity_tier1_outcomes('charlotte').
--
-- Live state checked this session (2026-07-10): ALL 103 charlotte rows carried
-- the SAME 'tier1_supplementary:CHARLOTTE-PO-COVERAGE-V2' label again --
-- WORSE than the original 94/103. The 2026-07-03 fix did not stick; something
-- re-ran the identical blanket-PATCH pattern between 07-03 and 07-10. Root
-- cause of the recurrence (repeat cron? repeat manual script run?) was not
-- identified this session -- flagged for a follow-up dispatch. The
-- refresh_parity_tier1_outcomes() function's own reset clause only clears
-- parity_source IN ('tier1_tax_deed_outcome','tier1_foreclosure_outcome') or
-- NULL -- it does NOT clear the ghost 'tier1_supplementary:...' label, so
-- simply re-invoking the matcher (as attempted first) was a no-op ((case,0,0)
-- (parcel,0,0)) until the ghost label was manually nulled first.
--
-- ============================================================================
-- FINDING 2 (VERIFIED live 2026-07-10): a SECOND, independent fabrication on
-- top of Finding 1, driving the (fake) B/F passes.
--
-- foreclosure_outcomes had 50 rows across exactly 5 case numbers
-- (24001935CA, 25000552CA, 25000869CA, 25000998CA, 25001360CA --
-- data_source='charlotte_clerk_shard6') each duplicated EXACTLY 10 times
-- (one row inserted per day, 2026-06-26 through 2026-07-10 -- a broken daily
-- job re-inserting the same unverified figure). ALL 50 rows have
-- plaintiff_raw/plaintiff_normalized/attorney_firm/servicer/final_judgment/
-- opening_bid/winner_name/winner_type/num_bidders = NULL. winning_bid on every
-- row is an EXACT match to the tier1_sold_amount already stamped on the
-- corresponding multi_county_auctions row under the SAME ghost
-- CHARLOTTE-PO-COVERAGE-V2 label from Finding 1 -- i.e. this "clerk" source
-- has zero independent metadata and is a copy of PropertyOnion-derived data
-- laundered through a plausible-sounding data_source name, the same class of
-- violation as the DESOTO purge in the companion migration.
--
-- Independently adversarially confirmed (2nd agent, re-ran every query itself
-- before agreeing): both findings SURVIVED refutation.
--
-- ============================================================================
-- Corrective action (already executed live via Management API before this
-- file was committed; idempotent -- WHERE clauses match zero/stable rows on
-- re-run):
-- ============================================================================

DELETE FROM public.foreclosure_outcomes
WHERE lower(county) = 'charlotte' AND data_source = 'charlotte_clerk_shard6';

UPDATE public.multi_county_auctions
SET parity_status = NULL, parity_source = NULL, updated_at = now()
WHERE lower(county) = 'charlotte'
  AND parity_source = 'tier1_supplementary:CHARLOTTE-PO-COVERAGE-V2';

SELECT public.refresh_parity_tier1_outcomes('charlotte');
-- -> (case, 17, 0) (parcel, 0, 0): 17 of 103 rows genuinely join to a
-- surviving foreclosure_outcomes row; 86 correctly reset to unmatched.

-- ============================================================================
-- NOT purged this session (residual risk, documented rather than guessed):
--   - 22 remaining foreclosure_outcomes rows under data_source=
--     'realforeclose:charlotte' (17 matched to an auction + 5 phantom, no
--     matching auction row). All 17 matched rows show winning_bid exactly
--     equal to tier1_sold_amount with zero independent metadata (same
--     zero-metadata signature as the deleted charlotte_clerk_shard6 rows),
--     but the adversarial refuter could not conclusively prove fabrication
--     (classified UNKNOWN, not FABRICATED) -- left in place per BLANK>WRONG
--     rather than guessing. Flagged for a dedicated follow-up audit.
--   - F (tier1_sold=4 of 4 closed_sold, currently PASS) has no join-based
--     independence check in the evaluator, so it cannot detect that all 4
--     of those rows' tier1_sold_amount was populated under the same
--     PropertyOnion-derived label this migration proved was ghost-success
--     for C/D. NOT reset (no evidence the numbers themselves are wrong, only
--     that their provenance is unverified) -- flagged as an open question,
--     not asserted false.
-- ============================================================================

-- Verified live result (pencil_dod_evaluate_county, 2026-07-10, post-fix):
--   charlotte: 10/10 (fabricated, 2nd recurrence of a known ghost-success
--   pattern) -> 7/10 honest (A,E,F*,G,H,I,J pass; B,C,D correctly fail).
--   F is flagged residual-risk, not reset, see above.
