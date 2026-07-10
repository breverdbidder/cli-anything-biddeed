-- Hernando County Tax Deed Parcel ID Backfill
-- Source: Hernando County PA GIS (services6.arcgis.com/HIgwINUB3SYLTb14)
--         Layer: Map/FeatureServer/3 (EPL Parcels)
-- Date: 2026-06-24
-- Confirmed: 7 of 10 TD auctions (70%)
-- Ambiguous (NOT updated): 2026-011TD (SHYLA RD - 2 candidates),
--                           2026-018TD (TAMER LN - 32 candidates),
--                           2026-030TD (AZALEA CIR - 8 candidates)
-- Source service: https://services6.arcgis.com/HIgwINUB3SYLTb14/arcgis/rest/services/Map/FeatureServer/3

UPDATE multi_county_auctions
SET parcel_id = 'R27 222 18 1474 0490 0090'
WHERE county = 'hernando' AND case_number = '2026-032TD';
-- 9009 CENTRAL AVE, BROOKSVILLE FL 34613 (1:1 exact match)

UPDATE multi_county_auctions
SET parcel_id = 'R22 222 19 2650 0010 0120'
WHERE county = 'hernando' AND case_number = '2024-077TD';
-- 224 W FORT DADE AVE, BROOKSVILLE FL 34601 (1:1 exact match)

UPDATE multi_county_auctions
SET parcel_id = 'R14 123 21 0382 0060 0110'
WHERE county = 'hernando' AND case_number = '2026-021TD';
-- 35010 FRASER ST, DADE CITY FL 33523 (1:1 exact match)

UPDATE multi_county_auctions
SET parcel_id = 'R04 223 19 3571 0003 0240'
WHERE county = 'hernando' AND case_number = '2026-022TD';
-- 19491 LILY POND CT, BROOKSVILLE FL 34601 (1:1 exact match)

UPDATE multi_county_auctions
SET parcel_id = 'R27 222 18 1474 0740 0080'
WHERE county = 'hernando' AND case_number = '2026-023TD';
-- 8187 FORTUNE HUNTER DR, BROOKSVILLE FL 34613 (1:1 exact match)

UPDATE multi_county_auctions
SET parcel_id = 'R29 222 18 2500 0070 0160'
WHERE county = 'hernando' AND case_number = '2026-024TD';
-- 7403 HIGHPOINT BLVD, BROOKSVILLE FL 34613 (1:1 exact match)

UPDATE multi_county_auctions
SET parcel_id = 'R01 221 17 3330 0227 0030'
WHERE county = 'hernando' AND case_number = '2026-029TD';
-- 12220 MARVELWOOD RD, WEEKI WACHEE FL 34614 (1:1 exact match)

-- AMBIGUOUS - requires manual verification against realtaxdeed case files:
-- 2026-011TD: SHYLA RD, BROOKSVILLE - candidates:
--   R14 223 19 2700 0090 0210 (ODONNELL CHAS P, Atlanta GA, 0.5 ac, MAURINE PLACE BLK 9 LOTS 21-30)
--   R14 223 19 2700 0090 0010 (PUCKETT C O MRS, Holiday FL, 0.2 ac, MAURINE PLACE BLK 9 LOTS 1 2 31 32)
--
-- 2026-018TD: TAMER LN, DADE CITY - 32 vacant lot candidates in Talisman Estates subdivision
--
-- 2026-030TD: AZALEA CIR, DADE CITY - 8 candidates in Lakewood Unit 3 subdivision
