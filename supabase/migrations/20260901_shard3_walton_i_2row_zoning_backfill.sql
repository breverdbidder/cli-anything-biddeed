-- Gold Standard walton letter I (card_complete): 2-row zoning-linkage gap.
--
-- pencil_dod_evaluate_county('walton') entry state this session (VERIFIED live):
--   I: card_complete=148 of 157, metric=94.3, FAIL (needs >=95)
--
-- Live re-derivation of the 9 blocking rows (VERIFIED, this session) against
-- v_zoning_gold_standard_card + multi_county_auctions for county=walton:
--   3 rows: fully-empty calendar_sweep_mca_v3 stub rows (no address/geo/value/parcel_id)
--   2 rows: parcel_id literal sentinel values "MULTIPLE PARCELS" / "TIMESHARE" (not real parcels)
--   1 row (2026-0125TD): missing property_address only, already zone-linked
--   2 rows (THIS FIX): 25CA000518 (131 Silk Oak Dr, DeFuniak Springs) and
--     26CA000046 (31 Fire Dept Ave, DeFuniak Springs) -- real addresses, real
--     lat/lon, real assessed_value, real dashed-format Walton PA parcel_id
--     (17-3N-20-28080-012-0160 / 33-3N-18-10010-000-0940), but genuinely ABSENT
--     from parcel_zones (confirmed: neighboring parcels in the same subdivision,
--     e.g. 17-3N-20-28080-056-0020 and -082-0280, already carry real zone_code
--     "Rural Low Density" sourced from the same layer -- this is an individual
--     parcel coverage gap in a prior GIS harvest, not a format/linkage bug).
--
-- FIX (real data, live fetch this session): Walton County's own EnerGov ArcGIS
-- FeatureServer, layer 19 "Zoning" (services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/
-- rest/services/EnerGov/FeatureServer/19) -- the exact same source
-- (jurisdiction_id=1333 "Unincorporated Walton County", data_source string
-- "EnerGov ArcGIS FeatureServer (services1.arcgis.com/TaXHPwWfIMuzJ7Ov)") already
-- used to populate every other walton parcel_zones row. Layer 19 is a polygon
-- layer with no parcel-number attribute, so both parcels were resolved by
-- point-in-polygon spatial query against the lat/lon already on file in
-- multi_county_auctions for each case:
--
--   25CA000518 @ (30.752694, -86.260279) -> ZONE_CLASS "Rural Low Density",
--     PLAN_AREA "North Central", Ordinance_Number 2018-29, Ordinance_Date 2018-12-11
--   26CA000046 @ (30.719175, -86.040289) -> ZONE_CLASS "Rural Village",
--     PLAN_AREA "North Central", Ordinance_Number 2018-29, Ordinance_Date 2018-12-11
--
-- Both points independently confirmed OUTSIDE any Municipalities polygon
-- (layer 52 -- empty feature set both queries), i.e. unincorporated Walton,
-- matching jurisdiction_id=1333.
--
-- Idempotent: ON CONFLICT DO NOTHING guard via a NOT EXISTS pre-check (no
-- unique constraint on parcel_zones.parcel_id known ahead of time, so this
-- uses an explicit anti-join instead of ON CONFLICT).
--
-- EXPECTED I-METRIC IMPACT: card_complete 148 -> 150 of 157 (95.5%%, FAIL -> PASS
-- if these are the only two levers still reachable this session; the remaining
-- 7 rows are either empty stubs, sentinel-value parcels, or a single missing-
-- address row -- none fixed by this migration).

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, effective_date, source)
SELECT v.parcel_id, v.parcel_id, 1333, v.zone_code, v.effective_date, v.source
FROM (VALUES
  ('17-3N-20-28080-012-0160', 'Rural Low Density', DATE '2018-12-11',
   'walton_energov_arcgis_layer19_spatial/gold_standard_shard3_i_2row_20260901'),
  ('33-3N-18-10010-000-0940', 'Rural Village', DATE '2018-12-11',
   'walton_energov_arcgis_layer19_spatial/gold_standard_shard3_i_2row_20260901')
) AS v(parcel_id, zone_code, effective_date, source)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);
