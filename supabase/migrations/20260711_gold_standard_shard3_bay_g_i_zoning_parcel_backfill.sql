-- Gold Standard shard-3 bay county fix: letters G (zoning KPI) and I (card_complete)
-- Session: 2026-07-11, dispatch_id ef2bce50-7c8f-4df0-b9d9-b7f8b1a83ed8
--
-- Built on FOUR parallel research findings (see session report / ultraloop_audit
-- rows for full citations). Applies ONLY to county='bay'. No fabricated codes,
-- parcel_ids, or dimensional values -- every value here traces to either a live
-- Bay County GIS query (re-verified fresh in this session) or a cited ordinance
-- section from the research findings.
--
-- ============================================================================
-- PART 1: G root cause -- resolve the 8 orphan parcel_zones rows whose
-- zone_code has no matching zoning_districts row (LEFT JOIN miss), which is
-- what makes pk1000_applicable default to TRUE via COALESCE for exactly these
-- 8 parcels (every other bay zoning_districts row has pk1000_applicable
-- hardcoded false). Resolving these drops pk1000_applicable_parcels to 0,
-- pct_pk1000_of_applicable becomes NULL, and LEAST() (verified: Postgres
-- LEAST ignores NULL args unless ALL are NULL) then evaluates G as
-- MIN(density%, far%) only.
-- ============================================================================

-- 1a. Panama City "MU 1" (jurisdiction 884) -- genuinely distinct district,
--     confirmed NOT a typo/normalization of MU-2/MU-3 (Research Finding 1:
--     330 live-GIS parcels, 2 independent Planning Board staff reports).
--     District-specific max_density/max_far NOT FOUND in any primary source
--     (absent from the current official district guide and Municode) --
--     left NULL per BLANK > WRONG. category='Mixed-Use'.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
VALUES (884, 'MU 1', 'Mixed Use-1', 'Mixed-Use', true, true)
ON CONFLICT DO NOTHING;

-- zone_standards row intentionally NOT inserted for MU-1: no sourced
-- dimensional value exists (district-specific density/FAR not found; only
-- the umbrella Comp Plan FLU-category ceiling of 20 du/acre / 0.75 FAR was
-- found, which is NOT MU-1's own confirmed standard -- not used here).

-- 1b. Data-quality fix: parcel 28388-000-000 (1719 Louise Ave) was miscoded
--     "MU 1" in our parcel_zones table. Freshly re-verified via independent
--     live GIS point query (tight-buffer envelope + exact esriGeometryPoint,
--     both single-polygon reads) at this session: true zone is GIS-raw
--     "GC 2" (General Commercial-2). The existing zoning_districts row for
--     this district (id=7273) stores its canonical code as "GC-2" (hyphen,
--     not space) -- corrected to match the DB's canonical code so the join
--     succeeds (self-caught bug: an intermediate step of this same session
--     first wrote "GC 2" verbatim from the GIS string, which left the row
--     an orphan against "GC-2" and kept pk1000_applicable_parcels=1; fixed
--     before final verification).
UPDATE parcel_zones
SET zone_code = 'GC-2'
WHERE parcel_id = '28388-000-000' AND jurisdiction_id = 884 AND zone_code IN ('MU 1', 'GC 2');

-- 1c. Panama City Beach "CH" (Commercial - High Intensity), "R" (Recreation),
--     "R-1c" (Single Family, High Density) -- all 3 confirmed as formal PCB
--     LDC zoning districts (Research Finding 2, VERIFIED via PCB LDC Chapter 2
--     PDFs + cross-verified against Bay County's own live ArcGIS renderer
--     legend JSON, an independent machine-readable source).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
VALUES
  (907, 'CH', 'Commercial - High Intensity', 'Commercial', true, true),
  (907, 'R', 'Recreation', 'Public/Recreation', true, false),
  (907, 'R-1c', 'Single Family, High Density', 'Residential', false, true)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section)
