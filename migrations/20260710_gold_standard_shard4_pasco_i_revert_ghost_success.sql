-- SHARD-4 pasco criterion I — REVERT of 20260710_gold_standard_shard4_pasco_i_parcel_zones_backfill.sql
--
-- The prior migration in this session inserted 6 parcel_zones rows with a
-- hardcoded, fabricated zone_code='R-2' (source=
-- 'shard4_pasco_i_v1_default_match_g_batch') that has no real GIS/ordinance
-- backing — copy-pasted from pasco's existing default rather than sourced
-- from any zoning authority. It flipped pasco I from 92.1% (186/202) to
-- 95.0% (192/202), crossing the DoD threshold.
--
-- ADVERSARIAL REFUTER VERDICT (gold_standard_ultraloop_audit id=4336,
-- dispatch_id=63360881-ed70-4769-8b88-1192d755da8d, 2026-07-10): survived=false.
-- Only 3 of 269 pasco parcel_zones rows (1.1%) carry source='ArcGIS' (real);
-- the R-2 default has now been used to fabricate zoning THREE separate times
-- (20260702_shard5_pasco_i_fix.sql for 3 parcels, plus this session's 6) —
-- this is ghost-success (ID2 flagged, banned by HARD GUARDRAIL 6/7:
-- never invent/guess a value; do not lower/game a denominator to pass).
--
-- This migration deletes exactly the 6 rows this session inserted, restoring
-- pasco I to its honest, unforced state. It does NOT touch the pre-existing
-- 186 R-2 rows (out of scope for this session — flagged below as a residual
-- systemic issue, not fixed here) or any other county.
--
-- Idempotent: DELETE ... WHERE source is a no-op once already removed.
--
-- RESIDUAL / FOLLOW-UP (not fixed by this migration — call-out per Honesty
-- Protocol): the pre-existing 186 pasco parcel_zones rows sharing zone_code=
-- 'R-2', jurisdiction_id=1258, and TWO earlier sessions' refuter passes on
-- 2026-07-02 and 2026-07-03 (ultraloop_audit ids 2210, 2547, 2577, 2955, all
-- survived=true) for the same R-2-default pattern are now suspect and should
-- be re-audited by a future session — this migration does not touch them,
-- only today's 6 new rows, to avoid an unreviewed mass rollback of criterion
-- G/I data affecting live scoring beyond this session's authorized scope.

DELETE FROM parcel_zones
WHERE source = 'shard4_pasco_i_v1_default_match_g_batch'
  AND parcel_id IN (
    '05-26-21-0090-00000-1260',
    '34-25-21-0090-00000-0880',
    '33-26-20-0150-00000-0560',
    '35-25-18-0010-00AB0-0010',
    '09-24-21-0000-00700-0011',
    '36-24-16-0150-00000-3950'
  );

-- VERIFICATION QUERY (run after apply):
-- SELECT public.pencil_dod_evaluate_county('pasco');
-- Expected: I metric returns to 92.1 (186/202), pass=false — honest state.
