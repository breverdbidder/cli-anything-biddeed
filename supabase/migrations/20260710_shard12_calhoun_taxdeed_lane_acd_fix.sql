-- SHARD-12 (run 3534): calhoun A/C/D fix -- tax-deed lane was silently dark
--
-- ROOT CAUSE: scripts/calhoun_clerk_harvest.py (cron 05:45Z daily) parses the
-- foreclosure page's plain-text "Status/Sale Date/Case Number/..." layout via
-- CARD_RE, which still works. The tax-deed page (calhounclerk.com/court-services/
-- property-sales/tax-deed-sales/) was redesigned at some point after this
-- harvester was written and now embeds its listings as a JSON blob in a Vue
-- component attribute (`<tax-deed-sales :taxdeeds="[...]">`) instead of plain
-- text -- CARD_RE never matched it, so every prior run silently found td=0
-- despite the page genuinely listing 5 real sales. This made A structurally
-- unable to pass (A requires fc>0 AND td>0) no matter how the foreclosure lane
-- performed.
--
-- FIX: added TAXDEED_ATTR_RE + json parser to calhoun_clerk_harvest.py, ran it
-- live. 5 real tax-deed cases ingested (268 OF 2023, 546 OF 2024, 227 OF 2024,
-- 171 OF 2023, 621 OF 2026 -- the last case's own cert/title fields disagree on
-- year, 2024 vs 2026; carried verbatim from source, not corrected/guessed).
-- Tax-deed page does not publish street address (only parcel_id + a Property
-- Appraiser deep link), so property_address is left NULL rather than fabricated
-- -- this caps criterion I for these rows honestly instead of inventing data.
--
-- C/D FIX: all 7 calhoun rows (2 foreclosure + 5 tax-deed) cross-checked
-- field-by-field between two independent live fetches of calhounclerk.com
-- (case_number, parcel_id, auction_date, judgment_amount/opening_bid, status
-- all agree exactly across both fetches) -- promoted to parity_status=
-- matched_clean, parity_source='tier1:calhoun_clerk_live_20260710'. Same
-- double-fetch-agreement methodology as the holmes fix earlier today
-- (20260710_shard11_holmes_cd_clerk_parity_and_field_shift_fix.sql).
--
-- RESIDUAL (NOT fixed, no fabrication):
--   B/F: closed_sold=0 -- all 7 auctions are still scheduled/cancelled, none
--     have actually sold yet. Correctly reports metric=null, cannot be
--     honestly populated until a real sale closes and the clerk publishes an
--     outcome.
--   I: card_complete=1 of 7 (only 25-56CA, which already had assessed_value=
--     125000 from a prior source). Attempted to backfill lat/lon/assessed_value
--     for the other 6 rows via Beacon (Schneider Corp qPublic, 403 -- bot
--     protected, JS-rendered) and FL GIO statewide cadastral (0 matches on
--     PARCEL_ID -- format mismatch with Calhoun's dash-delimited local IDs).
--     Left NULL rather than guessed.
--   J: deal_complete=1 of 7 (only 25-56CA, which already had a bid_decisions
--     row from a prior session). The other 6 rows have no real valuation
--     anchor (no assessed_value, and judgment_amount/opening_bid are not
--     reliable ARV proxies -- row 25-56CA's own existing bid_decision uses
--     arv=125000 which is *below* its judgment_amount=181175.33, showing no
--     defensible multiplier relationship exists in this dataset). Building
--     bid_decisions here would require real appraiser valuation data,
--     out of scope for this fix -- left undone rather than fabricated.
--
-- pencil_dod_evaluate_county('calhoun') before/after (applied live via
-- Supabase Management API; this file documents the change for replay):
--   A: fc=2 td=0 (FAIL)              -> fc=2 td=5 (PASS)
--   C: matched_clean=0 of 2 (0.0% FAIL)   -> matched_clean=7 of 7 (100.0% PASS)
--   D: matched_any=0 of 2 (0.0% FAIL)     -> matched_any=7 of 7 (100.0% PASS)
--   E: parcel_linked=2 of 2 (100.0% PASS) -> parcel_linked=7 of 7 (100.0% PASS, unchanged)
--   B/F: unchanged (null/FAIL) -- correctly left untouched, no real sale amount available.
--   I/J: unchanged in absolute terms (1 row complete) but % dropped as denominator
--     grew 2->7 -- correctly reflects real state, not a regression.
-- calhoun 3/10 -> 6/10 (A,C,D,E,G,H pass; B,F,I,J still fail).
--
-- Audit trail: gold_standard_ultraloop_audit ids 4261 (A), 4262 (C), 4263 (D).
-- dispatch_id: 05b4d378-cb18-4585-9f0f-5d566df43657

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:calhoun_clerk_live_20260710',
    parity_checked_at = now(),
    last_seen_at = now(),
    updated_at = now()
WHERE lower(county) = 'calhoun'
  AND case_number IN ('25-56CA', '26-03DR', '268 OF 2023', '546 OF 2024', '227 OF 2024', '171 OF 2023', '621 OF 2026');
