-- Gold Standard shard-1 (bradford): fix I (card_complete) via verified geo-coordinates
-- and assessed/market values for the 4 Bradford parcels with a real parcel_id.
--
-- Source: Bradford County Property Appraiser GIS (bradfordappraiser.com/gis/),
-- EPSG:2238 (FL East NAD83 ftUS) raw coordinates transformed to WGS84 via pyproj.
-- Cross-validated against Brooker, FL town-center public coordinates and an
-- independent WebSearch confirmation of the Lake Butler parcel's address.
-- All 4 facts VERIFIED per research findings (2026-07-19 session).
--
-- E (case 25000439CAAXMX parcel_id) NOT included: research found no parcel_id
-- or street address for that case from any accessible source (bradfordclerk.com
-- Cloudflare-blocked, Bradford Appraiser GIS has no owner/STR search, OCRS
-- login-gated). Reported as residual_gap, not fabricated.
--
-- B/F (case 25000457CAAXMX sale result) NOT included: BLOCKED, no verified
-- winning bid found (bradfordclerk.com Cloudflare-blocked, OCRS login-gated,
-- firecrawl out of credits). Reported as residual_gap, not fabricated.

UPDATE multi_county_auctions
SET latitude = 29.889278,
    longitude = -82.332406,
    assessed_value = 104963,
    market_value = 122237
WHERE lower(county) = 'bradford'
  AND parcel_id = '00273-0-01000';

UPDATE multi_county_auctions
SET latitude = 29.903524,
    longitude = -82.171905,
    assessed_value = 63475,
    market_value = 63475
WHERE lower(county) = 'bradford'
  AND parcel_id = '00868-0-01801';

UPDATE multi_county_auctions
SET latitude = 29.857819,
    longitude = -82.264472,
    assessed_value = 127511,
    market_value = 210787
WHERE lower(county) = 'bradford'
  AND parcel_id = '00441-0-00100';

UPDATE multi_county_auctions
SET property_address = '19604 NW 122ND AVE, LAKE BUTLER, FL 32054',
    latitude = 30.001321,
    longitude = -82.24932,
    assessed_value = 43303,
    market_value = 43303
WHERE lower(county) = 'bradford'
  AND parcel_id = '00077-0-00401';
