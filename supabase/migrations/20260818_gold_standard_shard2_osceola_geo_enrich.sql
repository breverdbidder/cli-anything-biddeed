-- GOLD STANDARD shard-2 (dispatch d3ebfbe4): osceola geo/address/value backfill for 13
-- tax_deed rows that were auto-promoted today (via biddeed.flow_card_to_mca /
-- promote_upcoming_tier1_cards, pg_cron 'gold-calendar-parity-cycle') with real parcel_id
-- but no address/lat/lon/assessed_value.
--
-- Source: FL DOR Statewide Parcel Centroid ArcGIS FeatureServer
-- (services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Parcel_Centroid_Version/FeatureServer/0),
-- CO_NO=59 for Osceola (confirmed against the official FL DOR county-number map PDF).
-- Cross-validated against 4 rows that already had assessed_value stored -- AV_NSD field
-- matched exactly in all 4 before trusting the mapping for the other 9.
--
-- NOTE: this backfill improves data completeness but does NOT flip osceola's I or J
-- criteria -- the actual I-blocker for these 13 rows is a separate join requirement
-- (v_zoning_gold_standard_card / parcel_zones) that these parcels aren't populated in; a
-- ZoneWise zoning-ordinance ingestion gap, not a geo/address gap. See session report
-- GOLD_STANDARD_SHARD2_CALHOUN_GILCHRIST_WALTON_OSCEOLA_DISPATCH_D3EBFBE4_SESSION_REPORT.md.
--
-- Applied live via Supabase Management API during this session; this migration file
-- documents that already-applied change. COALESCE guards make re-running a no-op for
-- fields already populated.

UPDATE multi_county_auctions SET property_address = COALESCE(property_address, 'HOLOPAW GROVES RD, SAINT CLOUD, FL 34771'), latitude = 28.133208790529768, longitude = -81.18172744585546, assessed_value = COALESCE(assessed_value, 1800) WHERE case_number = '28622024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET property_address = COALESCE(property_address, 'BRACK ST, KISSIMMEE, FL 34744'), latitude = 28.30633001973833, longitude = -81.40237288598279, assessed_value = COALESCE(assessed_value, 41800) WHERE case_number = '28952024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET property_address = COALESCE(property_address, 'E CYPRESS ST, KISSIMMEE, FL 34744'), latitude = 28.30586242981037, longitude = -81.40236728802554, assessed_value = COALESCE(assessed_value, 41800) WHERE case_number = '28972024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET latitude = 28.183297380592105, longitude = -81.2773243268487 WHERE case_number = '59612024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET property_address = COALESCE(property_address, 'OCEAN ST, KISSIMMEE, FL 34744'), latitude = 28.308748897122538, longitude = -81.39381981925077, assessed_value = COALESCE(assessed_value, 42240) WHERE case_number = '29202024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET latitude = 28.13435962871, longitude = -81.05731294416763 WHERE case_number = '37342024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET latitude = 28.307720733947367, longitude = -81.44842343044682 WHERE case_number = '34492024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET latitude = 28.325231466588708, longitude = -81.32988653612537 WHERE case_number = '17532024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET property_address = COALESCE(property_address, 'HOLOPAW GROVES RD, SAINT CLOUD, FL 34771'), latitude = 28.096184983211963, longitude = -81.1639258638143, assessed_value = COALESCE(assessed_value, 1800) WHERE case_number = '61152024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET property_address = COALESCE(property_address, 'HOLOPAW GROVES RD, SAINT CLOUD, FL 34771'), latitude = 28.095051763726406, longitude = -81.1641677838136, assessed_value = COALESCE(assessed_value, 1800) WHERE case_number = '61212024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET latitude = 28.09346210930921, longitude = -81.16389235203155 WHERE case_number = '61362024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET property_address = COALESCE(property_address, 'OLD DIXIE HWY, KISSIMMEE, FL 34744'), latitude = 28.31270301189991, longitude = -81.40219480234528, assessed_value = COALESCE(assessed_value, 16651) WHERE case_number = '29462024' AND lower(county) = 'osceola';
UPDATE multi_county_auctions SET latitude = 28.095254034152315, longitude = -81.15905999671877 WHERE case_number = '61172024' AND lower(county) = 'osceola';
