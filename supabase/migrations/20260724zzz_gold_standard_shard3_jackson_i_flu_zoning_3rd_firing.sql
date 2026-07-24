-- Gold Standard shard-3 (jackson), dispatch da3fde1c-5c12-4786-bbda-4ea2708ee2e1, loop run 6253
-- (3rd firing of this dispatch -- today's trigger re-fired the same dispatch the 2nd firing
-- already shipped as commit 86d01a26; live DB matched that commit exactly at session start, so
-- this session picked up the 2nd firing's own documented "next_session_priorities" instead of
-- repeating completed work). Letter I (property card completeness), final 5 rows.
--
-- BACKGROUND: the 2nd firing's migration (20260724zz_..._jackson_i_flu_zoning.sql) resolved 7 of
-- 12 originally-uncovered parcels and left 5 unresolved as a "genuine research ceiling":
--   - 274N07000000700021 (Sneads) and 01-6N-12-0000-0250-0000 (Campbellton): centroid inside a
--     town's real corporate limits, town's own FLU map believed non-georeferenced (Sneads) or
--     nonexistent (Campbellton).
--   - 02-2N-11-0083-00V0-0070, 02-2N-11-0083-00V0-0080, 234N10000000500000: parcel genuinely
--     straddles two FLU categories, no area-clip capability available to pick a majority.
--
-- THIS SESSION resolved all 5, via an ultracode fan-out-research + adversarial-verify workflow
-- (5 builder agents, 5 independent refuters) followed by direct self-verification of the
-- highest-value refutation:
--
-- 1. GEOMETRY SOURCE for the 3 parcels that don't resolve via the FL GIO Statewide Cadastral
--    FeatureServer by exact PARCEL_ID (confirmed live: genuinely zero features for this plat's
--    dashed ID format, not a rate-limit artifact -- re-verified independently by the refuter).
--    Found a second, independent ArcGIS Online FeatureServer covering Jackson County parcels:
--    https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/Jackson_County_Parcel/FeatureServer
--    (ArcGIS item d399fbd4cca14cf2ab3e8a21c6865ab9, "Jackson County Florida Parcel Map",
--    FEMA_Archive, ~2018-2019 vintage -- geometry/address only, not used for current values).
--    Its APN field matches the dashed tax-roll format exactly for '02-2N-11-0083-00V0-0070' and
--    '...-0080' (Layer 1, Non-Residential Parcels), and for '01-6N-12-0000-0250-0000' (Layer 0,
--    Residential Parcels, SITE_STR=FERNWOOD, SITE_CITY=CAMPBELLTON). Fully independently
--    re-verified: every attribute, polygon ring, and negative finding (FDOT MapServer token-gated,
--    jacksonpa.com Cloudflare-gated) reproduced field-for-field by a separate refuter agent.
--
-- 2. AREA-WEIGHTED FLU SPLIT for the 3 straddling parcels, using the parcel's real polygon
--    geometry (from FL GIO cadastral or the FeatureServer above) intersected against every layer
--    of the Jackson County FLUM FeatureServer (services.arcgis.com/9Jk4Zl9KofTtvg3x/.../FLUM),
--    computed with shapely, cross-checked against ArcGIS's own authoritative Shape__Area field
--    (matched to 5 decimal places) and validated as a clean full-coverage, non-overlapping
--    partition (union of intersection pieces = parcel area; pairwise overlap = 0) on every parcel.
--    Independently re-derived by a refuter using a fully separate Python session -- all
--    percentages matched exactly:
--      - 234N10000000500000 (4624 Magnolia Rd): CORRECTS the 2nd firing's characterization --
--        the parcel does NOT straddle Residential/Conservation (Residential layer returns ZERO
--        features against this parcel's real polygon); it straddles AG2 (3.64%) / Conservation
--        (96.36%). Majority category: CONSERVATION.
--      - 02-2N-11-0083-00V0-0070 (Dixie Dr): Conservation 0.08% / Residential 99.92%. Majority:
--        RESIDENTIAL.
--      - 02-2N-11-0083-00V0-0080 (Dixie Dr): Conservation 12.58% / Residential 87.42%. Majority:
--        RESIDENTIAL.
--    All 3 confirmed OUTSIDE any incorporated place via US Census TIGERweb Incorporated Places
--    (re-verified live by me directly, not just the workflow), so the county FLUM is the correct
--    land-use authority for each.
--
-- 3. TOWN-LEVEL FLU for Sneads and Campbellton: a research agent's finding that no georeferenced
--    per-town FLU data exists (Sneads' adopted map is a raster-only PDF, confirmed at the PDF
--    content-stream level -- 32 image "Do" operators, 0 vector fill operators) was REFUTED by its
--    own adversarial verifier, which re-ran the exact same ArcGIS Online item-search query the
--    builder used and found the builder had stopped at the first hit instead of reading the full
--    result list. Two additional, real, per-town vector FeatureServers exist in that same result
--    set for EVERY Jackson County municipality:
--      https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/Sneads_FLUM/FeatureServer
--      https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/Campbellton_FLUM/FeatureServer
--    Both carry a `Category` field (10 real categories for Sneads incl. Agriculture, Commercial,
--    Conservation, Residential-Suburban etc. -- matching the PDF's own legend text verbatim,
--    confirming this is the actual underlying georeferenced source data behind that PDF).
--    I independently re-verified this refutation myself, live, before relying on it (per
--    ULTRALOOP protocol -- a refuter's own claim gets the same scrutiny, not a free pass):
--      curl Sneads_FLUM/FeatureServer/0/query at the Sneads parcel's exact centroid (EPSG:3086,
--      x=312019.62789409666 y=745725.2717292765) -> FID=76, Category="Agriculture". Reproduced.
--      curl Campbellton_FLUM/FeatureServer/0/query at both of the Campbellton parcel's split-
--      geometry centroids (EPSG:4326: 30.946193,-85.395442 and 30.945725,-85.395425) -> FID=52
--      and FID=40, BOTH Category="Residential-Suburban" -- consistent, no split ambiguity.
--
-- Verified live before (re-run at start of this session, matched the 2nd firing's committed
-- final_state exactly, confirming no drift and no other shard touching these rows):
--   SELECT public.pencil_dod_evaluate_county('jackson')
--   I: {"pass":false,"detail":"card_complete=68 of 73","metric":93.2}
-- Verified live after (re-run immediately post-application, in the session, before this file was
-- committed):
--   I: {"pass":true,"detail":"card_complete=73 of 73","metric":100.0}
--   G: {"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0}  -- unchanged, no
--     regression (checked immediately per the P0 lesson from the wakulla G-regression fix earlier
--     in this campaign -- new zone codes without matching zoning_districts/zone_standards rows
--     silently fail the density denominator).
-- jackson reaches 10/10 on this migration (I is the county's only remaining failing letter).
--
-- Applied live via the Supabase REST API (service-role key) -- direct psql/pooler access was
-- unavailable in this sandbox (stale DB_PASSWORD, consistent with both prior firings). This file
-- is the durable record of exactly what was written; statements are idempotent to re-run.

BEGIN;

-- New zoning district: Conservation, for unincorporated Jackson County (corrects the 2nd
-- firing's belief that 234N10000000500000 was Residential/Conservation -- it is AG2/Conservation,
-- majority Conservation).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT j.id, 'FLU-CONSERVATION',
  'Future Land Use: Conservation -- Jackson County FLUM FeatureServer, LAND_USE=''Conservation'', Max_Densit=''1 per 40 Acres''. Same FLU schema as FLU-RES/FLU-AG2 -- no FAR/parking figure exists; far_regulated/pk1000_regulated explicitly false.',
  'conservation', false, false, true
FROM jurisdictions j WHERE j.name = 'Unincorporated Jackson County' AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT zd.id, 1.0/40.0, 'https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/FLUM/FeatureServer/3 (Jackson_Conservation, Max_Densit field)', 'Jackson County FLUM 2018'
FROM zoning_districts zd JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.name = 'Unincorporated Jackson County' AND zd.code = 'FLU-CONSERVATION'
ON CONFLICT DO NOTHING;

-- New zoning district: Town of Sneads, Agriculture category. This is a SEPARATE, real,
-- georeferenced vector FeatureServer (Category field) from the county's own FLUM -- Sneads'
-- schema has no per-acre density figure at all (only Category/Shape__Area/Shape__Length), hence
-- density_regulated explicitly false rather than fabricated, same honesty pattern already applied
-- to far/pk1000 on the county districts.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT j.id, 'FLU-SNEADS-AG',
  'Future Land Use: Agriculture -- Town of Sneads FLUM FeatureServer (services.arcgis.com/9Jk4Zl9KofTtvg3x/.../Sneads_FLUM/FeatureServer, Category=''Agriculture''). Town-maintained vector FLU layer, separate from the county FLUM -- schema carries only Category/Shape__Area/Shape__Length, no density/FAR/parking figures exist, hence far_regulated/pk1000_regulated/density_regulated all explicitly false.',
  'agricultural', false, false, false
FROM jurisdictions j WHERE j.name = 'Sneads' AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, source_url, ordinance_section)
SELECT zd.id, 'https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/Sneads_FLUM/FeatureServer/0 (Category field, FID=76)', 'Town of Sneads FLUM (Existing and Future Land Use Map 2017-2027, adopted 11-11-17)'
FROM zoning_districts zd JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.name = 'Sneads' AND zd.code = 'FLU-SNEADS-AG'
ON CONFLICT DO NOTHING;

-- New zoning district: Town of Campbellton, Residential-Suburban category. Same town-level
-- vector FLU pattern as Sneads -- no density/FAR/parking figures in this schema either.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT j.id, 'FLU-CAMPBELLTON-RES',
  'Future Land Use: Residential-Suburban -- Town of Campbellton FLUM FeatureServer (services.arcgis.com/9Jk4Zl9KofTtvg3x/.../Campbellton_FLUM/FeatureServer, Category=''Residential-Suburban''). Town-maintained vector FLU layer, separate from the county FLUM -- schema carries only Category/Shape__Area/Shape__Length, no density/FAR/parking figures exist, hence far_regulated/pk1000_regulated/density_regulated all explicitly false.',
  'residential', false, false, false
FROM jurisdictions j WHERE j.name = 'Campbellton' AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, source_url, ordinance_section)
SELECT zd.id, 'https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/Campbellton_FLUM/FeatureServer/0 (Category field, FID=52 and FID=40, both split-geometry pieces of the parcel agree)', 'Town of Campbellton FLUM'
FROM zoning_districts zd JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.name = 'Campbellton' AND zd.code = 'FLU-CAMPBELLTON-RES'
ON CONFLICT DO NOTHING;

-- The 5 parcels, each linked to its resolved jurisdiction + zone code.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT v.parcel_id, j.id, v.zone_code, v.zone_name, v.future_land_use, v.source
FROM (VALUES
  ('234N10000000500000',       'Unincorporated Jackson County', 'FLU-CONSERVATION',   'Conservation (majority 96.36% of parcel area, area-weighted split vs AG2 3.64%)', 'Conservation',        'jackson_flum_areasplit:shard3_run6253_3rd_firing'),
  ('02-2N-11-0083-00V0-0070',  'Unincorporated Jackson County', 'FLU-RES',            'Residential (Compass Lake HOA, majority 99.92% of parcel area, area-weighted split vs Conservation 0.08%)', 'Residential', 'jackson_flum_areasplit:shard3_run6253_3rd_firing'),
  ('02-2N-11-0083-00V0-0080',  'Unincorporated Jackson County', 'FLU-RES',            'Residential (Compass Lake HOA, majority 87.42% of parcel area, area-weighted split vs Conservation 12.58%)', 'Residential', 'jackson_flum_areasplit:shard3_run6253_3rd_firing'),
  ('274N07000000700021',       'Sneads',                        'FLU-SNEADS-AG',      'Agriculture (Town of Sneads FLUM)', 'Agriculture',         'sneads_flum_pointinpolygon:shard3_run6253_3rd_firing'),
  ('01-6N-12-0000-0250-0000',  'Campbellton',                   'FLU-CAMPBELLTON-RES','Residential-Suburban (Town of Campbellton FLUM)', 'Residential-Suburban', 'campbellton_flum_pointinpolygon:shard3_run6253_3rd_firing')
) AS v(parcel_id, jurisdiction_name, zone_code, zone_name, future_land_use, source)
JOIN jurisdictions j ON j.name = v.jurisdiction_name AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

COMMIT;
