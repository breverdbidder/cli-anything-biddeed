-- BRADFORD gold-standard DoD fix session — 2026-07-10
-- Follow-up to prior diagnosis (session: gold_standard_loop C/D v2 wiring verification,
-- decision log .claude/session-logs/2026-07-10-*.yml). Scope: county=bradford only.
--
-- =====================================================================================
-- 1) I — STOP RE-FABRICATION (data fix; code fix shipped separately in
--    scripts/shard4_run472_main_executor.py which now SKIPS bradford in phase_i_property_cards)
-- =====================================================================================
-- Confirmed live (2026-07-10T00:15Z eval + direct SELECT) that all 4 bradford rows still carry
-- assessed_value=145000 / market_value=152250.0 -- the exact fabricated constant previously
-- reverted by 20260703_shard13_..._bradford_i_honesty_fix.sql on 2026-07-03. The source bug
-- (scripts/shard4_run472_main_executor.py phase_i_property_cards, hardcoded
-- county_median={'bradford': 145000, ...}) has run twice daily since (confirmed via
-- gh run list --workflow=gold-standard-shard4-run472.yml, 5/5 recent runs success) and its
-- `WHERE assessed_value IS NULL` guard re-applied the same guess every time the prior fix nulled
-- it out. Same 4 row ids as the 07-03 revert (64f76e07-85ba-4d68-880b-7207f89f9470,
-- 7b7d7ff2-3f4e-4678-b4db-61585b463b3a, fa1d1ae8-7c64-4973-a158-9d7563426011,
-- 2fb112bd-a170-4a35-87a8-4ad003f853ed) -- confirms same rows, same bug, recurring.
--
-- This time the source is ALSO fixed (bradford excluded from county_median loop with an
-- explicit skip + log line) so this null-out should hold going forward. BLANK > WRONG: no
-- real per-parcel assessed_value source was found for bradford this session either (see (2)
-- below -- bradfordappraiser.com was probed but its ArcGIS layer doesn't expose assessed value
-- in the schema check performed); nulling, not re-guessing.
--
-- =====================================================================================
-- 2) E — parcel_id/property_address backfill via Bradford County Property Appraiser ArcGIS
-- =====================================================================================
-- See scripts/shard_bradford_appraiser_lookup.py for the live lookup + row-count proof.
-- This migration file documents the resulting UPDATE only if the script found real matches;
-- otherwise no E-related UPDATE is included here (BLANK > WRONG).

UPDATE multi_county_auctions
SET assessed_value = NULL,
    market_value = NULL,
    updated_at = now()
WHERE county = 'bradford'
  AND assessed_value = 145000
  AND market_value = 152250.0;

-- Verification
SELECT public.pencil_dod_evaluate_county('bradford');
