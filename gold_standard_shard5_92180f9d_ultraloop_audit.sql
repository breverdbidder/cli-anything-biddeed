-- Gold Standard shard-5 (dispatch 92180f9d-afec-4a9b-99e4-8ef780ea2851): hamilton + baker
-- ultraloop_audit rows for this session's claims. All 4 survived independent verification
-- (3 via a dedicated adversarial-refuter subagent workflow, the 4th -- baker C/D -- via
-- the orchestrating session independently re-running pencil_dod_evaluate_county('baker')
-- live and confirming C/D=100.0/matched_clean=10 after the fix, plus re-reading the
-- live-source evidence captured in supabase/migrations/20260813b_..._realforeclose_cd_fix.sql).
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('92180f9d-afec-4a9b-99e4-8ef780ea2851', 'fallback', 'hamilton', 'C/D',
   'case 2025-CA-46 flipped PHANTOM_NOT_ON_CLERK -> matched_clean (live hamiltonclerk.com/foreclosures/ match, case+date+judgment+address all exact)',
   '{"method":"adversarial_refuter_subagent","checked":["live_html_refetch","db_state","cross_county_collision_check","staleness_check"],"result":"all_fields_matched_exactly"}'::jsonb,
   true),
  ('92180f9d-afec-4a9b-99e4-8ef780ea2851', 'fallback', 'baker', 'I',
   'cases 117+132 card-completeness fixed via Baker County GIS ArcGIS parcels_web2 FeatureServer (zoning + centroid geo) + bakerpa.com (assessed_value); baker I 80.0%->100.0%',
   '{"method":"adversarial_refuter_subagent","checked":["arcgis_zoning_requery","bakerpa_value_requery","independent_centroid_recompute","db_state","jurisdiction_id_check","live_metric_requery"],"result":"exact_match_on_every_leg"}'::jsonb,
   true),
  ('92180f9d-afec-4a9b-99e4-8ef780ea2851', 'fallback', 'baker', 'J',
   'bid_decisions row inserted for case 132 (Shapira formula, arv=bakerpa Total Just Value, final_judgment=mca.judgment_amount, 5/5 factor keys); baker J 90.0%->100.0%',
   '{"method":"adversarial_refuter_subagent","checked":["db_row_requery","hand_recomputed_shapira_formula","factor_key_completeness","judgment_amount_cross_check","live_metric_requery"],"result":"exact_match_no_arithmetic_error"}'::jsonb,
   true),
  ('92180f9d-afec-4a9b-99e4-8ef780ea2851', 'fallback', 'baker', 'C/D',
   'cases 117+132 (last 2 residual rows) matched_clean via baker.realforeclose.com AJAX Waiting-area endpoint, genuinely untried source, no login/Turnstile; baker C/D 80.0%->100.0%',
   '{"method":"orchestrator_independent_reverify","checked":["live_pencil_dod_evaluate_county_baker_post_fix","migration_sql_content_review"],"result":"C=100.0 D=100.0 matched_clean=10, all 10 letters A-J now PASS live"}'::jsonb,
   true);
