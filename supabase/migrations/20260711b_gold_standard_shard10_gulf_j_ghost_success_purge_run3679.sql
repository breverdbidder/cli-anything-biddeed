-- GOLD STANDARD shard10 (citrus/seminole/lee/gulf), run3679 continuation, 2026-07-11
-- dispatch_id 0a47f574-b17a-4d24-98c7-8ee032514f17
-- Documents a live DB write applied via the Supabase Management API during this session.
-- Idempotent: guarded by exact-value match on the fabricated rows; safe to re-run (no-op if already purged).
--
-- FINDING: gulf letter J was falsely PASSING at 35.7% (5/14 deal_complete) via 5 bid_decisions
-- rows that are byte-identical templated placeholders, not real per-property Shapira/CMA output:
--   arv=109250.00, max_bid=35087.50, ml_score=0.7785, factors.distress_owner='unknown',
--   factors.distress_location='gulf_county' -- IDENTICAL across 5 DIFFERENT case numbers,
--   all with the exact same created_at=2026-06-19 11:12:22.865111+00 (single fabrication event).
-- This is the "ghost success" pattern the campaign has repeatedly had to purge elsewhere
-- (see prior *_ghost_success_purge.sql / *_fabrication_purge.sql migrations). Left in place,
-- it risks surfacing a fabricated $35,087.50 max-bid recommendation for a real Gulf County
-- auction. Verified live before/after via pencil_dod_evaluate_county('gulf'):
--   BEFORE: J deal_complete=5, metric=35.7 (false PASS-contributing rows)
--   AFTER:  J deal_complete=0, metric=0.0  (honest baseline; correct until a real generator runs)
-- Logged to gold_standard_ultraloop_audit id=5294 (survived=true -- this IS the refutation).

DELETE FROM bid_decisions
WHERE case_number IN (
  '232019CA000060CAAXMX','232024CA000042CAAXMX','232024CA000072CAAXMX',
  '232024CC000157CCAXMX','232025CA000037CAAXMX'
)
  AND created_at = '2026-06-19 11:12:22.865111+00'
  AND arv = 109250.00
  AND max_bid = 35087.50;

-- ============================================================
-- NOTE: no other live-data writes were applied this session (run3679 continuation).
-- citrus and seminole were confirmed already at 10/10 PASS (shipped by the earlier
-- run3679 wave today, commits 5730f17a / 7542b46a) -- no action taken, no duplicate work.
--
-- lee E-letter (17-row gap, 4 with real addresses) and gulf E-letter (3 case numbers,
-- no address on file) were investigated via a 14-agent research+adversarial-verify
-- workflow (real Property Appraiser / Clerk of Court / ArcGIS lookups). ZERO fixes were
-- applied: 6 of 7 targets were genuine "not found" (real access dead-ends, correctly not
-- guessed), and the 1 "found" candidate (lee 20-CA-005572 -> parcel_id 21452513000000150,
-- 14067 Danpark Loop) was adversarially REFUTED because the case-number-to-parcel linkage
-- relied on an unverifiable WebSearch summary (WebSearch hallucinated a fact elsewhere in
-- the same investigation) rather than a readable primary source. Per BLANK > WRONG, not
-- applied. All 7 findings logged to gold_standard_ultraloop_audit ids 5374-5380.
-- See SHARD10_RUN3679_CITRUS_SEMINOLE_LEE_GULF_SESSION_REPORT.md for full detail.
-- ============================================================
