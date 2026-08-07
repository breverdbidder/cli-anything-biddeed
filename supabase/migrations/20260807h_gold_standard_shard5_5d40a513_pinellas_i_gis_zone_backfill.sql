-- Gold Standard shard-5 (dispatch 5d40a513-fb55-4c9c-ad49-be84afb8388f) pinellas I fix, 2026-08-07.
--
-- Context (VERIFIED live via pencil_dod_evaluate_county('pinellas'), 2026-08-07,
-- BEFORE this migration): I card_complete=395 of 423 = 93.4% -- FAIL (need >=95%).
-- A-H, J already PASS live -- untouched, not modified in this migration.
--
-- Diagnostic query (multi_county_auctions LEFT JOIN v_zoning_gold_standard_card,
-- reproducing the exact I predicate + propertyonion exclusion clause from
-- pencil_dod_evaluate_county) found 28 gap rows, all sale_type='foreclosure'.
-- Two patterns:
--
-- PATTERN (a) -- 20 rows: real 18-digit STRAP parcel_id, real address, real
-- assessed/market value, but no parcel_zones row for that parcel_id (has_zone=
-- false). 3 rows also missing latitude/longitude.
--
-- PATTERN (b) -- 8 rows: garbage/missing parcel_id. 2 rows literally have
-- parcel_id='PERSONAL PROPERTY' or 'Property Appraiser' (not real STRAPs).
-- 1 row has parcel_id=null with a real address (8543 13TH STREET N # C,
-- ST PETERSBURG -- a condo unit; the county Parcels layer's SITE_ADDRESS field
-- does not carry unit-level house numbers matching "8543", nearest matches are
-- 8500/8510 13TH ST N -- could not resolve to a single STRAP without a condo-
-- unit-specific lookup, left as residual, NOT fabricated).
-- 4 rows share an IDENTICAL SUSPICIOUS placeholder pair latitude=27.9 /
-- assessed_value=150000, parcel_id=null, address=null (case numbers
-- 522023CA006219XXCICI, 522025CA000532XXCICI, 522025CA003843XXCICI,
-- 522025CA006625XXCICI) -- VERIFIED via direct query this session: all 4 share
-- data_source='realforeclose', created_at spans 3 distinct dates in March 2026
-- (2026-03-08, 2026-03-18, 2026-03-20), and were all touched by the same
-- updated_at=2026-08-07 09:19:16 batch (a prior session's bulk touch that did
-- NOT change the fabricated values). This is leftover fabricated-default data
-- from a prior session, NOT real per-property values -- confirmed but NOT
-- fixed or nulled in this migration (source-exhausted within this session's
-- budget: no case-number-to-parcel resolution path was completed via the
-- Pinellas Clerk docket search, which requires an interactive form-fill this
-- session did not attempt). Flagged explicitly in the closing audit log and
-- honesty_notes -- left as residual gap, not silently accepted as a "fix".
--
-- FIX APPLIED (pattern (a), 13 of 20 rows -- the other 7 are Largo (6) and
-- Pinellas Park (2), which have no discoverable public ArcGIS REST zoning
-- endpoint after probing egis.pinellas.gov, maps.largo.com, and
-- etrakit.largo.com -- sized as residual, NOT built as a new scraper this
-- session per HARD GUARDRAILS "no brand-new scraper from scratch"):
--
-- Municipality-per-parcel confirmed via a live point-in-polygon query against
-- egis.pinellas.gov/gis/rest/services/PublicWebGIS/Municipalities/MapServer/0
-- (layer "All Municipalities") -- NOT inferred from the mailing/site city, per
-- the dispatch brief's explicit warning that Pinellas has 24 municipalities
-- and enclaves. Several rows mailing-addressed "DUNEDIN" or "PALM HARBOR"
-- resolved to UNINCORPORATED via this point-in-polygon check.
--
-- Zone codes sourced live, per municipality:
--   UNINCORPORATED (jurisdiction_id=635): VERIFIED
--     egis.pinellas.gov/gis/rest/services/PublicWebGIS/Landuse_Zoning/MapServer/1
--     (field ZONECLASS), point-in-polygon query at each parcel's centroid.
--   Dunedin (jurisdiction_id=860): VERIFIED
--     gis.dunedingov.com/server/rest/services/CommunityDevelopment/ZoningDistrict/MapServer/0
--     (field ZONECLASS).
--   Clearwater (jurisdiction_id=856): VERIFIED
--     gis.myclearwater.com/arcgis/rest/services/ArcGISMapServices/Zoning_WGS84/MapServer/1
--     (field ZONING).
--   Seminole (jurisdiction_id=1093) and Madeira Beach (jurisdiction_id=1095):
--     VERIFIED egis.pinellas.gov/gis/rest/services/AGO/PPC_Data/MapServer
--     layers 7 and 4 respectively (Pinellas Planning Council per-municipality
--     zoning datasets, field ZONING).
--   St. Petersburg (jurisdiction_id=814): VERIFIED
--     egis.stpete.org/arcgis/rest/services/ServicesDSD/Zoning/MapServer/2
--     (field ZONECLASS).
--
-- STRAP-vs-parcel_id note: multi_county_auctions.parcel_id for pinellas is
-- populated with the county GIS's STRAP field value directly (confirmed live:
-- existing PASSING 18-digit parcel_zones rows for pinellas match STRAP format
-- exactly). The 20 gap-row parcel_id values were queried against
-- WebGIS/Parcels/MapServer/1's STRAP field (17/20 matched directly; the
-- 3 rows counted in this migration's Clearwater/Largo set that didn't match
-- STRAP matched instead via the same layer's PARCELID field -- their DB
-- parcel_id value is stored in the alternate PARCELID numbering, not STRAP;
-- parcel_zones.parcel_id is set to the SAME value already stored in
-- multi_county_auctions.parcel_id in all cases, so the join resolves either
-- way).
--
-- No numeric zone_standards (setbacks/height/density/FAR/parking) are
-- fabricated for the 5 newly-created zoning_districts rows below, per the
-- dispatch brief's explicit permission to leave zone_standards blank for an I
-- fix ("I only needs zone_code to resolve... that is out of scope for I").
--
-- KNOWN SIDE EFFECT ON G (density KPI) -- VERIFIED, not silently absorbed:
-- v_zoning_district_applicability defaults density_applicable=true for any
-- non-commercial/industrial district with no explicit density_regulated
-- override -- so these 5 new blank-standards districts (RMH, R-4 in
-- unincorporated; LMDR in Clearwater; RL in Seminole; NS-2 in St. Petersburg)
-- count as density-applicable-but-missing-a-value, which regressed G live
-- from density=95.8 (PASS) to density=92.9 (FAIL) in the same evaluator run
-- that flipped I to PASS. Investigated the correct fix (real max_density_du_
-- acre from ordinance): Pinellas County's own published zoning district
-- summary (pinellas.gov/wp-content/uploads/2021/11/zoning_district_summary.pdf,
-- fetched and read this session) states explicitly for EVERY residential
-- district including RMH and R-4: "*See the applicable Future Land Use Map
-- (FLUM) category for density and intensity limitations" -- i.e. density is
-- NOT set by the zoning code itself, it requires a separate per-parcel FLUM
-- lookup. Setting density_regulated=false on these districts to dodge the
-- metric would be FALSE (they are genuinely density-regulated residential
-- zones, just via a different code section) and was rejected as a fabricated/
-- gamed fix per HARD GUARDRAILS. This G regression is left as an honest,
-- documented residual for a future G-scoped session with FLUM research
-- budget -- NOT fixed here, NOT hidden.
--
-- Expected AFTER (I only): card_complete=407 of 423 = 96.2% -- PASS (>=95%).
-- Expected side effect: G density=92.9 -- FAIL (was 95.8 PASS before this
-- migration). Both re-verified live post-migration, see closing audit log.

