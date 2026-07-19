// S5 Shapira Formula — $25/call, gate: pro tier + CERT REQUIRED
import { get } from '../supabase.js';

export const schemas = [
  {
    name: 'predict_auction_outcome',
    description: 'Shapira Formula heuristic outcome scoring, calibrated per Gold Standard county on historical discount/size patterns. CERT REQUIRED: county must pass BidDeed 10-letter Gold Standard. Returns: predicted outcome (sell/cancel/postpone), confidence %, max bid, and risk factors. $25/call.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        case_number: { type: 'string', description: 'Auction case number' },
        county:      { type: 'string', description: 'FL county (must be Gold Standard certified)' },
        arv:         { type: 'number', description: 'Your After Repair Value estimate (improves accuracy)' },
        strategy:    { type: 'string', enum: ['rental', 'flip', 'brrrr'], description: 'Exit strategy for bid recommendation' },
      },
      required: ['case_number', 'county'],
    },
  },
];

export async function predict_auction_outcome({ case_number, county, arv, strategy = 'flip' }) {
  // GTM-22F — the CERT_REQUIRED gate for this tool now runs centrally in
  // server.js (evaluateCertGate, before the charge decision) against the
  // canonical v_certified_counties view. This handler previously reimplemented
  // its own gate directly against gold_standard_county_status with an ad-hoc
  // 8-letter threshold and no hysteresis — a source that could disagree with
  // the certification state used everywhere else. By the time this handler
  // runs, county is guaranteed certified; certRecord below is informational
  // context for the response only, not a gate.
  const certRows = await get(
    `gold_standard_county_status?county_slug=eq.${encodeURIComponent(county.toLowerCase())}&status=eq.PASS&order=evaluated_at.desc&limit=20`
  ).catch(() => []);
  const certRecord = certRows[0] || null;

  // Fetch auction data
  const rows = await get(
    `multi_county_auctions?case_number=eq.${encodeURIComponent(case_number)}&limit=1`
  ).catch(() => []);

  if (!rows.length) {
    return { error: 'AUCTION_NOT_FOUND', case_number, county, message: 'Auction not found in database.' };
  }

  const auction = rows[0];
  const bid = auction.opening_bid || 0;
  const fj = auction.judgment_amount || 0;

  // Shapira Formula feature set
  const discount = fj > 0 ? (fj - bid) / fj : 0;
  const bidToFJ = fj > 0 ? bid / fj : 1;

  // Fetch historical outcomes for this county to calibrate
  const outcomes = await get(
    `foreclosure_outcomes?county=eq.${encodeURIComponent(county.toLowerCase())}&order=auction_date.desc&limit=500&select=outcome,winning_bid`
  ).catch(() => []);

  const totalOutcomes = outcomes.length;
  const soldToThirdParty = outcomes.filter(o => o.outcome === 'sold_to_third_party' || o.outcome === 'sold').length;
  const baseRate = totalOutcomes > 0 ? soldToThirdParty / totalOutcomes : 0.42;

  // Shapira scoring model — heuristic (discount/size/cert calibration). No XGBoost/LGBM/CatBoost
  // model call in this endpoint today; V14 XGBoost (72.2% acc / 0.7834 AUC) lives in shapira_models
  // but is not yet wired here. See docs/ARCHITECTURE.md AUDIT TRAIL.
  const discountScore = Math.min(1, discount * 2);  // high discount = more likely to sell
  const sizeScore = bid > 500000 ? 0.6 : bid < 50000 ? 1.2 : 1.0;  // sweet spot
  const countyScore = 1.1; // county is guaranteed certified at this point (central gate)

  const rawScore = baseRate * discountScore * sizeScore * countyScore;
  const sellProbability = Math.min(0.95, Math.max(0.05, rawScore));

  // Shapira max bid
  const effectiveArv = arv || (bid * 2.2);
  const shapiraMax = Math.round((effectiveArv * 0.70) - (effectiveArv * 0.15) - 10000 - Math.min(25000, effectiveArv * 0.15));

  const confidence = totalOutcomes >= 50 ? 'HIGH' : totalOutcomes >= 20 ? 'MEDIUM' : 'LOW';

  return {
    case_number,
    county,
    cert_status: 'certified',
    gold_standard: certRecord?.gold_standard,
    prediction: {
      outcome: sellProbability >= 0.5 ? 'SELL_TO_THIRD_PARTY' : 'REVERTS_TO_PLAINTIFF',
      sell_probability_pct: Math.round(sellProbability * 100),
      confidence,
      accuracy_baseline: 'Heuristic scoring, calibrated per-county on historical outcomes (not an ML model prediction)',
    },
    shapira_analysis: {
      opening_bid: bid,
      final_judgment: fj,
      bid_to_judgment_ratio: bidToFJ.toFixed(3),
      judgment_discount_pct: Math.round(discount * 100),
      shapira_max_bid: shapiraMax,
      strategy,
      arv_used: effectiveArv,
      verdict: shapiraMax >= bid
        ? `BID — Max bid $${shapiraMax.toLocaleString()} gives $${(shapiraMax - bid).toLocaleString()} cushion`
        : `PASS — Opening bid $${bid.toLocaleString()} exceeds Shapira max $${shapiraMax.toLocaleString()}`,
    },
    risk_factors: [
      bidToFJ > 0.85 ? 'HIGH_BID_TO_JUDGMENT: Competitive opening — limited profit margin' : null,
      bid < 10000 ? 'TITLE_RISK: Very low bid may indicate title/environmental issues' : null,
      !arv ? 'NO_ARV_PROVIDED: Shapira max is estimated — provide ARV for precision' : null,
    ].filter(Boolean),
    historical_context: {
      county_outcomes_analyzed: totalOutcomes,
      county_sell_rate_pct: Math.round(baseRate * 100),
    },
    billing_note: '$25 charged to your account. View billing at biddeed.ai/dashboard/billing.',
    cert_record: certRecord,
  };
}
