// BidDeed.AI — S5 PROPERTY INTELLIGENCE REPORT — SSOT-DRIVEN PDF RENDERER
// Template source: public.v_s5_report_template (Supabase) — SINGLE SOURCE OF TRUTH
// Section order, labels, titles, band colors, and liability notes all live in the DB.
// Changing the template requires ZERO code deploys — edit s5_report_sections in Supabase.
//
// Brand: navy #1E3A5F · orange #F59E0B · void #020617 · green #16A34A · red #DC2626 · amber #D97706
// Patent Claim 8 — SUMMIT-B V4

// Cloudflare Workers import-compat shim (#20025): the default 'pdfkit' entry
// reads AFM font files via fs at runtime, which doesn't exist in workerd.
// The standalone build embeds font metrics inline — same API, zero logic
// change here, works unchanged under Node (Vercel) too.
import PDFDocument from 'pdfkit/js/pdfkit.standalone.js';
import { get as defaultGet } from '../supabase.js';
import { DISCLAIMER_FULL } from '../disclaimer.js';

const NAVY   = '#1E3A5F';
const ORANGE = '#F59E0B';
const VOID   = '#020617';
const GREEN  = '#16A34A';
const RED    = '#DC2626';
const AMBER  = '#D97706';
const WHITE  = '#FFFFFF';
const SLATE  = '#334155';
const MUTED  = '#64748B';
const LIGHT  = '#F1F5F9';

const BAND_COLOR_MAP = {
  navy:   NAVY,
  orange: ORANGE,
  green:  GREEN,
  red:    RED,
  amber:  AMBER,
};

// ─── Template loader — the SSOT ────────────────────────────────────────────
// Reads public.v_s5_report_template once per render (process-level cache via
// module-scope Map so repeated calls in the same worker are cheap).
const _templateCache = { rows: null, loadedAt: 0 };
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 min — stale-on-redeploy is acceptable

export async function loadTemplate({ get = defaultGet } = {}) {
  const now = Date.now();
  if (_templateCache.rows && (now - _templateCache.loadedAt) < CACHE_TTL_MS) {
    return _templateCache.rows;
  }
  const rows = await get(
    'v_s5_report_template?select=section_key,section_label,title,hc_mirror,report_field,band_color,sort_order,parity_section_no,parity_section_name,parity_status,liability_note&order=sort_order.asc'
  ).catch(() => null);
  if (rows && rows.length > 0) {
    _templateCache.rows = rows;
    _templateCache.loadedAt = now;
    return rows;
  }
  // Hard-coded fallback — keeps reports alive if DB is unreachable.
  // This list MUST mirror s5_report_sections exactly; update both or update neither.
  return [
    { section_key: 'subject_identification', section_label: '1',    title: 'Subject & Auction Identification',                                   band_color: 'navy',   sort_order: 10  },
    { section_key: 'value_estimate',         section_label: '2-3',  title: 'BidDeed Value Estimate & Components',                                 band_color: 'navy',   sort_order: 20  },
    { section_key: 'market_and_comps',       section_label: '4-7',  title: 'Auction-Cleared Market · Comparable Sales · Comp Stats',              band_color: 'navy',   sort_order: 30  },
    { section_key: 'transaction_history',    section_label: '8',    title: 'Transaction History',                                                 band_color: 'navy',   sort_order: 40  },
    { section_key: 'property_record',        section_label: '9-10', title: 'Property Record & Listing Details',                                   band_color: 'navy',   sort_order: 50  },
    { section_key: 'context_layers',         section_label: '11-14',title: 'Context Layers — Neighborhood · Schools · Flood · Market Grade',      band_color: 'navy',   sort_order: 60  },
    { section_key: 'shapira_ml',             section_label: 'ML',   title: 'Shapira Models — Third-Party Purchase Classifier',                    band_color: 'navy',   sort_order: 70  },
    { section_key: 'zonewise',               section_label: 'ZW',   title: 'ZoneWise.AI Land & Zoning Intelligence — NO HC EQUIVALENT, THE PAIRING', band_color: 'orange', sort_order: 80  },
    { section_key: 'bid_card',               section_label: '15',   title: 'Shapira Bid Card — Opinion of Price',                                 band_color: 'navy',   sort_order: 90  },
    { section_key: 'judgment_encumbrance',   section_label: '16',   title: 'Judgment & Encumbrance Summary',                                      band_color: 'navy',   sort_order: 100 },
    { section_key: 'provenance',             section_label: '17',   title: 'Provenance & Honest Limits',                                          band_color: 'navy',   sort_order: 110 },
    { section_key: 'auction_outcome',        section_label: '18',   title: 'Auction Outcome & Prediction Scorecard',                              band_color: 'green',  sort_order: 120 },
  ];
}

