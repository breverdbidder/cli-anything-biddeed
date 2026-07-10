-- Gold Standard shard-3 (run3645, dispatch fae25c74-55dd-4ef0-840c-569cbf825b29): putnam E fix.
--
-- putnam was 7/10, E FAIL at 95.8% (229/239 parcel_linked). 10 rows had parcel_id IS NULL,
-- most with property_address='Address Not Available, Putnam County, FL' (no usable
-- lookup key). Live re-harvest of putnam.realforeclose.com for the 7 distinct auction
-- dates covering these 10 cases found exactly ONE with a genuine, publishable parcel_id:
--
--   case 542024CA000405CAAXMX (auction_date 2026-06-18): parcel_id 02-10-26-1510-0000-0010,
--   address 220 STILWELL AV, PALATKA FL 32177 -- independently cross-verified against the
--   Putnam County Property Appraiser's own API, which returned matching STILWELL AV /
--   PALATKA data for that exact parcel number.
--
-- The other 9 cases genuinely have no usable single parcel_id on the county's own live
-- source (the platform's "Parcel ID" field is blank/non-numeric for those cases) -- NOT
-- fixed here; fabricating a value for them would violate the campaign's honesty protocol.
-- This single-row UPDATE was adversarially verified (independent refuter subagent
-- reproduced the parcel_id/address match against both the RealAuction platform and the
-- Property Appraiser API) before being applied.
--
-- Verified live result (pencil_dod_evaluate_county('putnam'), before -> after this fix):
--   E: 95.8% (229/239, FAIL) -> 96.2% (230/239, PASS)
--   putnam: 7/10 -> 8/10
-- C/D (68.2%, 76-row tax_deed date-mismatch gap) and I (92.1%, blocked on the same 9
-- no-parcel rows above + a separate 9-row zoning-ingestion gap) remain FAIL -- both were
-- investigated this session with live evidence but no safe fix exists yet (see session
-- report); NOT force-fixed.
-- ============================================================================

UPDATE public.multi_county_auctions
SET parcel_id = '02-10-26-1510-0000-0010',
    property_address = '220 STILWELL AV, PALATKA, FL 32177'
WHERE case_number = '542024CA000405CAAXMX'
  AND lower(county) = 'putnam'
  AND parcel_id IS NULL;
