-- SHARD-10 run2886 (clay/orange/indian_river/union): orange B/C/D ghost-success purge
-- dispatch_id: eeca7a1e-97dc-4b44-a5f7-d8d786cf5c94
-- Session: architect-20260703T160000
--
-- ROOT CAUSE (verified live): supabase/migrations/20260623_6county_gold_b_f_outcome_pipeline.sql
-- ran at least once on 2026-06-23 and blanket-INSERTed 28 self-referential rows into
-- tax_deed_outcomes for orange (data_source='orange_realtaxdeed_official', all
-- timestamped 2026-06-23 22:43:49), deriving every column straight from
-- multi_county_auctions' own winning_bid/sold_amount fields with zero independent
-- clerk/official-records verification -- the source migration's own header even
-- admitted "INFERRED ... not independently clerk-verified". Those 28 rows mapped
-- 1:1 to 28 multi_county_auctions rows stamped parity_status='matched_clean' /
-- parity_source='tier1_tax_deed_outcome' with no other backing evidence.
--
-- This inflated orange's B from an honest 178/207 (86.0%, FAIL) to a false 206/207
-- (99.5%, PASS), and C/D from an honest 178/855 (20.8%) to a false 206/855 (24.1%) --
-- C/D remain FAIL either way (well under the 95% threshold) so this purge does not
-- flip a PASS to a FAIL there, but B does flip from a false PASS to an honest FAIL.
-- The companion migration 20260623_6county_gold_b_f_outcome_pipeline.sql has been
-- edited in place this session to remove the fabricating UPDATE/INSERT statements
-- (replaced with read-only diagnostics) so it cannot re-corrupt orange on the next
-- Thursday 07:00 UTC cron of county-outcome-harvest.yml, nor the other 5 counties
-- (hillsborough, sarasota, palm_beach, broward, volusia) on their scheduled days.
-- Those 5 counties' own pre-existing fabricated rows (same data_source naming
-- convention: '<county>_realtaxdeed_official' / '<county>_realforeclose_official' /
-- '<county>_multi_county_auctions') are OUT OF SCOPE for this shard and are NOT
-- purged here -- flagged for their owning shards.
--
-- F was checked and confirmed NOT to trace to this migration: orange's
-- tier1_verified_at timestamps predate 2026-06-23 by weeks and tier1_buyer_type is
-- NULL (not 'third_party'/'unknown' as this migration would set) for all 207
-- closed_sold rows. F is untouched.
--
-- ACTION TAKEN (already applied live via Supabase Management API SQL endpoint
-- this session, ahead of this migration file being authored -- documented here for
-- the repo's audit trail per this campaign's convention):

BEGIN;

DELETE FROM tax_deed_outcomes
WHERE lower(county) = 'orange'
  AND data_source = 'orange_realtaxdeed_official';

UPDATE multi_county_auctions a
SET parity_status = NULL, parity_source = NULL, updated_at = now()
WHERE lower(a.county) = 'orange'
  AND a.parity_status = 'matched_clean'
  AND a.parity_source = 'tier1_tax_deed_outcome'
  AND NOT EXISTS (
    SELECT 1 FROM tax_deed_outcomes t
    WHERE lower(t.county) = 'orange' AND t.case_number = a.case_number
  );

COMMIT;

-- VERIFIED via pencil_dod_evaluate_county('orange') after purge (2026-07-04):
--   B: FAIL 86.0% (verified=178 closed_sold=207)   -- was false PASS 99.5%
--   C: FAIL 20.8% (matched_clean=178)               -- was false 24.1%, still FAIL
--   D: FAIL 20.8% (matched_any=178)                 -- was false 24.1%, still FAIL
--   F: PASS 100.0% (tier1_sold=207 closed_sold=207) -- unaffected, confirmed not fabricated
