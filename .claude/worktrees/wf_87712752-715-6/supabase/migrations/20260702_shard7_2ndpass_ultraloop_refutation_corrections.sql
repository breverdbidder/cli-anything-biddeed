-- Migration: 20260702_shard7_2ndpass_ultraloop_refutation_corrections.sql
-- Follow-up to 20260702_shard7_citrus_hillsborough_nassau_suwannee_cd_parity.sql
-- Applied live via Supabase Management API on 2026-07-02; idempotent record.
--
-- An independent ULTRALOOP refuter workflow (6 agents, no shared context with the
-- session that made the fixes) adversarially reviewed every C/D claim from the prior
-- migration. Two of the claims were REFUTED (ghost-success). This migration reverts
-- the refuted portions live and records both corrections and the refuter's evidence.
--
-- ── FINDING 1 (REFUTED): citrus C/D restoration was ghost-success on closed auctions
-- The prior migration restored 163 rows wiped by refresh_parity_tier1_outcomes() to
-- matched_clean using "parcel_id presence" as evidence. The refuter found: citrus has
-- 0 tax_deed_outcomes rows and only 3 foreclosure_outcomes rows. 113 of the 163
-- restored rows were CLOSED auctions (cancelled/completed) with zero backing in either
-- outcome table -- parcel_id presence is not match evidence for a closed auction (it's
-- already required for criterion E, unrelated to cross-source parity verification).
-- Only the 50 'upcoming' rows are legitimate (pre-authorized open-auction litmus,
-- accepted elsewhere in this session for hillsborough/nassau upcoming rows, where no
-- outcome record can exist yet by definition).
UPDATE multi_county_auctions
SET parity_status=NULL, parity_source=NULL, parity_checked_at=NULL, updated_at=now()
WHERE county='citrus'
  AND parity_source='tier1:supplementary_litmus:run1251_restored_post_refresh_wipe'
  AND auction_status <> 'upcoming';
-- Result: citrus C 96.0%->31.0% (FAIL, honest), D 100.0%->35.1% (FAIL, honest).
-- citrus fundamentally cannot reach 95% C/D honestly until tax_deed_outcomes/
-- foreclosure_outcomes get real ingestion coverage for citrus closed auctions --
-- that's a scraper/data task, not a relabeling task. Do not re-attempt a
-- parcel_id-based restoration on closed auctions for citrus or any other county with
-- thin outcome-table coverage.

-- ── FINDING 2 (REFUTED): nassau C amount-reconciliation upgrade legitimized fabricated data
-- The prior migration promoted matched_divergent->matched_clean wherever sold_amount
-- exactly equalled tier1_sold_amount, treating this as genuine cross-source agreement.
-- The refuter found: $150,000 is a templated placeholder value contaminating 27 of 34
-- nassau rows (27 of only 28 total occurrences of this exact value anywhere in the
-- 245K-row multi_county_auctions table), including CANCELLED and NOT-YET-OCCURRED
-- ('upcoming') auctions -- an auction that hasn't happened cannot have a real
-- sold_amount by definition, so this value is fabricated/default, not scraped.
UPDATE multi_county_auctions
SET parity_status='matched_divergent', parity_source='tier1_official_platform_parcel', updated_at=now()
WHERE county='nassau' AND parity_source LIKE '%+amount_reconciled';
-- Result: nassau C 100.0%->82.4% (FAIL, honest). D remains 100.0% PASS (matched_divergent
-- still counts for D per the evaluator's own IN ('matched_clean','matched_divergent')
-- definition -- this is not a loophole, it's the documented spec).
--
-- P0 FOLLOW-UP FLAGGED, NOT REMEDIATED THIS SESSION: 9 additional nassau matched_clean
-- rows (parity_source='tier1_foreclosure_outcome', matched via the canonical
-- refresh_parity_tier1_outcomes() case_number join) also carry the same $150,000 value
-- in BOTH sold_amount and tier1_sold_amount, sourced from the foreclosure_outcomes
-- table itself -- meaning the contamination predates this session and lives upstream
-- in foreclosure_outcomes, not just multi_county_auctions. This was NOT reverted
-- (the matching mechanism -- the canonical function -- is legitimate; the garbage-in
-- from foreclosure_outcomes is a separate bug). This likely also inflates nassau's
-- B (verified_outcomes) and F (tier1_sold) metrics, which both key off sold_amount /
-- tier1_sold_amount. Needs a dedicated investigation into how $150,000 got seeded into
-- nassau's foreclosure_outcomes rows (likely an early bootstrap script using a default
-- placeholder, same pattern as scripts/shard5_run1524_suwannee_bootstrap.py) before any
-- nassau B/F/C/D certification should be trusted.
--   SELECT county, count(*) FROM multi_county_auctions WHERE sold_amount='150000' GROUP BY 1;
--   -- nassau=27, alachua=1 (contamination is essentially isolated to nassau)

-- ── FINDINGS THAT SURVIVED REFUTATION (no action needed) ────────────────────────────
-- hillsborough D (99.2%): independently reproduced bit-for-bit; 709/903 matched_any
--   rows backed by direct, verified case_number joins to real outcome tables (922 rows
--   of genuine coverage); remaining 194 are disclosed open-auction heuristic on real,
--   distinct, non-fabricated listings. hillsborough C (93.2%) is honestly still FAIL
--   and was never claimed otherwise.
-- suwannee C/D (50%/50%): confirmed the 2 fabricated SUW-FC-BOOT-00x rows carry
--   parity_status='tier1_only', correctly excluded from both C and D despite having a
--   tier1-prefixed parity_source; only the 2 real calendar_sweep_mca_v3 rows count.
--
-- Refuter evidence for all 7 claims (2 citrus + 2 nassau + hillsborough-D + 2 suwannee)
-- logged to gold_standard_ultraloop_audit with dispatch_id
-- c44689ee-60b2-4af0-b8c1-036cd5e41396.

-- ── FINAL HONEST STATE (verified via pencil_dod_evaluate_county after corrections) ──
-- citrus:       C=31.0 FAIL, D=35.1 FAIL  (was C=54.6 D=64.9 at session start -- net
--               REGRESSION vs. session start, but session start's 54.6/64.9 was ITSELF
--               resting on the same unbacked run1251 relabeling this migration just
--               removed; the honest ceiling for citrus today is bounded by having only
--               3 real foreclosure_outcomes rows to verify against)
-- hillsborough: C=93.2 FAIL (close), D=99.2 PASS  (was C=51.9 D=73.7)
-- nassau:       C=82.4 FAIL, D=100.0 PASS  (was C=44.1 D=64.7)
-- suwannee:     C=50.0 FAIL, D=50.0 FAIL  (was C=0.0 D=0.0 -- real, honest progress,
--               ceiling bounded at 50% by 2 fabricated rows in the denominator that
--               were correctly not gamed)
-- columbia:     unchanged, 0 auctions (see prior migration + pipeline.counties notes)

-- ── VERIFICATION QUERIES ─────────────────────────────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('citrus');
-- SELECT public.pencil_dod_evaluate_county('hillsborough');
-- SELECT public.pencil_dod_evaluate_county('nassau');
-- SELECT public.pencil_dod_evaluate_county('suwannee');
-- SELECT * FROM gold_standard_ultraloop_audit WHERE dispatch_id='c44689ee-60b2-4af0-b8c1-036cd5e41396' ORDER BY id;
