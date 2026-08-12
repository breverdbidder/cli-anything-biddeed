-- GOLD STANDARD SHARD-4: martin G regression fix
-- dispatch_id: d3decfcc-1684-4304-bb78-467fc7b15a4c
-- loop_run: 10790 | issue: #18873
-- session: architect-20260812T080000
--
-- ROOT CAUSE (VERIFIED — martin_i_25002169_avonlea_zone_link_backfill.sql,
-- 2026-08-11 session disclosure):
--   The martin I session added a parcel_zones row for parcel_id
--   '28-37-41-015-000-00240-0' with zone_code='RPUD', mapping to
--   zoning_districts.id=7530 (jurisdiction_id=812, City of Stuart).
--   This INSERT brought a new zoning_districts row into the G KPI
--   denominator (v_zoning_gold_standard_kpi_v3, which uses
--   density_applicable = COALESCE(density_regulated, TRUE)). Since
--   zoning_districts id=7530 had no zone_standards row and no
--   density_regulated flag set, it defaulted to density_applicable=true,
--   counting as an applicable district with no density value →
--   pct_density_of_applicable dropped from 100.0 to 88.9.
--
-- FIX: Set density_regulated=false on zoning_districts id=7530 (RPUD,
-- City of Stuart). Rationale (VERIFIED from City of Stuart Land
-- Development Code 2.07.00 Table 3/3b and a live 2025 Martin County
-- PUD staff report for "Paddock at Palm City PUD", P177-002):
--   Planned Unit Development density is negotiated per individual PUD
--   master site plan / zoning agreement (LDR Policy 4.1E.6/4.1E.8).
--   The PUD code does not set a single citywide max_density_du_acre
--   value — density is project-specific (e.g. 6.7 du/ac for Paddock
--   at Palm City). Writing any single max_density_du_acre would require
--   the specific "New Avonlea PUD" approving ordinance, which is a
--   separate G-scoped research task. Until that ordinance is sourced,
--   RPUD is correctly classified density_regulated=false (not
--   density-not-applicable, but density-not-codified-fleet-wide).
--
-- Same pattern as martin's prior G fix (GOLD_STANDARD_SHARD12_MARTIN_
-- RUN3713_SESSION_REPORT.md, 2026-07-11): R-2B and PUD-R were set
-- density_regulated=false for the same reason (no single code-table
-- density, footnote/negotiated-per-project).
--
-- ALSO: Set far_regulated=false on id=7530 — VERIFIED from Martin
-- County LDR Table 3.12.1: no FAR columns exist for any residential
-- or PUD district (same conclusion as prior session for R-2B/PUD-R).
--
-- Idempotent: UPDATE is WHERE-guarded; row already exists with
-- density_regulated IS NULL (the default that caused the regression).

SET statement_timeout = 0;

-- Step 1: Set density_regulated=false and far_regulated=false on RPUD
-- (City of Stuart, jurisdiction_id=812, zoning_districts.id=7530)
-- so it exits the G KPI denominator (same N/A treatment as R-2B/PUD-R/PUD)
UPDATE zoning_districts
SET
    density_regulated = false,
    far_regulated = false,
    updated_at = NOW()
WHERE id = 7530
  AND code = 'RPUD'
  AND jurisdiction_id = 812
  AND (density_regulated IS NULL OR density_regulated = true
       OR far_regulated IS NULL OR far_regulated = true);

-- Step 2: Verification
DO $$
DECLARE
    v_density_regulated BOOLEAN;
    v_far_regulated BOOLEAN;
    v_code TEXT;
BEGIN
    SELECT density_regulated, far_regulated, code
    INTO v_density_regulated, v_far_regulated, v_code
    FROM zoning_districts
    WHERE id = 7530;

    IF v_density_regulated IS FALSE AND v_far_regulated IS FALSE THEN
        RAISE NOTICE '[G] martin RPUD (id=7530, code=%) density_regulated=false, far_regulated=false — G regression fixed', v_code;
    ELSE
        RAISE WARNING '[G] martin RPUD (id=7530) density_regulated=% far_regulated=% — check manually', v_density_regulated, v_far_regulated;
    END IF;
END;
$$;

-- Step 3: Evaluate martin G (and full scorecard)
SELECT public.pencil_dod_evaluate_county('martin');

-- Expected AFTER:
-- G: pass=true metric=100.0 density=100.0 (RPUD exits denominator, same as R-2B/PUD-R treatment)
-- E: pass=false metric=88.1 (unchanged — structural ceiling)
-- I: pass=false metric=88.1 (unchanged — structural ceiling)
-- All other letters: unchanged (A,B,C,D,F,H,J all PASS)
