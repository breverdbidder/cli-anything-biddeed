-- santa_rosa E (parcel linkage) + I (card completeness) fix
-- run: santa_rosa E=92.1% (70/76) -> target 73+/76; I=69.7% (53/76) -> target 73+/76
--
-- Sources (all VERIFIED, no fabrication):
--   E: public.realforeclose_aids (real RealForeclose scrape rows) cross-verified against
--      public.fl_parcels (co_no=67 = Santa Rosa, statewide DOR cadastral) by exact
--      parcel_id + address match. jv/av_sd from fl_parcels matches judgment/assessed
--      figures independently scraped into realforeclose_aids.
--   I (assessed_value gap, 4 rows): public.fl_parcels co_no=67, exact parcel_id match
--      (parcel_id already present on the row from a prior E fix; value was the only gap).
--   I (lat/lng gap, 15 rows): US Census Bureau Geocoder
--      (geocoding.geo.census.gov/geocoder/locations/onelineaddress, benchmark=Public_AR_Current),
--      TIGER-line address-range match verified against matchedAddress in the response.
--
-- NOT fixed (reported, not fabricated):
--   572025CA000043CAAXMX - no realforeclose_aids address ("MULTIPLE PARCELS"), no fl_parcels match possible
--   572025CA000445CAAXMX - no realforeclose_aids address (parcel_id="Property Appraiser" placeholder)
--   572022CA000671CAAXMX - no row in realforeclose_aids at all, no address anywhere
--   572026CC000065CCAXMX - "120 BAYBRIDGE DR G" (condo unit) - zero Census TIGER matches,
--                           tried with and without unit suffix

BEGIN;

-- ── E: parcel_id backfill (3 rows) ──────────────────────────────────────────

UPDATE multi_county_auctions
SET parcel_id = '21-2S-26-0780-0WW00-0220',
    assessed_value = 212562.00,
    latitude = 30.413410276236,
    longitude = -86.805467047464,
    assessed_value_source = 'fl_parcels_co67'
WHERE county = 'santa_rosa' AND case_number = '572016CA000376CAAXMX';

UPDATE multi_county_auctions
SET parcel_id = '23-2S-27-2357-00D00-0010',
    property_address = '2052 ALFRED BLVD, NAVARRE, FL- 32566',
    assessed_value = 368785.00,
    latitude = 30.410806036442,
    longitude = -86.920699599175,
    assessed_value_source = 'fl_parcels_co67'
WHERE county = 'santa_rosa' AND case_number = '572025CA000353CAAXMX';

UPDATE multi_county_auctions
SET parcel_id = '33-2N-27-0000-00159-0000',
    assessed_value = 63490.00,
    latitude = 30.629613072953,
    longitude = -86.961213036847,
    assessed_value_source = 'fl_parcels_co67'
WHERE county = 'santa_rosa' AND case_number = '572024CA000662CAAXMX';

-- ── I: assessed_value backfill from fl_parcels (parcel_id already present) ──

UPDATE multi_county_auctions
SET assessed_value = 169750.00,
    assessed_value_source = 'fl_parcels_co67'
WHERE county = 'santa_rosa' AND case_number = '2026092' AND parcel_id = '23-1N-29-1210-05800-0080';

UPDATE multi_county_auctions
SET assessed_value = 100228.00,
    assessed_value_source = 'fl_parcels_co67'
WHERE county = 'santa_rosa' AND case_number = '2026099' AND parcel_id = '10-1N-28-0870-00200-0041';

UPDATE multi_county_auctions
SET assessed_value = 42614.00,
    assessed_value_source = 'fl_parcels_co67'
WHERE county = 'santa_rosa' AND case_number = '2026101' AND parcel_id = '18-1N-28-0000-00460-0000';

-- ── I: lat/lng backfill via US Census Geocoder (15 rows) ────────────────────

UPDATE multi_county_auctions SET latitude = 30.966461158807, longitude = -87.138176928742
WHERE county = 'santa_rosa' AND case_number = '2026075';

UPDATE multi_county_auctions SET latitude = 30.369082095951, longitude = -87.173619802924
WHERE county = 'santa_rosa' AND case_number = '2026077';

UPDATE multi_county_auctions SET latitude = 30.579631843086, longitude = -87.02718028633
WHERE county = 'santa_rosa' AND case_number = '2026082';

UPDATE multi_county_auctions SET latitude = 30.951584000275, longitude = -87.147060244902
WHERE county = 'santa_rosa' AND case_number = '2026085';

UPDATE multi_county_auctions SET latitude = 30.594362586072, longitude = -87.161219626082
WHERE county = 'santa_rosa' AND case_number = '2026092';

UPDATE multi_county_auctions SET latitude = 30.613931254696, longitude = -87.036569258433
WHERE county = 'santa_rosa' AND case_number = '2026099';

UPDATE multi_county_auctions SET latitude = 30.588865107042, longitude = -87.095579777074
WHERE county = 'santa_rosa' AND case_number = '2026101';

UPDATE multi_county_auctions SET latitude = 30.380846110262, longitude = -87.063605291855
WHERE county = 'santa_rosa' AND case_number = '572025CA000212CAAXMX';

UPDATE multi_county_auctions SET latitude = 30.386624144194, longitude = -87.048703831704
WHERE county = 'santa_rosa' AND case_number = '572025CA000298CAAXMX';

UPDATE multi_county_auctions SET latitude = 30.637760464322, longitude = -87.051702200858
WHERE county = 'santa_rosa' AND case_number = '572025CA000543CAAXMX';

UPDATE multi_county_auctions SET latitude = 30.633570042227, longitude = -87.047437553367
WHERE county = 'santa_rosa' AND case_number = '572025CA000544CAAXMX';

UPDATE multi_county_auctions SET latitude = 30.644876735084, longitude = -87.16998160491
WHERE county = 'santa_rosa' AND case_number = '572025CA000756CAAXMX';

UPDATE multi_county_auctions SET latitude = 30.594061299568, longitude = -87.120501823857
WHERE county = 'santa_rosa' AND case_number = '572025CA000772CAAXMX';

UPDATE multi_county_auctions SET latitude = 30.618224940335, longitude = -87.069758773199
WHERE county = 'santa_rosa' AND case_number = '572025CA000801CAAXMX';

UPDATE multi_county_auctions SET latitude = 30.630791697653, longitude = -87.127378192989
WHERE county = 'santa_rosa' AND case_number = '572026CC000629CCAXMX';

COMMIT;
