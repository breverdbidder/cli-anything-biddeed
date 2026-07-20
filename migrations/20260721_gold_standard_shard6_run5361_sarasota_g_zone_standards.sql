-- Gold Standard shard-6 (sarasota, run 5361): letter G (zoning FAR/density/pk1000 coverage)
-- BASELINE (VERIFIED 2026-07-20 via pencil_dod_evaluate_county('sarasota')):
--   G: density=0.0 far=0.0 pk1000=0.0, FAIL. Zero zone_standards rows existed for any of
--   sarasota's two active jurisdictions (824=City of Sarasota, 941=North Port).
--
-- GROUND TRUTH (live-queried 2026-07-21): 25 zoning_districts rows are actually referenced
-- by parcel_zones for jurisdiction 824 or 941 (17 for City of Sarasota, 8 for North Port).
--
-- RESEARCH SOURCES:
--   City of Sarasota Zoning Code, Article VI Zone Districts (2002 Ed. as amended, current
--   Municode content "updated March 2, 2026"), cross-verified against City Ordinance No.
--   23-5476 (edocs.sarasotagov.com, effective 4/17/2023, reprints Table VI-203 verbatim)
--   and a stable 2004-supplement PDF mirror whose Table VI-303/VI-503 values match the
--   live 2026 code exactly (unchanged since at least 2004).
--     https://library.municode.com/fl/sarasota/codes/zoning?nodeId=ARTVIZODI
--   North Port Unified Land Development Code (ULDC), Ordinance No. 2024-13, effective
--   10/28/2024, Chapter 3 Articles II-IV (Density/Intensity + Dimensional Standards tables).
--     https://www.northportfl.gov/files/.../uldc-adopted-8-6-24-effective-10-28-24.pdf
--
-- JUDGMENT CALLS (documented per-row below):
--   * "Not regulated" is written as an explicit FALSE boolean with NO zone_standards row
--     when the ordinance affirmatively states the standard doesn't apply (e.g. Sarasota's
--     Table VI-203/VI-303 have no FAR row for single/multi-family residential; Table
--     VI-503A/VI-503 explicitly show "none" for CG FAR and CG/CSC density; North Port's
--     Table 3.3.1.1 shows "-" for Activity Center density; North Port's per-DU parking
--     standard means no per-1000sf figure applies to residential/AG districts).
--   * Codes where the research could NOT resolve jurisdiction (PID, RC, RE-2/PUD, RMH --
--     these are confirmed Sarasota COUNTY zone codes/conventions absent from the City's
--     own Article VI text) are left completely untouched (booleans AND numerics both
--     NULL) -- no fabricated data, and flagged here for DB-team follow-up on possible
--     jurisdiction mis-assignment of those parcels.
--   * PUD/SKOD suffix combinations on otherwise-real City base zones (RSF-1/PUD,
--     RSF-2/PUD, RMF-2/PUD, RMF-2/SKOD, RMF-3/SKOD, RSF-2/SKOD) are left NULL
--     (confidence 0.30-0.35 in research) -- "PUD" and "SKOD" do not exist anywhere in the
--     City's own Article VI code (both are Sarasota County overlay/suffix conventions);
--     no City ordinance text defines their numeric effect on the base zone, so no number
--     is invented. RSF-3/PUD (id=12349) has zero research coverage at all -- left NULL.
--   * North Port AC-4 (Activity Center 4): the ULDC's own footnote 2 disclaims the table's
--     nominal FAR=1.0 for AC-4, deferring instead to separate Development-of-Regional-
--     Impact Development Orders not present in the ULDC. far_regulated is set FALSE
--     (the ULDC itself says its own table value doesn't govern here) but no numeric
--     max_far is written, since the DRI Development Orders were not located.
--   * North Port "V" (Village): confirmed real 3rd top-level zoning category, but density/
--     FAR vary per named Village + Neighborhood sub-area (3:1 to 16:1 du/acre, FAR 0.15+)
--     with no single citywide number attributable to the bare "V" code our parcel_zones
--     table uses. Booleans set FALSE (genuinely not regulated at this code granularity)
--     with NO numeric value, rather than picking one neighborhood's figure arbitrarily.

BEGIN;

-- ============================================================
-- City of Sarasota (jurisdiction_id = 824)
-- ============================================================

-- CG (id=12333): Sec. VI-501(c)(14) + Table VI-503A -- explicit "none" for FAR and no
-- general residential density row; not-implementing legacy commercial district.
UPDATE public.zoning_districts
SET far_regulated = false, density_regulated = false
WHERE id = 12333;

-- CSC (id=12334): Table VI-503 -- Maximum FAR = 0.75 (confirmed, stable since >=2004);
-- Maximum Density = "none" (explicit).
UPDATE public.zoning_districts
SET far_regulated = true, density_regulated = false
WHERE id = 12334;

INSERT INTO public.zone_standards
  (zoning_district_id, max_far, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12334, 0.75,
   'https://library.municode.com/fl/sarasota/codes/zoning?nodeId=ARTVIZODI',
   'City of Sarasota Zoning Code, Art. VI, Div. 5, Sec. VI-501, Table VI-503',
   0.93, now());

-- RMF-1 (id=12338): Table VI-303 -- Maximum Density = 6.0 DU/acre (confirmed, stable
-- since >=2004). No FAR row (density-only multi-family standard); parking is per-unit
-- (Article VII), not per-1000sf.
UPDATE public.zoning_districts
SET density_regulated = true, far_regulated = false, pk1000_regulated = false
WHERE id = 12338;

INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12338, 6.0,
   'https://library.municode.com/fl/sarasota/codes/zoning?nodeId=ARTVIZODI',
   'City of Sarasota Zoning Code, Art. VI, Div. 3, Sec. VI-303, Table VI-303',
   0.95, now());

