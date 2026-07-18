-- GTM-22 Phase 2: model provenance verdict logged to insights
-- (issue #12745, session 3, 2026-07-18)
--
-- HONESTY V3: all findings below are VERIFIED via code search this session.
-- References:
--   1. brevard-bidder-scraper/src/models/ensemble_model_v4.py (V4 training code)
--   2. .github/workflows/summit-train-shapira-v4.yml (GHA workflow, never run)
--   3. packages/biddeed-mcp/src/tools/shapira.js (live S5 tool implementation)
--   4. scripts/train_shapira_v14.py (V14 trainer, comment: "NOT the V4 patent's stacked ensemble")
--
-- CORPUS: 21,308 (5,788 foreclosure + 15,520 tax deed) — VERIFIED by Session 2.
-- "49,973" in external materials: not found in code/DB as of this search. UNVERIFIED.

INSERT INTO public.insights (
  anomaly_type, severity, county, detail, source, created_at
) VALUES (
  'gtm22_phase2_model_provenance',
  'high',
  NULL,
  jsonb_build_object(
    'session', 'gtm22_session3_20260718',
    'verdict', 'VERIFIED_partial',
    'production_model', jsonb_build_object(
      'version', 'v14.0',
      'family', 'xgboost_single',
      'accuracy', 0.7221,
      'auc', 0.7834,
      'cv_auc', '0.7785±0.0014',
      'trained_at', '2026-05-27',
      'n_train', 137488,
      'n_test', 34372,
      'n_features', 21,
      'status', 'VERIFIED_sole_production_row'
    ),
    'v4_ensemble', jsonb_build_object(
      'code_found', true,
      'file', 'brevard-bidder-scraper/src/models/ensemble_model_v4.py',
      'gha_workflow', '.github/workflows/summit-train-shapira-v4.yml',
      'ever_run', false,
      'trained_artifact_in_registry', false,
      'status', 'CANDIDATE_CODE_ONLY_UNTESTED',
      'note', 'Training code exists (XGB+LGBM+CatBoost->LogReg meta, is_production=false guard). GHA workflow has never green-run per code comment [UNTESTED]. No shapira_models row for v4.0 confirmed by Session 2.'
    ),
    'marketed_82_6_pct', jsonb_build_object(
      'value', '82.6%',
      'status', 'UNVERIFIED',
      'files_containing_claim', ARRAY[
        'packages/biddeed-mcp/smithery.yaml:5',
        'packages/biddeed-mcp/README.md:85',
        'packages/biddeed-mcp/src/tools/shapira.js:7',
        'packages/biddeed-mcp/src/tools/shapira.js:94'
      ],
      'evidence_basis', 'No trained V4 model with measured metrics. V14 accuracy=72.2%, not 82.6%.',
      'action_required', 'Replace with verified figure or UNVERIFIED label in all LP-facing files'
    ),
    's5_predict_auction_outcome', jsonb_build_object(
      'served_by', 'packages/biddeed-mcp/src/tools/shapira.js',
      'actual_implementation', 'heuristic_scorecard_not_ml_model',
      'note', 'Live S5 tool uses base_rate * discount_score * size_score heuristic. No server-side XGBoost call. Comment in code acknowledges "full XGBoost runs server-side" but implementation does not call any model endpoint. Marketing copy claiming 82.6% XGBoost+LGBM+CatBoost ensemble is UNVERIFIED.',
      'action_for_lp', 'LP doc must use v14.0 verified metrics (acc=72.2%, AUC=0.7834) or mark ensemble as UNVERIFIED/in-development'
    ),
    'corpus_verified', jsonb_build_object(
      'foreclosure_outcomes', 5788,
      'tax_deed_outcomes', 15520,
      'total_verified', 21308,
      'multi_county_auctions_total', 85675,
      'status', 'VERIFIED_by_session2',
      'claim_49973_status', 'UNVERIFIED - not found in any table or code this session'
    )
  )::text,
  'gtm22_session3_model_provenance_search',
  now()
);
