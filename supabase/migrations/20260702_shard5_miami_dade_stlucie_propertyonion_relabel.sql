-- SHARD-5: miami_dade + st_lucie — HARD GUARDRAIL FIX: PropertyOnion-litmus matches were
-- mislabeled with a 'tier1_*' parity_source, falsely crediting them as independent
-- clerk-verified matches under pencil_dod_evaluate_county's C/D criteria.
-- dispatch_id: bec9a9b3-ce1c-4a46-b7e0-a861096f5ffb
-- Session: architect-20260702T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02 via ULTRALOOP audit workflow wf_63692fb6-dbb):
-- Standing HARD GUARDRAIL #1: "PropertyOnion = litmus ONLY. Never ingest as a data source."
-- pencil_dod_evaluate_county's C/D criteria trust any parity_source LIKE 'tier1%%' as an
-- independent clerk/official-records match. Two counties' matching batches stamped
-- PropertyOnion-vs-MCA comparisons (rows where parity_po_id IS NOT NULL, i.e. matched
-- against propertyonion_listings, NOT against tax_deed_outcomes/foreclosure_outcomes)
-- with generic labels that satisfy the 'tier1%%' filter:
--   miami_dade: parity_source IN ('tier1_clerk_official_records_shard1_run1113',
--     'tier1_clerk_official_records_shard3') on 51 rows (7 matched_clean, 44
--     matched_divergent) -- VERIFIED zero corresponding rows actually exist in
--     tax_deed_outcomes/foreclosure_outcomes for miami_dade; the harvest these labels
--     claim to come from never actually landed independent data.
--   st_lucie: parity_source='tier1_matched_clean_bootstrap' on 28 of 30 such rows (2 of
--     the 30 DO have real tax_deed_outcomes/foreclosure_outcomes backing and are left
--     untouched).
--
-- This directly inflated C (miami_dade +7, st_lucie 0) and D (miami_dade +51, st_lucie
-- +28) above the true independently-verified baseline. Per HONESTY PROTOCOL this must be
-- corrected even though it makes the scoreboard look worse -- a passing/near-passing
-- number built on litmus-only data is not a pass.
--
-- FIX: relabel these rows so parity_source no longer matches the evaluator's 'tier1%%'
-- filter, while leaving parity_status/parity_po_id untouched (they remain valid
-- PropertyOnion-litmus comparison records, just correctly no longer counted as
-- independent verification).
--
-- VERIFIED live via pencil_dod_evaluate_county before/after:
--   miami_dade C: 2.0%  (matched_clean=7  of 355) -> 0.0% (matched_clean=0 of 355)
--   miami_dade D: 14.4% (matched_any=51   of 355) -> 0.0% (matched_any=0  of 355)
--   st_lucie   C: 1.4%  (matched_clean=1  of 72)  -> 0.0% (matched_clean=0 of 72)
--   st_lucie   D: 41.7% (matched_any=30   of 72)  -> 2.8% (matched_any=2  of 72, the 2
--     rows with genuine tax_deed_outcomes/foreclosure_outcomes backing)
--   A/B/E/F/G/H/I/J unaffected on both counties (confirmed no regression)
--
-- NOTE: this exposes that miami_dade's prior "10/10 GOLD" session-report claims (commits
-- 4b12691a, 7fb5b6d0, 27ca940a) rested in part on this same mislabeled data for C/D --
-- flagging for the record; those reports predate this audit and were not fabricated
-- knowingly, but the underlying labeling bug means miami_dade's true C/D state has likely
-- never been genuinely >=95% during this campaign. Both counties now need REAL
-- clerk/official-records harvesting (tax_deed_outcomes/foreclosure_outcomes population)
-- to move C/D -- no further SQL relabeling can fix this; it is a data-gap, not a bug.
--
-- Applied live 2026-07-02 via Supabase Management API; this file documents it.

UPDATE multi_county_auctions
SET parity_source = replace(parity_source, 'tier1_clerk_official_records', 'propertyonion_litmus')
WHERE lower(county) = 'miami_dade'
  AND parity_po_id IS NOT NULL
  AND parity_source LIKE 'tier1_clerk_official_records%';

UPDATE multi_county_auctions
SET parity_source = 'litmus_po_only'
WHERE lower(county) = 'st_lucie'
  AND parity_source = 'tier1_matched_clean_bootstrap'
  AND parity_po_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM foreclosure_outcomes fo WHERE fo.case_number = multi_county_auctions.case_number)
  AND NOT EXISTS (SELECT 1 FROM tax_deed_outcomes tdo WHERE tdo.case_number = multi_county_auctions.case_number);
