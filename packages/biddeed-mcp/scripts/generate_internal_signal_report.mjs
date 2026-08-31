// INTERNAL-REVIEW SIGNAL$ Property Report generator — issue #19661.
//
// buildReport() (composer.js) always computes the real lien_survival.classify()
// output regardless of biddeed_report_composition.ship_status — the ship-gate
// only withholds it from the CUSTOMER-facing composition.lien_survival.status
// field (see composer.js sectionComposition() comment). This script is a
// separate, additive internal rendering path: it reads that always-computed
// report.lien_survival directly and renders it in full, clearly marked
// INTERNAL PREVIEW — NOT FOR CUSTOMER DELIVERY. It does not touch ship_status,
// does not bypass sectionComposition() (that function still runs unmodified
// and still correctly reports "Pending" to any real customer path), and does
// not change any customer-facing renderer (worker.js, pdf.js customer usage).
//
// Usage: node scripts/generate_internal_signal_report.mjs <case_number> [out.html]
import { get } from '../src/supabase.js';
import { buildReport } from '../src/report/composer.js';
import fs from 'fs';

const NAVY = '#1E3A5F', ORANGE = '#F59E0B', VOID = '#020617';

function escHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function money(v) {
  if (v == null) return 'Pending';
  const n = typeof v === 'object' ? v.value : v;
  if (n == null) return typeof v === 'object' && v.display ? v.display : 'Pending';
  return `$${Number(n).toLocaleString()}`;
}

export async function fetchAuction(caseNumber) {
  const rows = await get(`multi_county_auctions?case_number=eq.${encodeURIComponent(caseNumber)}&select=*`);
  if (!rows || !rows.length) return null;
  return rows[0];
}

// Verbatim disclosure_text + ship_status straight off biddeed_report_composition
// — NOT the gated get_report_composition_gate RPC that composer.js's
// sectionComposition() uses for the customer path (that RPC's gate logic is
// untouched by this script).
export async function fetchRawGate(sectionKey) {
  const rows = await get(`biddeed_report_composition?section_key=eq.${encodeURIComponent(sectionKey)}&select=section_key,ship_status,disclosure_text`);
  return rows?.[0] || null;
}

function renderLienSurvivalHtml(lienSurvival, rawGate) {
  if (!lienSurvival?.available) {
    return `<div class="pending">Pending — ${escHtml(lienSurvival?.reason || 'insufficient recorded-document coverage on file for this parcel/case')}</div>`;
  }
  const items = (lienSurvival.items || []).map(item => {
    const tag = item.survives === true ? 'SURVIVES' : item.survives === false ? 'EXTINGUISHED' : 'UNRESOLVED';
    const cls = item.survives === true ? 'survives' : item.survives === false ? 'extinguished' : 'unresolved';
    const label = item.creditor && item.creditor !== 'Pending — not on file' ? `${escHtml(item.lien_type)} — ${escHtml(item.creditor)}` : escHtml(item.lien_type);
    return `<div class="lien-item ${cls}">
      <div class="lien-item-head"><span class="lien-tag ${cls}">${tag}</span> <span class="lien-label">${label}</span></div>
      <div class="lien-meta">Recorded ${escHtml(item.recording_date || 'Pending')}${item.book_page ? ' &middot; Book/Page ' + escHtml(item.book_page) : ''} &middot; Basis: ${escHtml(item.statutory_basis || '—')}</div>
      <div class="lien-statement">${escHtml(item.statement)}</div>
    </div>`;
  }).join('');
  return `
    <div class="row"><span class="row-l">Sale Type</span><span class="row-v">${escHtml(lienSurvival.sale_type)}</span></div>
    <div class="row"><span class="row-l">Statutory Basis</span><span class="row-v">${escHtml(lienSurvival.statutory_basis)}</span></div>
    <div class="row"><span class="row-l">Items on File</span><span class="row-v">${lienSurvival.n_items}</span></div>
    <div class="lien-items">${items}</div>
    ${rawGate?.disclosure_text ? `<div class="disclosure"><b>Disclosure (verbatim, biddeed_report_composition.disclosure_text):</b> ${escHtml(rawGate.disclosure_text)}</div>` : ''}
    <div class="ship-status">ship_status for this section in production: <b>${escHtml(rawGate?.ship_status || 'unknown')}</b> — unchanged by this render. This content is withheld from every customer-facing report until a human flips that flag.</div>
  `;
}

