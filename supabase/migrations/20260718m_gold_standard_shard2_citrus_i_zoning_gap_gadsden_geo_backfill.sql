-- SHARD-2 (dispatch bca41e8b, session 2 -- same dispatch_id was already fully
-- executed once and shipped as a6022ea6; this is genuinely new follow-on work,
-- not a re-fire of identical work).
--
-- CITRUS letter I: 34 of the 35 zoning-ingestion-gated auction parcels (the
-- root cause documented in a6022ea6) were resolved via a live ArcGIS
-- point-in-polygon query against the ALREADY-PROVEN county endpoint
-- (maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0, field
-- HANSEN__PRCLZON_ZONING -- same source as the existing 46 citrus_gis-sourced
-- rows). Used a tight envelope buffer (2-17m) around each parcel's real,
-- distinct lat/lon and ONLY inserted when the query returned a single
-- unambiguous zone; 1 of the 35 (parcel 1199611) sits exactly on a
-- RUR MH / GNC boundary at every tested tolerance down to ~2m and was left
-- unresolved rather than guessed. Two new zoning_districts rows were added
-- (LDR MH, RUR MH under jurisdiction_id=1327 Unincorporated Citrus) with
-- names taken verbatim from the live GIS DSECRIPT field -- no numeric
-- density/FAR/parking standards were fabricated for them (zone_standards
-- left absent, matching HONESTY PROTOCOL / no-ghost-success).
--
-- Live pencil_dod_evaluate_county('citrus') before -> after (2026-07-18):
--   I: card_complete=143 of 189 (75.7%, FAIL) -> card_complete=177 of 189 (93.7%, FAIL)
--   G: density=97.7 (PASS) -> density=95.6 (PASS, no regression)
-- I remains FAIL (need 180/189=95%). Residual 12-row gap reconciled live:
--   7 auctions have NULL parcel_id in source data (genuinely unresolvable)
--   1 genuinely ambiguous zoning boundary (1199611, left unresolved on purpose)
--   ~4 calendar-sweep placeholder rows with no real address (documented in a6022ea6)
-- None of the residual gap is a zoning-ingestion problem anymore -- the
-- "Phase 3/4 zonewise ingestion gap" cited in a6022ea6 is now fully closed
-- for citrus; what remains is a source-data completeness problem out of
-- scope for this pass.
--
-- GADSDEN data-integrity fix (no letter flip, real progress not claimed as one):
-- All 23 gadsden multi_county_auctions rows carried the IDENTICAL placeholder
-- lat/lon (30.5768, -84.5875) for every row -- discovered while investigating
-- why a naive spatial-join zoning fix (the obvious next move per the G/I
-- playbook) would have been a ghost-success risk: querying an ArcGIS endpoint
-- with 23 identical coordinates would return the same zone for every parcel
-- regardless of where the parcel actually is. Found real, distinct
-- centroid_lat/centroid_lng already sitting in fl_parcels for 21 of the 23
-- gadsden parcels (keyed by parcel_id) and backfilled multi_county_auctions
-- latitude/longitude from that source. 2 rows have NULL parcel_id and were
-- left untouched. This does NOT flip any letter (E/G/I unchanged) -- it
-- removes a fabricated-looking placeholder from live production data so a
-- future zoning pass can do a real spatial join instead of an accidental
-- ghost-success. fl_parcels.zone_code is null for all 21 (no shortcut
-- available there either). 13 of 21 parcels are municipality='COUNTY'
-- (unincorporated) and there is still no "Unincorporated Gadsden" jurisdiction
-- row in `jurisdictions` -- that remains the real blocker for gadsden G/I,
-- consistent with a6022ea6's finding (qpublic/municode/gadsdencountyfl.gov
-- all Cloudflare-403 for parcel-level GIS).
--
-- Both changes applied live via Supabase REST (service-role) during this
-- session; this migration is the in-repo record of what was written.
-- Adversarially re-verified by two independent refuter agents (ULTRALOOP
-- protocol) against live DB + live ArcGIS source before this commit.
--
-- dispatch_id: bca41e8b-a306-444b-a860-b0f5c34e605a (session 2)

-- Citrus: 2 new zoning_districts codes discovered live via GIS DSECRIPT field
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
VALUES
  (1327, 'LDR MH', 'Low Density Residential - MH Allowed', 'Residential',
   'LOW DENSITY RES - MH ALLOWED (live GIS DSECRIPT field, maps.citrusbocc.com ZONING_DESCR/0)'),
  (1327, 'RUR MH', 'Rural Residential - MH Allowed', 'Residential',
   'RURAL RESIDENTIAL - MH ALLOWED (live GIS DSECRIPT field, maps.citrusbocc.com ZONING_DESCR/0)')
ON CONFLICT DO NOTHING;

-- Citrus: 34 parcel_zones rows from live single-match ArcGIS point-in-polygon queries
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('1112044', 1327, 'LDR MH', 'LOW DENSITY RES - MH ALLOWED', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1428521', 1327, 'PDR', 'PLANNED DEVELOP. RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1430101', 1327, 'RUR', 'RURAL RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1432383', 1327, 'RUR', 'RURAL RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1433673', 1327, 'RUR', 'RURAL RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1437237', 1327, 'RUR', 'RURAL RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1438519', 1327, 'RUR', 'RURAL RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1442621', 1327, 'RUR', 'RURAL RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1588782', 1327, 'LDR MH', 'LOW DENSITY RES - MH ALLOWED', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1634954', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1635110', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1635241', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1635781', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1637198', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1643422', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1644305', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1646081', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1646260', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1646308', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1648483', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1649382', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1649790', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1650437', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1650941', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('2948647', 1327, 'RUR', 'RURAL RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1482585', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1517494', 1327, 'RUR MH', 'RURAL RESIDENTIAL - MH ALLOWED', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1657407', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1657423', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1658900', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('1665001', 1327, 'MDR', 'MEDIUM DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('3220777', 1327, 'RUR MH', 'RURAL RESIDENTIAL - MH ALLOWED', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('3526121', 1327, 'CLR MH', 'COASTL/LAKES RESDNTL-MH ALLWED', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 15-17m envelope query, dispatch bca41e8b shard2 citrus-I-gap-close, verified single-zone match)'),
  ('2749164', 1327, 'LDR', 'LOW DENSITY RESIDENTIAL', 'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon 2-6m envelope, resolved unambiguous at tight tolerance after 65m buffer showed CLR/LDR boundary noise, dispatch bca41e8b)')
ON CONFLICT DO NOTHING;

-- Gadsden: real per-parcel geocoding backfill (fl_parcels.centroid_lat/lng),
-- replacing the identical (30.5768,-84.5875) placeholder that was present on
-- all 23 rows. Applied live via REST PATCH keyed on parcel_id during this
-- session; recorded here for audit trail (idempotent no-op if lat/lon already
-- matches fl_parcels).
UPDATE multi_county_auctions mca
SET latitude = fp.centroid_lat,
    longitude = fp.centroid_lng
FROM fl_parcels fp
WHERE mca.county = 'gadsden'
  AND mca.parcel_id = fp.parcel_id
  AND fp.centroid_lat IS NOT NULL
  AND fp.centroid_lng IS NOT NULL;