SELECT id, 45.0, 1.0,
  'https://www.pcbfl.gov/DocumentCenter/View/339',
  'PCB LDC Table 2.04.01 (Density and Intensity Standards for Zoning Districts), column CH'
FROM zoning_districts WHERE jurisdiction_id = 907 AND code = 'CH'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section)
SELECT id, NULL, 0.30,
  'https://www.pcbfl.gov/DocumentCenter/View/339',
  'PCB LDC Table 2.04.01 (Density and Intensity Standards for Zoning Districts), column R (Recreation)'
FROM zoning_districts WHERE jurisdiction_id = 907 AND code = 'R'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section)
SELECT id, 7.2, NULL,
  'https://www.pcbfl.gov/DocumentCenter/View/339',
  'PCB LDC Table 2.04.01 (Density and Intensity Standards for Zoning Districts), column R-1c; FAR not applicable per LDC Sec.2.04.01 note B'
FROM zoning_districts WHERE jurisdiction_id = 907 AND code = 'R-1c'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- PART 2: density gap -- 3 already-matched districts with max_density_du_acre
-- NULL out of bay's 110 density-applicable parcels.
-- ============================================================================

-- 2a. Panama City "RLD 1" (Residential Low Density-1, id=11236). Research
--     Finding 1 (INFERRED, corroborated not proof-positive): RLD-1 is Bay
--     County GIS's label for Panama City's own "R-1" (Residential-1) district
--     -- same ordinance_section (2675), matching purpose-statement text, and
--     the resulting density value (10.00 du/acre per Ord. 3252, 2024-12-10)
--     is identical to our existing separate "R-1" row's already-populated
--     value. Kept as its own zoning_districts row (schema/audit-trail
--     preservation) per Finding 1 option (b), NOT merged into "R-1" -- populate
--     max_density_du_acre=10.00 citing Ord. 3252 explicitly.
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section)
VALUES (
  11236, 10.00, NULL,
  'https://www.panamacity.gov/AgendaCenter/ViewFile/Item/13890?fileID=29375',
  'Ordinance No. 3252 (adopted 2024-12-10), Sec. 104-26(A)(2) -- R-1/RLD-1 density amended to 10 du/acre gross; RLD-1=R-1 equivalence is INFERRED, not an explicit primary-source statement'
)
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  source_url = EXCLUDED.source_url,
  ordinance_section = EXCLUDED.ordinance_section;

-- 2b. Callaway "R-6" and "R-6M" (ids 6008, 6010): Research Finding 3 VERIFIED
--     max_density_du_acre is genuinely ABSENT from the Callaway ordinance
--     (confirmed via verbatim bulk-regulations text, cross-checked against
--     5 sibling single-family districts using the identical template with no
--     density field, vs. the multi-family R-MFMD district which DOES state
--     density explicitly -- proving the absence is a real drafting choice,
--     not an extraction gap). Left NULL, NOT fabricated. max_far=40.00 is
--     independently VERIFIED correct (Callaway LDC Sec.15.531(d)(3) /
--     15.532(d)(3): "Floor Area Ratio - 40%") -- left untouched, no UPDATE.
--     No SQL statement needed for R-6/R-6M; documenting as residual only.

-- ============================================================================
-- PART 3: I card_complete -- group (d), 3 NEW auction rows with usable
-- lat/lon but NULL parcel_id. Resolved via live point-in-polygon GIS lookup
-- (both TEST_Parcels for parcel_id/address cross-check via VASJUST match to
-- assessed_value, and Land_Use_Planning/MapServer/1 for zone_code) --
-- VERIFIED fresh in this session (independent of the 4 research findings).
-- ============================================================================