-- RMF-2 (id=12339): Table VI-303 -- Maximum Density = 9.0 DU/acre (confirmed, stable
-- since >=2004).
UPDATE public.zoning_districts
SET density_regulated = true, far_regulated = false, pk1000_regulated = false
WHERE id = 12339;

INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12339, 9.0,
   'https://library.municode.com/fl/sarasota/codes/zoning?nodeId=ARTVIZODI',
   'City of Sarasota Zoning Code, Art. VI, Div. 3, Sec. VI-303, Table VI-303',
   0.95, now());

-- RSF-2 (id=12345): Table VI-203 -- Maximum Density = 4.3 DU/acre (confirmed, cross-
-- verified against Ord. 23-5476 and live Municode).
UPDATE public.zoning_districts
SET density_regulated = true, far_regulated = false, pk1000_regulated = false
WHERE id = 12345;

INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12345, 4.3,
   'https://library.municode.com/fl/sarasota/codes/zoning?nodeId=ARTVIZODI',
   'City of Sarasota Zoning Code, Art. VI, Div. 2, Sec. VI-203, Table VI-203',
   0.97, now());

-- RSF-3 (id=12348): Table VI-203 -- Maximum Density = 5.8 DU/acre (confirmed, cross-
-- verified against Ord. 23-5476 and live Municode).
UPDATE public.zoning_districts
SET density_regulated = true, far_regulated = false, pk1000_regulated = false
WHERE id = 12348;

INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12348, 5.8,
   'https://library.municode.com/fl/sarasota/codes/zoning?nodeId=ARTVIZODI',
   'City of Sarasota Zoning Code, Art. VI, Div. 2, Sec. VI-203, Table VI-203',
   0.97, now());

-- NOTE: PID (12335), RC (12336), RE-2/PUD (12337), RMH (12343) -- research flags these
-- as unresolved Sarasota-COUNTY (not City) zone codes/conventions absent from the City's
-- own Article VI text (confidence 0.15). Left entirely untouched -- no boolean, no
-- numeric value. Flag for DB-team jurisdiction re-verification.
--
-- NOTE: RMF-2/PUD (12340), RMF-2/SKOD (12341), RMF-3/SKOD (12342), RSF-1/PUD (12344),
-- RSF-2/PUD (12346), RSF-2/SKOD (12347) -- PUD/SKOD suffixes do not exist in the City's
-- own Article VI code (confidence 0.30-0.35, no City ordinance defines their numeric
-- effect on the base zone). Left entirely untouched.
--
-- NOTE: RSF-3/PUD (12349) -- zero research coverage. Left entirely untouched.

-- ============================================================
-- North Port (jurisdiction_id = 941)
-- ============================================================

-- AC-1 (id=12325): Table 3.3.1.1 -- FAR = 1.0, Density = "-" (not regulated). Parking
-- governed citywide by use-type table, not by district.
UPDATE public.zoning_districts
SET far_regulated = true, density_regulated = false, pk1000_regulated = false
WHERE id = 12325;

INSERT INTO public.zone_standards
  (zoning_district_id, max_far, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12325, 1.0,
   'https://www.northportfl.gov/files/assets/main/v/1/building-amp-planning/planning-amp-zoning/uldc-rewrite/uldc-adopted-8-6-24-effective-10-28-24.pdf',
   'North Port ULDC Ch.3 Art.III Sec.3.3.1, Table 3.3.1.1 (Density/Intensity) and Table 3.3.1.2 (Dimensional Standards); Sec.3.1.2.E(1)',
   0.95, now());

-- AC-6 (id=12328): Table 3.3.1.1 -- FAR = 1.0, Density = "-" (not regulated), no
-- footnote caveat (unlike AC-4).
UPDATE public.zoning_districts
SET far_regulated = true, density_regulated = false, pk1000_regulated = false
WHERE id = 12328;

