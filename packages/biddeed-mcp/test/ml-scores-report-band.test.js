// Issue #20044 item 2d — the nightly GHA batch (scripts/ml_score_nightly.py)
// pre-scores upcoming auctions with the real 3-learner pkl ensemble and
// upserts one row per (mca_id, model_version) into ml_scores. composer.js's
// scoreModel() must prefer that row over a live Modal/pure-JS call when
// present, and it must carry three DISTINCT learner probabilities through
// to the report band (never three identical numbers).
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { buildReport } = await import('../src/report/composer.js');
const { MODEL_VERSION } = await import('../src/report/ensemble-model.js');

const MCA_ID = '19499973-5191-4e5b-bb96-c0f59fb14101'; // case 250104, per docs/spec/20043.md

const AUCTION_250104 = {
  id: MCA_ID,
  case_number: '250104', county: 'brevard',
  property_address: '123 TEST BLVD, MELBOURNE, FL 32901',
  judgment_amount: 150000, assessed_value: 120000, opening_bid: null,
  sale_type: 'foreclosure', owner_name: 'TEST OWNER',
};

const ML_SCORES_ROW = {
  p_third_party: 0.812, xgb_prob: 0.79, lgbm_prob: 0.83, catb_prob: 0.81,
  feature_vector: { judgment_amount_log1p: 11.9 }, scored_at: '2026-09-06T06:20:00Z',
};

function mockGetWithMlScoresRow() {
  return async (pathStr) => {
    if (pathStr.startsWith('ml_scores')) {
      assert.match(pathStr, new RegExp(`mca_id=eq\\.${MCA_ID}`));
      assert.match(pathStr, new RegExp(`model_version=eq\\.${MODEL_VERSION.replace(/\./g, '\\.')}`));
      return [ML_SCORES_ROW];
    }
    return []; // priors, fl_parcels, zoning_assignments, shapira_formula_params — all empty, not under test here
  };
}

test('scoreModel prefers an existing ml_scores row over live Modal/pure-JS scoring', async () => {
  const get = mockGetWithMlScoresRow();
  const report = await buildReport(AUCTION_250104, { get });
  const ml = report.context_layers.ml_model;
  assert.equal(ml.available, true);
  assert.equal(ml.method, 'ml_scores_nightly_batch');
  assert.equal(ml.model_version, MODEL_VERSION);
  assert.equal(ml.probability_third_party_purchase, 0.812);
  assert.equal(ml.base_learners.xgb_prob, 0.79);
  assert.equal(ml.base_learners.lgbm_prob, 0.83);
  assert.equal(ml.base_learners.catb_prob, 0.81);
  // The three learner probabilities must be genuinely distinct — never a
  // copied/repeated number presented as three learners.
  const { xgb_prob, lgbm_prob, catb_prob } = ml.base_learners;
  assert.ok(!(xgb_prob === lgbm_prob && lgbm_prob === catb_prob), 'learner probabilities must not all be equal');
});

test('scoreModel falls back to the live path when no ml_scores row exists for this mca_id/model_version', async () => {
  const get = async (pathStr) => {
    if (pathStr.startsWith('ml_scores')) return [];
    return [];
  };
  const report = await buildReport(AUCTION_250104, { get });
  const ml = report.context_layers.ml_model;
  assert.notEqual(ml.method, 'ml_scores_nightly_batch');
});

test('scoreModel does not query ml_scores at all when the auction has no id (never crashes on a missing key)', async () => {
  const { id, ...noId } = AUCTION_250104;
  let queriedMlScores = false;
  const get = async (pathStr) => {
    if (pathStr.startsWith('ml_scores')) queriedMlScores = true;
    return [];
  };
  const report = await buildReport(noId, { get });
  assert.equal(queriedMlScores, false);
  assert.ok(report.context_layers.ml_model);
});
