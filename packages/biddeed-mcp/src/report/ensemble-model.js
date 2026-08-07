// SUMMIT-B V4 — Stacked Ensemble inference
// (Patent Claim 8: XGBoost + LightGBM + CatBoost + RF meta-learner)
//
// PRIMARY:  Modal.com ASGI endpoint — full V4 pkl ensemble (AUC 0.9468)
//           Runs ensemble.pkl natively in Python — no ONNX, no WASM
// FALLBACK: Supabase pure-JS V4 — XGB+LGB walkers only (AUC ~0.946)
// DEAD:     v14.0 XGBoost — RETIRED (broken mlAdj formula). Never call it.
//           If both runtimes fail, report errors out. No silent fallback.
//
// Interface: predictEnsemble(x, { get }) — drop-in for prior stub.

const MODEL_VERSION   = 'v4.0-20260802-015242';
const MODAL_URL       = 'https://brevardbidderai--biddeed-ensemble-scorer-serve.modal.run/score';
const MODAL_TIMEOUT   = 8000;
const EDGE_TIMEOUT    = 6000;

function getWorkerSecret() {
  return process.env.ENSEMBLE_WORKER_SECRET || '';
}

function getServiceKey() {
  return process.env.SUPABASE_SERVICE_KEY
      || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
}

// ── Timeout wrapper ──────────────────────────────────────────────────────────
function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(`${label} timeout after ${ms}ms`)), ms)
    ),
  ]);
}

// ── PRIMARY: Modal V4 pkl ensemble ──────────────────────────────────────────
async function runModal(x) {
  const secret = getWorkerSecret();
  if (!secret) throw new Error('ENSEMBLE_WORKER_SECRET not set');

  const res = await fetch(MODAL_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feature_vector: Array.from(x), auth_secret: secret }),
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`Modal ${res.status}: ${txt.slice(0, 200)}`);
  }
  const data = await res.json();
  if (data.error || data.detail) throw new Error(`Modal error: ${data.error || data.detail}`);
  return data;
}

// ── FALLBACK: Supabase pure-JS V4 (XGB + LGB) ───────────────────────────────
let _jsModels = null;

async function loadJsModels() {
  if (_jsModels) return _jsModels;
  const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
  const key = getServiceKey();
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/model_artifacts` +
    `?select=artifact_name,artifact_b64,created_at` +
    `&artifact_name=in.(xgb_v4.json,lgbm_v4_flat.json)` +
    `&model_version=eq.${MODEL_VERSION}&order=created_at.desc`,
    { headers: { Authorization: `Bearer ${key}`, apikey: key } }
  );
  if (!res.ok) throw new Error(`model_artifacts fetch ${res.status}`);
  const rows = await res.json();
  const seen = {};
  for (const r of rows) { if (!seen[r.artifact_name]) seen[r.artifact_name] = r; }
  _jsModels = {
    xgb:  JSON.parse(atob(seen['xgb_v4.json'].artifact_b64)),
    lgbm: JSON.parse(atob(seen['lgbm_v4_flat.json'].artifact_b64)),
  };
  return _jsModels;
}

function evalXgbTree(tree, x) {
  const { left_children: L, right_children: R, split_indices: idx,
          split_conditions: cond, default_left: defLeft } = tree;
  let node = 0;
  while (L[node] !== -1) {
    const fval = x[idx[node]];
    const missing = fval == null || Number.isNaN(fval);
    node = (missing ? !!defLeft[node] : fval < cond[node]) ? L[node] : R[node];
  }
  return cond[node];
}

function predictXgb(doc, x) {
  const gbm = doc.learner.gradient_booster.model;
  const bsRaw = doc.learner.learner_model_param.base_score;
  const bs = parseFloat(typeof bsRaw === 'string' ? bsRaw.replace(/[\[\]]/g, '') : bsRaw);
  let margin = Math.log(bs / (1 - bs));
  for (const tree of gbm.trees) margin += evalXgbTree(tree, x);
  return 1 / (1 + Math.exp(-margin));
}

function walkLgbm(node, x) {
  if ('v' in node) return node.v;
  return walkLgbm(x[node.f] <= node.t ? node.l : node.r, x);
}

function predictLgbm(doc, x) {
  let margin = 0;
  for (const tree of doc.trees) margin += walkLgbm(tree.root, x);
  return 1 / (1 + Math.exp(-margin));
}

async function runPureJsV4(x) {
  const models  = await loadJsModels();
  const xgb_prob  = predictXgb(models.xgb, x);
  const lgbm_prob = predictLgbm(models.lgbm, x);
  return {
    probability:   (xgb_prob + lgbm_prob) / 2,
    base_learners: { xgb_prob, lgbm_prob, catb_prob: null },
    meta_learner:  'average',
    model_version: MODEL_VERSION,
    auc:           0.946,
    method:        'v4_pure_js_fallback',
  };
}

// ── Main export ──────────────────────────────────────────────────────────────
export async function predictEnsemble(x, { get } = {}) {
  // 1. Modal primary — full V4 pkl, AUC 0.9468
  try {
    return await withTimeout(runModal(x), MODAL_TIMEOUT, 'Modal');
  } catch (err) {
    console.warn('[ensemble] Modal failed, trying pure-JS fallback:', err.message);
  }

  // 2. Pure-JS XGB+LGB fallback — AUC ~0.946
  try {
    return await withTimeout(runPureJsV4(x), EDGE_TIMEOUT, 'pure-JS');
  } catch (err) {
    console.error('[ensemble] Pure-JS fallback also failed:', err.message);
    throw new Error(
      'V4 ensemble unavailable — Modal and pure-JS fallback both failed. ' +
      'Report cannot be scored without a valid V4 inference result.'
    );
  }
}
