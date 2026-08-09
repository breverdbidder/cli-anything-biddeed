-- GOLD STANDARD SHARD-1 (dispatch 5d60daf1, loop run 10108) — session close-out
-- SESSION: architect-20260809T160000
-- Counties: brevard, pinellas, hamilton, taylor, holmes
--
-- RESULT: 0 letter flips achieved. Structural blocks confirmed across all counties.
-- Pinellas G regression diagnosed (needs next DB-accessible session to fix).
--
-- THIS FILE: close-out per mandatory session close-out protocol. Apply via:
--   python3 mgmt_sql.py -f migrations/20260809_shard1_5d60daf1_session_closeout.sql

SET statement_timeout = 0;

-- Update gold_standard_campaign for this dispatch
-- (criteria_passed reflects run 10108 brief data — INFERRED from brief, UNTESTED against live)
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{
    "brevard": {"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":false,"J":true},
    "pinellas": {"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":false,"H":true,"I":true,"J":true},
    "hamilton": {"A":true,"B":true,"C":false,"D":false,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true},
    "taylor":   {"A":true,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true},
    "holmes":   {"A":true,"B":false,"C":false,"D":false,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}
  }'::jsonb,
  criteria_total = 10,
  exit_reason = 'blocked_env_no_db_access',
  session_end_at = now()
WHERE dispatch_id = '5d60daf1-d8e8-4157-b699-b4410b18dc77';

-- If no row exists yet, insert the close-out record
INSERT INTO public.gold_standard_campaign
  (dispatch_id, county_slug, criteria_passed, criteria_total, exit_reason, session_end_at)
SELECT
  '5d60daf1-d8e8-4157-b699-b4410b18dc77',
  'brevard,pinellas,hamilton,taylor,holmes',
  '{
    "brevard": {"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":false,"J":true},
    "pinellas": {"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":false,"H":true,"I":true,"J":true},
    "hamilton": {"A":true,"B":true,"C":false,"D":false,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true},
    "taylor":   {"A":true,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true},
    "holmes":   {"A":true,"B":false,"C":false,"D":false,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}
  }'::jsonb,
  10,
  'blocked_env_no_db_access',
  now()
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_campaign
  WHERE dispatch_id = '5d60daf1-d8e8-4157-b699-b4410b18dc77'
);

