/**
 * ensemble-inference — Cloudflare Worker
 * 
 * SUMMIT-B V4 Stacked Ensemble Inference
 * Primary inference runtime for BidDeed.AI predict_auction_outcome (S5)
 * 
 * Architecture: XGBoost + LightGBM + CatBoost base learners
 *               → Random Forest meta-learner
 * AUC: 0.9468 (vs v14.0 baseline 0.7834)
 * Trained: 2026-08-02 on 5,118 FL auction outcomes
 * 
 * Artifacts loaded from Supabase model_artifacts at cold start.
 * Exposes POST /score — called by ensemble-model.js in the MCP server.
 * 
 * Deploy: workers/ensemble-inference/wrangler.toml
 * Secrets required (wrangler secret put):
 *   SUPABASE_URL          — https://mocerqjnksmhcjzxrewo.supabase.co
 *   SUPABASE_SERVICE_KEY  — service role JWT
 *   WORKER_AUTH_SECRET    — shared secret, must match ENSEMBLE_WORKER_SECRET on Vercel
 */

import * as ort from 'onnxruntime-web';

const MODEL_VERSION = 'v4.0-20260802-015242';

// ── Cold-start artifact cache ──────────────────────────────────────────────
let sessions = null;    // { xgb, lgbm, catb, rf }
let loadError = null;
let loadPromise = null;

async function loadSessions(env) {
  if (sessions) return sessions;
  if (loadError) throw loadError;
  if (loadPromise) return loadPromise;

  loadPromise = (async () => {
    const artifacts = ['xgb_base.onnx', 'lgbm_base.onnx', 'catb_base.onnx', 'rf_meta.onnx'];
    const keys      = ['xgb',           'lgbm',            'catb',            'rf'];

    const rows = await fetchArtifacts(env, artifacts);
    const result = {};

    for (let i = 0; i < artifacts.length; i++) {
      const row = rows.find(r => r.artifact_name === artifacts[i]);
      if (!row) throw new Error(`Missing artifact: ${artifacts[i]}`);

      const bytes = base64ToUint8Array(row.artifact_b64);
      result[keys[i]] = await ort.InferenceSession.create(bytes, {
        executionProviders: ['wasm'],
      });
    }

    sessions = result;
    return sessions;
  })();

  try {
    return await loadPromise;
  } catch (err) {
    loadError = err;
    loadPromise = null;
    throw err;
  }
}

async function fetchArtifacts(env, names) {
  const inList = names.map(n => `"${n}"`).join(',');
  const url = `${env.SUPABASE_URL}/rest/v1/model_artifacts` +
    `?select=artifact_name,artifact_b64` +
    `&artifact_name=in.(${inList})` +
    `&model_version=eq.${MODEL_VERSION}` +
    `&order=created_at.desc`;

  const res = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
      'apikey': env.SUPABASE_SERVICE_KEY,
    },
  });
  if (!res.ok) throw new Error(`Supabase fetch failed: ${res.status}`);

  const rows = await res.json();

  // Deduplicate — keep first occurrence per name (latest due to order=desc)
  const seen = new Set();
  return rows.filter(r => {
    if (seen.has(r.artifact_name)) return false;
    seen.add(r.artifact_name);
    return true;
  });
}

// ── Inference ──────────────────────────────────────────────────────────────
async function runEnsemble(sess, featureVector) {
  const x = Float32Array.from(featureVector);
  const inputTensor = new ort.Tensor('float32', x, [1, x.length]);

  // Base learners — all take the 13-float feature vector
  const [xgbOut, lgbmOut, catbOut] = await Promise.all([
    sess.xgb.run({ float_input: inputTensor }),
    sess.lgbm.run({ float_input: inputTensor }),
    sess.catb.run({ float_input: inputTensor }),
  ]);

  const xgb_prob  = extractProb(xgbOut);
  const lgbm_prob = extractProb(lgbmOut);
  const catb_prob = extractProb(catbOut);

  // RF meta-learner — input is [xgb_prob, lgbm_prob, catb_prob]
  const metaInput = new ort.Tensor('float32',
    Float32Array.from([xgb_prob, lgbm_prob, catb_prob]), [1, 3]);

  const rfOut = await sess.rf.run({ float_input: metaInput });
  const ensemble_prob = extractProb(rfOut);

  return { ensemble_prob, xgb_prob, lgbm_prob, catb_prob };
}

function extractProb(output) {
  // ONNX classifiers return output_probability as a map — pull class-1 prob
  const key = Object.keys(output).find(k =>
    k.includes('probab') || k.includes('label') || k === 'output_label'
  ) || Object.keys(output)[0];

  const val = output[key];
  if (val && val.data) {
    const data = val.data;
    // Sequence map [{0: p0, 1: p1}] or flat [p0, p1]
    if (typeof data[0] === 'object') return Number(data[0][1] ?? data[0][0]);
    // For regressors (RF) output is a single float
    return Number(data[data.length === 1 ? 0 : 1] ?? data[0]);
  }
  return Number(val);
}

// ── Auth ───────────────────────────────────────────────────────────────────
function checkAuth(request, env) {
  const auth = request.headers.get('Authorization') || '';
  const secret = auth.replace('Bearer ', '').trim();
  return secret === env.WORKER_AUTH_SECRET;
}

// ── WASM init ──────────────────────────────────────────────────────────────
// CF Workers require ort.env.wasm.wasmPaths to point to the bundled WASM.
// With wrangler --no-bundle the WASM is served from the same worker URL.
function initOrt() {
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.simd = true;
}

// ── Base64 helper ──────────────────────────────────────────────────────────
function base64ToUint8Array(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

// ── Request handler ────────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Health check — no auth required
    if (url.pathname === '/health') {
      return json({ status: 'ok', model_version: MODEL_VERSION, sessions_loaded: !!sessions });
    }

    if (url.pathname !== '/score') {
      return json({ error: 'Not found' }, 404);
    }

    if (request.method !== 'POST') {
      return json({ error: 'POST required' }, 405);
    }

    if (!checkAuth(request, env)) {
      return json({ error: 'Unauthorized' }, 401);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: 'Invalid JSON body' }, 400);
    }

    const { feature_vector } = body;
    if (!Array.isArray(feature_vector) || feature_vector.length !== 13) {
      return json({ error: 'feature_vector must be array of 13 floats' }, 400);
    }

    try {
      initOrt();
      const sess = await loadSessions(env);
      const { ensemble_prob, xgb_prob, lgbm_prob, catb_prob } = await runEnsemble(sess, feature_vector);

      return json({
        probability: ensemble_prob,
        base_learners: { xgb_prob, lgbm_prob, catb_prob },
        meta_learner: 'rf',
        model_version: MODEL_VERSION,
        auc: 0.9468,
        method: 'v4_onnx_cf_worker',
      });
    } catch (err) {
      console.error('Inference error:', err);
      return json({ error: err.message, method: 'v4_onnx_cf_worker' }, 500);
    }
  },
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
