-- SHARD-9 run3497 (dispatch 97977765-5157-4919-b206-11f8e29045e3)
-- Criterion I (card_complete) backfill for putnam: 2 rows had a real, known
-- parcel_id and address but NULL lat/long/assessed_value. Backfilled from
-- Putnam County's own ArcGIS FeatureServer (pamap.putnam-fl.gov, CadastralData
-- FeatureServer/2), the county's authoritative first-party CAMA data source --
-- not a scrape, not an estimate. Verified live this session (fetched
-- 2026-07-10), then independently re-fetched by an adversarial refuter agent
-- against the same source_url: parcel_id, site address, owner, land value,
-- and assessed value all matched exactly; lat/long (parcel-polygon centroid,
-- ring-vertex-averaged, NOT a rooftop geocode -- documented as such) matched
-- to 6+ decimal places. refuted=false.
--
-- Small, real, non-ghost improvement: does not by itself flip putnam I over
-- the 95% threshold (220/239 -> 222/239 = 92.9%, still short of 227 needed).

UPDATE multi_county_auctions
SET assessed_value = 135840,
    latitude = 29.40490862591114,
    longitude = -81.60273042642326
WHERE case_number = '542025CA000332CAAXMX'
  AND lower(county) = 'putnam'
  AND parcel_id = '31-12-27-7227-0170-0130';

UPDATE multi_county_auctions
SET assessed_value = 115170,
    latitude = 29.64930956239177,
    longitude = -81.86038095693905
WHERE case_number = '542026CA000135CAAXMX'
  AND lower(county) = 'putnam'
  AND parcel_id = '01-10-24-4075-2310-0110';
