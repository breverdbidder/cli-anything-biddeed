-- Gold Standard shard-3 (jackson), dispatch da3fde1c-5c12-4786-bbda-4ea2708ee2e1, loop run 6253
-- (2nd firing of this dispatch). Letter I (property card completeness).
--
-- BACKGROUND: the 1st firing's commit (0587f682) left jackson I at 61/73 (83.6%), reporting a
-- "genuine research ceiling" for the other 12 rows: unincorporated Jackson County was believed
-- to use Future Land Use (FLU) categories instead of zoning districts (no zone_code to assign),
-- Jackson's Property Appraiser/Clerk portals are Cloudflare-gated, and Sneads' zoning map could
-- not be fetched live.
--
-- THIS SESSION found the actual Jackson County FLUM (Future Land Use Map) ArcGIS FeatureServer
-- (services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/FLUM/FeatureServer, 12 layers:
-- AG1/AG2/Commercial/Conservation/Incorporated/Industrial/Industrial2/MUUT/Public/Recreation/
-- Residential/RMHP, vintage 2018-07-18) -- confirming the FLU-not-zoning premise directly, and
-- making per-parcel FLU categories genuinely sourceable (this service was not found in the 1st
-- firing). Per the same-campaign precedent already committed for Taylor County
-- (20260724d_shard13_taylor_i_flu_geopdf_parcel_zones.sql), an FLU category is an acceptable
-- zone_code substitute for unincorporated parcels whose actual land-use authority is FLU-based,
-- provided (a) a real zoning_districts row backs the code so v_zoning_gold_standard_kpi_v3 does
-- not silently default it to "applicable but missing" (the exact regression class already fixed
-- once this session for wakulla, 20260724x_gold_standard_shard3_wakulla_g_regression_fix.sql),
-- and (b) far_regulated/pk1000_regulated are set false where the FLU schema genuinely has no
-- such figures (verified: Max_Densit is the only bulk-standard field on this FeatureServer;
-- no FAR or per-1000sf parking attribute exists anywhere in it).
--
-- Of the 12 uncovered rows, an initial 5-agent research + adversarial-refutation workflow's
-- Jackson finding was marked REFUTED by its own verifier -- but only over one incidental,
-- unrelated claim (whether library.municode.com/fl/sneads returns HTTP 403 or 200; the refuter
-- got 200). The refuter's own reasoning independently reproduced every substantive geodata fact
-- (the FLUM FeatureServer's existence/schema, all 12 parcels' FLU categories, the incorporated/
-- unincorporated determination for each). Rather than apply the whole finding on a partially-
-- refuted verdict, every fact actually used below was RE-VERIFIED live, directly, in this
-- session (not merely re-trusting the refuted claim): each of the 7 parcel_id -> FLU category
-- lookups was re-run live against the FDOR Statewide Cadastral (geometry) + Jackson FLUM
-- FeatureServer (LAND_USE/F_NAME/Max_Densit) + US Census TIGERweb Incorporated Places (to
-- confirm each parcel sits outside any town's real corporate limits, not just its mailing
-- city) -- all 7 independently reproduced with zero divergence from the workflow's original
-- claim.
--
-- 7 of the 12 parcels resolve cleanly to a single, unambiguous FLU designation and are applied
-- here. The other 5 are NOT touched, honestly left as-is:
--   - 274N07000000700021 (2114 3rd Ave, Sneads) and 01-6N-12-0000-0250-0000 (Fernwood St,
--     Campbellton): centroid falls INSIDE their towns' real corporate limits (confirmed via
--     TIGERweb + the county's own FLUM, which labels their polygon LAND_USE='Incorporated') --
--     falsifying the 1st firing's "unincorporated based on mailing city" assumption for these 2
--     specifically. Their FLU/zoning authority is the town, not the county. Sneads has its own
--     adopted FLU map (PDF, non-georeferenced, no parcel-level lookup possible without
--     fabricating a color read); Campbellton has no findable GIS/ordinance online at all. Left
--     unresolved, not guessed.
--   - 02-2N-11-0083-00V0-0070, 02-2N-11-0083-00V0-0080 (Dixie Dr), 234N10000000500000 (Magnolia
--     Rd): each parcel's polygon genuinely intersects TWO FLU categories (Residential +
--     Conservation, or Ag_2 + Conservation) with no area-clip/geometry-service access available
--     to compute which designation actually covers the buildable portion. Assigning either
--     single code without that split would be a guess. Left unresolved.
--
-- Verified live before: SELECT public.pencil_dod_evaluate_county('jackson')
--   I: {"pass":false,"detail":"card_complete=61 of 73","metric":83.6}
-- Verified live after (re-run post-application):
--   I: {"pass":false,"detail":"card_complete=68 of 73","metric":93.2}
--   G: {"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0}  -- unchanged, no
--     regression (re-checked immediately after applying, per the P0 lesson from the wakulla fix
--     earlier this same session).
-- jackson I remains FAIL (93.2%, needs 70/73=95.9% -- 2 more of the remaining 5 rows would be
-- needed) but moved materially. The 5 remaining rows are a genuine ceiling this session (2
-- incorporated-town parcels with no town-level parcel lookup, 3 dual-FLU parcels with no area
-- split available) -- not fabricated, not further guessed.
--
-- Applied live via the Supabase REST API (service-role key) during this session -- direct
-- psql/pooler access was unavailable in this sandbox (stale DB_PASSWORD). This file is the
-- durable record of exactly what was written; statements are idempotent to re-run.

BEGIN;

INSERT INTO jurisdictions (name, county, state, data_source)
VALUES ('Unincorporated Jackson County', 'Jackson', 'FL', 'shard3_run6253_2nd_firing')
ON CONFLICT DO NOTHING;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT j.id, 'FLU-RES',
  'Future Land Use: Residential (Compass Lake Home Owners Assoc.) -- Jackson County FLUM FeatureServer, LAND_USE=''Residential'', Max_Densit=''Min 1 per Acre Max 4 per Acre''. Unincorporated Jackson County is regulated by Future Land Use category, not a traditional zoning district -- no FAR or per-1000sf parking figure exists in this FLU schema, hence far_regulated/pk1000_regulated explicitly false rather than fabricated.',
  'residential', false, false, true
FROM jurisdictions j WHERE j.name = 'Unincorporated Jackson County' AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT j.id, 'FLU-AG2',
  'Future Land Use: Agriculture 2 -- Jackson County FLUM FeatureServer, LAND_USE=''Ag_2'', Max_Densit=''1 per 1 Acre''. Same FLU schema as FLU-RES -- no FAR/parking figure exists; far_regulated/pk1000_regulated explicitly false.',
  'agricultural', false, false, true
FROM jurisdictions j WHERE j.name = 'Unincorporated Jackson County' AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT zd.id, 4.0, 'https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/FLUM/FeatureServer/10 (Jackson_Residential, Max_Densit field)', 'Jackson County FLUM 2018'
FROM zoning_districts zd JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.name = 'Unincorporated Jackson County' AND zd.code = 'FLU-RES'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT zd.id, 1.0, 'https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/FLUM/FeatureServer/1 (Jackson_AG2, Max_Densit field)', 'Jackson County FLUM 2018'
FROM zoning_districts zd JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.name = 'Unincorporated Jackson County' AND zd.code = 'FLU-AG2'
ON CONFLICT DO NOTHING;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT v.parcel_id, j.id, v.zone_code, v.zone_name, v.future_land_use,
  'jackson_flum_featureserver_pointinpolygon:shard3_run6253_2nd_firing'
FROM (VALUES
  ('02-2N-11-0083-10AE-0300', 'FLU-RES', 'Residential (Compass Lake HOA)', 'Residential'),
  ('02-2N-11-0083-10AE-0280', 'FLU-RES', 'Residential (Compass Lake HOA)', 'Residential'),
  ('02-2N-11-0083-00F0-0120', 'FLU-RES', 'Residential (Compass Lake HOA)', 'Residential'),
  ('02-2N-11-0083-00V0-0060', 'FLU-RES', 'Residential (Compass Lake HOA)', 'Residential'),
  ('02-2N-11-0083-10AD-0060', 'FLU-RES', 'Residential (Compass Lake HOA)', 'Residential'),
  ('02-2N-11-0083-00V0-0010', 'FLU-RES', 'Residential (Compass Lake HOA)', 'Residential'),
  ('065N08000000700040',      'FLU-AG2', 'Agriculture 2', 'Ag_2')
) AS v(parcel_id, zone_code, zone_name, future_land_use)
JOIN jurisdictions j ON j.name = 'Unincorporated Jackson County' AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

COMMIT;
