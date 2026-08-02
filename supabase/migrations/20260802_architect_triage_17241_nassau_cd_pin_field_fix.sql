-- architect-triage issue #17241 (2026-08-02): nassau C/D field-name bug fix
--
-- Applied LIVE this session via Supabase REST (service role key), not psql.
-- This file is a durable record of the equivalent SQL for repo history /
-- future migration replay.
--
-- Root cause: dispatch 41bd7ce3 (run 8166, earlier the same day) shipped a
-- correctly-designed nassau C/D/I fix script to side branch
-- claude/issue-17241-20260802-0800 (commit 482f0bdd, never merged to main
-- -- a SHIP-TO-MAIN MANDATE violation). The script queried Nassau County
-- PA ArcGIS (maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/
-- TaxMap4_CitrixV2/MapServer/144) with `WHERE UPPER(dsp_strap) = ...`.
-- That field does not exist on this layer (live schema probe: fields are
-- PIN / PIN_NODELIM / PIN_DSP, no dsp_strap) -- every query returned
-- ArcGIS HTTP 400, silently swallowed, so the script's own live run
-- reported parity_fixed=0 zone_fixed=0. Nassau C/D stayed at 34/37 (91.9%)
-- unchanged.
--
-- Re-queried the 3 gap rows with the corrected field (PIN): all 3 resolved
-- to real, address-matching parcels via Nassau County's own GIS (the same
-- "supplementary_litmus_official_platforms" method already established for
-- 7 other nassau rows in migrations/20260702_shard10_run2346_nassau_cdi_g_fix.sql):
--   452025CA000241CAAXYX  PIN 26-2N-28-0552-0025-0000  ZoningDistrict=PUD  32428 POND PARKE PL
--   452025CA000281CAAXYX  PIN 37-1N-25-0000-0019-0010  ZoningDistrict=OR   43761 RATLIFF RD
--   452026XX000003TDAXYX  PIN 33-2N-25-0000-0001-0010  ZoningDistrict=OR   55100 HART TER
--
-- Result: pencil_dod_evaluate_county('nassau') C=100.0 D=100.0 (was 91.9/91.9).
-- nassau reached genuine 10/10; certified flipped true after 2 consecutive
-- gold gold_standard_loop()+gold_standard_certify() runs (8273, then 8309).
-- Full diagnosis: public.decision_log id=889.

UPDATE public.multi_county_auctions SET
  parity_status = 'matched_clean',
  parity_source = 'tier1_official_platform_parcel',
  parity_scope = 'supplementary_litmus_official_platforms_architect_triage_17241',
  parity_checked_at = '2026-08-02T14:29:00Z'
WHERE county = 'nassau'
  AND id IN (
    '93b0ffb6-ead2-45de-9a0c-14d79dd8de85',  -- 452025CA000241CAAXYX
    '74afd909-8e23-4a6a-8f46-92b5a229a8d6',  -- 452025CA000281CAAXYX
    '66efb879-c202-4ed5-9290-0fec46b42601'   -- 452026XX000003TDAXYX
  );
