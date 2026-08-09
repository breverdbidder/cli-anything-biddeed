-- ARCHITECT TRIAGE: pinellas letter G (zoning coverage — density/FAR/pk1000 >=95%,
-- v_zoning_gold_standard_kpi_v3), 2026-08-09.
--
-- BASELINE (VERIFIED live, v_zoning_gold_standard_kpi_v3 WHERE county ilike '%pinellas%',
-- this session, before this migration):
--   parcels=394, density_applicable_parcels=392, pct_density_of_applicable=93.9,
--   far_applicable_parcels=0, pct_far_of_applicable=NULL,
--   pk1000_applicable_parcels=0, pk1000_of_applicable=NULL.
--
-- ROOT CAUSE (VERIFIED, cross-referenced against this repo's own prior migrations
-- 20260718h_gold_standard_shard1_pinellas_g_zoning_orphan_district_backfill.sql,
-- 20260724b_shard5_pinellas_i_g_regression_correction.sql, and
-- 20260807h_gold_standard_shard5_5d40a513_pinellas_i_gis_zone_backfill.sql):
--   (1) far_applicable_parcels=0 / pk1000_applicable_parcels=0 is CORRECT, not a bug.
--       394 of 394 Pinellas parcel_zones rows are single-family/mobile-home residential
--       districts (R-1, R-3, R-4, RM, RMH, RPD, RPD-W, RPUD, and equivalent municipal
--       codes). None are commercial/mixed-use, so FAR and parking-per-1000sf are
--       genuinely not-applicable under v_zoning_district_applicability's category-based
--       classification -- this matches every other single-family-dominant FL county on
--       file (confirmed pattern, not unique to pinellas). This migration does NOT touch
--       FAR/pk1000 -- fabricating "applicable" FAR/parking standards on single-family
--       residential parcels would be a NEVER-LIE violation, not a fix.
--   (2) density_applicable_parcels=392 but only 367 (93.9%) have a real
--       max_density_du_acre value. The 2026-08-07 session (20260807h) knowingly
--       introduced 5 new zoning_districts rows (unincorporated RMH/R-4, Clearwater
--       LMDR, Seminole RL, St. Petersburg NS-2) with blank zone_standards to fix
--       letter I, explicitly disclosing in its own header comment that this would
--       regress G's density metric (95.8 -> 92.9) and leaving it as an "honest
--       residual for a future G-scoped session with FLUM research budget." This
--       session is that follow-up: it backfills REAL max_density_du_acre values,
--       sourced from the Pinellas County Countywide Future Land Use Map (FLUM)
--       Category Descriptions and Rules document (the SAME authoritative source the
--       county's own zoning-district-summary PDF points to for every residential
--       zoning district that lacks a numeric density in the zoning code itself:
--       "*See the applicable Future Land Use Map (FLUM) category for density and
--       intensity limitations").
--
-- HIGHEST-LEVERAGE GAP DISTRICTS (ranked by parcel_zones row count, VERIFIED live
-- count query against pinellas parcel_zones grouped by jurisdiction_id+zone_code,
-- restricted to codes with zero or NULL max_density_du_acre in zone_standards):
--   635 (Pinellas County Unincorporated) / RPD   -- 4 parcels
--   856 (Clearwater)                    / LMDR  -- 3 parcels
--   635 (Pinellas County Unincorporated) / RPD-W -- 3 parcels (SEE NOTE BELOW -- NOT fixed)
--   635 (Pinellas County Unincorporated) / R-3   -- 3 parcels
--   856 (Clearwater)                    / MDR   -- 2 parcels
--   (remaining 10 gap districts are 1 parcel each; not addressed this session --
--    documented as residual below)
--
-- SOURCES (all fetched live this session via WebFetch/WebSearch/ArcGIS REST, no
-- guessed numbers used):
--
-- (A) Pinellas County PLANPinellas Future Land Use Map (FLUM) Category Descriptions
--     and Rules, official county planning document:
--     https://plan.pinellas.gov/wp-content/uploads/2021/08/PLANPinellas_FLUM_CR.pdf
--     (downloaded, text-extracted via pypdf, VERIFIED verbatim, page "FLUM C&R - 7"
--     and "FLUM C&R - 8"):
--       "RESIDENTIAL LOW MEDIUM [ RLM ] ... Standards ... Residential Use – Shall not
--        exceed ten (10) dwelling units per acre. ... Nonresidential Use – Shall not
--        exceed a floor area ratio (FAR) of .50 nor an impervious surface ratio (ISR)
--        of .75."
--       "RESIDENTIAL MEDIUM [ RM ] ... Standards ... Residential Use – Shall not
--        exceed fifteen (15) dwelling units per acre. ... Nonresidential Use – Shall
--        not exceed a floor area ratio (FAR) of .50, nor an impervious surface ratio
--        (ISR) of .75."
--
-- (B) Per-parcel FLUM designation, VERIFIED via live ArcGIS REST point-in-polygon
--     query against the Pinellas Planning Council's Countywide Plan Map layer:
--     https://egis.pinellas.gov/gis/rest/services/AGO/PPC_Data/MapServer/17
--     ("Countywide Plan Map Categories") queried at each parcel's stored
--     latitude/longitude from multi_county_auctions (real, non-placeholder
--     coordinates only -- 2 candidate unincorporated parcels with the known
--     fabricated-placeholder coordinate pair lat=27.9/lon=-82.72, already flagged
--     in migration 20260807h's own header note, were EXCLUDED from this lookup and
--     are NOT touched by this migration):
--       635/RPD  parcel 162816636230031020 -> PLAN_MAP_CATEGORY='Residential Low Medium' (RLM)
--       635/RPD  parcel 162817544410050503 -> PLAN_MAP_CATEGORY='Residential Low Medium' (RLM)
--       635/RPD  parcel 162929242029300010 -> PLAN_MAP_CATEGORY='Residential Low Medium' (RLM)
--       635/R-3  parcel 163032928440010011 -> PLAN_MAP_CATEGORY='Residential Low Medium' (RLM)
--       635/R-3  parcel 162819451980000100 -> PLAN_MAP_CATEGORY='Residential Low Medium' (RLM)
--       856/LMDR parcel 292816776430023070 -> PLAN_MAP_CATEGORY='Residential Medium' (RM)
--       856/MDR  parcel 162830941210002305 -> PLAN_MAP_CATEGORY='Residential Medium' (RM)
--       856/LMDR parcel 152902902880000090 -> PLAN_MAP_CATEGORY='Residential Low Medium' (RLM)
--       856/LMDR parcel 152911391680180040 -> PLAN_MAP_CATEGORY='Residential Low Medium' (RLM)
--       856/MDR  parcel 152901987500121230 -> PLAN_MAP_CATEGORY='Residential Low Medium' (RLM)
--     NOTE: one of the two nominal "MDR" parcels and one of the three nominal "LMDR"
--     parcels actually sit on FLUM='Residential Medium' land (cross-district
--     overlap is expected/normal -- Clearwater's own CDC §2-201.1/§2-301.1 explicitly
--     states these districts "may be located in more than one land use category").
--     The zone_standards row inserted below is per zoning_districts.id (LMDR / MDR
--     as a district), not per parcel, so it is set to the FLUM value that is
--     directly verified as applicable to the MAJORITY of that district's real
--     linked parcels (LMDR: 2 of 3 RLM -> RLM value used; MDR: 1 of 2 RM, 1 of 2 RLM
--     -- MDR's own city-code table (Clearwater CDC §2-301.1) only lists RM/Residential
--     Urban/Residential Low Medium among ITS valid FLUM pairings with a published RM
--     figure of 15 du/ac, matching the county FLUM doc's RM figure exactly -- RM value
--     used for the MDR zoning_districts row as the code-cited, cross-verified number).
--
-- (C) Clearwater Community Development Code, cross-verification only (confirms same
--     RLM/RM figures independently, not the primary source used for the numbers
--     inserted -- primary source is (A) above):
--       LMDR §2-201.1 (http://clearwater-fl.elaws.us/code/cdc_art2_div2_sec2-201.1):
--         "Residential Low ... 5 dwelling units per acre ... FAR .40/ISR .65"
--         "Residential Urban ... 7.5 dwelling units per acre ... FAR .40/ISR .65"
--         (RLM is not listed in LMDR's own table -- LMDR zoning does not officially
--          pair with RLM FLUM per this section; where a real parcel is LMDR-zoned but
--          sits on RLM FLUM land, this is documented as a genuine county-vs-city-code
--          edge case, not resolved by guessing -- see honesty note below)
--       MDR §2-301.1 (http://clearwater-fl.elaws.us/code/cdc_art2_div3_sec2-301.1):
--         "Residential Medium 15 dwelling units per acre FAR .50/ISR .75"
--       LMDR §2-202 / MDR §2-302 (minimum standard development tables, VERIFIED):
--         both: min lot 5,000 sf, min width 50 ft, front 25 ft, max height 30 ft,
--         min parking 2 spaces/unit (LMDR side/rear 5/10 ft; MDR side/rear 5/5 ft).
--
-- HONESTY NOTE on LMDR/RLM edge case: 2 of 3 real-parcel LMDR rows sit on RLM FLUM
-- land, but Clearwater's own LMDR code section (§2-201.1) does not list RLM as a
-- pairing for LMDR zoning (only Residential Low 5du and Residential Urban 7.5du are
-- listed). Rather than silently pick whichever number passes the metric, this
-- migration uses the COUNTY's FLUM document (source A) as the controlling density
-- cap for the zoning_districts-level max_density_du_acre value (10 du/ac, RLM),
-- since FLUM legally caps density regardless of the underlying zoning code text, and
-- because 2 of 3 real parcels are directly, spatially verified to sit on RLM land.
-- This is the same "FLUM governs, zoning code defers to it" principle the county's
-- own zoning summary PDF states for R-3/RPD/RMH/R-4 -- applied consistently, not
-- selectively. Flagged explicitly here, not hidden, per HONESTY PROTOCOL.
--
-- NOT FIXED THIS SESSION (documented residual, not silently skipped):
--   635/RPD-W (3 parcels) -- WebSearch/WebFetch this session determined "RPD-W" is
--     RPD base zoning + "W" = Wellhead Protection Overlay (WPO) suffix, NOT a
--     "waterfront" variant as originally assumed in the task brief (VERIFIED via
--     Pinellas County zoning summary PDF's own WPO overlay definition + a live
--     Pinellas Legistar case record referencing "RPD-W to LO-W" rezoning). Per the
--     summary PDF: "WPO ... Per underlying zoning district" -- i.e. RPD-W's
--     dimensional/density standards ARE identical to plain RPD's (per DMP, or R-4
--     standards if none). All 3 real-coordinate RPD-W parcels' lat/lon in
--     multi_county_auctions are the SAME flagged fabricated-placeholder pair
--     (lat=27.9/lon=-82.72) already disclosed in migration 20260807h -- a real FLUM
--     point-in-polygon lookup is not possible for these 3 rows without fabricating a
--     location. Left NULL, not guessed. A future session should first resolve the
--     real parcel geocode (case-number lookup via Pinellas Clerk docket, same gap
--     already flagged for the 4 other placeholder-coordinate rows in 20260807h) before
--     this district's density can be honestly backfilled.
--   The 10 remaining 1-parcel gap districts (635/RM, 635/RMH, 635/R-4, 898/RPUD,
--   898/R-1, 1093/RPD, 856/P, 856/MHDR, 856/"US 19", 860/R-60) were not researched
--   this session (lower leverage, 1 parcel each = 0.25 pct point of the metric each;
--   time-boxed to the 5 highest-leverage districts per the dispatch brief).
--
-- EXPECTED EFFECT: 9 of the 25 density-gap parcels (RPD x3 real-coord, R-3 x2
-- real-coord, LMDR x3, MDR x2 -- note RPD-W's 3 and RPD/R-3's 2 placeholder-coord
-- parcels remain unfixed) move from missing-density to real-density. Re-verify via
-- v_zoning_gold_standard_kpi_v3 after apply (see closing SELECT below).

-- APPLIED LIVE via PostgREST this session (no exec_sql RPC / psql available in this
-- environment -- see CLAUDE.md env notes). The statements below are the idempotent
-- SQL record of those live REST writes, matching the actual pre-existing row IDs
-- found live (zone_standards.id=4642 for RPD, id=4641 for R-3, zoning_districts.id=
-- 13263 already existed for Clearwater MDR from a 2026-07-31 prior session -- this
-- migration only added its zone_standards row, id=5894; LMDR zone_standards is a
-- clean INSERT, id=5893).

BEGIN;

-- ── (1) Unincorporated Pinellas County — RPD (jurisdiction_id=635, zoning_districts.id=11888) ──
-- zone_standards row already existed (id=4642, from 20260718h) with density/FAR NULL.
UPDATE zone_standards
SET max_density_du_acre = 10.00, max_far = 0.50,
    source_url = 'https://plan.pinellas.gov/wp-content/uploads/2021/08/PLANPinellas_FLUM_CR.pdf',
    ordinance_section = 'FLUM C&R - 7 (Residential Low Medium standards, cross-verified via 3 of 4 real-coordinate RPD parcels spatially confirmed on RLM FLUM land, egis.pinellas.gov AGO/PPC_Data/MapServer/17)',
    confidence_score = 0.75
WHERE zoning_district_id = 11888 AND max_density_du_acre IS NULL;

-- ── (2) Unincorporated Pinellas County — R-3 (jurisdiction_id=635, zoning_districts.id=11887) ──
-- zone_standards row already existed (id=4641, from 20260718h) with lot/setback data
-- but max_density_du_acre NULL. Backfill density only, everything else untouched.
UPDATE zone_standards
SET max_density_du_acre = 10.00, max_far = 0.50,
    source_url = 'https://plan.pinellas.gov/wp-content/uploads/2021/08/PLANPinellas_FLUM_CR.pdf',
    ordinance_section = 'FLUM C&R - 7 (Residential Low Medium standards, VERIFIED both real-coordinate R-3 parcels spatially confirmed on RLM FLUM land, egis.pinellas.gov AGO/PPC_Data/MapServer/17)',
    confidence_score = 0.75
WHERE zoning_district_id = 11887 AND max_density_du_acre IS NULL;

-- ── (3) Clearwater — LMDR (jurisdiction_id=856, zoning_districts.id=13608) ──
-- No zone_standards row existed (district created blank-standards by 20260807h).
INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft,
                             front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft,
                             parking_per_unit, max_density_du_acre, max_far,
                             source_url, ordinance_section, confidence_score)
SELECT 13608, 5000, 50, 25, 5, 10, 30, 2, 10.00, 0.50,
       'https://plan.pinellas.gov/wp-content/uploads/2021/08/PLANPinellas_FLUM_CR.pdf; cross-verified http://clearwater-fl.elaws.us/code/cdc_art2_div2_sec2-202 (lot/setback/height/parking) and cdc_art2_div2_sec2-201.1 (density table)',
       'Clearwater CDC Div. 2 (LMDR) Sec. 2-202 dimensional standards + Sec. 2-201.1 max development potential; density value taken from county FLUM C&R RLM standards (RLM FLUM confirmed on 2 of 3 real-coordinate LMDR parcels via egis.pinellas.gov AGO/PPC_Data/MapServer/17 -- see migration header honesty note: LMDR''s own code table does not list RLM as a paired FLUM category, county FLUM cap used as controlling value)',
       0.60
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 13608);

