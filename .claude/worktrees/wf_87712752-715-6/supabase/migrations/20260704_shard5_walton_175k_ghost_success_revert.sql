-- SHARD-5 (walton): $175,000 placeholder ghost-success revert (CRITICAL)
-- Session: architect-20260704T000000 (adversarial refuter re-verification pass)
--
-- ORIGIN OF FABRICATION:
-- supabase/migrations/20260625_shard4_run581_gold_standard.sql lines 55-62 applied a blind
-- COALESCE fallback for walton with zero real-data backing:
--   UPDATE multi_county_auctions
--   SET sold_amount = COALESCE(NULLIF(opening_bid, 0), 175000),
--       tier1_sold_amount = COALESCE(NULLIF(opening_bid, 0), 175000), updated_at = NOW()
--   WHERE lower(county)='walton' AND sold_amount IS NULL;
-- A follow-on migration (20260625_shard4_run581_gold_standard_v2.sql) compounded this with a
-- $200,000 assessed_value placeholder and built bid_decisions (ARV/max_bid) math on top of the
-- already-fabricated sold_amount/assessed_value, self-labeling the chain
-- 'HYPOTHESIS'/'INFERRED' in its own SQL comments. No later migration
-- (20260626_shard5_run1032, 20260628_shard7_run1524, or the "walton 10/10 certified" commits
-- fbbf896a/edc9eca3/0338d9ab/bf5cd982) ever reverted the underlying $175,000 sold_amount -- they
-- only re-stamped parity_source labels on top of the already-fabricated matched_clean rows.
--
-- RE-VERIFIED LIVE 2026-07-04 (Management API SQL; direct psql pooler auth fails in this
-- sandbox, same documented constraint as every prior shard session):
--
-- 1. multi_county_auctions: exactly 18 walton rows (of 30 total, excl. PropertyOnion) carry
--    sold_amount=175000 AND opening_bid IS NULL -- a 100% correlation (every $175,000 row has a
--    NULL opening_bid, zero exceptions), the unmistakable signature of the pure COALESCE
--    fallback, not real scraped data. Case numbers: 25CA000379, 25CA000161, 25CA000175,
--    25CA000334, 24CA000541, 25CA000453, 25CA000040, 25CC000657, 25CA000317, 25CA000377,
--    25CA000068, 25CA000561, 25CA000562, 24CA000281, 25CA000566, 23CA000443, 25CA000080,
--    25CA000437. Of these: 6 are auction_status='cancelled' (a cancelled auction cannot have a
--    real sale price), 4 are auction_status='upcoming' with a "sale amount" already populated
--    (impossible -- the auction has not happened), 8 are auction_status='sold' with the
--    identical placeholder. 14 of these 18 carried parity_status='matched_clean' /
--    parity_source='tier1_foreclosure_outcome'.
--
-- 2. foreclosure_outcomes backing (walton_mca_official data_source): 14 rows, ALL winning_bid
--    =175000.00 exactly, ALL sharing one identical batch timestamp
--    enriched_at='2026-06-25 16:18:20.930264+00' -- proof of a single bulk batch insert, not
--    independent per-case scraping. Case numbers match the 14 non-"upcoming" rows from #1
--    exactly.
--
-- 3. NEW FINDING (beyond the original refuter brief, discovered during this session's live
--    re-verification): the 4 remaining "upcoming" fabricated case numbers (24CA000541,
--    25CA000317, 25CA000437, 25CC000657) ALSO have a foreclosure_outcomes row -- in a
--    *different* batch, data_source='walton_realforeclose_official',
--    enriched_at='2026-06-25 16:18:30.308553+00' (the same batch the original refuter brief
--    characterized as "real distinct 175000-adjacent-but-genuine values" for 6 OTHER case
--    numbers in that batch). Live inspection shows this batch is a mix: 6 genuine rows have
--    winning_bid==opening_bid with distinct plausible dollar values (e.g. 24CA000292=9026.65,
--    25CA000128=640756.78), but the SAME 4 fabricated case numbers have winning_bid=175000.00
--    exactly with opening_bid IS NULL -- the identical fabrication signature as #2, just
--    duplicated into a second data_source label. These 4 rows were deleted alongside the 14 for
--    consistency (same rationale as the primary batch: leaving them would let the matcher
--    re-match against fabricated "independent" outcome data).
--
-- 4. tax_deed_outcomes for walton (5 rows: 2025-0090TD, 2025-0092TD, 2026-0001TD, 2026-0002TD,
--    2026-0006TD) independently re-checked: all carry distinct, plausible, tax-deed-scale
--    dollar amounts (none = 175000), confirmed genuinely real. NOT touched by this migration.
--    2026-0001TD in particular (winning_bid=1024.27, data_source='walton_mca_official' but a
--    DIFFERENT table/row than the deleted foreclosure_outcomes batch) remains the sole
--    genuinely-backed matched_clean row for walton post-revert.
--
-- ACTION: null sold_amount/tier1_sold_amount/parity_status/parity_source on the 18 fabricated
-- multi_county_auctions rows; delete the 14 fabricated foreclosure_outcomes rows
-- (walton_mca_official batch) plus the 4 fabricated foreclosure_outcomes rows discovered in the
-- walton_realforeclose_official batch (finding #3); re-run refresh_parity_tier1_outcomes to
-- reclassify against the remaining genuine outcome data.
--
-- EXACT SQL EXECUTED LIVE (via Management API, already applied -- this file is the record):

BEGIN;

UPDATE multi_county_auctions
   SET sold_amount = NULL,
       tier1_sold_amount = NULL,
       parity_status = NULL,
       parity_source = NULL,
       updated_at = now()
 WHERE lower(county) = 'walton'
   AND sold_amount = 175000
   AND opening_bid IS NULL;
-- RETURNING confirmed 18 rows affected (case_numbers listed in finding #1).

DELETE FROM foreclosure_outcomes
 WHERE lower(county) = 'walton'
   AND data_source = 'walton_mca_official'
   AND winning_bid = 175000.00
   AND enriched_at = '2026-06-25 16:18:20.930264+00';
-- RETURNING confirmed 14 rows deleted.

DELETE FROM foreclosure_outcomes
 WHERE lower(county) = 'walton'
   AND data_source = 'walton_realforeclose_official'
   AND winning_bid = 175000.00
   AND opening_bid IS NULL;
-- RETURNING confirmed 4 rows deleted (24CA000541, 25CA000317, 25CA000437, 25CC000657) --
-- finding #3, same fabrication signature in a second data_source label.

-- Reclassify parity_status for the now-cleared rows against remaining real outcome data:
-- SELECT * FROM public.refresh_parity_tier1_outcomes('walton');
-- Result: [{"pass":"case","matched_clean":1,"matched_divergent":0},
--          {"pass":"parcel","matched_clean":0,"matched_divergent":0}]

INSERT INTO honesty_violations
  (id, domain, claim, tag_used, actual_truth, severity, session_source, corrective_action, resolved)
VALUES
  (gen_random_uuid(), 'GOLD_STANDARD_CAMPAIGN',
   'walton pencil_dod_evaluate_county reported B=100%% (verified=29/29), C/D=50.0%% (matched_clean/any=15/30), F=100%% (tier1_sold=29/29)',
   'VERIFIED',
   'All four metrics rested in part on an 18-row COALESCE($175,000 default) fallback applied by
20260625_shard4_run581_gold_standard.sql to rows with NULL opening_bid, backed by a single-batch-
timestamp foreclosure_outcomes insert (14 rows at 2026-06-25 16:18:20.930264+00, data_source
walton_mca_official) plus 4 more rows discovered this session in a second data_source
(walton_realforeclose_official) sharing the identical winning_bid=175000.00/opening_bid-NULL
signature. Real walton state post-revert: B=100%% (verified=11/11, correct denominator drop),
C/D=3.3%% (matched_clean/any=1/30, the sole genuine 2026-0001TD tax-deed match), F=100%%
(tier1_sold=11/11). C/D dropping from 50%% to 3.3%% is the honest outcome, not a regression --
the prior 50%% was itself half-fabricated (14 of the 15 "matched_clean" rows were the placeholder).',
   'CRITICAL',
   'architect-20260704T000000',
   'Nulled sold_amount/tier1_sold_amount/parity_status/parity_source on 18 fabricated multi_county_auctions rows; deleted 18 fabricated foreclosure_outcomes rows across two data_source batches; re-ran refresh_parity_tier1_outcomes; re-ran pencil_dod_evaluate_county to confirm honest current state. See supabase/migrations/20260704_shard5_walton_175k_ghost_success_revert.sql.',
   true);

COMMIT;

-- ── BEFORE / AFTER pencil_dod_evaluate_county('walton') ──
--
-- BEFORE (fabricated, live-verified at session start):
--   A: pass=true  fc=24 td=6                        metric=6
--   B: pass=true  verified=29 closed_sold=29         metric=100.0
--   C: pass=false matched_clean=15                   metric=50.0
--   D: pass=false matched_any=15                     metric=50.0
--   E: pass=true  parcel_linked=30                   metric=100.0
--   F: pass=true  tier1_sold=29 closed_sold=29        metric=100.0
--   G: pass=true  density=100.0 far=100.0             metric=100.0
--   H: pass=true  hours since last_seen               metric=0.3
--   I: pass=true  card_complete=29 of 30              metric=96.7
--   J: pass=true  deal_complete=30                    metric=100.0
--   auctions_total: 30
--
-- AFTER (honest, live-verified post-revert):
--   A: pass=true  fc=24 td=6                        metric=6
--   B: pass=true  verified=11 closed_sold=11         metric=100.0
--   C: pass=false matched_clean=1                    metric=3.3
--   D: pass=false matched_any=1                      metric=3.3
--   E: pass=true  parcel_linked=30                   metric=100.0
--   F: pass=true  tier1_sold=11 closed_sold=11        metric=100.0
--   G: pass=true  density=100.0 far=100.0             metric=100.0
--   H: pass=true  hours since last_seen               metric=0.0
--   I: pass=true  card_complete=29 of 30              metric=96.7
--   J: pass=true  deal_complete=30                    metric=100.0
--   auctions_total: 30
--
-- Net effect: closed_sold denominator dropped 29->11 (18 fabricated "sold" rows removed from
-- the numerator/denominator alike, so B/F stay at 100%% but against an honest, much smaller real
-- base). matched_clean/matched_any dropped 15/30 (50.0%%) -> 1/30 (3.3%%) -- this drop is the
-- correct and honest outcome of removing fabricated data, not a regression to compensate for.
