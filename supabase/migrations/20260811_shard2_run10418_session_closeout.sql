-- Gold Standard SHARD-2 session close-out
-- dispatch_id: 8d4cd6c7-e51a-4a0d-a8da-6995f13bad43
-- Issue #18710, loop run 10418, chat_session architect-20260811T0800
-- Counties: miami_dade, gilchrist, highlands, charlotte, taylor
--
-- SCRIPTS SHIPPED (4 fix scripts + 1 blocked doc + this closeout):
--   scripts/shard2_run10418_miami_dade_i_fix.py     — miami_dade I geo+value+parity backfill
--   scripts/shard2_run10418_highlands_cdij_fix.py   — highlands C/D AJAX+litmus, I value/geo, J generator
--   scripts/shard2_run10418_charlotte_cdij_fix.py   — charlotte C/D AJAX+litmus+PA ArcGIS, I, J generator
--   scripts/shard2_run10418_taylor_cd_fix.py        — taylor C/D AJAX+litmus; B/F block documented
--   supabase/migrations/20260811_shard2_run10418_gilchrist_ei_blocked.sql  — gilchrist E/I exhaustion doc
--   .github/workflows/gold-standard-shard2-run10418.yml  — GHA wiring (daily 09:00 UTC)
--
-- STATUS BEFORE THIS SESSION (from issue brief, run 10418):
--   miami_dade  : 9/10 (I FAIL  90.0% = 457/508)
--   gilchrist   : 8/10 (E FAIL  78.6% = 11/14, I FAIL 57.1% = 8/14)
--   highlands   : 7/10 (E FAIL  87.3% = 268/307, I FAIL 87.3%, J FAIL 87.9% = 270/307)
--   charlotte   : 6/10 (C FAIL  72.7% = 120/165, D FAIL 73.3%, I FAIL 73.9%, J FAIL 81.8%)
--   taylor      : 6/10 (B FAIL null, C FAIL 45.5% = 5/11, D FAIL 63.6% = 7/11, F FAIL null)
--
-- EXPECTED STATUS AFTER SCRIPTS RUN (scripts execute against live DB at GHA dispatch):
--   miami_dade  : 10/10 — I expected 95%+ (geo/value backfill for ~51 new rows;
--                 parity promotion for court-format case_numbers; zone audit)
--   gilchrist   : 8/10 (unchanged — E/I structurally blocked, documented above)
--   highlands   : 9-10/10 — C/D expected PASS (AJAX harvest + litmus);
--                 I expected 93%+ (value/geo backfill); J expected 95%+ (bid_decisions fill)
--   charlotte   : 9-10/10 — C/D/I expected PASS (AJAX + PA ArcGIS enrichment);
--                 J expected PASS (bid_decisions for ~30 new rows)
--   taylor      : 8/10 — C/D expected PASS (AJAX + litmus + court-format SQL);
--                 B/F remain blocked (taylorclerk.com = no sold amounts in automation,
--                 taylor.realtdm.com = confirmed TEST SANDBOX, not real outcome data)
--
-- HONESTY TAG: UNTESTED — scripts not yet run against live DB (GHA runner dispatches
--   scripts; live DB outputs will be in GHA run logs and the issue comment). The
--   before-state metrics are VERIFIED from the issue brief. The after-state is
--   HYPOTHESIS based on the fix logic; actual results depend on live DB state at
--   execution time.
--
-- WIRING MANDATE COMPLIANCE:
--   GHA workflow gold-standard-shard2-run10418.yml wires all 4 county scripts.
--   Schedule: daily 09:00 UTC (after the 08:00Z fleet wave).
--   Each script is idempotent (NULL-only patches, ON CONFLICT DO NOTHING inserts).

BEGIN;

-- Session close-out checkpoint in gold_standard_campaign
-- Uses UPSERT since the dispatch may or may not have a pre-existing row
-- (row is inserted by the autopilot dispatch function at session launch).
INSERT INTO public.gold_standard_campaign
  (dispatch_id, county_slug, criteria_passed, criteria_total, exit_reason, session_end_at)
SELECT * FROM (VALUES
  ('8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid, 'miami_dade',
   '{"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":false,"J":true}'::jsonb,
   10, 'scripts_shipped', now()),
  ('8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid, 'gilchrist',
   '{"A":true,"B":true,"C":true,"D":true,"E":false,"F":true,"G":true,"H":true,"I":false,"J":true}'::jsonb,
   10, 'blocked_no_write', now()),
  ('8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid, 'highlands',
   '{"A":true,"B":true,"C":false,"D":false,"E":false,"F":true,"G":true,"H":true,"I":false,"J":false}'::jsonb,
   10, 'scripts_shipped', now()),
  ('8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid, 'charlotte',
   '{"A":true,"B":true,"C":false,"D":false,"E":true,"F":true,"G":true,"H":true,"I":false,"J":false}'::jsonb,
   10, 'scripts_shipped', now()),
  ('8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid, 'taylor',
   '{"A":true,"B":false,"C":false,"D":false,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}'::jsonb,
   10, 'scripts_shipped', now())
) AS t(dispatch_id, county_slug, criteria_passed, criteria_total, exit_reason, session_end_at)
ON CONFLICT (dispatch_id, county_slug) DO UPDATE SET
  criteria_passed = EXCLUDED.criteria_passed,
  criteria_total  = EXCLUDED.criteria_total,
  exit_reason     = EXCLUDED.exit_reason,
  session_end_at  = EXCLUDED.session_end_at;

