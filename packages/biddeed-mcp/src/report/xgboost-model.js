// V4 Stacked Ensemble — ONNX inference for Node.js
//
// Architecture: XGBoost + LightGBM + CatBoost base learners
//               → Random Forest meta-learner
// AUC: 0.9468 (vs v14.0 XGBoost baseline: 0.7834)
// Trained: 2026-08-02 on 5,118 FL auction outcomes
// Artifacts: stored in model_artifacts table (artifact_b64, ONNX format)
//
// Pipeline:
//   feature_vector (13 floats)
//     → xgb_base.onnx  → xgb_prob
//     → lgbm_base.onnx → lgbm_prob
//     → catb_base.onnx → catb_prob
//     → rf_meta.onnx([xgb_prob, lgbm_prob, catb_prob]) → ensemble_prob
//
// Features (order matters — matches training pipeline):
//   judgment_amount_log1p, opening_bid_log1p, assessed_value_log1p,
//   prior_sale_price_log1p, beds_f, baths_f, sqft_f, property_age,
//   opening_to_market, judgment_to_market, is_foreclosure, is_tax_deed,
//   county_target_enc

import ort from 'onnxruntime-node';

const MODEL_VERSION = 'v4.0-20260802-015242';

export const FEATURES = [
  'judgment_amount_log1p',
  'opening_bid_log1p',
  'assessed_value_log1p',
  'prior_sale_price_log1p',
  'beds_f',
  'baths_f',
  'sqft_f',
  'property_age',
  'opening_to_market',
  'judgment_to_market',
  'is_foreclosure',
  'is_tax_deed',
  'county_target_enc',
];

// County target encoding — mean 3P probability per county from training set.
// If county not found, use global mean 0.72.
const COUNTY_TARGET_ENC = {
  hillsborough: 0.81, palm_beach: 0.79, broward: 0.78, duval: 0.76,
  brevard: 0.74, orange: 0.73, pinellas: 0.72, sarasota: 0.71,
  volusia: 0.70, manatee: 0.69, collier: 0.68, marion: 0.67,
  lee: 0.66, alachua: 0.65, st_johns: 0.74, pasco: 0.72,
  hernando: 0.70, charlotte: 0.71, putnam: 0.65, nassau: 0.68,
  indian_river: 0.69, monroe: 0.64, washington: 0.62,
};
const COUNTY_ENC_DEFAULT = 0.72;

// Process-level cache — artifacts are immutable once trained
let sessions = null;

async function loadSessions(get) {
  if (sessions) return sessions;

  const artifacts = ['xgb_base.onnx', 'lgbm_base.onnx', 'catb_base.onnx', 'rf_meta.onnx'];
  const loaded = {};

  for (const name of artifacts) {
    const rows = await get(
      `model_artifacts?model_version=eq.${MODEL_VERSION}&artifact_name=eq.${name}&select=artifact_b64&limit=1`
    ).catch(() => []);

    if (!rows.length || !rows[0].artifact_b64) {
      throw new Error(`ONNX artifact not found in model_artifacts: ${name} (version ${MODEL_VERSION})`);
    }

    const buf = Buffer.from(rows[0].artifact_b64, 'base64');
    loaded[name] = await ort.InferenceSession.create(buf);
  }

  sessions = loaded;
  return sessions;
}

// Test-only injection hook
export function _setSessionsForTest(s) { sessions = s; }
export function _resetSessionsForTest() { sessions = null; }

// Build the 13-float feature vector from auction + parcel data.
// Safe defaults for missing fields — never throws.
export function buildFeatureVector(auction, parcel, marketMidpoint) {
  const safe = (v, fallback = 0) => (v != null && isFinite(v) ? v : fallback);
  const log1p = (v) => Math.log1p(safe(v, 0));

  const assessedValue  = safe(auction.assessed_value, 0);
  const openingBid     = safe(auction.opening_bid, 0);
  const judgmentAmount = safe(auction.judgment_amount, 0);
  const priorSale      = safe(auction.prior_sale_price || parcel?.sale_prc1, 0);
  const market         = safe(marketMidpoint, assessedValue) || 1; // avoid div/0

  const currentYear    = new Date().getFullYear();
  const yearBuilt      = safe(parcel?.act_yr_blt || parcel?.year_built, currentYear - 30);
  const propertyAge    = Math.max(0, currentYear - yearBuilt);

  const isForeclosure  = auction.sale_type === 'foreclosure' ? 1 : 0;
  const isTaxDeed      = auction.sale_type === 'tax_deed' ? 1 : 0;
  const countyEnc      = COUNTY_TARGET_ENC[auction.county] ?? COUNTY_ENC_DEFAULT;

  return [
    log1p(judgmentAmount),         // judgment_amount_log1p
    log1p(openingBid),             // opening_bid_log1p
    log1p(assessedValue),          // assessed_value_log1p
    log1p(priorSale),              // prior_sale_price_log1p
    safe(parcel?.no_bdrms, 3),     // beds_f
    safe(parcel?.no_bath, 2),      // baths_f
    safe(parcel?.tot_lvg_area || parcel?.sqft, 1200), // sqft_f
    propertyAge,                   // property_age
    openingBid  / market,          // opening_to_market
    judgmentAmount / market,       // judgment_to_market
    isForeclosure,                 // is_foreclosure
    isTaxDeed,                     // is_tax_deed
    countyEnc,                     // county_target_enc
  ];
}

// Main inference function.
// Returns { probability, model_version, base_probs, caveat }
// Throws on artifact load failure — callers render "unavailable" not a fake number.
export async function predict(auction, parcel, marketMidpoint, { get }) {
  const sess = await loadSessions(get);

  const fv = buildFeatureVector(auction, parcel, marketMidpoint);
  const input = new ort.Tensor('float32', Float32Array.from(fv), [1, fv.length]);

  // Run 3 base learners in parallel
  const [xgbOut, lgbmOut, catbOut] = await Promise.all([
    sess['xgb_base.onnx'].run({ float_input: input }),
    sess['lgbm_base.onnx'].run({ float_input: input }),
    sess['catb_base.onnx'].run({ features: input }),  // CatBoost uses 'features' input name
  ]);

  const xgbProb  = xgbOut.probabilities.data[1];   // class=1 (3rd party purchase)
  const lgbmProb = lgbmOut.probabilities.data[1];
  const catbProb = catbOut.probabilities.data[1];

  // RF meta-learner takes [xgb, lgbm, catb] probs as input
  const metaInput = new ort.Tensor('float32', Float32Array.from([xgbProb, lgbmProb, catbProb]), [1, 3]);
  const rfOut = await sess['rf_meta.onnx'].run({ meta_input: metaInput });
  const ensembleProb = rfOut.output_probability.data[1];

  return {
    probability: ensembleProb,
    model_version: MODEL_VERSION,
    base_probs: { xgb: xgbProb, lgbm: lgbmProb, catb: catbProb },
    caveat: 'V4 stacked ensemble (XGBoost + LightGBM + CatBoost + RF meta-learner). AUC 0.9468. Trained on 5,118 FL auction outcomes.',
  };
}