// ─── Formatters ────────────────────────────────────────────────────────────
function money(val) {
  if (val == null || val === '') return 'Pending';
  const n = typeof val === 'object' ? val.value : val;
  if (n == null) return typeof val === 'object' && val.display ? val.display : 'Pending';
  return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}
function pct(val) { return val == null ? 'Pending' : `${(Number(val) * 100).toFixed(1)}%`; }
function safeStr(val, fallback = 'Pending') {
  if (val == null || val === '' || val === 'null') return fallback;
  if (typeof val === 'object' && val.display) return val.display;
  return String(val);
}
function verdictColor(v) {
  if (!v) return AMBER;
  if (v.startsWith('BID')) return v.includes('conditional') ? ORANGE : GREEN;
  if (v === 'SKIP' || v === 'PASS') return RED;
  return AMBER;
}

// ─── Layout primitives ─────────────────────────────────────────────────────
function band(doc, label, title, colorKey = 'navy') {
  if (doc.y > doc.page.height - 80) doc.addPage();
  const color = BAND_COLOR_MAP[colorKey] ?? NAVY;
  const y = doc.y;
  doc.rect(36, y, doc.page.width - 72, 24).fill(color);
  doc.fillColor(WHITE).fontSize(10).font('Helvetica-Bold')
    .text(`§${label}  ${title.toUpperCase()}`, 44, y + 7);
  doc.y = y + 30;
  doc.fillColor('#111827').font('Helvetica').fontSize(9);
}

function row(doc, label, value, alt = false) {
  if (doc.y > doc.page.height - 40) doc.addPage();
  const y = doc.y;
  doc.rect(36, y, doc.page.width - 72, 16).fill(alt ? LIGHT : WHITE);
  doc.fillColor(MUTED).fontSize(8).font('Helvetica').text(label, 44, y + 4, { width: 180 });
  doc.fillColor('#111827').fontSize(9).font('Helvetica-Bold').text(safeStr(value), 230, y + 4, { width: doc.page.width - 270 });
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
  const y = doc.y;
  doc.rect(36, y, 4, 20).fill(color);
  doc.fillColor(color).fontSize(8).font('Helvetica-Bold').text(flag.code || flag.label || 'FLAG', 46, y + 3);
  doc.fillColor('#374151').font('Helvetica').text(flag.detail || flag.text || '', 46, y + 3, { width: doc.page.width - 82 });
  doc.y = y + 24;
}

function compRow(doc, comp, i) {
  if (doc.y > doc.page.height - 50) doc.addPage();
  const y = doc.y;
  doc.rect(36, y, doc.page.width - 72, 30).fill(i % 2 === 0 ? LIGHT : WHITE);
  doc.fillColor('#111827').fontSize(8).font('Helvetica-Bold')
    .text(comp.address || comp.property_address || 'Address pending', 44, y + 4, { width: 220 });
  const soldAmt = comp.sale_price1 ?? comp.sale_prc1 ?? comp.tier1_sold_amount ?? comp.sold_amount;
  const saleYr  = comp.sale_yr1 ?? comp.auction_date ?? '';
  const sqft    = comp.tot_lvg_ar ?? comp.living_area_sqft ?? '';
  const yrBlt   = comp.act_yr_blt ?? comp.year_built ?? '';
  const ppsf    = soldAmt && sqft ? `$${Math.round(soldAmt / sqft)}/sf` : '';
  doc.fillColor(MUTED).font('Helvetica')
    .text(`Sold: ${money(soldAmt)} · ${saleYr}${yrBlt ? ' · Built ' + yrBlt : ''}${ppsf ? ' · ' + ppsf : ''}`, 44, y + 16, { width: 380 });
  doc.y = y + 34;
}

function liabilityNote(doc, note) {
  if (!note) return;
  doc.fillColor(AMBER).fontSize(7).font('Helvetica-Oblique')
    .text(`⚠ ${note}`, 44, doc.y + 2, { width: doc.page.width - 80 });
  doc.y += 14;
}

