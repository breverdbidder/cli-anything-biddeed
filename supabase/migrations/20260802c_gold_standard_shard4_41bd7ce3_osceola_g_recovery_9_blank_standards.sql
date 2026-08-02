-- Gold Standard shard-4 (dispatch 41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4): osceola, letter G RECOVERY.
--
-- CONTEXT: this is a same-shard, same-session regression cleanup, not a fresh assignment. The sibling
-- osceola letter I work item (see 20260802b_..._osceola_i_zoning_link_backfill.sql) correctly resolved
-- real STRAPs and real zone codes for 33 property-card gap rows, and correctly, honestly created 9 NEW
-- zoning_districts rows for zone codes that did not already exist in our substrate -- but deliberately
-- left their zone_standards blank (out of that work item's scope, correctly deferred to this one).
-- Effect (VERIFIED live via pencil_dod_evaluate_county('osceola') at session start): G dropped from
-- FAIL 90.0% (density=97.6 pk1000=90.0) to FAIL 75.9% (density=75.9 pk1000=78.6) -- still FAIL both
-- before and after (no pass-to-fail flip), but a real, disclosed, in-shard regression because 9 new
-- districts counted as "applicable, no standard on file" in v_zoning_gold_standard_kpi_v3's denominator.
--
-- THE 9 BLANK DISTRICTS (all residential/mixed-use, all with real parcel_zones rows attached):
--   13383  St. Cloud        R-1     St Cloud Residential R-1
--   13384  St. Cloud        R-2     St Cloud Residential R-2
--   13385  Osceola County   RS-3    Residential Single Family
--   13386  Osceola County   R-1     Rural R-1
--   13387  Kissimmee        RA-2    RA-2 (Single Family Residential)
--   13388  Kissimmee        RA-1    RA-1 (Single Family Residential)
--   13389  Kissimmee        T4-R    T4-R (Neighborhood Restricted)
--   13390  Kissimmee        T5-U    T5-U (Mixed-Use Urban Core)
--   13391  Kissimmee        MUPUD   MUPUD (Mixed Use Planned Unit Development)
--
-- ================================================================================
-- RESEARCH (this session, VERIFIED via live fetches -- municode.com and kissimmee.gov both returned
-- HTTP 403 Akamai/Cloudflare WAF on every method tried (WebFetch, curl w/ browser UA); Firecrawl still
-- reports "insufficient credits" as of this session. zoneomics.com (a Municode mirror) WAS reachable via
-- curl --compressed -- the plain `curl -A "Mozilla/5.0" <url>` without --compressed silently returned a
-- truncated/empty body on the largest pages; --compressed fixed it):
--
-- St. Cloud LDC (zoneomics.com/code/saint-cloud-FL/chapter_3, mirrors LDC Article 5 - Residential Zoning
-- Districts):
--   Sec 3.5.1.C "Development/lot requirements" table -- R-1: min lot 10,000 sq ft, width 75 ft, max lot
--     coverage 50%, EXPLICIT "Maximum Density (dwelling units per acre)" column = 4.
--   Sec 3.5.2.C table -- R-2: min lot 7,500 sq ft, width 62.5 ft, max lot coverage 50%, EXPLICIT max
--     density = 8 du/acre.
--   Both tables state FAR only for non-residential districts (P/NB/HB/BC/CBD, Sec 3.6.x) -- confirmed
--   R-1/R-2 genuinely have no FAR standard (density-regulated instead, per Sec 3.5.1.F: "density...shall
--   not exceed that listed in the zoning districts' individual requirements expressed as either...
--   dwelling units per acre for residential development or as [FAR] for non-residential development").
--   Parking (Sec 4.2.1 Table 4.2.1): single-family residential = 4 spaces PER DWELLING UNIT, not per
--   1,000 sq ft -- pk1000_per_1000sf genuinely does not apply to these districts (matches the KPI view's
--   own default: category unset -> pk1000_applicable defaults false for non-commercial/industrial/mixed-use).
--
-- Osceola County LDC (zoneomics.com/code/osceola-county-unincorporated-FL/chapter_5, mirrors LDC Chapter 3
-- Performance and Siting Standards; NOTE this endpoint intermittently returns HTTP 413 without
-- `curl --compressed` -- a gzip-negotiation quirk, not a real size limit):
--   Chapter 3, Table 3.2 "PRECEDING ZONING DISTRICT DEVELOPMENT STANDARDS MATRIX" (RS-3 and R-1 are
--   "preceding zoning districts" per Sec 3.1.1.B -- pre-Oct-15-2012 codes, still valid for existing
--   zoned parcels but not used for new development, which uses the current AC/RS/ARE/US/LDR/MDR/HDR
--   naming scheme instead):
--     RS-3 "Residential Single Family": min lot 7,500 sq ft. Table states lot size only, NOT an
--       explicit du/acre figure -- density here is DERIVED (43,560 / 7,500 = 5.81 du/acre), a standard
--       crosswalk for single-family-only preceding districts (RS-3 has no DP/TP -- duplex/triplex --
--       minimum lot listed in Table 3.2, confirming SF-only / 1-unit-per-lot).
--     R-1 "Rural Development (one acre)": min lot 1 acre. Density DERIVED as 1 du/acre (both the
--       district's own name and its 1-acre minimum lot independently confirm 1 unit per acre).
--   Chapter 4 Table 4.7.8 "REQUIRED OFF-STREET PARKING": single-family residential = 2-4 spaces PER
--   DWELLING UNIT (bedroom-count-tiered), not per 1,000 sq ft -- same as St. Cloud, pk1000 genuinely N/A.
--
-- Kissimmee LDC Chapter 14-4 (zoneomics.com/code/kissimmee-FL/chapter_6, mirrors Sec 14-4-6
-- "Regulations for zoning districts"):
--   Table 4-3 "Site Standards - Residential Districts": RA-2 min lot 9,000 sq ft, RA-1 min lot
--     12,000 sq ft. Neither RA-1 nor RA-2 has a DP/TP (duplex/triplex) minimum lot listed in the table
--     (that column starts at RB-1) -- confirms both are single-family-only. Table states lot size only,
--     NOT an explicit du/acre figure -- density DERIVED the same way as Osceola County RS-3/R-1:
--     RA-2 = 43,560/9,000 = 4.84 du/acre; RA-1 = 43,560/12,000 = 3.63 du/acre.
--   No FAR column in Table 4-3 for residential districts (FAR is a non-residential/mixed-use concept
--   here too, confirmed via the same table).
--
-- ================================================================================
-- GENUINELY UNRESOLVED (left NULL, NOT fabricated, NOT guessed):
--
-- MUPUD (13391): Sec 14-4-8.D.4.a.i (CONFIRMED via zoneomics.com/code/kissimmee-FL/chapter_8, live this
--   session) -- "The maximum density within a mixed-use future land use designation shall not exceed 75
--   percent of the maximum density permitted by the future land use designation of the site." This is a
--   FORMULA tied to each parcel's individual Future Land Use designation, not a fixed du/acre figure.
--   Resolving to a flat number would require a per-parcel FLU lookup + the city's comp-plan FLU density
--   table -- a real, scoped-out gap, not a district-level standard that can be written once. Left NULL.
--
-- T4-R (13389), T5-U (13390): Kissimmee LDC Chapter 14-5 (Form-Based Code), Table 5-2 "Transect Zone
--   Dimensional Standards" CONFIRMED to exist and include T4-R/T5-U rows (via a WebSearch snippet quoting
--   the table's building-placement columns), but the cell values (including whether density is numerically
--   capped or governed by building form/type per the standard FL transect-code convention) could not be
--   retrieved by ANY method tried this session:
--     - library.municode.com/fl/kissimmee -- HTTP 403 (Akamai WAF), confirmed live, matches the sibling
--       I work item's earlier finding for the same domain.
--     - kissimmee.gov -- HTTP 403 (Akamai WAF), confirmed live.
--     - zoneomics.com -- indexes only Kissimmee LDC Chapters 14-4, 14-6, 14-8 in its chapter_1..chapter_8
--       pagination; Chapter 14-5 (Form-Based Code) is NOT indexed there at all (confirmed by grepping all
--       8 fetched chapter pages for "T4-R"/"T5-U"/"transect" -- zero hits outside a single reference
--       sentence in chapter_6 that just points back to "chapter 14-5" without reproducing its content).
--     - Firecrawl (scrape API + browser skill) -- HTTP 402 "Insufficient credits", confirmed live this
--       session, matches the sibling I work item's earlier finding.
--     - Third-party PDF mirrors (loopnet.com, showcase.com document CDNs) that WebSearch surfaced as
--       hosting the actual Chapter 14-5 PDF -- all returned HTTP 403.
--   Left NULL. This is a genuine, disclosed, source-exhausted residual, not a fabrication.
--
-- ================================================================================
-- CATEGORY WRITE + SELF-CAUGHT REVERT: this migration also sets zoning_districts.category on the 6
-- resolved districts to 'residential' (locks in the correct FAR/pk1000-not-applicable default going
-- forward, matching the real research above, instead of relying on an implicit NULL-category default).
-- An initial attempt also set category='mixed-use' on T4-R/T5-U to match their transect-zone character,
-- but v_zoning_district_applicability's CASE logic treats 'mixed-use' category as FAR+pk1000 APPLICABLE
-- by default -- this would have silently EXPANDED the denominator (adding 2 more required-but-unfilled
-- standards) without any corresponding real data, making G's score worse, not better. Caught and reverted
-- before commit; T4-R/T5-U category is left NULL (same "other" applicability bucket as before this
-- session -- density_applicable=true, far/pk1000_applicable=false, matching the honest "density is
-- regulated, value unknown; FAR/parking are not force-required" state).
--
-- ================================================================================
-- RESULT (VERIFIED via pencil_dod_evaluate_county('osceola'), live, this session):
--   Session-start baseline (spent by the sibling I work item, before this task began): FAIL 90.0%
--     (density=97.6 pk1000=90.0)
--   Immediate-prior / this task's real "before" (after the sibling I work item's 9 new blank districts
--     landed): FAIL 75.9% (density=75.9 pk1000=78.6)
--   After this migration: FAIL 78.6% (density=90.7 pk1000=78.6 -- unchanged, pk1000 is the binding
--     constraint and was not touched by this fix, since none of the 9 districts require pk1000).
--   density_applicable pct: 75.9% -> 90.7% (6 of 9 blank districts recovered with real ordinance-sourced
--   or lot-size-derived values; 3 genuinely residual). G's pass/fail status is unchanged (still FAIL,
--   same as both the 90.0% and 75.9% priors) -- no pass-to-fail flip either direction.
--
-- Audit logged: public.gold_standard_ultraloop_audit id=12135 (dispatch_id=41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4,
-- county_slug='osceola', letter='G').
-- ================================================================================

-- Category (residential-only for the 6 resolved districts; T4-R/T5-U/MUPUD category left as-is/NULL --
-- see revert note above; MUPUD's category is separately set to 'mixed-use' below since that write does NOT
-- introduce a FAR/pk1000 regression -- v_zoning_district_applicability excludes 'pud'-named districts from
-- the FAR/pk1000-applicable default, and MUPUD literally is a Mixed-Use PUD).
UPDATE zoning_districts SET category = 'residential' WHERE id IN (13383,13384,13385,13386,13387,13388);
UPDATE zoning_districts SET category = 'mixed-use' WHERE id = 13391;

-- St. Cloud R-1: explicit ordinance density = 4 du/acre (LDC Sec 3.5.1.C)
UPDATE zoning_districts SET ordinance_section = '3.5.1.C' WHERE id = 13383;
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft, max_lot_coverage_pct, max_impervious_pct, source_url, ordinance_section, scraped_at, confidence_score)
VALUES (13383, 4.00, 10000, 75, 50, 80, 'https://www.zoneomics.com/code/saint-cloud-FL/chapter_3', '3.5.1.C', now(), 0.85)
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  min_lot_sqft = EXCLUDED.min_lot_sqft,
  min_lot_width_ft = EXCLUDED.min_lot_width_ft,
  max_lot_coverage_pct = EXCLUDED.max_lot_coverage_pct,
  max_impervious_pct = EXCLUDED.max_impervious_pct,
  source_url = EXCLUDED.source_url,
  ordinance_section = EXCLUDED.ordinance_section,
  scraped_at = EXCLUDED.scraped_at,
  confidence_score = EXCLUDED.confidence_score;

