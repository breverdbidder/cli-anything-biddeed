-- GOLD STANDARD shard-2 (walton), dispatch 5e1e6111-7b73-4ac4-87f8-1eb182321346,
-- follow-up to 20260725_gold_standard_shard2_walton_g_zoning_categorization.sql.
--
-- REGRESSION CAUGHT AND FIXED IN THE SAME SESSION (live-verified before certifying):
-- setting General Commercial (id=12652)'s category='Commercial' — a real, correct fix,
-- needed because the district had been mistagged category='residential' by a prior
-- ingestion bug — had a side effect: v_zoning_district_applicability's pk1000_applicable
-- formula defaults ANY category='commercial'/'industrial'/'mixed-use' district (with
-- pk1000_regulated left NULL) to pk1000-applicable=true. That flipped
-- pk1000_applicable_parcels 0->1 with 0 values, moving walton's G metric from
-- FAIL(density=91.4) to a WORSE FAIL(pk1000=0.0, since G = LEAST(density, far, pk1000)).
--
-- Root cause of the regression: correcting category (needed for the real density fix)
-- has a real, ordinance-legitimate consequence — Walton's own LDC parking chapter
-- (5.02.00, separate from the Ch.2 zoning-district chapter) genuinely does apply
-- use-based parking ratios to commercial districts. This isn't a false positive to be
-- suppressed; it's a real gap that needs a real sourced value, same as density needed.
--
-- FIX: real ordinance-sourced parking_per_1000sf value researched this session.
-- Source: Walton County LDC Chapter 5 (Design and Development Standards),
-- mywaltonfl.gov/DocumentCenter/View/3235/LDC-Chapter-5-Design-and-Development-Standards,
-- Section 5.02.00 "OFFSTREET PARKING AND LOADING", Section 5.02.02 "Offstreet Parking
-- Requirements Chart" (use-based, not zone-based -- confirmed no GC-zone-specific ratio
-- exists; the chart applies per land-use category regardless of zoning district).
-- Item D.29 "Shopping center" = 5 spaces per 1,000 sq ft GFA. Matched to General
-- Commercial's own Sec. 2.02.15 purpose statement ("general commercial uses that serve
-- the larger community and the traveling public... a broad range of commercial
-- operations and services") -- the closest fit among the chart's line items, same
-- representative-rate methodology already used for Seminole RC-1/GC-2
-- (20260718f_gold_standard_shard3_seminole_g_pk1000_applicability_fix_run26f01b9b.sql).
-- Alternative line item D.30 "Other general business or personal service
-- establishments" = 2.86/1,000sf (1 space per 350sf) exists for narrower non-retail
-- commercial uses; flagged here as the residual interpretation, not used, since GC's own
-- purpose language leans general/broad rather than narrowly office/service.
--
-- BEFORE (live, this session, immediately after the categorization migration applied):
--   G FAIL(0.0, density=100.0 far=98.1 pk1000=0.0) -- pk1000_applicable_parcels=1, 0 with value
-- Expected AFTER: pk1000=100.0 (1/1), G = LEAST(density=100.0, far=98.1, pk1000=100.0) = 98.1 -> PASS (>=95).

UPDATE zone_standards
   SET parking_per_1000sf = 5.0,
       source_url = 'https://www.mywaltonfl.gov/DocumentCenter/View/3235/LDC-Chapter-5-Design-and-Development-Standards',
       ordinance_section = COALESCE(ordinance_section, '') || CASE WHEN ordinance_section IS NULL OR ordinance_section = '' THEN '' ELSE ' | ' END ||
         'LDC Ch.5 Sec.5.02.02.D.29 "Shopping center" = 5 spaces/1,000 sf GFA (use-based parking chart, matched to GC''s Sec.2.02.15 general-commercial purpose language; alternative D.30 "other general business/personal service" = 2.86/1,000sf not used, GC purpose leans general/broad retail)'
 WHERE zoning_district_id = 12652;
