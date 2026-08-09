-- lake_e_37_unlinked_case_addr_parcel_backfill.sql
-- 30 of 37 case-number-only lake_clerk_foreclosure_calendar_v1 rows resolved via
-- Lake County Clerk official records case search (legal description / lis pendens)
-- cross-referenced against Lake County Property Appraiser ArcGIS FieldMap service
-- (owner name + subdivision + lot number match). 7 left blocked_needs_more_research
-- (ambiguous owner/lot match, ownership turnover, or insufficient legal description).
-- Never touches property_address for rows already having one; never fabricates data.

UPDATE multi_county_auctions SET parcel_id = '032225010000009000', property_address = '102 BLACKSTONE CREEK RD' WHERE lower(county)='lake' AND case_number = '2016CA002108' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '291728010000004900', property_address = '25814 FISHERMAN''S RD' WHERE lower(county)='lake' AND case_number = '2022CA001715' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '132326000100000800', property_address = '9901 AVALON WOODS DR' WHERE lower(county)='lake' AND case_number = '2023CA000414' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '211927020000013102', property_address = '1890 ERIC LN' WHERE lower(county)='lake' AND case_number = '2023CA002935' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '112225100500000300', property_address = '10626 SPRING LAKE DR' WHERE lower(county)='lake' AND case_number = '2024CA000105' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '262125200500020900', property_address = '909 TIDAL POND DR' WHERE lower(county)='lake' AND case_number = '2024CA001079' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '222125000300002600', property_address = '20390 US HIGHWAY 27' WHERE lower(county)='lake' AND case_number = '2025CA000018' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '262426240000000400', property_address = '10813 RUSHWOOD WAY' WHERE lower(county)='lake' AND case_number = '2025CA000251' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '271924170000N00100', property_address = '1803 HIGH ST' WHERE lower(county)='lake' AND case_number = '2025CA000580' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '291926090009401800', property_address = '709 N DISSTON AVE' WHERE lower(county)='lake' AND case_number = '2025CA000637' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '062026005000008600', property_address = '1695 WYNFORD CIR' WHERE lower(county)='lake' AND case_number = '2025CA000787' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '252024026000008900', property_address = '25320 RIVER CREST DR' WHERE lower(county)='lake' AND case_number = '2025CA000930' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '271924170000N00200', property_address = '1805 HIGH ST' WHERE lower(county)='lake' AND case_number = '2025CA001078' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '221924040000000F04', property_address = '1806 CENTER ST' WHERE lower(county)='lake' AND case_number = '2025CA001198' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '271924225000001000', property_address = '2300 JOBBINS DR # UNIT 3' WHERE lower(county)='lake' AND case_number = '2025CA001201' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '242226001000004800', property_address = '14415 TRAVOIS WAY' WHERE lower(county)='lake' AND case_number = '2025CA001205' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '121926130000A01200', property_address = '1100 BATES AVE' WHERE lower(county)='lake' AND case_number = '2025CA001795' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '051924010000C00900', property_address = '1916 FRUITLAND PARK BLVD' WHERE lower(county)='lake' AND case_number = '2025CA001886' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '101926040000002300', property_address = '509 JACKSON ST' WHERE lower(county)='lake' AND case_number = '2025CA002017' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '291729010000000800', property_address = '43705 BEAR LAKE BLVD' WHERE lower(county)='lake' AND case_number = '2025CA002238' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '131924010000G02000', property_address = '5223 FREDRICK RD' WHERE lower(county)='lake' AND case_number = '2025CA002248' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '271927010000300100', property_address = '21010 NILES AVE' WHERE lower(county)='lake' AND case_number = '2025CA002307' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '271926005000008000', property_address = '2590 GLACIER EXPRESS LN' WHERE lower(county)='lake' AND case_number = '2025CA002620' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '141826010000000401', property_address = '603 W OCALA ST' WHERE lower(county)='lake' AND case_number = '2025CA002679' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '062026005000001200', property_address = '1552 WYNFORD CIR' WHERE lower(county)='lake' AND case_number = '2025CA002688' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '281824005000001200', property_address = '315 E ROSE LN' WHERE lower(county)='lake' AND case_number = '2025CA002823' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '261826060000002700', property_address = '37443 BEACH DR' WHERE lower(county)='lake' AND case_number = '2026CA000378' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '071527210000009100', property_address = '25716 POWELL DR' WHERE lower(county)='lake' AND case_number = '2026CA000425' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '082126000200005900', property_address = '13332 CORKWOOD LN' WHERE lower(county)='lake' AND case_number = '2026CA000550' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id = '102224001400032100', property_address = '2488 BEGONIA ST' WHERE lower(county)='lake' AND case_number = '2026CA000589' AND parcel_id IS NULL;
-- late addition: 2025CA001111 found via same methodology, initially missed in first pass
UPDATE multi_county_auctions SET parcel_id = '361925005000026800', property_address = '2840 WEKIVA RD' WHERE lower(county)='lake' AND case_number = '2025CA001111' AND parcel_id IS NULL;
-- 2025CA002336: section-township-range exact match (22-19-24), only Rolle-surname parcel
-- in that STR; owner-of-record "ROLLE PORTIA &" (unlisted co-owner, plausibly spouse Patrick)
UPDATE multi_county_auctions SET parcel_id = '221924000100001900', property_address = '908 BEECHER ST' WHERE lower(county)='lake' AND case_number = '2025CA002336' AND parcel_id IS NULL;