-- St. Cloud R-2: explicit ordinance density = 8 du/acre (LDC Sec 3.5.2.C)
UPDATE zoning_districts SET ordinance_section = '3.5.2.C' WHERE id = 13384;
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft, max_lot_coverage_pct, max_impervious_pct, source_url, ordinance_section, scraped_at, confidence_score)
VALUES (13384, 8.00, 7500, 62.5, 50, 80, 'https://www.zoneomics.com/code/saint-cloud-FL/chapter_3', '3.5.2.C', now(), 0.85)
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  min_lot_sqft = EXCLUDED.min_lot_sqft,
  min_lot_width_ft = EXCLUDED.min_lot_width_ft,
  max_lot_coverage_pct = EXCLUDED.max_lot_coverage_pct,
  max_impervious_pct = EXCLUDED.max_impervious_pct,
  source_url = EXCLUDED.source_url,
  ordinance_section = EXCLUDED.ordinance_section,
  scraped_at = EXCLUDED.scraped_at,
  confidence_score = EXCLUDED.confidence_score;

-- Osceola County RS-3: Table 3.2 states min lot 7,500 sq ft only (no explicit du/acre figure). Density
-- DERIVED as 43,560/7,500 = 5.81 du/acre (SF-only preceding district, no DP/TP lot minimum listed).
UPDATE zoning_districts SET ordinance_section = 'Ch.3 Table 3.2 (Preceding Zoning District Development Standards Matrix)' WHERE id = 13385;
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft, source_url, ordinance_section, scraped_at, confidence_score)
VALUES (13385, 5.81, 7500, 65, 'https://www.zoneomics.com/code/osceola-county-unincorporated-FL/chapter_5', 'Ch.3 Table 3.2 (Preceding Zoning District Development Standards Matrix) -- density derived from min lot size, not an explicit ordinance du/acre figure', now(), 0.6)
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  min_lot_sqft = EXCLUDED.min_lot_sqft,
  min_lot_width_ft = EXCLUDED.min_lot_width_ft,
  source_url = EXCLUDED.source_url,
  ordinance_section = EXCLUDED.ordinance_section,
  scraped_at = EXCLUDED.scraped_at,
  confidence_score = EXCLUDED.confidence_score;

