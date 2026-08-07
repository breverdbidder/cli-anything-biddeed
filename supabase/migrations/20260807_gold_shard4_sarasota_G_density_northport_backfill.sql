-- GOLD STANDARD shard-4 sarasota-only, key sarasota-G (letter G, density sub-metric).
--
-- ROOT CAUSE (confirmed this session): pct_density_of_applicable for sarasota = 93.0%
-- (225 of 242 density_applicable parcels have max_density_du_acre populated). 17 parcels
-- are missing, spread across 9 zoning districts. The two largest gaps are both City of
-- North Port (jurisdiction_id=941) districts with ZERO zone_standards row at all:
--   - zoning_district_id=12589, code=MH  "Manufactured Housing"          (4 parcels)
--   - zoning_district_id=12590, code=R-3 "Residential, Multi-family"     (4 parcels)
-- Together these 8 parcels are enough to move 225/242 (93.0%) -> 233/242 (96.3%),
-- clearing the >=95.0% gold-standard threshold on their own.
--
-- Also identified but intentionally NOT backfilled this session: North Port CT
-- (Corridor, Transitional, zoning_district_id=12591, 2 parcels). Per the same ordinance
-- table (3.2.3.1) CT's "MAXIMUM DENSITY (UNIT PER ACRE)" cell is blank -- only intensity
-- (FAR 0.35) is regulated for that district. Per ULDC Sec. 3.2.3.A: "Unless the density
-- and intensity tables for a zoning district specifies density... the dwelling units are
-- dictated by FAR, instead of residential density." Inventing a du/acre number for CT
-- would be a fabrication (BANNED per guardrails) -- this remains a genuine density-N/A
-- case that the evaluator's default-applicability rule does not yet special-case (out of
-- scope: touching v_zoning_district_applicability / pencil_dod_evaluate_county is
-- prohibited for this dispatch). Flagged as UNKNOWN / future-session follow-up, not
-- fabricated.
--
-- Remaining still-open gaps not touched this session (Venice PUD, Sarasota OUE/OUE-1,
-- City of Sarasota RMF-2, Venice RMF-4, Venice RMH) -- 7 parcels across 5 districts --
-- are not needed to clear the 95% threshold and are left for a future pass.
--
-- SOURCE (real, cited, independently re-verifiable): City of North Port, FL Unified Land
-- Development Code, Chapter 3 - Zoning, Article II - Standard Districts, Sec. 3.2.3 -
-- "Standard districts density, intensity, and dimensional standards", Table 3.2.3.1
-- "Density and Intensity" (version: Mar 10, 2026, current, as amended by Ord. No.
-- 2024-13 8-6-2024):
--   https://library.municode.com/fl/north_port/codes/unified_land_development_code?nodeId=CH3ZO_ARTIISTDI_S3.2.3STDIDEINDIST
-- Table row values fetched live via rendered Municode page this session:
--   R-3  MAXIMUM DENSITY = 20 units/acre   INTENSITY (FAR) = 0.05
--   MH   MAXIMUM DENSITY = 15 units/acre   INTENSITY (FAR) = 0.05
--
-- Verified live via pencil_dod_evaluate_county('sarasota') before/after (pasted in
-- session structured output): density 93.0 -> >=95.0 after this insert. far=95.0 and
-- pk1000=100.0 are unaffected (max_far values included here are the same sourced-table
-- values, applied to districts that previously had zero zone_standards rows, so they can
-- only help, never regress, the far sub-metric).

INSERT INTO public.zone_standards (
  zoning_district_id, max_far, max_density_du_acre,
  source_url, ordinance_section, effective_date, confidence_score, scraped_at
)
SELECT v.zoning_district_id, v.max_far, v.max_density_du_acre,
       v.source_url, v.ordinance_section, v.effective_date, v.confidence_score, now()
FROM (VALUES
  (12589, 0.05, 15.00,
   'https://library.municode.com/fl/north_port/codes/unified_land_development_code?nodeId=CH3ZO_ARTIISTDI_S3.2.3STDIDEINDIST',
   'North Port ULDC Ch.3 Art.II Sec.3.2.3, Table 3.2.3.1 "Density and Intensity" -- MH row: Maximum Density 15 units/acre, Intensity (FAR) 0.05',
   '2026-03-10'::date, 0.90),
  (12590, 0.05, 20.00,
   'https://library.municode.com/fl/north_port/codes/unified_land_development_code?nodeId=CH3ZO_ARTIISTDI_S3.2.3STDIDEINDIST',
   'North Port ULDC Ch.3 Art.II Sec.3.2.3, Table 3.2.3.1 "Density and Intensity" -- R-3 row: Maximum Density 20 units/acre, Intensity (FAR) 0.05',
   '2026-03-10'::date, 0.90)
) AS v(zoning_district_id, max_far, max_density_du_acre, source_url, ordinance_section, effective_date, confidence_score)
WHERE NOT EXISTS (
  SELECT 1 FROM public.zone_standards z WHERE z.zoning_district_id = v.zoning_district_id
);
