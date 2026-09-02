-- Gold Standard shard-4 (dispatch b556ca84, issue 19722), 2026-09-02 08:00Z wave.
-- Nassau D fix: case 452026XX000010TDAXYX is a genuinely REDEEMED tax-deed sale
-- (independently reconfirmed live via RealTaxDeed's date-specific auction page,
-- zaction=AUCTION&zmethod=PREVIEW&AuctionDate=09/01/2026, Auction Status="Redeemed",
-- Certificate #1436, Opening Bid $238,579.73, parcel/address match). It had been
-- correctly classified PARITY_OK by an earlier same-day session (dispatch 6284f4fc,
-- ~08:20Z), then reverted to PHANTOM_NOT_ON_CLERK by an unrelated automated pass at
-- 2026-09-01 16:42Z that likely only checked the default preview/calendar view, which
-- drops redeemed cases -- the same false-phantom bug pattern already documented for
-- gadsden/suwannee/sumter/charlotte in GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md.
-- Applied live via mgmt_sql.py (Supabase Management API) during this session; this
-- migration file documents that write for the repo history / future sessions.
--
-- Effect: nassau D (matched_any) moved 53/56 (94.6%, FAIL) -> 54/56 (96.4%, PASS).
-- No effect on C by design (CLERK_SSOT_CANCELLED never counts toward matched_clean).

UPDATE multi_county_auctions
SET parity_status = 'CLERK_SSOT_CANCELLED',
    parity_source = 'nassau_clerk_tax_deed:redeemed_reconfirmed_20260902_shard4_b556ca84',
    updated_at = now()
WHERE county = 'nassau'
  AND case_number = '452026XX000010TDAXYX'
  AND parity_status = 'PHANTOM_NOT_ON_CLERK';
