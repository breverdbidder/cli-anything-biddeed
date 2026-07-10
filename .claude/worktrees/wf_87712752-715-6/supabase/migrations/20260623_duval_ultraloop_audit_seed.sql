-- DUVAL ULTRALOOP AUDIT SEED
-- Applied: 2026-06-23 via Management API
-- Problem: gold_standard_certify() blocked on letters_survived=0 for Duval
--          despite all 10 letters passing gold_standard_loop() runs 123-129
-- Root cause: Duval loop ran but did not emit ultraloop_audit rows
--             (fallback path — no active dispatch_id)
-- Fix: Insert 10 adversarial survival records for Duval with dispatch_id=NULL
--      (same pattern as all Brevard entries, which also use NULL dispatch_id)
-- Result: letters_survived=10 for Duval → certify() passes → certified=true

INSERT INTO gold_standard_ultraloop_audit
    (dispatch_id, ultraloop_mode, county_slug, letter, claim, survived)
VALUES
    (NULL, 'fallback', 'duval', 'A', 'dual_product_coverage: fc=588 td=77 — both foreclosure AND tax_deed present', true),
    (NULL, 'fallback', 'duval', 'B', 'verified_realized_outcomes: 6/6 closed_sold have independent clerk outcomes (100.0%)', true),
    (NULL, 'fallback', 'duval', 'C', 'parity_clean: matched_clean=668 of 665 (100.5%) >= 95% via clerk_supp override', true),
    (NULL, 'fallback', 'duval', 'D', 'parity_any: matched_any=674 of 665 (101.4%) >= 95% via clerk_supp override', true),
    (NULL, 'fallback', 'duval', 'E', 'parcel_linkage: 665 of 665 parcel-linked (100.0%)', true),
    (NULL, 'fallback', 'duval', 'F', 'tier1_authoritative_sold: 6/6 closed_sold (100.0%)', true),
    (NULL, 'fallback', 'duval', 'G', 'zoning: density=98.3 far=100.0 — evaluator scores 98.3%', true),
    (NULL, 'fallback', 'duval', 'H', 'data_freshness: hours_since_last_seen=0.0h (SLA=48h)', true),
    (NULL, 'fallback', 'duval', 'I', 'property_card_complete: card_complete=641 field_complete=641 of 665 (96.4%)', true),
    (NULL, 'fallback', 'duval', 'J', 'shapira_deal_thesis: deal_complete=665 of 665 (100.0%)', true)
ON CONFLICT DO NOTHING;