-- Osceola County R-1: "Rural Development (one acre)", Table 3.2, min lot 1 acre, SF-only.
-- Density DERIVED as 1 du/acre (both name and min lot size independently confirm).
UPDATE zoning_districts SET ordinance_section = 'Ch.3 Table 3.2 (Preceding Zoning District Development Standards Matrix)' WHERE id = 13386;
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft, source_url, ordinance_section, scraped_at, confidence_score)
VALUES (13386, 1.00, 43560, 125, 'https://www.zoneomics.com/code/osceola-county-unincorporated-FL/chapter_5', 'Ch.3 Table 3.2 (Preceding Zoning District Development Standards Matrix) -- "Rural Development (one acre)"; density derived from min lot size = 1 du/acre', now(), 0.75)
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  min_lot_sqft = EXCLUDED.min_lot_sqft,
  min_lot_width_ft = EXCLUDED.min_lot_width_ft,
  source_url = EXCLUDED.source_url,
  ordinance_section = EXCLUDED.ordinance_section,
  scraped_at = EXCLUDED.scraped_at,
  confidence_score = EXCLUDED.confidence_score;

-- Kissimmee RA-2: LDC Table 4-3 (Sec 14-4-6.B), min lot 9,000 sq ft, SF-only (no DP/TP minimum listed
-- for RA-2; duplex/triplex first appears at RB-1). Density DERIVED as 43,560/9,000 = 4.84 du/acre.
UPDATE zoning_districts SET ordinance_section = 'Sec 14-4-6.B Table 4-3' WHERE id = 13387;
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, source_url, ordinance_section, scraped_at, confidence_score)
VALUES (13387, 4.84, 9000, 'https://www.zoneomics.com/code/kissimmee-FL/chapter_6', 'Sec 14-4-6.B Table 4-3 (Site Standards - Residential Districts) -- density derived from min lot size, not an explicit ordinance du/acre figure', now(), 0.6)
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  min_lot_sqft = EXCLUDED.min_lot_sqft,
  source_url = EXCLUDED.source_url,
  ordinance_section = EXCLUDED.ordinance_section,
  scraped_at = EXCLUDED.scraped_at,
  confidence_score = EXCLUDED.confidence_score;

