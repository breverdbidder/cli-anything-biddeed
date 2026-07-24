-- Gold Standard shard-3 (jackson/wakulla), dispatch da3fde1c-5c12-4786-bbda-4ea2708ee2e1, loop run 6253.
-- Fan-out research (5 parallel agents) + adversarial refutation via Workflow, all live sources cited below.
--
-- JACKSON (letters E/I): 2 orphan foreclosure rows had NULL parcel_id/property_address and a
-- placeholder lat/lon (30.7345/-85.2148, identical for both rows). Resolved via PropertyOnion's
-- public case-number lookup (address only -- their lat/lon endpoint is gated 401 and was REFUTED
-- during adversarial verification, so NOT used here) cross-referenced against a live, independently
-- re-run FL DOR Statewide Cadastral ArcGIS query (services9.arcgis.com/Gh9awoU677aKree0/.../
-- Florida_Statewide_Cadastral/FeatureServer/0) for parcel_id + a self-computed polygon centroid
-- (returnGeometry=true&outSR=4326, ring-average) for lat/lon -- this centroid is our own VERIFIED
-- source, not the refuted PropertyOnion figure (though the two agree to within ~250m, corroborating).
-- NOTE: letter I still does NOT pass for these 2 rows -- neither parcel matches any parcel_zones
-- row (checked live, zero rows), and extensive research this session found Jackson County's
-- unincorporated area (which both parcels fall in, per city name alone being an unreliable signal --
-- see Compass Lakehills finding below) uses Future Land Use categories, not zoning districts, per
-- the county's own Planning Division -- so no zone_code may exist to assign. Not fabricated.
-- The other 10 jackson I-failing rows (8 Marianna/Compass Lakehills + Campbellton + Sneads
-- parcel_zones gaps) remain UNRESOLVED this session -- see closeout report for the honest ceiling
-- and per-parcel source-exhaustion detail. No zone_code guessed for any of them.
UPDATE multi_county_auctions
   SET property_address = '4624 MAGNOLIA RD, MARIANNA, FL 32448',
       parcel_id = '234N10000000500000',
       latitude = 30.725114289064365,
       longitude = -85.211132190514
 WHERE lower(county) = 'jackson' AND case_number = '322025CC000895CCAXMX';

UPDATE multi_county_auctions
   SET property_address = '4032 WINTERGREEN RD, GREENWOOD, FL 32443',
       parcel_id = '065N08000000700040',
       latitude = 30.857605180859924,
       longitude = -85.077001032422
 WHERE lower(county) = 'jackson' AND case_number = '322025CA000120CAAXMX';

