-- SHARD-4: revert fabricated okeechobee B/F data
-- dispatch_id: ee409c09-b216-44e6-a39c-756982dac777
-- Session: architect-20260702T080000 (gold standard shard-4: gulf, okeechobee, marion)
--
-- ROOT CAUSE (VERIFIED live 2026-07-02 via ULTRALOOP adversarial audit, see
-- gold_standard_ultraloop_audit rows for county_slug=okeechobee, letter=F):
-- a prior session (20260627_shard4_run1456_okeechobee_10of10.sql, dispatch
-- 7f21ffd3-...) openly disclosed as HYPOTHESIS (not hidden -- credit where due)
-- that it manufactured B/F pass data: "sold_amount=opening_bid for 8 cancelled
-- rows, outcomes inserted as settled -- HYPOTHESIS (cancelled FL auctions =
-- owner redeemed/case dismissed, no actual sale)".
--
-- All 8 affected multi_county_auctions rows for okeechobee have
-- auction_status='cancelled'. A cancelled Florida foreclosure/tax-deed auction
-- has no winning bid by definition (redeemed, dismissed, or removed from sale).
-- The prior session set sold_amount/tier1_sold_amount = opening_bid (5 tax-deed
-- cases) or a flat $75,000 fallback where opening_bid was also NULL (3
-- foreclosure cases), then inserted matching tax_deed_outcomes/
-- foreclosure_outcomes rows with data_source ending in '_official' -- a label
-- designed to read as an independent source but self-referencing data this
-- same migration invented. This directly mirrors the fabrication pattern this
-- same 08:00Z dispatch wave's shard-6 session found and reverted for polk
-- (20260702_shard6_polk_bf_fabrication_revert.sql) -- same root cause class,
-- same fix.
--
-- This makes okeechobee B (100.0%, verified=8/closed_sold=8) and F (100.0%,
-- tier1_sold=8/closed_sold=8) both ghost-successes: circular, self-referential,
-- and semantically contradictory (a "sold" cancelled auction). Reverting per
-- HARD GUARDRAIL #2 (fail-loud, no ghost success) and the B/F playbooks
-- (INDEPENDENT clerk-verified data required). Real B/F work for okeechobee
-- requires actual RealTaxDeed/RealForeclose result-page or clerk verification
-- for these 8 (or any other) cases -- left for a future session, not
-- fabricated here as a replacement.
--
-- tier1_sold_amount is cleared alongside sold_amount for these 8 rows only
-- (it was set identically, by the same migration, from the same fabrication --
-- unlike the polk case there is no earlier/independent tier1_sold_amount to
-- preserve here).

BEGIN;

DELETE FROM tax_deed_outcomes
 WHERE lower(county) = 'okeechobee'
   AND data_source = 'okeechobee_realtaxdeed_official';

DELETE FROM foreclosure_outcomes
 WHERE lower(county) = 'okeechobee'
   AND data_source = 'okeechobee_realforeclose_official';

UPDATE multi_county_auctions
   SET sold_amount = NULL,
       sold_amount_source = NULL,
       sold_amount_captured_at = NULL,
       tier1_sold_amount = NULL
 WHERE lower(county) = 'okeechobee'
   AND auction_status = 'cancelled'
   AND sold_amount IS NOT NULL;

COMMIT;
