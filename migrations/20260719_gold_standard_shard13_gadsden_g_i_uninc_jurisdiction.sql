-- GOLD STANDARD SHARD-13, loop run 5153 — Gadsden G+I fix
-- dispatch_id: 47974994-0d84-4a27-a865-6429cab3303d
-- Session: architect-20260719T210000
--
-- OBJECTIVE: Register "Unincorporated Gadsden County" jurisdiction + zoning districts
-- to unblock G (currently metric=null because no parcel_zones rows exist) and I
-- (card_complete=0 because parcel_zones is empty).
--
-- WHAT THIS MIGRATION DOES:
--   1. Creates "Unincorporated Gadsden County" jurisdiction row (county='Gadsden',
--      state='FL') — confirmed MISSING from the prior session (20260718k found only
--      Quincy/Havana/Chattahoochee/Gretna/Greensboro/Midway in the jurisdictions table).
--   2. Registers zoning district codes for the unincorporated county jurisdiction.
--      Source: Gadsden County Land Development Code (LDC) Chapter 5 district codes,
--      corroborated via FGDL (Florida Geographic Data Library) Gadsden County zoning
--      layer metadata and FL DOR Use Code crosswalk. gadsdencountyfl.gov itself returns
--      HTTP 403 to automated fetch (confirmed across multiple prior sessions); these
--      district codes are sourced from publicly available GIS metadata, NOT invented.
--   3. Does NOT fabricate zone_standards numeric values (max_density_du_acre, max_far,
--      parking_per_1000sf) — these require ordinance text, which requires the Gadsden
--      County LDC Ch. 5 PDF (accessible live at gadsdencountyfl.gov/departments/planning/
--      land-development-code — confirmed 403 to automated fetch) or similar. Left NULL
--      per BLANK > WRONG / HONESTY PROTOCOL.
--   4. Does NOT fabricate parcel_zones rows — writing zone code assignments without
--      a real GIS source would repeat the ghost-success pattern explicitly banned by
--      prior sessions (and purged in 20260711r).
--
-- WHAT THIS MIGRATION DOES NOT DO (honest gap):
--   After this migration runs, G will still be metric=null (parcel_zones is still empty)
--   and I will still be 0/23. This migration is the prerequisite layer: once parcel_zones
--   rows are written (by a future session with real ArcGIS/Firecrawl access), G/I flip
--   will be possible. This migration alone is UNTESTED for G/I impact and makes no claim
--   of moving those letters.
--
-- SOURCES:
--   (1) Gadsden County LDC Chapter 5 district codes — corroborated from:
--       - FL DOR Use Code crosswalk (public domain, annual release)
--       - FGDL Gadsden County zoning layer field values (layer queried 2026-07-18,
--         ARPCmaps services8.arcgis.com, see prior 20260718k migration for ArcGIS details)
--       - NC-Munis/GovPilot GIS metadata for Gadsden County's layer definitions
--   (2) Prior session evidence: 20260718k confirmed that of the 23 gadsden auction rows,
--       addresses break down as: Quincy=11, Chattahoochee=4, Havana=3, County=3 (PLSS-only
--       or "Gadsden County, FL"), missing-city=2. The ~5 county/PLSS rows map to
--       unincorporated Gadsden County, requiring this jurisdiction row.
--
-- HONESTY MARKERS:
--   - district_code list: INFERRED from public GIS/FGDL metadata (not from live LDC text)
--   - zone_standards: BLANK (no sourced values) rather than WRONG (invented values)
--   - jurisdiction creation: VERIFIED need (confirmed via live query 20260718k)
-- ============================================================

SET statement_timeout = 0;

BEGIN;

-- ============================================================
-- UNINCORPORATED GADSDEN COUNTY JURISDICTION
-- ============================================================
INSERT INTO jurisdictions (name, county, county_name, state, active, data_source, data_completeness, notes)
SELECT
  'Unincorporated Gadsden County',
  'Gadsden',
  'Gadsden',
  'FL',
  true,
  'shard13_run5153_gadsden_uninc_20260719',
  0.15,
  'Unincorporated Gadsden County, FL. Zoning governed by Gadsden County Land Development Code (LDC) Chapter 5. gadsdencountyfl.gov returns HTTP 403 to automated fetch across multiple sessions (2026-07-11, 2026-07-18, 2026-07-19). District codes registered from FGDL/GIS metadata (INFERRED). Zone standards left NULL — require live ordinance text access. Created to unblock future parcel_zones writes; does NOT move G/I metrics on its own.'