-- WAKULLA (letters I/E): every one of the 30 live wakulla auctions had NULL property_address,
-- NULL lat/lon, and NULL assessed_value/market_value (100% enrichment gap -- this, not zoning,
-- was the actual card_complete=0/30 root cause; zoning already covered 20/30 parcels going in).
-- All values below are from two live ArcGIS FeatureServer sources, each re-queried independently
-- during adversarial verification and confirmed to reproduce exactly (75/75 findings survived):
--   (1) FL DOR Statewide Cadastral (services9.arcgis.com/Gh9awoU677aKree0/.../Florida_Statewide_
--       Cadastral/FeatureServer/0, filtered CO_NO=75) for property_address + JV (just/market value)
--       + AV_SD (assessed value, school-district cap) + assessment year 2025.
--   (2) Wakulla_Parcels FeatureServer (services.arcgis.com/yghUoIoA2Cd2cWki/.../Wakulla_Parcels/
--       FeatureServer/0, returnCentroid=true&outSR=4326) for a true WGS84 parcel centroid lat/lon.
-- assessed_value is set to AV_SD (county assessed/capped value) and market_value to JV (just value)
-- to match the semantic meaning of each column.
UPDATE multi_county_auctions SET property_address='KLICKITAT DR, CRAWFORDVILLE, FL 32327', assessed_value=9500, market_value=9500, latitude=30.169083957531292, longitude=-84.30588585158904 WHERE lower(county)='wakulla' AND parcel_id='00-00-043-010-08943-000';
UPDATE multi_county_auctions SET property_address='FRANKLIN DR, CRAWFORDVILLE, FL 32327', assessed_value=13000, market_value=13000, latitude=30.104757395928115, longitude=-84.39670113969746 WHERE lower(county)='wakulla' AND parcel_id='26-4s-02w-022-02204-000';
UPDATE multi_county_auctions SET property_address='FRANKLIN DR, CRAWFORDVILLE, FL 32327', assessed_value=13000, market_value=13000, latitude=30.10778127553697, longitude=-84.39718216632005 WHERE lower(county)='wakulla' AND parcel_id='26-4s-02w-022-02220-000';
UPDATE multi_county_auctions SET property_address='SOPCHOPPY HWY, SOPCHOPPY, FL 32358', assessed_value=7500, market_value=7500, latitude=30.063716939949984, longitude=-84.47057621868137 WHERE lower(county)='wakulla' AND parcel_id='07-5S-02W-000-02638-000';
UPDATE multi_county_auctions SET property_address='COMANCHE TRL, CRAWFORDVILLE, FL 32327', assessed_value=18500, market_value=18500, latitude=30.179939755804195, longitude=-84.30383032467063 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-06854-000';
UPDATE multi_county_auctions SET property_address='CHOCTAW RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.18571595854109, longitude=-84.3031364264758 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07276-000';
UPDATE multi_county_auctions SET property_address='CHOCTAW RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.180163277209743, longitude=-84.30114385874585 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07344-000';
UPDATE multi_county_auctions SET property_address='RENEGADE RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.185789305991314, longitude=-84.30233391536316 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07474-000';
UPDATE multi_county_auctions SET property_address='NEELEY RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.189012718745015, longitude=-84.30266184951074 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07526-000';
UPDATE multi_county_auctions SET property_address='NEELEY RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.183460032646572, longitude=-84.30066924206746 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07597-000';
UPDATE multi_county_auctions SET property_address='ROCHELSIE RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.18554222546699, longitude=-84.30058759193923 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07761-000';
UPDATE multi_county_auctions SET property_address='ROCHELSIE RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.187240019668526, longitude=-84.30069953509185 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07784-000';
UPDATE multi_county_auctions SET property_address='CHICOPEE RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.188240628811847, longitude=-84.3007270654625 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07816-000';
UPDATE multi_county_auctions SET property_address='ROCHELSIE RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.18339360615442, longitude=-84.29931931497973 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07862-000';
UPDATE multi_county_auctions SET property_address='CHICOPEE RD, CRAWFORDVILLE, FL 32327', assessed_value=8000, market_value=8000, latitude=30.184131708225, longitude=-84.2992526369777 WHERE lower(county)='wakulla' AND parcel_id='00-00-035-008-07878-000';
UPDATE multi_county_auctions SET property_address='DR MLK JR MEMORIAL RD, CRAWFORDVILLE, FL 32327', assessed_value=12000, market_value=12000, latitude=30.179040884417482, longitude=-84.36348818193538 WHERE lower(county)='wakulla' AND parcel_id='00-00-077-014-10391-000';
UPDATE multi_county_auctions SET property_address='TED LOTT LN, CRAWFORDVILLE, FL 32327', assessed_value=16500, market_value=16500, latitude=30.169088274982105, longitude=-84.36314038748507 WHERE lower(county)='wakulla' AND parcel_id='00-00-078-013-11303-000';
UPDATE multi_county_auctions SET property_address='90 SPOKAN TRL, CRAWFORDVILLE, FL 32327', assessed_value=191335, market_value=191335, latitude=30.177856855288105, longitude=-84.30513964610402 WHERE lower(county)='wakulla' AND parcel_id='00-00-034-009-08162-000';
UPDATE multi_county_auctions SET property_address='30 CHICKAT TRL, CRAWFORDVILLE, FL 32327', assessed_value=147928, market_value=147928, latitude=30.172345177200516, longitude=-84.29925755389483 WHERE lower(county)='wakulla' AND parcel_id='00-00-034-012-09571-064';
UPDATE multi_county_auctions SET property_address='78 WHITLOCK WAY, CRAWFORDVILLE, FL 32327', assessed_value=109516, market_value=192255, latitude=30.23264192124809, longitude=-84.35893816172693 WHERE lower(county)='wakulla' AND parcel_id='08-3s-01w-208-04334-028';
UPDATE multi_county_auctions SET property_address='1705 DR MLK JR MEMORIAL RD, CRAWFORDVILLE, FL 32327', assessed_value=152528, market_value=152528, latitude=30.173726888475514, longitude=-84.29486235602782 WHERE lower(county)='wakulla' AND parcel_id='00-00-034-012-09631-001';
UPDATE multi_county_auctions SET property_address='1031 SHADEVILLE RD, CRAWFORDVILLE, FL 32327', assessed_value=51839, market_value=56287, latitude=30.19301139514101, longitude=-84.32790768231251 WHERE lower(county)='wakulla' AND parcel_id='00-00-054-000-09911-001';
UPDATE multi_county_auctions SET property_address='28 CLOER LN, CRAWFORDVILLE, FL 32327', assessed_value=154485, market_value=157708, latitude=30.17205979957815, longitude=-84.35957001627196 WHERE lower(county)='wakulla' AND parcel_id='00-00-078-013-10734-000';
UPDATE multi_county_auctions SET assessed_value=112763, market_value=112763, latitude=30.28617654875171, longitude=-84.38353017670087 WHERE lower(county)='wakulla' AND parcel_id='25-2S-02W-000-01425-003';
UPDATE multi_county_auctions SET assessed_value=356221, market_value=356221, latitude=30.20011087834846, longitude=-84.33616995210647 WHERE lower(county)='wakulla' AND parcel_id='00-00-055-422-19932-088';

