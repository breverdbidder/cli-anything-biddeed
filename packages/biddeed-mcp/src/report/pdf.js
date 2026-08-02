// BidDeed.AI — S5 PROPERTY INTELLIGENCE REPORT — FULL 18-SECTION SSOT PDF RENDERER
// Brand: navy #1E3A5F (surfaces) · orange #F59E0B (accent) · void #020617 (bg)
// green #16A34A (positive) · red #DC2626 (risk) · amber #D97706 (pending)
// Patent Claim 8 — SUMMIT-B V4 — August 2026

import PDFDocument from 'pdfkit';
import { DISCLAIMER_FULL } from '../disclaimer.js';

const NAVY  = '#1E3A5F';
const ORANGE = '#F59E0B';
const VOID  = '#020617';
const GREEN  = '#16A34A';
const RED    = '#DC2626';
const AMBER  = '#D97706';
const WHITE  = '#FFFFFF';
const SLATE  = '#334155';
const MUTED  = '#64748B';
const LIGHT  = '#F1F5F9';

function money(val) {
  if (val == null || val === '') return 'Pending';
  const n = typeof val === 'object' ? val.value : val;
  if (n == null) return 'Pending';
  return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function pct(val) {
  if (val == null) return 'Pending';
  return `${(Number(val) * 100).toFixed(1)}%`;
}

function verdictColor(v) {
  if (!v) return AMBER;
  if (v.startsWith('BID')) return v.includes('conditional') ? ORANGE : GREEN;
  if (v === 'SKIP' || v === 'PASS') return RED;
  return AMBER;
}

function safeStr(val, fallback = 'Pending') {
  if (val == null || val === '' || val === 'null') return fallback;
  if (typeof val === 'object' && val.display) return val.display;
  return String(val);
}

// ─── Layout helpers ────────────────────────────────────────────────────────

function band(doc, number, title, color = NAVY) {
  if (doc.y > doc.page.height - 80) doc.addPage();
  const y = doc.y;
  doc.rect(36, y, doc.page.width - 72, 24).fill(color);
  doc.fillColor(WHITE).fontSize(10).font('Helvetica-Bold')
    .text(`§${number}  ${title.toUpperCase()}`, 44, y + 7);
  doc.y = y + 30;
  doc.fillColor('#111827').font('Helvetica').fontSize(9);
}

function row(doc, label, value, highlight = false) {
  if (doc.y > doc.page.height - 40) doc.addPage();
  const y = doc.y;
  const even = highlight ? LIGHT : WHITE;
  doc.rect(36, y, doc.page.width - 72, 16).fill(even);
  doc.fillColor(MUTED).fontSize(8).font('Helvetica')
    .text(label, 44, y + 4, { width: 180 });
  doc.fillColor('#111827').fontSize(9).font('Helvetica-Bold')
    .text(safeStr(value), 230, y + 4, { width: doc.page.width - 270 });
  doc.y = y + 18;
}

function twoCol(doc, pairs) {
  const colW = (doc.page.width - 72) / 2;
  pairs.forEach(([l, v], i) => {
    const isLeft = i % 2 === 0;
    const x = isLeft ? 36 : 36 + colW;
    const y = isLeft ? doc.y : doc.y - 18;
    doc.rect(x, y, colW - 2, 16).fill(i % 4 < 2 ? LIGHT : WHITE);
    doc.fillColor(MUTED).fontSize(8).font('Helvetica').text(l, x + 8, y + 4, { width: 80 });
    doc.fillColor('#111827').fontSize(9).font('Helvetica-Bold').text(safeStr(v), x + 92, y + 4, { width: colW - 100 });
    if (!isLeft) doc.y = y + 18;
    else if (i === pairs.length - 1) doc.y = y + 18;
  });
}

function flagBox(doc, flag) {
  if (doc.y > doc.page.height - 50) doc.addPage();
  const color = flag.severity === 'risk' ? RED : flag.severity === 'pending' ? AMBER : GREEN;
  doc.rect(36, doc.y, 4, 20).fill(color);
  doc.fillColor(color).fontSize(8).font('Helvetica-Bold').text(flag.code || flag.label || 'FLAG', 46, doc.y + 3);
  doc.fillColor('#374151').font('Helvetica').text(flag.detail || '', 46, doc.y + 3, { width: doc.page.width - 82, continued: false });
  doc.y += 24;
}

function compRow(doc, comp, i) {
  if (doc.y > doc.page.height - 50) doc.addPage();
  const y = doc.y;
  doc.rect(36, y, doc.page.width - 72, 30).fill(i % 2 === 0 ? LIGHT : WHITE);
  doc.fillColor('#111827').fontSize(8).font('Helvetica-Bold')
    .text(comp.address || comp.property_address || 'Address pending', 44, y + 4, { width: 220 });
  doc.fillColor(MUTED).font('Helvetica')
    .text(`Sold: ${money(comp.sale_price || comp.tier1_sold_amount || comp.sold_amount)} · ${comp.sale_date || comp.auction_date || ''}`, 44, y + 16, { width: 220 });
  const ratio = comp.clearing_pct ? `${comp.clearing_pct}% of assessed` :
    comp.sold_pct_of_assessed ? `${Math.round(Number(comp.sold_pct_of_assessed) * 100)}% of assessed` : '';
  doc.fillColor(GREEN).font('Helvetica-Bold').text(ratio, 280, y + 10, { width: 120 });
  doc.y = y + 34;
}

// ─── Main render ────────────────────────────────────────────────────────────

export function renderReportPdf(report) {
  return new Promise((resolve, reject) => {
    const doc = new PDFDocument({ size: 'LETTER', margins: { top: 36, bottom: 36, left: 36, right: 36 }, bufferPages: true });
    const chunks = [];
    doc.on('data', c => chunks.push(c));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const cover = report.cover || {};
    const auction = report.auction_listing || {};
    const value = report.value_estimate;
    const priors = report.county_market_priors;
    const prop = report.property_record || {};
    const zoning = report.zoning || {};
    const cma = report.cma || {};
    const ml = report.context_layers?.ml_model || {};
    const judgment = report.judgment || {};
    const flags = report.red_flags || [];
    const outcome = report.auction_outcome || {};
    const comp = report.composition || {};
    const prov = report.provenance || {};

    // ── COVER BAND ──────────────────────────────────────────────────────────
    doc.rect(0, 0, doc.page.width, 100).fill(VOID);
    doc.fillColor(ORANGE).fontSize(22).font('Helvetica-Bold')
      .text('BidDeed.AI', 40, 20);
    doc.fillColor(WHITE).fontSize(13).font('Helvetica')
      .text('Shapira S5 Property Intelligence Report', 40, 50);
    doc.fillColor(MUTED).fontSize(9)
      .text(`Case ${cover.case_number || '—'} · ${(cover.county || '').toUpperCase()} County, FL · Generated ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`, 40, 72);
    doc.y = 110;

    // ── VERDICT BANNER ──────────────────────────────────────────────────────
    const vColor = verdictColor(cover.verdict);
    doc.rect(36, doc.y, doc.page.width - 72, 48).fill(vColor);
    doc.fillColor(WHITE).fontSize(20).font('Helvetica-Bold')
      .text(cover.verdict || 'PENDING', 50, doc.y - 38);
    doc.fontSize(11).font('Helvetica')
      .text(`Investment Grade: ${cover.investment_grade || '—'}   ·   Shapira Max Bid: ${money(cover.shapira_max_bid)}   ·   Opening Bid: ${money(cover.entry_bid)}`, 50, doc.y - 16);
    doc.y += 14;

    // ── §1 SUBJECT PROPERTY ─────────────────────────────────────────────────
    band(doc, 1, 'Subject Property Identification');
    row(doc, 'Property Address', cover.property_address, true);
    row(doc, 'County', `${(cover.county || '').toUpperCase()} County, Florida`);
    row(doc, 'Case Number', cover.case_number, true);
    row(doc, 'Sale Type', cover.sale_type);
    row(doc, 'Auction Date', cover.auction_date);
    row(doc, 'Auction Status', cover.auction_status);
    row(doc, 'Platform', cover.source_platform, true);
    row(doc, 'Parity Status', cover.parity_status);
    row(doc, 'Gold Standard', cover.cert_status || 'Standard');

    // ── §2 FINANCIAL SUMMARY ────────────────────────────────────────────────
    band(doc, 2, 'Financial Summary');
    twoCol(doc, [
      ['Opening Bid', money(cover.entry_bid)],
      ['Assessed Value', money(auction.assessed_value)],
      ['Final Judgment', money(judgment.judgment_amount)],
      ['Equity Gap (raw)', money(auction.assessed_value?.value != null && cover.entry_bid != null
        ? (auction.assessed_value.value || auction.assessed_value) - cover.entry_bid : null)],
      ['Bid / Judgment Ratio', judgment.bid_to_judgment_ratio ? `${judgment.bid_to_judgment_ratio}×` : 'Pending'],
      ['Prior Sale Price', money(prop.prior_sale_price)],
    ]);

    // ── §3 BD VALUE ESTIMATE ─────────────────────────────────────────────────
    band(doc, 3, 'BidDeed Value Estimate (ARV)');
    if (value && value.midpoint != null) {
      twoCol(doc, [
        ['ARV Estimate', money(value.midpoint)],
        ['Range Low', money(value.low)],
        ['Range High', money(value.high)],
        ['Confidence', value.confidence || 'Moderate'],
        ['Anchors Used', value.n_anchors || '—'],
        ['Primary Source', value.primary_source || 'County priors'],
      ]);
      if (value.anchors?.length) {
        doc.fillColor(MUTED).fontSize(8).text('Value anchors: ' + value.anchors.map(a => `${a.key} ($${Number(a.value).toLocaleString()})`).join(' · '), 44, doc.y + 2, { width: doc.page.width - 80 });
        doc.y += 14;
      }
    } else {
      row(doc, 'ARV Estimate', 'Pending — parcel not located');
    }

    // ── §4 AUCTION-CLEARED MARKET STATS ────────────────────────────────────
    band(doc, 4, 'Auction-Cleared Market Stats (Distressed CMA — Layer 1)');
    if (priors && !priors.insufficient) {
      twoCol(doc, [
        ['County', (cover.county || '').toUpperCase()],
        ['Sale Type', cover.sale_type],
        ['Outcomes Analyzed', priors.n_sold_to_judgment || priors.n || '—'],
        ['Median Sold/Judgment', priors.median_sold_to_judgment ? `${(priors.median_sold_to_judgment * 100).toFixed(1)}%` : '—'],
        ['Clearing Ratio p25', priors.p25 ? `${(priors.p25 * 100).toFixed(1)}%` : '—'],
        ['Clearing Ratio p75', priors.p75 ? `${(priors.p75 * 100).toFixed(1)}%` : '—'],
      ]);
    } else {
      row(doc, 'County Priors', 'Insufficient sample — less than 5 outcomes');
    }

    // ── §5 COMPARABLE SALES (Dual CMA) ──────────────────────────────────────
    band(doc, 5, 'Comparable Sales (Retail CMA — Layer 2)');
    const comps = Array.isArray(cma.comps) ? cma.comps : [];
    if (comps.length > 0) {
      doc.fillColor(NAVY).fontSize(8).font('Helvetica-Bold')
        .text('Source', 44, doc.y).text('Address', 120, doc.y).text('Sold', 310, doc.y).text('Ratio', 400, doc.y);
      doc.y += 14;
      comps.slice(0, 6).forEach((c, i) => compRow(doc, c, i));
    } else {
      row(doc, 'Retail Comps', cma.note || 'Pending — Zillow/Redfin enrichment required');
    }

    // ── §6 COMP STATS ────────────────────────────────────────────────────────
    band(doc, 6, 'Comp Statistics');
    if (cma.median_sale_price) {
      twoCol(doc, [
        ['Median Sale Price', money(cma.median_sale_price)],
        ['Comp Count', cma.n || '—'],
        ['Price / Sqft', cma.median_ppsf ? `$${Number(cma.median_ppsf).toFixed(0)}` : '—'],
        ['Days on Market', cma.median_dom || '—'],
        ['Sale/List Ratio', cma.sale_to_list ? `${(cma.sale_to_list * 100).toFixed(1)}%` : '—'],
        ['Comp Radius', cma.radius_miles ? `${cma.radius_miles} mi` : 'Same zip'],
      ]);
    } else {
      row(doc, 'Comp Stats', 'Pending — insufficient retail comps');
    }

    // ── §ZW ZONEWISE ────────────────────────────────────────────────────────
    band(doc, 'ZW', 'ZoneWise.AI — Land & Zoning Intelligence', ORANGE);
    if (zoning.zoning_code || zoning.zoning) {
      twoCol(doc, [
        ['Zoning Code', zoning.zoning_code || zoning.zoning],
        ['Land Use', zoning.land_use || zoning.flu || '—'],
        ['District', zoning.district || '—'],
        ['Max Height', zoning.max_height_ft ? `${zoning.max_height_ft} ft` : '—'],
        ['FAR Max', zoning.far_max || '—'],
        ['Density', zoning.density_max_units_per_acre ? `${zoning.density_max_units_per_acre} u/ac` : '—'],
        ['Front Setback', zoning.setback_front_ft ? `${zoning.setback_front_ft} ft` : '—'],
        ['Rear Setback', zoning.setback_rear_ft ? `${zoning.setback_rear_ft} ft` : '—'],
      ]);
      if (zoning.opportunity_flags?.length) {
        doc.y += 4;
        doc.fillColor(GREEN).fontSize(8).font('Helvetica-Bold').text('Opportunities: ', 44, doc.y, { continued: true });
        doc.fillColor('#111827').font('Helvetica').text(zoning.opportunity_flags.join(' · '));
        doc.y += 12;
      }
    } else {
      row(doc, 'ZoneWise', zoning.note || 'No zoning match — parcel not in ZoneWise.AI database');
    }

    // ── §7 RED FLAGS ─────────────────────────────────────────────────────────
    band(doc, 7, 'Red Flags & Risk Factors');
    if (flags.length > 0) {
      flags.forEach(f => flagBox(doc, f));
    } else {
      row(doc, 'Risk Flags', 'None identified');
    }

    // ── §8 REPORT COMPOSITION ────────────────────────────────────────────────
    band(doc, 8, 'Report Composition (Section Delivery Status)');
    const sections = [
      ['§1 Subject Property', 'delivered'],
      ['§2 Financial Summary', 'delivered'],
      ['§3 ARV Estimate', value?.midpoint != null ? 'delivered' : 'pending'],
      ['§4 Auction-Cleared Market', priors && !priors.insufficient ? 'delivered' : 'pending'],
      ['§5 Retail Comps', comps.length > 0 ? 'delivered' : 'pending'],
      ['§ZW ZoneWise Zoning', zoning.zoning_code ? 'delivered' : 'pending'],
      ['§9 Property Record', prop.living_area_sqft && prop.living_area_sqft !== 'Pending' ? 'delivered' : 'pending'],
      ['§ML ML Prediction', ml.probability_third_party_purchase != null ? 'delivered' : 'pending'],
      ['§15 Shapira Bid Card', cover.shapira_max_bid?.value != null ? 'delivered' : 'pending'],
      ['§16 Judgment Stack', judgment.judgment_amount != null ? 'delivered' : 'pending'],
      ['§17 Provenance', 'delivered'],
      ['§18 Auction Outcome', outcome.result ? 'delivered' : 'pending (post-auction)'],
      ['Lien Search', 'pending — Title Tier 1 not yet live'],
    ];
    sections.forEach(([s, status], i) => {
      const color = status === 'delivered' ? GREEN : status.startsWith('pending') ? AMBER : MUTED;
      if (doc.y > doc.page.height - 40) doc.addPage();
      const y = doc.y;
      doc.rect(36, y, doc.page.width - 72, 14).fill(i % 2 === 0 ? LIGHT : WHITE);
      doc.fillColor('#111827').fontSize(8).font('Helvetica').text(s, 44, y + 3, { width: 220 });
      doc.fillColor(color).font('Helvetica-Bold').text(status.toUpperCase(), 270, y + 3, { width: 200 });
      doc.y = y + 16;
    });

    // ── §9 PROPERTY RECORD ──────────────────────────────────────────────────
    band(doc, 9, 'Property Record');
    twoCol(doc, [
      ['Living Area', prop.living_area_sqft ? `${prop.living_area_sqft} sqft` : 'Pending'],
      ['Year Built', prop.year_built || 'Pending'],
      ['Beds', prop.beds || 'Pending'],
      ['Baths', prop.baths || 'Pending'],
      ['Lot Size', prop.lot_size_sqft ? `${Number(prop.lot_size_sqft).toLocaleString()} sqft` : 'Pending'],
      ['Building Class', prop.building_class || 'Pending'],
      ['DOR Use Code', prop.dor_use_code || 'Pending'],
      ['Homestead', prop.homestead ? 'Yes — owner-occupied' : prop.homestead === false ? 'No' : 'Pending'],
      ['Just Value', money(prop.just_value)],
      ['Land Value', money(prop.land_value)],
      ['Owner Type', prop.owner_type || 'Pending'],
      ['USPS Vacancy', prop.usps_vacancy || 'Pending'],
    ]);

    // ── §10-14 CONTEXT LAYERS ────────────────────────────────────────────────
    band(doc, '10-14', 'Context Layers — Market, Schools, Flood, Neighborhood');
    const ctx = report.context_layers || {};
    row(doc, 'Market Grade', ctx.market_grade || 'Pending', true);
    row(doc, 'Investor Activity', ctx.investor_activity || 'Pending');
    row(doc, 'School District', ctx.school_district || 'Pending', true);
    row(doc, 'School Rating', ctx.school_rating || 'Pending');
    row(doc, 'Flood Zone', ctx.flood_zone || prop.flood_zone || 'Pending', true);
    row(doc, 'SFHA Designation', ctx.sfha ? 'Yes — Special Flood Hazard Area' : ctx.sfha === false ? 'No' : 'Pending');
    row(doc, 'Median Household Income', ctx.median_income ? `$${Number(ctx.median_income).toLocaleString()}` : 'Pending', true);
    row(doc, 'Appreciation Rate', ctx.appreciation_rate ? pct(ctx.appreciation_rate) : 'Pending');

    // ── §ML SCOREwise — ML PREDICTION ───────────────────────────────────────
    band(doc, 'ML', 'ScoreWise — ML Auction Outcome Prediction (SUMMIT-B V4)');
    twoCol(doc, [
      ['Model Version', ml.model_version || 'v14.0'],
      ['Model Family', ml.model_family || 'XGBoost'],
      ['Ensemble AUC', ml.ensemble_auc ? ml.ensemble_auc.toFixed(4) : '—'],
      ['Sell Probability', ml.probability_third_party_purchase != null ? `${(ml.probability_third_party_purchase * 100).toFixed(1)}%` : 'Pending'],
      ['Confidence', ml.confidence || 'Pending'],
      ['Predicted Outcome', ml.predicted_outcome || '—'],
      ['Method', ml.method || '—'],
      ['Training Samples', ml.n_train_samples ? Number(ml.n_train_samples).toLocaleString() : '5,118'],
    ]);
    if (ml.caveat) {
      doc.fillColor(AMBER).fontSize(7).font('Helvetica').text(`⚠ ${ml.caveat}`, 44, doc.y + 2, { width: doc.page.width - 80 });
      doc.y += 16;
    }

    // ── §15 SHAPIRA BID CARD ────────────────────────────────────────────────
    band(doc, 15, 'BIDwise — Shapira Bid Card (Opinion of Price)', NAVY);
    const smb = cover.shapira_max_bid || {};
    const smbVal = typeof smb === 'object' ? smb.value : smb;
    doc.rect(36, doc.y, doc.page.width - 72, 50).fill(smbVal != null && smbVal > 0 ? '#F0FDF4' : '#FFF7ED');
    doc.fillColor(smbVal != null && smbVal > 0 ? GREEN : AMBER).fontSize(28).font('Helvetica-Bold')
      .text(money(smbVal), 50, doc.y - 40);
    doc.fillColor('#374151').fontSize(10).font('Helvetica')
      .text('SHAPIRA MAX BID', 50, doc.y - 12);
    doc.y += 16;
    if (smb.source) {
      doc.fillColor(MUTED).fontSize(7).font('Helvetica').text(`Formula: ${smb.source}`, 44, doc.y, { width: doc.page.width - 80 });
      doc.y += 12;
    }
    twoCol(doc, [
      ['Bid Floor', money(smb.bid_floor)],
      ['Bid Ceiling', money(smb.bid_ceiling)],
      ['Opening Bid', money(cover.entry_bid)],
      ['Equity at Opening', smbVal != null && cover.entry_bid != null ? money(smbVal - cover.entry_bid) : 'Pending'],
    ]);

    // ── §16 JUDGMENT & ENCUMBRANCE ──────────────────────────────────────────
    band(doc, 16, 'Judgment & Encumbrance Summary');
    twoCol(doc, [
      ['Plaintiff', judgment.plaintiff || 'Pending'],
      ['Judgment Amount', money(judgment.judgment_amount)],
      ['Bid / Judgment', judgment.bid_to_judgment_ratio ? `${judgment.bid_to_judgment_ratio}×` : 'Pending'],
      ['IRS Lien Risk', judgment.irs_lien_risk || 'Pending'],
      ['HOA Lien', judgment.hoa_lien || 'Pending'],
      ['Title Tier', comp.lien_search?.status || 'Pending'],
    ]);

    // ── §17 PROVENANCE ───────────────────────────────────────────────────────
    band(doc, 17, 'Provenance & Methodology');
    const mlDisc = prov.model_disclosure || `ML Stack: SUMMIT-B V4 Stacked Ensemble (Patent Claim 8)\n- XGBoost (AUC 0.9044) · LightGBM (AUC 0.9067) · CatBoost (AUC 0.8858)\n- RF Meta-learner · Ensemble AUC: 0.9468 · n=5,118 FL auction outcomes 2018-2026\n- is_production: ${ml.model_version || 'v4.0-20260802-015242'}`;
    doc.fillColor('#374151').fontSize(8).font('Helvetica').text(mlDisc, 44, doc.y, { width: doc.page.width - 80 });
    doc.y += (mlDisc.split('\n').length * 12) + 8;
    row(doc, 'Data Sources', prov.generated_from || 'multi_county_auctions, fl_parcels, zw_parcels, shapira_models, shapira_formula_params', true);
    row(doc, 'Report Generated', new Date().toISOString().slice(0, 19).replace('T', ' ') + ' UTC');

    // ── §18 AUCTION OUTCOME SCORECARD ───────────────────────────────────────
    band(doc, 18, 'Auction Outcome Scorecard');
    if (outcome.result) {
      twoCol(doc, [
        ['Result', outcome.result],
        ['Winning Bid', money(outcome.winning_bid)],
        ['Buyer Type', outcome.buyer_type || '—'],
        ['Prediction Accuracy', outcome.prediction_correct != null ? (outcome.prediction_correct ? '✅ Correct' : '❌ Miss') : '—'],
        ['Shapira Accuracy', outcome.shapira_accurate != null ? (outcome.shapira_accurate ? '✅ Within ceiling' : '❌ Exceeded ceiling') : '—'],
        ['Result Date', outcome.result_date || '—'],
      ]);
    } else {
      row(doc, 'Outcome', `Pending — Auction scheduled ${cover.auction_date || '—'}. This section populates automatically after the auction closes.`);
      if (ml.probability_third_party_purchase != null) {
        row(doc, 'Predicted Outcome', `${(ml.probability_third_party_purchase * 100).toFixed(1)}% probability of 3rd-party sale (${ml.predicted_outcome || '—'})`, true);
      }
    }

    // ── DISCLAIMER ───────────────────────────────────────────────────────────
    if (doc.y > doc.page.height - 80) doc.addPage();
    doc.rect(36, doc.y + 8, doc.page.width - 72, 1).fill(SLATE);
    doc.y += 16;
    doc.fillColor(MUTED).fontSize(7).font('Helvetica')
      .text(DISCLAIMER_FULL || 'Informational only — not legal, financial, or investment advice. Verify all data with county clerk and property appraiser before bidding. BidDeed.AI · Everest Capital USA · biddeed.ai/disclaimer', 36, doc.y, { width: doc.page.width - 72, align: 'center' });

    doc.end();
  });
}

// Backward compat alias
export { renderReportPdf as renderPDF };
