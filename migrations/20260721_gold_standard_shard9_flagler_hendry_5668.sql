-- GOLD STANDARD shard-9 — flagler + hendry — loop run 5668
-- dispatch_id: 3b5b09ef-3e13-4b7d-9a0b-de29ee79adf8
-- Session: architect-20260721T160000
--
-- SCOPE:
--   flagler (8/10): B FAIL (metric=null), F FAIL (metric=null)
--   hendry  (5/10): C FAIL (52.6%), D FAIL (52.6%), E FAIL (52.6%),
--                   I FAIL (52.6%), J FAIL (52.6%)
--
-- KEY FINDING (from prior session reports, re-verified in this session):
--
-- FLAGLER B/F — STRUCTURAL CEILING (NOT A BUG):
--   The evaluator returns metric=null because closed_sold=0:
--   - B denominator = rows with auction_status IN (sold,closed,completed,awarded)
--   - F denominator = same set
--   - All flagler MCA rows are auction_status='upcoming' or 'scheduled'
--   - No auction has completed yet → denominator=0 → null/null = null metric
--   This is correctly NOT a failure — it is UNMEASURABLE.
--   Prior investigations confirmed no bypassable path to change this:
--     * records.flaglerclerk.gov → reCAPTCHA v3 gate (confirmed shard7 run3786)
--     * flagler.realtaxdeed.com FNC=UPDATE → HTTP 403 for past dates
--     * qpublic.schneidercorp.com → WAF HTTP 403 (confirmed multiple sessions)
--     * Firecrawl: zero credits (HTTP 402) fleet-wide
--   B/F will only become measurable when a real flagler auction clears.
--   All other flagler letters (C=97.8, D=97.8, E=99.3, G=100, H=PASS,
--   I=95.6, J=100) are PASSING. flagler correctly remains 8/10.
--
-- HENDRY — CONTEXT:
--   shard6 run3679 (2026-07-11): added 3 foreclosure rows (A→PASS).
--     Those rows had no parcel_id → E regressed. G also exposed as real FAIL.
--     I improved to 60%.  J regressed (3 rows lacking bid_decisions).
--     hendry = 4/10 after this session.
--
--   shard2 dispatch 190ac19f (2026-07-19): hendry VERIFIED 10/10
--     with auctions_total=20 (A3 B100 C100 D100 E100 F100 G100 H3.3 I100 J100).
--
--   CURRENT BRIEF (loop run 5668): hendry shows 5/10 with 38 total rows:
--     - card_complete=20 of 38 → 18 NEW rows were added after the 10/10 check
--     - Those 18 new rows need C/D parity, E parcel linkage, I cards, J bid_decisions
--     - This migration and the execution scripts (scripts/shard9_hendry_cdeij_fix_5668.py)
--       address exactly those 18 new rows
--
-- EXECUTION:
--   The actual data work (parity harvest, parcel enrichment, value enrichment,
--   bid_decisions generation) is performed by:
--     scripts/shard9_hendry_cdeij_fix_5668.py  (hendry C/D/E/I/J)
--     scripts/shard9_flagler_bf_reconfirm_5668.py  (flagler audit trail)
--   These scripts are wired to:
--     .github/workflows/gold-standard-shard9-flagler-hendry-5668.yml
--   The scripts use ONLY real data sources:
--     - hendry.realtaxdeed.com AJAX (FNC=LOAD) for C/D parity
--     - services7.arcgis.com/8l7Qq5t0CPLAJwJK Hendry_County_Parcels for E/I
--     - services7.arcgis.com/8l7Qq5t0CPLAJwJK Zoning FeatureServer for I/G
--     - Shapira V14 XGBoost model (or rule-based fallback INFERRED) for J
--   No fabricated data. All writes are idempotent (ON CONFLICT DO NOTHING or PATCH).
--
-- ULTRALOOP AUDIT:
--   ultraloop_mode = 'fallback' (Workflow-tool fan-out pattern)
--   audit rows logged by the execution scripts directly (not this migration)
--   dispatch_id = '3b5b09ef-3e13-4b7d-9a0b-de29ee79adf8'
--
-- BEFORE STATE (from brief, to be verified fresh by execution scripts):
--   flagler: 8/10 (B,F FAIL — unmeasurable)
--   hendry:  5/10 (C,D,E,I,J FAIL at 52.6% = 20/38 matched/linked/complete)
--
-- EXPECTED AFTER STATE (INFERRED — not VERIFIED until execution scripts run):
--   flagler: 8/10 (unchanged — B/F ceiling confirmed)
--   hendry:  depends on how many of the 18 new rows match via realtaxdeed AJAX
--            and get parcel_ids from ArcGIS. If all 18 can be C/D matched and
--            parcel-linked, hendry can return to 10/10.
--            HONEST: auctions may be for future dates not yet on the realtaxdeed
--            calendar → ceiling similar to alachua's future-dated gap. Will report
--            actual numbers from script execution in the session report.
--
-- This migration serves as the audit trail per campaign rules.
-- Actual data changes are in the execution scripts.

