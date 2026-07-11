-- Gold Standard shard-12 continuation (run3713) -- martin county E + G + I.
-- Method: ULTRALOOP research fan-out (4 parallel research agents + independent adversarial
-- refuters, all refuted=false / survived) against live first-party sources: Martin County
-- Property Appraiser JSON API (pamartinfl.gov), Martin County GIS ArcGIS REST (geoweb.martin.fl.us
-- Parcel Polygons + Zoning layers), and Martin County government staff-report PDFs read directly
-- with pypdf (martin.fl.us, martin.legistar.com). Findings logged to gold_standard_ultraloop_audit.
--
-- ============================================================================
-- PART 1 -- E: parcel_id fabrication purge + real linkage (E was FAIL 93.8%, 30/32)
-- ============================================================================
-- FABRICATION FOUND: 3 auction rows (case 23001555CCAXMX, 25001632CCAXMX, 25001634CCAXMX) carry
-- parcel_id = 'MARTIN-SYNTHETIC-<case>' -- a self-labeled placeholder string, not a real Martin
-- County folio (folios are always NN-NN-NN-NNN-NNN-NNNNN-N). Repo history confirms these 3 rows
-- are REAL auctions scraped from martin.realforeclose.com (distinct AIDs 1490119/1494243/1491114,
-- distinct judgment amounts, distinct auction dates, provenance=primary_scrape, created_at
-- 2026-03-08/2026-04-03 -- pre-dating the shard12_run1113 (2026-06-27) script that wrote the
-- placeholder). scripts/shard12_run1113_martin_fix.py itself tags these as PERSONAL PROPERTY
-- (23001555) and TIMESHARE (25001632, 25001634) foreclosures -- non-real-property liens that
-- genuinely have no assessable parcel to attach. supabase/migrations/20260704_shard8_run2886_
-- martin_cd_pa_certificate_of_title_fix.sql already flagged 23001555's value as fabricated.
-- These 3 fake parcel_ids currently inflate E's "has_parcel" numerator. Per HARD GUARDRAILS
-- (never fabricate; purge found fabrication) and the calhoun/liberty precedent, we NULL them.
-- This is an honest regression on E's raw count, not a bug -- HYPOTHESIS-tier, CONFIRMED not
-- refuted on independent adversarial re-check (see gold_standard_ultraloop_audit).
--
-- REAL LINKAGE RECOVERED (Martin County PA JSON API, https://www.pamartinfl.gov/app/search/
-- real-property?format=json&search=...):
--   * case 25000442CAAXMX ("2700 NW FEDERAL HIGHWAY, STUART, FL 34994") was previously NULL.
--     Real parcel CONFIRMED via exact-match PA API query: PIN 19-37-41-000-000-00520-7,
--     owner FRANKIE MARTIN INVESTMENTS LLC (the only PA record matching this address).
--   * case 25002267CCAXMX shares the identical address string and previously carried parcel_id
--     '04-38-41-012-000-01020-3' -- CONFIRMED FABRICATED: that PIN does not exist anywhere in
--     the live PA database (the entire 04-38-41-012 block only has sub-blocks 001-007, all on
--     SE MLK Blvd/Church St, nowhere near NW Federal Hwy). Corrected to the same real PIN
--     19-37-41-000-000-00520-7 (two distinct case numbers/types against the same property is
--     plausible for separate lien proceedings; not independently docket-confirmed -- HYPOTHESIS).
--   * case 25000195CAAXMX had NO address and NO parcel_id at all. Recovered via: (1) our own
--     stored lat/long (27.1979,-80.2516) reverse-geocoded through Martin County's own official
--     GeocodeServer (geoweb.martin.fl.us/.../mc_address_points_ll) -> "31 SE OCEAN BLVD";
--     (2) cross-checked against the PA API -> PIN 04-38-41-015-004-00160-7, owner BRUNER BROS
--     LLC, parcel centroid 16.6m from the auction's stored coordinates. Two independent
--     first-party sources converge within 17m. HYPOTHESIS (not court-docket confirmed -- both
--     martin.realforeclose.com's case-detail view and court.martinclerk.com's case search are
--     JS/CAPTCHA-gated and could not be rendered in this environment).
--
-- NET EFFECT ON E: 30/32 (93.8%, includes 3 fabricated non-null placeholders) -> 29/32 (90.6%,
-- all genuinely real). E remains FAIL, honestly, and is now structurally capped below the 95%
-- threshold: 3 of martin's 32 auctions are personal-property/timeshare liens with no parcel to
-- assign (auctions_total is not scoped by sale_type in the evaluator). This is a genuine ceiling,
-- not an oversight -- flagged for the fleet (auctions_total denominator may need a sale-type
-- carve-out for non-real-property liens, out of scope for this county-scoped session).

BEGIN;

UPDATE multi_county_auctions
SET parcel_id = NULL
WHERE lower(county) = 'martin'
  AND case_number IN ('23001555CCAXMX','25001632CCAXMX','25001634CCAXMX')
  AND parcel_id LIKE 'MARTIN-SYNTHETIC-%';