-- WAKULLA letter E (parcel linkage): 2 foreclosure cases had NULL parcel_id. Resolved by
-- cross-referencing the Wakulla Clerk's live public foreclosure-sale list
-- (wakullaclerk.org/courts/foreclosures.php, defendant/case/date/amount) against the same live
-- Wakulla parcel-appraisal ArcGIS layer (Zoning_Pro/FeatureServer/3, OWNER_NAME field), each an
-- unambiguous single-match on defendant surname -- both re-confirmed independently during
-- adversarial verification and again live here while authoring this migration (address/value
-- enrichment + zone via point-in-polygon against Zoning_Pro/FeatureServer/0, Sec. 5-27/5-43 LDC).
UPDATE multi_county_auctions SET parcel_id='00-00-036-103-09671-034', property_address='27 LESLIE CIR, CRAWFORDVILLE, FL 32327', assessed_value=138817, market_value=138817, latitude=30.19148745944266, longitude=-84.31077933507305 WHERE lower(county)='wakulla' AND case_number='23-CA-627';
UPDATE multi_county_auctions SET parcel_id='00-00-077-014-10524-021', property_address='24 BREWSTER RD, CRAWFORDVILLE, FL 32327', assessed_value=128002, market_value=188181, latitude=30.173304586420183, longitude=-84.36526941696809 WHERE lower(county)='wakulla' AND case_number='24-CA-130';

-- 25-CA-50: case-to-parcel link is INFERRED, not VERIFIED -- the Clerk's case-search docket is
-- Cloudflare-Turnstile-gated and could not be queried directly. The link rests on defendant
-- "Miranda Storm West" being the sole WEST+MIRANDA owner-name combination in the entire county
-- parcel dataset (re-confirmed live: combined AND query returns exactly 1 row). Recorded because
-- the evidence is a genuine unique cross-reference, not a guess, but flagged here for a human/
-- next-session docket check before this case is treated as certain.
UPDATE multi_county_auctions SET parcel_id='00-00-056-405-09946-041', property_address='105 WINDSOR WAY, CRAWFORDVILLE, FL 32327', assessed_value=348837, market_value=348837, latitude=30.20935734889185, longitude=-84.33453559450183 WHERE lower(county)='wakulla' AND case_number='25-CA-50';
-- 25-CA-68 (2 same-owner-name candidate parcels, could not disambiguate without the docket legal
-- description) and 2026-TXD-097 (not found on the Clerk's live tax-deed page, legacy page, or Tax
-- Collector site) are intentionally left NULL -- not guessed.

-- Zoning linkage for the newly-enriched Unincorporated Wakulla parcels (jurisdiction_id=1402),
-- from the live Wakulla County Zoning GIS (Zoning_Pro/FeatureServer/0, CUR_ZONING field, Wakulla
-- LDC sections cited), point-in-polygon on each parcel's centroid, re-verified during adversarial
-- refutation for the first 5 and again live while authoring this migration for the 3 orphan-linked
-- parcels below.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('26-4s-02w-022-02204-000', 1402, 'RR5', 'Rural Residential District', 'wakulla_zoning_pro_gis:shard3_run6253'),
  ('26-4s-02w-022-02220-000', 1402, 'RR5', 'Rural Residential District', 'wakulla_zoning_pro_gis:shard3_run6253'),
  ('07-5S-02W-000-02638-000', 1402, 'C2', 'General Commercial District', 'wakulla_zoning_pro_gis:shard3_run6253'),
  ('25-2S-02W-000-01425-003', 1402, 'RR1', 'Semi-Rural Residential District', 'wakulla_zoning_pro_gis:shard3_run6253'),
  ('00-00-055-422-19932-088', 1402, 'PUD', 'Planned Unit Development', 'wakulla_zoning_pro_gis:shard3_run6253'),
  ('00-00-036-103-09671-034', 1402, 'RR1', 'Semi-Rural Residential District', 'wakulla_zoning_pro_gis:shard3_run6253'),
  ('00-00-077-014-10524-021', 1402, 'RMH1', 'Mobile Home Residential District', 'wakulla_zoning_pro_gis:shard3_run6253'),
  ('00-00-056-405-09946-041', 1402, 'PUD', 'Planned Unit Development', 'wakulla_zoning_pro_gis:shard3_run6253')
ON CONFLICT DO NOTHING;
