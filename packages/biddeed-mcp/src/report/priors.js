// GTM-22 S5 REPORT ENGINE — county clearance priors (read-only).
//
// Computes the county's historical sold-to-assessed and sold-to-judgment
// ratios live from multi_county_auctions, per issue #12853 §"Value estimate"
// anchor #1. Never borrows another county's priors — a thin county renders
// LOW confidence with its own (small) n disclosed, per the brief's honesty
// rule. multi_county_auctions is read-only here (protected object, SSOT §3).
import { get as defaultGet } from '../supabase.js';

const MIN_N_FOR_CONFIDENCE = 10;

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function percentile(values, p) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

// get: injected for testability (mirrors the pattern in other report modules
// so tests can substitute a synthetic corpus without mocking global.fetch).
export async function getCountyClearancePriors(county, { get = defaultGet, sinceYear = 2024, saleType = 'foreclosure' } = {}) {
  const rows = await get(
    `multi_county_auctions?county=eq.${encodeURIComponent(county.toLowerCase())}&sold_amount=gt.100&auction_date=gte.${sinceYear}-01-01&sale_type=eq.${encodeURIComponent(saleType)}&select=sold_amount,assessed_value,judgment_amount&limit=5000`
  ).catch(() => []);

  const soldToAssessed = rows.filter(r => r.assessed_value > 0).map(r => r.sold_amount / r.assessed_value);
  const soldToJudgment = rows.filter(r => r.judgment_amount > 0).map(r => r.sold_amount / r.judgment_amount);

  const n = rows.length;
  const nJudgment = soldToJudgment.length;
  // Confidence is gated on the SMALLER of the two samples used (sold/FJ is
  // usually the thinner one, since not every auction row carries a judgment
  // amount) — never claim confidence the weaker anchor doesn't support.
  const effectiveN = Math.min(n, nJudgment || n);
  const confidence = effectiveN < MIN_N_FOR_CONFIDENCE ? 'LOW' : effectiveN < 30 ? 'MEDIUM' : 'HIGH';

  return {
    county: county.toLowerCase(),
    n_sold_to_assessed: n,
    n_sold_to_judgment: nJudgment,
    median_sold_to_assessed: median(soldToAssessed),
    median_sold_to_judgment: median(soldToJudgment),
    p25_sold_to_judgment: percentile(soldToJudgment, 25),
    p75_sold_to_judgment: percentile(soldToJudgment, 75),
    confidence,
    insufficient: effectiveN < MIN_N_FOR_CONFIDENCE,
    note: effectiveN < MIN_N_FOR_CONFIDENCE
      ? `insufficient county priors (n=${effectiveN}) — not borrowing another county's priors`
      : null,
  };
}
