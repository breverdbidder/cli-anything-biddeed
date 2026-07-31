-- Gold Standard shard-5 gilchrist (letters E, I): parcel_id + property-card backfill
-- for the 2 of 8 unlinked rows that carried a real property_address.
--
-- Source: Gilchrist County Property Appraiser official parcel records portal
--   https://gilchrist-search.gsacorp.io/ (GSA Corp platform, official appraiser
--   site linked from https://gilchrist.wordpress.gsacorp.io/, the county's
--   published Property Appraiser site). Confirmed via the site's own
--   api/livesearch/<address> endpoint and per-parcel detail pages.
--
-- Row 1: case 26-0005-TD (tax_deed), property_address "1202 SW FOURTH AVE"
--   Parcel 17-10-15-0051-0000-0180, owner THE MHF RETIREMENT TRUST.
--   Sales history shows Official Record 202621003203, Tax Deed, dated
--   2026-06-16, Grantor "CLERK OF THE COURT TODD NEWTON" -> Grantee
--   "THE MHF RETIREMENT TRUST" -- exact date match to this row's auction_date
--   (2026-06-16), confirming this is the parcel sold at this tax deed auction.
--   Use Code 0000: VACANT. Total Market $18,800 / Total Assessed $18,448.
--
-- Row 2: case 212025CA000069CAAXMX (foreclosure), property_address
--   "7439 SE 78 PL, TRENTON, FL- 32693"
--   Parcel 11-10-16-0552-0010-0060, owner LAKEVIEW LOAN SERVICING LLC.
--   Sales history shows Official Record 202621003223, Certificate of Title,
--   dated 2026-06-16, Grantor "TODD NEWTON CLERK OF THE COURT" -> Grantee
--   "LAKEVIEW LOAN SERVICING LLC" -- classic foreclosure-sale-to-plaintiff
--   pattern, dated within days of this row's auction_date (2026-06-08),
--   confirming this is the same case/property. Use Code 0100: SINGLE FAMILY.
--   Total Market $181,839 / Total Assessed $181,839. Legal: LOT 6 BLK 10
--   UNIT 2 SUN N FUN.

UPDATE multi_county_auctions
SET
  parcel_id = '17-10-15-0051-0000-0180',
  owner_name = 'THE MHF RETIREMENT TRUST',
  legal_description = 'LOT 18 SCHOFIELD BROTHERS SUBD',
  assessed_value = 18448,
  market_value = 18800,
  property_type = 'VACANT',
  city = 'TRENTON',
  state = 'FL',
  zip = '32693',
  assessed_value_source = 'gilchrist_county_property_appraiser_gsacorp'
WHERE case_number = '26-0005-TD'
  AND lower(county) = 'gilchrist'
  AND parcel_id IS NULL;

UPDATE multi_county_auctions
SET
  parcel_id = '11-10-16-0552-0010-0060',
  owner_name = 'LAKEVIEW LOAN SERVICING LLC',
  legal_description = 'LOT 6 BLK 10 UNIT 2 SUN N FUN',
  assessed_value = 181839,
  market_value = 181839,
  property_type = 'SINGLE FAMILY',
  bedrooms = 2,
  bathrooms = 2,
  living_area_sqft = 1110,
  year_built = 2023,
  city = 'TRENTON',
  state = 'FL',
  zip = '32693',
  assessed_value_source = 'gilchrist_county_property_appraiser_gsacorp'
WHERE case_number = '212025CA000069CAAXMX'
  AND lower(county) = 'gilchrist'
  AND parcel_id IS NULL;
