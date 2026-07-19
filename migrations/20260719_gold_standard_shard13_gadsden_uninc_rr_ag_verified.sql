-- GOLD STANDARD SHARD-13, dispatch 47974994 (2nd re-fire, session architect-20260719T160000)
-- Gadsden G+I fix: unincorporated Rural Residential / Agriculture-1 / Agriculture-2
--
-- SUPERSEDES the unrun 20260719 migration
-- (20260719_gold_standard_shard13_gadsden_g_i_uninc_jurisdiction.sql, session
-- architect-20260719T210000) for zoning_districts content: that migration's 12 district
-- codes (A-1, A-2, E-1, R-1, R-2, MH, C-1, C-2, M-1, M-2, P, CF) were explicitly marked
-- INFERRED from FGDL/GIS metadata guesswork, not live ordinance text, and left
-- zone_standards NULL by design. This migration uses REAL Gadsden County LDC Chapter 4
-- "Land Use Categories" (rev. 11-15-16) ordinance text plus a live ArcGIS spatial
-- point-in-polygon match against the Gadsden_FLUM FeatureServer for each specific
-- auction parcel. Jurisdiction name is identical ('Unincorporated Gadsden County') so the
-- two migrations do not collide (jurisdictions.name is UNIQUE; ON CONFLICT-safe below);
-- district codes are disjoint strings (RR/AG-1/AG-2 vs A-1/A-2/R-1/R-2/...) so no
-- zoning_districts collision either, whichever runs first.
--
-- SOURCES (independently adversarially re-verified this session, see session report):
--   Ordinance text: Gadsden County LDC Chapter 4 "Land Use Categories" (rev. 11-15-16),
--     https://web.archive.org/web/20201020071952/https://www.gadsdencountyfl.gov/Document%20Center/Departments/Planning%20&%20Community%20development/Land%20Development%20Regulations/Land%20Development%20Code/Chapter%204%20Land%20Use%20Categories.pdf
--     - Subsection 4102 (Rural Residential): "net density does not exceed one dwelling
--       unit per acre" -> max_density_du_acre = 1.0
--     - Table 4103 (Agriculture 1/2): "1DU/5 Acres" -> 0.2; "1DU/10 Acres" -> 0.1
--   Spatial assignment: Gadsden_FLUM FeatureServer,
--     https://services8.arcgis.com/N3lCn6dEKCL6LidU/arcgis/rest/services/Gadsden_FLUM/FeatureServer
--     (layers Gads_RuralRes, Ag1, Ag2) — point-in-polygon query against each auction
--     parcel's centroid lat/lon confirmed no overlap across all 15 category layers.
--
-- HONESTY MARKERS:
--   - RR/AG-1/AG-2 density figures: CONFIRMED verbatim in ordinance text, independently
--     re-fetched and re-quoted by an adversarial verifier this session.
--   - Spatial parcel-to-category match: CONFIRMED, independently re-run by the same
--     verifier for a sample and matched exactly with no cross-layer ambiguity.
--   - max_far / parking_per_1000sf: intentionally left NULL. The ordinance provides no
--     FAR or parking-space-count regulation for these 3 rural/agricultural categories
--     (only Neighborhood Commercial, subsection 4104, has FAR/parking, and no auction
--     parcel falls in NC this session) -- far_regulated/pk1000_regulated explicitly set
--     to false below so v_zoning_district_applicability treats them as N/A rather than
--     a missing value, per the same pattern used for brevard/duval residential districts.
--   - CONFIDENCE CAVEAT (logged via zone_standards.confidence_score = 0.85, not 1.0):
--     the Gadsden_FLUM ArcGIS layers report lastEditDate ~2019-01-14 and the cited LDC
--     revision is dated 2016-11-15. The verifier found evidence (undated-but-newer CMS
--     document reference, embedded timestamp decoding to 2023-06-23) that a newer LDC
--     revision may exist behind gadsdencountyfl.gov's WAF (403, unreachable this
--     session). Could not confirm whether density figures changed in a newer revision.
--     This is a real residual risk, not a disqualifying one -- flagging honestly rather
--     than either fabricating certainty or withholding real, sourced data.
--   - 8 of the 21 gadsden auction parcels fall in the ArcGIS "Municipal" category (inside
--     Quincy/Chattahoochee/Havana city limits) and are DELIBERATELY NOT touched by this
--     migration -- no per-parcel municipal zoning source exists (confirmed dead end
--     across 4+ prior sessions: qpublic 403, no Quincy_Zoning/Chattahoochee_Zoning
--     FeatureServer). Writing a zone for those parcels here would be fabrication.
-- ============================================================

SET statement_timeout = 0;

BEGIN;

-- 1. Unincorporated Gadsden County jurisdiction (idempotent: name is UNIQUE)
INSERT INTO jurisdictions (name, county, county_name, state, active, data_source, data_completeness, co_no)
SELECT 'Unincorporated Gadsden County', 'Gadsden', 'Gadsden', 'FL', true,
       'gadsden_flum_arcgis+ldc_ch4_wayback_verified_20260719', 0.15, 20
WHERE NOT EXISTS (SELECT 1 FROM jurisdictions WHERE name = 'Unincorporated Gadsden County');

-- 2. Zoning districts: RR / AG-1 / AG-2, sourced from LDC Chapter 4 category names
DO $$
DECLARE
  v_jur_id bigint;
  v_rr_id bigint;
  v_ag1_id bigint;
  v_ag2_id bigint;
