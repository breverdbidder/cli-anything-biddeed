// GTM-22 S5 REPORT ENGINE — live inference for shapira_models v14.0.
//
// Pure-JS reader for the standard XGBoost "gbtree" JSON dump format
// (learner.gradient_booster.model.trees[]), so the S5 report can score a
// property without a Python runtime in the MCP process. Cross-validated
// against `xgboost.Booster.predict()` in Python on the live v14.0 artifact
// (2026-07-20): zeros/ones/fixture-414 probability vectors matched to
// float32 precision (see issue #12853 report for the pasted comparison).
//
// Scope note: this reads the TRAINED ARTIFACT (model.json) faithfully. It
// does NOT reconstruct the original feature-engineering pipeline that
// produced training-time feature values — that source is not in this repo
// (see feature-vector.js header). The probability this module returns is
// only as faithful as the feature vector handed to it.
import { storageGet } from '../supabase.js';

const MODEL_VERSION = 'v14.0';
const BUCKET = 'shapira-models';
const MODEL_PATH = 'v14/2026-05-27-180308/model.json';

let cachedModel = null;

function sigmoid(z) {
  return 1 / (1 + Math.exp(-z));
}

// Walks one gbtree node array to a leaf, honoring the model's own
// missing-value routing (default_left) rather than assuming a direction.
function evalTree(tree, x) {
  const { left_children: left, right_children: right, split_indices: idx, split_conditions: cond, default_left: defLeft } = tree;
  let node = 0;
  while (left[node] !== -1) {
    const fval = x[idx[node]];
    const missing = fval === null || fval === undefined || Number.isNaN(fval);
    const goLeft = missing ? !!defLeft[node] : fval < cond[node];
    node = goLeft ? left[node] : right[node];
  }
  return cond[node]; // leaf weight (split_conditions doubles as leaf value at leaf nodes)
}

// Loads + caches the production v14.0 artifact for this process lifetime.
// Model artifacts are immutable once trained (new versions get a new
// storage_path_model row in shapira_models) — safe to cache at module scope,
// unlike certification state in cert-gate.js which can change intra-day.
export async function loadModel() {
  if (cachedModel) return cachedModel;
  const text = await storageGet(BUCKET, MODEL_PATH);
  const doc = JSON.parse(text);
  const gbm = doc.learner.gradient_booster.model;
  cachedModel = {
    version: MODEL_VERSION,
    trees: gbm.trees,
    baseScore: parseFloat(doc.learner.learner_model_param.base_score),
    featureNames: doc.learner.feature_names,
    objective: doc.learner.objective?.name || 'binary:logistic',
  };
  return cachedModel;
}

// Test-only hook — lets tests inject a small fixture model instead of
// fetching the 1.9MB production artifact from storage.
export function _setModelForTest(model) {
  cachedModel = model;
}
export function _resetModelForTest() {
  cachedModel = null;
}

// x: array of 21 numeric feature values in shapira_models.features_used order.
// Returns { probability, margin, model_version }. Throws if the artifact
// cannot be loaded — callers must treat that as "artifact not deployed",
// per Amendment 2, and render the model card without a number, not a fake one.
export async function predict(x) {
  const model = await loadModel();
  // base_score is stored in label-space (boost_from_average) — invert to
  // margin-space before summing tree contributions, matching XGBoost's own
  // predict() behavior for binary:logistic (verified against Python output).
  let margin = Math.log(model.baseScore / (1 - model.baseScore));
  for (const tree of model.trees) margin += evalTree(tree, x);
  return {
    probability: sigmoid(margin),
    margin,
    model_version: model.version,
  };
}
