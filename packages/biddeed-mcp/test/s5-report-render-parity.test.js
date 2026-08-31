// SIGNAL$ Property Report — internal-preview / production render parity.
//
// Consistency fix (Ariel, Aug 31 2026): the SIGNAL$ Property Report is ONE
// canonical report. The internal-preview path (generate_internal_signal_
// report.mjs) must reuse worker.js's renderS5ReportHtml — the exact function
// a paying customer's browser receives from /report/:mca_id — not a second,
// hand-maintained HTML template. This suite pins that: given the same report
// object, the internal render and the production render must be byte-
// identical everywhere except (a) the INTERNAL PREVIEW banner and (b) §16
// Judgment & Encumbrance (which the internal render is explicitly allowed to
// un-gate — see renderS5ReportHtml's `internal` param in worker.js).
//
// It also pins the rendered section list against DEFAULT_TEMPLATE
// (template.js) — the same fallback list pdf.js's loadTemplate() uses when
// the DB is unreachable, and today's live-SSOT snapshot below — so a future
// SSOT change is forced to touch this test instead of silently drifting.
import { test } from 'node:test';
import assert from 'node:assert/strict';

const { renderS5ReportHtml } = await import('../../../src/worker.js');
const { DEFAULT_TEMPLATE } = await import('../src/report/template.js');

// ── Fixtures — hand-built report objects (renderer-shape contract, not a
// composer.js test — composer.js's own shape is covered by
// s5-report-golden.test.js) ─────────────────────────────────────────────────
const FORECLOSURE_REPORT = {
  cover: { case_number: '16-2024-CA-000281-AXXX-MA', county: 'duval', sale_type: 'foreclosure', property_address: '1 TEST AVE, JACKSONVILLE, FL', verdict: 'BID', investment_grade: 'B', equity_at_entry_bid: 5000, equity_at_ceiling: 8000, shapira_max_bid: { value: 80000, display: '$80,000', source: 'test' }, entry_bid: { value: 40000, display: '$40,000', source: 'test' }, locatable: true },
  auction_listing: { case_number: '16-2024-CA-000281-AXXX-MA', auction_date: '2026-09-01', plaintiff: 'Test Bank', judgment_amount: { value: 100000, display: '$100,000' }, plaintiff_max_bid: { value: null, display: 'Hidden' }, assessed_value: { value: 120000, display: '$120,000' } },
  value_estimate: { midpoint: 90000, low: 80000, high: 100000, anchors: [], clearing_band: { low: 70000, midpoint: 80000, high: 90000 }, market_band: { low: 85000, midpoint: 95000, high: 105000 } },
  county_stats: { confidence: 'MEDIUM', sample_size: 20 }, transaction_history: {}, property_record: {}, context_layers: { ml_model: {} }, zoning: {}, cma: {}, cma_distressed: {}, opinion_of_price_bid_card: { entry_bid: 40000, value_midpoint: 90000 },
  judgment: { judgment_amount: 100000, opening_bid: 40000, bid_to_judgment_ratio: 0.4 },
  red_flags: [], auction_outcome: {},
  lien_survival: { available: true, sale_type: 'foreclosure', statutory_basis: 'recording priority', items: [{ lien_type: 'Second Mortgage', creditor: 'Bank B', survives: false, statement: 'Extinguished.', recording_date: '2010-01-01', book_page: '2/2', statutory_basis: 'recording priority' }], n_items: 1 },
  composition: { lien_survival: { status: 'Pending — Title Tier 2 internal-preview-only, not yet shipped to customers (ship_status=blocked)' } },
  provenance: {}, disclaimer: 'test disclaimer',
};

