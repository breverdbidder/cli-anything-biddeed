-- GOLD STANDARD shard-9 (dispatch 20a33672), 5th firing, broward Letter I lane.
-- SECOND CORRECTION to 20260721_gold_standard_shard9_broward_i_5th_firing.sql.
--
-- Root cause of CACE-20-018707 (Bay Club Dr) still failing after both the
-- parcel_id fix AND the market_value correction: the original diagnosis
-- (has_zone=true, pre-migration) was checking the OLD truncated parcel_id
-- ("494124") against v_zoning_gold_standard_card and got a false-positive
-- match (the 6-digit truncated code coincidentally matched something in that
-- view). The REAL folio (494212AK1970, confirmed live via BCPA) has NO
-- existing zoning_districts/parcel_zones entry at all -- this was missed in
-- the original migration because the pre-fix diagnostic query used the wrong
-- (stale) parcel_id.
--
-- Also discovered live: the row's existing lat/long (26.1224, -80.1373 -- the
-- same P0 fallback-default coordinate flagged in the original migration)
-- resolves via Fort Lauderdale's live zoning GIS
-- (gis.fortlauderdale.gov/.../ZoningGIS/LayerList/MapServer/15) to
-- "RAC-CC - City Center District" -- a COMPLETELY different zone than BCPA's
-- real per-folio landCalcZoning ("RMM-25 - RESIDENTIAL MULTIFAMILY MID
-- RISE/MEDIUM HIGH DENSITY"). This is direct, concrete proof that the fallback
-- coordinate is fake and location-dependent lookups against it produce wrong
-- answers -- BCPA's landCalcZoning field (looked up by folio, not by
-- coordinate) was used instead, which is not affected by the bad geocode.
--
-- max_density_du_acre=25 is a direct-quote WebSearch citation of Fort
-- Lauderdale ULDC Sec. 47-5.36 ("Table of dimensional requirements for the
-- RMM-25 district" -- "maximum density of 25 dwelling units per net acre").

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated)
VALUES (913, 'RMM-25', 'Residential Multifamily Mid Rise/Medium High Density', 'residential', NULL, true, false)
RETURNING id;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url)
SELECT id, 25.00, 'Fort Lauderdale ULDC Sec. 47-5.36 Table of dimensional requirements for the RMM-25 district (BCPA landCalcZoning cross-check for folio 494212AK1970)'
FROM zoning_districts WHERE jurisdiction_id = 913 AND code = 'RMM-25';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('494212AK1970', 913, 'RMM-25', 'Residential Multifamily Mid Rise/Medium High Density', 'bcpa_landCalcZoning_verified_folio_lookup');
