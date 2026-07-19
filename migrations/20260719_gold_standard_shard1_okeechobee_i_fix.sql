-- Gold Standard shard-1: okeechobee letter I (card_complete) partial fix
-- Case 472025CA000225CAAXMX currently stores placeholder parcel_id 'MULTIPLE PARCELS'.
-- VERIFIED (clerk Notice of Foreclosure Sale, lakeonews.com classifieds, case 2025-CA-000225):
-- this is a genuine two-parcel judgment (Basswood Inc. Unit No. 6, Block 64, Plat Book 3 Pg 50):
--   Parcel 1: 1-05-37-35-0060-00640-0170 (Lot 17 + portion of Lot 18) -- primary/lead parcel
--   Parcel 2: 1-05-37-35-0060-00640-0190 (portion of Lots 18 & 19)
-- Schema stores a single parcel_id per row; using the lead parcel per research recommendation.
-- NOTE: neither parcel_id is zoning-linked (no parcel_zones/zoning coverage exists for the
-- Basswood subdivision), so this fix improves data accuracy but does NOT flip card_complete
-- for this row -- documented as a residual gap, not claimed as a pass.
--
-- Cases 2026TD050, 472025CA000130CAAXMX, 472025CA000205CAAXMX: research BLOCKED (no verified
-- address/parcel found in either source). Per guardrails, no rows written for these -- reported
-- as residual gaps instead of guessing.

UPDATE multi_county_auctions
SET parcel_id = '1-05-37-35-0060-00640-0170'
WHERE case_number = '472025CA000225CAAXMX'
  AND lower(county) = 'okeechobee'
  AND parcel_id = 'MULTIPLE PARCELS';