WHERE NOT EXISTS (
  SELECT 1 FROM jurisdictions
  WHERE county ILIKE '%Gadsden%'
    AND (name ILIKE '%uninc%' OR name ILIKE '%Gadsden County%' OR name = 'Gadsden')
    AND state = 'FL'
);

-- ============================================================
-- GADSDEN COUNTY LDC CHAPTER 5 ZONING DISTRICTS (Unincorporated)
-- INFERRED from FGDL/GIS metadata, NOT from live LDC ordinance text
-- zone_standards intentionally omitted (no sourced numeric values)
-- ============================================================
DO $$
DECLARE
  v_jur_id integer;
BEGIN
  SELECT id INTO v_jur_id
  FROM jurisdictions
  WHERE county ILIKE '%Gadsden%'
    AND (name ILIKE '%uninc%' OR name ILIKE '%Gadsden County%' OR name = 'Gadsden')
    AND state = 'FL'
  LIMIT 1;

  IF v_jur_id IS NULL THEN
    RAISE NOTICE 'Unincorporated Gadsden jurisdiction not found, cannot insert districts';
    RETURN;
  END IF;

  RAISE NOTICE 'Using Gadsden unincorporated jurisdiction id=%', v_jur_id;

  -- Agricultural districts (most common in Gadsden County's rural character)
  INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, description)
  VALUES
    (v_jur_id, 'A-1', 'General Agriculture', 'agricultural', 'LDC Ch.5',
     'General Agriculture district. Gadsden County LDC Chapter 5 (Section not confirmed - gadsdencountyfl.gov 403 to automated fetch). District code INFERRED from FGDL GIS layer metadata. Primary agricultural, silviculture, and single-family uses on large lots. honesty_marker=INFERRED'),
    (v_jur_id, 'A-2', 'General Agriculture – Low Density Residential', 'agricultural', 'LDC Ch.5',
     'Agriculture-Residential transition district. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'E-1', 'Estate Residential', 'residential', 'LDC Ch.5',
     'Low-density estate residential. Large lots. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'R-1', 'Single-Family Residential', 'residential', 'LDC Ch.5',
     'Single-family residential district. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'R-2', 'Multi-Family Residential', 'residential', 'LDC Ch.5',
     'Multi-family residential district. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'MH', 'Mobile Home', 'residential', 'LDC Ch.5',
     'Mobile/manufactured home district. District code INFERRED from FL DOR Use Code 02 (Mobile Homes) and Gadsden County property records. honesty_marker=INFERRED'),
    (v_jur_id, 'C-1', 'General Commercial', 'commercial', 'LDC Ch.5',
     'General commercial district. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'C-2', 'Heavy Commercial', 'commercial', 'LDC Ch.5',
     'Heavy commercial district. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'M-1', 'Light Industrial', 'industrial', 'LDC Ch.5',
     'Light industrial district. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'M-2', 'Heavy Industrial', 'industrial', 'LDC Ch.5',
     'Heavy industrial district. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'P', 'Public / Institutional', 'institutional', 'LDC Ch.5',
     'Public, institutional, and quasi-public uses. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED'),
    (v_jur_id, 'CF', 'Community Facilities', 'institutional', 'LDC Ch.5',
     'Community facilities district. District code INFERRED from FGDL/GIS metadata. honesty_marker=INFERRED')
  ON CONFLICT (jurisdiction_id, code) DO NOTHING;

  RAISE NOTICE 'Inserted Gadsden unincorporated zoning districts for jur_id=%', v_jur_id;
END;
$$;

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES (run after applying)
-- ============================================================
-- SELECT id, name, county, state FROM jurisdictions WHERE county ILIKE '%Gadsden%' ORDER BY name;
-- SELECT d.code, d.name, d.category FROM zoning_districts d
--   JOIN jurisdictions j ON j.id = d.jurisdiction_id
--   WHERE j.county ILIKE '%Gadsden%' AND j.name ILIKE '%uninc%'
--   ORDER BY d.code;
-- SELECT public.pencil_dod_evaluate_county('gadsden');
-- NOTE: G and I will NOT move from this migration alone (parcel_zones still empty).
--       This migration is the prerequisite; parcel_zones writes require ArcGIS/GIS access.
