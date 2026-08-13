-- Gold Standard shard-3 (dispatch 59758c8a-8d8d-48f7-843d-5e2c6844fbf9), county highlands, letter I.
--
-- Context: pencil_dod_evaluate_county('highlands') letter I (card_complete) was
-- 341/360 (94.7%), below the 95% pass threshold. Diagnosis found exactly two
-- rows with parcel_id already zone-linked, with lat/lon and assessed_value
-- present, missing ONLY property_address:
--   case_number 25000831  parcel_id C-22-37-30-080-0510-0020
--   case_number 25000865  parcel_id C-22-37-30-170-1770-0070
--
-- Fix: looked up the real site address for both parcels via the official
-- Highlands County Property Appraiser search (https://www.hcpao.org/Search,
-- POST SearchMode=RealEstate-ParcelId, RealEstateParcelId=<parcel_id>).
-- Confirmed live results:
--   C-22-37-30-080-0510-0020 -> BORGES-BUXO HERMINIA -> "375 PARADISE AVE LAKE PLACID" 33852
--   C-22-37-30-170-1770-0070 -> MATOS-MELENDEZ JUANA ESTATE -> "415 WIND ROSE AVE LAKE PLACID" 33852
--
-- Result: I moved from 341/360 (94.7%, FAIL) to 343/360 (95.3%, PASS).
-- (Card_complete rose by 2 rows, consistent with both target rows now
-- satisfying every I condition.)

UPDATE multi_county_auctions
SET property_address = '375 PARADISE AVE, LAKE PLACID, FL 33852'
WHERE lower(county) = 'highlands'
  AND case_number = '25000831'
  AND parcel_id = 'C-22-37-30-080-0510-0020';

UPDATE multi_county_auctions
SET property_address = '415 WIND ROSE AVE, LAKE PLACID, FL 33852'
WHERE lower(county) = 'highlands'
  AND case_number = '25000865'
  AND parcel_id = 'C-22-37-30-170-1770-0070';
