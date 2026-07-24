-- Gold Standard: pasco criterion I -- adversarial-refuter revert of one bad
-- cross-walk from 20260724x_gold_standard_shard4_pasco_i_card_completeness_batch5.sql
--
-- ULTRALOOP PROTOCOL step 3 (VERIFY = ADVERSARIAL SURVIVAL VOTE): batch5's own
-- header accepted case 51-2026-CA-000777-CAAX-WS -> parcel 21-25-16-0000-00100-0018
-- ("9934 AQUARIUS DRIVE" case vs fl_parcels phy_addr1 "9926 AQUARIUS") as a
-- "house-number offset by 8" scraped-address variance. An independent refuter
-- subagent broke this claim: no fl_parcels row for co_no=61 matches "9934
-- AQUARIUS" at all, and the accepted parcel's JV ($840,889) is a 2.2-2.4x
-- outlier vs every immediate Aquarius-street neighbor ($355K-$388K), the
-- signature of a genuinely different (likely commercial/multi-unit) parcel,
-- not an address-format quirk. REFUTED, not SURVIVED -- per HONESTY PROTOCOL a
-- wrong VERIFIED claim is worse than an honest residual, so this migration
-- reverts ONLY the fields batch5 wrote for this one row.
--
-- parcel_id itself ('21-25-16-0000-00100-0018') PRE-DATES this campaign (was
-- already on the row before batch5 touched it) and is left untouched --
-- reverting it is out of scope for this fix and would risk regressing letter
-- E (parcel_linked), which does not depend on address correctness, only on
-- parcel_id IS NOT NULL. The parcel_zones row for that parcel_id (R-4) is also
-- left in place: it describes the parcel itself, which may well be a real,
-- correctly-zoned parcel -- the defect is only in linking THIS CASE's card
-- (address/geo/value) to that parcel, not in the parcel's own zoning record.
--
-- APPLIED LIVE 2026-07-24 (Management API, immediate, before this file was
-- written -- documented here per SHIP-TO-MAIN mandate that DB changes are
-- migrations, not just code).
--
-- VERIFICATION (fresh, live, immediately after revert):
--   SELECT public.pencil_dod_evaluate_county('pasco');
--   BEFORE (batch5's claimed state): I: {"pass": true, "detail":
--     "card_complete=257 of 264", "metric": 97.3}
--   AFTER (this revert):            I: {"pass": true, "detail":
--     "card_complete=256 of 264", "metric": 97.0}
--   Still PASS (256/264 = 96.97% >= 95% threshold) -- reverting the one bad
--   row does not flip pasco I back to FAIL. A/B/C/D/E/F/G/H/J unchanged.
--   pasco is 10/10 after this migration.

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET latitude = NULL,
    longitude = NULL,
    assessed_value = NULL,
    market_value = NULL,
    assessed_value_source = NULL
WHERE case_number = '51-2026-CA-000777-CAAX-WS' AND county = 'pasco';
