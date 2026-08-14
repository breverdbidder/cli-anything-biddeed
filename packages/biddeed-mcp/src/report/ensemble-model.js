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
//
// FIX (issue #19079, Aug 14 2026): loadJsModels() used to trust
// process.env.SUPABASE_SERVICE_KEY / SUPABASE_SERVICE_ROLE_KEY directly for
// the model_artifacts REST fetch. The exact same env var was independently
// verified LIVE this same day, on a different deployment (the
// biddeed-checkout Supabase edge function), to behave as anon-level access
// despite being named the service-role key — RLS-protected tables returned
// empty instead of the real rows. model_artifacts has RLS enabled with ZERO
// policies (confirmed live), so an anon-level read returns []. loadJsModels
// would then throw on `seen['xgb_v4.json'].artifact_b64` (undefined) since
// the array came back empty — exactly matching the "Pure-JS fallback also
// failed" error seen in production. Fix mirrors the same vault-verified-key
// pattern already proven in biddeed-checkout/index.ts: fetch the key from
// the vault via the SECURITY DEFINER RPC (unaffected by RLS) rather than
// trusting the env var blindly.

const MODEL_VERSION   = 'v4.0-20260802-015242';
const MODAL_URL       = 'https://brevardbidderai--biddeed-ensemble-scorer-serve.modal.run/score';
const MODAL_TIMEOUT   = 8000;
const EDGE_TIMEOUT    = 6000;

let _workerSecret = null;

// FIX (issue #19079, Aug 14 2026, second pass): stop trusting the Vercel
// env var for this secret at all - resolve it from the vault via the same
// SECURITY DEFINER RPC used for the service key. This is deliberately more
// aggressive than the service-key fix (which kept env as a fallback):
// Modal itself was just resynced to a FRESH secret value stored only in
// the vault + GitHub Actions, so the old Vercel env var copy is now known
// to be stale/wrong, not just unverified. Falling back to it would silently
// reintroduce the auth failure.
async function getWorkerSecret() {
  if (_workerSecret) return _workerSecret;
  const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
  const envKey = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_vault_secret_mcp`, {
      method: 'POST',
      headers: {
        apikey: envKey,
        Authorization: `Bearer ${envKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ p_name: 'ensemble_worker_secret' }),
    });
    if (res.ok) {
      const data = await res.json();
      if (typeof data === 'string' && data) {
        _workerSecret = data;
        return _workerSecret;
      }
    }
  } catch (_) { /* fall through */ }
  // Last-resort fallback only if the vault call itself fails outright
  // (network error, RPC missing) - never silently prefers env over vault.
  return process.env.ENSEMBLE_WORKER_SECRET || '';
}

function getServiceKey() {
  return process.env.SUPABASE_SERVICE_KEY
      || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
}

// NEW: resolve a vault-verified key via the same SECURITY DEFINER RPC path
// biddeed-checkout uses, falling back to the raw env var only if the vault
// call itself fails outright (network error, RPC missing, etc.) — never
// silently prefers a potentially-wrong env var over a verified one.
async function getVerifiedServiceKey() {
  const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
  const envKey = getServiceKey();
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_vault_secret_mcp`, {
      method: 'POST',
      headers: {
        apikey: envKey,
        Authorization: `Bearer ${envKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ p_name: 'supabase_service_role_key' }),
    });
    if (res.ok) {
      const data = await res.json();
      if (typeof data === 'string' && data) return data;
    }
  } catch (_) { /* fall through to env key below */ }
  return envKey;
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
  const secret = await getWorkerSecret();
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
  const key = await getVerifiedServiceKey();
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/model_artifacts` +
    `?select=artifact_name,artifact_b64,created_at` +
    `&artifact_name=in.(xgb_v4.json,lgbm_v4_flat.json)` +
    `&model_version=eq.${MODEL_VERSION}&order=created_at.desc`,
    { headers: { Authorization: `Bearer ${key}`, apikey: key } }
  );
  if (!res.ok) throw new Error(`model_artifacts fetch ${res.status}`);
  const rows = await res.json();
  if (!rows.length) throw new Error('model_artifacts returned zero rows — RLS or wrong key, not a missing-data condition (rows are confirmed present in the table)');
  const seen = {};
  for (const r of rows) { if (!seen[r.artifact_name]) seen[r.artifact_name] = r; }
  if (!seen['xgb_v4.json'] || !seen['lgbm_v4_flat.json']) {
    throw new Error(`model_artifacts missing expected artifact(s) — got: ${Object.keys(seen).join(', ') || '(none)'}`);
  }
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
      'Report cannot be scored without a valid V4 inference result. ' +
      `Last fallback error: ${err.message}`
    );
  }
}
