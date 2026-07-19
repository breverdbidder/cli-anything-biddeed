-- SHARD-14 run5153: martin J + I residual fix
-- dispatch_id: 9d22d82f-cbfe-4f01-a459-b5259d8d08df
-- chat_session: architect-20260719T210000
-- Applied LIVE via REST API (direct psql/pooler auth unavailable in GHA environment).
-- This file is the historical record of what was executed; statements are idempotent.
--
-- CONTEXT:
--   martin is 7/10. Failing: E (91.9%), I (70.3%), J (89.2%).
--   - J: 33/37 — 4 newly-linked auctions from 2026-07-18 session have real parcel_ids/zoning
--     but no bid_decisions yet. J generator run via Python script (shard14_run5153_martin_j_i_fix.py).
--   - I: 26/37 — 8 parcels still lack parcel_zones. Python script attempts live GIS queries
--     (Martin County GIS + Stuart COS_Zoning + Indiantown). Those results tracked here.
--   - E: 91.9% (34/37) — STRUCTURAL CEILING: 3 CAPTCHA-gated Clerk records with zero
--     metadata (23001555CCAXMX, 25001634CCAXMX, 25001632CCAXMX). Cannot script. Confirmed
--     in the 2026-07-18 re-fire addendum: court.martinclerk.com requires image/audio CAPTCHA +
--     anti-forgery token with no bypass. Do not attempt further.
--
-- VERIFICATION PROTOCOL:
--   SELECT public.pencil_dod_evaluate_county('martin');
--   Expected J: pass if deal_complete >= 35/37 (= 94.6% >= 95% threshold needs 36/37)
--   Note: J needs 95% → ceil(37 * 0.95) = 36 rows. If we fill 4 → 37/37 = 100% PASS.
--   Expected I: any improvement toward 95% threshold (need 36/37 = 97.3%)
--
-- SESSION FINDINGS (VERIFIED via pencil_dod_evaluate_county before/after):
--   See session report: GOLD_STANDARD_SHARD14_RUN5153_MARTIN_SESSION_REPORT.md
--   (written at session close)
--
-- HONESTY MARKERS applied per HONESTY PROTOCOL:
--   - VERIFIED: DB queries and GIS calls run this session
--   - INFERRED: zone_code from single-unanimous buffer query result
--   - HYPOTHESIS: ARV from assessed_value or county_default_arv=239480
--   - UNTESTED: code paths not yet executed

SET statement_timeout = 0;

-- ============================================================================
-- FINDING (pre-session analysis, VERIFIED):
-- martin J = 89.2% (33/37). The 4 missing bid_decisions are the newly-linked
-- auctions from 2026-07-18's third-firing session that added parcel_zones
-- for 11 previously-unzoned parcels. The J generator
-- (scripts/shard14_run5153_martin_j_i_fix.py, Phase J) fills them.
-- No manual SQL needed for J — the Python generator handles idempotent upsert.
-- ============================================================================

-- ============================================================================
-- FINDING (pre-session analysis, VERIFIED):
-- martin I = 70.3% (26/37). 8 parcels remain without parcel_zones:
--   - 3 coastal/riverfront unincorporated (zero polygon coverage at 500m)
--   - 4 City of Stuart parcels (zero COS_Zoning coverage at 200m)
--   - 1 Village of Indiantown parcel (no independent GIS found prior sessions)
-- The Python script attempts live GIS at wider buffers (300m/500m for Stuart,
-- trying indiantownfl.gov). Results (if any) are written by the script directly
-- to parcel_zones and zoning_districts via REST API.
--
-- For the 3 coastal gap parcels: confirmed by the 2026-07-18 session that
-- geoweb.martin.fl.us returns zero polygons even at 500m. These are real
-- source gaps in the county's GIS layer (Hobe Sound/Jupiter waterfront areas).
-- Cannot improve without a different data source. Structural gap.
--
-- structural ceiling clarification:
--   I needs 36/37 = 97.3% for PASS (95% threshold).
--   Current: 26/37 = 70.3%.
--   Maximum reachable (if 8 residual parcels resolved + 3 E structural ceiling excluded):
--     The 3 E-ceiling parcels (CAPTCHA-gated, no address) also can never get parcel_zones.
--     So hard ceiling is 34/37 = 91.9% unless the denominator is scoped by sale_type
--     to exclude non-real-property liens.
--   If only the 4 GIS-resolvable parcels are fixed: 30/37 = 81.1%.
--   If all 8 residual are resolved: 34/37 = 91.9%.
--   PASS threshold requires 36/37 = 97.3% — structurally unreachable under current denominator.
-- ============================================================================

-- Track this session in the honesty violations / audit log
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='honesty_violations') THEN
    -- Only insert if the table exists; non-blocking
    INSERT INTO honesty_violations (
      session_id, letter, county, claim, marker, evidence, created_at
    ) VALUES (
      '9d22d82f-cbfe-4f01-a459-b5259d8d08df',
      'J',
      'martin',
      'martin J: 33/37 -> targeting 37/37 via bid_decisions generator for 4 missing auctions',
      'VERIFIED',
      'pencil_dod_evaluate_county(''martin'') run before session: J=89.2% deal_complete=33',
      NOW()
    ) ON CONFLICT DO NOTHING;
  END IF;
END;
$$;

-- ============================================================================
-- VERIFICATION QUERY (copy-paste to confirm after the Python script runs):
-- ============================================================================
-- SELECT public.pencil_dod_evaluate_county('martin');
-- Expected: J->pass=true (100.0, deal_complete=37) if all 4 filled,
--           I->improved if GIS found any of the 8 residual parcels
