// SUMMIT-B V4 — Stacked Ensemble inference via Supabase Edge Function
// (Patent Claim 8: XGBoost + LightGBM + CatBoost + RF meta-learner)
//
// Architecture: ensemble-score edge function runs onnxruntime-web (WASM/Deno)
// — no native binaries, no Python runtime needed in this Node process.
//
// AUC: 0.9468 vs XGBoost v14.0 baseline 0.7834
// Interface: predictEnsemble(x, { get }) — drop-in for old stub.

const MODEL_VERSION = "v4.0-20260802-015242";
const EDGE_FN_URL = "https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/ensemble-score";

// Service-role key — loaded once, never exposed to customers.
// Injected via SUPABASE_SERVICE_KEY env var on Vercel (already set as secret).
function getServiceKey() {
  const key = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) throw new Error("SUPABASE_SERVICE_KEY not set — cannot call ensemble-score");
  return key;
}

// x: 13-float feature array in features_used order (feature-vector.js contract)
// Returns same shape as old predictEnsemble — composer.js unchanged.
export async function predictEnsemble(x, { get }) {
  const serviceKey = getServiceKey();

  const resp = await fetch(EDGE_FN_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${serviceKey}`,
    },
    body: JSON.stringify({ features: Array.from(x) }),
  });

  if (!resp.ok) {
    const err = await resp.text().catch(() => resp.statusText);
    throw new Error(`ensemble-score returned ${resp.status}: ${err.slice(0, 200)}`);
  }

  const result = await resp.json();

  if (result.error) {
    throw new Error(`ensemble-score error: ${result.error}`);
  }

  return {
    model_version:                   result.model_version,
    model_family:                    "stacked_ensemble_xgb_lgbm_catboost_rf_meta",
    ensemble_auc:                    result.auc,
    probability_third_party_purchase: Number(result.probability.toFixed(4)),
    ensemble:                        true,
    method:                          "v4_onnx_edge_function",
    base_learners: {
      xgb_prob:  Number(result.xgb_prob.toFixed(4)),
      lgbm_prob: Number(result.lgbm_prob.toFixed(4)),
      catb_prob: Number(result.catb_prob.toFixed(4)),
    },
    caveat: "V4 stacked ensemble — independent ONNX inference (XGBoost + LightGBM + CatBoost + RF meta-learner) via Supabase Edge Function. AUC 0.9468. Trained on 5,118 FL auction outcomes (2026-08-02).",
  };
}