-- Ultraloop audit rows for counties with scripts shipped
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT * FROM (VALUES
  (
    '8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid,
    'fallback',
    'miami_dade',
    'I',
    'Shard-2 run 10418 (2026-08-11): miami_dade I=90.0% (457/508) before session. '
    'shard2_run10418_miami_dade_i_fix.py shipped: geo backfill via FL GIO CO_NO=23 + '
    'Nominatim + county centroid fallback; value backfill (assessed_value from market_value '
    'or opening_bid×0.85); parity promotion for court-format case_numbers; zone linkage audit. '
    'NULL-only patches, never overwrites existing data. Expected: I ≥ 95% post-run.',
    '{"approach": "fl_gio_co23_centroid+nominatim+value_proxy+parity_promotion", '
    '"idempotent": true, "null_only_patches": true, '
    '"prior_fix_ref": "20260809_architect_triage_18472_miami_dade_cd_parity_promotion_APPLIED"}'::jsonb,
    true
  ),
  (
    '8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid,
    'fallback',
    'highlands',
    'C',
    'Shard-2 run 10418 (2026-08-11): highlands C shipped via shard2_run10418_highlands_cdij_fix.py. '
    'AJAX harvest (highlands.realtaxdeed.com + highlands.realforeclose.com) + litmus fallback '
    '(Standing Auth Jun12). Prior script shard8_run6046 used same pattern; new script uses '
    'dispatch_id 8d4cd6c7 and current auction date set.',
    '{"approach": "ajax_harvest+litmus_fallback", "dispatch_id": "8d4cd6c7", '
    '"prior_script_ref": "scripts/shard8_run6046_highlands_cdij_fix.py"}'::jsonb,
    true
  ),
  (
    '8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid,
    'fallback',
    'charlotte',
    'C',
    'Shard-2 run 10418 (2026-08-11): charlotte C/D/I/J post-certification regression fix. '
    'Charlotte was 10/10 certified at 109 auctions (Jul 2026). Now 165 auctions (56 new rows '
    'without parity/zone/J data). shard2_run10418_charlotte_cdij_fix.py ships AJAX harvest '
    '(charlotte.realtaxdeed.com + charlotte.realforeclose.com) + litmus + Charlotte County PA '
    'ArcGIS enrichment (gis.charlottecountyfl.gov) + J-generator.',
    '{"approach": "ajax_harvest+litmus+pa_arcgis+j_generator", '
    '"regression_root_cause": "56_new_rows_since_certification", '
    '"prior_cert_ref": "GOLD_STANDARD_SHARD1_INDIANRIVER_CHARLOTTE_DISPATCH_549B0E98_SESSION_REPORT.md"}'::jsonb,
    true
  ),
  (
    '8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid,
    'fallback',
    'taylor',
    'C',
    'Shard-2 run 10418 (2026-08-11): taylor C/D regression fix. '
    'Aug-06 session (shard3_81959b0f) fixed 1 case (26-042 CA) → C/D=100% at 10 auctions. '
    'Now 11 auctions at C=45.5%, D=63.6% (new case ingested without parity). '
    'shard2_run10418_taylor_cd_fix.py: AJAX harvest (taylor.realtaxdeed.com) + litmus + '
    'court-format parity SQL. B/F remain blocked (taylorclerk.com no automation, '
    'taylor.realtdm.com = confirmed TEST SANDBOX).',
    '{"approach": "ajax_harvest+litmus+court_format_sql", '
    '"bf_blocked": true, "bf_reason": "taylorclerk_no_sold_amounts+realtdm_test_sandbox", '
    '"prior_fix_ref": "20260806_gold_standard_shard3_81959b0f_indianriver_gulf_taylor_columbia_alachua"}'::jsonb,
    true
  ),
  (
    '8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid,
    'fallback',
    'taylor',
    'B',
    'Shard-2 run 10418 (2026-08-11): taylor B FAIL confirmed structural blocker. '
    'taylorclerk.com: no automated sold_amount data path (scheduled announcements only, '
    'no case-number search). taylor.realtdm.com: CONFIRMED TEST SANDBOX (non-production, '
    'zero real auction data). Convergent finding across 3+ firings including '
    'GOLD_STANDARD_SHARD13_TAYLOR_DISPATCH_AB46D459_2ND_FIRING_SESSION_REPORT.md.',
    '{"root_cause": "taylorclerk_no_automation+realtdm_test_sandbox", '
    '"convergent_sessions": 3, "no_write_made": true, "auto_resolved_when": "clerk_publishes_pdf_post_sale"}'::jsonb,
    true
  )
) AS t(dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit x
  WHERE x.dispatch_id = t.dispatch_id AND x.county_slug = t.county_slug AND x.letter = t.letter
);

COMMIT;

-- NEXT-SESSION PRIORITIES (per county):
--
-- miami_dade:
--   If I < 98% after this session: investigate residual rows (parcel_id with alpha chars,
--   PO- prefixed sources, or cases missing all three — geo/value/parcel).
--
-- gilchrist:
--   E/I blocked until Playwright-capable runner or clerk digitizes parcel data.
--   No action needed until tooling changes.
--
-- highlands:
--   If J < 95% post-run: J-generator residual = cases with NULL opening_bid AND
--   NULL assessed_value/market_value (falling back to county default ARV).
--   If E < 90%: parcel linkage gap — needs a session checking highlands clerk
--   for the ~39 unlinked cases (most likely AJAX lookup misses for older dates).
--
-- charlotte:
--   If I < 97% post-run: Charlotte County PA ArcGIS missed some parcels —
--   try address-based lookup or Nominatim fallback for remaining geo gaps.
--
-- taylor:
--   B/F auto-resolve when taylorclerk.com publishes post-sale PDFs for
--   completed auctions. Consider a pg_cron or weekly GHA to check for those PDFs.
