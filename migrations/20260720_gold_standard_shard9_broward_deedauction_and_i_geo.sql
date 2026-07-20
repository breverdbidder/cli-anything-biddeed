-- GOLD STANDARD shard-9 (dispatch 20a33672), 4th firing 2026-07-20
-- broward Letter A + Letter I real fixes.
--
-- A: pipeline.counties.taxdeed_platform/taxdeed_url was pointing at
-- broward.realtaxdeed.com (RealAuction), which is the WRONG platform for
-- broward tax deeds -- verified live 2026-07-20 that broward.realtaxdeed.com
-- renders zero CALBOX auction-day cells Jul-Dec 2026 (a real, honest zero;
-- confirmed by diffing against alachua.realtaxdeed.com, which DOES render a
-- real scheduled-day cell anonymously) and its own "Jump To" county list has
-- no "Broward Taxdeed" entry. The real platform is broward.deedauction.net
-- (Grant Street Group), confirmed live via its anonymous /auctions/upcoming
-- JSON endpoint (auction id=112, 10/26/2026 sale, 17 items). Two prior
-- sessions misdiagnosed this as a bot block and fabricated a synthetic
-- tax_deed seed row instead (caught + reverted twice, see f9cf6890).
--
-- I: 11 of broward's 42 card-incomplete rows have a real, resolvable folio
-- and already have address+value+zoning -- only latitude/longitude was
-- missing, and fl_parcels (already ingested via the FL GIO statewide
-- cadastral pipeline) has real centroid data for all 11. Straight backfill,
-- no fabrication.

UPDATE pipeline.counties
SET taxdeed_platform = 'deedauction',
    taxdeed_url = 'https://broward.deedauction.net/auctions'
WHERE county_slug = 'broward';

UPDATE multi_county_auctions mca
SET latitude = fp.centroid_lat,
    longitude = fp.centroid_lng
FROM fl_parcels fp
WHERE mca.parcel_id = fp.parcel_id
  AND lower(mca.county) = 'broward'
  AND mca.latitude IS NULL
  AND fp.centroid_lat IS NOT NULL;
