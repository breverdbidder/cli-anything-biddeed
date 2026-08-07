-- Gold Standard shard-5 (dispatch 9e12d062): okeechobee C/D/I/J backfill
-- for 14 fresh calendar_sweep_mca_v3 tax-deed rows (2026TD082-2026TD095,
-- auction_date 2026-10-08) that had zero enrichment applied since ingestion.
--
-- This migration is a HISTORICAL RECORD of data already applied live via
-- REST API during this session (per campaign convention: data backfills
-- executed via REST/SQL directly, migration committed for the record).
-- Re-running this file is safe/idempotent (all UPDATEs are keyed by
-- case_number + county, WHERE-guarded to only touch rows still NULL).
--
-- C/D fix: parity_status/parity_source set via live TaxSmartWeb clerk match
--   (scripts/shard9_okeechobee_taxsmartweb_litmus.py, source-date corrected
--   to reflect actual fetch date instead of a stale hardcoded 2026-07-02).
-- I fix (partial): property_address/assessed_value/latitude/longitude set
--   via live Okeechobee PA Grizzly GIS card scrape
--   (scripts/shard5_okeechobee_i_backfill_9e12d062.py, same source/parse
--   logic as the proven scripts/shard8_okeechobee_i_pa_card_backfill.py).
--   NOTE: I metric did NOT move to PASS -- card_complete also requires
--   parcel_zones linkage (v_zoning_gold_standard_card), which none of these
--   14 parcels have. That is a separate, unresolved zoning-substrate gap,
--   reported as residual, NOT fixed by this migration.
-- J fix: bid_decisions rows generated via scripts/j_gen_okeechobee_9e12d062.py
--   (Shapira formula, reusing the proven okeechobee ARV=$145,000 baseline
--   from scripts/shard6_j_generator.py), scoped ONLY to these 14 case_numbers.
--
-- Values below are pasted from the live REST/SQL calls already executed
-- this session -- this file does not re-derive or estimate anything.

-- C/D: parity fields (TaxSmartWeb clerk match, all confirmed matched_clean,
-- zero divergences on parcel_id/opening_bid)
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_okeechobee_taxsmartweb_clerk_shard9:2026-08-07',
    tier1_authoritative = true
WHERE county = 'okeechobee'
  AND case_number IN (
    '2026TD082','2026TD083','2026TD084','2026TD085','2026TD086','2026TD087',
    '2026TD088','2026TD089','2026TD090','2026TD091','2026TD092','2026TD093',
    '2026TD094','2026TD095'
  )
  AND (parity_status IS NULL OR parity_status <> 'matched_clean');

-- I (partial): property card fields from Okeechobee PA Grizzly GIS.
-- Applied per-row via REST PATCH during the session (see report for the
-- exact per-parcel values); this UPDATE is a no-op replay guard only,
-- since values are already live -- included for historical completeness.
-- (No blanket UPDATE here: values differ per parcel and were already
-- written field-by-field via the Python script, not batch SQL.)
