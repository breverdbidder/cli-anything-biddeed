// SUMMIT-B V4 stacked ensemble wiring — issue: "Wire V4 ensemble into MCP:
// load from model_artifacts table + replace xgboost-model.js".
//
// Exercises predictEnsemble() directly (mocked Supabase `get`, no network)
// against the three states it must handle: V4 production + artifact present
// (ensemble scoring), V4 production but artifact missing (fallback), and no
// stacked_ensemble production row at all (fallback) — mirroring the shapes
// confirmed live against Supabase on 2026-08-02 (shapira_models.model_version
// = 'v4.0-20260802-015242', model_artifacts.artifact_name = 'ensemble.pkl').
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const { predictEnsemble } = await import('../src/report/ensemble-model.js');
const { _setModelForTest, _resetModelForTest } = await import('../src/report/xgboost-model.js');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const tinyModelDoc = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/tiny-xgb-model.json'), 'utf8'));

function installTinyModel() {
  const gbm = tinyModelDoc.learner.gradient_booster.model;
  _setModelForTest({
    version: 'v14.0',
    trees: gbm.trees,
    baseScore: parseFloat(tinyModelDoc.learner.learner_model_param.base_score),
    featureNames: [],
  });
}

const FEATURE_VECTOR = new Array(17).fill(0);

test('predictEnsemble: V4 production row + artifact present -> ensemble scoring, model_family carries stacked_ensemble', async () => {
  installTinyModel();
  const get = async (pathStr) => {
    if (pathStr.startsWith('shapira_models')) {
      return [{ model_version: 'v4.0-20260802-015242', model_family: 'stacked_ensemble_xgb_lgbm_catboost_rf_meta', auc: 0.9468 }];
    }
    if (pathStr.startsWith('model_artifacts')) {
      return [{ size_bytes: 2253960 }];
    }
    return [];
  };
  const result = await predictEnsemble(FEATURE_VECTOR, { get });
  assert.equal(result.ensemble, true);
  assert.ok(result.model_family.includes('stacked_ensemble'), `model_family must contain "stacked_ensemble", got ${result.model_family}`);
  assert.equal(result.model_version, 'v4.0-20260802-015242');
  assert.equal(result.ensemble_auc, 0.9468);
  assert.equal(result.method, 'v4_stacked_ensemble_weighted');
  assert.equal(typeof result.probability_third_party_purchase, 'number');
  assert.ok(result.base_learners);
  assert.ok(result.caveat.includes('cannot execute'), 'caveat must disclose the pickle-inference limitation');
  _resetModelForTest();
});

test('predictEnsemble: V4 production row but no model_artifacts row -> falls back to plain XGBoost, ensemble:false', async () => {
  installTinyModel();
  const get = async (pathStr) => {
    if (pathStr.startsWith('shapira_models')) {
      return [{ model_version: 'v4.0-20260802-015242', model_family: 'stacked_ensemble_xgb_lgbm_catboost_rf_meta', auc: 0.9468 }];
    }
    if (pathStr.startsWith('model_artifacts')) return [];
    return [];
  };
  const result = await predictEnsemble(FEATURE_VECTOR, { get });
  assert.equal(result.ensemble, false);
  assert.equal(result.method, 'xgb_v14_fallback_no_artifact');
  assert.equal(result.model_family, 'xgboost');
  _resetModelForTest();
});

test('predictEnsemble: no stacked_ensemble production row -> falls back to plain XGBoost, ensemble:false', async () => {
  installTinyModel();
  const get = async (pathStr) => {
    if (pathStr.startsWith('shapira_models')) {
      return [{ model_version: 'v14.0', model_family: 'xgboost', auc: 0.7834 }];
    }
    return [];
  };
  const result = await predictEnsemble(FEATURE_VECTOR, { get });
  assert.equal(result.ensemble, false);
  assert.equal(result.method, 'xgb_v14_fallback');
  assert.equal(result.model_family, 'xgboost');
  _resetModelForTest();
});
