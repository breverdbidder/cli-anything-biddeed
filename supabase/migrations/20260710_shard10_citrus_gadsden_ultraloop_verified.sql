-- SHARD-10 run3534 (dispatch 3a90abbe): ULTRALOOP-verified enrichment
-- Source: Workflow wf_6247de42-81b (Discover -> adversarial Verify, 18 agents, 897827 tokens)
-- Every row below survived an independent refuter agent that re-fetched the cited
-- source URL and reproduced the exact field values from raw HTML/JSON (not summaries).
-- One candidate (gadsden 24000726CA) was REFUTED by the verify pass (discover agent
-- claimed "121 Squirrel Ln / Bridges Joan" but the live source is actually
-- "310 Holly Cir / Jackson Al" -- a hallucination) and is correctly excluded below.

-- citrus: 10 tax-deed parcels, real assessed_value + clean address from
-- SWFWMD ArcGIS BaseVector/parcel_search (SOURCEAGENT=CITRUS COUNTY PROPERTY APPRAISER)
UPDATE multi_county_auctions SET property_address='10274 W OZELLO TRL', assessed_value=26500, market_value=26500,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=17E19S05 22000 0050 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0145TD';
UPDATE multi_county_auctions SET property_address='1945 W ATTUCKS LN', assessed_value=11500, market_value=11500,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=18E16S350010 7220 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0147TD';
UPDATE multi_county_auctions SET property_address='715 N ROOKS AVE', assessed_value=16440, market_value=16440,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=19E19S020080 00160 0730 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0148TD';
UPDATE multi_county_auctions SET property_address='916 N CHARLES AVE', assessed_value=8560, market_value=8560,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=19E19S020080 00030 0130 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0149TD';
UPDATE multi_county_auctions SET property_address='50 CYPRESS BLVD W', assessed_value=44960, market_value=44960,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=18E20S130010 000D0 0070 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0150TD';
UPDATE multi_county_auctions SET property_address='996 N CHARLES AVE', assessed_value=17120, market_value=17120,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=19E19S020080 00030 0320 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0151TD';
UPDATE multi_county_auctions SET property_address='100 S DESOTO ST', assessed_value=163731, market_value=163731,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=18E18S110050 00880 0140 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0152TD';
UPDATE multi_county_auctions SET property_address='6075 S LEWDINGAR DR', assessed_value=137071, market_value=137071,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=18E20S060020 00190 00C0 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0153TD';
UPDATE multi_county_auctions SET property_address='6722 S WALD PT', assessed_value=159955, market_value=159955,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=18E20S070010 00250 0260 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0156TD';
UPDATE multi_county_auctions SET property_address='2214 E FOUR SEASONS LN', assessed_value=7200, market_value=7200,
  assessed_value_source='swfwmd_arcgis:BaseVector/parcel_search PARNO=19E19S030010 00060 0260 (ultraloop-verified, run3534)'
  WHERE lower(county)='citrus' AND case_number='2026-0158TD';

-- gadsden: 5 of 6 candidate parcel linkages survived adversarial verification
-- (source: floridaparcels.com FL DOR tax-roll mirror, CO_NO=30). 24000726CA excluded
-- (refuted -- discover agent hallucinated the address/owner match).
UPDATE multi_county_auctions SET parcel_id='2-03-3N-6W-0000-00342-0200'
  WHERE lower(county)='gadsden' AND case_number='23000820CA';
UPDATE multi_county_auctions SET parcel_id='2-12-3N-5W-0000-00111-0200'
  WHERE lower(county)='gadsden' AND case_number='24000687CA';
UPDATE multi_county_auctions SET parcel_id='3-16-2N-3W-0785-00000-0120'
  WHERE lower(county)='gadsden' AND case_number='25000121CA';
UPDATE multi_county_auctions SET parcel_id='3-14-2N-2W-0565-0000E-0070'
  WHERE lower(county)='gadsden' AND case_number='25000126CA';
UPDATE multi_county_auctions SET parcel_id='3-07-2N-3W-0730-00000-1711'
  WHERE lower(county)='gadsden' AND case_number='25000148CA';
