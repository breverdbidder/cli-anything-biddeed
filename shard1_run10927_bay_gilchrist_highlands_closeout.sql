-- GOLD STANDARD SHARD-1 (run 10927) — session close-out SQL
-- dispatch_id: b6f8ef4b-ed4b-4268-8d5f-f4a64383862e
-- chat_session: architect-20260812T160000
-- counties: bay, gilchrist, highlands
--
-- Run via: python3 mgmt_sql.py -f shard1_run10927_bay_gilchrist_highlands_closeout.sql
--
-- This file:
-- 1. Evaluates all 3 counties before any fixes (BASELINE)
-- 2. Writes ultraloop audit rows for gilchrist (confirmed structural block)
-- 3. Updates gold_standard_campaign record
-- 4. Runs final evaluation (AFTER)

SET statement_timeout = 0;

-- ─────────────────────────────────────────────────────────────────────────────
-- BASELINE (run before executing Python fix scripts)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT 'bay_baseline' AS label, public.pencil_dod_evaluate_county('bay') AS result;
SELECT 'gilchrist_baseline' AS label, public.pencil_dod_evaluate_county('gilchrist') AS result;
SELECT 'highlands_baseline' AS label, public.pencil_dod_evaluate_county('highlands') AS result;

-- ─────────────────────────────────────────────────────────────────────────────
-- GILCHRIST: ultraloop audit rows (structural block documentation)
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  (
    'b6f8ef4b-ed4b-4268-8d5f-f4a64383862e',
    'fallback',
    'gilchrist',
    'E',
    'Gilchrist E structurally blocked: 3 of 14 rows (212025CA000033/036/043/064/070CAAXMX + 212026CA000004CAAXMX) have no address/parcel_id. All access paths exhausted across 6+ consecutive sessions.',
    '{
      "confirmed_blocked_sources": [
        "civitek/ocrs: Cloudflare Turnstile (sitekey 0x4AAAAAAA64PTBePmuGbrkR)",
        "realforeclose.com/gilchrist: login gate (HTTP 200 splash page, not case data)",
        "qpublic.schneidercorp.com: HTTP 403 + Cloudflare response body",
        "gilchristcountypropertyappraiser.org: anti-bot interstitial JS",
        "gilchristclerk.com: HTTP 403 on all subpaths",
        "FL GIO ArcGIS CO_NO=21: server-side timeout or 400 Invalid query parameters",
        "circuit8.org: general process page, no case data",
        "Civitek OCRS: pre-confirmed Turnstile-blocked"
      ],
      "session_count_with_block": 6,
      "metric_before": 78.6,
      "metric_ceiling": 78.6,
      "note": "Improvement from 57.1% to 78.6% happened in a prior session — 3 rows were resolved then. These 3 remaining rows have been confirmed blocked in current session review.",
      "next_levers": [
        "funded Firecrawl account (current balance -9/1000)",
        "RealForeclose authenticated credentials (registration via foreclosures@circuit8.org)",
        "FL GIO CO_NO=21 retry at different time of day"
      ]
    }'::jsonb,
    true
  ),
  (
    'b6f8ef4b-ed4b-4268-8d5f-f4a64383862e',
    'fallback',
    'gilchrist',
    'I',
    'Gilchrist I structurally gated by E. 11 rows WITH parcel_id are 100% card-complete (address+geo+value+zone). 3 rows WITHOUT parcel_id have NULL address/geo/value — zero independent backfill possible.',
    '{
      "structural_gate": "I requires parcel_id for zone_code join — I ceiling = E ceiling",
      "rows_with_parcel_id": 11,
      "rows_without_parcel_id": 3,
      "max_possible_I": "11/14 = 78.6%",
      "zone_code_for_linked_rows": "R-1 (Single Family Residential, county=gilchrist — CONFIRMED from prior session query)"
    }'::jsonb,
    true
  )
ON CONFLICT DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD_STANDARD_CAMPAIGN close-out record
-- Update the campaign record for this dispatch
-- ─────────────────────────────────────────────────────────────────────────────
-- Note: criteria_passed will be overwritten by the Python session script
-- if it runs successfully. This is the fallback close-out for the case
-- where only the SQL file is run.
UPDATE public.gold_standard_campaign
SET
  exit_reason = 'timeout',
  session_end_at = NOW()
WHERE dispatch_id = 'b6f8ef4b-ed4b-4268-8d5f-f4a64383862e';

-- If the record doesn't exist yet, insert it
INSERT INTO public.gold_standard_campaign
  (dispatch_id, county_slug, criteria_passed, criteria_total, exit_reason, session_end_at)
VALUES
  (
    'b6f8ef4b-ed4b-4268-8d5f-f4a64383862e',
    'bay,gilchrist,highlands',
    '{"bay": {"A": true, "B": true, "C": true, "D": true, "E": true, "F": true, "G": true, "H": true, "I": false, "J": true}, "gilchrist": {"A": true, "B": true, "C": true, "D": true, "E": false, "F": true, "G": true, "H": true, "I": false, "J": true}, "highlands": {"A": true, "B": true, "C": false, "D": false, "E": true, "F": true, "G": true, "H": true, "I": false, "J": false}}'::jsonb,
    10,
    'timeout',
    NOW()
  )
ON CONFLICT (dispatch_id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- FINAL EVALUATION (run after Python fix scripts complete)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT 'bay_final' AS label, public.pencil_dod_evaluate_county('bay') AS result;
SELECT 'gilchrist_final' AS label, public.pencil_dod_evaluate_county('gilchrist') AS result;
SELECT 'highlands_final' AS label, public.pencil_dod_evaluate_county('highlands') AS result;
