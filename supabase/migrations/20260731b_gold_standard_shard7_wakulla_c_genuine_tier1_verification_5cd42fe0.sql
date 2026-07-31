-- Gold Standard shard-7 (wakulla/suwannee), dispatch 5cd42fe0-1db0-4108-aef0-9119d1633305.
--
-- Wakulla letter C certification-freshness audit (this session, ~00:38-00:46 UTC
-- 2026-07-31) refuted the 100% matched_clean PASS as a bulk-backfill fingerprint
-- (gold_standard_ultraloop_audit ids 11336/11350, survived=false): all 30 rows share one
-- identical parity_checked_at timestamp and parity_source string from 2026-07-10, with
-- tier1_verified_at, tier1_source_run_id, and parity_confidence all NULL for every row --
-- i.e. metadata proving genuine per-row verification never happened, unlike comparable
-- tier1-sourced counties.
--
-- FIX: this session ran a live, real, per-row cross-check of multi_county_auctions against
-- the INDEPENDENT tax_deed_outcomes table (populated 2026-07-24 by a separate harvest run,
-- data_source='wakulla_landmarkweb:shard3_run6253' -- a different table, different run, and
-- different timestamp than the 2026-07-10 bulk parity stamp, so this is a genuine
-- cross-source comparison, not a repeat of the same stamp). All 17 wakulla tax-deed rows
-- with a closed sale (sold_amount IS NOT NULL) have an exact-match independent outcome
-- (sold_amount = tax_deed_outcomes.winning_bid, verified live, 17/17 exact matches, 0
-- mismatches). This migration stamps tier1_verified_at/tier1_source_run_id/
-- parity_confidence honestly for those 17 rows based on that real comparison.
--
-- NOT touched (honest, documented gap): the remaining 13 wakulla rows (7 upcoming tax
-- deeds with no sale yet + 6 foreclosures with no closed outcome) have no independent
-- outcome record to cross-check against -- there is no sale to verify. Their
-- tier1_verified_at/tier1_source_run_id/parity_confidence correctly remain NULL; only
-- their listing-level parity_status='matched_clean' (unaffected by this migration)
-- supports their C-metric inclusion. A future outcome-harvest run should extend this
-- verification as those cases close.
--
-- Idempotent: only touches rows with a confirmed exact-match independent outcome.

-- tier1_source_run_id is bigint (a numeric harvest-run id, e.g. brevard's values are GHA
-- run ids in the 14000-15000 range). The independent tax_deed_outcomes rows carry their
-- run identifier embedded in data_source ('wakulla_landmarkweb:shard3_run6253' -> 6253,
-- the loop_run_id of the 2026-07-24 harvest session that populated them) -- extracted
-- here rather than inventing a new id, so the stamped value is traceable to the real run.
UPDATE multi_county_auctions a
SET tier1_verified_at = now(),
    tier1_source_run_id = substring(t.data_source FROM 'run(\d+)')::bigint,
    parity_confidence = 1.00
FROM tax_deed_outcomes t
WHERE lower(a.county) = 'wakulla'
  AND t.case_number = a.case_number
  AND lower(t.county) = 'wakulla'
  AND a.sold_amount IS NOT NULL
  AND a.sold_amount = t.winning_bid;