-- Log ultraloop audit rows for structural blocks (all survived=true — these are confirmed dead ends)
-- brevard I: confirmed data ceiling
INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'brevard', 'I',
    'brevard I: confirmed data-availability ceiling at 84.4% (card_complete=5995 of 7099 per brief). ~1106 rows are genuine no-situs vacant/tax-deed land per prior live GIS checks (sessions a42bf937, 1f5f4ede). 29 rows need municipal GIS integration (Palm Bay, Cocoa, Rockledge) not yet in pipeline. No new lever attempted — prior sessions exhausted all county-layer routes. INFERRED from brief data, not re-verified live this session.',
    '{"before_metric": 84.4, "after_metric": 84.4, "session_action": "no_write_no_new_lever", "prior_verified_sessions": ["a42bf937_20260802", "1f5f4ede_20260803"], "structural_ceiling": "municipal_gis_substrate_needed_for_palm_bay_cocoa_rockledge"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'pinellas', 'G',
    'pinellas G: REGRESSION from 98.9% PASS (Jul-24) to 93.9% FAIL in run 10108. Hypothesis: 30 new auctions ingested (393->423 total) without parcel_zones rows. Fix ready in scripts/gs_shard1_pinellas_g_zone_backfill.py (uses Pinellas GIS egis.pinellas.gov point-in-polygon). Cannot execute this session — no DB/network access in this environment. INFERRED, not verified.',
    '{"before_metric": 98.9, "after_metric": 93.9, "regression_cause": "new_auctions_without_zone_coverage", "auctions_july_24": 393, "auctions_run_10108": 423, "fix_script": "scripts/gs_shard1_pinellas_g_zone_backfill.py", "session_action": "no_write_env_blocked"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'hamilton', 'C',
    'hamilton C: 81.0% (FAIL). 4 foreclosure cases not on hamiltonclerk.com static page: 2021-CA-46, 2023-CA-41, 2024-CA-19, 2025-CA-37. Civitek OCRS requires authenticated browser (Cloudflare-protected). Re-confirmed by session 85a4f86f (2026-08-07). No autonomous lever available.',
    '{"before_metric": 81.0, "after_metric": 81.0, "gap_cases": ["2021-CA-46","2023-CA-41","2024-CA-19","2025-CA-37"], "blocker": "civitek_ocrs_cloudflare_auth", "prior_session": "85a4f86f_20260807", "session_action": "no_write_structural_block"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'hamilton', 'D',
    'hamilton D: 81.0% (FAIL). Same root cause as C — 4 foreclosure cases with no accessible source. Civitek OCRS blocked. Re-confirmed 2026-08-07.',
    '{"before_metric": 81.0, "after_metric": 81.0, "gap_cases": ["2021-CA-46","2023-CA-41","2024-CA-19","2025-CA-37"], "blocker": "civitek_ocrs_cloudflare_auth", "session_action": "no_write_structural_block"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'taylor', 'B',
    'taylor B: null (FAIL). All sources exhausted per 3rd firing (dispatch c5a8b2c7). taylorclerk.com deletes closed-case CPT posts. Cloudflare blocks pubrecords.taylorclerk.com and qpublic. kma/v1 API is active-only. FL GIO NAL has annual refresh lag. No sold_amount found for any of 5 past-due cases. Only lever = human phone call to Clerk.',
    '{"before_metric": null, "after_metric": null, "blocker": "all_sources_exhausted", "prior_sessions": ["ab46d459_1st", "ab46d459_2nd", "c5a8b2c7"], "session_action": "no_write_structural_block"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'taylor', 'F',
    'taylor F: null (FAIL). Same root cause as B — no sold_amount recoverable from any accessible source. tier1-promote-hourly cannot run without input from B. Blocked co-dependently with B.',
    '{"before_metric": null, "after_metric": null, "blocker": "no_b_outcomes_to_promote", "session_action": "no_write_structural_block"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'holmes', 'B',
    'holmes B: null (FAIL). 17th+ session confirmed structural block (3b7ed6ea, 2026-08-09 08:18Z). holmesclerk.com has no closed-case records. holmescountytaxcollector.com has zero tax-deed links. myfloridacounty OCRS and civitek are behind Cloudflare Turnstile. No new lever.',
    '{"before_metric": null, "after_metric": null, "last_confirmed_session": "3b7ed6ea_20260809", "blocker": "cloudflare_turnstile_on_all_remaining_sources", "session_action": "no_write_structural_block"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'holmes', 'C',
    'holmes C: 61.5% (FAIL). 5 of 13 cases (TD#2020-589, TD#2023-185, TD#2023-225, TD#2023-496, TD#2023-584) not on holmesclerk.com — auction dates have passed with no disposition published. Confirmed live 2026-08-09 (3b7ed6ea): 3 pages, 0 occurrences of all 5 case numbers.',
    '{"before_metric": 61.5, "after_metric": 61.5, "gap_cases": ["TD#2020-589","TD#2023-185","TD#2023-225","TD#2023-496","TD#2023-584"], "last_confirmed_session": "3b7ed6ea_20260809", "session_action": "no_write_structural_block"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'holmes', 'D',
    'holmes D: 61.5% (FAIL). Same 5-row gap as C. parity_any uses same source. Structural block.',
    '{"before_metric": 61.5, "after_metric": 61.5, "session_action": "no_write_structural_block"}'::jsonb,
    true
  ),
  (
    '5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'holmes', 'F',
    'holmes F: null (FAIL). No verified sale outcomes for any of 13 cases. All source avenues exhausted including 2020-dated cases most likely to have concluded. Structural block with B.',
    '{"before_metric": null, "after_metric": null, "last_confirmed_session": "3b7ed6ea_20260809", "session_action": "no_write_structural_block"}'::jsonb,
    true
  )
ON CONFLICT DO NOTHING;