export function renderInternalPreviewHtml(report, rawGate, { caseNumber }) {
  const cover = report.cover || {};
  const auction = report.auction_listing || {};
  const generatedAt = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SIGNAL$ Property Report — INTERNAL PREVIEW — ${escHtml(caseNumber)}</title>
<style>
  body { font-family: Inter, -apple-system, sans-serif; background: ${VOID}; color: #E2EAF2; margin: 0; padding: 0 0 60px; }
  .header { background: ${VOID}; padding: 24px 40px 16px; border-bottom: 2px solid ${ORANGE}; }
  .brand { color: ${ORANGE}; font-size: 22px; font-weight: 800; }
  .title { color: #fff; font-size: 15px; margin-top: 6px; letter-spacing: 0.5px; }
  .sub { color: #94A3B8; font-size: 12px; margin-top: 4px; }
  .preview-banner { background: #DC2626; color: #fff; font-weight: 800; text-align: center; padding: 14px; font-size: 16px; letter-spacing: 1px; }
  .preview-sub { background: #7F1D1D; color: #FEE2E2; text-align: center; padding: 8px; font-size: 12px; }
  .body { max-width: 900px; margin: 24px auto; background: ${NAVY}; border-radius: 10px; padding: 24px 32px; }
  .sec { margin-bottom: 28px; }
  .sec-h { color: ${ORANGE}; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #33507a; padding-bottom: 6px; margin-bottom: 10px; }
  .row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #26426b; font-size: 13px; }
  .row-l { color: #94A3B8; }
  .row-v { color: #fff; font-weight: 600; }
  .lien-items { margin-top: 10px; }
  .lien-item { border-left: 4px solid #64748B; background: #16304f; border-radius: 4px; padding: 10px 14px; margin-bottom: 8px; }
  .lien-item.survives { border-left-color: #DC2626; }
  .lien-item.extinguished { border-left-color: #16A34A; }
  .lien-item.unresolved { border-left-color: #F59E0B; }
  .lien-tag { font-weight: 800; font-size: 11px; padding: 2px 8px; border-radius: 3px; }
  .lien-tag.survives { background: #DC2626; color: #fff; }
  .lien-tag.extinguished { background: #16A34A; color: #fff; }
  .lien-tag.unresolved { background: #F59E0B; color: #1a1a1a; }
  .lien-label { font-weight: 700; margin-left: 6px; }
  .lien-meta { color: #94A3B8; font-size: 11px; margin-top: 4px; }
  .lien-statement { color: #cbd5e1; font-size: 12px; margin-top: 6px; line-height: 1.4; }
  .disclosure { margin-top: 14px; font-size: 11px; color: #94A3B8; background: #0f2440; padding: 10px 12px; border-radius: 4px; line-height: 1.5; }
  .ship-status { margin-top: 8px; font-size: 11px; color: #FCD34D; }
  .pending { color: #94A3B8; font-style: italic; }
  .footer { max-width: 900px; margin: 0 auto; color: #64748B; font-size: 10px; padding: 12px 32px; }
</style></head>
<body>
  <div class="preview-banner">&#9888; INTERNAL PREVIEW — NOT FOR CUSTOMER DELIVERY</div>
  <div class="preview-sub">Generated for Ariel's internal review only (issue #19661). Title/lien sections carry biddeed_report_composition.ship_status=blocked in production and are not shipped to any paying customer.</div>
  <div class="header">
    <div class="brand">BidDeed.AI</div>
    <div class="title">SIGNAL$ PROPERTY REPORT</div>
    <div class="sub">${escHtml(cover.property_address || 'Address pending')} &middot; ${escHtml((cover.county||'').toUpperCase())} County, FL &middot; Case ${escHtml(cover.case_number)} &middot; Generated ${generatedAt}</div>
  </div>
  <div class="body">
    <div class="sec">
      <div class="sec-h">&sect;1 Subject &amp; Auction Identification</div>
      <div class="row"><span class="row-l">Sale Type</span><span class="row-v">${escHtml(report.lien_survival?.sale_type === 'tax_deed' ? 'Tax Deed' : 'Foreclosure')}</span></div>
      <div class="row"><span class="row-l">Auction Date</span><span class="row-v">${escHtml(auction.auction_date || 'Pending')}</span></div>
      <div class="row"><span class="row-l">Assessed Value</span><span class="row-v">${money(auction.assessed_value)}</span></div>
      <div class="row"><span class="row-l">Judgment Amount</span><span class="row-v">${money(auction.judgment_amount)}</span></div>
      <div class="row"><span class="row-l">Verdict</span><span class="row-v">${escHtml(cover.verdict || 'Pending')}</span></div>
    </div>
    <div class="sec">
      <div class="sec-h">&sect;16 Judgment &amp; Encumbrance Summary — Lien Survival (Title Tier 2)</div>
      ${renderLienSurvivalHtml(report.lien_survival, rawGate)}
    </div>
  </div>
  <div class="footer">${escHtml(report.disclaimer || '')}</div>
</body></html>`;
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

  if (!report.lien_survival?.available) {
    console.log(JSON.stringify({ case_number: caseNumber, generated: false, reason: `lien_survival not available — ${report.lien_survival?.reason || 'no data on file'}` }));
    return;
  }

  const html = renderInternalPreviewHtml(report, rawGate, { caseNumber });
  if (outPath) fs.writeFileSync(outPath, html);
  console.log(JSON.stringify({ case_number: caseNumber, generated: true, out: outPath || null, n_lien_items: report.lien_survival.n_items, sale_type: report.lien_survival.sale_type }));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(err => { console.error(JSON.stringify({ error: err.message })); process.exit(1); });
}
