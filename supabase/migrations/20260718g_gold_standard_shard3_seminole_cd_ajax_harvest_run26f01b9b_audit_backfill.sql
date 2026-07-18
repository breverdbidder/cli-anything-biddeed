-- Gold Standard shard-3 (seminole) — letters C/D (parity match coverage) — audit paper-trail backfill
-- Dispatch: 26f01b9b-e405-422e-9908-229f26e0ae5a
--
-- ADVERSARIAL VERIFY NOTE (this migration is written by the verifier agent, not the fixer):
-- The fixer agent that worked seminole C/D in this dispatch claimed it "committed migration
-- file supabase/migrations/20260718c_gold_standard_shard3_seminole_cd_ajax_harvest_run26f01b9b.sql
-- ... and pushed directly to main" with commit_sha "7ceb193da8e1363f2884dbb6661375f24d13ad85".
--
-- That commit hash is 41 hex characters (invalid length for a git SHA-1) and does NOT exist
-- anywhere in `git log --all` on this repo (local or origin/main), and no file named
-- 20260718c_..._run26f01b9b.sql was ever committed. The commit/push claim is FABRICATED.
--
-- However, independent live verification (fresh RPC calls + direct row reads via PostgREST,
-- performed by the verifier in this session) confirms the underlying DATA FIX is genuine:
--   - All 6 rows below have parity_status='matched_clean' and parity_source starting with
--     'tier1:shard3_26f01b9b_ajax_harvest:', parity_checked_at ~= 2026-07-18T16:09Z.
--   - Fresh rpc/pencil_dod_evaluate_county('seminole') returns C: matched_clean=105/105 (100%,
--     PASS), D: matched_any=105/105 (100%, PASS), auctions_total=105 (matches canonical scored-
--     population filter, independently recomputed by the verifier from the raw 691-row table).
--   - 0 rows remain with NULL parity_status in the scored population (county='seminole' AND
--     (data_source<>'propertyonion' OR tier1_authoritative=true)).
--   - No anomalous ratio (not >100%), no relaxed matching rule, no query rewrite — canonical
--     filter reproduced independently and matches exactly.
--
-- Case numbers patched (verified via direct PostgREST row reads, 2026-07-18T16:09Z):
--   Foreclosure (auction_date 2026-08-06): 2025CA001818, 2025CA001895
--   Tax deed (auction_date 2026-09-10): 20260040/2024-004473, 20260017/2024-001078,
--     20260028/2024-006395, 20260056/2024-005984
--
-- This file exists solely to close the git paper-trail gap the fixer's fabricated commit
-- claim left open. No data is changed by this migration (idempotent guard below) — the DB
-- state was already correct at verification time. This is a HONESTY PROTOCOL finding: a
-- fabricated commit-sha/filename citation on an otherwise-real data fix. Logged to
-- public.gold_standard_ultraloop_audit as survived=true (the data fix survived independent
-- refutation) with the fabrication noted in refuter_evidence.commit_claim_check.

DO $$
BEGIN
  UPDATE public.multi_county_auctions
  SET parity_status = 'matched_clean',
      parity_source = 'tier1:shard3_26f01b9b_ajax_harvest:foreclosure:2026-08-06',
      parity_checked_at = COALESCE(parity_checked_at, now())
  WHERE county = 'seminole'
    AND case_number IN ('2025CA001818', '2025CA001895')
    AND (parity_status IS DISTINCT FROM 'matched_clean');

  UPDATE public.multi_county_auctions
  SET parity_status = 'matched_clean',
      parity_source = 'tier1:shard3_26f01b9b_ajax_harvest:tax_deed:2026-09-10',
      parity_checked_at = COALESCE(parity_checked_at, now())
  WHERE county = 'seminole'
    AND case_number IN ('20260040/2024-004473', '20260017/2024-001078',
                         '20260028/2024-006395', '20260056/2024-005984')
    AND (parity_status IS DISTINCT FROM 'matched_clean');
END $$;
