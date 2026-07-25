-- Gold Standard shard-2 (loop 6288): baker criterion I enrichment via ArcGIS
-- dispatch_id: 0c5b222d-47d8-4a85-8e3c-3344c9e01394
-- date: 2026-07-25
--
-- BASELINE (from issue brief, loop run 6288):
--   C=40.0 [matched_clean=6]  D=40.0 [matched_any=6]
--   E=40.0 [parcel_linked=6]  I=20.0 [card_complete=3 of 15]
--
-- ROOT CAUSE (documented across 20260724_shard2_baker_c_d_e_i_property_appraiser_purge.sql
-- and 20260724b_shard2_baker_e_property_appraiser_regression_repurge.sql):
--   15 baker rows total. 6 have valid parcel_ids. Of those 6:
--   - 3 are already card_complete (have address + geo + value + zone_code join)
--   - 3 are NOT card_complete: likely missing lat/lng, assessed_value, or
--     parcel_zones zone_code match
--   The other 9 rows (6 case numbers with empty parcel links on RealAuction)
--   are genuinely blocked — Baker County hasn't linked those cases to parcels yet.
--   5 sources confirmed dead-end as of 2026-07-24 (see prior migration for details).
--
-- STRATEGY:
--   1. Baker County ArcGIS FeatureServer:
--      services6.arcgis.com/HSWu3dhzHf7nZfIa/arcgis/rest/services/parcels_web2/FeatureServer/0
--      Confirmed live (HTTP 200) in 20260711_shard8_baker_g_regression_city_delegation_fix.sql.
--      Note: "headless-browser re-query" was noted in that session — plain curl may need a UA header.
--   2. fl_parcels (co_no=12) as fallback — 12,661 rows confirmed (SHARD4_RUN20260710_MANATEE session).
--   3. scripts/baker_i_arcgis_enrichment.py (new, shipped this session) executes live queries.
--   4. .github/workflows/baker-i-arcgis-enrichment.yml (new) wires the script to daily 06:15 UTC.
--
-- MAXIMUM POSSIBLE I IMPROVEMENT (honest bound):
--   Best case: the 3 card-incomplete parcel_id rows get geo+value+zone → I = 6/15 = 40.0%
--   Still FAIL (threshold 95%) — but moves from 20.0% toward 40.0%, which is real progress.
--   The ceiling is 40% until Baker publishes parcel data for the 9 currently-unlinked rows.
--
-- COUNTY EXCEPTION: Baker is NOT flagged in COUNTY EXCEPTIONS (brevard-only exceptions listed).
--   baker.realforeclose.com and baker.realtaxdeed.com are both active RealAuction tenants.
--
-- HARD GUARDRAILS COMPLIANCE:
--   - No fabricated lat/lng (county centroid defaults banned per prior migrations).
--   - No invented assessed_value (must come from ArcGIS JV or fl_parcels jv).
--   - No invented zone_code (must come from ArcGIS Zoning field).
--   - If ArcGIS returns no feature for a parcel_id, the row stays unchanged — honest gap.
--   - FAIL-LOUD: the script raises if parsed > 0 and inserted = 0.
--
-- WIRING MANDATE compliance:
--   baker_i_arcgis_enrichment.py is wired to baker-i-arcgis-enrichment.yml (daily 06:15Z).
--   The workflow runs baker_i_arcgis_enrichment.py and calls pencil_dod_evaluate_county before+after.
--
-- ULTRALOOP AUDIT:
--   Logged here as UNTESTED (script will be run by the wired GHA workflow).
--   Once the workflow executes, update survived based on actual pencil_dod_evaluate_county output.

SET statement_timeout = 0;

-- Register ultraloop audit row for this session's baker I work
-- honesty_marker = UNTESTED — the script + workflow have been shipped and wired,
-- but the GHA run that proves enrichment is pending (awaits 06:15Z cron or manual dispatch).
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT
  '0c5b222d-47d8-4a85-8e3c-3344c9e01394',
  'fallback',
  'baker',
  'I',
  'Shipped scripts/baker_i_arcgis_enrichment.py + .github/workflows/baker-i-arcgis-enrichment.yml '
  'to enrich baker rows with parcel_id via Baker County ArcGIS FeatureServer (parcels_web2) and '
  'fl_parcels (co_no=12). Targets the 3 card-incomplete rows (of 6 with parcel_id). '
  'Maximum achievable I metric = 40.0% (6/15) — still FAIL, but honest real progress from 20.0%. '
  'The 9 rows without parcel_id remain genuinely blocked (Baker County has not linked them on '
  'RealAuction as of 2026-07-24, 5 independent sources confirmed dead-end).',
  jsonb_build_object(
    'honesty_marker', 'UNTESTED',
    'note', 'Script + workflow shipped and wired (daily 06:15Z). Survival determination pending first GHA execution.',
    'sources', jsonb_build_array(
      'Baker County ArcGIS FeatureServer (services6.arcgis.com/HSWu3dhzHf7nZfIa/arcgis/rest/services/parcels_web2/FeatureServer/0) — confirmed live per 20260711_shard8_baker_g_regression_city_delegation_fix.sql',
      'fl_parcels co_no=12 — 12,661 rows confirmed per SHARD4_RUN20260710_MANATEE_OKEECHOBEE_BAKER_MADISON_SESSION_REPORT.md',
      'Prior migration 20260724b_shard2_baker_e_property_appraiser_regression_repurge.sql documents 9 structurally-blocked rows'
    ),
    'maximum_achievable_I', '40.0% (6/15 rows have parcel_id; 3 already card_complete; 3 targeted)',
    'blocked_rows', 9,
    'blocked_reason', 'Baker County has not published parcel links for 6 case numbers on RealAuction as of 2026-07-24 (auction_dates 2026-08-13 to 2026-10-15 — future sales, pre-linkage is normal)',
    'wired_to', 'baker-i-arcgis-enrichment.yml daily 06:15Z cron'
  ),
  NULL   -- NULL = outcome not yet determined (pending GHA run)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit
  WHERE dispatch_id = '0c5b222d-47d8-4a85-8e3c-3344c9e01394'
    AND county_slug = 'baker'
    AND letter = 'I'
);
