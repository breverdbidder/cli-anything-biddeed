-- GOLD STANDARD shard-4 (leon/glades/walton), loop run 6148, dispatch 0fc2eae2.
-- County: walton. Letter G further mitigation -- resolves 5 of the 9
-- "Municipal"-stub parcels flagged in the earlier regression-fix migration
-- of this run as unresolvable within the county EnerGov zoning layer.
--
-- FOUND THIS SESSION (after the earlier migration shipped): the City of
-- DeFuniak Springs publishes its OWN zoning layer on ArcGIS Online --
-- https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/CityofDefuniakSprings/FeatureServer/0
-- (layer "Zoning_Updated", field PARCELNO -- exact parcel-number match, not a
-- spatial guess) -- discoverable via Walton County's own "Municipalities GIS
-- Data" page (mywaltonfl.gov/172) linking to arcgis.com item
-- 5a68c2b83c6f4dcc94434e315c4856c7. Queried live for all 9 "Municipal"-stub
-- parcel_ids: 5 matched with real zone codes (R-1 x3, R-2 x2), 4 returned no
-- match either by exact PARCELNO or by spatial point-in-polygon using the
-- row's own lat/lon (those 4 rows' coordinates fall well outside DeFuniak
-- Springs proper -- one near the coast at lat 30.49, three near the Alabama
-- state line at lat ~30.98 -- suggesting the county EnerGov "Municipal" tag
-- for those 4 may not even mean DeFuniak Springs specifically; left open,
-- not guessed).
--
-- R-1 and R-2 already have real zone_standards for jurisdiction 842
-- (DeFuniak Springs) from prior sessions (max_density_du_acre 4.00 and 16.00
-- respectively, source talgov/prior DeFuniak Springs LDC research) -- this
-- migration only corrects the zone_code on 5 existing parcel_zones rows to
-- their real DeFuniak Springs zoning designation; it does not add any new
-- numeric standard.
--
-- Expected effect: 5 more density-applicable parcels get a real
-- max_density_du_acre value for free (via the existing R-1/R-2
-- zone_standards). walton G density: 85.2% -> ~93.4% (57/61). Still short of
-- 95% (needs 58/61) by 1 row -- the remaining 4 unresolvable Municipal stubs
-- are the residual gap, documented in the prior migration and the session
-- ultraloop_audit row (not re-claimed as fixed here).

UPDATE parcel_zones SET
  zone_code = 'R-1',
  zone_name = 'Single-family residential district',
  source = 'defuniak_springs_arcgis_zoning_updated_parcelno_exact:shard4-run6148:0fc2eae2'
WHERE jurisdiction_id = 842 AND zone_code = 'Municipal'
  AND parcel_id IN ('25-3N-19-19070-000-0160', '25-3N-19-19070-000-3960', '30-3N-18-10000-027-0020');

UPDATE parcel_zones SET
  zone_code = 'R-2',
  zone_name = 'Multiple family residential district',
  source = 'defuniak_springs_arcgis_zoning_updated_parcelno_exact:shard4-run6148:0fc2eae2'
WHERE jurisdiction_id = 842 AND zone_code = 'Municipal'
  AND parcel_id IN ('25-3N-19-19070-001-7230', '25-3N-19-19070-001-5400');
