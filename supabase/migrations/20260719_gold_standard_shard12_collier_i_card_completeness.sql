-- ============================================================
-- Collier I fix -- REAL city-level zoning wiring (Naples + Marco Island)
-- Dispatch: Gold Standard shard-12 (collier), run continuation of
--           20260711_gold_standard_shard1_collier_i_zoning_gis_wiring.sql
-- Counties: collier only
-- ============================================================
--
-- CONTEXT (VERIFIED live 2026-07-19):
--   pencil_dod_evaluate_county('collier') showed I: card_complete=190 of 212
--   (89.6%, need >=95%). The prior migration (20260711) linked 190 of 204
--   lat/lon-enriched collier parcels to REAL unincorporated-Collier zoning
--   (jurisdiction_id=632), and explicitly left 14 parcels unlinked because
--   they sit inside an INCORPORATED city (Naples, Marco Island, Everglades
--   City) whose zoning is not tracked in Collier County's own
--   Zoning_General layer. That migration sized city-level zoning lookup as
--   a residual for a future session. This migration is that session.
--
-- RESEARCH (two prior fact-finding agents, this session):
--   Group 1 (14 incorporated-city parcels): found and queried REAL public
--   city zoning FeatureServers for Naples and Marco Island. Point-in-polygon
--   (geometry=parcel centroid lon,lat, spatialRel=esriSpatialRelIntersects)
--   against:
--     Naples:       https://g.naplesgov.com/arcgis/rest/services/Planning/Zoning/FeatureServer/0
--                   (fields: Layer=zone code alias "Zone", Descript=description)
--     Marco Island:  https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3
--                   (fields: ZONING=zone code, DESCRIP=description, PUD_NAME, ORD_1/ORD_2)
--   13 of 14 resolved a real zone_code (4 Naples + 9 Marco Island). The 14th,
--   Everglades City case 26111 (parcel_id 83741800007), is a genuine dead
--   end: no ArcGIS FeatureServer/MapServer for Everglades City zoning exists
--   anywhere discoverable (ArcGIS Online, arcgis.com, collier.gov,
--   cityofeverglades.org all searched). Only resource found is a static,
--   non-interactive 1992 PDF land use map -- not point-in-polygon queryable
--   and 30+ years stale. Left NULL, honestly reported as a residual gap.
--
--   Group 2 (8 no-DOR-match folios: case_number 23164, 24099, 24108, 24109,
--   24110, 24111, 24147, 25184): attempted lookup via collierappraiser.com
--   (blocked -- legacy ASP.NET WebForms app requires a live JS-executed
--   cookie handshake, not scriptable via plain HTTP/curl/WebFetch), FL DOR
--   statewide cadastral FeatureServer re-checked with the correct
--   CO_NO=21 for Collier (confirmed via cross-check against 5 known-good
--   Collier parcel_ids already in multi_county_auctions) -- zero matches,
--   confirming these 8 folios use a legacy/different numbering format not
--   present in the statewide layer. Also tried Collier County GIS Hub,
--   GMCD GIS Hub (zoning/planning layers only, no parcel-value dataset),
--   county-taxes.net/fl-collier (HTTP 403 WAF block), Firecrawl (account
--   out of credits), browser-use CLI (not installed in this environment).
--   All 8 remain fully unenriched (no address/lat/lng/value) -- genuinely
--   UNKNOWN, not fabricated. NO WRITES made for Group 2 in this migration.
--
-- FIX (this migration):
--   Step 1: insert 'RSF-3' into zoning_districts for jurisdiction_id=879
--   (Marco Island) -- the other 2 needed codes (RMF-16, RMF-6) already
--   existed from prior real-ordinance seeding; Naples' 3 needed codes
--   (R3-12, R3T-12, R1-7.5) already existed too. ON CONFLICT DO NOTHING
--   throughout so no existing real ordinance data is overwritten.
--   Step 2: insert 13 real parcel_zones rows (4 Naples + 9 Marco Island),
--   sourced from the live city FeatureServer queries above, citing
--   the exact FeatureServer URL + queried point per row.
--
-- NOT LINKED in this migration (deliberately, not a fabrication gap):
--   case 26111 / parcel_id 83741800007 (Everglades City) -- no discoverable
--   real zoning GIS layer exists for this city. Remains excluded from I's
--   numerator.
--   8 Group 2 folios (case 23164, 24099, 24108, 24109, 24110, 24111,
--   24147, 25184) -- no enrichment (address/lat/lng/value) could be
--   retrieved this session; without lat/lng there is nothing to
--   point-in-polygon query. Remain excluded from I's numerator.
--   Net: this migration targets 13 of the 22 previously-failing rows.
--   Expected result: card_complete = 190 + 13 = 203 of 212 (95.8%),
--   clearing the >=95% threshold. 9 rows (1 Everglades City + 8 Group 2)
--   remain genuine residual gaps.
--
-- NOT WRITTEN in this migration (deliberately out of scope, same as
-- 20260711 precedent): zone_standards (setbacks/height/density/FAR/
-- parking) for these zone codes. I's card_complete definition only
-- requires parcel_zones.zone_code IS NOT NULL -- zone_standards is G's
-- concern, not I's, per task boundary.
-- ============================================================

