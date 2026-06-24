-- Shard 3: Franklin county parcel-id backfill for E criterion
-- Session: architect-20260624
-- 
-- Auction 1: FC-25-001-FRANKLIN, 100 Market St, Apalachicola, FL 32320
--   Source: fl_parcels (co_no=29, phy_addr1='100 MARKET ST')
--   Parcel ID: 0109S08W833000020050 (VERIFIED via fl_parcels DB match)
--   Owner: HEWITT BEVERLY ETAL, JV=278228, lat=29.7274869, lng=-84.9847156
--
-- Auction 2: TD-25-001-FRANKLIN, 200 Ave D, Apalachicola, FL 32320
--   PARCEL NOT FOUND in fl_parcels (co_no=29, 18,009 parcels searched)
--   Address gap confirmed: fl_parcels has 196 AVE D and 207 AVE D, but NOT 200 AVE D
--   FL GIO services9 timed out (network restriction on runner)
--   QPublic (franklinpa.com) is parked domain - unavailable
--   Result: parcel_id left NULL — cannot fabricate a parcel ID
--   E criterion: 50% (1/2) — does NOT pass threshold (need >=95%)

-- Apply parcel_id for auction 1 (already applied via REST API PATCH)
UPDATE multi_county_auctions
SET
    parcel_id        = '0109S08W833000020050',
    latitude         = 29.7274869,
    longitude        = -84.9847156,
    assessed_value   = 278228,
    owner_name       = 'HEWITT BEVERLY ETAL',
    updated_at       = NOW()
WHERE id = 'cca0b8a2-8774-40b1-858d-0172d16129a6'
  AND county = 'franklin';

-- Verification query:
-- SELECT id, case_number, property_address, parcel_id, latitude, assessed_value
-- FROM multi_county_auctions
-- WHERE county = 'franklin';
