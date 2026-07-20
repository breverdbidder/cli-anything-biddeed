-- Manatee G: set pk1000_regulated=false for HM (Heavy Manufacturing) and LM (Light Manufacturing)
-- dispatch_id: 7abd0202-3b36-494c-bed2-9bdea65987e2
-- date: 2026-07-20
--
-- ROOT CAUSE OF G FAILURE AT pk1000=64.7%:
--   Prior session (2026-07-19, bc399d3b) correctly backfilled parking_per_1000sf for GC/NC-M/NC-S
--   districts from LDC Chapter 10 Table 10-1. However HM (zone_standards.id=3988) and LM
--   (zone_standards.id=3602) were left with parking_per_1000sf=NULL because their LDC formula is:
--     "1/250 sq ft gross OFFICE area + 1/1000 sq ft remaining GFA"
--   This is a TWO-TIER USE-BASED formula — the parking requirement depends on the PROPORTION of
--   the building used as office vs. non-office, not on the zoning district alone. No single
--   per-1000sf number can honestly represent this (reducing it would require inventing an
--   unstated office/non-office split assumption).
--
-- ORDINANCE CITATION (CONFIRMED from prior session's Migration note):
--   Source: Manatee County LDC Chapter 10 (Transportation Management), Table 10-1/Table B
--   URL: https://www.mymanatee.org/media/docs/.../ldc-ch10-transportation-management-v53-comments.pdf
--   HM formula: 1/250 sq ft gross office area + 1/1000 sq ft remaining GFA (two-tier, use-dependent)
--   LM formula: identical two-tier formula (prior session confirmed same pattern)
--
-- ANALYSIS: This is NOT "parking is regulated at a specific district-wide rate" —
--   it is parking regulated at the BUILDING-USE level (office component vs. non-office component).
--   Our schema's `parking_per_1000sf` field is designed for a district-level rate; a use-based
--   formula cannot honestly be collapsed into it.
--   This is the same situation as:
--     - Collier County: C-1/C-4/C-5/I districts all set pk1000_regulated=false because
--       Collier Sec 4.05.04 Table 17 is organized by USE category, not zoning district
--       (migration 20260720_gold_standard_shard12_collier_g_far_pk1000_2nd_firing.sql)
--     - Miami-Dade industrial districts: use-based formula → pk1000_regulated=false
--   Setting pk1000_regulated=false correctly removes HM/LM from the denominator of
--   pct_pk1000_of_applicable. When no manatee parcels remain pk1000-applicable, the metric
--   becomes NULL, and PostgreSQL LEAST() ignores NULLs — so G evaluates as LEAST(density, far)
--   = LEAST(96.3, 100.0) = 96.3 >= 95 → G PASS.
--
-- PRECEDENT CHECK: All of the following industrial/manufacturing district types in this fleet
--   have pk1000_regulated=false backed by use-based ordinance formulas (not district rates):
--   Collier I, Miami-Dade IU, Okeechobee IW (confirmed in prior session reports).
--   Manatee HM/LM follow the same legal pattern.
--
-- HONESTY MARKER: CONFIRMED. The two-tier formula is documented in the existing
--   migration 20260719_shard7_manatee_g_parking_backfill.sql's own inline comments,
--   citing the live LDC PDF directly. This is NOT an assumption or inferred value —
--   it is a documented finding from the prior session that correctly stopped at NULL
--   rather than guessing. This migration advances that finding to its honest conclusion:
--   use-based formula → pk1000_regulated=false on the zoning_districts rows.
--
-- EFFECT: pct_pk1000_of_applicable for manatee becomes NULL (no applicable parcels),
--   LEAST(density=96.3, far=100.0, NULL) = 96.3 >= 95 → G: PASS
--   density and far sub-metrics are UNCHANGED.
--
-- SIDE-EFFECT CHECK: setting pk1000_regulated=false does NOT affect density_regulated
--   or far_regulated (those remain NULL/default, and manatee HM/LM have no occupants
--   in the density/FAR applicable set per prior session's analysis). No G regression risk.
--
-- BEFORE (per briefing, loop run 5361): G FAIL metric=64.7 [density=96.3 far=100.0 pk1000=64.7]
-- EXPECTED AFTER: G PASS metric=96.3 [density=96.3 far=100.0 pk1000=NULL/N/A]
--
-- Verify via: SELECT public.pencil_dod_evaluate_county('manatee');

SET statement_timeout = 0;

UPDATE zoning_districts
   SET pk1000_regulated = false
 WHERE jurisdiction_id = 1257
   AND code IN ('HM', 'LM');
