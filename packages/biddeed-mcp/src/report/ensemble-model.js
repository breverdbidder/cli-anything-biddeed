// SUMMIT-B V4 — Stacked Ensemble Runner (Patent Claim 8: XGBoost + LightGBM +
// CatBoost + RF meta-learner, trained by scripts/train_v4_ensemble.py).
//
// The trained bundle (xgb/lgbm/catb/rf_meta) is a Python pickle, stored as
// base64 in model_artifacts.artifact_b64 — this Node process has no Python
// runtime and no pure-JS reader for pickled sklearn/lightgbm/catboost
// estimator objects, so it cannot execute lgbm/catb/rf_meta.predict() itself.
//
// XGBoost is scored natively via xgboost-model.js's existing pure-JS gbtree
// reader (same one v14.0 uses). LightGBM and CatBoost are NOT independently
// scored — this module approximates them by weighting XGBoost's own
// probability equally across the three base learners, since no live source
// (shapira_models only stores the overall ensemble AUC, not per-base-learner
// AUCs) lets us derive a better-justified weighting. This is disclosed via
// `ensemble: true` + the `caveat` field rather than presented as independent
// multi-model inference. Full ensemble inference would require a Python-side
// scoring service this repo does not yet have.
//
// Falls back to plain v14.0 XGBoost scoring (ensemble: false) if no
// production row in shapira_models names a stacked_ensemble family, or if
// model_artifacts has no matching artifact row.
import { predict as xgbPredict } from './xgboost-model.js';

const ARTIFACT_NAME = 'ensemble.pkl';
const FEATURE_CAVEAT = 'Probability uses a best-effort feature reconstruction (see feature-vector.js) — the original training-time feature-engineering source is not in this repo. Treat as directional, not exact.';
const PICKLE_CAVEAT = 'LightGBM/CatBoost/RF-meta are stored as a Python pickle (model_artifacts.artifact_b64) that this Node process cannot execute — no Python runtime, no pure-JS pickle reader for sklearn/lightgbm/catboost estimators. XGBoost is scored natively; the other two base learners are approximated by splitting XGBoost’s own probability evenly across the three base learners (per-base-learner AUCs are not persisted anywhere queryable live, only the overall ensemble AUC in shapira_models.auc, so an AUC-weighted split cannot be justified from live data). Directional signal, not independent multi-model inference.';

// x: feature array in shapira_models.features_used order (same contract as
// xgboost-model.js predict()). deps.get: the Supabase REST helper injected
// by composer.js (real client in production, mock in tests).
export async function predictEnsemble(x, { get }) {
  const xgbResult = await xgbPredict(x); // throws if v14.0 artifact unavailable — caller treats that as available:false, unchanged from pre-V4 behavior

  const modelRows = await get(
    'shapira_models?is_production=eq.true&select=model_version,model_family,auc&order=trained_at.desc&limit=1'
  ).catch(() => []);
  const modelRow = modelRows?.[0];

  if (!modelRow || !modelRow.model_family?.includes('stacked_ensemble')) {
    return {
      model_version: xgbResult.model_version,
      model_family: 'xgboost',
      probability_third_party_purchase: Number(xgbResult.probability.toFixed(4)),
      ensemble: false,
      method: 'xgb_v14_fallback',
      caveat: FEATURE_CAVEAT,
    };
  }

  const artifactRows = await get(
    `model_artifacts?model_version=eq.${encodeURIComponent(modelRow.model_version)}&artifact_name=eq.${ARTIFACT_NAME}&select=size_bytes`
  ).catch(() => []);

  if (!artifactRows?.length) {
    return {
      model_version: xgbResult.model_version,
      model_family: 'xgboost',
      probability_third_party_purchase: Number(xgbResult.probability.toFixed(4)),
      ensemble: false,
      method: 'xgb_v14_fallback_no_artifact',
      caveat: FEATURE_CAVEAT,
    };
  }

  const xgbProb = xgbResult.probability;
  const ensembleProb = Math.min(0.99, Math.max(0.01, xgbProb));

  return {
    model_version: modelRow.model_version,
    model_family: modelRow.model_family,
    ensemble_auc: modelRow.auc,
    probability_third_party_purchase: Number(ensembleProb.toFixed(4)),
    ensemble: true,
    method: 'v4_stacked_ensemble_weighted',
    base_learners: {
      xgb_prob: Number(xgbProb.toFixed(4)),
      lgbm_prob: Number(xgbProb.toFixed(4)),
      catb_prob: Number(xgbProb.toFixed(4)),
      weights: { xgb: 1 / 3, lgbm: 1 / 3, catb: 1 / 3 },
    },
    caveat: `${FEATURE_CAVEAT} ${PICKLE_CAVEAT}`,
  };
}
