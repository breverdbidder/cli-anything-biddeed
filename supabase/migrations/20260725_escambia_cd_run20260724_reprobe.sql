-- Escambia C/D re-probe session (2026-07-25, one day after run20260724).
--
-- Baseline (VERIFIED live this session via pencil_dod_evaluate_county before any
-- write): escambia C=D=321/395 matched_clean/matched_any (81.3%), 74 gap rows all
-- with parity_status IS NULL, zero matched_divergent (C exactly equals D -- the gap
-- is unresolved rows, not mismatches). All 74 gap rows are tax_deed, spanning the
-- same 5 far-future auction dates documented by scripts/shard_escambia_cd_run20260724.py
-- (08/05, 09/02, 10/07, 11/04, 12/02/2026), plus 1 already-resolved foreclosure
-- date (07/23/2026, 2 live items, 0 new matches -- already fully matched).
--
-- Root cause (CONFIRMED, same as documented by the 20260711c and run20260724
-- sessions before this one): escambia.realtaxdeed.com's live TD calendar for
-- far-future dates diverges from our calendar_sweep_mca_v3 source snapshot --
-- NOT a matcher bug, NOT a key-normalization bug, NOT a coverage gap in the
-- litmus source itself (escambia.realtaxdeed.com IS live and fully populated:
-- 60-61 AITEM records per date confirmed live this session via the shared
-- harvest_date_paginated() AJAX helper). It is a temporal convergence gap:
-- RealAuction's live TD certificate list updates as each auction date approaches
-- (cert substitution/redemption before the sale posts), so re-probing periodically
-- recovers more real matches over time as dates get closer to "today".
--
-- FIX APPLIED (re-ran the existing script verbatim, no new matcher code written,
-- per K3 surgical + REPOEVAL reuse mandate):
--   python3 scripts/shard_escambia_cd_run20260724.py
-- This re-harvested all 6 target dates live and found 9 NEW exact case_number
-- matches that did not exist in the 2026-07-24 run's live snapshot (calendar
-- convergence, not a bug): case numbers 2024 TD 002400, 2024 TD 002973,
-- 2024 TD 002746, 2024 TD 002742, 2024 TD 003027, 2024 TD 002972,
-- 2024 TD 006980, 2024 TD 007387, 2024 TD 007035 -- all promoted to
-- parity_status='matched_clean', parity_source='tier1_realauction_escambia_run20260724'
-- (reused the existing source label since this is the same matcher/method, just a
-- later re-run -- not a new source).
--
-- The script's PATCH was executed live via direct Supabase REST call during this
-- session (idempotent WHERE guard: parity_status IS NULL only). This migration is
-- the durable record of that same write; the WHERE clause below is a no-op on
-- re-apply since parity_status is already 'matched_clean' for these 9 ids.
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county after promotion, this
-- session): C/D moved 321/395 (81.3%) -> 330/395 (83.5%). Re-ran the script a
-- second time immediately after (idempotency + genuine-residual check): 0 new
-- matches, 65 residual gap rows stable across the same 5 tax_deed dates
-- (08/05 x8, 09/02 x14, 10/07 x14, 11/04 x10, 12/02 x19) -- confirms genuine
-- residual, not a bug artifact.
--
-- HONEST GAP REPORT: 65 of 395 (16.5%) remain genuinely unmatched. Target is
-- >=95% (>=376 matched). This is STILL SHORT of target and is NOT resolvable
-- this session without a new data source -- the residual case numbers simply do
-- not exist yet on escambia.realtaxdeed.com's live calendar for dates 3-5 months
-- out. Per the three prior sessions' documented pattern (20260705, 20260711c,
-- run20260724), this gap closes gradually as each auction date approaches and the
-- county's TD calendar finalizes (commonly 1-3 weeks pre-sale). Re-probing this
-- same script periodically (e.g. weekly) as dates approach is the correct ongoing
-- remediation -- not a one-shot fix. Deferred, not fabricated. Do not force-match
-- the residual 65.

BEGIN;

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realauction_escambia_run20260724'
WHERE lower(county) = 'escambia'
  AND sale_type = 'tax_deed'
  AND parity_status IS NULL
  AND id IN (
    'd1814f41-3a52-4aac-9eb2-c391395223da',
    '10b650d6-7202-418c-9c54-d0d2016ce005',
    'e94ca5e1-46b7-46e3-a137-ba5a85f8e1fe',
    '9c05dedb-9767-4c03-8e56-886a0e702a0a',
    '41a8e165-7508-42ad-94ae-d41dad2696f2',
    '28e91f3e-bc13-48a5-b3c9-d8235dbe7b7d',
    'be4cf30b-71dc-48dc-9363-0c2ad246d7c2',
    '0cc155a1-4e87-43c3-a2f2-b0e9f0328c77',
    'b8831770-028b-4075-af07-745e16851e31'
  );

COMMIT;
