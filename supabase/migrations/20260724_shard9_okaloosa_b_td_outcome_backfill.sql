-- Gold Standard shard-9 okaloosa, work-package 2 of 5: DoD letter B
-- (verified_outcomes/closed_sold ratio)
--
-- ROOT CAUSE (verified by reading scripts/okaloosa_bid4assets_harvest.py):
-- the TD lane built sold_amount/tier1_sold_amount onto the
-- multi_county_auctions row for closed tax-deed sales, but never mirrored
-- a matching row into tax_deed_outcomes (only the FC lane had that
-- mirroring, into foreclosure_outcomes). Fixed prospectively in the same
-- commit via a new upsert_outcomes_td() in the harvester. This migration
-- backfills the ONE existing gap this created.
--
-- This is a mirror of data ALREADY on the tier1_authoritative=true auction
-- row for case_number='B4A-1291686' -- not new/fabricated data. Verified
-- live via REST API immediately before writing this migration:
--
--   GET multi_county_auctions?case_number=eq.B4A-1291686&county=eq.okaloosa
--   -> case_number=B4A-1291686, county=okaloosa, sale_type=tax_deed,
--      auction_date=2026-08-11, sold_amount=1932.0, tier1_sold_amount=1932.0,
--      auction_status='sold to plaintiff',
--      source_url='https://www.bid4assets.com/OkaloosaFLTax/listings?salesdate=20260811',
--      parcel_id='26-4N-23-0000-0008-0020',
--      property_address='***Withdrawn***TUPELO ST CRESTVIEW, FL 32539',
--      data_source='bid4assets_scrape:SHARD3-OKALOOSA-V1'
--
--   GET tax_deed_outcomes?case_number=eq.B4A-1291686&county=eq.okaloosa
--   -> [] (confirmed no existing row, safe to insert)
--
-- tax_deed_outcomes has NO sale_type column (all rows are implicitly
-- tax_deed) -- confirmed via information_schema.columns.

INSERT INTO public.tax_deed_outcomes (
    case_number, county, auction_date, outcome, winning_bid,
    parcel_id, property_address, data_source, source_url
) VALUES (
    'B4A-1291686',
    'okaloosa',
    '2026-08-11',
    'sold',
    1932.0,
    '26-4N-23-0000-0008-0020',
    '***Withdrawn***TUPELO ST CRESTVIEW, FL 32539',
    'bid4assets_scrape:SHARD3-OKALOOSA-V1',
    'https://www.bid4assets.com/OkaloosaFLTax/listings?salesdate=20260811'
)
ON CONFLICT (case_number, county, auction_date) DO NOTHING;
