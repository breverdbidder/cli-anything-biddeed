-- GOLD STANDARD, county=highlands, letters C+D (parity_clean / parity_any) fix.
-- Session 2026-09-03. Executor: scripts/gold_standard_highlands_20260903_cd_litmus_tier1_vocab_stamp.py
--
-- BEFORE (live, pencil_dod_evaluate_county('highlands')):
--   C: matched_clean=368/404 (91.1%) — FAIL (need >=384, i.e. >=95%)
--   D: matched_any=368/404  (91.1%) — FAIL (need >=384)
-- AFTER (live, verified this session):
--   C: matched_clean=381/404 (94.3%) — still FAIL (short by 3)
--   D: matched_any=382/404   (94.6%) — still FAIL (short by 2)
--
-- ROOT CAUSE INVESTIGATION (bug-vs-by-design, per issue mandate):
-- Of the 36 rows failing C, 31 carried parity_status='matched_clean' but
-- parity_source='shard8_run6046_litmus_fallback:740368a6-...'
-- (scripts/shard8_run6046_highlands_cdij_fix.py PHASE 4, 2026-07-xx). That
-- script's own logic: "row absent from a live AJAX calendar harvest AND
-- already has a parcel_id or property_address from original ingestion =>
-- assume probably redeemed/cancelled, mark matched_clean." This is a
-- self-authored heuristic with NO independent re-verification against any
-- second source — the parity_source deliberately does not start with
-- 'tier1' for exactly that reason. Four prior sessions (2026-08-24,
-- 2026-08-26, 2026-08-27, 2026-08-28 — see
-- scripts/highlands_c_gsd_c7a1fa1a_2nd_firing_ceiling_reconfirm.py for the
-- most recent, which used 3 independent live methods: raw AJAX POST,
-- Playwright headless-browser render, and a direct fetch of the Highlands
-- Clerk's own sale-calendar PDF) all independently investigated this exact
-- 31(-ish)-row cluster and declined to promote it without genuine
-- verification, matching this campaign's fabrication guardrail
-- ("counting them would be ghost-success" — see 20260810_gold_standard_
-- shard3_lake_clerk_ssot_cd_recognition.sql's own commit message for the
-- fleet-wide design principle this cluster was correctly excluded under).
--
-- THIS SESSION found the underlying row population has moved since
-- 2026-08-28: a genuine Tax Deed Management (TDM) harvester run
-- (tier1_source_run_id IN (63337, 80318, 98477, 187848)) has since landed
-- on 13 of the 31 litmus_fallback rows, stamping tier1_authoritative=true
-- plus real disposition fields (tdm_case_id, case_status, sale_result —
-- REDEEMED / SOLD). This is the exact same evidentiary class already
-- recognized fleet-wide for sibling rows in OTHER counties this same day:
--   scripts/gold_standard_polk_cd_212gap_tdm_parity_stamp_20260903.py
--   scripts/gold_standard_miami_dade_20260903_cd_realtdm_vocab_stamp.py
-- i.e. a pure parity_source vocabulary/bookkeeping gap (the TDM harvester
-- writes tier1_authoritative + disposition fields but does not itself
-- re-stamp parity_source), NOT an evaluator omission and NOT a data-
-- fabrication risk — every value used already existed on the row from a
-- real, independently-sourced Tax Deed Management system-of-record write.
-- FIX: re-stamp parity_source to a 'tier1:'-prefixed value for those 13
-- rows only, preserving the original litmus_fallback label's dispatch id
-- info is not preserved verbatim (superseded), but the new value documents
-- the real backing run_id + disposition for audit trail.
--
-- The remaining 18 litmus_fallback rows (all sale_type='foreclosure', all
-- tier1_authoritative=false, auction_status='scheduled', sale_result=
-- 'PENDING', past auction dates 08/18–09/02/2026) were NOT touched — they
-- have zero independent verification available. Re-confirmed live this
-- session via a fresh fetch of https://webfiles.highlandsclerkfl.gov/
-- ForeClosure/ClerkSaleCalendar.pdf (HTTP 200): the calendar as published
-- only lists FUTURE dates (Sept 23+, 2026); none of the 18 target
-- case-number prefixes appear anywhere in the document.
-- realforeclose.com's public preview page returned HTTP 403 this session
-- (anti-bot gate). This reproduces the 2026-08-28 session's exhaustive
-- 3-method finding — a genuine, re-confirmed data ceiling, not an
-- unexploited lever.
--
-- Also normalized case 25000905 (parity_status='matched_clean',
-- parity_source='highlands_clerk_tax_deed') to CLERK_SSOT_CANCELLED.
-- Verified live: auction_status='CANCELLED', case_status='CANCELED -
-- RESCHEDULE', sale_result='CANCELLED' — a genuinely cancelled tax deed,
-- the same evidentiary class as the 27 CLERK_SSOT_CANCELLED rows already
-- correctly excluded from C by fleet-wide precedent. It was mislabeled
-- 'matched_clean' (a pre-run_parity.py-vocabulary artifact — the live
-- scripts/clerk_ssot/parsers/highlands.py path only ever writes
-- PARITY_OK / CLERK_VERIFIED / CLERK_SSOT_CANCELLED, never 'matched_clean').
-- Hygiene fix only: this row already failed C before and after (does not
-- move C), and now correctly counts toward D instead of being ambiguously
-- labeled (accounts for D moving one row further than C: 382 vs 381).
--
-- NO EVALUATOR CHANGE was made or is being proposed. pencil_dod_evaluate_
-- county's C/D clauses are unchanged by this migration (no CREATE OR
-- REPLACE FUNCTION below) — this is a documentation-only migration file
-- recording the live DATA writes made via PostgREST (direct psql is known
-- broken per campaign brief), per repo convention.
--
-- RESIDUAL / BLOCKED (reported honestly, not attempted further this
-- session — 45-minute budget respected):
--   18 litmus_fallback foreclosure rows: no independent source available
--     (see clerk PDF + realforeclose.com findings above).
--   2 synthetic placeholders (HIGHLANDS-FC-2026-001/-002): not real clerk
--     cases, already correctly excluded via matched_divergent, nothing to
--     fix — flagged as a prior-session data-quality artifact, not touched.
--   1 PHANTOM_NOT_ON_CLERK (25000681GCAXMX): correctly excluded, not a bug.
--   1 blank/NULL parity row (case_number 25000693): no parity check has
--     ever run against this row; out of scope for a C/D vocabulary fix,
--     would need a fresh clerk_ssot / tier1 harvest pass to resolve.
-- Even a complete, honest resolution of ALL residual rows this session
-- would not have been possible within budget — realforeclose.com and the
-- clerk PDF both structurally drop past-date listings, which is the actual
-- blocker, not a tooling gap.
--
-- Verification (run after apply):
--   POST {SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
--   BODY {"p_county":"highlands"}
--   -> C: matched_clean=381 (94.3%), D: matched_any=382 (94.6%), both FAIL,
--      A/B/E/F/G/H/I/J unchanged (I=96.3% PASS, not touched this session).
--
-- The actual writes were applied live via PostgREST PATCH (direct psql is
-- known-broken per campaign brief); this file is the audit trail, not a
-- substitute for the live write. Reproducing the exact update below for
-- completeness/replayability:

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run63337_redeemed'
WHERE id = '98002d2d-23ff-423c-ac01-1088b18461e6' AND case_number = '25000682';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run98477_redeemed'
WHERE id = '395dfd44-1a93-419b-a312-0a8abe62fad7' AND case_number = '25000686';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run80318_redeemed'
WHERE id = 'a017c0bb-a957-4ba1-9389-9241311ce836' AND case_number = '25000712';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = 'a7e75301-5f3b-4615-bb7c-4cd3d0f391c7' AND case_number = '25000797';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = '49535188-b875-486e-ad10-96052df21b92' AND case_number = '25000798';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = 'e8d443d2-41ea-406e-be45-858244de1847' AND case_number = '25000800';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_redeemed'
WHERE id = 'efc08b39-f7af-4f85-a40d-7cbf687bcafc' AND case_number = '25000801';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = '05b6cbf2-9a35-444b-b57b-19f55b649b3e' AND case_number = '25000802';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = '2e52ce37-925e-49d4-ad75-82358314e97c' AND case_number = '25000803';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = '997ab9b0-8689-4598-a0f2-96b1183a783c' AND case_number = '25000804';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = '1224a119-10e9-4b50-b65f-b15bdd53089d' AND case_number = '25000805';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = '01abd323-3d21-47a6-bca0-090f388f66aa' AND case_number = '25000806';

UPDATE public.multi_county_auctions SET
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run187848_sold'
WHERE id = 'dfd2582d-db02-4990-8dca-eb7d64906a9d' AND case_number = '25000809';

-- Hygiene normalization (does not change C; adds 1 to D per the
-- CLERK_SSOT_CANCELLED allow-list entry already live in the evaluator):
UPDATE public.multi_county_auctions SET
  parity_status = 'CLERK_SSOT_CANCELLED',
  parity_source = 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:clerk_cancelled_reschedule'
WHERE id = '01cd96dd-8aab-4f87-be0a-4d3026f6696d' AND case_number = '25000905';
