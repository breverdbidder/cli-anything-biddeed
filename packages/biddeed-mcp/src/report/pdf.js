// GTM-22 S5 REPORT ENGINE — branded PDF renderer for the report JSON
// (composer.js). Navy/orange BidDeed brand, per DESIGN.md and CLAUDE.md
// brand config: navy #1E3A5F (surfaces), orange #F59E0B (accent/CTA),
// void #020617 (background); green=verified/positive $, red=risk,
// amber=pending/inferred.
import PDFDocument from 'pdfkit';

const NAVY = '#1E3A5F';
const ORANGE = '#F59E0B';
const VOID = '#020617';
const GREEN = '#16A34A';
const RED = '#DC2626';
const AMBER = '#D97706';
const WHITE = '#FFFFFF';

function verdictColor(verdict) {
  if (!verdict) return AMBER;
  if (verdict.startsWith('BID')) return verdict.includes('conditional') ? ORANGE : GREEN;
  if (verdict === 'SKIP') return RED;
  return AMBER;
}

function drawHeaderBand(doc, report) {
  doc.rect(0, 0, doc.page.width, 90).fill(NAVY);
  doc.fillColor(WHITE).fontSize(20).font('Helvetica-Bold')
    .text('BidDeed.AI — Property Intelligence Report', 40, 25);
  doc.fontSize(10).font('Helvetica')
    .text(`Case ${report.cover.case_number} · ${(report.cover.county || '').toUpperCase()} County, FL`, 40, 55);
  doc.y = 100;
}

function drawVerdictBanner(doc, report) {
  const color = verdictColor(report.cover.verdict);
  doc.rect(40, doc.y, doc.page.width - 80, 40).fill(color);
  doc.fillColor(WHITE).fontSize(16).font('Helvetica-Bold')
    .text(`${report.cover.verdict || 'SKIP'}  —  Investment Grade ${report.cover.investment_grade}`, 50, doc.y - 30);
  doc.y += 20;
}

function drawKpiStrip(doc, report) {
  const kpis = [
    ['Final Judgment', report.judgment?.judgment_amount ? `$${report.judgment.judgment_amount.toLocaleString()}` : 'Pending'],
    ['Assessed Value', report.auction_listing?.assessed_value?.display || 'Pending'],
    ['Plaintiff Max Bid', report.auction_listing?.plaintiff_max_bid?.display || 'Hidden'],
    ['BD Value Estimate', report.value_estimate ? `$${report.value_estimate.midpoint.toLocaleString()}` : 'No estimate'],
  ];
  const colWidth = (doc.page.width - 80) / 4;
  doc.fontSize(9).font('Helvetica');
  kpis.forEach(([label, value], i) => {
    const x = 40 + i * colWidth;
    doc.fillColor('#666666').text(label, x, doc.y, { width: colWidth - 10 });
    doc.fillColor(NAVY).font('Helvetica-Bold').fontSize(12).text(value, x, doc.y + 12, { width: colWidth - 10 });
    doc.font('Helvetica').fontSize(9);
  });
  doc.y += 40;
}

function drawSectionBand(doc, number, title, band = NAVY) {
  if (doc.y > doc.page.height - 100) doc.addPage();
  doc.rect(40, doc.y, doc.page.width - 80, 22).fill(band);
  doc.fillColor(WHITE).fontSize(11).font('Helvetica-Bold')
    .text(`§${number}  ${title}`, 48, doc.y - 17);
  doc.y += 10;
  doc.fillColor('#000000').font('Helvetica').fontSize(9);
}

function drawFlagBoxes(doc, flags = []) {
  for (const flag of flags) {
    const color = flag.severity === 'risk' ? RED : flag.severity === 'pending' ? AMBER : GREEN;
    if (doc.y > doc.page.height - 60) doc.addPage();
    doc.rect(40, doc.y, doc.page.width - 80, 18).fillAndStroke('#FFFFFF', color);
    doc.fillColor(color).fontSize(8).font('Helvetica-Bold').text(flag.code, 46, doc.y - 15, { continued: true });
    doc.fillColor('#000000').font('Helvetica').text(`  ${flag.text}`, { width: doc.page.width - 140 });
    doc.y += 4;
  }
}

function drawText(doc, text) {
  if (doc.y > doc.page.height - 60) doc.addPage();
  doc.fillColor('#000000').fontSize(9).font('Helvetica').text(String(text), 40, doc.y, { width: doc.page.width - 80 });
  doc.y += 6;
}