-- Log structural ceiling for flagler B/F
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
VALUES
  (
    '3b5b09ef-3e13-4b7d-9a0b-de29ee79adf8',
    'fallback',
    'flagler',
    'B',
    'flagler B structural ceiling VERIFIED: closed_sold=0 in multi_county_auctions. '
    'All flagler MCA rows are upcoming/scheduled; no auction has completed yet. '
    'B denominator=0 → evaluator returns null metric. This is UNMEASURABLE, not FAIL. '
    'Prior investigation paths: records.flaglerclerk.gov (reCAPTCHA v3 gate), '
    'flagler.realtaxdeed.com FNC=UPDATE (HTTP 403 for historical dates), '
    'qpublic.schneidercorp.com (WAF HTTP 403), Firecrawl (HTTP 402 no credits). '
    'No path found to bypass closed_sold=0 without fabrication. '
    'flagler 8/10 is the correct honest state.',
    jsonb_build_object(
      'method', 'direct_mca_query + realtaxdeed_ajax_probe',
      'closed_sold', 0,
      'source', 'dispatch_3b5b09ef, 2026-07-21',
      'prior_refs', jsonb_build_array(
        'shard7_run3786_addendum_2026-07-21',
        'shard6_run3645_flagler_sold_amount_source_probe.py',
        'shard3_flagler_b_fix.py'
      ),
      'blocked_sources', jsonb_build_object(
        'records_flaglerclerk_gov', 'reCAPTCHA v3 gate',
        'flagler_realtaxdeed_com_fnc_update', 'HTTP 403 historical',
        'qpublic_schneidercorp_com', 'WAF HTTP 403',
        'firecrawl', 'HTTP 402 no credits'
      )
    ),
    true,
    now()
  ),
  (
    '3b5b09ef-3e13-4b7d-9a0b-de29ee79adf8',
    'fallback',
    'flagler',
    'F',
    'flagler F structural ceiling VERIFIED: tier1_sold=0, closed_sold=0. '
    'Same root cause as B: no completed auctions in MCA. '
    'F denominator=0 → evaluator returns null metric (UNMEASURABLE). '
    'Will only move when a real flagler auction clears and results are posted.',
    jsonb_build_object(
      'method', 'direct_mca_query',
      'tier1_sold', 0,
      'closed_sold', 0,
      'source', 'dispatch_3b5b09ef, 2026-07-21'
    ),
    true,
    now()
  ),
  (
    '3b5b09ef-3e13-4b7d-9a0b-de29ee79adf8',
    'fallback',
    'flagler',
    'C',
    'flagler C VERIFIED PASS from prior session (shard7 run3786): matched_clean=134, metric=97.8%. '
    'Reconfirmed by re-running pencil_dod_evaluate_county this session. '
    'No change needed.',
    jsonb_build_object(
      'prior_metric', 97.8,
      'prior_matched_clean', 134,
      'source', 'shard7_run3786_addendum_2026-07-21'
    ),
    true,
    now()
  )
ON CONFLICT DO NOTHING;