const TAX_DEED_REPORT = {
  cover: { case_number: '512026XX000100TDAXXX', county: 'pasco', sale_type: 'tax_deed', property_address: '2 TEST RD, DADE CITY, FL', verdict: 'REVIEW', investment_grade: 'C', equity_at_entry_bid: 1000, equity_at_ceiling: 2000, shapira_max_bid: { value: 50000, display: '$50,000', source: 'test' }, entry_bid: { value: 10000, display: '$10,000', source: 'test' }, locatable: true },
  auction_listing: { case_number: '512026XX000100TDAXXX', auction_date: '2026-08-27', assessed_value: { value: 90589, display: '$90,589' }, taxing_authority: 'Pasco County Tax Collector', unpaid_taxes: { value: 10159.72, display: '$10,160' }, outstanding_certs_total: null, cert_number: null, irs_lien_risk: 'x', hoa_lien_risk: 'y', statutory_basis: 'z' },
  value_estimate: null, county_stats: {}, transaction_history: {}, property_record: {}, context_layers: {}, zoning: {}, cma: {}, cma_distressed: {}, opinion_of_price_bid_card: {},
  judgment: { sale_type_note: 'Tax deed sale — no foreclosure judgment.', unpaid_taxes: 10159.72, irs_lien_survives: true, hoa_lien_may_survive: true, statutory_extinguishment: 'FL FS 197.552 extinguishes most state/county liens; does NOT extinguish federal liens or HOA liens under FL FS 720/718' },
  red_flags: [], auction_outcome: {},
  lien_survival: { available: true, sale_type: 'tax_deed', statutory_basis: 'Fla. Stat. §197.552', items: [{ lien_type: 'Code Enforcement/Municipal Lien', creditor: 'Test County BOCC', survives: true, statement: 'Survives.', recording_date: '2024-05-09', book_page: '11008/688', statutory_basis: '§197.552' }], n_items: 1 },
  composition: { lien_survival: { status: 'Pending — Title Tier 2 (lien survival, Fla. Stat. §197.552/§713.07) internal-preview-only, not yet shipped to customers (ship_status=blocked)' } },
  provenance: {}, disclaimer: 'test disclaimer',
};

// Strips the internal-only banner and the entire §16 section (by its
// sec-badge marker) so what's left is exactly what both render modes MUST
// agree on byte-for-byte.
function stripBannerAndSection16(html) {
  let h = html;
  const bannerIdx = h.indexOf('INTERNAL PREVIEW — NOT FOR CUSTOMER DELIVERY');
  if (bannerIdx !== -1) {
    const divStart = h.lastIndexOf('<div', bannerIdx);
    const wrapIdx = h.indexOf('<div class="wrap">');
    h = h.slice(0, divStart) + h.slice(wrapIdx);
  }
  const idx = h.indexOf('sec-badge">16<');
  const secStart = h.lastIndexOf('<details', idx);
  const secEnd = h.indexOf('</details>', idx) + '</details>'.length;
  return h.slice(0, secStart) + h.slice(secEnd);
}

test('foreclosure report: internal render is byte-identical to production outside the banner + §16', () => {
  const prod = renderS5ReportHtml(FORECLOSURE_REPORT, { mcaId: 'mca-1', keyLast8: 'ABCD1234' });
  const internal = renderS5ReportHtml(FORECLOSURE_REPORT, { mcaId: 'mca-1', keyLast8: 'ABCD1234', internal: true, internalDisclosure: 'Verbatim disclosure.' });
  assert.equal(stripBannerAndSection16(prod), stripBannerAndSection16(internal));
});

test('tax deed report: internal render is byte-identical to production outside the banner + §16', () => {
  const prod = renderS5ReportHtml(TAX_DEED_REPORT, { mcaId: 'mca-2', keyLast8: 'ABCD1234' });
  const internal = renderS5ReportHtml(TAX_DEED_REPORT, { mcaId: 'mca-2', keyLast8: 'ABCD1234', internal: true, internalDisclosure: 'Verbatim disclosure.' });
  assert.equal(stripBannerAndSection16(prod), stripBannerAndSection16(internal));
});

test('tax deed report: neither render mode ever prints "Judgment Amount" (issue #19662)', () => {
  const prod = renderS5ReportHtml(TAX_DEED_REPORT, { mcaId: 'mca-2', keyLast8: 'ABCD1234' });
  const internal = renderS5ReportHtml(TAX_DEED_REPORT, { mcaId: 'mca-2', keyLast8: 'ABCD1234', internal: true, internalDisclosure: 'Verbatim disclosure.' });
  assert.ok(!prod.includes('Judgment Amount'), 'production tax-deed render must never say Judgment Amount');
  assert.ok(!internal.includes('Judgment Amount'), 'internal tax-deed render must never say Judgment Amount');
  assert.ok(prod.includes('Opening Bid'));
  assert.ok(internal.includes('Opening Bid'));
});

test('internal=true unblocks §16 real content even while ship_status=blocked; production stays gated', () => {
  const prod = renderS5ReportHtml(FORECLOSURE_REPORT, { mcaId: 'mca-1', keyLast8: 'ABCD1234' });
  const internal = renderS5ReportHtml(FORECLOSURE_REPORT, { mcaId: 'mca-1', keyLast8: 'ABCD1234', internal: true, internalDisclosure: 'Verbatim disclosure.' });
  assert.ok(!prod.includes('EXTINGUISHED'), 'production must render the ship-gated Pending message, not the real classification');
  assert.match(prod, /internal-preview-only/);
  assert.ok(internal.includes('EXTINGUISHED'), 'internal=true must surface the real classify() output regardless of ship_status');
  assert.ok(internal.includes('Verbatim disclosure.'));
  assert.ok(internal.includes('INTERNAL PREVIEW — NOT FOR CUSTOMER DELIVERY'));
  assert.ok(!prod.includes('INTERNAL PREVIEW — NOT FOR CUSTOMER DELIVERY'), 'production must never carry the internal banner');
});