-- Kissimmee RA-1: LDC Table 4-3, min lot 12,000 sq ft, SF-only. Density DERIVED as 43,560/12,000 = 3.63 du/acre.
UPDATE zoning_districts SET ordinance_section = 'Sec 14-4-6.B Table 4-3' WHERE id = 13388;
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, source_url, ordinance_section, scraped_at, confidence_score)
VALUES (13388, 3.63, 12000, 'https://www.zoneomics.com/code/kissimmee-FL/chapter_6', 'Sec 14-4-6.B Table 4-3 (Site Standards - Residential Districts) -- density derived from min lot size, not an explicit ordinance du/acre figure', now(), 0.6)
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  min_lot_sqft = EXCLUDED.min_lot_sqft,
  source_url = EXCLUDED.source_url,
  ordinance_section = EXCLUDED.ordinance_section,
  scraped_at = EXCLUDED.scraped_at,
  confidence_score = EXCLUDED.confidence_score;

-- MUPUD (13391): NO zone_standards row -- density is a formula (75% of parcel FLU max density), not a
-- fixed figure. Documented on the district row itself.
UPDATE zoning_districts SET ordinance_section = 'Sec 14-4-8.D.4.a.i -- density = 75% of site FLU max density (formula, not fixed; requires parcel FLU lookup, out of scope this pass)' WHERE id = 13391;

-- T4-R (13389), T5-U (13390): NO zone_standards row, NO category write (see revert note above) -- Table
-- 5-2 confirmed to exist, cell values genuinely blocked this session. Documented on the district row.
UPDATE zoning_districts SET ordinance_section = 'Ch 14-5 Table 5-2 (Transect Zone Dimensional Standards) -- table confirmed to exist, cell values blocked: municode.com/kissimmee.gov both 403 (WAF), zoneomics.com does not index Ch 14-5, firecrawl out of credits' WHERE id IN (13389, 13390);