UPDATE multi_county_auctions
SET parcel_id = '19-37-41-000-000-00520-7'
WHERE lower(county) = 'martin' AND case_number = '25000442CAAXMX';

UPDATE multi_county_auctions
SET parcel_id = '19-37-41-000-000-00520-7'
WHERE lower(county) = 'martin' AND case_number = '25002267CCAXMX'
  AND parcel_id = '04-38-41-012-000-01020-3';

UPDATE multi_county_auctions
SET parcel_id = '04-38-41-015-004-00160-7',
    property_address = '31 SE OCEAN BLVD, STUART, FL'
WHERE lower(county) = 'martin' AND case_number = '25000195CAAXMX';

-- ============================================================================
-- PART 2 -- G + I: real Martin County zoning + LDR density (G was FAIL 0.0%; I was FAIL 9.4%)
-- ============================================================================
-- GIS SOURCE (CONFIRMED live, adversarially re-verified): geoweb.martin.fl.us ArcGIS Server 11.5.
--   Parcel Polygons: Administrative_Areas/base_map/MapServer/10 (key field PCN, 18-digit no-dash).
--   Zoning:          Administrative_Areas/Administrative_Areas/MapServer/8 (fields ZONING,
--                     ZONING_DETAILS; AGOL item 45cb7cd779fc4c60b1569b38b0ec0827, owner=martincounty).
--   Method: PCN -> parcel polygon -> centroid -> point-in-polygon query against the Zoning layer.
--   Sanity check: all 3 pre-existing martin parcel_zones rows (R-2B, PUD-R x2) matched exactly.
--
-- IMPORTANT DATA-INTEGRITY NOTE: Martin's ZONING field mixes real county LDR district codes
-- (R-2B, PUD-R, RS-6, R-2A, A-2, R-4, ...) with MUNICIPALITY-PASSTHROUGH values (STUART,
-- Indiantown, ...) for parcels inside incorporated cities, where the municipality -- not Martin
-- County -- holds zoning authority under its own separate code. We do NOT attach a Martin County
-- LDR zoning_districts row to municipality-passthrough parcels (5 parcels return 'STUART', 1
-- returns 'Indiantown' -- these need the City of Stuart / Village of Indiantown's own zoning
-- ordinance, not researched this session -- residual gap, flagged for next session). We also do
-- NOT link the 3 folios with NO_PARCEL_MATCH (malformed/retired) or the 2 folios whose centroid
-- falls outside the Martin County boundary layer (SITUS_CITY=JUPITER; likely Palm Beach County
-- parcels mis-attributed to martin upstream -- flagged, not silently linked).
--
-- ORDINANCE SOURCE for density (Martin County LDR, Article 3, Division 2, Section 3.12, Table
-- 3.12.1): primary source (library.municode.com / martincounty-fl.elaws.us) returned 403/503 on
-- every attempt this session. Values below are from zoneomics.com's mirror of the same table,
-- fetched independently 3x with consistent results, and CROSS-VALIDATED against the table's own
-- column SCHEMA read directly from two live 2026 Martin County government staff-report PDFs
-- (martin.fl.us project S281-001, 456 South Ocean LLC Rezoning; martin.legistar.com project
-- P177-002, Paddock at Palm City PUD) which quote verbatim excerpts of the same Table 3.12.1 and
-- confirm: (a) the table has NO floor-area-ratio column for ANY residential district (Category A
-- or B) -- CONFIRMED, not inferred; (b) PUD districts are NOT in Table 3.12.1 at all -- density
-- is set per individual PUD zoning agreement / master site plan under LDR Policy 4.1E.6/4.1E.8,
-- confirmed both by policy text ("neither is guaranteed maximum benefits by right... negotiated
-- voluntarily by the developer and the County") and by a real example (Paddock at Palm City PUD,
-- P177-002: 6.7 units/acre, a negotiated project-specific figure, not a code default).
-- Every value below is tagged HYPOTHESIS (mirror-sourced, schema-corroborated by primary-source
-- PDFs, not a personally-rendered primary-source page) except the "no FAR column exists" and
-- "PUD density is negotiated, not code-tabled" facts, which are CONFIRMED via direct pypdf reads
-- of live government PDFs. Nothing here is guessed: every numeric value traces to a specific
-- table row; every N/A determination traces to a specific documented ordinance mechanism.
--
-- R-2B and PUD-R/PUD are explicitly marked density_regulated=false (NOT a fabricated pass --
-- Martin County genuinely does not regulate these via a max_density_du_acre-style figure: R-2B
-- and the other "Category B" districts use "one single-family dwelling unit per lawfully
-- established lot" (a per-lot cap, not a density multiplier); PUD/PUD-R density is set per
-- individual development order. Both are structurally analogous to the liberty-county FAR gap
-- already accepted by this evaluator's own design ("verify v_zoning_district_applicability flags
-- so genuinely-N/A districts do not count against the denominator" -- G playbook, this brief).
-- far_regulated=false for all four districts touched here is CONFIRMED (no FAR column exists in
-- Table 3.12.1 for any residential district, verified directly from a live government PDF).
-- RS-6 (Category A, Table 3.12.1) has a real flat density value (6 units/acre) and is left
-- density-regulated (default), giving G a genuine, non-fabricated numerator.
--
-- RESIDUAL GAPS (not touched this session, no data found/researched): R-2A, A-2 (agricultural),
-- R-4, and "Golden Gate Redevelopment Zoning District" (Ord. 1147, a Martin County CRA special
-- district) all have real GIS zone_code matches but NO density data was located this session.
-- We deliberately do NOT insert parcel_zones rows for these codes: doing so without a matching,
-- correctly-configured zoning_districts row would make v_zoning_gold_standard_kpi_v3's
-- applicability CTE default far_applicable/pk1000_applicable to TRUE (COALESCE(...,true) when no
-- district row exists), introducing new unmet requirements and making G's metric WORSE, not
-- better. Left unlinked -- honest gap, flagged for a future session with time to source their
-- ordinance values (or the City of Stuart / Village of Indiantown codes for the passthrough
-- parcels).

UPDATE zoning_districts
SET category = 'residential', density_regulated = false, far_regulated = false
WHERE jurisdiction_id = 1331 AND code IN ('R-2B','PUD-R');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, ordinance_section, created_at)
VALUES
  (1331, 'PUD', 'Planned Unit Development (Martin County LDR)', 'residential', false, false,
   'LDR Division 5 / Policy 4.1E.6, 4.1E.8 -- density negotiated per individual PUD zoning agreement, not a code table value (same mechanism as PUD-R; ZONING_DETAILS on live GIS cites Res. 05.6-26 for this specific parcel''s PUD approval).', now()),
  (1331, 'RS-6', 'Single Family Residential (Martin County LDR, Table 3.12.1 Category A)', 'residential', true, false,
   'LDR Article 3, Division 2, Section 3.12, Table 3.12.1, Category A district row "RS-6".', now())
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, min_lot_sqft, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, NULL, NULL, 7500,
       'https://www.zoneomics.com/code/martin-county-unincorporated-FL/chapter_3 (mirror of LDR Table 3.12.1; schema cross-validated against live martin.fl.us staff-report PDF S281-001)',
       'Table 3.12.1 Category B "R-2B": min lot 7,500 sq ft; density governed by footnote (a) "one single-family dwelling unit per lawfully established lot" -- not a du/acre figure, see density_regulated=false on zoning_districts.',
       0.6, now()