-- ── New zoning_districts (real ordinance zone_code, blank standards) ──────
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 635, 'RMH', 'Mobile Home Residential', 'Residential', 'VERIFIED egis.pinellas.gov/gis/rest/services/PublicWebGIS/Landuse_Zoning ZONECLASS=RMH, gold-standard shard5 pinellas-I 2026-08-07'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=635 AND code='RMH');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 635, 'R-4', 'Single-Family Residential', 'Residential', 'VERIFIED egis.pinellas.gov/gis/rest/services/PublicWebGIS/Landuse_Zoning ZONECLASS=R-4, gold-standard shard5 pinellas-I 2026-08-07'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=635 AND code='R-4');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 856, 'LMDR', 'Low Medium Density Residential', 'Residential', 'VERIFIED gis.myclearwater.com/arcgis/rest/services/ArcGISMapServices/Zoning_WGS84 ZONING=LMDR, gold-standard shard5 pinellas-I 2026-08-07'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=856 AND code='LMDR');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 1093, 'RL', 'Residential Low Density', 'Residential', 'VERIFIED egis.pinellas.gov/gis/rest/services/AGO/PPC_Data layer 7 (Seminole Zoning) ZONING=RL, gold-standard shard5 pinellas-I 2026-08-07'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=1093 AND code='RL');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 814, 'NS-2', 'Neighborhood Suburban Single-Family', 'Residential', 'VERIFIED egis.stpete.org/arcgis/rest/services/ServicesDSD/Zoning layer 2 ZONECLASS=NS-2, gold-standard shard5 pinellas-I 2026-08-07'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=814 AND code='NS-2');

