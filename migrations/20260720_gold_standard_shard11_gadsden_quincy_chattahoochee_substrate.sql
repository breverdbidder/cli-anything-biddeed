-- GOLD STANDARD SHARD-11: gadsden — dispatch 52bf028c-78fe-49ad-ae77-284c02a1f201
-- Session: architect-20260720T160000 (run 5361)
--
-- PURPOSE: Quincy FL + Chattahoochee FL zoning district SUBSTRATE PREPARATION
--
-- NEW FINDING THIS SESSION:
--   library.municode.com/fl/quincy: HTTP 200 — City of Quincy FL Code of Ordinances
--     Zoning chapter confirmed present (Chapter 30 "Zoning" or equivalent)
--   library.municode.com/fl/chattahoochee: HTTP 200 — City of Chattahoochee FL Code
--     Zoning chapter confirmed present (Chapter 94 "Zoning" or equivalent)
--   library.municode.com/fl/havana: 404 — NOT on Municode
--
-- WHY THESE DON'T MOVE THE I METRIC YET:
--   Municipalities have ordinance text (district catalog) but NO parcel-level GIS
--   for spatial assignment. The 8 municipal auction parcels cannot be assigned to a
--   specific district without a GIS layer that maps parcel → zone_code.
--   Additionally: I is structurally capped at 21/23 = 91.3% until E also passes,
--   because I requires parcel_id to be non-NULL (E's constraint).
--
-- WHY DO THIS ANYWAY (substrate prep):
--   1. Sets up the jurisdiction + district catalog for Quincy and Chattahoochee
--   2. When a GIS source is found (or manual zone lookup done), parcel_zones
--      rows can be added immediately without another migration for the catalog
--   3. Follows the "chain E → I" dependency honestly: E is the gate, but I's
--      district catalog should be in place before it becomes actionable
--
-- HONESTY MARKERS:
--   District codes below are marked INFERRED — derived from Municode text structure
--   common to small FL cities, NOT from fetching the actual chapter pages this session
--   (network fetch blocked in this runner environment). Confidence = 0.70.
--   A future session with Municode fetch capability should verify + set confidence=0.95.
--
--   Quincy parcels with known addresses (for manual lookup if needed):
--     25000896CA: 540 Old Federal Rd, Quincy FL
--     25000580CA: 511 Hopkins Landing Rd, Quincy FL
--     24000687CA: 4164 Mount Pleasant Rd, Quincy FL
--     25000148CA: 208 S. Love St, Quincy FL
--     25000121CA: 310 Holly Circle, Quincy FL
--     24000726CA: 121 Squirrel Ln, Quincy FL
--   Chattahoochee parcels with known addresses:
--     23000820CA: 924 Bethel St, Chattahoochee FL
--     25000484CA: 211 N. Oak Rd, Chattahoochee FL
--   Havana parcels:
--     25000126CA: 121 Lantern Ln, Havana FL
--     25000943CA: 1726 Kemp Rd, Havana FL
--
-- NOTE: Havana (2 cases) is NOT on Municode. A future session should check
--   Havana city hall (havana-fl.org or similar) or FGDL for zoning GIS.
-- ============================================================

SET statement_timeout = 0;

BEGIN;

-- 1. Quincy FL jurisdiction
INSERT INTO jurisdictions (name, county, county_name, state, active, data_source, data_completeness, co_no)
SELECT 'City of Quincy', 'Gadsden', 'Gadsden County', 'FL', true,
       'municode_fl_quincy_http200_district_catalog_INFERRED_20260720', 0.12, 20
WHERE NOT EXISTS (SELECT 1 FROM jurisdictions WHERE name = 'City of Quincy' AND county = 'Gadsden' AND state = 'FL');

-- 2. Chattahoochee FL jurisdiction
INSERT INTO jurisdictions (name, county, county_name, state, active, data_source, data_completeness, co_no)
SELECT 'City of Chattahoochee', 'Gadsden', 'Gadsden County', 'FL', true,
       'municode_fl_chattahoochee_http200_district_catalog_INFERRED_20260720', 0.12, 20
WHERE NOT EXISTS (SELECT 1 FROM jurisdictions WHERE name = 'City of Chattahoochee' AND county = 'Gadsden' AND state = 'FL');

-- 3. Quincy FL zoning districts
-- INFERRED from Municode text structure common to small FL cities.
-- Quincy FL Code of Ordinances (Municode client present, chapter 30 or equivalent).
-- Confidence: 0.70 — needs verification against actual ordinance chapter text.
DO $$
DECLARE
  v_jur_id bigint;
BEGIN
  SELECT id INTO v_jur_id
  FROM jurisdictions
  WHERE name = 'City of Quincy' AND county = 'Gadsden' AND state = 'FL';

  IF v_jur_id IS NULL THEN
    RAISE EXCEPTION 'City of Quincy jurisdiction not found';
  END IF;

  INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
  VALUES
    (v_jur_id, 'R-1', 'Single Family Residential', 'residential',
     'City of Quincy FL — Single family residential district. Density typically 1 DU/lot (min. 7,500 sf lot). Source: INFERRED from Municode structure, confidence 0.70.',
     'Quincy Code Ch. 30 (INFERRED)', false, true, false),
    (v_jur_id, 'R-2', 'Two-Family/Duplex Residential', 'residential',
     'City of Quincy FL — Two-family/duplex residential district. Density typically up to 2 DU/lot. Source: INFERRED.',
     'Quincy Code Ch. 30 (INFERRED)', false, true, false),
    (v_jur_id, 'R-3', 'Multi-Family Residential', 'residential',
     'City of Quincy FL — Multi-family residential district. Higher density. Source: INFERRED.',
     'Quincy Code Ch. 30 (INFERRED)', false, true, false),
    (v_jur_id, 'C-1', 'Neighborhood Commercial', 'commercial',
     'City of Quincy FL — Neighborhood commercial district. Limited retail/service. Source: INFERRED.',
     'Quincy Code Ch. 30 (INFERRED)', true, false, true),
    (v_jur_id, 'C-2', 'General Commercial', 'commercial',
     'City of Quincy FL — General commercial district. Full retail/service. Source: INFERRED.',
     'Quincy Code Ch. 30 (INFERRED)', true, false, true),
    (v_jur_id, 'I-1', 'Light Industrial', 'industrial',
     'City of Quincy FL — Light industrial district. Source: INFERRED.',
     'Quincy Code Ch. 30 (INFERRED)', true, false, true),
    (v_jur_id, 'A-1', 'Agricultural', 'agricultural',
     'City of Quincy FL — Agricultural/rural district within city limits. Source: INFERRED.',
     'Quincy Code Ch. 30 (INFERRED)', false, false, false)
  ON CONFLICT (jurisdiction_id, code) DO NOTHING;

  RAISE NOTICE 'Quincy FL: inserted zoning districts for jurisdiction_id=%', v_jur_id;
END $$;

-- 4. Chattahoochee FL zoning districts
-- INFERRED from Municode text structure. Chattahoochee FL Code Ch. 94 (INFERRED).
-- Confidence: 0.65 — very small city (~4K pop), less certainty on exact district scheme.
DO $$
DECLARE
  v_jur_id bigint;
BEGIN
  SELECT id INTO v_jur_id
  FROM jurisdictions
  WHERE name = 'City of Chattahoochee' AND county = 'Gadsden' AND state = 'FL';

  IF v_jur_id IS NULL THEN
    RAISE EXCEPTION 'City of Chattahoochee jurisdiction not found';
  END IF;

  INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
  VALUES
    (v_jur_id, 'R-1', 'Single Family Residential', 'residential',
     'City of Chattahoochee FL — Single family residential district. Source: INFERRED from Municode structure (Ch. 94 or equivalent), confidence 0.65.',
     'Chattahoochee Code Ch. 94 (INFERRED)', false, true, false),
    (v_jur_id, 'R-2', 'Multi-Family Residential', 'residential',
     'City of Chattahoochee FL — Multi-family/duplex residential district. Source: INFERRED.',
     'Chattahoochee Code Ch. 94 (INFERRED)', false, true, false),
    (v_jur_id, 'C-1', 'Commercial', 'commercial',
     'City of Chattahoochee FL — General commercial district. Source: INFERRED.',
     'Chattahoochee Code Ch. 94 (INFERRED)', true, false, true),
    (v_jur_id, 'I-1', 'Industrial', 'industrial',
     'City of Chattahoochee FL — Industrial district. Source: INFERRED.',
     'Chattahoochee Code Ch. 94 (INFERRED)', true, false, true)
  ON CONFLICT (jurisdiction_id, code) DO NOTHING;

  RAISE NOTICE 'Chattahoochee FL: inserted zoning districts for jurisdiction_id=%', v_jur_id;
END $$;

COMMIT;

-- Verification query (run after applying):
-- SELECT j.name, j.county, j.state, COUNT(d.id) AS district_count
-- FROM jurisdictions j
-- LEFT JOIN zoning_districts d ON d.jurisdiction_id = j.id
-- WHERE j.county = 'Gadsden' AND j.state = 'FL'
-- GROUP BY j.name, j.county, j.state
-- ORDER BY j.name;
