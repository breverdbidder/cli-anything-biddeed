// SUMMIT-B V4 — Stacked Ensemble inference
// (Patent Claim 8: XGBoost + LightGBM + CatBoost + RF meta-learner)
//
// PRIMARY:    CF Worker ensemble-inference (ONNX WASM, full 4-model, AUC 0.9468)
// FALLBACK:   Supabase Edge pure-JS (XGB+LGB V4 walkers, AUC ~0.946, no CatBoost)
// DEAD:       v14.0 XGBoost — RETIRED. Never call it. It had a broken mlAdj
//             formula that crushed ceilings to ~$33K. If both runtimes above
//             are unreachable, the report returns an error — no silent fallback
//             to a broken model.
//
// Interface: predictEnsemble(x, { get }) — drop-in for prior stub.
// x = Float32Array or plain array of 13 floats (feature_vector order in feature-vector.js)

import { storageGet } from '../supabase.js';

const MODEL_VERSION     = 'v4.0-20260802-015242';
const CF_WORKER_URL     = 'https://ensemble-inference.breverdbidder.workers.dev/score';
const EDGE_FN_URL       = 'https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/ensemble-score';
const CF_TIMEOUT_MS     = 4000;
const EDGE_TIMEOUT_MS   = 6000;

// ── Auth helpers ────────────────────────────────────────────────────────────
function getWorkerSecret() {
  return process.env.ENSEMBLE_WORKER_SECRET || '';
}

function getServiceKey() {
  return process.env.SUPABASE_SERVICE_KEY
      || process.env.SUPABASE_SERVICE_ROLE_KEY
      || '';
}

// ── Pure-JS V4 walkers (Supabase Edge fallback) ─────────────────────────────
// Artifacts: xgb_v4.json + lgbm_v4_flat.json loaded from model_artifacts table.
// CatBoost omitted — walker broken, Option C (CF Worker) is the fix.
// XGB+LGB averaged directly; RF meta skipped (needs catb slot).

let jsModels = null;
let jsModelError = null;

async function loadJsModels(get) {
  if (jsModels) return jsModels;
  if (jsModelError) throw jsModelError;

  try {
    const SUPABASE_URL = process.env.SUPABASE_URL
      || 'https://mocerqjnksmhcjzxrewo.supabase.co';
    const key = getServiceKey();

    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/model_artifacts` +
      `?select=artifact_name,artifact_b64,created_at` +
      `&artifact_name=in.(xgb_v4.json,lgbm_v4_flat.json)` +
      `&model_version=eq.${MODEL_VERSION}` +
      `&order=created_at.desc`,
      { headers: { Authorization: `Bearer ${key}`, apikey: key } }
    );
    if (!res.ok) throw new Error(`model_artifacts fetch ${res.status}`);

    const rows = await res.json();
    const seen = {};
    for (const r of rows) {
      if (!seen[r.artifact_name]) seen[r.artifact_name] = r;
    }

    const xgbJson  = JSON.parse(atob(seen['xgb_v4.json'].artifact_b64));
    const lgbmJson = JSON.parse(atob(seen['lgbm_v4_flat.json'].artifact_b64));

    jsModels = { xgb: xgbJson, lgbm: lgbmJson };
    return jsModels;
  } catch (err) {
    jsModelError = err;
    throw err;
  }
}

// XGBoost pure-JS walker
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
  // base_score stored as string '[0.96...]' in XGBoost JSON dump
  const bs = parseFloat(
    typeof bsRaw === 'string' ? bsRaw.replace(/[\[\]]/g, '') : bsRaw
  );
  let margin = Math.log(bs / (1 - bs));
  for (const tree of gbm.trees) margin += evalXgbTree(tree, x);
  return 1 / (1 + Math.exp(-margin));
}

// LightGBM pure-JS walker
function walkLgbm(node, x) {
  if ('v' in node) return node.v;
  return walkLgbm(x[node.f] <= node.t ? node.l : node.r, x);
}

function predictLgbm(doc, x) {
  let margin = 0;
  for (const tree of doc.trees) margin += walkLgbm(tree.root, x);
  return 1 / (1 + Math.exp(-margin));
}

async function runPureJsV4(x, get) {
  const models = await loadJsModels(get);
  const xgb_prob  = predictXgb(models.xgb, x);
  const lgbm_prob = predictLgbm(models.lgbm, x);
  const probability = (xgb_prob + lgbm_prob) / 2;
  return {
    probability,
    base_learners: { xgb_prob, lgbm_prob, catb_prob: null },
    meta_learner: 'average',
    model_version: MODEL_VERSION,
    auc: 0.946,
    method: 'v4_pure_js_edge',
  };
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

// ── Primary: CF Worker ONNX ─────────────────────────────────────────────────
async function runCfWorker(x) {
  const secret = getWorkerSecret();
  if (!secret) throw new Error('ENSEMBLE_WORKER_SECRET not set');

  const res = await fetch(CF_WORKER_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${secret}`,
    },
    body: JSON.stringify({ feature_vector: Array.from(x) }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`CF Worker ${res.status}: ${text.slice(0, 200)}`);
  }

  const data = await res.json();
  if (data.error) throw new Error(`CF Worker error: ${data.error}`);
  return data;
}

// ── Main export ──────────────────────────────────────────────────────────────
export async function predictEnsemble(x, { get } = {}) {
  // 1. Try CF Worker (primary — full V4 ONNX, AUC 0.9468)
  try {
    const result = await withTimeout(runCfWorker(x), CF_TIMEOUT_MS, 'CF Worker');
    return result;
  } catch (cfErr) {
    console.warn('[ensemble] CF Worker failed, trying Supabase Edge fallback:', cfErr.message);
  }

  // 2. Try Supabase Edge pure-JS V4 (fallback — XGB+LGB, AUC ~0.946)
  try {
    const result = await withTimeout(runPureJsV4(x, get), EDGE_TIMEOUT_MS, 'Supabase Edge');
    return result;
  } catch (edgeErr) {
    console.error('[ensemble] Supabase Edge fallback also failed:', edgeErr.message);
    // Both runtimes down — surface the error. Do NOT fall back to v14.0.
    throw new Error(
      `V4 ensemble unavailable — CF Worker and Supabase Edge both failed. ` +
      `Report cannot be scored without a valid V4 inference result.`
    );
  }
}
