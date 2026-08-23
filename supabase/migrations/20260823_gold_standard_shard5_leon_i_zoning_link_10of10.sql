-- Gold Standard shard-5 (dispatch 79ee1554): LEON county criterion I — final fix,
-- county reaches 10/10.
--
-- Prior fix this session (20260823_gold_standard_shard5_leon_i_geo_value.sql)
-- closed the geo/value gap for 42 rows but I stayed at 81.4% because 0 of those
-- 42 parcels existed in parcel_zones (a genuine zoning-ingestion coverage gap,
-- documented as residual/out-of-scope at the time).
--
-- Follow-up: found Leon County's own zoning GIS layer --
-- https://intervector.leoncountyfl.gov/intervector/rest/services/MapServices/
-- TLC_OverlayZoning_D_WM/MapServer/0 (fields ZONING/ZONED/JURISDICTION) -- and ran
-- a live spatial point lookup (lat/long from the prior fix) for all 43 I-gap
-- parcels. 42 resolved to a real zone code (1 left unresolved: case
-- "2025 CA 002309", parcel_id="MULTIPLE PARCELS", structurally unparseable, left
-- untouched). JURISDICTION field mapped City->jurisdiction_id 917 (Tallahassee),
-- County->1397 (Unincorporated Leon), and the 8 "Multiple"-boundary parcels were
-- assigned to whichever jurisdiction already had that zone code registered
-- (PUD/CP -> 917, R -> 1397; both already existed pre-session) rather than
-- guessed.
--
-- Two zone codes (R-5 "Manufactured Home and Single Family Residential", LP
-- "Lake Protection") had no existing zoning_districts row for Leon at all --
-- pre-classified them with a category (residential / conservation respectively,
-- both taken verbatim from Leon's own GIS legend, not invented) BEFORE inserting
-- the parcel_zones rows, specifically to avoid the exact G-regression mechanism
-- that hit Clay earlier this session (unclassified codes default to
-- "applicable but standards missing" in v_zoning_gold_standard_kpi_v3).
--
-- VERIFIED live via pencil_dod_evaluate_county('leon'): I 81.4%->98.4%
-- (201/247->243/247), PASS. G held PASS at 95.9% (small expected dip from
-- 98.5%, still clears >=95%, no regression). leon is now 10/10.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category)
VALUES
  (917, 'R-5', 'Manufactured Home and Single Family Residential', 'residential'),
  (1397, 'R-5', 'Manufactured Home and Single Family Residential', 'residential'),
  (1397, 'LP', 'Lake Protection', 'conservation')
ON CONFLICT DO NOTHING;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('210915 E0230', 917, 'RP-1', 'Residential Preservation-1', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('310550B0030', 917, 'RP-1', 'Residential Preservation-1', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('4123201300000', 1397, 'R-5', 'Manufactured Home and Single Family Residential', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('4123060000380', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('331740E0110', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('2121320080010', 917, 'MR-1', 'Medium Density Residential', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('310645B0180', 917, 'RP-1', 'Residential Preservation-1', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('311525A0010', 917, 'PUD', 'Southwood PUD', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('311840H0280', 917, 'RP-2', 'Residential Preservation-2', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('311930C0030', 917, 'CP', 'Commercial Parkway', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('320883A0250', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('320883A0251', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('4112206160000', 917, 'RP-1', 'Residential Preservation-1', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('1115202000000', 917, 'PUD', 'Canopy PUD', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('142560VV0160', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('1109204470000', 917, 'R-3', 'Single Detached, Attached and Two Family Residential', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('1201206110000', 1397, 'R', 'Rural', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('110250CD0150', 917, 'RP-1', 'Residential Preservation-1', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('210370E0220', 1397, 'LP', 'Lake Protection', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('210650D0310', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('121750B0050', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('121750E0090', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('140705A0010', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('1618204680000', 1397, 'R', 'Rural', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('1635202410000', 1397, 'R', 'Rural', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('210610A0010', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('2115450000040', 1397, 'LP', 'Lake Protection', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('2116080000130', 917, 'RP-2', 'Residential Preservation-2', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('2121210066020', 917, 'PUD', 'Hartsfield Green Condominiums PUD', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('212525A0090', 917, 'RP-2', 'Residential Preservation-2', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('212528A0080', 917, 'RP-2', 'Residential Preservation-2', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('212635N0040', 917, 'RP-2', 'Residential Preservation-2', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('212635N0090', 917, 'RP-2', 'Residential Preservation-2', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('212635N0210', 917, 'RP-2', 'Residential Preservation-2', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('212645A0440', 917, 'RP-2', 'Residential Preservation-2', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('212851E0001', 917, 'MR-1', 'Medium Density Residential', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('223516A0160', 1397, 'UF', 'Urban Fringe', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('223517A0120', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('2235204090000', 1397, 'UF', 'Urban Fringe', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('2424050000060', 1397, 'R', 'Rural', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('310328B0060', 917, 'R-5', 'Manufactured Home and Single Family Residential', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial'),
  ('322116B0110', 1397, 'RP', 'Residential Preservation', 'leon_county_gis_tlc_overlay_zoning_20260823_spatial')
ON CONFLICT DO NOTHING;
