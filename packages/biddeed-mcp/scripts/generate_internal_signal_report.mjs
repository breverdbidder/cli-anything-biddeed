// INTERNAL-REVIEW SIGNAL$ Property Report generator — issue #19661, refactored
// for the consistency fix (Aug 31 2026 directive): the SIGNAL$ Property
// Report is ONE canonical report — the full biddeed.ai report, every active
// SSOT section, same titles/numbering/band colors/branding/ordering as what
// a customer sees. This script no longer maintains a second, custom 2-section
// HTML template (the #19661 version rendered only §1 + §16) — it calls the
// EXACT SAME renderer worker.js uses in production (renderS5ReportHtml),
// passing an internal-only flag, so the two paths cannot drift apart again.
//
// The only two allowed differences from a customer-facing render:
//   (a) the INTERNAL PREVIEW — NOT FOR CUSTOMER DELIVERY banner
//   (b) §16 Judgment & Encumbrance renders the REAL lien_survival.classify()
//       content + the verbatim biddeed_report_composition.disclosure_text,
//       instead of the ship-gated "Pending" message a customer sees while
//       ship_status stays 'blocked'.
// Both are opt-in via renderS5ReportHtml(report, { internal: true, ... }) —
// see the comment on that function in worker.js. Every other section renders
// through the identical code path production uses; there is no parallel
// template left to drift.
//
// Usage: node scripts/generate_internal_signal_report.mjs <case_number> [out.html]
import { get } from '../src/supabase.js';
import { buildReport } from '../src/report/composer.js';
import { renderS5ReportHtml } from '../../../src/worker.js';
import fs from 'fs';

export async function fetchAuction(caseNumber) {
  const rows = await get(`multi_county_auctions?case_number=eq.${encodeURIComponent(caseNumber)}&select=*`);
  if (!rows || !rows.length) return null;
  return rows[0];
}

// Verbatim disclosure_text straight off biddeed_report_composition — NOT the
// gated get_report_composition_gate RPC that composer.js's sectionComposition()
// uses for the customer path (that RPC's gate logic is untouched by this
// script; ship_status is never read or modified here).
export async function fetchRawGate(sectionKey) {
  const rows = await get(`biddeed_report_composition?section_key=eq.${encodeURIComponent(sectionKey)}&select=section_key,ship_status,disclosure_text`);
  return rows?.[0] || null;
}

async function main() {
  const caseNumber = process.argv[2];
  const outPath = process.argv[3];
  if (!caseNumber) {
    console.error('Usage: node generate_internal_signal_report.mjs <case_number> [out.html]');
    process.exit(1);
  }
  const auction = await fetchAuction(caseNumber);
  if (!auction) {
    console.log(JSON.stringify({ case_number: caseNumber, generated: false, reason: 'no multi_county_auctions row on file for this case_number' }));
    return;
  }
  const report = await buildReport(auction, { get });
  const rawGate = await fetchRawGate('lien_survival');

  const html = renderS5ReportHtml(report, {
    mcaId: auction.id || caseNumber,
    keyLast8: 'INTERNAL',
    internal: true,
    internalDisclosure: rawGate?.disclosure_text || null,
  });
  if (outPath) fs.writeFileSync(outPath, html);
  console.log(JSON.stringify({
    case_number: caseNumber,
    generated: true,
    out: outPath || null,
    sale_type: report.cover?.sale_type,
    lien_survival_available: !!report.lien_survival?.available,
    n_lien_items: report.lien_survival?.n_items ?? 0,
    production_ship_status: rawGate?.ship_status || 'unknown',
  }));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(err => { console.error(JSON.stringify({ error: err.message })); process.exit(1); });
}
