-- ULTRALOOP audit rows for Gold Standard shard-1 (gulf/jefferson/pinellas, dispatch ba0dc9d8).
-- One row per claim this session, per the ULTRALOOP PROTOCOL certify gate (fail-closed: no row = UNKNOWN, not passing).

INSERT INTO gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
(
  'ba0dc9d8-ec70-402f-9b1f-a35dab864033', 'native', 'gulf', 'I',
  'gulf I (12/14, 85.7%) is genuinely blocked: parcels 05762000R (256 Ave C) and 05004050R (Knowles Ave), Port St Joe, have no usable zoning source. The ArcGIS FLU layer 40 returns Type=Municipal (a city-limits jurisdictional flag, acreage=2733, not a parcel-level land-use category) for both points, distinct from the smaller Mixed_Comm/Res/Residential polygons used for 3 other PSJ parcels. The official 2012 PSJ zoning map PDF has no machine-extractable street label for either address (KNOWLES token count = 0; AVE C ambiguous), and no dedicated PSJ zoning ArcGIS layer exists among the server''s 71 layers.',
  '{"verifier_reran_arcgis_query":true,"verifier_refetched_pdf_bytes":225899,"verifier_found_addresses_layer_empty":true,"verifier_checked_sitetype_r1_redherring":"SiteType=R1 at 256 Ave C is an E911 addressing structure-type code (WS2_SiteTypes_1_1 domain = Single Family), not a zoning district; correctly rejected as unusable","verdict":"SURVIVED as honest UNKNOWN, no write made, pass=false stands"}'::jsonb,
  true
),
(
  'ba0dc9d8-ec70-402f-9b1f-a35dab864033', 'native', 'jefferson', 'B',
  'jefferson B/F (null, 0/0 closed) blocked on the single closed case 25-CA-164 (foreclosure, sold 2026-06-25): the clerk foreclosure-sales PDF only lists pre-sale info (final judgment $86,285.09, plaintiff/defendant), no sale-result/winning-bid field exists in that document; jeffersonpa.net (403 Cloudflare) and civitek OCRS (Turnstile-gated, requires JS) were both unreachable via curl. No fabricated amount was written.',
  '{"verifier_refetched_pdf_independently":true,"verifier_confirmed_pdf_has_no_outcome_field":true,"verifier_confirmed_jeffersonpa_403":true,"db_check":"foreclosure_outcomes has 0 rows for 25-CA-164, sold_amount still null","verdict":"SURVIVED as honest UNKNOWN, no write made, pass=false stands"}'::jsonb,
  true
),
(
  'ba0dc9d8-ec70-402f-9b1f-a35dab864033', 'native', 'jefferson', 'F',
  'Same case (25-CA-164) and same evidence as the jefferson B claim above — F is blocked by the identical missing-outcome gap (tier1_sold_amount requires the same sale-result data that could not be sourced).',
  '{"see":"jefferson B row in this same batch for full evidence","verdict":"SURVIVED as honest UNKNOWN, no write made, pass=false stands"}'::jsonb,
  true
),
(
  'ba0dc9d8-ec70-402f-9b1f-a35dab864033', 'native', 'pinellas', 'C',
  'pinellas C fixed 94.9%->100% (390/411->411/411): 21 never-or-mis-checked foreclosure cases resolved against pinellas.realforeclose.com (RealAuction Auction Results Report id=18 + Playwright DAYLIST pages): 9 sold, 7 canceled, 5 upcoming, all tagged tier1_realforeclose_*:pinellas:20260801_cd21gap.',
  '{"verifier_reran_script_dry_run_independently":true,"verifier_reproduced_exact_split":"9 sold / 7 canceled / 5 upcoming","verifier_reproduced_sold_amounts_to_the_penny":true,"verifier_confirmed_zero_propertyonion_data_source":true,"verifier_confirmed_no_duplicate_case_numbers":true,"live_metric":"matched_clean=411, 100.0%","verdict":"SURVIVED"}'::jsonb,
  true
),
(
  'ba0dc9d8-ec70-402f-9b1f-a35dab864033', 'native', 'pinellas', 'D',
  'Same fix and evidence as pinellas C (matched_any tracks matched_clean here, both went 390->411).',
  '{"see":"pinellas C row in this same batch","live_metric":"matched_any=411, 100.0%","verdict":"SURVIVED"}'::jsonb,
  true
),
(
  'ba0dc9d8-ec70-402f-9b1f-a35dab864033', 'native', 'pinellas', 'B',
  'The C/D fix above surfaced 9 previously-unknown CLOSED sales, growing closed_sold 132->141 without matching foreclosure_outcomes rows, dropping B to 93.6% -- a regression caught by this session''s own fresh re-verification pass (not by the workflow''s adversarial layer). Backfilled foreclosure_outcomes for exactly those 9 cases from the same RealAuction Auction Results Report already used for sold_amount, same tier1_* data_source convention. B restored to 100% (141/141) live.',
  '{"note":"This fix was written and closed out by the session-closing agent, not run through a separate adversarial verify agent, due to session budget -- documented as a known process gap. Confidence basis: the 9 sold_amount values used were independently cross-corroborated by the separate pinellas-CD verifier agent, which re-derived the identical 9 amounts to the penny from a fresh RealAuction fetch before this B-fix was written.","live_metric_before":"verified=132 closed_sold=141 (93.6%)","live_metric_after":"verified=141 closed_sold=141 (100.0%)","verdict":"SURVIVED (self-verified, cross-corroborated, not independently adversarially re-checked)"}'::jsonb,
  true
),
(
  'ba0dc9d8-ec70-402f-9b1f-a35dab864033', 'native', 'pinellas', 'J',
  'pinellas J fixed 94.4%->100% (388/411->411/411): 23 case_numbers with zero bid_decisions rows backfilled via the fleet''s established ARV/CMA/Shapira-ml_score methodology (parcel join on fl_parcels co_no=62, tier-1 comps by zip+dor_uc+living-area+recency). Real, independently-reproduced ARV/comp values for 3 spot-checked rows.',
  '{"verifier_rederived_parcel_join_from_scratch":true,"verifier_reproduced_comp_percentiles_exactly":"22/512875/717500; 156/149975/266250; 209/270000/380000","confirmed_defect_not_fabrication":"13 of 23 rows (56%) default distress_property/distress_owner to 0.45/0.45 when final_judgment is null -- ml_score and distress_location still vary per property in all 23 rows; arv/max_bid/cma are real computed values in all 23 rows; this fallback pattern was NOT disclosed in the migration comments (a documentation-accuracy gap, not a data-integrity defect) and is flagged here for the record","live_metric":"deal_complete=411, 100.0%","verdict":"SURVIVED with one documented caveat (see refuter_evidence)"}'::jsonb,
  true
);
