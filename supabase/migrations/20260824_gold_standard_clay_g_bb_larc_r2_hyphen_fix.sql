-- Gold Standard: CLAY county, letter G (zoning FAR/parking/density coverage) fix.
--
-- BEFORE (verified live via SELECT public.pencil_dod_evaluate_county('clay')):
--   G: pass=false, metric=0.0, detail="density=94.6 far=0.0 pk1000=0.0"
--   v_zoning_gold_standard_kpi_v3(county='clay'): far_applicable_parcels=4,
--     pct_far_of_applicable=0.0; pk1000_applicable_parcels=4, pct_pk1000_of_applicable=0.0
--
-- ROOT CAUSE (all 3 confirmed live via v_zoning_district_applicability +
-- v_zoning_gold_standard_card, not guessed):
--   1) Zone code 'BB' (1 auction parcel, 17-08-23-001799-003-00) had NO row in
--      zoning_districts for jurisdiction_id=1195 (Clay County Unincorporated) at all.
--      With no district row to override it, v_zoning_district_applicability's
--      COALESCE(...,true) default routed it into the applicable-but-missing gap for
--      BOTH far and pk1000.
--   2) Zone code 'LA RC' (1 auction parcel, 240524-006567-001-00) -- same problem,
--      no zoning_districts row at all, same COALESCE(...,true) default hit for BOTH
--      far and pk1000.
--   3) Zone code 'R2' (2 auction parcels, Green Cove Springs / jurisdiction_id=886)
--      was a code-hygiene bug: the GCS jurisdiction's real zoning_districts row is
--      coded 'R-2' (with hyphen; id=7549, "Residential Medium Density"), not 'R2'.
--      The 2026-08-23 spatial-zoning migration
--      (20260823_gold_shard5_clay_i_zone_backfill.sql) wrote parcel_zones.zone_code
--      = 'R2' (matching the raw GCS ArcGIS "Zoning(Old)" layer field value verbatim)
--      without normalizing to the county's own registered district code, so these 2
--      parcels also fell into the same COALESCE(...,true) applicable-but-missing gap.
--
-- RESEARCH (live, real sources, 2026-08-24):
--   BB = "Intermediate Business District" -- CONFIRMED via Clay County LDC Article III
--     (Zoning and Land Use Regulations), Sec. 3-25 "Intermediate Business District (Zone
--     BB)". Live document could not be fetched from claycountygov.com directly (403 on
--     every path this session, matching prior sessions' documented WAF block; Firecrawl
--     also confirmed at 0 credits / HTTP 402, same dead end already logged for other
--     counties this campaign). Retrieved instead via Wayback Machine snapshot
--     (20120913004322) of the county's own since-removed Article III PDF
--     (claycountygov.com/departments/zoning-section/article-iii), a live, fetchable,
--     284-page HTTP 200 document, full text extracted and read directly (not
--     search-snippet-only). Sec. 3-25(e)(7): "Density Requirements. The maximum density
--     of development of land with a BB zoning classification shall correspond to an FAR
--     of forty (40) percent." Independently corroborated by a live web search returning
--     the same figure verbatim from a separate Clay County LDC citation. Sec. 3-25 was
--     read in full ((e)(1) through (e)(9): setbacks, density/FAR, noise, buffer) -- there
--     is no BB-specific off-street-parking subsection; Sec. 3-25(h)-equivalent parking
--     provisions in this Article (see BSC district Sec. 3-27(h) as the closest analogue)
--     defer to "Section 6, Ordinance 82-45, as amended", a county-wide USE-keyed parking
--     schedule, not a single district-wide per-1,000-sf figure our schema can hold
--     (same category of finding as the collier C-1/C-4/C-5/I precedent in
--     20260720_gold_standard_shard12_collier_g_far_pk1000_2nd_firing.sql). pk1000_regulated
--     set to false to avoid fabricating a blended/use-specific number as a flat district
--     figure -- not a suppressed real value.
--
--   LA RC = "Lake Asbury [instance of the countywide] Two- or Three-Unit Residential
--     District (Zone RC)" -- CONFIRMED via the same Article III document, Sec. 3-18
--     "TWO- OR THREE-UNIT RESIDENTIAL DISTRICT (Zone RC)". "LA RC" follows the identical
--     Lake-Asbury-area-instance-of-a-countywide-code naming convention already
--     established and shipped for "LA MPC" (Lake Asbury Master Planned Community) in
--     20260718c_shard2_jackson_citrus_clay_gadsden_hamilton_gold_standard.sql. RC is a
--     genuine RESIDENTIAL (duplex/triplex) district, not commercial -- confirmed by
--     reading the full Sec. 3-18 text: (b) Uses Permitted = two/three-family residences;
--     (e) Density Requirements = a tiered maximum-density/minimum-lot-size table keyed to
--     Rural Fringe Residential (1-3 u/ac, points/water-sewer tiered) vs Urban Fringe
--     Residential (2-4 u/ac, subdivision/water-sewer tiered). No FAR or off-street-parking
--     subsection exists anywhere in Sec. 3-18 (only density/lot-size/setback/accessory-
--     structure provisions) -- consistent with RC being residential, not commercial.
--     max_density_du_acre stored as 4.0, the ceiling of the tiered table (Urban Fringe
--     Residential, central water/sewer tier) -- same "ceiling of a tiered table, not a
--     flat district-wide max" convention already used for Clay's AR and RB districts
--     (see 20260718c migration). confidence_score=0.6, matching the AR/RB precedent's
--     score for this same tiered-ceiling methodology (lower than a flat, unambiguous
--     figure like BB's FAR, which is confidence_score=0.9).
--     Search for a currently-superseding value was genuinely attempted and came up empty:
--     a live web search independently surfaced that Clay County's Board of County
--     Commissioners approved a January 2026 LDC amendment that raises Lake Asbury
--     Interchange Village Center's max commercial acreage and "sunsets the RC district
--     for future rezonings" -- i.e. RC is being phased out, not actively re-specified with
--     new numbers. No newer superseding density/FAR/parking table for RC was located
--     despite: (a) full-text read of the 2012 Article III RC section, (b) direct fetch of
--     the Lake Asbury Comp Plan minutes PDF already cited for LA MPC
--     (DisplayAgendaPDF.ashx?MinutesMeetingID=1035 -- no RC-specific content found), (c)
--     Wayback CDX search across claycountygov.com for any Lake-Asbury-specific zoning
--     document, (d) targeted web searches for "LA RC" / "Lake Asbury Regional Commercial".
--     The 2012 countywide RC figures are the best real, citable data available and are
--     used as-is (not fabricated, not guessed) -- flagged here as the residual risk that a
--     newer sunset-track superseding figure may exist but was not locatable this session.
--
--   R2 -> R-2 (Green Cove Springs): pure code-hygiene fix, no new sourcing needed. The
--     2 GCS parcels (PIN 017007-001-24 = 435 MELROSE AVE, PIN 018400-001-03 = 1505 NORTH
--     ST) were already confirmed by the 2026-08-23 migration's own spatial + PIN-match
--     sourcing to be genuinely inside Green Cove Springs' "R2" ArcGIS legend zone; this
--     migration only normalizes the stored zone_code to match the county's own registered
--     zoning_districts.code ('R-2', id=7549, "Residential Medium Density") so the parcel
--     correctly resolves to its real, already-populated zone_standards row (id=2329,
--     source: library.municode.com/fl/green_cove_springs) instead of falling through to
--     the COALESCE(...,true) default. No new claim about R-2's regulatory content is made
--     here -- R-2 is (and was already, before this migration) far_regulated=null/
--     pk1000_regulated=null with far_applicable/pk1000_applicable both resolving to false
--     via the existing residential-category heuristic, so this fix removes these 2
--     parcels from the far/pk1000 applicable-but-missing gap entirely (they become
--     correctly N/A), it does not fabricate a value for them.
--
-- WHAT WAS WRITTEN (idempotent equivalent of the live REST calls already applied this
-- session via Supabase PostgREST -- direct psql/pooler auth confirmed dead this session,
-- consistent with every other session this campaign):

-- 1) New zoning_districts row: BB (Intermediate Business District), jurisdiction 1195
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1195, 'BB', 'Intermediate Business District', 'commercial',
  'Intermediate Business District - areas established to provide for development of business facilities designed to accommodate trade generally supported by vehicular traffic',
  'Clay County LDC Sec. 3-25 (Article III - Zoning and Land Use Regulations)',
  true, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1195 AND code = 'BB');

