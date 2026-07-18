-- Gold Standard shard-5 (dispatch 9f070f2b, 3rd firing, chat_session
-- architect-20260718T160000): ghost-success provenance purge for sarasota,
-- nassau, bay, gulf.
--
-- Two prior sessions today (16:37 UTC and a continuation) worked this shard's
-- FAILING letters and made real, verified progress (bay I/G, ghost-success
-- job deletion). Neither audited the PROVENANCE of already-PASSING letters.
-- Since sarasota is currently displayed as gold_standard=true (10/10) in the
-- live gold_standard_scoreboard view, a false PASS there is the worst-case
-- Honesty Protocol violation in this campaign. A 24-agent ULTRALOOP workflow
-- (12 audits + 12 independent adversarial refuters, all against live prod
-- data and repo source) found 10 of 11 audited (county,letter) pairs to be
-- GHOST_SUCCESS -- every claim independently reproduced by a refuter running
-- from scratch. Only bay/E survived as genuinely LEGITIMATE (verified via a
-- live point-in-polygon re-check against gis.baycountyfl.gov ArcGIS).
--
-- IMPORTANT CONTEXT: gold_standard_certifications (the actual cert-of-record
-- table, distinct from the live gold_standard_scoreboard view) already shows
-- certified=false for all 4 shard counties, with sarasota explicitly
-- revoked_at=2026-07-12 -- i.e. the system had already caught that sarasota
-- should not be certified, three weeks before this session, but the
-- fabricated DATA underneath was never cleaned up and the scoreboard VIEW
-- (read by the dispatch brief and both prior sessions today) was never wired
-- to reflect the revocation. This migration purges the underlying fabricated
-- rows so the scoreboard's own recompute becomes honest, regardless of that
-- separate scoreboard/certifications wiring gap (flagged in the session
-- report, not fixed here -- it's a scoring-infrastructure change, out of a
-- single engineer session's authority per HARD GUARDRAILS).
--
-- ============================================================================
-- 1. SARASOTA B/F -- circular self-referential outcome rows
-- ============================================================================
-- supabase/migrations/20260623_6county_gold_b_f_outcome_pipeline.sql's own
-- header already documents this exact pattern as "CONFIRMED GHOST SUCCESS"
-- for sibling county orange in the same batch, and explicitly names sarasota
-- as one of "the other 5 counties ... outside this shard's authorization ...
-- NOT purged here -- flagged for their owning shards." That flag is being
-- actioned now. All 165 rows share one of two identical bulk-insert
-- timestamps (2026-06-23 22:43:48/49), zero enrichment fields (source_url/
-- winner_name/winner_type all NULL), and winning_bid byte-identical to the
-- MCA row's own sold_amount -- i.e. the "independent verification" is a copy
-- of the auction's own already-scraped field, not a clerk/court record.
-- Confirmed sold_amount_source <> 'tax_deed_outcomes_sync' for all sarasota
-- rows (0 matches), meaning MCA.sold_amount itself is NOT derived from these
-- fake outcomes (unlike the bay case below) -- so sold_amount is left
-- intact; only the false "independently verified"/tier1 layer is reverted.

DELETE FROM public.foreclosure_outcomes
WHERE county = 'sarasota' AND data_source = 'sarasota_realforeclose_official';

DELETE FROM public.tax_deed_outcomes
WHERE county = 'sarasota' AND data_source = 'sarasota_realtaxdeed_official';

UPDATE public.multi_county_auctions
SET tier1_sold_amount = NULL,
    tier1_authoritative = false,
    parity_status = NULL,
    parity_source = NULL,
    updated_at = now()
WHERE lower(county) = 'sarasota'
  AND parity_source IN ('tier1_tax_deed_outcome','tier1_foreclosure_outcome');

-- ============================================================================
-- 2. SARASOTA G -- "Beta Synthetic" zoning district (self-labeled fabrication)
-- ============================================================================
-- zoning_districts.id=10679 is literally named 'Single Family Residential
-- (Beta Synthetic)', source_url/confidence_score both NULL, scraped_at
-- 2026-06-23 22:50:47 -- 48 minutes before sarasota's original
-- first_certified_at (23:38:34 same day), i.e. this fabricated district is
-- what produced the original certification. All 196 parcel_zones rows
-- referencing jurisdiction_id=824 (Sarasota city -- 1 of 3 sarasota
-- jurisdictions; Venice and North Port have ZERO zoning coverage) trace to
-- this one district via 3 script/backfill source tags, zero GIS/ordinance
-- citations. Repo-wide grep for the literal source strings returned zero
-- hits -- no checked-in script performed this write.

DELETE FROM public.parcel_zones
WHERE jurisdiction_id = 824
  AND (source = 'sarasota_city_beta'
       OR source LIKE 'shard8_run757%'
       OR source = 'sarasota_i_fix_20260623');

DELETE FROM public.zone_standards WHERE zoning_district_id = 10679;
DELETE FROM public.zoning_districts WHERE id = 10679;

-- ============================================================================
-- 3. SARASOTA E -- literal scraped-UI-label junk leaked into parcel_id
-- ============================================================================
-- 10 rows carry parcel_id values that are scraped HTML label text, not real
-- Sarasota Property Appraiser parcel/strap numbers ('Property Appraiser' x7,
-- 'TIMESHARE' x2, 'MULTIPLE PARCEL' x1) -- a scraper defect (grabbing an
-- anchor/table-header label instead of the parcel field), not deliberate
-- fabrication, but these currently pass a naive `parcel_id IS NOT NULL`
-- completeness check. Nulled so E stops counting them as linked.

UPDATE public.multi_county_auctions
SET parcel_id = NULL, updated_at = now()
WHERE lower(county) = 'sarasota'
  AND parcel_id IN ('Property Appraiser','TIMESHARE','MULTIPLE PARCEL');

-- ============================================================================
-- 4. SARASOTA J -- hardcoded-formula bid_decisions (no real ML/CMA)
-- ============================================================================
-- All 204 sarasota bid_decisions rows trace to 3 generator runs
-- (shard12_shapira_v14_proxy_20260619=189, shard8_run757_shapira_v14=14,
-- 6county_beta_v1=1). Source scripts self-label the output INFERRED/proxy:
-- ml_score is a deterministic function of assessed value/ARV (a clamped
-- ratio or a literal 4-bucket step function), not a trained model output;
-- cma_resale/cma_distressed are fixed multipliers of arv (ratios exactly
-- 0.960 and 0.8542/0.8750 with ZERO variance across all 203 numeric rows --
-- proof of a formula, not sourced comparables); distress_location/property/
-- owner are circular linear functions of the same synthetic ml_score. No
-- genuine J row exists for sarasota in this dataset.

DELETE FROM public.bid_decisions WHERE county_slug ILIKE 'sarasota';

-- ============================================================================
-- 5. NASSAU G/E -- bulk-inserted synthetic R-1 zoning (jurisdiction 865)
-- ============================================================================
-- 27 parcel_zones rows (79.4% of nassau's 34-parcel G denominator) share one
-- identical bulk-insert timestamp (2026-06-25 16:18:44), one carries the
-- corrupted sentinel value parcel_id='Property Appraiser' proving mechanical
-- fabrication, and the zone_standards row they all resolve to
-- (zoning_district_id=7716, jurisdiction 865) has source_url/ordinance_
-- section/confidence_score all NULL. By contrast the 6-7 rows sourced
-- 'shard10_run2346_nassau_ncpa_gis[_ordinance_backed]' are genuinely cited
-- (zoneomics.com, Nassau 2030 Comp Plan, maps.ncpafl.com) and are left
-- untouched. (nassau E's raw evaluator metric is a pure MCA.parcel_id
-- IS NOT NULL check with no format/junk anomaly rising to the same
-- confidence level as sarasota's -- not purged here; flagged in the session
-- report as a separate metric-design weakness, not fabricated data.)

DELETE FROM public.parcel_zones
WHERE jurisdiction_id = 865 AND source = 'shard4_run581_v2/nassau_synthetic';

DELETE FROM public.zone_standards WHERE zoning_district_id = 7716;
DELETE FROM public.zoning_districts WHERE id = 7716;

-- ============================================================================
-- 6. BAY B -- circular proxy-invented + self-synced outcome rows
-- ============================================================================
-- scripts/shard3_bay_bcdf_fix.py step_b_f_outcomes(): for 4/6 rows, invents
-- sold_amount = COALESCE(opening_bid, assessed_value*0.7) with opening_bid
-- actually NULL (verified: 392719*0.7=274903.30, 76159*0.7=53311.30,
-- 335750*0.7=235025.00, 365500*0.7=255850.00 -- exact arithmetic match, no
-- observed sale price); for the other 2, sold_amount was synced FROM the
-- outcomes row the same script had just inserted
-- (sold_amount_source='tax_deed_outcomes_sync'). All 6 outcomes rows
-- (data_source='shard3_bay_B_fix:2026-06-26') were then inserted by copying
-- that same MCA.sold_amount value back in -- both "sides" of the
-- verification were written by the same script, same transaction, same
-- source value.

DELETE FROM public.foreclosure_outcomes
WHERE county = 'bay' AND data_source = 'shard3_bay_B_fix:2026-06-26';

DELETE FROM public.tax_deed_outcomes
WHERE county = 'bay' AND data_source = 'shard3_bay_B_fix:2026-06-26';

UPDATE public.multi_county_auctions
SET sold_amount = NULL,
    tier1_sold_amount = NULL,
    tier1_authoritative = false,
    sold_amount_source = NULL,
    sold_amount_captured_at = NULL,
    updated_at = now()
WHERE lower(county) = 'bay'
  AND case_number IN ('2026-3080TD','2026-3113TD','24000802CA','25000131CA','25000427CA','25000431CA')
  AND sold_amount_source IN ('shard3_bay_opening_bid_proxy','tax_deed_outcomes_sync');

-- ============================================================================
-- 7. GULF G -- single "bootstrap" zone_standards row backing 68% of parcels
-- ============================================================================
-- Port St. Joe's only zoning district (R-1, id=10669) has exactly one
-- zone_standards row whose own source_url field is literally
-- "shard5_bootstrap_gulf", ordinance_section=NULL -- a fabricated/assumed
-- density value, not a lookup. All 15 non-Wewahitchka parcel_zones rows
-- (4 different cosmetically-distinct source tags: bootstrap_v2, inferred_
-- residential_default, auto, pa_fix -- all resolving to the SAME single
-- unsourced standard) collapse onto this one row. The 7 Wewahitchka rows
-- (jurisdiction 1010, real cityofwewahitchka.com LDR PDF citation,
-- confidence_score=0.90) are genuinely ordinance-backed and untouched.

DELETE FROM public.parcel_zones
WHERE jurisdiction_id = 952
  AND source IN ('gulf_bootstrap_v2:IJ_FIX','shard5_gulf_auto','shard5_gulf_pa_fix',
                 'inferred_residential_default_dor_crosswalk_r1_match');

DELETE FROM public.zone_standards WHERE zoning_district_id = 10669;
DELETE FROM public.zoning_districts WHERE id = 10669;
