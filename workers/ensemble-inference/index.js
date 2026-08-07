/**
 * ensemble-inference — Cloudflare Worker v2
 * 
 * SUMMIT-B V4 Stacked Ensemble Inference
 * Primary inference runtime for BidDeed.AI predict_auction_outcome (S5)
 * 
 * Fix v2: ort.env.wasm.wasmPaths set to jsDelivr CDN before session creation.
 * The CF Worker bundler doesn't co-locate the ort WASM binary, so we load it
 * from CDN at cold start. This is the standard pattern for CF Workers + ONNX.
 */

import * as ort from 'onnxruntime-web';

const MODEL_VERSION = 'v4.0-20260802-015242';
const ORT_VERSION   = '1.18.0';
// jsDelivr CDN for onnxruntime-web WASM — served via CF edge, effectively free latency
const WASM_CDN = `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ORT_VERSION}/dist/`;

let sessions   = null;
let loadError  = null;
let loadPromise = null;

function initOrt() {
  ort.env.wasm.wasmPaths = WASM_CDN;
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.simd = false; // disable SIMD — CF Workers WASM has limited SIMD support
}

async function loadSessions(env) {
  if (sessions) return sessions;
  if (loadError) throw loadError;
  if (loadPromise) return loadPromise;

  loadPromise = (async () => {
    initOrt();

    const SUPABASE_URL = env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
    const artifacts = ['xgb_base.onnx', 'lgbm_base.onnx', 'catb_base.onnx', 'rf_meta.onnx'];
    const keys      = ['xgb',           'lgbm',            'catb',            'rf'];

    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/model_artifacts` +
      `?select=artifact_name,artifact_b64` +
      `&artifact_name=in.(${artifacts.map(n => `"${n}"`).join(',')})` +
      `&model_version=eq.${MODEL_VERSION}` +
      `&order=created_at.desc`,
      {
        headers: {
          Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
          apikey: env.SUPABASE_SERVICE_KEY,
        },
      }
    );
    if (!res.ok) throw new Error(`Supabase fetch failed: ${res.status}`);

    const rows = await res.json();
    const seen = {};
    for (const r of rows) {
      if (!seen[r.artifact_name]) seen[r.artifact_name] = r;
    }

    const result = {};
    for (let i = 0; i < artifacts.length; i++) {
      const row = seen[artifacts[i]];
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

async function runEnsemble(sess, featureVector) {
  const x = Float32Array.from(featureVector);
  const inputTensor = new ort.Tensor('float32', x, [1, x.length]);

  // Run all 3 base learners in parallel
  const [xgbOut, lgbmOut, catbOut] = await Promise.all([
    sess.xgb.run({ float_input: inputTensor }),
    sess.lgbm.run({ float_input: inputTensor }),
    sess.catb.run({ float_input: inputTensor }),
  ]);

  const xgb_prob  = extractProb(xgbOut);
  const lgbm_prob = extractProb(lgbmOut);
  const catb_prob = extractProb(catbOut);

  // RF meta-learner input: [xgb_prob, lgbm_prob, catb_prob]
  const metaInput = new ort.Tensor('float32',
    Float32Array.from([xgb_prob, lgbm_prob, catb_prob]), [1, 3]);
  const rfOut = await sess.rf.run({ float_input: metaInput });
  const ensemble_prob = extractProb(rfOut);

  return { ensemble_prob, xgb_prob, lgbm_prob, catb_prob };
}

function extractProb(output) {
  // Try output_probability (classifiers) then output_label (regressors)
  const keys = Object.keys(output);
  const probKey = keys.find(k => k.includes('probab')) || 
                  keys.find(k => k.includes('label')) ||
                  keys[0];
  const val = output[probKey];
  if (!val) return 0;
  const data = val.data;
  if (typeof data[0] === 'object') return Number(data[0][1] ?? data[0][0]);
  // Regressor single float OR classifier [p0, p1]
  return Number(data.length === 1 ? data[0] : data[1] ?? data[0]);
}

function checkAuth(request, env) {
  const auth = (request.headers.get('Authorization') || '').replace('Bearer ', '').trim();
  return auth === env.WORKER_AUTH_SECRET;
}

function base64ToUint8Array(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === '/health') {
      return json({
        status: 'ok',
        model_version: MODEL_VERSION,
        sessions_loaded: !!sessions,
        wasm_cdn: WASM_CDN,
      });
    }

    if (url.pathname !== '/score') return json({ error: 'Not found' }, 404);
    if (request.method !== 'POST') return json({ error: 'POST required' }, 405);
    if (!checkAuth(request, env)) return json({ error: 'Unauthorized' }, 401);

    let body;
    try { body = await request.json(); }
    catch { return json({ error: 'Invalid JSON' }, 400); }

    const { feature_vector } = body;
    if (!Array.isArray(feature_vector) || feature_vector.length !== 13) {
      return json({ error: 'feature_vector must be 13 floats' }, 400);
    }

    try {
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
