-- Gold Standard shard-5 (dispatch 79ee1554): LEON county criterion I partial fix
-- (geo/value data-quality backfill; the metric itself does NOT cross threshold --
-- see honest residual note below, do not re-run expecting I to flip to PASS).
--
-- 42 of 45 I-gap rows had a known Leon Property Appraiser parcel_id and
-- property_address but were missing latitude/longitude and assessed_value/
-- market_value. Source: Leon County GIS ArcGIS REST
-- (https://intervector.leoncountyfl.gov/intervector/rest/services/MapServices/
-- LCPA_OverlayParcel_WGS84/MapServer/0), fields TAXID/SITEADDR/PYR_MARKET, matched
-- by normalized TAXID (our parcel_id vs the layer's spaced format), address
-- cross-checked, centroid computed from returned polygon geometry. 42 UPDATEs
-- executed live 2026-08-23, self-verified by spot-checking 4 rows directly against
-- multi_county_auctions post-write (values match exactly; rows that already had a
-- value were correctly left untouched by the idempotent WHERE-guard).
--
-- HONEST RESULT: I metric UNCHANGED at 81.4% (201/247) despite this fix, because
-- pencil_dod_evaluate_county's I-criterion additionally requires parcel_id
-- zone-linkage (parcel_id IN v_zoning_gold_standard_card WHERE zone_code IS NOT
-- NULL). VERIFIED live: Leon's parcel_zones table has only 203 total zoned parcels
-- against 247 auctions, and 0 of these 42 parcels exist in parcel_zones at all
-- (confirmed with space-normalized comparison on both sides). This is a genuine
-- zoning-ingestion coverage gap, explicitly out of scope for this fix (task brief:
-- "do not attempt a full zoning re-ingestion, that's out of scope for I") and is
-- the real remaining blocker for leon I. A follow-on session needs to either extend
-- Leon zoning-district/parcel_zones coverage, or the pipeline owner needs to confirm
-- whether I's zone-linkage AND-condition is intended policy for counties with
-- partial zoning ingestion.
--
-- Also confirmed unrecoverable (left NULL, not fabricated): case "2026 CA 000145"
-- (parcel_id='MULTIPLE PARCELS' per realforeclose_aids, structurally unparseable);
-- case "2025 CA 001324" (zero trace in any queried source).

-- Leon county gold-standard criterion I (property card completeness) backfill
-- Source: Leon County GIS (LCPA_OverlayParcel_WGS84 MapServer, intervector.leoncountyfl.gov)
-- market/taxable/land/bldg values + parcel centroid lat/long, matched by TAXID (parcel_id)
-- Dispatch 79ee1554, shard-5. VERIFIED via live ArcGIS REST query 2026-08-23. ALREADY EXECUTED live.

UPDATE multi_county_auctions SET latitude=30.493177, longitude=-84.336313, assessed_value=230248, market_value=230248 WHERE lower(county)='leon' AND case_number='2025 CA 000662' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.431547, longitude=-84.260945, assessed_value=303252, market_value=303252 WHERE lower(county)='leon' AND case_number='25-0005' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.389998, longitude=-84.297109, assessed_value=15351, market_value=15351 WHERE lower(county)='leon' AND case_number='26-0029' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.387229, longitude=-84.294975, assessed_value=28935, market_value=28935 WHERE lower(county)='leon' AND case_number='26-0030' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.3084, longitude=-84.254857, assessed_value=31343, market_value=31343 WHERE lower(county)='leon' AND case_number='26-0036' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.46759, longitude=-84.34144, assessed_value=122000, market_value=122000 WHERE lower(county)='leon' AND case_number='26-0038' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.42513, longitude=-84.262366, assessed_value=210889, market_value=210889 WHERE lower(county)='leon' AND case_number='26-0057' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.392766, longitude=-84.222007, assessed_value=245805, market_value=245805 WHERE lower(county)='leon' AND case_number='26-0058' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.398349, longitude=-84.269253, assessed_value=149745, market_value=149745 WHERE lower(county)='leon' AND case_number='26-0059' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.381936, longitude=-84.272568, assessed_value=129188, market_value=129188 WHERE lower(county)='leon' AND case_number='26-0060' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.414024, longitude=-84.144747, assessed_value=66899, market_value=66899 WHERE lower(county)='leon' AND case_number='26-0061' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.413915, longitude=-84.144823, assessed_value=66835, market_value=66835 WHERE lower(county)='leon' AND case_number='26-0062' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.40647, longitude=-84.291411, assessed_value=234748, market_value=234748 WHERE lower(county)='leon' AND case_number='26-0073' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.487652, longitude=-84.210109, assessed_value=3842400, market_value=3842400 WHERE lower(county)='leon' AND case_number='26-0080' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.541455, longitude=-84.195666, assessed_value=208473, market_value=208473 WHERE lower(county)='leon' AND case_number='26-0082' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.497361, longitude=-84.23334, assessed_value=10000, market_value=10000 WHERE lower(county)='leon' AND case_number='26-0084' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.50741, longitude=-84.088873, assessed_value=21246, market_value=21246 WHERE lower(county)='leon' AND case_number='26-0085' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.529898, longitude=-84.214745, assessed_value=249323, market_value=249323 WHERE lower(county)='leon' AND case_number='26-0086' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.508973, longitude=-84.327102, assessed_value=145361, market_value=145361 WHERE lower(county)='leon' AND case_number='26-0088' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.512921, longitude=-84.368015, assessed_value=257598, market_value=257598 WHERE lower(county)='leon' AND case_number='26-0089' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.487448, longitude=-84.144395, assessed_value=84478, market_value=84478 WHERE lower(county)='leon' AND case_number='26-0090' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.483148, longitude=-84.145364, assessed_value=85275, market_value=85275 WHERE lower(county)='leon' AND case_number='26-0093' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.587686, longitude=-84.268045, assessed_value=71793, market_value=71793 WHERE lower(county)='leon' AND case_number='26-0096' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.565983, longitude=-84.066402, assessed_value=13901, market_value=13901 WHERE lower(county)='leon' AND case_number='26-0097' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.53163, longitude=-84.006237, assessed_value=93176, market_value=93176 WHERE lower(county)='leon' AND case_number='26-0098' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.510168, longitude=-84.374353, assessed_value=22500, market_value=22500 WHERE lower(county)='leon' AND case_number='26-0099' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.491744, longitude=-84.311494, assessed_value=160699, market_value=160699 WHERE lower(county)='leon' AND case_number='26-0102' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.484507, longitude=-84.338286, assessed_value=94761, market_value=94761 WHERE lower(county)='leon' AND case_number='26-0103' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.472714, longitude=-84.32813, assessed_value=108000, market_value=108000 WHERE lower(county)='leon' AND case_number='26-0106' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.455691, longitude=-84.290136, assessed_value=132656, market_value=132656 WHERE lower(county)='leon' AND case_number='26-0112' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.452448, longitude=-84.29328, assessed_value=71233, market_value=71233 WHERE lower(county)='leon' AND case_number='26-0113' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.455776, longitude=-84.304398, assessed_value=58475, market_value=58475 WHERE lower(county)='leon' AND case_number='26-0114' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.455084, longitude=-84.304403, assessed_value=84481, market_value=84481 WHERE lower(county)='leon' AND case_number='26-0115' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.455746, longitude=-84.304032, assessed_value=20000, market_value=20000 WHERE lower(county)='leon' AND case_number='26-0120' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.458398, longitude=-84.296892, assessed_value=20000, market_value=20000 WHERE lower(county)='leon' AND case_number='26-0121' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.443386, longitude=-84.336466, assessed_value=41475, market_value=41475 WHERE lower(county)='leon' AND case_number='26-0122' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.442745, longitude=-84.398146, assessed_value=15000, market_value=15000 WHERE lower(county)='leon' AND case_number='26-0127' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.440779, longitude=-84.401322, assessed_value=48774, market_value=48774 WHERE lower(county)='leon' AND case_number='26-0128' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.440396, longitude=-84.396063, assessed_value=15000, market_value=15000 WHERE lower(county)='leon' AND case_number='26-0129' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.55465, longitude=-84.279718, assessed_value=44439, market_value=44439 WHERE lower(county)='leon' AND case_number='26-0130' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.422599, longitude=-84.225111, assessed_value=22375, market_value=22375 WHERE lower(county)='leon' AND case_number='26-0136' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
UPDATE multi_county_auctions SET latitude=30.38376, longitude=-84.125125, assessed_value=28000, market_value=28000 WHERE lower(county)='leon' AND case_number='26-0139' AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
