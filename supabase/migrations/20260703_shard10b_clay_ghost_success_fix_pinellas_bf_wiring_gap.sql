-- SHARD-10 (wave: clay, leon, taylor, pinellas): clay C/D ghost-success completion +
-- pinellas B/F wiring-gap fix (sold_amount never backfilled from tier1_sold_amount)
-- dispatch_id: b2e2da00-b59f-40c6-bdce-3ba8109e3ca0
-- Session: architect-20260703T080000

-- ============================================================
-- 1) CLAY — complete the 2026-07-02 shard8 migration
--    (20260702_shard8_clay_holmes_cd_parity_fix.sql)
-- ============================================================
-- That migration's SECOND UPDATE (relabel the 12 matched_clean rows carrying
-- parity_po_id) was committed and documented as "AFTER: C matched_clean=17
-- (15.7%)" but VERIFIED live 2026-07-03 to have never actually executed against
-- the database: only the 21 matched_divergent rows were relabeled, the 12
-- matched_clean/parity_po_id rows still carried the old
-- 'tier1_clerk_supp_shard5_run651' label (C/D metric=26.9%, matched_clean=29 --
-- identical to the migration's own documented BEFORE state). This is a ghost
-- success: code committed, never executed. No new investigation was needed --
-- the prior migration's own evidence (12 named case numbers, all with
-- parity_po_id IS NOT NULL) was reused verbatim.
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('clay'):
--   BEFORE: C matched_clean=29 (26.9%) FAIL | D matched_any=29 (26.9%) FAIL
--   AFTER:  C matched_clean=17 (15.7%) FAIL | D matched_any=17 (15.7%) FAIL
-- Matches the shard8 migration's documented target exactly. Both remain FAIL
-- (honesty correction, not a certification-relevant gain). A/B/E/F/G/H/I/J
-- confirmed unchanged before/after.
--
-- Applied live via PostgREST PATCH 2026-07-03 (before this file was committed).

UPDATE multi_county_auctions
SET parity_source = 'propertyonion_litmus_source_not_tier1_shard8_20260702'
WHERE lower(county) = 'clay'
  AND parity_status = 'matched_clean'
  AND parity_po_id IS NOT NULL;

-- ============================================================
-- 2) PINELLAS — B/F wiring gap: sold_amount never backfilled from
--    tier1_sold_amount, plus 3 cancelled-auction rows with PropertyOnion
--    po_sold_amount=0.0 leaking into the operational sold_amount field
-- ============================================================
-- ROOT CAUSE (VERIFIED live 2026-07-03 via REST queries): pinellas has 301 rows
-- with tier1_sale_status set (CANCELED=155, SOLD=132, REDEEMED=7, blank=7).
-- Of the 132 tier1_sale_status='SOLD' rows, ALL 132 already carry a real,
-- independently-scraped tier1_sold_amount (per-row tier1_verified_at /
-- tier1_source_run_id) -- this is exactly the F-criterion's own definition
-- (authenticated RealAuction result pages) -- yet the operational sold_amount
-- column, which the evaluator's closed_sold/B/F filters key off of, was NULL
-- for every one of them. Separately, of the 168 tier1_sale_status='CANCELED'
-- rows, 165 correctly have sold_amount NULL and exactly 3 (the only 3 pinellas
-- rows with sold_amount NOT NULL before this fix) have sold_amount=0.0 --
-- verified to be byte-for-byte identical to their PropertyOnion po_sold_amount
-- field (a PropertyOnion placeholder for a cancelled/never-sold listing, not a
-- real transaction), i.e. PropertyOnion data leaking into an operational field
-- via provenance='po_only_2026_05_13_backfill'. A cancelled auction is not a
-- $0 sale; per HARD GUARDRAIL #1 (PropertyOnion = litmus only) this value must
-- not stand in as a completed-sale amount.
--
-- These are the SAME 3 rows the 2026-07-02 shard13 migration
-- (20260702_shard13_tier1_authoritative_propertyonion_correction.sql)
-- deliberately preserved in the tier1_authoritative allowlist -- that decision
-- is UNCHANGED and correct (they are legitimately independently re-verified
-- via realforeclose, tier1_authoritative=true stays true). This fix only
-- corrects the separate sold_amount field, not the inclusion/exclusion logic.
--
-- FIX:
--   (a) the 3 cancelled rows: sold_amount NULL -> NULL (no PO leakage)
--   (b) the 132 genuinely-sold rows: sold_amount <- tier1_sold_amount
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('pinellas'):
--   BEFORE: B verified=0  closed_sold=3   (0.0%)  FAIL
--           F tier1_sold=0 closed_sold=3  (0.0%)  FAIL
--   AFTER:  B verified=50 closed_sold=132 (37.9%) FAIL (honest number now;
--           50 of 132 already match independent foreclosure_outcomes rows,
--           data_source='realforeclose:pinellas:shard9', non-promote)
--           F tier1_sold=132 closed_sold=132 (100.0%) PASS -- real gain
-- A/C/D/E/G/H/I/J confirmed unchanged before/after.

-- (a) revert PropertyOnion po_sold_amount leakage on cancelled auctions
UPDATE multi_county_auctions
SET sold_amount = NULL,
    sold_amount_source = 'reverted_po_leakage_cancelled_auction_shard10_20260703'
WHERE lower(county) = 'pinellas'
  AND tier1_sale_status = 'CANCELED'
  AND sold_amount = 0;

-- (b) backfill sold_amount from the already-verified tier1_sold_amount for
--     genuinely sold auctions
UPDATE multi_county_auctions
SET sold_amount = tier1_sold_amount,
    sold_amount_source = 'tier1_realforeclose_backfill_shard10_20260703'
WHERE lower(county) = 'pinellas'
  AND tier1_sale_status = 'SOLD'
  AND sold_amount IS NULL
  AND tier1_sold_amount IS NOT NULL;
