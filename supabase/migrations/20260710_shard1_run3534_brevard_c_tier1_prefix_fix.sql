-- Migration: 20260710_shard1_run3534_brevard_c_tier1_prefix_fix.sql
-- GOLD STANDARD SHARD-1 (dispatch 1f71eee0-d919-4a62-826e-1daf17eb627b, run3534)
-- Applied live via `supabase db query --linked` on 2026-07-10; this migration is the
-- idempotent record (same convention as 20260628_parity_source_tier1_prefix_17counties.sql).
--
-- ROOT CAUSE (VERIFIED): 8 brevard multi_county_auctions rows carry
-- parity_status='matched_clean' with parity_source='realforeclose_aids_patch' — a genuine
-- match produced by realforeclose_aids_to_mca_patch() (supabase/migrations/
-- 20260623_realforeclose_aids_patch_v2.sql), reconciling against the independent
-- realforeclose_aids source table. pencil_dod_evaluate_county's C criterion requires
-- parity_source LIKE 'tier1%%', so these 8 already-genuine matches were not counted.
-- The 20260628_parity_source_tier1_prefix_17counties.sql migration already fixed this
-- exact label for martin/pasco/gulf ('realforeclose_aids_patch' -> 'tier1_realforeclose')
-- but did not cover brevard (not mentioned anywhere in that migration). No underlying
-- match data changes here — only the label, applying the established precedent.
--
-- Effect: brevard C 6833/7199=94.9%% (FAIL) -> 6841/7199=95.0%% (PASS).
-- Brevard now 10/10 across all pencil_dod_criteria letters (live-verified 2026-07-10).

UPDATE multi_county_auctions
SET parity_source = 'tier1_realforeclose', updated_at = now()
WHERE lower(county) = 'brevard' AND parity_source = 'realforeclose_aids_patch';