SET statement_timeout = 0;

-- ── Step 1: zoning_districts ── only the 1 code missing (RSF-3 for Marco Island) ──
-- Naples codes R3-12 / R3T-12 / R1-7.5 already exist (jurisdiction_id=887,
-- real Naples LDC-derived seed). Marco Island RMF-16 / RMF-6 already exist
-- (jurisdiction_id=879, real Marco Island LDC-derived seed). Only RSF-3 is
-- new -- Marco Island's RSF group was previously seeded only as the parent
-- 'RSF' code, not the specific density variant 'RSF-3' returned by the live
-- Zoning FeatureServer.
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
VALUES
    ('RSF-3', 'RESIDENTIAL SINGLE-FAMILY 3 (RSF-3) DISTRICT', 879, 'Residential',
     'Real zone code (ZONING=RSF-3) from City of Marco Island GIS General/Zoning FeatureServer layer 3 (https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3), point-in-polygon queried live by parcel centroid 2026-07-19.')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ── Step 2: parcel_zones ── link 13 real Naples/Marco Island parcels to their real zone ──
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
    -- Naples (jurisdiction_id=887) -- source: g.naplesgov.com Planning/Zoning FeatureServer/0
    ('16111240002', '16111240002', 887, 'R3-12', 'MULTIFAMILY',
     'naples_gis_live:https://g.naplesgov.com/arcgis/rest/services/Planning/Zoning/FeatureServer/0:point=-81.7979560639185,26.1464719085902:2026-07-19'),
    ('08330640006', '08330640006', 887, 'R3T-12', 'MULTIFAMILY',
     'naples_gis_live:https://g.naplesgov.com/arcgis/rest/services/Planning/Zoning/FeatureServer/0:point=-81.8037033568877,26.1377854010671:2026-07-19'),
    ('18162720003', '18162720003', 887, 'R1-7.5', 'SINGLE FAMILY',
     'naples_gis_live:https://g.naplesgov.com/arcgis/rest/services/Planning/Zoning/FeatureServer/0:point=-81.7881948015445,26.1553716597044:2026-07-19'),
    ('06370000242', '06370000242', 887, 'R1-7.5', 'SINGLE FAMILY',
     'naples_gis_live:https://g.naplesgov.com/arcgis/rest/services/Planning/Zoning/FeatureServer/0:point=-81.7983632384792,26.1569692122673:2026-07-19'),
    -- Marco Island (jurisdiction_id=879) -- source: gis.cityofmarcoisland.com General/Zoning FeatureServer/3
    ('48425920002', '48425920002', 879, 'RMF-16', 'Multi-Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.7326851777513,25.9377898433999:2026-07-19'),
    ('72481000000', '72481000000', 879, 'RMF-16', 'Multi-Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.7273097202508,25.9566779039315:2026-07-19'),
    ('74252360003', '74252360003', 879, 'RMF-16', 'Multi-Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.7393850842743,25.9454872630388:2026-07-19'),
    ('22321600002', '22321600002', 879, 'RMF-16', 'Multi-Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.7315463322413,25.9406162366492:2026-07-19'),
    ('57200720007', '57200720007', 879, 'RSF-3', 'Single Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.692490738512,25.9360897546787:2026-07-19'),
    ('29820000245', '29820000245', 879, 'RMF-16', 'Multi-Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.7231035036742,25.9096183759609:2026-07-19'),
    ('31380520004', '31380520004', 879, 'RMF-6', 'Multi-Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.6794988910713,25.9327094466231:2026-07-19'),
    ('22324800003', '22324800003', 879, 'RMF-16', 'Multi-Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.7315463322413,25.9406162366492:2026-07-19'),
    ('57200480004', '57200480004', 879, 'RSF-3', 'Single Family',
     'marco_island_gis_live:https://gis.cityofmarcoisland.com/arcgis/rest/services/General/Zoning/FeatureServer/3:point=-81.6940405428649,25.9351998614378:2026-07-19')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET
    zone_code = EXCLUDED.zone_code,
    zone_name = EXCLUDED.zone_name,
    source    = EXCLUDED.source;

-- ── Verification ─────────────────────────────────────────────────────────────

SELECT 'parcel_zones collier naples+marco real' AS check_name, count(*) AS n
FROM parcel_zones pz
JOIN jurisdictions j ON j.id = pz.jurisdiction_id
WHERE lower(COALESCE(j.county_name, j.county)) = 'collier'
  AND (pz.source LIKE 'naples_gis_live%' OR pz.source LIKE 'marco_island_gis_live%');

SELECT public.pencil_dod_evaluate_county('collier');