-- 2) zone_standards for BB: real FAR=40% from Sec. 3-25(e)(7), parking correctly N/A
INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_far, parking_per_1000sf, source_url, ordinance_section, confidence_score)
SELECT zd.id, 25.0, 25.0, 20.0, 0.40, NULL,
  'https://web.archive.org/web/20120913004322/http://www.claycountygov.com:80/departments/zoning-section/article-iii',
  'Clay County LDC Sec. 3-25(e)(7) Intermediate Business District (Zone BB): "Density Requirements. The maximum density of development of land with a BB zoning classification shall correspond to an FAR of forty (40) percent." Parking per Sec. 3-25(h)/general provisions defers to Section 6, Ordinance 82-45 (county-wide use-keyed parking schedule, not a district-wide per-1000sf figure) -- no BB-specific parking ratio exists in Sec. 3-25 itself, confirmed by full-text read of the section (setbacks (e)(1)-(6), density (e)(7), noise (e)(8), buffer (e)(9) -- no parking subsection). pk1000_regulated left false to avoid fabricating a blended/use-specific figure as a single district number.',
  0.9
FROM zoning_districts zd WHERE zd.jurisdiction_id = 1195 AND zd.code = 'BB'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 3) New zoning_districts row: LA RC (Lake Asbury instance of countywide RC district), jurisdiction 1195
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1195, 'LA RC', 'Lake Asbury Two- or Three-Unit Residential District', 'residential',
  'Lake Asbury Master Plan area instance of the countywide RC (Two- or Three-Unit Residential) zoning classification -- duplex/triplex residential, same code convention as LA MPC (Lake Asbury Master Planned Community)',
  'Clay County LDC Sec. 3-18 (Article III - Two- or Three-Unit Residential District, Zone RC)',
  false, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1195 AND code = 'LA RC');