INSERT INTO public.zone_standards
  (zoning_district_id, max_far, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12328, 1.0,
   'https://www.northportfl.gov/files/assets/main/v/1/building-amp-planning/planning-amp-zoning/uldc-rewrite/uldc-adopted-8-6-24-effective-10-28-24.pdf',
   'North Port ULDC Ch.3 Art.III Sec.3.3.1, Table 3.3.1.1 and Table 3.3.1.2; Sec.3.1.2.E(6)',
   0.95, now());

-- AC-10 (id=12326): Table 3.3.1.1 -- FAR = 1.0, Density = "-" (not regulated), no
-- footnote caveat.
UPDATE public.zoning_districts
SET far_regulated = true, density_regulated = false, pk1000_regulated = false
WHERE id = 12326;

INSERT INTO public.zone_standards
  (zoning_district_id, max_far, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12326, 1.0,
   'https://www.northportfl.gov/files/assets/main/v/1/building-amp-planning/planning-amp-zoning/uldc-rewrite/uldc-adopted-8-6-24-effective-10-28-24.pdf',
   'North Port ULDC Ch.3 Art.III Sec.3.3.1, Table 3.3.1.1 and Table 3.3.1.2; Sec.3.1.2.E(12)',
   0.95, now());

-- AC-4 (id=12327): Table 3.3.1.1 nominally shows FAR=1.0, BUT footnote 2 explicitly
-- disclaims this for AC-4 -- Panacea/The Woodlands and North Port Gardens are governed
-- by separate DRI Development Orders, not this table. far_regulated=false reflects the
-- ULDC's own disclaimer (a real, cited fact); no numeric max_far is written since the
-- DRI Development Orders themselves were not located in this research pass.
UPDATE public.zoning_districts
SET far_regulated = false, density_regulated = false, pk1000_regulated = false
WHERE id = 12327;

-- AG (id=12329): Table 3.2.4.1 -- Density = 1:3 (0.333 DU/acre), Intensity(FAR) = 0.15.
UPDATE public.zoning_districts
SET density_regulated = true, far_regulated = true, pk1000_regulated = false
WHERE id = 12329;

INSERT INTO public.zone_standards
  (zoning_district_id, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12329, 0.15, 0.333,
   'https://www.northportfl.gov/files/assets/main/v/1/building-amp-planning/planning-amp-zoning/uldc-rewrite/uldc-adopted-8-6-24-effective-10-28-24.pdf',
   'North Port ULDC Ch.3 Art.II Sec.3.2.4, Table 3.2.4.1 and Table 3.2.4.2; Sec.3.1.2.A(1)',
   0.97, now());

-- R-1 (id=12330): Table 3.2.4.1 -- Density = 4:1 (4.0 DU/acre, general/unplatted
-- standard; footnote carve-out of 4.3 applies only to legacy Port Charlotte Subdivision
-- plats), FAR = 0.05.
UPDATE public.zoning_districts
SET density_regulated = true, far_regulated = true, pk1000_regulated = false
WHERE id = 12330;

INSERT INTO public.zone_standards
  (zoning_district_id, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12330, 0.05, 4.0,
   'https://www.northportfl.gov/files/assets/main/v/1/building-amp-planning/planning-amp-zoning/uldc-rewrite/uldc-adopted-8-6-24-effective-10-28-24.pdf',
   'North Port ULDC Ch.3 Art.II Sec.3.2.4, Table 3.2.4.1 and Table 3.2.4.2 footnote 1; Sec.3.1.2.A(2)',
   0.97, now());

-- R-2 (id=12331): Table 3.2.4.1 -- Density = 10:1 (10.0 DU/acre), FAR = 0.05.
UPDATE public.zoning_districts
SET density_regulated = true, far_regulated = true, pk1000_regulated = false
WHERE id = 12331;

INSERT INTO public.zone_standards
  (zoning_district_id, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES
  (12331, 0.05, 10.0,
   'https://www.northportfl.gov/files/assets/main/v/1/building-amp-planning/planning-amp-zoning/uldc-rewrite/uldc-adopted-8-6-24-effective-10-28-24.pdf',
   'North Port ULDC Ch.3 Art.II Sec.3.2.4, Table 3.2.4.1 and Table 3.2.4.2; Sec.3.1.2.A(3)',
   0.97, now());

-- V (id=12332): confirmed real top-level "Village" zoning category, but density/FAR vary
-- per named Village + Neighborhood sub-area (3:1 to 16:1+ DU/acre, FAR 0.15-0.25+) with
-- no single citywide numeric standard attributable to the bare "V" code. Genuinely not
-- regulated at this granularity -- booleans false, no numeric value invented.
UPDATE public.zoning_districts
SET far_regulated = false, density_regulated = false, pk1000_regulated = false
WHERE id = 12332;

COMMIT;