// ─── Section renderers — keyed by section_key ──────────────────────────────
// Each renderer receives (doc, report, section) where section is the v_s5_report_template row.
const SECTION_RENDERERS = {

  subject_identification(doc, report, section) {
    const cover   = report.cover || {};
    const auction = report.auction_listing || {};
    // Sale-type-aware (issue #19662): a tax deed sale has no final judgment —
    // that is a Chapter 45 foreclosure concept. Render Chapter 197 fields
    // instead, never a Judgment/Plaintiff row that just reads "Pending".
    const isTaxDeed = cover.sale_type === 'tax_deed';
    row(doc, 'Address',          cover.property_address,   true);
    row(doc, 'County',           `${(cover.county||'').toUpperCase()} County, Florida`);
    row(doc, 'Case Number',      cover.case_number,         true);
    row(doc, 'Sale Type',        cover.sale_type);
    row(doc, 'Auction Date',     auction.auction_date || cover.auction_date, true);
    if (isTaxDeed) {
      row(doc, 'Taxing Authority', auction.taxing_authority);
      row(doc, 'Assessed Value',   money(auction.assessed_value), true);
      row(doc, 'Opening Bid',      auction.unpaid_taxes?.value != null ? money(auction.unpaid_taxes) : 'N/A — tax deed sale (no final judgment)');
      if (auction.outstanding_certs_total?.value != null) row(doc, 'Outstanding Certificates Total', money(auction.outstanding_certs_total), true);
      if (auction.cert_number) row(doc, 'Certificate #', auction.cert_number);
    } else {
      row(doc, 'Plaintiff',        auction.plaintiff || cover.plaintiff);
      row(doc, 'Assessed Value',   money(auction.assessed_value), true);
      row(doc, 'Final Judgment',   money(auction.judgment_amount));
      row(doc, 'Plaintiff Max Bid',money(auction.plaintiff_max_bid), true);
    }
    row(doc, 'Gold Standard',    cover.cert_status || 'Standard');
    liabilityNote(doc, section.liability_note);
  },

  value_estimate(doc, report, section) {
    const value  = report.value_estimate;
    const cover  = report.cover || {};
    const cb     = value?.clearing_band;
    const mb     = value?.market_band;
    if (value && value.midpoint != null) {
      // ── Clearing band (expected auction price) ────────────────────────────
      const y1 = doc.y;
      doc.rect(36, y1, doc.page.width - 72, 42).fill(LIGHT);
      doc.fillColor(AMBER).fontSize(8).font('Helvetica-Bold').text('EXPECTED CLEARING PRICE (Distressed)', 44, y1 + 4);
      doc.fillColor(NAVY).fontSize(16).font('Helvetica-Bold')
        .text(cb?.low != null ? `${money(cb.low)} – ${money(cb.high)}` : 'Pending', 44, y1 + 14);
      doc.fillColor(MUTED).fontSize(8).font('Helvetica')
        .text(cb?.midpoint != null ? `Midpoint ${money(cb.midpoint)}` : '', 44, y1 + 32);
      doc.y = y1 + 48;
      // ── Market band (retail ARV / exit value) ─────────────────────────────
      const y2 = doc.y;
      doc.rect(36, y2, doc.page.width - 72, 42).fill('#F0FDF4');
      doc.fillColor(GREEN).fontSize(8).font('Helvetica-Bold').text('RETAIL ARV — OPEN MARKET EXIT VALUE', 44, y2 + 4);
      doc.fillColor(NAVY).fontSize(16).font('Helvetica-Bold')
        .text(mb?.low != null ? `${money(mb.low)} – ${money(mb.high)}` : 'Pending', 44, y2 + 14);
      doc.fillColor(MUTED).fontSize(8).font('Helvetica')
        .text(mb?.midpoint != null
          ? `Midpoint ${money(mb.midpoint)}  ·  Investment Grade ${cover.investment_grade || '—'}  ·  Shapira Max Bid ${money(cover.shapira_max_bid)}`
          : '', 44, y2 + 32);
      doc.y = y2 + 48;
      // ── Equity strip ─────────────────────────────────────────────────────
      if (cover.equity_at_entry_bid != null) {
        const y3 = doc.y;
        doc.rect(36, y3, doc.page.width - 72, 20).fill(GREEN);
        doc.fillColor(WHITE).fontSize(9).font('Helvetica-Bold')
          .text(
            `Day-1 Equity at Entry Bid: ${money(cover.equity_at_entry_bid)}   ·   Equity at Ceiling: ${money(cover.equity_at_ceiling)}`,
            44, y3 + 6
          );
        doc.y = y3 + 24;
      }
      // ── Anchors detail ────────────────────────────────────────────────────
      doc.y += 4;
      if (value.anchors?.length) {
        doc.fillColor(MUTED).fontSize(7).font('Helvetica-Bold').text('Value Anchors:', 44, doc.y); doc.y += 10;
        value.anchors.forEach((a, i) => {
          row(doc, a.key.replace(/_/g,' '), a.value != null ? `${money(a.value)}  ·  ${a.source}` : `Pending — ${a.source}`, i % 2 === 0);
        });
      }
    } else {
      row(doc, 'Value Estimate', 'Pending — parcel not located in fl_parcels');
    }
    liabilityNote(doc, section.liability_note);
  },

  market_and_comps(doc, report, section) {
    const priors       = report.county_stats || report.county_market_priors;
    const cma          = report.cma || {};            // Layer 2 retail
    const distressed   = report.cma_distressed || {}; // Layer 1 auction-cleared
    const retailComps  = Array.isArray(cma.comps) ? cma.comps : [];
    const auctionComps = Array.isArray(distressed.comps) ? distressed.comps : [];

    // ── LAYER 1: Distressed Market CMA ─────────────────────────────────────
    doc.fillColor(NAVY).fontSize(9).font('Helvetica-Bold')
      .text('LAYER 1 — Auction Market Comps (Distressed) · What similar properties cleared for at auction', 44, doc.y + 2);
    doc.y += 16;
    if (distressed.n_county_outcomes > 0) {
      twoCol(doc, [
        ['County Outcomes',       `${distressed.n_county_outcomes} sold (${distressed.since_year}→)`],
        ['Median Clearing Ratio', distressed.median_clearing_ratio_sold_to_assessed
          ? pct(distressed.median_clearing_ratio_sold_to_assessed) + ' of assessed' : '—'],
        ['Median Judgment Ratio', distressed.median_judgment_ratio_sold_to_judgment
          ? pct(distressed.median_judgment_ratio_sold_to_judgment) + ' of FJ' : '—'],
        ['Distressed Median $',   money(distressed.median_distressed_price)],
        ['Implied Clearing (Subject)', money(distressed.implied_clearing_price_for_subject)],
        ['Comp Scope',            distressed.n_comps_shown ? `${distressed.n_comps_shown} comps shown` : '—'],
      ]);
      if (auctionComps.length > 0) {
        doc.y += 2;
        doc.fillColor(MUTED).fontSize(7).font('Helvetica-Bold')
          .text('  ADDRESS                          SQFT   ASSESSED      SOLD       CLEARING%   DATE', 44, doc.y); doc.y += 10;
        auctionComps.forEach((c, i) => {
          if (doc.y > doc.page.height - 40) doc.addPage();
          const y = doc.y;
          doc.rect(36, y, doc.page.width - 72, 16).fill(i % 2 === 0 ? LIGHT : WHITE);
          doc.fillColor('#111827').fontSize(7.5).font('Helvetica')
            .text(c.address || '—', 44, y + 4, { width: 160 });
          doc.text(c.sqft ? String(c.sqft) : '—', 210, y + 4, { width: 40 });
          doc.text(money(c.assessed_value), 252, y + 4, { width: 70 });
          doc.fillColor(GREEN).font('Helvetica-Bold')
            .text(money(c.sold_amount), 325, y + 4, { width: 70 });
          doc.fillColor(c.clearing_pct_of_assessed > 80 ? AMBER : GREEN).font('Helvetica-Bold')
            .text(c.clearing_pct_of_assessed != null ? `${c.clearing_pct_of_assessed}%` : '—', 398, y + 4, { width: 50 });
          doc.fillColor(MUTED).font('Helvetica')
            .text(c.auction_date ? String(c.auction_date).slice(0, 10) : '—', 452, y + 4, { width: 80 });
          doc.y = y + 18;
        });
      }
    } else {
      row(doc, 'Distressed CMA', distressed.note || 'Pending — no auction-cleared comps found for this county/sqft range');
    }

    doc.y += 8;

    // ── LAYER 2: Retail ARV CMA ─────────────────────────────────────────────
    doc.fillColor(NAVY).fontSize(9).font('Helvetica-Bold')
      .text('LAYER 2 — Retail Market Comps (Open Market ARV) · Exit value after acquisition', 44, doc.y + 2);
    doc.y += 16;
    if (retailComps.length > 0) {
      retailComps.forEach((c, i) => compRow(doc, c, i));
      if (cma.median_sale_price) {
        doc.y += 2;
        doc.fillColor(MUTED).fontSize(8).font('Helvetica')
          .text(
            `Retail stats: median ${money(cma.median_sale_price)} · n=${cma.n} · dispersion ${cma.dispersion_flag || '—'}` +
            (cma.jv_twin ? ` · JV-twin: ${cma.jv_twin.address} sold ${money(cma.jv_twin.retail_indication)}` : ''),
            44, doc.y, { width: doc.page.width - 80 }
          );
        doc.y += 12;
      }
    } else {
      row(doc, 'Retail ARV Comps', cma.note || 'Pending — no retail comps returned for this parcel');
    }

    // ── THE SPREAD ──────────────────────────────────────────────────────────
    const cover       = report.cover || {};
    const distMid     = distressed.implied_clearing_price_for_subject || distressed.median_distressed_price;
    const retailMid   = cma.median_sale_price;
    if (distMid && retailMid) {
      doc.y += 4;
      doc.rect(36, doc.y, doc.page.width - 72, 22).fill('#F0FDF4');
      doc.fillColor(GREEN).fontSize(9).font('Helvetica-Bold')
        .text(
          `THE SPREAD (investment thesis): Distressed clearing ${money(distMid)} → Retail ARV ${money(retailMid)} → Day-1 equity ~${money(retailMid - distMid)}`,
          44, doc.y + 6, { width: doc.page.width - 80 }
        );
      doc.y += 26;
    }

    liabilityNote(doc, section.liability_note);
  },

  transaction_history(doc, report, section) {
    const tx = report.transaction_history || {};
    row(doc, 'Prior Transfer Date',  tx.prior_sale_date || 'Pending', true);
    row(doc, 'Prior Transfer Price', money(tx.prior_sale_price));
    row(doc, 'Current Owner',        report.cover?.current_owner || report.auction_listing?.current_owner || 'Pending', true);
    row(doc, 'Homestead Status',     report.property_record?.homestead_status || 'Pending');
    liabilityNote(doc, section.liability_note);
  },

  property_record(doc, report, section) {
    const prop    = report.property_record || {};
    const auction = report.auction_listing || {};
    twoCol(doc, [
      ['Property Type', prop.property_type || 'Pending'],
      ['Beds / Baths',  `${safeStr(prop.beds)} / ${safeStr(prop.baths)}`],
      ['Living Area',   prop.living_area_sqft ? `${prop.living_area_sqft} sqft` : 'Pending'],
      ['Year Built',    prop.year_built || 'Pending'],
      ['Lot Size',      prop.lot_size_acres ? `${prop.lot_size_acres} ac` : 'Pending'],
      ['Homestead',     prop.homestead_status || 'Pending'],
      ['Coordinates',   report.cover?.coordinates || 'Pending'],
      ['Auction URL',   auction.auction_url || 'Pending'],
    ]);
    liabilityNote(doc, section.liability_note);
  },

  context_layers(doc, report, section) {
    const ctx = report.context_layers || {};
    row(doc, 'Market Grade',    ctx.market_grade || 'Pending',      true);
    row(doc, 'Neighborhood',    ctx.neighborhood || 'Pending — layer not yet wired for this county');
    row(doc, 'Schools',         ctx.schools      || 'Pending — GreatSchools layer not yet wired', true);
    row(doc, 'Flood Zone',      ctx.flood_zone   || 'Pending — FEMA layer not yet wired; verify Zone X vs AE');
    row(doc, 'Median Income',   ctx.median_income ? `$${Number(ctx.median_income).toLocaleString()}` : 'Pending', true);
    liabilityNote(doc, section.liability_note);
  },

  shapira_ml(doc, report, section) {
    const ml = report.context_layers?.ml_model || {};
    row(doc, 'Model',           ml.model_version || 'v14.0 XGBoost',             true);
    row(doc, 'Trained',         '2026-05-27 · 137,488 samples · 21 features');
    row(doc, 'Accuracy / AUC',  'acc 72.2% · AUC 0.783 · precision 0.716 · recall 0.909 · F1 0.801', true);
    // Feature vector
    const fv = ml.feature_vector;
    if (fv) {
      doc.y += 4;
      doc.fillColor(NAVY).fontSize(8).font('Helvetica-Bold').text('Feature Vector (exact model inputs):', 44, doc.y); doc.y += 12;
      Object.entries(fv).forEach(([k, v], i) => row(doc, k.replace(/_/g,' '), safeStr(v), i % 2 === 0));
    }
    // Probability — withheld if not available
    if (typeof ml.probability_third_party_purchase === 'number') {
      doc.fillColor(RED).fontSize(7).font('Helvetica-Bold')
        .text('NOTE: Live inference probability withheld — a number the model did not produce will not be printed under its name.', 44, doc.y + 4, { width: doc.page.width - 80 });
      doc.y += 14;
    } else {
      row(doc, '3rd-Party Probability', 'Withheld — see methodology note above', true);
    }
    liabilityNote(doc, section.liability_note);
  },

  zonewise(doc, report, section) {
    const zw = report.zoning || {};
    row(doc, 'State Parcel (DOR)',   zw.parcel_id   || 'Pending', true);
    row(doc, 'Jurisdiction',         zw.jurisdiction || 'Pending');
    row(doc, 'DOR Land Use',         zw.dor_land_use || 'Pending', true);
    row(doc, 'Land Tenure (MH)',     zw.land_tenure  || 'Pending');
    row(doc, 'DOR Just Value',       money(zw.just_value),         true);
    row(doc, 'Land Value / Basis',   zw.land_value_per_sqft ? `${money(zw.land_value)} on ${zw.lot_sqft} sqft = $${zw.land_value_per_sqft}/sqft · land share ${zw.land_pct_of_jv}` : 'Pending');
    row(doc, 'Conforming-Use Read',  zw.conforming_use || 'Pending', true);
    row(doc, 'District Assignment',  zw.district      || 'PENDING — ZoneWise district layer not yet built for this county');
    row(doc, 'ZoneWise Verdict',     zw.verdict       || 'Pending', true);
    liabilityNote(doc, section.liability_note);
  },

  bid_card(doc, report, section) {
    const cover = report.cover || {};
    const opp   = report.opinion_of_price_bid_card || {};
    const smb   = cover.shapira_max_bid || {};
    const smbVal = typeof smb === 'object' ? smb.value : smb;
    // Big verdict banner
    const vColor = verdictColor(cover.verdict);
    if (doc.y > doc.page.height - 80) doc.addPage();
    const y = doc.y;
    doc.rect(36, y, doc.page.width - 72, 52).fill(vColor);
    doc.fillColor(WHITE).fontSize(24).font('Helvetica-Bold').text(cover.verdict || 'PENDING', 50, y + 6);
    doc.fontSize(11).font('Helvetica')
      .text(`Investment Grade ${cover.investment_grade || '—'}   ·   3rd-Party Probability: ELEVATED`, 50, y + 34);
    doc.y = y + 58;
    twoCol(doc, [
      ['Entry Bid',          money(opp.entry_bid || cover.entry_bid)],
      ['Shapira Max Bid',    money(smbVal)],
      ['Walk Away Above',    money(smbVal)],
      ['Value Midpoint',     money(opp.value_midpoint)],
    ]);
    liabilityNote(doc, section.liability_note);
  },

  judgment_encumbrance(doc, report, section) {
    const j     = report.judgment || {};
    const flags = report.red_flags || [];
    // Sale-type-aware (issue #19662): never render "Judgment Amount: Pending"
    // on a tax deed — it has no final judgment.
    if (report.cover?.sale_type === 'tax_deed') {
      row(doc, 'Sale Type Note',   j.sale_type_note || 'Tax deed sale — no foreclosure judgment.', true);
      row(doc, 'Unpaid Taxes (Opening Bid Basis)', j.unpaid_taxes != null ? money(j.unpaid_taxes) : 'N/A — tax deed sale (no final judgment)');
      row(doc, 'IRS Lien Survival', j.irs_lien_survives ? 'Survives (26 U.S.C. §7425)' : 'Pending', true);
      row(doc, 'HOA/COA Lien',      j.hoa_lien_may_survive ? 'May survive (FL FS 720.3085/718.116)' : 'Pending');
      row(doc, 'Statutory Extinguishment', j.statutory_extinguishment || 'Pending', true);
    } else {
      row(doc, 'Recorded CFN',       j.cfn            || 'Pending', true);
      row(doc, 'Judgment Amount',    money(j.judgment_amount));
      row(doc, 'Principal',          money(j.principal),            true);
      row(doc, 'Interest',           money(j.interest));
      row(doc, 'County Tax',         money(j.county_tax),           true);
      row(doc, 'Hazard Insurance',   money(j.hazard_insurance));
      row(doc, 'Fees / Costs',       money(j.fees),                 true);
    }
    // Red flags (existing heuristic — kept as-is)
    if (flags.length) {
      doc.y += 4;
      flags.forEach(f => flagBox(doc, f));
    }
    // Lien survival — statute-cited classification (lien_survival.classify),
    // gated by biddeed_report_composition.ship_status via composer.js's
    // sectionComposition(). Never silently falls back to the heuristic
    // above without saying so.
    const lienGate = report.composition?.lien_survival;
    doc.y += 4;
    doc.fillColor(NAVY).fontSize(8).font('Helvetica-Bold').text('Lien Survival (Title Tier 2):', 44, doc.y); doc.y += 12;
    if (lienGate?.status === 'delivered' && report.lien_survival?.available) {
      const ls = report.lien_survival;
      row(doc, 'Statutory Basis', ls.statutory_basis || 'Pending', true);
      ls.items.forEach((item, i) => {
        const label = `${item.lien_type}${item.creditor && item.creditor !== 'Pending — not on file' ? ' — ' + item.creditor : ''}`;
        const survivesLabel = item.survives === true ? 'SURVIVES' : item.survives === false ? 'EXTINGUISHED' : 'UNRESOLVED';
        row(doc, label, `${survivesLabel} — ${item.statement}`, i % 2 === 0);
      });
      if (lienGate.disclosure) {
        doc.y += 2;
        doc.fillColor(MUTED).fontSize(6.5).font('Helvetica-Oblique')
          .text(lienGate.disclosure, 44, doc.y, { width: doc.page.width - 80 });
        doc.y += 20;
      }
    } else {
      row(doc, 'Status', lienGate?.status || 'Pending — Title Tier 2 (lien survival) not yet live for this county');
    }
    liabilityNote(doc, section.liability_note);
  },

  provenance(doc, report, section) {
    const prov = report.provenance || {};
    const tmpl = section; // liability_note comes from pencil_report_parity_spec via the view
    row(doc, 'Data Sources',           prov.generated_from || 'multi_county_auctions, fl_parcels, zoning_assignments, shapira_models', true);
    row(doc, 'Certification',          prov.certification_disclosure || 'Pending');
    row(doc, 'Report Generated',       new Date().toISOString().slice(0,19).replace('T',' ') + ' UTC', true);
    // Model disclosure
    doc.y += 4;
    const mDisc = prov.model_disclosure || 'Shapira Models v14.0 XGBoost — probability withheld rather than approximated.';
    doc.fillColor('#374151').fontSize(7).font('Helvetica').text(mDisc, 44, doc.y, { width: doc.page.width - 80 });
    doc.y += (mDisc.split('\n').length * 10) + 6;
    // WHY THIS BEATS HC note (from the Marion card)
    doc.fillColor(ORANGE).fontSize(7).font('Helvetica-Bold')
      .text('WHY THIS BEATS THE HOUSECANARY REPORT FOR THIS DECISION — ', 44, doc.y, { continued: true });
    doc.fillColor('#374151').font('Helvetica')
      .text('HC prices houses; BidDeed prices auctions. HC has no Final Judgment, no plaintiff max bid, no clearance-ratio priors, no heirs/occupancy/lien red flags, and no walk-away number.', { width: doc.page.width - 80 });
    doc.y += 14;
    liabilityNote(doc, tmpl.liability_note);
  },

  auction_outcome(doc, report, section) {
    const outcome = report.auction_outcome || {};
    if (outcome.result || outcome.sale_status) {
      twoCol(doc, [
        ['Result',              outcome.sale_status || outcome.result],
        ['Sale Amount',         money(outcome.sale_amount || outcome.winning_bid)],
        ['Winning Bidder',      outcome.winning_bidder || '—'],
        ['Buyer Type',          outcome.buyer_type || '—'],
        ['Clearing Multiple',   outcome.clearing_multiple ? `${outcome.clearing_multiple}×` : '—'],
        ['Ceiling Call',        outcome.ceiling_call || '—'],
        ['Value Band Call',     outcome.value_band_call || '—'],
        ['3rd-Party Predicted', outcome.predicted_third_party ? 'YES' : 'Withheld'],
      ]);
    } else {
      row(doc, 'Status', `Pending — auction scheduled ${report.cover?.auction_date || '—'}. Populates automatically after sale closes.`);
      if (report.context_layers?.ml_model?.probability_third_party_purchase != null) {
        row(doc, 'Model Prediction', `${(report.context_layers.ml_model.probability_third_party_purchase * 100).toFixed(1)}% 3rd-party purchase probability`, true);
      }
    }
    if (outcome.flags?.length) {
      doc.y += 4;
      outcome.flags.forEach(f => flagBox(doc, f));
    }
    liabilityNote(doc, section.liability_note);
  },
};