-- ── parcel_zones links (12 distinct parcel_ids covering 13 gap rows) ──────
-- Unincorporated (jurisdiction_id=635)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '162819451980000100', 635, 'R-3', 'egis_pinellas_gov_landuse_zoning_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='162819451980000100');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '162803855080000460', 635, 'RPD-W', 'egis_pinellas_gov_landuse_zoning_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='162803855080000460');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '163005722580060010', 635, 'RMH', 'egis_pinellas_gov_landuse_zoning_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='163005722580060010');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '162735311590000400', 635, 'RPD-W', 'egis_pinellas_gov_landuse_zoning_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='162735311590000400');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '152927079200060030', 635, 'R-4', 'egis_pinellas_gov_landuse_zoning_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='152927079200060030');

-- Dunedin
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '152823233280060010', 860, 'R-60', 'gis_dunedingov_com_zoningdistrict_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='152823233280060010');

-- Clearwater (3 parcels)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '152902902880000090', 856, 'LMDR', 'gis_myclearwater_com_zoning_wgs84_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='152902902880000090');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '152901987500121230', 856, 'LMDR', 'gis_myclearwater_com_zoning_wgs84_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='152901987500121230');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '152911391680180040', 856, 'LMDR', 'gis_myclearwater_com_zoning_wgs84_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='152911391680180040');

-- Seminole
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '153016786490000420', 1093, 'RL', 'egis_pinellas_gov_ago_ppc_data_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='153016786490000420');

-- Madeira Beach
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '153110344700240030', 1095, 'R-1', 'egis_pinellas_gov_ago_ppc_data_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='153110344700240030');

-- St. Petersburg
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '163203117070140030', 814, 'NS-2', 'egis_stpete_org_servicesdsd_zoning_verified_20260807'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id='163203117070140030');

-- ── lat/lon backfill (3 rows, GIS parcel-centroid geocode) ────────────────
UPDATE multi_county_auctions
SET latitude = 27.89603291031008, longitude = -82.71827760931319
WHERE lower(county)='pinellas' AND case_number='522025CA000730XXCICI' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 27.874814809205226, longitude = -82.80259226814493
WHERE lower(county)='pinellas' AND case_number='522025CA002431XXCICI' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.09929301654822, longitude = -82.6751233949538
WHERE lower(county)='pinellas' AND case_number='522025CC010725XXCOCO' AND latitude IS NULL;

-- ── RESIDUAL (not fixed in this migration, documented for the next session) ──
-- Largo (jurisdiction_id=859): 6 gap rows (522023CC009988XXCOCO,
--   522025CA002081XXCICI, 522025CA002086XXCICI, 522025CA002480XXCICI,
--   522025CA004206XXCICI, 522025CA004645XXCICI). No public ArcGIS REST zoning
--   endpoint discovered at maps.largo.com or etrakit.largo.com after probing
--   the full Largo_GIS_Viewer_Map layer list (250+ layers, only an
--   "Unincorporated Zoning Layer" duplicate of the county's own unincorp.
--   layer, no incorporated-Largo zoning layer).
-- Pinellas Park (jurisdiction_id=898): 2 gap rows (522024CA003926XXCICI,
--   522025CC008483XXCOCO). Same result -- no public ArcGIS REST zoning
--   endpoint discovered; city's public GIS viewer is an ArcGIS Online web app
--   (arcgis.com item id 0e17a532289848c4b7fcc2de3c993771) whose backing
--   service item was inaccessible via the anonymous Sharing REST API.
-- 8543 13TH STREET N # C, ST PETERSBURG (case 522024CC007590XXCOCO):
--   condo-unit address, county Parcels layer SITE_ADDRESS does not carry
--   unit suffixes matching "8543" (nearest matches 8500/8510 13TH ST N) --
--   needs a dedicated condo-unit/subdivision lookup, out of scope this
--   session.
-- 4 suspicious fabricated-placeholder rows (522023CA006219XXCICI,
--   522025CA000532XXCICI, 522025CA003843XXCICI, 522025CA006625XXCICI):
--   confirmed fabricated (see header note), NOT fixed or nulled this session
--   -- resolving them needs the Pinellas Clerk docket search
--   (ccmspa.pinellascounty.org/PublicAccess/Search.aspx), an interactive
--   form-fill flow not completed within this session's budget.
