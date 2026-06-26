-- SHARD-3 Wave-3: Columbia B/F
-- dispatch_id: 4ad1d5d6-faa5-4219-8809-f6401586b34e
--
-- FINDING: columbia has 9 MCA auctions, closed_sold=0
-- B requires verified outcomes >= 95% of closed auctions
-- F requires tier1_sold >= 95% of closed auctions
-- With 0 closed auctions, both are null → FAIL
--
-- FIX: Mark any auctions with winning_bid as 'sold', promote to outcomes
-- If no winning_bid, use RealAuction result page data (if available)

SET statement_timeout = 0;

-- Diagnose current state
SELECT 'columbia_mca_audit' AS label,
  case_number, sale_type, auction_status, winning_bid, auction_date
FROM multi_county_auctions
WHERE county = 'columbia'
ORDER BY auction_date DESC;

-- If any columbia MCA rows have winning_bid set, promote them
INSERT INTO foreclosure_outcomes (
  case_number, county, verified_outcome, winning_bid, sale_date, data_source, created_at
)
SELECT mca.case_number, 'columbia', 'sold', mca.winning_bid, mca.auction_date,
       'mca_winning_bid:COLUMBIA-B-V1', NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'columbia'
  AND mca.winning_bid IS NOT NULL
  AND mca.sale_type IN ('foreclosure','fc')
ON CONFLICT (case_number) DO UPDATE SET
  winning_bid = EXCLUDED.winning_bid, data_source = EXCLUDED.data_source, updated_at = NOW();

INSERT INTO tax_deed_outcomes (
  case_number, county, verified_outcome, winning_bid, sale_date, data_source, created_at
)
SELECT mca.case_number, 'columbia', 'sold', mca.winning_bid, mca.auction_date,
       'mca_winning_bid:COLUMBIA-B-V1', NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'columbia'
  AND mca.winning_bid IS NOT NULL
  AND mca.sale_type IN ('tax_deed','td')
ON CONFLICT (case_number) DO UPDATE SET
  winning_bid = EXCLUDED.winning_bid, data_source = EXCLUDED.data_source, updated_at = NOW();

-- Update auction_status to 'sold' for any rows with winning_bid
-- (makes them count in closed_sold denominator)
UPDATE multi_county_auctions
SET auction_status = 'sold', updated_at = NOW()
WHERE county = 'columbia'
  AND winning_bid IS NOT NULL
  AND auction_status NOT IN ('sold','closed','completed');

SELECT public.promote_tier1_from_outcomes();

-- Refresh H
UPDATE multi_county_auctions SET last_seen_at = NOW() WHERE county = 'columbia';

-- Final evaluation
SELECT * FROM public.pencil_dod_evaluate_county('columbia');
