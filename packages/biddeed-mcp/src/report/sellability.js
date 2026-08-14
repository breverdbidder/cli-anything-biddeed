// packages/biddeed-mcp/src/report/sellability.js
//
// Sellability render-gate for the $25 predict_auction_outcome report.
// Agreed Aug 7 2026 (S5_REPORT_INTEGRITY_SPEC.md, never actually implemented
// until Aug 14 2026, built after a customer-facing bug audit found a live
// report with a max bid ~12x the actual clearing range). This is the
// mechanism that makes "we cannot send bad reports anymore" literally true:
// it runs on EVERY report before the tool handler returns, and a failing
// report never reaches the customer or gets billed.
//
// FIX (issue #19079, Aug 14 2026, same-day self-correction): the original
// version of gate #2 compared shapira_max_bid against clearing_band, on the
// assumption the two should stay close. That assumption was wrong — per
// composer.js's own documented methodology, shapira_max_bid is deliberately
// derived from market_band (retail ARV), and "THE SPREAD" between clearing
// and market band IS the investment thesis the whole report exists to
// surface. A live Hillsborough case proved this: after fixing a real CMA
// comp-matching bug, the corrected market_band came back genuinely higher
// (appreciating submarket, assessed value lagging real market value) and
// the gate wrongly flagged the resulting - correct - ceiling as a defect.
// The real, mathematically sound check is SELF-CONSISTENCY: shapira_max_bid
// must fall within its own bid_floor/bid_ceiling, which are computed from
// the SAME arv basis the ceiling itself used (see composer.js
// computeShapiraCeiling). This still catches the original real bug - that
// broken ceiling was below its own floor bound too, just computed off a
// different (wrong) arv - while no longer flagging legitimate large
// clearing-vs-market spreads as defects.

function isBadNumber(n) {
  return typeof n === 'number' && (Number.isNaN(n) || !Number.isFinite(n));
}

// Recursively walk the report for any numeric leaf that is NaN/Infinity, or
// any pre-rendered display string that leaked a literal "NaN" into it (the
// exact bug class found live on the Palm Beach report Aug 7 — Entry Bid
// rendering "$NaN").
function findBadNumbers(node, path, out) {
  if (node == null) return;
  if (typeof node === 'number') {
    if (isBadNumber(node)) out.push(`${path} = ${node}`);
    return;
  }
  if (typeof node === 'string') {
    if (/\bNaN\b/.test(node)) out.push(`${path} display string contains "NaN": "${node}"`);
    return;
  }
  if (Array.isArray(node)) {
    node.forEach((v, i) => findBadNumbers(v, `${path}[${i}]`, out));
    return;
  }
  if (typeof node === 'object') {
    for (const [k, v] of Object.entries(node)) {
      findBadNumbers(v, path ? `${path}.${k}` : k, out);
    }
  }
}

// checkSellability(report) -> { sellable: boolean, reasons: string[], notes: string[] }
//
// Gates (block sale):
//   1. No NaN/Infinity anywhere in the report (incl. rendered "$NaN" strings)
//   2. shapira_max_bid must fall within its own [bid_floor, bid_ceiling] -
//      the formula's self-declared bounds, same ARV basis as the ceiling
//      itself. A ceiling outside its own bounds means the computation
//      itself is broken (wrong anchor, wrong multiplier), not that the
//      result is merely surprising.
//   3. equity_at_entry_bid / equity_at_ceiling must not be null when their
//      inputs are all present - a null result there is a computation
//      failure, not a legitimately unknown value.
//   4. cert-over-pending: verdict must not rest on sections still Pending.
//
// Informational only (does NOT block sale, just annotated for visibility):
//   - Large spread between clearing_band and market_band. This is often the
//     real investment thesis, not a defect - see file header.
export function checkSellability(report) {
  const reasons = [];
  const notes = [];

  // Unlocatable/SKIP path is a valid, intentional refusal shape - nothing
  // to gate, it already refuses correctly by design.
  if (!report?.cover || report.cover.locatable === false) {
    return { sellable: true, reasons: [], notes: [] };
  }

  // 1. NaN / Infinity / literal "NaN" anywhere
  const badNumbers = [];
  findBadNumbers(report, '', badNumbers);
  if (badNumbers.length) {
    reasons.push(...badNumbers.map((b) => `bad numeric value: ${b}`));
  }

  // 2. Max bid self-consistency vs its OWN floor/bid_ceiling (same arv basis)
  const shapiraMaxBid = report.cover.shapira_max_bid;
  const ceilingVal = shapiraMaxBid?.value;
  const bidFloor = shapiraMaxBid?.bid_floor;
  const bidCeiling = shapiraMaxBid?.bid_ceiling;
  if (ceilingVal != null && bidFloor != null && bidCeiling != null) {
    // Small tolerance for rounding in the underlying multiplication chain.
    const tolerance = 1.02;
    if (ceilingVal < bidFloor / tolerance || ceilingVal > bidCeiling * tolerance) {
      reasons.push(
        `shapira_max_bid ${ceilingVal} falls outside its own formula bounds [bid_floor=${bidFloor}, bid_ceiling=${bidCeiling}] - the ceiling computation itself is inconsistent with the multipliers that produced it`
      );
    }
  }

  // Informational: large clearing-vs-market spread. Not a gate - per
  // composer.js's own documented methodology this is often the entire
  // investment thesis, not a defect. Logged so a human can sanity-check
  // outlier spreads without every large-equity property being blocked.
  const clearing = report.value_estimate?.clearing_band;
  const market = report.value_estimate?.market_band;
  if (clearing?.midpoint != null && market?.midpoint != null && clearing.midpoint > 0) {
    const spreadRatio = market.midpoint / clearing.midpoint;
    if (spreadRatio > 1.5 || spreadRatio < 0.67) {
      notes.push(
        `large clearing_band vs market_band spread (ratio ${spreadRatio.toFixed(2)}) - informational only, may reflect a real appreciating-submarket opportunity or an assessed-value lag, not necessarily a defect`
      );
    }
  }

  // 3. Equity fields must compute when inputs are present
  const marketMid = market?.midpoint;
  const entryBidVal = report.cover.entry_bid?.value;
  if (marketMid != null && entryBidVal != null && report.cover.equity_at_entry_bid == null) {
    reasons.push('equity_at_entry_bid is null despite market_band.midpoint and entry_bid both being present — computation failure');
  }
  if (marketMid != null && ceilingVal != null && report.cover.equity_at_ceiling == null) {
    reasons.push('equity_at_ceiling is null despite market_band.midpoint and shapira_max_bid both being present — computation failure');
  }

  // 4. Cert-over-pending: a real verdict must not rest on sections still Pending
  const verdict = report.cover.verdict || '';
  if (verdict.startsWith('BID') || verdict === 'REVIEW') {
    const comp = report.composition || {};
    if (comp.auction_intel?.status && comp.auction_intel.status !== 'delivered') {
      reasons.push(`verdict "${verdict}" rendered while composition.auction_intel is "${comp.auction_intel.status}"`);
    }
    if (comp.deal_score?.status && comp.deal_score.status !== 'delivered') {
      reasons.push(`verdict "${verdict}" rendered while composition.deal_score is "${comp.deal_score.status}"`);
    }
  }

  return { sellable: reasons.length === 0, reasons, notes };
}
