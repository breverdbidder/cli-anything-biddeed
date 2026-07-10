-- SHARD-1 run2886 (baker/escambia/st_lucie/holmes/hamilton) — dispatch 6005f806-75ca-426f-a39d-ab82ebba9890
--
-- HONESTY PROTOCOL: purge unbacked ghost-success parity rows for escambia.
--
-- CONFIRMED (adversarially verified via ultraloop workflow, re-checked independently against
-- live DB): 60 escambia multi_county_auctions rows carry parity_status='matched_clean' with
-- parity_source IN ('tier1_realtaxdeed_calendar_v1', 'tier1_realforeclose_calendar_v1'), all
-- stamped parity_checked_at either 2026-07-04 08:22:04.638346+00 (57 rows) or
-- 2026-07-04 08:22:13.27571+00 (3 rows) — both batches this morning, both with
-- tier1_authoritative=false and tier1_source_run_id=NULL, structurally indistinguishable from
-- escambia's 185 genuinely-unmatched sibling rows (same data_source='calendar_sweep_mca_v3',
-- no cert_number, no winning_bidder). Neither source label appears in ANY committed script or
-- migration in this repo (grep across *.py/*.sql/*.yml/*.js returns zero hits). This is the
-- same ghost-success anti-pattern already purged for escambia once before in
-- 20260702_shard1_pencil_dod_cd_tier1_filter.sql (commit 652678dc), which documented escambia's
-- prior fake 262-row "matched_clean" batch (parity_source='official_parcel_linkage_shard2' — an
-- E-criterion parcel-link mistakenly counted as a C/D litmus match).
--
-- Escambia's only real, backed tier1 parity rows are 11: 9x tier1_realforeclose_escambia
-- (2026-07-02) + 2x tier1_foreclosure_outcome (2026-06-24). This migration reverts the other 60
-- rows back to their honest unmatched state (parity_status/parity_source/parity_checked_at =
-- NULL), dropping escambia C/D from a fabricated 26.7% back to the true 4.1% (11 of 266).
--
-- Per SHIP GATE: Sentinel/refuter is correct by default. The burden of proof was on the batch
-- that wrote these 60 rows, and no such proof (script, migration, source_run_id) exists.

BEGIN;

UPDATE public.multi_county_auctions
SET parity_status = NULL,
    parity_source = NULL,
    parity_checked_at = NULL
WHERE lower(county) = 'escambia'
  AND parity_status = 'matched_clean'
  AND parity_source IN ('tier1_realtaxdeed_calendar_v1', 'tier1_realforeclose_calendar_v1')
  AND tier1_authoritative = false
  AND tier1_source_run_id IS NULL;

COMMIT;