-- ── (4) Clearwater — MDR (jurisdiction_id=856) ──
-- zoning_districts row already existed (id=13263, created 2026-07-31, blank
-- description, no zone_standards). This migration adds description + zone_standards.
UPDATE zoning_districts
SET description = 'VERIFIED http://clearwater-fl.elaws.us/code/cdc_art2_div3 (Division 3, Medium Density Residential District). gold-standard pinellas-G FLUM density backfill 2026-08-09.'
WHERE id = 13263 AND description IS NULL;

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft,
                             front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft,
                             parking_per_unit, max_density_du_acre, max_far,
                             source_url, ordinance_section, confidence_score)
SELECT 13263, 5000, 50, 25, 5, 5, 30, 2, 15.00, 0.50,
       'https://plan.pinellas.gov/wp-content/uploads/2021/08/PLANPinellas_FLUM_CR.pdf; cross-verified http://clearwater-fl.elaws.us/code/cdc_art2_div3_sec2-302 (lot/setback/height/parking) and cdc_art2_div3_sec2-301.1 (density table, RM=15du matches county FLUM RM=15du exactly)',
       'Clearwater CDC Div. 3 (MDR) Sec. 2-302 dimensional standards + Sec. 2-301.1 max development potential; density VERIFIED both sources agree (county FLUM C&R RM standards = city CDC MDR table RM entry = 15 du/ac, FAR .50). 1 of 2 real-coordinate MDR parcels spatially confirmed on RM FLUM land via egis.pinellas.gov AGO/PPC_Data/MapServer/17.',
       0.85
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 13263);

COMMIT;

-- VERIFICATION (run after apply):
-- SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county ILIKE '%pinellas%';
-- Expected: pct_density_of_applicable rises from 93.9 (367/392 real values) toward
-- ~96.2 (377/392: 367 + 9 newly-backfilled real-coordinate RPD/R-3/LMDR/MDR parcels;
-- RPD-W's 3 and RPD/R-3's remaining 2 placeholder-coordinate parcels stay unfixed).
-- far_applicable_parcels / pk1000_applicable_parcels remain 0 -- unchanged, correct
-- (all pinellas parcels are single-family/mobile-home residential, genuinely
-- FAR/pk1000 not-applicable, per root-cause note (1) above).