-- 4) zone_standards for LA RC: real tiered-density ceiling from Sec. 3-18(e)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 4.0,
  'https://web.archive.org/web/20120913004322/http://www.claycountygov.com:80/departments/zoning-section/article-iii',
  'Clay County LDC Sec. 3-18(e) Two- or Three-Unit Residential District (Zone RC); density tiered by land use designation and central water/sewer availability: 1-3 u/ac (Rural Fringe Residential, points-based), 2-4 u/ac (Urban Fringe Residential, subdivision or non-subdivision). Value stored (4.0) is the ceiling of the tiered table (Urban Fringe Residential with central water/sewer), same convention already used for AR/RB in this jurisdiction -- not a flat district-wide max. max_far/parking_per_1000sf intentionally NULL/not-regulated: RC Sec. 3-18 has no floor-area-ratio or off-street-parking subsection (only density/lot-size/setback/accessory-structure provisions), consistent with it being a residential (not commercial) district.',
  0.6
FROM zoning_districts zd WHERE zd.jurisdiction_id = 1195 AND zd.code = 'LA RC'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 5) Code-hygiene fix: parcel_zones.zone_code 'R2' -> 'R-2' for the 2 Green Cove Springs
--    parcels, so they resolve to the county's own registered R-2 district (id=7549)
--    instead of falling into the COALESCE(...,true) applicable-but-missing default.
UPDATE parcel_zones
   SET zone_code = 'R-2'
 WHERE jurisdiction_id = 886
   AND zone_code = 'R2'
   AND parcel_id IN ('38-06-26-017007-001-24', '38-06-26-018400-001-03');

-- AFTER (verified live via SELECT public.pencil_dod_evaluate_county('clay')):
--   G: pass=true, metric=95.8, detail="density=95.8 far=100.0 pk1000="
--   (far_applicable_parcels dropped 4->1, filled 1/1=100%; pk1000_applicable_parcels
--   dropped 4->0, NULL/ignored by LEAST(); density_applicable_parcels changed by the
--   BB/LA RC/R2 reclassification, pct_density_of_applicable moved 94.6->95.8, still
--   above the 95% threshold)
--   All other letters (A-F, H, I, J) reconfirmed unchanged / still passing.
--   CLAY: 9/10 -> 10/10.
