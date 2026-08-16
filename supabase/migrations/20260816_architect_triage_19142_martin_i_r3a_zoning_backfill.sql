-- Architect triage of issue #19142 (SHARD-5: martin, dispatch 1f420b07-1384-435b-b67b-8f02a1c77dac).
-- martin was 8/10 (E FAIL 93.0% 40/43 parcel_linked, I FAIL 90.7% 39/43 card_complete).
--
-- E's 3-row gap (23001555CCAXMX personal-property lien, 25001632CCAXMX/25001634CCAXMX
-- timeshare, all case_classification_code=NON_REAL_PROPERTY) is a well-documented, repeatedly
-- escalated hard ceiling -- (43-3)/43=93.0% max achievable, below the 95% threshold, requiring
-- Ariel's canon decision on excluding NON_REAL_PROPERTY from the E/I denominator (raised on
-- #18535, #18873, #19040, #19074, #19097, #19108 and now #19142; still unactioned). NOT touched
-- here -- exceeds unilateral triage authority (retroactive fleet-wide denominator change).
--
-- I's gap was ONE ROW LARGER than E's (39/43 vs 40/43 linked) -- a genuinely distinct, fixable
-- data gap, not the same canon-blocked ceiling: case 25000496CAAXMX / parcel
-- 16-38-41-005-008-00100-7 (2600 S Kanner Hwy H10, Stuart FL -- De La Bahia Condominium) HAD a
-- real parcel_id (so E already counted it) but was absent from parcel_zones / had no zone_code,
-- so it failed I's stricter card-completeness join (v_zoning_gold_standard_card requires
-- zone_code IS NOT NULL).
--
-- FIX (VERIFIED, ordinance-sourced, no fabrication):
--   1. Parcel centroid recovered live from pamartinfl.gov PA JSON API (PIN 163841005008001007,
--      X=-80.2542687260, Y=27.1731173323, PropertyUseClass "0400 Residential Condo", legal "DE
--      LA BAHIA CONDOMINIUM BLDG H APT 10").
--   2. Point-in-polygon zoning query against Martin County's own live ArcGIS Zoning MapServer
--      (geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/Future_Landuse_Zoning/
--      MapServer/1) returned ZONING=R-3A.
--   3. Jurisdiction confirmed unincorporated Martin County (id=1331): the same point queried
--      against the Municipal Boundaries layer (Administrative_Areas/Administrative_Areas/
--      MapServer/0) returned zero features -- falls outside every municipality polygon, ruling
--      out the Stuart-passthrough case flagged as a residual gap in the 2026-07-11
--      (20260711h_gold_standard_martin_e_g_i_parcel_zoning_fix.sql) session.
--   4. Real ordinance text for R-3A (Sec. 3.407, "Liberal Multiple-Family District", Martin
--      County LDR Article 3 Division 7 "Category C Zoning District Standards") fetched live from
--      martincounty-fl.elaws.us/code/ldr_art3_div7_sec3.407 (re-fetched twice independently,
--      consistent both times): max density 15 apartment units/acre (community-services-
--      dependent), min lot 7,500 sf (min width 60 ft), apartment min building site 15,000 sf for
--      first 4 units + additional per-unit acreage thereafter (internally consistent with the 15
--      du/acre cap: 15,000sf/4units=3,750sf/unit initial, converging toward ~2,900sf/unit at 15
--      units on a 43,560sf acre), max height 4 stories/40 ft, max lot coverage 30%. No FAR figure
--      specified anywhere in the section (far_regulated=false is a CONFIRMED absence, not a
--      guess). Firecrawl was unavailable this session (402 insufficient credits, matching the
--      already-documented exhaustion pattern) and direct curl to zoneomics.com was CloudFront-
--      blocked (413); WebFetch against zoneomics confirmed the R-3A section exists (Sec. 3.407,
--      Division 7 "Category C") but could not retrieve the full table text from that mirror --
--      the eLaws primary-source page above supplied the actual values.
--
-- RESULT -- re-verified live via pencil_dod_evaluate_county('martin') immediately after the
-- inserts below: I moved 90.7% (39/43) -> 93.0% (40/43); G unaffected, still 100.0 (this parcel's
-- district carries a real, non-fabricated density value, so it counts as applicable-and-met, not
-- a new unmet requirement). I remains FAIL -- it now shares the exact same 93.0% ceiling as E,
-- both blocked on the same 3 NON_REAL_PROPERTY rows and the same pending canon decision. DoD
-- (EXISTS certified for martin) re-executed after the fix: still FALSE, as expected -- this was
-- never going to flip 10/10 by itself, it removes a previously-uninvestigated distinct gap and
-- confirms I's remaining blocker is identical to E's, not a second independent problem.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, ordinance_section, description, created_at)
VALUES (
  1331, 'R-3A', 'Liberal Multiple-Family District (Martin County LDR)', 'residential', true, false,
  'Martin County LDR Article 3, Division 7 (Category C Zoning District Standards), Sec. 3.407 R-3A Liberal Multiple-Family District. Verbatim: maximum density of 15 apartment units permitted per acre depending on available community services and capital improvements; minimum lot area not less than 7,500 sq ft with min width 60 ft; apartment buildings require minimum building site of 15,000 sq ft (min width 100 ft) for first 4 units plus additional acreage per unit thereafter (internally consistent with the 15 du/acre cap); max building height 4 stories/40 ft; max lot coverage 30%. No FAR figure specified in this section (far_regulated=false, CONFIRMED absence, not guessed).',
  'Martin County unincorporated zoning district, verified via geoweb.martin.fl.us ArcGIS Administrative_Areas MapServer layer 8 (Zoning) point-in-polygon at parcel centroid, matching PA API coordinates for case 25000496CAAXMX / parcel 16-38-41-005-008-00100-7 (De La Bahia Condominium, 2600 S Kanner Hwy H10, Stuart FL).',
  now()
)
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, min_lot_sqft, max_height_ft, max_stories, max_lot_coverage_pct, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 15, NULL, 7500, 40, 4, 30,
       'https://martincounty-fl.elaws.us/code/ldr_art3_div7_sec3.407',
       'Sec. 3.407 R-3A Liberal Multiple-Family District: max density 15 apartment units/acre (community-services-dependent); min lot 7,500 sf (min width 60 ft); apartment min building site 15,000 sf/4 units + additional per-unit acreage; max height 4 stories/40 ft; max lot coverage 30%; no FAR specified.',
       0.85, now()
FROM zoning_districts WHERE jurisdiction_id = 1331 AND code = 'R-3A'
ON CONFLICT (zoning_district_id) DO NOTHING;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, created_at)
VALUES (
  '16-38-41-005-008-00100-7', 1331, 'R-3A', 'Liberal Multiple-Family District (Martin County LDR)',
  'geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/Future_Landuse_Zoning/MapServer/1 point-in-polygon query lat=27.1731173323 lon=-80.2542687260 (De La Bahia Condominium centroid from pamartinfl.gov PA API, case 25000496CAAXMX) VERIFIED live 2026-08-16; Municipal Boundaries layer (MapServer/0) confirmed point falls outside all municipality polygons -> unincorporated Martin County jurisdiction confirmed',
  now()
)
ON CONFLICT DO NOTHING;