BEGIN
  SELECT id INTO v_jur_id FROM jurisdictions WHERE name = 'Unincorporated Gadsden County';

  INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, description, far_regulated, density_regulated, pk1000_regulated)
  VALUES (v_jur_id, 'RR', 'Rural Residential', 'residential', 'LDC Ch. 4 Subsection 4102',
          'Gadsden County LDC Chapter 4 Land Use Category. Min lot size 1 acre, net density <= 1 DU/acre. No FAR or parking-count regulation in the ordinance for this category.',
          false, true, false)
  ON CONFLICT (jurisdiction_id, code) DO NOTHING;

  INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, description, far_regulated, density_regulated, pk1000_regulated)
  VALUES (v_jur_id, 'AG-1', 'Agriculture-1', 'residential', 'LDC Ch. 4 Table 4103',
          'Gadsden County LDC Chapter 4 Land Use Category. Density 1 DU/5 acres (un-clustered); no FAR or parking-count regulation in the ordinance for this category.',
          false, true, false)
  ON CONFLICT (jurisdiction_id, code) DO NOTHING;

  INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, description, far_regulated, density_regulated, pk1000_regulated)
  VALUES (v_jur_id, 'AG-2', 'Agriculture-2', 'residential', 'LDC Ch. 4 Table 4103',
          'Gadsden County LDC Chapter 4 Land Use Category. Density 1 DU/10 acres (un-clustered); no FAR or parking-count regulation in the ordinance for this category.',
          false, true, false)
  ON CONFLICT (jurisdiction_id, code) DO NOTHING;

  SELECT id INTO v_rr_id  FROM zoning_districts WHERE jurisdiction_id = v_jur_id AND code = 'RR';
  SELECT id INTO v_ag1_id FROM zoning_districts WHERE jurisdiction_id = v_jur_id AND code = 'AG-1';
  SELECT id INTO v_ag2_id FROM zoning_districts WHERE jurisdiction_id = v_jur_id AND code = 'AG-2';

  -- 3. Zone standards -- density only, confidence 0.85 per staleness caveat above
  INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, effective_date, confidence_score)
  VALUES (v_rr_id, 1.0,
          'https://web.archive.org/web/20201020071952/https://www.gadsdencountyfl.gov/Document%20Center/Departments/Planning%20&%20Community%20development/Land%20Development%20Regulations/Land%20Development%20Code/Chapter%204%20Land%20Use%20Categories.pdf',
          'Ch. 4 Subsection 4102', '2016-11-15', 0.85)
  ON CONFLICT (zoning_district_id) DO NOTHING;

  INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, effective_date, confidence_score)
  VALUES (v_ag1_id, 0.2,
          'https://web.archive.org/web/20201020071952/https://www.gadsdencountyfl.gov/Document%20Center/Departments/Planning%20&%20Community%20development/Land%20Development%20Regulations/Land%20Development%20Code/Chapter%204%20Land%20Use%20Categories.pdf',
          'Ch. 4 Table 4103', '2016-11-15', 0.85)
  ON CONFLICT (zoning_district_id) DO NOTHING;

  INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, effective_date, confidence_score)
  VALUES (v_ag2_id, 0.1,
          'https://web.archive.org/web/20201020071952/https://www.gadsdencountyfl.gov/Document%20Center/Departments/Planning%20&%20Community%20development/Land%20Development%20Regulations/Land%20Development%20Code/Chapter%204%20Land%20Use%20Categories.pdf',
          'Ch. 4 Table 4103', '2016-11-15', 0.85)
  ON CONFLICT (zoning_district_id) DO NOTHING;

  -- 4. Parcel-to-zone assignment for the 13 unincorporated auction parcels, sourced from
  -- a live ArcGIS point-in-polygon query against Gadsden_FLUM (no cross-layer overlap).
  INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source)
  SELECT v.parcel_id, v_jur_id, v.zone_code, v.zone_name, v.zone_name,
         'gadsden_flum_arcgis_layer_lastedit_20190114+ldc_ch4_wayback_20201020_verified_20260719'
  FROM (VALUES
    ('2-12-3N-5W-0000-00111-0200', 'RR', 'Rural Residential'),
    ('3-16-2N-3W-0785-00000-0120', 'RR', 'Rural Residential'),
    ('3-14-2N-2W-0565-0000E-0070', 'RR', 'Rural Residential'),
    ('1-31-4N-5W-0000-00144-0000', 'RR', 'Rural Residential'),
    ('6-04-1S-4W-0000-00341-0100', 'RR', 'Rural Residential'),
    ('2-34-3N-2W-0315-0000A-0350', 'RR', 'Rural Residential'),
    ('3-33-2N-3W-1529-00000-0190', 'RR', 'Rural Residential'),
    ('3-11-2N-2W-0000-00411-1000', 'RR', 'Rural Residential'),
    ('3-24-2N-5W-0000-00120-1300', 'RR', 'Rural Residential'),
    ('6-02-1S-4W-1250-0000B-0230', 'RR', 'Rural Residential'),
    ('2-07-3N-2W-0000-00133-0100', 'AG-2', 'Agriculture-2'),
    ('4-01-1N-5W-0000-00331-0100', 'AG-2', 'Agriculture-2'),
    ('2-25-3N-2W-0000-00343-0200', 'AG-1', 'Agriculture-1')
  ) AS v(parcel_id, zone_code, zone_name)
  WHERE NOT EXISTS (
    SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v_jur_id
  );
END $$;

COMMIT;
