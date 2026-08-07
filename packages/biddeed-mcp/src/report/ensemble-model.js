// SUMMIT-B V4 — Stacked Ensemble ONNX Inference (Patent Claim 8)
// XGBoost + LightGBM + CatBoost base learners → Random Forest meta-learner
//
// AUC: 0.9468 (vs XGBoost v14.0 baseline: 0.7834) — real independent inference
// Artifacts: 4 ONNX files in model_artifacts table (xgb_base, lgbm_base, catb_base, rf_meta)
// Trained: 2026-08-02 on 5,118 FL auction outcomes
//
// Pipeline:
//   feature_array (13 floats, same order as training)
//     → xgb_base.onnx  → xgb_prob
//     → lgbm_base.onnx → lgbm_prob
//     → catb_base.onnx → catb_prob
//     → rf_meta.onnx([xgb_prob, lgbm_prob, catb_prob]) → ensemble_prob
//
// Interface: predictEnsemble(x, { get }) — drop-in replacement for the old stub.
// x: 13-float feature array in shapira_models.features_used order (same contract
// as feature-vector.js). deps.get: Supabase REST helper injected by composer.js.

import ort from 'onnxruntime-node';

const MODEL_VERSION = 'v4.0-20260802-015242';
const ARTIFACTS = ['xgb_base.onnx', 'lgbm_base.onnx', 'catb_base.onnx', 'rf_meta.onnx'];

// Process-level cache — immutable once trained
let _sessions = null;

async function loadSessions(get) {
  if (_sessions) return _sessions;

  const loaded = {};
  for (const name of ARTIFACTS) {
    const rows = await get(
      `model_artifacts?model_version=eq.${encodeURIComponent(MODEL_VERSION)}&artifact_name=eq.${encodeURIComponent(name)}&select=artifact_b64&limit=1`
    ).catch(() => []);

    if (!rows?.length || !rows[0]?.artifact_b64) {
      throw new Error(`V4 ONNX artifact missing from model_artifacts: ${name}`);
    }
    const buf = Buffer.from(rows[0].artifact_b64, 'base64');
    loaded[name] = await ort.InferenceSession.create(buf);
  }

  _sessions = loaded;
  return _sessions;
}

// Test injection hooks
export function _setSessionsForTest(s) { _sessions = s; }
export function _resetSessionsForTest() { _sessions = null; }

// x: 13-float array in features_used order (see feature-vector.js)
// Returns the same shape as old predictEnsemble — composer.js unchanged.
export async function predictEnsemble(x, { get }) {
  const sess = await loadSessions(get);

  const input13 = new ort.Tensor('float32', Float32Array.from(x), [1, 13]);

  // Run 3 base learners — CatBoost uses 'features' as input name
  const [xgbOut, lgbmOut, catbOut] = await Promise.all([
    sess['xgb_base.onnx'].run({ float_input: input13 }),
    sess['lgbm_base.onnx'].run({ float_input: input13 }),
    sess['catb_base.onnx'].run({ features: input13 }),
  ]);

  const xgbProb  = xgbOut.probabilities.data[1];
  const lgbmProb = lgbmOut.probabilities.data[1];
  const catbProb = catbOut.probabilities.data[1];

  // RF meta-learner
  const metaInput = new ort.Tensor('float32', Float32Array.from([xgbProb, lgbmProb, catbProb]), [1, 3]);
  const rfOut = await sess['rf_meta.onnx'].run({ meta_input: metaInput });
  const ensembleProb = rfOut.output_probability.data[1];

  return {
    model_version: MODEL_VERSION,
    model_family: 'stacked_ensemble_xgb_lgbm_catboost_rf_meta',
    ensemble_auc: 0.9468,
    probability_third_party_purchase: Number(ensembleProb.toFixed(4)),
    ensemble: true,
    method: 'v4_onnx_independent_inference',
    base_learners: {
      xgb_prob:  Number(xgbProb.toFixed(4)),
      lgbm_prob: Number(lgbmProb.toFixed(4)),
      catb_prob: Number(catbProb.toFixed(4)),
    },
    caveat: 'V4 stacked ensemble — independent ONNX inference for all 3 base learners + RF meta-learner. AUC 0.9468. Trained on 5,118 FL auction outcomes (2026-08-02).',
  };
}
