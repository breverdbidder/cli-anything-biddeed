-- Gold Standard shard-3 (dispatch e5b14c41-5caf-4088-a8e6-d26843815130, issue #19739)
-- washington letter E (parcel linkage): backfill parcel_id from the row's own
-- account_number for tax_deed stub rows ingested via the TaxDeedMaster (TDM)
-- pipeline that never copied it into parcel_id.
--
-- Evidence: 78 already-linked washington tax_deed rows have parcel_id already
-- equal to account_number on the same row (byte-identical), in Washington
-- County's dashed property-appraiser format 00000000-SS-BBBB-LLLL, confirmed
-- against qPublic/TaxNetUSA published format documentation for Washington
-- County FL. The 31 rows below simply lagged the backfill. Applied live via
-- PostgREST (direct psql auth is broken in the CI sandbox per prior sessions'
-- documented finding) as 31 individual per-id PATCH calls -- this file is the
-- audit-trail record of that operation, not the execution mechanism.
--
-- Result (VERIFIED via pencil_dod_evaluate_county('washington')):
--   E: parcel_linked 112/143 (78.3%, FAIL) -> 143/143 (100.0%, PASS)
--   county total: 5/10 -> 6/10 (A,B,E,F,G,H pass; C,D,I,J still fail)
-- C/D/I/J were investigated this session and root-caused to a SEPARATE issue
-- (these rows also lack property_address, which parity/card-completeness need
-- independently of parcel_id) -- see docs/spec/19739.md. This migration only
-- claims the E fix.

UPDATE public.multi_county_auctions
SET parcel_id = account_number,
    geo_source = 'tdm_account_number_backfill'
WHERE county = 'washington'
  AND parcel_id IS NULL
  AND account_number IS NOT NULL;

-- Idempotent: re-running matches zero rows once applied (parcel_id IS NULL
-- becomes false for all 31 target rows).
