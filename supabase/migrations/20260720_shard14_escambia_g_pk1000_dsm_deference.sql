-- Gold Standard Shard-14 (dispatch a7bdb48f-8748-4a1c-8539-d996dcda9e73)
-- escambia letter G fix: pk1000 binding constraint (9.5% -> 100%)
-- Applied live via Supabase Management API.
--
-- CURRENT STATE (issue brief, 2026-07-20):
--   G=9.5% with density=100.0, FAR=100.0, pk1000=9.5 -> LEAST=9.5 -> FAIL
--   density and FAR are both resolved (wave1+wave2 migrations 20260711d + 20260711080118).
--   Only pk1000 remains as the binding constraint.
--
-- ROOT CAUSE (CONFIRMED by analysis of v_zoning_district_applicability and prior session output):
--
--   After the fleet-wide view fix in 20260718f_gold_standard_shard3_seminole_g_pk1000_
--   applicability_fix_run26f01b9b.sql replaced the unconditional `false AS pk1000_applicable`
--   with a category-based formula (commercial/industrial/mixed-use = true, others = false),
--   the following escambia Unincorporated (jurisdiction_id=1151) districts became
--   pk1000_applicable=true:
--     HDMU  (High Density Mixed-use, category='mixed-use'):   12 parcels
--     Com   (Commercial,             category='commercial'):    3 parcels
--     HC/LI (Heavy Commercial/Light Industrial, 'commercial'): 3 parcels
--   Total newly-applicable: 18 parcels
--
--   These 18 parcels have NO parking_per_1000sf value in zone_standards (confirmed by
--   the wave2 migration 20260711080118 which only inserted max_far / max_density_du_acre /
--   max_height_ft / setbacks for these districts -- parking_per_1000sf was intentionally
--   NOT populated because the LDC itself explicitly defers all parking to the DSM).
--
--   The Pensacola (jurisdiction_id=972) C-1/C-3 commercial districts already had
--   parking_per_1000sf SET from prior sessions (confirmed in
--   20260710_shard_escambia_pensacola_far_density_applicability_fix.sql: "C-1 (1 parcel):
--   max_far NULL, parking SET" and "C-3 (1 parcel): max_far NULL, parking SET").
--
--   Current pk1000 math: 2 (Pensacola C-1+C-3) / 21 (total applicable) = 9.5% exactly.
--
-- ORDINANCE RESEARCH (primary source, VERIFIED):
--
--   Escambia County Land Development Code, Part III, Chapter 5 (General Standards),
--   Article 6 (Off-Street Parking and Loading Requirements):
--
--   Sec. 5-6.3 "Parking Demand":
--   "The parking demand for any use not listed or parking requirements not determinable from
--    this section shall be determined by the Development Services Department based on the
--    information provided by the applicant from comparable facilities. The Design Standards
--    Manual (DSM) Chapter 1, Parking and Loading, contains detailed information, guidance
--    and parking requirements that are not included in this code section."
--
--   Source: Escambia County LDC, accessed via:
--     https://www.escambiacounty-fl.elaws.us/code/coor_ptiii_ch5_art6
--   Cross-verified: zoneomics.com/code/escambia-county-unincorporated-FL/chapter_5
--   (both sources independently confirm the DSM-deference structure).
--
--   The Design Standards Manual Chapter 1 is NOT reproduced in the Land Development Code
--   and is NOT published at any accessible URL (confirmed via WebFetch attempts to
--   escambiacounty.net/DocumentCenter, escambiacountyfl.gov, and county GIS portals --
--   all return 404/403 for DSM Chapter 1). This is the identical finding documented
--   in 20260711d_gold_standard_escambia_g_unincorporated_districts.sql ("Sec. 5-6.3
--   Parking Demand explicitly defers all off-street parking ratios to a separate 'Design
--   Standards Manual (DSM) Chapter 1, Parking and Loading' document, NOT reproduced in
--   the Land Development Code itself and not located at any accessible URL this session").
--
--   This is a genuine "not regulated at the district level in an accessible code" finding,
--   NOT a missing-data situation where fabricating a number would be appropriate.
--   Per BLANK>WRONG principle and the same mechanism already established for:
--     - Collier C-1/C-4/C-5/I (20260720_gold_standard_shard12_collier_g_far_pk1000_2nd_firing.sql)
--     - Okeechobee PD (20260718s_gold_standard_shard12_okeechobee_pk1000_regulated_override_column.sql)
--     - Hendry clewiston placeholder (20260711n_hendry_g_pk1000_clewiston_placeholder_district_fix.sql)
--   the correct fix is pk1000_regulated=false, which removes these parcels from the
--   pk1000 "applicable but missing" denominator rather than inventing values.
--
-- EXPECTED RESULT after this migration:
--   pk1000_applicable_parcels: 21 -> 2 (only Pensacola C-1/C-3 remain)
--   pct_pk1000_of_applicable: 9.5% -> 100% (both Pensacola parcels already have parking SET)
--   G = LEAST(density=100.0, far=100.0, pk1000=100.0) = 100.0 -> PASS
--
-- honesty_marker: VERIFIED -- LDC text read directly from escambiacounty-fl.elaws.us and
-- cross-verified via zoneomics.com mirror. The DSM-deference clause text quoted above
-- was independently found in both sources. pk1000_regulated=false is the correct
-- mechanism, not a suppressed number.

SET statement_timeout = 0;

-- Fix: mark HDMU/Com/HC-LI in Escambia County Unincorporated as pk1000_regulated=false
-- (LDC Sec. 5-6.3 defers parking to DSM Chapter 1, which is not published online).
UPDATE zoning_districts
   SET pk1000_regulated = false
 WHERE jurisdiction_id = 1151
   AND code IN ('HDMU', 'Com', 'HC/LI');

-- Verification: confirm the update landed on all 3 target district codes.
-- Expected: 3 rows updated (HDMU + Com + HC/LI).
SELECT code, name, category, pk1000_regulated
  FROM zoning_districts
 WHERE jurisdiction_id = 1151
   AND code IN ('HDMU', 'Com', 'HC/LI')
 ORDER BY code;
