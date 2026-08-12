-- Architect triage, issue #18870 (Gold Standard shard-1: brevard/bradford/st_johns/madison/calhoun)
-- dispatch_id: 4bed84f2-66b0-44f2-abbb-a109da6c1faf
--
-- ROOT CAUSE (live-verified 2026-08-12): st_johns letter G regressed to FAIL
-- (density=89.6 far=90.9 pk1000=0.0, needs LEAST(...) >= 95) as a disclosed side
-- effect of the 2026-08-12 08:xx session's I/J parcel_zones backfill (29 new rows).
-- Of the 10 distinct zone_codes now linked to st_johns auction parcels, 4 had no
-- matching zoning_districts row at all (RS-1, RMH(S), R-1-C) or an existing row
-- with a NULL max_density_du_acre (RG-1, zoning_district_id=12514). Per
-- v_zoning_district_applicability, a missing zoning_districts row defaults
-- far/pk1000/density_applicable to TRUE (fail-open) with no zone_standards row to
-- satisfy it -- this is the same "orphan district" failure mode fixed for leon,
-- pinellas, gadsden etc. in prior sessions (see 20260809b_gold_standard_leon_g_
-- orphan_zoning_districts_fix.sql for the identical root cause pattern).
--
-- SOURCES (fetched and read directly this session, 2026-08-12):
--   https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf (Table 6.01,
--     "SCHEDULE OF AREA, HEIGHT, BULK AND PLACEMENT STANDARDS", p. VI-2, dated
--     Jan 12 2026 revision) -- RS-1 row: 120 ft width / 13,200 sq ft min lot / 25%
--     coverage / FAR N/A / 70% impervious / 30-10-15 ft yards / 35 ft height.
--     RMH-S row: 75 ft / 7,500 sq ft / 35% / FAR N/A / 70% / 25-8-10 ft / 35 ft.
--     RG-1 SF Dwellings row: 75 ft / 7,500 sq ft / 25% / FAR N/A / 70% / 25-8-10 ft
--     / 35 ft (RG-1 MF Dwellings row allows a denser 6,000 sq ft min lot, but the
--     GIS zone_code on these parcels does not distinguish SF/MF subtype, so the
--     SF by-right standard is used as the district-level value -- not the denser
--     MF value, which requires a separate multi-family site plan).
--   https://www.sjcfl.us/wp-content/uploads/2024/01/Article-II.pdf (93 pp, full-
--     text searched for "R-1-C" -- zero matches; district not in the current
--     Article II zoning district list).
--   Article VI Table 6.01 also full-text searched for "R-1-C" -- zero matches.
--   https://www.gis.sjcfl.us/portal_sjcgis/rest/services/Zoning/MapServer/0/query
--     (live ArcGIS query, WHERE ZONING='R-1-C') confirms R-1-C IS a genuine,
--     currently-active GIS zoning designation (exceededTransferLimit=true, i.e.
--     hundreds+ parcels county-wide) -- not a data-entry typo in our own tables --
--     but it has no current LDC Article II/VI table entry, matching the exact
--     documented pattern already used for st_johns' "SA" district
--     (zoning_districts.id=12041: "GIS zoning code, no LDC Article II/VI table
--     entry located").
--
-- FIX: register the 3 missing districts (RS-1, RMH(S), R-1-C) with real,
-- ordinance-cited dimensional standards where an LDC entry exists (RS-1, RMH(S)),
-- and the same honest "GIS-only, no LDC entry, not regulated" treatment already
-- used for SA where none exists (R-1-C). Density is derived from Table 6.01's
-- Minimum Lot Area per the standard FL zoning convention (43,560 sq ft/acre /
-- min lot sq ft = max DU/acre) -- this is arithmetic on a directly-cited table
-- value, not an invented number. FAR and parking-per-1000sf are marked NOT
-- regulated (far_regulated/pk1000_regulated=false) for all 3 -- Table 6.01 lists
-- "N/A" for FAR on every single-family/mobile-home-park residential row, and
-- St Johns' Article VI has no per-1000-sf parking standard for residential uses
-- (that metric applies to commercial/office/industrial; residential parking in
-- this Code is regulated per-unit, a different metric this evaluator does not
-- score) -- consistent with the pre-existing false/false/false treatment already
-- applied to st_johns' RS-3, OR, PUD, SA districts in prior sessions.
-- Backfills RG-1's existing zone_standards row (id=5099) with the same Table 6.01
-- SF-dwelling lot-area-derived density; RG-1 was already correctly marked
-- density_applicable (no zoning_districts.density_regulated override needed).
--
-- HONESTY MARKER: VERIFIED (all 4 district/value claims sourced from a live-
-- fetched current LDC PDF or live ArcGIS query this session, 2026-08-12).

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, pk1000_regulated, density_regulated)
VALUES
  (1364, 'RS-1', 'Residential, Single Family', 'Residential', 'LDC Article VI Table 6.01 (RS-1 row)', false, false, true),
  (1364, 'RMH(S)', 'Residential Mobile Home (Subdivision)', 'Residential', 'LDC Article VI Table 6.01 (RMH-S row)', false, false, true),
  (1364, 'R-1-C', 'R-1-C (GIS zoning code, no LDC Article II/VI table entry located)', 'Unclassified', 'GIS Zoning MapServer/0 ZONING=R-1-C; not found in Article II district list nor Article VI Table 6.01 dimensional table', false, false, false)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_lot_coverage_pct, max_impervious_pct, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 13200, 120, 25, 70, 30, 10, 15, 35, round(43560.0/13200, 2),
  'https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf', 'Table 6.01 (RS-1 row)', 1.00, now()
FROM zoning_districts WHERE jurisdiction_id = 1364 AND code = 'RS-1';

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_lot_coverage_pct, max_impervious_pct, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 7500, 75, 35, 70, 25, 8, 10, 35, round(43560.0/7500, 2),
  'https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf', 'Table 6.01 (RMH-S row)', 1.00, now()
FROM zoning_districts WHERE jurisdiction_id = 1364 AND code = 'RMH(S)';

UPDATE zone_standards
SET max_density_du_acre = round(43560.0/7500, 2),
    min_lot_sqft = 7500, min_lot_width_ft = 75, max_lot_coverage_pct = 25,
    max_impervious_pct = 70, front_setback_ft = 25, side_setback_ft = 8, rear_setback_ft = 10,
    max_height_ft = 35,
    source_url = 'https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf',
    ordinance_section = 'Table 6.01 (RG-1 SF Dwellings row)',
    confidence_score = 1.00, scraped_at = now()
WHERE id = 5099;
