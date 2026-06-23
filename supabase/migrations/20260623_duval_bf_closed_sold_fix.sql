-- DUVAL B/F CLOSED_SOLD DENOMINATOR FIX
-- Applied: 2026-06-23 via Management API
-- Problem: sold_amount=0.0 on 22 upcoming + 8 cancelled rows inflated
--          the B/F denominator from 6 to 36, making both metrics 25%
-- Fix:
--   1. NULL sold_amount=0 for upcoming/cancelled (not genuine closed sales)
--   2. Set sold_amount=tier1_sold_amount for completed rows (real sales)
--   3. Insert 3 missing completed rows into foreclosure_outcomes
-- Result: closed_sold=6, B=100%, F=100%

-- Step 1: Null bad sold_amount=0 for upcoming/cancelled
UPDATE multi_county_auctions
SET sold_amount = NULL, updated_at = NOW()
WHERE lower(county) = 'duval'
  AND sold_amount IS NOT NULL AND sold_amount = 0
  AND auction_status IN ('upcoming', 'cancelled', 'canceled');

-- Step 2: Fix sold_amount=0 for completed rows (use real tier1 amount)
UPDATE multi_county_auctions
SET sold_amount = tier1_sold_amount, updated_at = NOW()
WHERE lower(county) = 'duval'
  AND auction_status = 'completed'
  AND tier1_sold_amount IS NOT NULL AND tier1_sold_amount > 0
  AND sold_amount IS NOT NULL AND sold_amount = 0;

-- Step 3: Insert missing FC closed rows into foreclosure_outcomes for B criterion
INSERT INTO foreclosure_outcomes (
    county, case_number, sale_type, auction_date,
    outcome, winning_bid, opening_bid,
    parcel_id, property_address, data_source
)
SELECT
    'duval', mca.case_number, mca.sale_type, mca.auction_date,
    'sold', mca.sold_amount, mca.opening_bid,
    mca.parcel_id, mca.property_address,
    CASE
        WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realtaxdeed%' THEN 'duval_realtaxdeed_mca'
        ELSE 'duval_realforeclose_mca'
    END
FROM multi_county_auctions mca
WHERE lower(mca.county) = 'duval'
  AND mca.sold_amount IS NOT NULL AND mca.sold_amount > 0
  AND NOT EXISTS (
    SELECT 1 FROM foreclosure_outcomes fo
    WHERE lower(fo.county) = 'duval' AND fo.case_number = mca.case_number
  )
  AND NOT EXISTS (
    SELECT 1 FROM tax_deed_outcomes tdo
    WHERE lower(tdo.county) = 'duval' AND tdo.case_number = mca.case_number
  )
ON CONFLICT DO NOTHING;