FROM zoning_districts WHERE jurisdiction_id = 1331 AND code = 'R-2B'
ON CONFLICT (zoning_district_id) DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, NULL, NULL,
       'https://martin.legistar.com (Paddock at Palm City PUD staff report, Project P177-002, 2025-07-03)',
       'LDR Policy 4.1E.6/4.1E.8: "Specific PUD district regulations are negotiated voluntarily by the developer and the County, and neither is guaranteed maximum benefits by right." No code-table density value exists for PUD/PUD-R.',
       0.75, now()
FROM zoning_districts WHERE jurisdiction_id = 1331 AND code IN ('PUD-R','PUD')
ON CONFLICT (zoning_district_id) DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 6.0, NULL,
       'https://www.zoneomics.com/code/martin-county-unincorporated-FL/chapter_3 (mirror of LDR Table 3.12.1; schema cross-validated against live martin.fl.us staff-report PDF S281-001)',
       'Table 3.12.1 Category A district "RS-6": max residential density 6.00 units/acre.',
       0.6, now()
FROM zoning_districts WHERE jurisdiction_id = 1331 AND code = 'RS-6'
ON CONFLICT (zoning_district_id) DO NOTHING;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, created_at)
SELECT v.parcel_id, 1331, v.zone_code, v.zone_name,
       'martin_geoweb_arcgis_zoning_layer8_pip_2026-07-11', now()
FROM (VALUES
  ('52-38-41-005-000-02760-6', 'R-2B',  'Residential Estate Density'),
  ('10-38-40-001-000-02260-0', 'PUD',   'Planned Unit Development'),
  ('34-38-42-053-002-00190-3', 'PUD-R', 'Planned Unit Development - Residential'),
  ('13-38-40-006-000-10030-6', 'PUD-R', 'Planned Unit Development - Residential'),
  ('13-38-40-020-000-00130-8', 'RS-6',  'Single Family Residential'),
  ('19-38-41-002-000-00952-0', 'PUD-R', 'Planned Unit Development - Residential'),
  ('52-38-41-005-000-02320-9', 'R-2B',  'Residential Estate Density'),
  ('13-38-40-009-021-00040-8', 'PUD-R', 'Planned Unit Development - Residential'),
  ('13-38-40-018-030-00020-2', 'PUD-R', 'Planned Unit Development - Residential'),
  ('12-39-40-005-000-00670-0', 'PUD-R', 'Planned Unit Development - Residential')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = 1331
);

COMMIT;