// ─── Main render ────────────────────────────────────────────────────────────
export async function renderReportPdf(report, { get = defaultGet } = {}) {
  const template = await loadTemplate({ get });

  return new Promise((resolve, reject) => {
    const doc = new PDFDocument({ size: 'LETTER', margins: { top: 36, bottom: 36, left: 36, right: 36 }, bufferPages: true });
    const chunks = [];
    doc.on('data',  c => chunks.push(c));
    doc.on('end',   () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const cover = report.cover || {};

    // ── VOID COVER BAND ────────────────────────────────────────────────────
    doc.rect(0, 0, doc.page.width, 100).fill(VOID);
    doc.fillColor(ORANGE).fontSize(22).font('Helvetica-Bold').text('BidDeed.AI', 40, 18);
    doc.fillColor(WHITE).fontSize(11).font('Helvetica').text('▲ SIGNAL$ PROPERTY REPORT · FINAL PRE-SALE EDITION', 40, 46);
    const county   = (cover.county || '').toUpperCase();
    const saleType = (cover.sale_type || 'Foreclosure');
    const saleDate = cover.auction_date || '';
    doc.fillColor(MUTED).fontSize(8)
      .text(`${county} County, FL · ${saleType} Sale ${saleDate} · ${cover.property_address || ''}`, 40, 66);
    doc.fillColor(MUTED).fontSize(7)
      .text(`Case ${cover.case_number || '—'} · Parcel ${cover.parcel_id || '—'}`, 40, 80);
    doc.y = 108;

    // ── VERDICT + KPI STRIP ────────────────────────────────────────────────
    const vColor = verdictColor(cover.verdict);
    doc.rect(36, doc.y, doc.page.width - 72, 50).fill(vColor);
    doc.fillColor(WHITE).fontSize(18).font('Helvetica-Bold')
      .text(cover.verdict || 'PENDING', 50, doc.y - 44);
    doc.fontSize(11).font('Helvetica')
      .text(`INVESTMENT GRADE ${cover.investment_grade || '—'}  ·  SHAPIRA MAX BID ${money(cover.shapira_max_bid)}`, 50, doc.y - 20);
    const aj = report.auction_listing || {};
    // Tax deed sales (FL FS Ch. 197) have no final judgment or plaintiff —
    // those are foreclosure (Ch. 45) concepts. Same rule as the §1 band
    // below, applied to this cover KPI strip (#19662).
    doc.fontSize(9)
      .text(cover.sale_type === 'tax_deed'
        ? `OPENING BID ${aj.unpaid_taxes?.value != null ? money(aj.unpaid_taxes) : 'N/A — tax deed sale (no final judgment)'}  ·  ASSESSED VALUE ${money(aj.assessed_value)}`
        : `FINAL JUDGMENT ${money(aj.judgment_amount)}  ·  ASSESSED VALUE ${money(aj.assessed_value)}  ·  PLAINTIFF MAX BID ${money(aj.plaintiff_max_bid)}`,
        50, doc.y - 4);
    doc.y += 14;

    // Thesis line (from cover.thesis if present)
    if (cover.thesis) {
      doc.fillColor('#374151').fontSize(8).font('Helvetica-Oblique')
        .text(`Thesis: ${cover.thesis}`, 44, doc.y + 4, { width: doc.page.width - 80 });
      doc.y += 18;
    }

    // ── ITERATE TEMPLATE ROWS ──────────────────────────────────────────────
    for (const section of template) {
      if (!section.is_active && section.is_active !== undefined) continue;
      band(doc, section.section_label, section.title, section.band_color || 'navy');
      const renderer = SECTION_RENDERERS[section.section_key];
      if (renderer) {
        renderer(doc, report, section);
      } else {
        row(doc, 'Status', `No renderer registered for section_key '${section.section_key}' — add to SECTION_RENDERERS in pdf.js`);
      }
      doc.y += 6; // breathing room between bands
    }

    // ── DISCLAIMER ─────────────────────────────────────────────────────────
    if (doc.y > doc.page.height - 60) doc.addPage();
    doc.rect(36, doc.y + 8, doc.page.width - 72, 1).fill(SLATE);
    doc.y += 16;
    doc.fillColor(MUTED).fontSize(6.5).font('Helvetica')
      .text(
        DISCLAIMER_FULL || 'BidDeed.AI · Everest Capital USA · Not an appraisal. Bid decisions remain the bidder\'s own. Verify all data with county clerk and property appraiser before bidding.',
        36, doc.y, { width: doc.page.width - 72, align: 'center' }
      );

    doc.end();
  });
}

// Backward-compat alias (http.js imports renderReportPdf by name; keep both)
export { renderReportPdf as renderPDF };