-- 3a. case 26000195CA, 4321 BRANNON RD, Panama City FL 32404.
--     VERIFIED: parcel 11404-010-000 (VASJUST=122082 exact match to
--     assessed_value=122082). True jurisdiction per GIS SUB_ZONING=1 is
--     Unincorporated Bay County (id=1332), NOT Panama City despite mailing
--     city -- zone R-2, existing district id=11358, already has zone_standards
--     (density 15.00 du/acre) populated from a prior session.
UPDATE multi_county_auctions
SET parcel_id = '11404-010-000'
WHERE county = 'bay' AND case_number = '26000195CA' AND parcel_id IS NULL;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '11404-010-000', 1332, 'R-2', 'gis.baycountyfl.gov Land_Use_Planning MapServer/1 (live fetch 2026-07-11, point lookup at parcel centroid, tight-buffer verified)'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '11404-010-000');

-- 3b. case 25000943CA, 810 N HARRIS AVE, Panama City FL 32401.
--     VERIFIED: parcel 16582-000-000 (VASJUST=137680 exact match to
--     assessed_value=137680). This is the SAME parcel_id as the MU-1 orphan
--     resolved in Part 1a above -- its parcel_zones row (zone_code "MU 1",
--     jurisdiction 884) already exists; only multi_county_auctions.parcel_id
--     needed backfilling. No new parcel_zones INSERT needed.
UPDATE multi_county_auctions
SET parcel_id = '16582-000-000'
WHERE county = 'bay' AND case_number = '25000943CA' AND parcel_id IS NULL;

-- 3c. case 25000934CA, 2817 LONGLEAF ROAD, Panama City FL 32405.
--     VERIFIED: parcel 26904-117-000 (VASJUST=603373 exact match to
--     assessed_value=603373). True jurisdiction per GIS SUB_ZONING=1 at the
--     parcel's own polygon centroid (not the auction row's approximate
--     lat/lon) is Unincorporated Bay County (id=1332) -- zone R-1, existing
--     district id=11357, already has zone_standards (density 8.00 du/acre)
--     populated from a prior session.
UPDATE multi_county_auctions
SET parcel_id = '26904-117-000'
WHERE county = 'bay' AND case_number = '25000934CA' AND parcel_id IS NULL;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '26904-117-000', 1332, 'R-1', 'gis.baycountyfl.gov Land_Use_Planning MapServer/1 (live fetch 2026-07-11, point lookup at true parcel-polygon centroid, single-feature match)'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '26904-117-000');

-- ============================================================================
-- RESIDUALS -- documented, NOT fixed, no fabrication:
--
-- I group (c) -- See-FLU recheck (09647-000-000 / 10024-000-000, Lynn Haven):
--   Freshly re-verified LIVE in this session (2026-07-11) via the zoning
--   polygon layer (not just the parcel attribute field) at each parcel's true
--   polygon centroid. BOTH still return ZONING='See FLU', SUB_ZONING=3,
--   Label='See FLU(LH)' -- unchanged from the prior 2026-07-10 session finding.
--   No usable zone code exists in Bay County's published GIS for these two
--   parcels. Left unlinked. No parcel_zones row inserted.
--
-- I group (a) -- 3 AJAX-decoder placeholder parcel_ids (case 25000412CA
--   "TIMESHARE", 23001239CA "Property Appraiser", 25000637CA "MULTIPLE
--   PARCELS"): attempted one docket lookup (25000412CA source_url,
--   bay.realforeclose.com auction detail page) -- returned HTTP 403 to
--   automated fetch, consistent with the documented AJAX-decoder blocker.
--   Not fabricated. Left as residual per prior session's documented finding.
--
-- I group (b) -- case 25000874CA: parcel_id/address/geo/value all NULL in
--   source data, confirmed unchanged this session. Nothing to backfill.
--
-- Net result: I moves from 109/118 (92.4%) to 112/118 (94.9%) -- STILL BELOW
-- the >=95% threshold (113/118 needed). The brief's own math flagged this:
-- group (d) alone is insufficient, and group (c) (the only other reachable
-- path) was freshly re-verified to have no usable code. This is an honest
-- residual, not a failure to attempt -- see session report.
-- ============================================================================
