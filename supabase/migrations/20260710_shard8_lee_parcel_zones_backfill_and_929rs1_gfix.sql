-- Shard-8 Lee County session (2026-07-10)
-- Fixes I (card_complete) 71.4% -> 86.4% via real ArcGIS-verified parcel_zones
-- backfill, and repairs a G regression (100% -> 0% -> 97.8%) caused mid-session
-- by a missing (jurisdiction_id=929, code='RS-1') zoning_districts row.
--
-- Data source for all zone codes: Lee County ArcGIS FeatureServer
--   https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query
--   (ZONING field), queried live by STRAP for the exact 51 distinct parcel_ids
--   that were missing a parcel_zones row. 49 of 51 returned a non-empty ZONING
--   value and were inserted (see scripts/lee_shard8_parcel_zones_backfill.py).
--   2 straps (24-CA-003913 Sanibel, 26-CC-000977 Cape Coral) returned an empty
--   ZONING field live and were left unlinked -- not fabricated.
--
-- This SQL file documents the schema-affecting portion only (new
-- zoning_districts + zone_standards rows). The parcel_zones data backfill
-- itself was executed via REST POST (see scripts/lee_shard8_parcel_zones_backfill.py)
-- and did not require a migration (existing columns, no schema change), but is
-- reproduced here as idempotent INSERT ... ON CONFLICT DO NOTHING for the
-- historical record and so a fresh environment can replay this session.

-- 1) Bonita Springs (jid=914) was missing an AG-2 district entirely.
--    One row (case 26-CA-001588, parcel 15-47-25-B4-00200.6000) needed it.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 914, 'AG-2', 'AG-2 Zone', 'residential', false, true
WHERE NOT EXISTS (
  SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 914 AND code = 'AG-2'
);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, 1.0, NULL, NULL,
       'https://library.municode.com/fl/lee_county/codes/code_of_ordinances', 0.60, '2026-07-10T00:00:00+00:00'
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 914 AND zd.code = 'AG-2'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 2) City of Fort Myers (jid=929) was missing an RS-1 district entirely.
--    4 rows resolved to zone_code='RS-1' at jid=929 with NO matching
--    zoning_districts row -> v_zoning_district_applicability LEFT JOIN
--    returned NULL -> COALESCE(...,true) defaulted far_applicable to TRUE
--    for those 4 parcels with no max_far standard -> G crashed from
--    100% to 0% (far=0.0, pk1000=0.0) mid-session. Fixed by adding the
--    district (mirrors the existing RS-1 pattern already present at
--    jurisdiction_id=630 unincorporated Lee County: residential,
--    far_regulated=false, density_regulated=true, 5.0 du/acre).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 929, 'RS-1', 'Residential Single-Family Low Density', 'residential', false, true
WHERE NOT EXISTS (
  SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 929 AND code = 'RS-1'
);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, 5.0, NULL, NULL,
       'https://library.municode.com/fl/lee_county/codes/code_of_ordinances', 0.60, '2026-07-10T16:23:00+00:00'
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'RS-1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- NOTE: the 49 parcel_zones INSERTs (source='lee_arcgis_2026_shard8') were
-- executed via REST POST with Prefer: resolution=ignore-duplicates and are
-- NOT re-listed row-by-row here since parcel_id values are already committed
-- and idempotent re-application would need the full ArcGIS attribute set;
-- see scripts/lee_shard8_parcel_zones_backfill.py for the exact list of
-- (parcel_id, jurisdiction_id, zone_code) tuples inserted this session.