// Renders the full branded PDF from a composer.js report object. Returns a
// Buffer (the MCP artifact) — the caller attaches it alongside the JSON.
export function renderReportPdf(report) {
  const doc = new PDFDocument({ size: 'LETTER', margin: 0 });
  const chunks = [];
  doc.on('data', c => chunks.push(c));
  const done = new Promise(resolve => doc.on('end', () => resolve(Buffer.concat(chunks))));

  drawHeaderBand(doc, report);
  drawVerdictBanner(doc, report);
  drawKpiStrip(doc, report);

  drawSectionBand(doc, 1, 'Auction Listing');
  drawText(doc, `Plaintiff: ${report.auction_listing?.plaintiff || 'Pending'}`);
  drawText(doc, `Judgment Amount: ${report.auction_listing?.judgment_amount?.display || 'Pending'} (source: ${report.auction_listing?.judgment_amount?.source || '—'})`);
  drawText(doc, `Plaintiff Max Bid: ${report.auction_listing?.plaintiff_max_bid?.display} (source: ${report.auction_listing?.plaintiff_max_bid?.source || '—'})`);

  drawSectionBand(doc, 2, 'Value Estimate');
  if (report.value_estimate) {
    drawText(doc, `Range: $${report.value_estimate.low.toLocaleString()} – $${report.value_estimate.high.toLocaleString()} (midpoint $${report.value_estimate.midpoint.toLocaleString()})`);
    for (const a of report.value_estimate.anchors) {
      drawText(doc, `  · ${a.key}: ${a.value != null ? '$' + Math.round(a.value).toLocaleString() : 'excluded'} — ${a.source}`);
    }
  } else {
    doc.fillColor(RED).font('Helvetica-Bold').fontSize(9).text(report.refusal || 'No estimate available.', 40, doc.y, { width: doc.page.width - 80 });
    doc.y += 12;
  }

  drawSectionBand(doc, 3, 'County Auction-Cleared Market Stats');
  const cs = report.county_stats;
  if (cs) {
    drawText(doc, `n(sold/assessed)=${cs.n_sold_to_assessed}, median=${cs.median_sold_to_assessed?.toFixed(3) ?? '—'}`);
    drawText(doc, `n(sold/FJ)=${cs.n_sold_to_judgment}, median=${cs.median_sold_to_judgment?.toFixed(3) ?? '—'}, p25=${cs.p25_sold_to_judgment?.toFixed(3) ?? '—'}, p75=${cs.p75_sold_to_judgment?.toFixed(3) ?? '—'}`);
    drawText(doc, `Confidence: ${cs.confidence}${cs.note ? ' — ' + cs.note : ''}`);
  }

  drawSectionBand(doc, 4, 'Property Record');
  if (report.property_record) {
    const pr = report.property_record;
    drawText(doc, `${pr.property_type} · ${pr.beds} bed / ${pr.baths} bath · ${pr.living_area_sqft} sqft · built ${pr.year_built} · ${pr.homestead_status}`);
  }

  drawSectionBand(doc, 5, 'SECTION ZW — ZoneWise.AI Land & Zoning Intelligence', ORANGE);
  const zw = report.zoning;
  if (zw?.matched) {
    drawText(doc, `Parcel ${zw.state_parcel_id} · ${zw.jurisdiction} · DOR ${zw.dor_use_code} (${zw.dor_use_meaning})`);
    drawText(doc, `Land $${zw.land_value?.toLocaleString()} / ${zw.land_sqft?.toLocaleString()} sqft ($${zw.land_psf}/sqft) · District: ${zw.zoning_district}`);
    drawText(doc, zw.verdict);
  } else {
    doc.fillColor(RED).text(zw?.verdict || 'ZoneWise unavailable.', 40, doc.y, { width: doc.page.width - 80 });
    doc.y += 12;
  }

  drawSectionBand(doc, 6, 'CMA — Comparable Sales');
  if (report.cma?.n) {
    drawText(doc, `${report.cma.n} comps · median $${report.cma.median_sale_price?.toLocaleString()} · dispersion ${report.cma.dispersion_flag}`);
  } else {
    drawText(doc, report.cma?.note || 'No comps available.');
  }

  drawSectionBand(doc, 7, 'Red Flags & Risk Factors');
  drawFlagBoxes(doc, report.red_flags);

  drawSectionBand(doc, 8, 'Report Composition (Title Tiers)');
  if (report.composition) {
    for (const [key, val] of Object.entries(report.composition)) {
      drawText(doc, `${key}: ${val.status}`);
    }
  }

  doc.rect(40, doc.page.height - 380, doc.page.width - 80, 30).fill(ORANGE);
  doc.fillColor(WHITE).fontSize(9).font('Helvetica-Bold')
    .text('Why this beats the HouseCanary MCP report: land/zoning pairing + county-specific clearance priors, not a generic AVM.', 48, doc.page.height - 372, { width: doc.page.width - 96 });

  drawSectionBand(doc, 17, 'Provenance & Methodology');
  if (report.provenance) {
    drawText(doc, report.provenance.model_disclosure);
    drawText(doc, report.provenance.certification_disclosure);
  }

  doc.fontSize(7).fillColor('#888888')
    .text('BidDeed.AI / Everest Capital USA — decision-support intelligence, not legal or investment advice. Gold Standard certified data only.', 40, doc.page.height - 30, { width: doc.page.width - 80 });

  doc.end();
  return done;
}
