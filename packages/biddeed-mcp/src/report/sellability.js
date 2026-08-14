// packages/biddeed-mcp/src/report/sellability.js
//
// Sellability render-gate for the $25 predict_auction_outcome report.
// Agreed Aug 7 2026 (S5_REPORT_INTEGRITY_SPEC.md, never actually implemented
// until now — Aug 14 2026, built after a customer-facing bug audit found a
// live report with a max bid ~12x the actual clearing range). This is the
// mechanism that makes "we cannot send bad reports anymore" literally true:
// it runs on EVERY report before the tool handler returns, and a failing
// report never reaches the customer or gets billed.
//
// Philosophy match: same as composer.js's own honesty rules — refuse rather
// than fabricate or silently ship something wrong. A blocked report throws;
// it is never returned with a caveat bolted on.

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

// checkSellability(report) -> { sellable: boolean, reasons: string[] }
//
// Gates, per the Aug 7 agreed spec:
//   1. No NaN/Infinity anywhere in the report (incl. rendered "$NaN" strings)
//   2. Shapira Max Bid must fall within [clearing_band.low, clearing_band.high * 1.25]
//      when a clearing band exists (this is the exact defect class found live:
//      max bid derived from assessed value instead of the clearing/market model)
//   3. equity_at_entry_bid / equity_at_ceiling must not be null when their
//      inputs (market_band.midpoint, entry_bid, ceiling) are all present —
//      a null result there means a silent computation failure, not a
//      legitimately unknown value
//   4. cert-over-pending: the cover must never claim a verdict of BID/REVIEW
//      while composition.auction_intel or composition.deal_score show
//      anything other than 'delivered' for a locatable subject
export function checkSellability(report) {
  const reasons = [];

  // Unlocatable/SKIP path is a valid, intentional refusal shape — nothing
  // to gate, it already refuses correctly by design.
  if (!report?.cover || report.cover.locatable === false) {
    return { sellable: true, reasons: [] };
  }

  // 1. NaN / Infinity / literal "NaN" anywhere
  const badNumbers = [];
  findBadNumbers(report, '', badNumbers);
  if (badNumbers.length) {
    reasons.push(...badNumbers.map((b) => `bad numeric value: ${b}`));
  }

  // 2. Max bid vs clearing band sanity
  const ceilingVal = report.cover.shapira_max_bid?.value;
  const clearing = report.value_estimate?.clearing_band;
  if (ceilingVal != null && clearing?.low != null && clearing?.high != null) {
    const upperBound = clearing.high * 1.25;
    if (ceilingVal < clearing.low * 0.5 || ceilingVal > upperBound) {
      reasons.push(
        `shapira_max_bid ${ceilingVal} is outside sane range vs clearing_band [${clearing.low}, ${clearing.high}] (upper tolerance ${Math.round(upperBound)}) — likely derived from the wrong anchor`
      );
    }
  }

  // 3. Equity fields must compute when inputs are present
  const marketMid = report.value_estimate?.market_band?.midpoint;
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

  return { sellable: reasons.length === 0, reasons };
}
