-- SHARD-4 run2886 (desoto/hillsborough/wakulla/miami_dade/sumter) — hillsborough letter I fix
--
-- Root cause (confirmed live, matches independent shard8-run2820 diagnosis earlier the same day):
-- hillsborough's I metric (property card completeness, threshold >=95%) was FAIL at 870/916
-- (94.98%, rounds to display 95.0 but fails the strict >= comparison). 46 rows failed the card
-- join: 20 with NULL parcel_id, 26 with a parcel_id present but not represented in parcel_zones.
--
-- Fix (12 of the 26 "parcel present, not zoned" rows — the ones inside Hillsborough County's
-- unincorporated area, i.e. MUNI='U' on the county parcel layer):
--   1. Queried the live public Hillsborough County ArcGIS FeatureServer
--      https://maps.hillsboroughcounty.org/arcgis/rest/services/InfoLayers/HC_Parcels/FeatureServer/0
--      by each row's existing multi_county_auctions.parcel_id (as STRAP for 22-char folio-strap
--      values, as FOLIO for 10-digit values) to fetch real SITE_ADDR/SITE_CITY/MUNI/JUST/ASD_VAL
--      and parcel polygon geometry. Verified SITE_ADDR/SITE_CITY matched the MCA property_address
--      before using the record.
--   2. For the 13 rows whose MUNI was Tampa/Plant City/Temple Terrace (not 'U'), left unfixed —
--      those municipalities maintain zoning independently of the county GIS layer used here; a
--      real fix needs each city's own zoning source, not attempted this session.
--   3. For the 12 unincorporated rows, computed each parcel's polygon centroid and queried the
--      live public Zoning FeatureServer
--      https://maps.hillsboroughcounty.org/arcgis/rest/services/DSD_Viewer_Services/DSD_Viewer_Zoning_Regulatory/FeatureServer/1
--      with a point-in-polygon intersection to get the real NZONE/NZONE_DESC covering that exact
--      parcel today.
--
-- Side effect caught and fixed in the same migration: inserting these 12 parcel_zones rows with
-- no matching zoning_districts row caused view v_zoning_gold_standard_kpi_v3's `pj` CTE (which
-- LEFT JOINs zoning_districts and v_zoning_district_applicability) to default
-- far_applicable/pk1000_applicable to TRUE via COALESCE(a.far_applicable, true) /
-- COALESCE(a.pk1000_applicable, true), which cratered county letter G (FAR/parking sub-metrics)
-- from PASS (100.0, both denominators empty/0-parcels-applicable so NULL and ignored by LEAST())
-- to FAIL (0.0, 12 applicable-but-missing rows). Fixed by inserting 4 zoning_districts rows using
-- the verbatim CATEGORY string the same live ArcGIS zoning layer returns for each code (not
-- normalized or guessed) — this makes v_zoning_district_applicability correctly resolve
-- far_applicable=false for all 4 (their category strings don't exact-match the view's
-- 'commercial'/'industrial'/'mixed-use' set) and pk1000_applicable=false (hardcoded false in that
-- view whenever a real zoning_districts row exists), restoring far_applicable_parcels/
-- pk1000_applicable_parcels to 0 fleet-wide for hillsborough (same as before this migration) so
-- LEAST() again ignores those two NULL sub-metrics and G's PASS is driven by density alone at
-- 98.7% (904/916 parcels have a density value; down from an artifactual 100.0 baseline that
-- reflected 0 applicable-with-gaps parcels, not full completeness). NOTE: FAR and parking-per-1000
-- remain structurally unevaluated for hillsborough (0 parcels ever marked applicable) — this
-- migration does not change that pre-existing fact, it only avoids being the reason 12 parcels
-- newly and incorrectly become "applicable but missing" under G's default-to-true fallback.
--
-- Verified live before: I FAIL 95.0 (870/916), G PASS 100.0
-- Verified live after:  I PASS 96.3 (882/916), G PASS 98.7 (density-driven; FAR/pk1000 still N/A)
-- Independently adversarially verified via Workflow refuter (SURVIVED verdict; one narrative
-- inaccuracy in this comment's first draft about the mechanism's exact location was caught and
-- corrected here; a second flagged concern, that the 6-row lat/lng/assessed_value backfill below
-- didn't take effect, was checked and disproved — the values are live and exact-match, the table's
-- `updated_at` column simply isn't bumped by a plain UPDATE on this table, no trigger sets it).
-- See gold_standard_ultraloop_audit rows for county_slug='hillsborough', letter='I',
-- dispatch_id=428137af-dc82-4531-900a-2e54917fcbf0.

BEGIN;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
VALUES
  ('1931211TM000008000030U', 631, 'RSC-6', 'Residential - Single-Family Conventional', 'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('212930333A00000000340U', 631, 'RSC-6', 'Residential - Single-Family Conventional', 'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('0411040100',             631, 'CI',    'Commercial - Intensive',                    'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('0915030300',             631, 'AS-1',  'Agricultural - Single-Family',              'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('0828440000',             631, 'RSC-6', 'Residential - Single-Family Conventional', 'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('0929380000',             631, 'AS-1',  'Agricultural - Single-Family',              'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('0617050000',             631, 'AS-1',  'Agricultural - Single-Family',              'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('213017ZZZ000004368800U', 631, 'AS-1',  'Agricultural - Single-Family',              'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('1932071VD000000000030U', 631, 'RSC-6', 'Residential - Single-Family Conventional', 'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('20293474F000002000050U', 631, 'PD',    'Planned Development',                       'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('0503110000',             631, 'RSC-6', 'Residential - Single-Family Conventional', 'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE),
  ('1828050VG000002000150U', 631, 'PD',    'Planned Development',                       'arcgis:hillsborough_dsd_zoning_v1', CURRENT_DATE);

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, effective_date)
VALUES
  (631, 'RSC-6', 'Residential - Single-Family Conventional', 'Residential', CURRENT_DATE),
  (631, 'AS-1',  'Agricultural - Single-Family',              'Agricultural', CURRENT_DATE),
  (631, 'PD',    'Planned Development',                       'Planned Development', CURRENT_DATE),
  (631, 'CI',    'Commercial - Intensive',                     'Commercial/Office/Industr', CURRENT_DATE)
ON CONFLICT DO NOTHING;

-- Backfill lat/lng/assessed_value for the 6 rows that also lacked them, from the same
-- authoritative HCPAO parcel record fetched above (real centroid + real ASD_VAL).
UPDATE multi_county_auctions SET latitude=27.982117201899534, longitude=-82.38199948679468, assessed_value=3920.0
  WHERE case_number='2026-462' AND county='hillsborough' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude=27.973413943664323, longitude=-82.15040290717295, assessed_value=2272.0
  WHERE case_number='2026-468' AND county='hillsborough' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude=28.023958031141255, longitude=-82.22396719671737, assessed_value=50762.0
  WHERE case_number='2026-479' AND county='hillsborough' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude=27.935263973932706, longitude=-82.08454455074106, assessed_value=548.0
  WHERE case_number='2026-481' AND county='hillsborough' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude=28.02952639720739, longitude=-82.30690007271379, assessed_value=30162.0
  WHERE case_number='2026-494' AND county='hillsborough' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude=27.846550699614948, longitude=-82.35743276447197, assessed_value=13124.0
  WHERE case_number='2026-447' AND county='hillsborough' AND latitude IS NULL;

COMMIT;
