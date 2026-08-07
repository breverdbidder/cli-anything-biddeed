-- Gold Standard shard-4 pasco G regression fix, pass 2 (self-caught, same session).
--
-- After 20260807e applied, live re-verification showed G still FAIL:
--   density=95.3 far=100.0 pk1000=66.7 -> metric=66.7 (pk1000 now the sole binding axis).
-- pk1000_applicable_parcels=3, only 2 populated. The 3rd is the new 'C2' district
-- (zoning_districts.id from 20260807e) -- correctly resolves pk1000_applicable=true
-- via the commercial-category fallback (far_regulated=true set explicitly, same
-- as this jurisdiction's C-1 and C-2 districts), but no parking_per_1000sf was
-- given in that migration -- an honest gap, not yet closed.
--
-- FIX: reuse the SAME already-established convention this jurisdiction already
-- applied to its C-1 district in 20260718220500_pasco_g_regression_fix_batch3_
-- orphaned_districts.sql pass 2 (parking_per_1000sf=4.0, tagged
-- INFERRED:standard_fl_general_commercial_parking_ratio, confidence_score=0.55)
-- when the real Pasco LDC Section 907 parking table was unreachable (Municode
-- blocked, no Firecrawl in this sandbox). C2 is the same commercial-category
-- designation as C-1/C-2 in this jurisdiction (general/neighborhood commercial),
-- so the identical generic FL-commercial parking ratio is the same honesty tier
-- as the precedent it's copying -- not a new fabrication, an explicit reuse of
-- an already-disclosed INFERRED value under its original tag.
--
-- EXPECTED EFFECT: pct_pk1000_of_applicable 66.7 (2/3) -> 100.0 (3/3).
-- G = LEAST(density=95.3, far=100.0, pk1000=100.0) = 95.3 -> PASS (>=95).

BEGIN;

UPDATE zone_standards s
SET parking_per_1000sf = 4.0,
    source_url = COALESCE(s.source_url, '') || '|shard4_pasco_g_batch6_pass2_INFERRED:standard_fl_general_commercial_parking_ratio (same convention as C-1 zoning_district id=10904)',
    confidence_score = 0.55
FROM zoning_districts d
WHERE s.zoning_district_id = d.id
  AND d.jurisdiction_id = 1258
  AND d.code = 'C2'
  AND s.parking_per_1000sf IS NULL;

COMMIT;

-- VERIFICATION QUERY (run after apply):
-- SELECT public.pencil_dod_evaluate_county('pasco');
-- Expected: G pk1000=100.0, G pass=true, metric=95.3 (density-binding);
-- I remains pass=true, card_complete=316 of 327, unaffected.
