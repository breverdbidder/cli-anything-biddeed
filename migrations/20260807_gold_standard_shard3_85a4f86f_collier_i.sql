-- GOLD STANDARD shard-3 (dispatch 85a4f86f-993f-40c0-9095-47ac8d01a6e5) — collier I
-- card_complete baseline 91.4% (203/222), gap=19 rows, all collier_clerk_laserfiche
-- tax-deed rows harvested from the clerk's Laserfiche repo with zero enrichment. Reused the
-- precedent pipeline from scripts/gold_standard_shard1_collier_i_enrichment.py and
-- migrations/20260711_gold_standard_shard1_collier_i_zoning_gis_wiring.sql (targeted at just
-- the 19 gap rows, not a full re-run): FL DOR statewide cadastral (CO_NO=21) for
-- address/geo/value, Collier's Zoning_General_(Editable)_view FeatureServer for real
-- point-in-polygon zone_code. Also recovered parcel_id for case 24-CA-2240 via exact
-- PHY_ADDR1 match against fl_parcels.
--
-- Result (adversarially verified): I 91.4% -> 93.7%, still FAIL (<95% threshold).
--
-- 14 residual rows honestly documented as a likely real-data floor, not a scraping gap:
--   - 2 confirmed Oil/Gas/Mineral-rights sub-parcels (legal_description quotes "% O G & M
--     RIGHTS") — structurally outside the surface cadastral layer's scope.
--   - 1 likely-truncated 8-digit folio (78698105) vs the real 11-digit Valencia Lakes
--     pattern — not guess-reconstructed among many candidate lots.
--   - 4 more folios with zero match in FL GIO cadastral or the local fl_parcels mirror.
--   - 5 real vacant-land parcels with confirmed-blank DOR-recorded situs address.
--   - 2 parcels inside Everglades City (incorporated; county zoning layer returns
--     BASE='CITY', Everglades City's own municipal zoning layer not discovered this session).

SET statement_timeout = 0;

UPDATE multi_county_auctions SET latitude = 25.979902758758136, longitude = -81.74638320240174, market_value = 14945, assessed_value = 14945 WHERE id = '3f2aa181-4a46-490a-b71b-ab7ef561d3b8' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL;
UPDATE multi_county_auctions SET latitude = 25.96589390461036, longitude = -81.42350566512573, market_value = 1500, assessed_value = 1500 WHERE id = 'c447f14c-b5e3-477f-839c-b292a575d755' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL;
UPDATE multi_county_auctions SET latitude = 25.970592150368812, longitude = -81.44488196345321, market_value = 3756, assessed_value = 3756 WHERE id = '42e1b0c6-aa27-4629-abf1-c1db5ded4a88' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL;
UPDATE multi_county_auctions SET latitude = 25.9594792638002, longitude = -81.38428059557366, market_value = 3000, assessed_value = 3000 WHERE id = 'ff2da4c4-aaf3-4903-b999-2d4fb1700087' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL;
UPDATE multi_county_auctions SET latitude = 25.945881093605102, longitude = -81.24543534395511, market_value = 3100, assessed_value = 3100 WHERE id = 'dc7af71d-0db5-4942-baec-661857785252' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL;
UPDATE multi_county_auctions SET latitude = 25.95734047200829, longitude = -81.5110214479387, market_value = 47408, assessed_value = 47408, property_address = '525 NEWPORT DR, NAPLES, FL 34114' WHERE id = '428e3119-8c60-4739-8c2d-750fc2658113' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL AND property_address IS NULL;
UPDATE multi_county_auctions SET latitude = 25.957340472008298, longitude = -81.51102144793873, market_value = 47408, assessed_value = 47408, property_address = '525 NEWPORT DR, NAPLES, FL 34114' WHERE id = 'db69671f-7f4b-446c-8cc8-9a8fa8bfcd22' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL AND property_address IS NULL;
UPDATE multi_county_auctions SET latitude = 25.957340472008298, longitude = -81.51102144793873, market_value = 47408, assessed_value = 47408, property_address = '525 NEWPORT DR, NAPLES, FL 34114' WHERE id = '0fc58d8a-509b-4e2a-9a63-8d7d48e2e69f' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL AND property_address IS NULL;
UPDATE multi_county_auctions SET latitude = 26.412892217116372, longitude = -81.41586353847195, market_value = 51693, assessed_value = 51693, property_address = '407 GAUNT ST, IMMOKALEE, FL 34142' WHERE id = 'ca127a27-d804-455c-878e-d1f198c55287' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL AND property_address IS NULL;
UPDATE multi_county_auctions SET latitude = 25.857079402111786, longitude = -81.38329169532305, market_value = 45955, assessed_value = 45955 WHERE id = '11119d3c-aed0-4ff0-a5d9-a35010275719' AND latitude IS NULL AND market_value IS NULL AND assessed_value IS NULL;

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES
  ('01086400005','01086400005',632,'CON','Conservation','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.423506,25.965894:2026-08-07'),
  ('01097520000','01097520000',632,'CON','Conservation','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.444882,25.970592:2026-08-07'),
  ('01123320006','01123320006',632,'CON','Conservation','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.384281,25.959479:2026-08-07'),
  ('01153280006','01153280006',632,'CON','Conservation','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.245435,25.945881:2026-08-07'),
  ('68270001936','68270001936',632,'C-4','General Commercial','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511021,25.957340:2026-08-07'),
  ('68270002155','68270002155',632,'C-4','General Commercial','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511021,25.957340:2026-08-07'),
  ('68270002197','68270002197',632,'C-4','General Commercial','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511021,25.957340:2026-08-07'),
  ('56403960005','56403960005',632,'RMF-6','Residential Multi-Family 6','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.415864,26.412892:2026-08-07'),
  ('0745160001','0745160001',632,'A','Agricultural','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.746383,25.979903:2026-08-07')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET zone_code=EXCLUDED.zone_code, zone_name=EXCLUDED.zone_name, source=EXCLUDED.source;

UPDATE multi_county_auctions SET parcel_id='29731320001', latitude=26.1922731793358, longitude=-81.7957362590762, market_value=1020904, assessed_value=1020904 WHERE id='e82ce4e0-f92f-4c0b-844b-714eb7dbe6f6' AND parcel_id IS NULL AND latitude IS NULL;

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES
  ('29731320001','29731320001',632,'RSF-4','Residential Single Family 4','collier_gis_live:Zoning_General/FeatureServer/1:point=-81.795736,26.192273:2026-08-07')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET zone_code=EXCLUDED.zone_code, zone_name=EXCLUDED.zone_name, source=EXCLUDED.source;