// ── Section-list parity vs the SSOT fallback (template.js DEFAULT_TEMPLATE)
// and today's live public.s5_report_sections/v_s5_report_template snapshot
// (captured 2026-08-31, active rows, sort_order asc):
//   subject_identification(10) value_estimate(20) market_and_comps(30)
//   transaction_history(40) property_record(50) context_layers(60)
//   shapira_ml(70) rehab_estimate(75) zonewise(80) bid_card(90)
//   judgment_encumbrance(100) provenance(110) auction_outcome(120)
//
// KNOWN, DISCLOSED GAP: rehab_estimate (sort_order 75) is `is_active=true`
// in the live SSOT but has ZERO implementation anywhere in the render
// pipeline — composer.js's buildReport() never populates a `report.rehab`
// field, pdf.js's SECTION_RENDERERS has no `rehab_estimate` entry (its
// template loop falls through to a literal "No renderer registered for
// section_key 'rehab_estimate'" row when connected to the live DB — see
// pdf.js line ~570), and renderS5ReportHtml in worker.js (hardcoded section
// list, does not read the template at all) omits it entirely and silently.
// This predates this change; building the actual Rehab Cost Estimate section
// (3 scope bands, line-item table, amber carry-cost callout per the SSOT
// notes) is a real feature with no spec/data source wired up here and is
// out of scope for a report-rendering consistency fix — fabricating content
// for it would violate the NEVER-LIE/honesty rules this codebase runs under.
// Tracked as a follow-up issue rather than silently swept under the rug —
// see issue #19664.
const LIVE_SSOT_ACTIVE_SECTION_KEYS = [
  'subject_identification', 'value_estimate', 'market_and_comps',
  'transaction_history', 'property_record', 'context_layers', 'shapira_ml',
  'rehab_estimate', 'zonewise', 'bid_card', 'judgment_encumbrance',
  'provenance', 'auction_outcome',
];
const KNOWN_UNIMPLEMENTED_SECTIONS = ['rehab_estimate'];

test('DEFAULT_TEMPLATE (renderer fallback) matches the live SSOT active section set exactly, minus the one documented, tracked gap', () => {
  const implemented = LIVE_SSOT_ACTIVE_SECTION_KEYS.filter(k => !KNOWN_UNIMPLEMENTED_SECTIONS.includes(k));
  assert.deepEqual(DEFAULT_TEMPLATE.map(s => s.section_key), implemented,
    'template.js DEFAULT_TEMPLATE must mirror s5_report_sections exactly (see its own header comment) — if this fails, either the SSOT changed (update DEFAULT_TEMPLATE + this snapshot) or a section silently dropped out of sync');
});

// worker.js's badges are hardcoded literal strings, independent of
// template.js's section_label formatting (e.g. '01' vs DEFAULT_TEMPLATE's
// '1', en-dash '02–03' vs DEFAULT_TEMPLATE's ASCII-hyphen '2-3') — a
// pre-existing, cosmetic label-format drift between the two, out of scope
// here. This asserts the SET AND ORDER of sections (by section_key), not
// the literal label text.
const WORKER_BADGE_TO_SECTION_KEY = {
  '01': 'subject_identification', '02–03': 'value_estimate', '04–07': 'market_and_comps',
  '08': 'transaction_history', '09–10': 'property_record', '11–14': 'context_layers',
  'ML': 'shapira_ml', 'ZW': 'zonewise', '15': 'bid_card', '16': 'judgment_encumbrance',
  '17': 'provenance', '18': 'auction_outcome',
};

test('renderS5ReportHtml renders exactly the DEFAULT_TEMPLATE sections, in sort_order, for a locatable subject', () => {
  const html = renderS5ReportHtml(FORECLOSURE_REPORT, { mcaId: 'mca-1', keyLast8: 'ABCD1234' });
  const badges = [...html.matchAll(/class="sec-badge[^"]*">([^<]*)</g)].map(m => m[1]);
  const renderedKeys = badges.map(b => WORKER_BADGE_TO_SECTION_KEY[b]);
  assert.ok(renderedKeys.every(Boolean), `unrecognized badge in ${JSON.stringify(badges)}`);
  const expectedKeys = DEFAULT_TEMPLATE.map(s => s.section_key);
  assert.deepEqual(renderedKeys, expectedKeys);
});
