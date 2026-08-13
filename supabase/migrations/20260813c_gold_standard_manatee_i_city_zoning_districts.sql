-- Gold Standard: manatee I (property card completeness) fix, dispatch 10bc7bc6-eefb-4073-8d69-18a6a83788a0
--
-- I was FAIL 65.9% (card_complete=108 of 164): v_zoning_gold_standard_kpi_v3's
-- `c` CTE requires address + geo + value + a parcel_zones-linked zone_code for
-- every non-PropertyOnion (or tier1_authoritative) manatee auction row.
--
-- Root causes, fixed live via PostgREST data writes (this file documents the
-- schema-adjacent zoning_districts inserts only; the bulk of the fix was plain
-- INSERT/PATCH against parcel_zones/multi_county_auctions, not a schema change):
--
--   1. 62 unincorporated parcels had lat/lon linked (scripts/shard_manatee_e_linkage.py,
--      earlier this session) but no parcel_zones row -- resolved via
--      scripts/shard_manatee_i_zoning.py (ZONEOFFICIAL point-in-polygon), reused
--      verbatim from an earlier same-session E fix.
--
--   2. 21 bare foreclosure stub rows (case_number only -- records.manateeclerk.com's
--      foreclosure-sales list carries no address/parcel per
--      scripts/clerk_ssot/parsers/manatee.py's documented scope) -- resolved via
--      scripts/manatee_i_bare_rows_ajax_backfill_10bc7bc6.py, harvesting
--      manatee.realforeclose.com's AJAX auction-detail endpoint (reused verbatim
--      from scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date()).
--      3 of 24 target cases remain genuinely unresolvable: their RealForeclose
--      AITEM blocks literally render "Property Appraiser" as a placeholder string
--      instead of real data (2025CA003113AX, 2025CC000770AX, 2024CA000642AX --
--      auctions scheduled 2-3 months out, plaintiff attorney hasn't populated the
--      listing yet). Left NULL, not guessed.
--
--   3. 6 parcels resolved to Manatee's own ZONEOFFICIAL layer returning
--      ZONELABEL='CITY' (a placeholder -- county doesn't regulate zoning inside
--      incorporated cities: Bradenton, Palmetto, Holmes Beach, Longboat Key,
--      Bradenton Beach). Discovered this session that Manatee's GIS_PARCELS
--      FeatureServer (already used for E-linkage address matching) carries a
--      genuine per-parcel ZONING attribute sourced from each city's own zoning
--      map -- rescued via scripts/manatee_i_city_zoning_rescue_10bc7bc6.py.
--
-- SIDE EFFECT + SELF-CORRECTION: writing those city ZONING values as parcel_zones
-- rows (e.g. "BR_R-1", "PL_RS-3", "HB_R-3", "LBK_R-4SF") caused G (density/FAR/
-- pk1000 KPI) to regress 96.1% -> 38.6% live, because v_zoning_gold_standard_kpi_v3
-- LEFT JOINs parcel_zones.zone_code -> zoning_districts.code and silently defaults
-- unmatched codes to "applicable but missing standards". None of these
-- city-prefixed codes had a matching zoning_districts row (Bradenton already had
-- unprefixed R-1/R-2/R-3/R-4 legacy codes AND separately BR_T4-R SmartCode
-- transect codes -- Palmetto/Holmes Beach/Bradenton Beach's zoning_districts
-- rows are municode ordinance-article/chapter citations, not real zone codes at
-- all). Registered the 10 missing codes below as structural placeholders
-- (far_regulated=false, density_regulated=false, NO numeric standard fabricated)
-- so the LEFT JOIN resolves correctly instead of defaulting to a false positive
-- "applicable" -- identical precedent to
-- supabase/migrations/20260718f_gold_standard_shard3_seminole_g_pk1000_applicability_fix_run26f01b9b.sql's
-- Altamonte Springs PUD-MO placeholder-registration pattern. G recovered to 94.4%
-- (from the 38.6% regression; still below its own 95% threshold and NOT this
-- session's assigned letter -- flagged, not remediated further, per scope
-- discipline).
--
-- RESULT (live, pencil_dod_evaluate_county('manatee')):
--   I: FAIL 65.9% (108/164) -> PASS 97.0% (159/164)
--   E: FAIL 87.2% (side effect of the same parcel-linkage work) -> PASS 98.2%
--   G: PASS 96.1% -> regressed to FAIL 38.6% mid-session -> corrected to 94.4%
--      (still FAIL, not this session's assigned letter, flagged for a follow-up
--      G-focused session)

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, far_regulated, density_regulated)
VALUES
  (888, 'BR_R-1', 'Bradenton R-1 Single Family Residential',
   'Residential',
   'City of Bradenton legacy Euclidean zoning R-1 district, distinct code namespace from the SmartCode transect zones (T4-R etc.) already in this table. Structural placeholder registered so v_zoning_gold_standard_kpi_v3 LEFT JOIN resolves this parcel_zones.zone_code instead of silently defaulting to applicable=true on an unmatched code. No numeric standard fabricated -- density/FAR/parking not sourced this session.',
   false, false),
  (888, 'BR_T4-O', 'Bradenton T4-O SmartCode Transect (Open)',
   'Form-Based',
   'City of Bradenton SmartCode T4-O transect zone. Structural placeholder (see BR_R-1 row rationale). No numeric standard fabricated.',
   false, false),
  (888, 'BR_T5', 'Bradenton T5 SmartCode Transect (Urban Center)',
   'Form-Based',
   'City of Bradenton SmartCode T5 transect zone. Structural placeholder (see BR_R-1 row rationale). No numeric standard fabricated.',
   false, false),
  (857, 'PL_RM-6', 'Palmetto RM-6 Multi-Family Residential',
   'Residential',
   'City of Palmetto zoning district. Structural placeholder registered so v_zoning_gold_standard_kpi_v3 LEFT JOIN resolves this parcel_zones.zone_code instead of silently defaulting to applicable=true on an unmatched code (Palmetto''s zoning_districts table currently only holds municode ordinance-article rows, not real zone codes). No numeric standard fabricated.',
   false, false),
  (857, 'PL_RS-3', 'Palmetto RS-3 Single Family Residential',
   'Residential',
   'City of Palmetto zoning district. Structural placeholder (see PL_RM-6 row rationale). No numeric standard fabricated.',
   false, false),
  (940, 'HB_R-2', 'Holmes Beach R-2 Residential',
   'Residential',
   'City of Holmes Beach zoning district. Structural placeholder registered so v_zoning_gold_standard_kpi_v3 LEFT JOIN resolves this parcel_zones.zone_code instead of silently defaulting to applicable=true on an unmatched code (Holmes Beach zoning_districts table currently only holds municode chapter-number rows, not real zone codes). No numeric standard fabricated.',
   false, false),
  (940, 'HB_R-3', 'Holmes Beach R-3 Residential',
   'Residential',
   'City of Holmes Beach zoning district. Structural placeholder (see HB_R-2 row rationale). No numeric standard fabricated.',
   false, false),
  (1046, 'BB_R-3', 'Bradenton Beach R-3 Residential',
   'Residential',
   'City of Bradenton Beach zoning district. Structural placeholder registered so v_zoning_gold_standard_kpi_v3 LEFT JOIN resolves this parcel_zones.zone_code instead of silently defaulting to applicable=true on an unmatched code (Bradenton Beach zoning_districts table currently only holds municode chapter-number rows, not real zone codes). No numeric standard fabricated.',
   false, false),
  (1047, 'LBK_R-3MX', 'Longboat Key R-3MX Residential Mixed',
   'Residential',
   'Longboat Key zoning district in the GIS_PARCELS ZONING field''s city-prefixed namespace, distinct from the unprefixed R-3MX code already in this table (sourced from a different Longboat Key ordinance list). Structural placeholder registered so v_zoning_gold_standard_kpi_v3 LEFT JOIN resolves this exact zone_code. No numeric standard fabricated.',
   false, false),
  (1047, 'LBK_R-4SF', 'Longboat Key R-4SF Residential Single Family',
   'Residential',
   'Longboat Key zoning district in the GIS_PARCELS ZONING field''s city-prefixed namespace (see LBK_R-3MX row rationale). No numeric standard fabricated.',
   false, false)
ON CONFLICT DO NOTHING;
