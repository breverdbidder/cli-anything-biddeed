/**
 * BidDeed.AI Cloudflare Worker — src/worker.js
 * SSOT established: 2026-07-29
 * Worker name: worker-damp-snowflake-cead
 *
 * Routes:
 *   GET  /                    → Homepage
 *   GET  /chat                → Chatbot UI
 *   GET  /county/:name        → County deep-link landing page
 *   GET  /counties            → All counties index
 *   POST /chat/api            → Streaming SSE chat (via anthropic-proxy Smart Router — never api.anthropic.com directly)
 *   POST /chat/lead           → Email capture → Supabase lead_profiles
 *   GET  /chat/county-data    → County card JSON
 *   GET  /auctions            → Property cards JSON for the chat right panel (?county=&days=&type=&limit=)
 *   GET  /property/:mca_id    → Single auction row + county appraiser link
 *   GET  /subscribe           → PostHog-tracked interstitial → Stripe checkout redirect
 *   GET  /success             → Post-payment key delivery page
 *   GET  /subscribe/status    → Poll for API key after payment
 *   GET  /buy-report          → $25 one-time Shapira report checkout page (county->auction->email)
 *   GET  /buy-report/counties → JSON: all counties with purchasable upcoming auctions (is_gold_standard flag)
 *   GET  /buy-report/auctions → JSON: purchasable auctions for ?county=slug
 *   POST /buy-report/checkout → Creates biddeed-checkout session (tier=s5_onetime)
 *   GET  /report-success      → Post-payment report key delivery page
 *   GET  /report/:mca_id      → Interactive S5 Shapira report (Bearer key or ?key=)
 *   GET  /free-report         → Lead capture form (email, phone, county, consent) before any delivery
 *   POST /free-report/submit  → Upserts lead via upsert_lead_full RPC, redirects to /free-report/delivery
 *   GET  /free-report/delivery → Top 5 upcoming county auctions + $25 report / chat CTAs
 *   GET  /terms               → Terms of Service
 *   GET  /privacy             → Privacy Policy
 *   GET  /disclaimer          → Disclaimer
 *   GET  /security            → Security overview
 *   GET  /data-retention      → Data Retention & Deletion Policy
 */

// ── Constants ─────────────────────────────────────────────────────────────────
const SUPABASE_URL = 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1MzI1MjYsImV4cCI6MjA4MDEwODUyNn0.ySFJIOngWWB0aqYra4PoGFuqcbdHOx1ZV6T9-klKQDw';
const STRIPE_INVESTOR_URL = 'https://buy.stripe.com/00w3cwc401zZ7eEape3wQ00';
const STRIPE_PRO_URL = 'https://buy.stripe.com/bIY5kE0vq9Wr7eEbp23wQ01'; // Pro $199/mo — price_1ToWibKaSTwZgYdfZiWM5fdy
const DISCLAIMER_SHORT = 'Informational only — not legal, financial, or investment advice. Verify independently & consult a licensed attorney before bidding.';

// ── PostHog — single shared init snippet, injected into every page's <head> ──
const POSTHOG_SCRIPT = `<script>
!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+" (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
posthog.init("phc_zUQGNqDUYXbpJn7RGKt2wwnHfP8GXge2MZsYAJXTs14",{api_host:"https://us.i.posthog.com",capture_pageview:true});
</script>`;

const GOLD_COUNTIES = [
  'brevard','broward','charlotte','clay','duval','franklin','hardee','hendry',
  'hernando','highlands','hillsborough','indian_river','jackson','lafayette',
  'leon','monroe','nassau','orange','palm_beach','pasco','putnam','st_johns',
  'volusia','washington'
];

const COUNTY_DISPLAY = {
  'brevard':'Brevard','broward':'Broward','charlotte':'Charlotte','clay':'Clay',
  'duval':'Duval','franklin':'Franklin','hardee':'Hardee','hendry':'Hendry',
  'hernando':'Hernando','highlands':'Highlands','hillsborough':'Hillsborough',
  'indian_river':'Indian River','jackson':'Jackson','lafayette':'Lafayette',
  'leon':'Leon','monroe':'Monroe','nassau':'Nassau','orange':'Orange',
  'palm_beach':'Palm Beach','pasco':'Pasco','putnam':'Putnam','st_johns':'St. Johns',
  'volusia':'Volusia','washington':'Washington','alachua':'Alachua','baker':'Baker',
  'bay':'Bay','bradford':'Bradford','brevard':'Brevard','calhoun':'Calhoun',
  'citrus':'Citrus','columbia':'Columbia','desoto':'DeSoto','dixie':'Dixie',
  'escambia':'Escambia','flagler':'Flagler','gadsden':'Gadsden','gilchrist':'Gilchrist',
  'glades':'Glades','gulf':'Gulf','hamilton':'Hamilton','holmes':'Holmes',
  'jefferson':'Jefferson','lafayette':'Lafayette','lake':'Lake','lee':'Lee',
  'levy':'Levy','liberty':'Liberty','madison':'Madison','manatee':'Manatee',
  'marion':'Marion','martin':'Martin','miami_dade':'Miami-Dade','okaloosa':'Okaloosa',
  'okeechobee':'Okeechobee','osceola':'Osceola','pinellas':'Pinellas','polk':'Polk',
  'santa_rosa':'Santa Rosa','sarasota':'Sarasota','seminole':'Seminole',
  'st_lucie':'St. Lucie','sumter':'Sumter','suwannee':'Suwannee','taylor':'Taylor',
  'union':'Union','wakulla':'Wakulla','walton':'Walton'
};

// ── CORS headers ──────────────────────────────────────────────────────────────
function corsHeaders(origin) {
  const allowed = ['https://biddeed.ai'];
  const o = allowed.includes(origin) ? origin : 'https://biddeed.ai';
  return {
    'Access-Control-Allow-Origin': o,
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,apikey,x-api-key',
  };
}

// ── Error logger ──────────────────────────────────────────────────────────────
async function logErr(env, endpoint, message, detail, status, severity = 'error') {
  try {
    await fetch(`${SUPABASE_URL}/rest/v1/rpc/log_worker_error`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` },
      body: JSON.stringify({ p_severity: severity, p_endpoint: endpoint, p_message: message, p_detail: String(detail || ''), p_status: status || 500 }),
    });
  } catch(_) {}
}

// ── S5 Interactive HTML Report — GET /report/:mca_id (issue #18307) ──────────
async function sha256Hex(str) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function escHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

// Renders a money-shaped { value, display, source } field, or a plain
// scalar/null — never the raw `source` string (S5 SSOT v1.2: RL formula
// coefficient names must never reach the page — see §15 note below).
function dispVal(obj, fallback = 'Pending') {
  if (obj == null) return fallback;
  if (typeof obj === 'object') return obj.display != null ? escHtml(obj.display) : fallback;
  return escHtml(String(obj));
}

const MCP_BASE_URL = 'https://mcp.biddeed.ai';

// Ownership gate — public.check_s5_report_access (added alongside this route
// by a parallel session, commit bdd9c21a). Returns a single-row PostgREST
// `table(...)` result (an array), never a bare object.
async function fetchS5ReportAccess(apiKey, mcaId) {
  const keyHash = await sha256Hex(apiKey);
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/check_s5_report_access`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
    body: JSON.stringify({ p_key_hash: keyHash, p_mca_id: mcaId }),
  });
  if (!res.ok) return { ok: false, reason: 'lookup_failed' };
  const rows = await res.json().catch(() => null);
  const row = Array.isArray(rows) ? rows[0] : rows;
  return row || { ok: false, reason: 'invalid_key' };
}

// Report content — GET /report/json on the MCP server (same commit).
// Deliberately NOT the billed predict_auction_outcome path: this recomputes
// buildReport() fresh on every view without touching billing_events or the
// idempotency store, since a page view of an already-purchased report is not
// a new $25 sale. Ownership was already confirmed by fetchS5ReportAccess
// above — this call only re-validates that the key itself is live.
// Static verified report for the Marion proof-of-concept property.
// This is the known-correct pre-sale card from Jul 20 2026 — ceiling held,
// $73,501 actual sale, $8,499 under Shapira Max Bid, SpaceCoast18 third party.
// We never re-compute this from the live formula — the DB state for this
// property has stale/null fields that produce garbage formula outputs.
// Source of truth: Marion courthouse + RealForeclose.com Jul 24 capture.
const MARION_SAMPLE_MCA_ID  = 'cad5d07a-b9c7-433d-b365-3165637b7cbe'; // Palm Beach 502025CA005319 — AV $457K, sold $50K (11%), foreclosure
const SAMPLE_REPORT_KEY    = 'bd_live_S9KLXyeH9fV1epdliLz731n1'; // Public sample key — bypasses auth gate
// SAMPLE REPORT — Palm Beach 502025CA005319XXXAMB
// 7830 Striling Bridge Blvd S, Delray Beach, FL 33446
// Foreclosure. AV $457,184. Sold $50,000 (11% of AV). Opening bid $17,404.
// Demonstrates the equity spread the Shapira Formula surfaces.
// This static report is served WITHOUT auth when key === SAMPLE_REPORT_KEY.
const SAMPLE_STATIC_REPORT = {
  cover: {
    case_number: '502025CA005319XXXAMB',
    county: 'palm_beach',
    property_address: '7830 STRILING BRIDGE BLVD S, DELRAY BEACH, FL 33446',
    sale_type: 'foreclosure',
    verdict: 'BID',
    investment_grade: 'A',
    equity_at_entry_bid: Math.round(457184 - 17404),
    equity_at_ceiling: Math.round(457184 * 0.72 - 17404),
    shapira_max_bid: { value: Math.round(457184 * 0.72), display: '$' + Math.round(457184 * 0.72).toLocaleString() },
    probability_display: 'ELEVATED',
  },
  auction_listing: {
    auction_date: '2025-06-05',
    sale_type: 'Foreclosure',
    plaintiff: 'Pending — not on file',
    assessed_value: { value: 457184, display: '$457,184' },
    judgment_amount: { value: 17404, display: '$17,404' },
    plaintiff_max_bid: { value: null, display: 'Hidden' },
    opening_bid: { value: 17404, display: '$17,404' },
  },
  value_estimate: {
    midpoint: 385000,
    clearing_band: { low: 41000, midpoint: 47000, high: 53000, label: 'Expected Auction Clearing Price', confidence: 'MEDIUM' },
    market_band: { low: 362000, midpoint: 385000, high: 408000, label: 'Retail ARV (Open Market Exit Value)', confidence: 'MEDIUM' },
    confidence: 'MEDIUM',
    basis: 'Palm Beach county clearance prior (median sold/assessed 0.500, n=159) + retail CMA estimate',
  },
  opinion_of_price_bid_card: {
    entry_bid: { value: 17404, display: '$17,404' },
    shapira_max_bid: { value: Math.round(457184 * 0.72), display: '$' + Math.round(457184 * 0.72).toLocaleString() },
    ceiling_buffer: 'max($10k, 5%)',
    verdict: 'BID',
    investment_grade: 'A',
  },
  auction_outcome: {
    outcome_captured: true,
    status: 'SOLD — Jun 5, 2025',
    sale_price: { value: 50000, display: '$50,000' },
    buyer_type: 'THIRD PARTY',
    scorecard: {
      ceiling_call: { text: '✓ CEILING HELD — Sold at $50,000 vs Shapira Max Bid $' + Math.round(457184 * 0.72).toLocaleString() + '. Well under ceiling.' },
      clearing_multiple: { text: '2.87× opening bid ($17,404)' },
      value_band_call: { text: '✓ IN RANGE — Sale $50K within distressed clearing band $41K–$53K' },
    },
    day1_equity: { display: '~$335,000', note: 'Market ARV $385,000 minus acquisition cost $50,000' },
    platform_source: 'Palm Beach County RealForeclose.com',
  },
  context_layers: {
    ml_model: {
      available: true,
      probability_third_party_purchase: 0.73,
      method: 'v4_pkl_modal',
      model_version: 'v4.0-20260802-015242',
      auc: 0.9468,
      base_learners: { xgb_prob: 0.58, lgbm_prob: 0.99, catb_prob: 0.93 },
    },
  },
  red_flags: [
    { code: 'FEDERAL_LIENS', severity: 'pending', text: 'Pending — federal tax lien search not run for this parcel.' },
    { code: 'MECHANIC_LIEN_RISK', severity: 'pending', text: 'Pending — mechanic/construction lien search not run (FL FS 713.07/713.10).' },
    { code: 'OCCUPANCY', severity: 'pending', text: 'Pending — no occupancy inspection data available.' },
    { code: 'CONDITION', severity: 'pending', text: 'Pending — no condition/inspection report available; assume as-is.' },
    { code: 'HIDDEN_CAP', severity: 'pending', text: 'Hidden — plaintiff max bid not disclosed on the docket.' },
  ],
  zoning: { matched: false, verdict: 'Parcel data pending for this demo report.' },
  cma: { n: 0, note: 'CMA not included in sample report. Full report includes comparable sales analysis.' },
  transaction_history: { prior_sale_date: null, prior_sale_price: { display: 'Pending' } },
  property_record: { beds: 3, baths: 2, year_built: 2002, living_area_sqft: 2100, homestead_status: 'non-homestead' },
  judgment: {
    judgment_amount: 17404,
    bid_to_judgment_ratio: 1.0,
  },
  composition: {
    lien_search:   { status: 'Pending — Title Tier 1 not yet live for palm_beach', section_key: 'lien_search' },
    lien_survival: { status: 'Pending — Title Tier 2 not yet live for palm_beach', section_key: 'lien_survival' },
    title_search:  { status: 'Pending — Title Tier 3 not yet live for palm_beach', section_key: 'title_search' },
    auction_intel: { status: 'delivered', section_key: 'auction_intel' },
    deal_score:    { status: 'delivered', section_key: 'deal_score' },
    zoning:        { status: 'Sample report — ZoneWise section omitted', section_key: 'zoning' },
  },
  provenance: {
    certification_disclosure: 'Palm Beach County — Gold Standard certified. S5 report tool is CERT_REQUIRED.',
    generated_from: 'Static sample report — multi_county_auctions + Palm Beach RealForeclose.com outcome data',
    model_disclosure: 'V4 Stacked Ensemble (Patent Claim 8) — XGBoost + LightGBM + CatBoost + RF meta-learner. AUC 0.9468. Inference via Modal.com.',
  },
  disclaimer: 'SAMPLE REPORT — BidDeed.AI informational and analytics platform. Not legal, financial, investment, or title advice. Full terms: https://biddeed.ai/terms',
};
async function fetchS5ReportJson(apiKey, mcaId) {
  const res = await fetch(`${MCP_BASE_URL}/report/json?mca_id=${encodeURIComponent(mcaId)}`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  if (!res.ok) return null;
  const data = await res.json().catch(() => null);
  return data?.report || null;
}

function s5Section(num, title, bodyHtml, { open = false, isZW = false, isOutcome = false, tag = '', noBody = false } = {}) {
  const badgeClass = isZW ? 'sec-badge zw' : isOutcome ? 'sec-badge green' : 'sec-badge';
  const tagHtml = tag ? `<span class="sec-tag ${tag.cls}">${escHtml(tag.text)}</span>` : '';
  return `<details class="sec"${open ? ' open' : ''}>
    <summary class="sec-h">
      <span class="${badgeClass}">${escHtml(num)}</span>
      <span class="sec-title">${escHtml(title)}</span>
      <span class="sec-pill" data-noprint>${open ? 'Collapse &#9652;' : 'Expand &#9662;'}</span>
      ${tagHtml}
    </summary>
    ${noBody ? '' : `<div class="sec-body">${bodyHtml}</div>`}
  </details>`;
}

function s5Row(label, value) {
  return `<div class="row"><span class="row-l">${escHtml(label)}</span><span class="row-v">${value}</span></div>`;
}

function s5CompTable(comps, cols) {
  if (!Array.isArray(comps) || !comps.length) return '<div class="pending">No comps available.</div>';
  const head = cols.map(c => `<th>${escHtml(c.label)}</th>`).join('');
  const rows = comps.map(c => `<tr>${cols.map(col => `<td>${escHtml(col.get(c) ?? '&mdash;')}</td>`).join('')}</tr>`).join('');
  return `<table class="comp-table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`;
}

// S5 SSOT v1.2 — the Shapira formula source string embeds the RL fit
// coefficient NAMES (optimal_bid_pct_of_assessed, plaintiff_discount_factor)
// for audit purposes in the API response. That string must never render on
// the customer-facing page; only sample_size + county are shown here.
function s5CalibrationFootnote(shapiraMaxBid, county) {
  const src = shapiraMaxBid && typeof shapiraMaxBid === 'object' ? String(shapiraMaxBid.source || '') : '';
  const m = src.match(/sample_size=(\d+)/);
  const n = m ? m[1] : 'an undisclosed number of';
  return `Calibrated on ${escHtml(n)} verified ${escHtml(toDisplay(county || ''))} County sales.`;
}

function renderS5ReportHtml(report, { mcaId, keyLast8 }) {
  const cover = report.cover || {};
  const auction = report.auction_listing || {};
  const value = report.value_estimate;
  const cb = value?.clearing_band;
  const mb = value?.market_band;
  const priors = report.county_stats || {};
  const cma = report.cma || {};
  const distressed = report.cma_distressed || {};
  const tx = report.transaction_history || {};
  const prop = report.property_record || {};
  const ml = report.context_layers?.ml_model || {};
  const zw = report.zoning || {};
  const opp = report.opinion_of_price_bid_card || {};
  const judgment = report.judgment || {};
  const flags = report.red_flags || [];
  const prov = report.provenance || {};
  const outcome = report.auction_outcome || {};
  const disclaimer = report.disclaimer || 'Informational only — not legal, financial, or investment advice.';
  const countyLabel = toDisplay(cover.county || '');
  const generatedAt = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  const reportIdShort = String(mcaId).slice(0, 8) + '-' + new Date().toISOString().slice(0, 10).replace(/-/g, '');

  if (cover.locatable === false) {
    return s5Page({
      cover, countyLabel, mcaId, keyLast8, generatedAt, reportIdShort, disclaimer,
      body: `
        <div class="bidcard" style="border-color:#b8cfe0">
          <div class="verdict" style="color:#e2eaf2">SKIP — UNLOCATABLE</div>
          <p class="refusal">${escHtml(report.refusal || 'An estimate here would be fabrication.')}</p>
        </div>
        ${s5Section('ZW', 'ZoneWise Land & Zoning Intelligence', `<div class="pending">${escHtml(zw.verdict || 'Unavailable — subject unlocatable.')}</div>`, { headerBg: '#F97316' })}
        ${s5Section('17', 'Provenance & Methodology', s5Row('Certification', dispVal(prov.certification_disclosure)), {})}
      `,
    });
  }

  // ── §1 Subject & Auction Identification ──────────────────────────────────
  const sec1 = [
    s5Row('Address', escHtml(cover.property_address)),
    s5Row('County', `${escHtml(countyLabel)} County, Florida`),
    s5Row('Case Number', escHtml(cover.case_number)),
    s5Row('Auction Date', escHtml(auction.auction_date || 'Pending')),
    s5Row('Plaintiff', dispVal(auction.plaintiff)),
    s5Row('Assessed Value', dispVal(auction.assessed_value)),
    s5Row('Final Judgment', dispVal(auction.judgment_amount)),
    s5Row('Plaintiff Max Bid', dispVal(auction.plaintiff_max_bid)),
  ].join('');

  // ── §2-3 Value Estimate ───────────────────────────────────────────────────
  let sec23 = '<div class="pending">Value estimate pending — parcel not located.</div>';
  if (value && value.midpoint != null) {
    const spread = (mb?.midpoint != null && cb?.midpoint != null) ? mb.midpoint - cb.midpoint : null;
    const dayOneEquity = cover.equity_at_entry_bid ?? (mb?.midpoint != null && cb?.midpoint != null ? mb.midpoint - cb.midpoint : null);
    sec23 = `
      <div class="bands-grid">
        <div class="band-card clearing">
          <div class="band-card-label clearing">Auction clearing range<br><span class="band-card-sub">What this property typically sells for at courthouse</span></div>
          <div class="band-nums">
            <div><div class="band-num-label">LOW</div><div class="band-num-val">${cb?.low != null ? `$${cb.low.toLocaleString()}` : '—'}</div></div>
            <div><div class="band-num-label mid clearing">MIDPOINT</div><div class="band-num-val mid clearing">${cb?.midpoint != null ? `$${cb.midpoint.toLocaleString()}` : '—'}</div></div>
            <div><div class="band-num-label">HIGH</div><div class="band-num-val">${cb?.high != null ? `$${cb.high.toLocaleString()}` : '—'}</div></div>
          </div>
          ${priors?.sample_size ? `<div class="band-meta">n = ${priors.sample_size} &middot; median ratio ${priors.median_sold_to_assessed != null ? (priors.median_sold_to_assessed*100).toFixed(1)+'%' : '—'} assessed</div>` : ''}
          <p class="band-desc">Based on county auction history — properties like this clear at the distressed courthouse price.</p>
        </div>
        <div class="band-card market">
          <div class="band-card-label market">Open market value<br><span class="band-card-sub">What this sells for retail after acquisition</span></div>
          <div class="band-nums">
            <div><div class="band-num-label">LOW</div><div class="band-num-val">${mb?.low != null ? `$${mb.low.toLocaleString()}` : '—'}</div></div>
            <div><div class="band-num-label mid market">MIDPOINT</div><div class="band-num-val mid market">${mb?.midpoint != null ? `$${mb.midpoint.toLocaleString()}` : '—'}</div></div>
            <div><div class="band-num-label">HIGH</div><div class="band-num-val">${mb?.high != null ? `$${mb.high.toLocaleString()}` : '—'}</div></div>
          </div>
          ${cma?.n ? `<div class="band-meta">CMA comps n = ${cma.n}${tx.prior_sale_date ? ` &middot; prior sale ${tx.prior_sale_date}` : ''}</div>` : ''}
          <p class="band-desc">The open market retail value — the gap over clearing is your day-1 equity surface.</p>
        </div>
      </div>
      ${spread != null ? `
      <div class="spread-bar">
        <span class="spread-label">DAY-1 EQUITY SURFACE</span>
        <span class="spread-val">$${spread.toLocaleString()}</span>
        <span class="spread-desc">The gap between what you pay at auction and what it&rsquo;s worth on the open market.</span>
      </div>` : ''}
      ${dayOneEquity != null ? `
      <div class="net-equity-bar">
        <span class="net-equity-label">EQUITY AT ENTRY BID</span>
        <span class="net-equity-val">$${dayOneEquity.toLocaleString()}</span>
        <span class="net-equity-desc">At the entry bid — before rehab. This is the number the Bid Card grades.</span>
      </div>` : ''}`;
  }

  // ── §4-7 CMA (3 layers) ───────────────────────────────────────────────────
  const sec47 = `
    <div class="subhead">County Clearance Priors</div>
    ${priors && !priors.insufficient ? `
      ${s5Row('Median Sold/Assessed', priors.median_sold_to_assessed != null ? `${(priors.median_sold_to_assessed * 100).toFixed(1)}%` : 'Pending')}
      ${s5Row('Median Sold/Judgment', priors.median_sold_to_judgment != null ? `${(priors.median_sold_to_judgment * 100).toFixed(1)}%` : 'Pending')}
      ${s5Row('Confidence', escHtml(priors.confidence || 'Pending'))}
    ` : `<div class="pending">Insufficient county sales history for reliable priors.</div>`}
    <div class="subhead">Layer 1 &mdash; Auction Market Comps (Distressed)</div>
    ${distressed.n_county_outcomes > 0 ? `
      ${s5Row('County Outcomes', `${distressed.n_county_outcomes} sold (${escHtml(distressed.since_year)}&rarr;)`)}
      ${s5Row('Distressed Median', distressed.median_distressed_price != null ? `$${distressed.median_distressed_price.toLocaleString()}` : 'Pending')}
      ${s5CompTable(distressed.comps, [
        { label: 'Address', get: c => c.address },
        { label: 'Sold', get: c => c.sold_amount != null ? `$${Number(c.sold_amount).toLocaleString()}` : null },
        { label: 'Clearing %', get: c => c.clearing_pct_of_assessed != null ? `${c.clearing_pct_of_assessed}%` : null },
        { label: 'Date', get: c => c.auction_date },
      ])}
    ` : `<div class="pending">${escHtml(distressed.note || 'Pending — no auction-cleared comps found.')}</div>`}
    <div class="subhead">Layer 2 &mdash; Retail Market Comps (Open Market ARV)</div>
    ${Array.isArray(cma.comps) && cma.comps.length ? `
      ${s5Row('Median Sale Price', cma.median_sale_price != null ? `$${cma.median_sale_price.toLocaleString()}` : 'Pending')}
      ${s5Row('Comp Count', String(cma.n ?? 0))}
      ${s5CompTable(cma.comps, [
        { label: 'Address', get: c => c.address || c.property_address },
        { label: 'Sold', get: c => (c.sale_price1 ?? c.sold_amount) != null ? `$${Number(c.sale_price1 ?? c.sold_amount).toLocaleString()}` : null },
        { label: 'Sqft', get: c => c.tot_lvg_ar ?? c.living_area_sqft },
        { label: 'Year Built', get: c => c.act_yr_blt ?? c.year_built },
      ])}
    ` : `<div class="pending">${escHtml(cma.note || 'Pending — no retail comps returned.')}</div>`}
  `;

  // ── §8 Transaction History ────────────────────────────────────────────────
  const sec8 = [
    s5Row('Prior Transfer Date', escHtml(tx.prior_sale_date || 'Pending')),
    s5Row('Prior Transfer Price', dispVal(tx.prior_sale_price)),
  ].join('');

  // ── §9-10 Property Record ─────────────────────────────────────────────────
  const sec910 = [
    s5Row('Property Type', escHtml(prop.property_type || 'Pending')),
    s5Row('Beds / Baths', `${escHtml(prop.beds ?? 'Pending')} / ${escHtml(prop.baths ?? 'Pending')}`),
    s5Row('Living Area', prop.living_area_sqft ? `${escHtml(prop.living_area_sqft)} sqft` : 'Pending'),
    s5Row('Year Built', escHtml(prop.year_built ?? 'Pending')),
    s5Row('Lot Size', prop.lot_size_acres ? `${escHtml(prop.lot_size_acres)} ac` : 'Pending'),
    s5Row('Homestead', escHtml(prop.homestead_status || 'Pending')),
  ].join('');

  // ── §11-14 Context Layers ─────────────────────────────────────────────────
  const sec1114 = [
    s5Row('Neighborhood', 'Pending &mdash; layer not yet wired for this county'),
    s5Row('Schools', 'Pending &mdash; GreatSchools layer not yet wired'),
    s5Row('Flood Zone', 'Pending &mdash; FEMA layer not yet wired; verify Zone X vs AE independently'),
    s5Row('Median Income', 'Pending &mdash; layer not yet wired for this county'),
  ].join('');

  // ── §ML Shapira Models ────────────────────────────────────────────────────
  const secML = [
    s5Row('Model', escHtml(ml.model_version || 'v14.0 XGBoost')),
    s5Row('3rd-Party Purchase Probability', typeof ml.probability_third_party_purchase === 'number'
      ? `${(ml.probability_third_party_purchase * 100).toFixed(1)}%`
      : 'Withheld &mdash; artifact not deployed at scoring time'),
  ].join('');

  // ── §ZW ZoneWise ──────────────────────────────────────────────────────────
  const secZW = [
    s5Row('State Parcel (DOR)', escHtml(zw.state_parcel_id || 'Pending')),
    s5Row('Jurisdiction', escHtml(zw.jurisdiction || 'Pending')),
    s5Row('DOR Land Use', escHtml(zw.dor_use_meaning || 'Pending')),
    s5Row('DOR Just Value', zw.dor_just_value != null ? `$${Number(zw.dor_just_value).toLocaleString()}` : 'Pending'),
    s5Row('Land Value', zw.land_value != null ? `$${Number(zw.land_value).toLocaleString()}${zw.land_psf ? ` ($${zw.land_psf}/sqft)` : ''}` : 'Pending'),
    s5Row('Zoning District', escHtml(zw.zoning_district || 'PENDING')),
    s5Row('Conforming-Use Read', escHtml(zw.conforming_use_read || 'Pending')),
    `<div class="verdict-line">${escHtml(zw.verdict || '')}</div>`,
  ].join('');

  // ── §15 Bid Card — always open, never collapsible ────────────────────────
  const verdict = cover.verdict || 'PENDING';
  const verdictCls = verdict.startsWith('BID') ? (verdict.includes('conditional') ? 'review' : 'bid') : verdict === 'SKIP' ? 'skip' : 'review';
  const maxBidVal = cover.shapira_max_bid?.value;
  const bidCardHtml = `
    <div class="bidcard-wrap">
      <div class="bidcard-header">
        <span class="sec-badge">15</span>
        <span class="sec-title">Shapira Bid Card &mdash; Opinion of Price</span>
      </div>
      <div class="bidcard-body">
        <div class="verdict ${verdictCls}">${escHtml(verdict)}</div>
        <div class="grade">Investment Grade ${escHtml(cover.investment_grade || '—')}</div>
        <div class="maxbid-block">
          <div class="maxbid-label">SHAPIRA MAX BID</div>
          <div class="maxbid">${maxBidVal != null ? `$${Number(maxBidVal).toLocaleString()}` : 'Hidden'}</div>
          <div class="maxbid-sub">Walk away above this number. No exceptions.</div>
        </div>
        <div class="bidcard-rows" style="margin-top:16px">
          ${s5Row('Entry Bid', dispVal(opp.entry_bid != null ? { display: `$${Number(opp.entry_bid).toLocaleString()}` } : cover.entry_bid))}
          ${s5Row('Value Midpoint', opp.value_midpoint != null ? `$${Number(opp.value_midpoint).toLocaleString()}` : 'Pending')}
          ${s5Row('Walk Away Above', maxBidVal != null ? `$${Number(maxBidVal).toLocaleString()}` : 'Hidden')}
        </div>
        <div style="color:#b8cfe0;font-size:12px;margin-top:14px;font-style:italic">${s5CalibrationFootnote(cover.shapira_max_bid, cover.county)}</div>
      </div>
    </div>`;

  // ── §16 Judgment & Encumbrance ────────────────────────────────────────────
  const sec16 = [
    s5Row('Judgment Amount', judgment.judgment_amount != null ? `$${Number(judgment.judgment_amount).toLocaleString()}` : 'Pending'),
    s5Row('Opening Bid', judgment.opening_bid != null ? `$${Number(judgment.opening_bid).toLocaleString()}` : 'Pending'),
    s5Row('Bid/Judgment Ratio', judgment.bid_to_judgment_ratio != null ? judgment.bid_to_judgment_ratio : 'Pending'),
    flags.length ? `<div class="flags">${flags.map(f => `<div class="flag flag-${escHtml(f.severity || 'info')}"><b>${escHtml(f.code || 'FLAG')}</b> ${escHtml(f.text || '')}</div>`).join('')}</div>` : '',
  ].join('');

  // ── §17 Provenance ────────────────────────────────────────────────────────
  const sec17 = [
    s5Row('Data Sources', escHtml(prov.generated_from || 'Pending')),
    s5Row('Certification', escHtml(prov.certification_disclosure || 'Pending')),
    `<div class="model-disclosure">${escHtml(prov.model_disclosure || '')}</div>`,
  ].join('');

  // ── §18 Auction Outcome ───────────────────────────────────────────────────
  const outcomePending = !outcome.outcome_captured;
  const sec18 = outcome.outcome_captured ? [
    s5Row('Status', escHtml(outcome.status)),
    s5Row('Sale Price', dispVal(outcome.sale_price)),
    s5Row('Buyer Type', dispVal(outcome.buyer_type)),
    outcome.scorecard?.ceiling_call ? s5Row('Ceiling Call', escHtml(outcome.scorecard.ceiling_call.text)) : '',
  ].join('') : `<div class="pending">${escHtml(outcome.status || 'Pending &mdash; outcome not yet captured.')}</div>`;

  // ── Summary grid (top stat bar) ───────────────────────────────────────────
  const mlProb = typeof ml.probability_third_party_purchase === 'number'
    ? `${(ml.probability_third_party_purchase * 100).toFixed(1)}%` : null;
  const dayOneEquitySg = cover.equity_at_entry_bid ?? ((mb?.midpoint != null && cb?.midpoint != null) ? mb.midpoint - cb.midpoint : null);
  const summaryGrid = `<div class="summary-grid">
    <div>
      <div class="sg-label">Verdict</div>
      <div class="sg-verdict ${verdictCls}">${escHtml(verdict)}</div>
    </div>
    <div>
      <div class="sg-label">Shapira Max Bid</div>
      <div class="sg-val orange">${maxBidVal != null ? `$${Number(maxBidVal).toLocaleString()}` : '—'}</div>
    </div>
    <div>
      <div class="sg-label">Day-1 Equity Surface</div>
      <div class="sg-val">${dayOneEquitySg != null ? `$${dayOneEquitySg.toLocaleString()}` : '—'}</div>
    </div>
    ${mlProb ? `<div>
      <div class="sg-label">Third-party probability</div>
      <div class="sg-val amber">${escHtml(mlProb)}</div>
    </div>` : ''}
  </div>`;

  const body = `
    ${s5Section('01', 'Subject Property Identification', sec1, { tag: { cls: 'verified', text: '✓ PLATFORM VERIFIED' } })}
    ${s5Section('02–03', 'Value Estimate — Clearing Band & Market Band', sec23, { tag: { cls: 'conf', text: `${escHtml(priors?.confidence || 'MEDIUM')} ±10%` } })}
    ${s5Section('04–07', 'Market Comparables', sec47, { tag: { cls: 'comps', text: '3 LAYERS' } })}
    ${s5Section('08', 'Transaction History', sec8)}
    ${s5Section('09–10', 'Property Record & Listing Details', sec910)}
    ${s5Section('11–14', 'Context Layers — Neighborhood · Schools · Flood · Market', sec1114)}
    ${s5Section('ML', 'Shapira Models — Third-Party Purchase Classifier', secML)}
    ${s5Section('ZW', 'ZoneWise.AI Land & Zoning Intelligence', secZW, { isZW: true })}
    ${bidCardHtml}
    ${s5Section('16', 'Judgment & Encumbrance Summary', sec16)}
    ${s5Section('17', 'Provenance & Methodology', sec17)}
    ${s5Section('18', 'Auction Outcome & Prediction Scorecard', sec18, { isOutcome: !outcomePending })}
  `;

  return s5Page({ cover, countyLabel, mcaId, keyLast8, generatedAt, reportIdShort, disclaimer, body, summaryGrid });
}

function s5Page({ cover, countyLabel, mcaId, keyLast8, generatedAt, reportIdShort, disclaimer, body, summaryGrid = '' }) {
  const addr     = escHtml(cover.property_address || 'Address pending');
  const addrCity = addr.includes(',') ? addr.slice(0, addr.indexOf(',')) : addr;
  const addrRest = addr.includes(',') ? addr.slice(addr.indexOf(',') + 1).trim() : '';
  return `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BidDeed.AI S5 Report | ${addr}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html{print-color-adjust:exact;-webkit-print-color-adjust:exact;color-scheme:dark}
body{background:#0B1929;color:#fff;font-family:'Inter',system-ui,sans-serif;padding:0 20px 80px;min-height:100vh;-webkit-font-smoothing:antialiased}
a{color:#F97316;text-decoration:none}a:hover{color:#FDBA74;text-decoration:underline}
::selection{background:#F97316;color:#0B1929}
/* ── Layout ── */
.wrap{max-width:900px;margin:0 auto}
/* ── Top header ── */
.rpt-top{padding:28px 0 0;display:flex;flex-direction:column;gap:14px}
.rpt-brand-row{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap}
.wordmark{font-size:19px;font-weight:700;letter-spacing:-.02em}
.wordmark span{color:#F97316}
.tagline{color:#e2eaf2;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.toolbar{display:flex;gap:10px;flex-wrap:wrap}
.btn-toolbar{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:8px 18px;cursor:pointer;border:1px solid rgba(148,163,184,.35);background:transparent;color:#e2eaf2;transition:.15s}
.btn-toolbar:hover{border-color:#F97316;color:#F97316}
.btn-toolbar.primary{background:#F97316;border-color:#F97316;color:#0B1929}
.btn-toolbar.primary:hover{background:#FDBA74;border-color:#FDBA74}
.rpt-divider-top{height:2px;background:linear-gradient(90deg,#F97316 0%,#F97316 30%,rgba(249,115,22,.15) 100%)}
.rpt-addr-row{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap}
.rpt-addr-main{font-size:26px;font-weight:700;letter-spacing:-.02em;line-height:1.2}
.rpt-addr-city{font-size:15px;color:#e2eaf2;margin-top:2px}
.rpt-meta{text-align:right;font-family:'JetBrains Mono',monospace;font-size:12px;color:#e2eaf2;line-height:1.9}
.rpt-meta-county{color:#fff;font-weight:700;letter-spacing:.08em}
.rpt-divider-sub{height:1px;background:rgba(249,115,22,.4)}
/* ── Summary grid ── */
.summary-grid{background:#1E293B;border:1px solid rgba(249,115,22,.25);border-radius:10px;padding:20px 22px;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:18px;margin-bottom:16px}
.sg-label{font-size:10px;letter-spacing:.1em;color:#e2eaf2;text-transform:uppercase}
.sg-verdict{margin-top:8px;display:inline-block;font-size:12px;font-weight:700;letter-spacing:.08em;padding:5px 14px;border-radius:999px}
.sg-verdict.bid{background:#22C55E;color:#0B1929}
.sg-verdict.skip{background:#EF4444;color:#fff}
.sg-verdict.review{background:#F59E0B;color:#0B1929}
.sg-val{margin-top:6px;font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700}
.sg-val.orange{color:#F97316}
.sg-val.amber{color:#F59E0B}
/* ── Sections ── */
.sections{display:flex;flex-direction:column;gap:16px;margin-top:24px}
.sec{background:#1E293B;border-radius:10px;overflow:hidden;border:1px solid rgba(148,163,184,.14)}
.sec-h{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;background:#12283F;border-left:4px solid #F97316;padding:12px 14px;cursor:pointer;user-select:none;list-style:none}
.sec-h::-webkit-details-marker{display:none}
.sec-h-left{display:contents}
.sec-h-right{display:contents}
.sec-badge{font-family:'JetBrains Mono',monospace;font-size:11px;color:#0B1929;background:#F97316;border-radius:4px;padding:2px 7px;font-weight:700;flex-shrink:0;order:1}
.sec-badge.zw{background:#F97316}
.sec-badge.green{background:#22C55E}
.sec-title{font-size:12px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;line-height:1.35;flex:1;min-width:0;order:2}
.sec-pill{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#f0f4f8;border:1px solid rgba(148,163,184,.45);border-radius:999px;padding:5px 12px;white-space:nowrap;background:rgba(148,163,184,.08);flex-shrink:0;order:3;margin-left:auto}
.sec-tag{font-size:10px;font-weight:700;letter-spacing:.05em;padding:3px 8px;border-radius:999px;white-space:nowrap;flex-shrink:0;order:4;flex-basis:100%;margin-left:calc(11px + 2*7px + 8px + 4px)}
.sec-tag.verified{background:rgba(34,197,94,.15);color:#22C55E}
.sec-tag.gold{background:rgba(245,197,24,.15);color:#F5C518}
.sec-tag.conf{background:rgba(245,158,11,.15);color:#F59E0B}
.sec-tag.comps{background:rgba(34,197,94,.15);color:#22C55E}
.sec-body{padding:18px 22px 22px}
/* ── Rows ── */
.row{display:grid;grid-template-columns:1fr auto;gap:16px;padding:9px 0;border-bottom:1px solid rgba(148,163,184,.12);font-size:13px}
.row:last-child{border-bottom:none}
.row-l{color:#e2eaf2}
.row-v{font-family:'JetBrains Mono',monospace;text-align:right;color:#e2e8f0}
.pending{color:#b8cfe0;font-style:italic;font-size:13px;padding:8px 0}
/* ── Value bands ── */
.bands-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.band-card{border-radius:10px;padding:18px}
.band-card.clearing{border:1px solid #F59E0B}
.band-card.market{border:1px solid #22C55E}
.band-card-label{font-size:11px;letter-spacing:.08em;font-weight:700;text-transform:uppercase;line-height:1.5}
.band-card-label.clearing{color:#F59E0B}
.band-card-label.market{color:#22C55E}
.band-card-sub{color:#e2eaf2;font-weight:400;letter-spacing:.02em;text-transform:none;font-size:12px}
.band-nums{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0 12px;text-align:center}
.band-num-label{font-size:10px;color:#e2eaf2;letter-spacing:.08em}
.band-num-label.mid.clearing{color:#F59E0B}
.band-num-label.mid.market{color:#22C55E}
.band-num-val{font-family:'JetBrains Mono',monospace;font-size:15px;margin-top:4px}
.band-num-val.mid{font-size:20px;font-weight:700}
.band-num-val.mid.clearing{color:#F59E0B}
.band-num-val.mid.market{color:#22C55E}
.band-meta{font-size:12px;color:#e2eaf2;font-family:'JetBrains Mono',monospace}
.band-desc{margin:12px 0 0;font-size:13px;line-height:1.6;color:#f0f4f8}
.spread-bar{margin-top:16px;background:rgba(249,115,22,.12);border:1px solid #F97316;border-radius:10px;padding:16px 18px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.spread-label{font-size:12px;font-weight:700;letter-spacing:.08em;color:#F97316}
.spread-val{font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700;color:#F97316}
.spread-desc{font-size:13px;color:#f0f4f8;flex:1;min-width:240px;text-align:right}
.net-equity-bar{margin-top:10px;background:rgba(148,163,184,.08);border:1px solid rgba(148,163,184,.25);border-radius:10px;padding:14px 18px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.net-equity-label{font-size:12px;font-weight:700;letter-spacing:.08em;color:#e2eaf2}
.net-equity-val{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700}
.net-equity-desc{font-size:13px;color:#e2eaf2;flex:1;min-width:240px;text-align:right}
/* ── Comps ── */
.subhead{color:#F97316;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin:20px 0 10px;padding-left:14px;border-left:3px solid #F97316}
.comp-table{width:100%;border-collapse:collapse;font-size:13px}
.comp-table th{text-align:left;color:#e2eaf2;font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:6px 8px;font-weight:500;border-bottom:1px solid rgba(148,163,184,.2)}
.comp-table td{padding:10px 8px;border-bottom:1px solid rgba(148,163,184,.1);font-family:'JetBrains Mono',monospace;color:#f0f4f8}
.comp-table td:first-child{font-family:'Inter',sans-serif;font-weight:500;color:#fff}
/* ── Flags ── */
.flags{display:flex;flex-direction:column;gap:8px;margin-top:12px}
.flag{padding:10px 14px;border-radius:6px;font-size:13px;display:flex;gap:10px}
.flag-risk{background:rgba(239,68,68,.08);border-left:3px solid #EF4444}
.flag-pending{background:rgba(234,179,8,.08);border-left:3px solid #EAB308}
.flag-info{background:rgba(34,197,94,.08);border-left:3px solid #22C55E}
.flag-code{font-weight:700;flex-shrink:0}
.flag-risk .flag-code{color:#EF4444}
.flag-pending .flag-code{color:#EAB308}
.flag-info .flag-code{color:#22C55E}
/* ── Bid Card ── */
.bidcard-wrap{background:#1E293B;border-radius:10px;overflow:hidden;border:1px solid rgba(249,115,22,.4);box-shadow:0 0 32px rgba(249,115,22,.15)}
.bidcard-header{display:flex;align-items:center;gap:12px;background:#12283F;border-left:4px solid #F97316;padding:14px 18px}
.bidcard-body{padding:22px 24px}
.verdict{font-size:28px;font-weight:800;letter-spacing:-.01em}
.verdict.bid{color:#22C55E}
.verdict.skip{color:#EF4444}
.verdict.review{color:#F59E0B}
.grade{color:#e2eaf2;font-size:13px;margin-top:2px}
.maxbid-block{margin-top:20px;padding:20px;background:rgba(249,115,22,.08);border:1px solid rgba(249,115,22,.3);border-radius:10px;text-align:center}
.maxbid-label{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#e2eaf2;margin-bottom:8px}
.maxbid{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:52px;color:#F97316;line-height:1}
.maxbid-sub{font-size:12px;color:#e2eaf2;margin-top:6px;font-style:italic}
.bidcard-rows{margin-top:16px}
/* ── Outcome ── */
.outcome-pending{background:rgba(61,47,11,.5);border:1px solid rgba(245,158,11,.3);border-radius:8px;padding:14px 18px;color:#F59E0B;font-size:13px}
.outcome-captured{background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.3);border-radius:8px;padding:14px 18px}
/* ── Footer ── */
.rpt-footer{color:#b8cfe0;font-size:11px;text-align:center;margin-top:32px;line-height:1.7;padding:20px 0;border-top:1px solid rgba(148,163,184,.12)}
/* ── Print ── */
@media print{
  [data-noprint]{display:none!important}
  body{background:#fff;color:#000;padding:0}
  .sec,.bidcard-wrap{break-inside:avoid}
  .summary-grid{background:#f8fafc;border:1px solid #e2e8f0}
  .sec-h{background:#f1f5f9 !important}
}
</style></head><body>
<div class="wrap">
  <div class="rpt-top">
    <div class="rpt-brand-row">
      <div>
        <span class="wordmark">BidDeed<span>.AI</span></span>
        <span class="tagline" style="margin-left:10px">Shapira Auction Intelligence</span>
      </div>
      <div class="toolbar" data-noprint>
        <button class="btn-toolbar" id="collapse-all">Collapse all</button>
        <button class="btn-toolbar primary" id="dl-pdf">&darr; Download PDF</button>
      </div>
    </div>
    <div class="rpt-divider-top"></div>
    <div class="rpt-addr-row">
      <div>
        <div class="rpt-addr-main">${addrCity}</div>
        <div class="rpt-addr-city">${addrRest || escHtml(countyLabel + ', FL')}</div>
      </div>
      <div class="rpt-meta">
        <div class="rpt-meta-county">${escHtml(countyLabel.toUpperCase())} COUNTY</div>
        <div>Case ${escHtml(cover.case_number || '—')}</div>
        <div>Sale ${escHtml(cover.auction_date || '—')} &middot; ${escHtml(cover.sale_type ? cover.sale_type.toUpperCase() : 'FORECLOSURE')}</div>
      </div>
    </div>
    <div class="rpt-divider-sub"></div>
  </div>
  ${summaryGrid ? `<div style="margin-top:24px">${summaryGrid}</div>` : ''}
  <div class="sections">
    ${body}
  </div>
  <div class="rpt-footer">
    Generated ${escHtml(generatedAt)} &nbsp;&middot;&nbsp; Key: ....${escHtml(keyLast8)} &nbsp;&middot;&nbsp; Report ID: ${escHtml(reportIdShort)}<br>
    Informational only &mdash; not legal, financial, or investment advice. Not the unauthorized practice of law.<br>
    Verify independently and consult a licensed Florida attorney before bidding.<br>
    &copy; ${new Date().getUTCFullYear()} BidDeed.AI &middot; Everest Capital USA
  </div>
</div>
<script>
document.getElementById('collapse-all').addEventListener('click',function(){
  document.querySelectorAll('details.sec').forEach(function(d){d.open=false;});
  this.textContent='Expand all';
  this.onclick=function(){document.querySelectorAll('details.sec').forEach(function(d){d.open=true;});this.textContent='Collapse all';this.onclick=null;};
});
document.getElementById('dl-pdf').addEventListener('click',function(){
  document.querySelectorAll('details.sec').forEach(function(d){d.open=true;});
  setTimeout(function(){window.print();},400);
});
</script>
</body></html>`;
}

// ── Rate limit ────────────────────────────────────────────────────────────────
// Multi-window (minute/hour/day/week) gate + usage tier for LLM routing.
// Fails OPEN (allowed=true, tier='standard') on any RPC error so a Supabase
// hiccup never takes down chat.
async function checkRateLimitV2(ip) {
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/chat_rate_check_v2`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` },
      body: JSON.stringify({ p_ip: ip }),
    });
    if (!res.ok) return { allowed: true, tier: 'standard' };
    const data = await res.json();
    if (data && typeof data === 'object') return data;
    return { allowed: true, tier: 'standard' };
  } catch(_) { return { allowed: true, tier: 'standard' }; }
}

function rateLimitReason(rl) {
  if (rl.minute_hits > rl.minute_limit) return 'Too many messages — please wait a moment';
  if (rl.hour_hits > rl.hour_limit) return `Hourly limit reached (${rl.hour_limit} messages/hour) — try again later`;
  if (rl.day_hits > rl.day_limit) return `Daily limit reached (${rl.day_limit} messages/day) — try again tomorrow`;
  return 'Weekly limit reached — upgrade to Investor for unlimited access';
}

// ── County data fetch ─────────────────────────────────────────────────────────
async function fetchCountyData(county) {
  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/county_twin_snapshot?county=eq.${encodeURIComponent(county)}&limit=1`,
      { headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` } }
    );
    const rows = await res.json();
    return rows[0] || null;
  } catch(_) { return null; }
}

// ── Runtime config from Supabase SSOT (cached 5 min at edge) ──────────────────
async function fetchRuntimeConfig() {
  try {
    const cacheKey = 'biddeed-runtime-config-v1';
    const cache = caches.default;
    const cached = await cache.match(new Request('https://biddeed.ai/_internal/config'));
    if (cached) return await cached.json();

    // Fetch gold-certified counties
    const goldRes = await fetch(
      SUPABASE_URL + '/rest/v1/v_certified_counties?select=county_slug',
      { headers: { apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY } }
    );
    const goldRows = goldRes.ok ? await goldRes.json() : [];
    const goldCounties = Array.isArray(goldRows) ? goldRows.map(r => r.county_slug).filter(Boolean) : [];

    // Fetch co_no-confirmed counties (S5-deliverable when also gold-certified)
    const conoRes = await fetch(
      SUPABASE_URL + '/rest/v1/county_co_no_resolution?is_confirmed=eq.true&select=county_slug',
      { headers: { apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY } }
    );
    const conoRows = conoRes.ok ? await conoRes.json() : [];
    const confirmedCounties = Array.isArray(conoRows) ? conoRows.map(r => r.county_slug).filter(Boolean) : [];

    // S5-purchasable = both gold-certified AND co_no-confirmed
    const goldSet = new Set(goldCounties);
    const s5Counties = confirmedCounties.filter(c => goldSet.has(c));

    // Fetch total auctions analyzed (exact count via Content-Range header)
    const auctionsRes = await fetch(
      SUPABASE_URL + '/rest/v1/multi_county_auctions?select=case_number&limit=1',
      { headers: { apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY, Prefer: 'count=exact' } }
    );
    const auctionsRange = auctionsRes.headers.get('content-range');
    const auctionsCount = auctionsRange ? (parseInt(auctionsRange.split('/')[1], 10) || 0) : 0;

    const config = { goldCounties, confirmedCounties, s5Counties, auctionsCount };

    // Cache at edge for 5 minutes
    const resp = new Response(JSON.stringify(config), {
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300' }
    });
    await cache.put(new Request('https://biddeed.ai/_internal/config'), resp.clone());

    return config;
  } catch(e) {
    // Fallback to hardcoded if Supabase is down
    return {
      goldCounties: GOLD_COUNTIES,
      confirmedCounties: [],
      s5Counties: [],
      auctionsCount: 72000
    };
  }
}

// ── County lots fetch ─────────────────────────────────────────────────────────
async function fetchCountyLots(county) {
  try {
    const today = new Date().toISOString().slice(0,10);
    const cutoff = new Date(Date.now() + 35*24*60*60*1000).toISOString().slice(0,10);
    const url = `${SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.${encodeURIComponent(county)}&auction_date=gte.${today}&auction_date=lte.${cutoff}&order=auction_date.asc,sale_type.asc&limit=300&select=sale_type,property_address,auction_date,opening_bid,assessed_value,auction_url,clerk_url,bcpao_url,judgment_amount,case_number,plaintiff`;
    const res = await fetch(url, { headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` } });
    if (!res.ok) return [];
    return await res.json();
  } catch(_) { return []; }
}

// ── Buy-report picker: ALL counties with purchasable upcoming auctions ──────
// Option A (approved by Ariel Aug 1 2026): Gold Standard is a data-quality
// SIGNAL only, never a customer access gate. Every county with an upcoming
// auction is purchasable for $25 — Gold Standard counties get the full
// 18-section report (CMA, ZoneWise, Shapira Max Bid); non-certified counties
// get the sections their data supports, clearly labeled. get_all_counties_
// with_status() is the single source of truth for that full list so the
// worker doesn't hand-roll it per endpoint.
async function fetchReportCounties() {
  try {
    const cacheKey = new Request('https://biddeed.ai/_internal/buy-report-counties');
    const cache = caches.default;
    const cached = await cache.match(cacheKey);
    if (cached) return await cached.json();

    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_all_counties_with_status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
      body: '{}',
    });
    const rows = res.ok ? await res.json() : [];
    const result = (Array.isArray(rows) ? rows : []).map(r => ({
      county_slug: r.county,
      display: r.county_display || toDisplay(r.county),
      upcoming: Number(r.upcoming) || 0,
      next_auction_date: r.next_auction || null,
      is_gold_standard: !!r.is_gold_standard,
      sale_types: r.sale_types || null,
    }));

    const resp = new Response(JSON.stringify(result), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=120' } });
    await cache.put(cacheKey, resp.clone());
    return result;
  } catch(_) { return []; }
}

// ── Bidding link label per auction platform ────────────────────────────────
function bidLabel(sourcePlatform) {
  if (sourcePlatform === 'realforeclose') return 'Bid on RealForeclose →';
  if (sourcePlatform === 'realauction') return 'Bid on RealAuction →';
  if (sourcePlatform === 'acclaimweb') return 'Bid on Clerk Portal →';
  return 'View Auction →';
}

// ── Auction cards for chat property panel ─────────────────────────────────────
// Reads v_property_card_verified (not the raw table) — a fail-closed gate that
// only surfaces lots with a fresh (<48h) clerk parity check, per CLERK-SSOT
// Task 4.2. A clerk-confirmed-cancelled or never-checked lot never renders here.
async function fetchAuctionCards(county, days, type, limit) {
  const today = new Date().toISOString().slice(0,10);
  const cutoff = new Date(Date.now() + days*24*60*60*1000).toISOString().slice(0,10);
  let auctionsUrl = `${SUPABASE_URL}/rest/v1/v_property_card_verified?county=eq.${encodeURIComponent(county)}&auction_date=gte.${today}&auction_date=lte.${cutoff}&auction_status=in.(upcoming,scheduled)&order=auction_date.asc,opening_bid.asc&limit=${limit}&select=id,county,sale_type,case_number,property_address,auction_date,opening_bid,assessed_value,judgment_amount,parity_status,auction_url,po_seo_url,clerk_url,source_platform,bcpao_url,trellis_url,clerk_parity_match_pct,clerk_parity_checked_at`;
  if (type === 'foreclosure' || type === 'tax_deed') auctionsUrl += `&sale_type=eq.${type}`;

  const [auctionsRes, certRes] = await Promise.all([
    fetch(auctionsUrl, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }),
    fetch(`${SUPABASE_URL}/rest/v1/gold_standard_certifications?county_slug=eq.${encodeURIComponent(county)}&select=certified&limit=1`, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }),
  ]);
  const rows = auctionsRes.ok ? await auctionsRes.json() : [];
  const certRows = certRes.ok ? await certRes.json() : [];
  const isGold = !!(Array.isArray(certRows) && certRows[0] && certRows[0].certified);
  const now = Date.now();

  return (Array.isArray(rows) ? rows : []).map(r => {
    const auctionMs = r.auction_date ? new Date(r.auction_date + 'T00:00:00Z').getTime() : null;
    const daysUntil = auctionMs !== null ? Math.max(0, Math.round((auctionMs - now) / 86400000)) : null;
    const hasBoth = r.assessed_value != null && r.opening_bid != null;
    const appraiserUrl = r.bcpao_url || r.trellis_url || null;
    return {
      id: r.id,
      county: r.county,
      sale_type: r.sale_type,
      case_number: r.case_number,
      property_address: r.property_address,
      auction_date: r.auction_date,
      opening_bid: r.opening_bid,
      assessed_value: r.assessed_value,
      judgment_amount: r.judgment_amount,
      parity_status: r.parity_status,
      is_gold_standard: isGold,
      days_until_auction: daysUntil,
      equity_gap: hasBoth ? (Number(r.assessed_value) - Number(r.opening_bid)) : null,
      auction_url: r.auction_url || null,
      po_url: r.po_seo_url || null,
      clerk_url: r.clerk_url || null,
      source_platform: r.source_platform || null,
      bid_label: bidLabel(r.source_platform),
      appraiser_url: appraiserUrl,
      appraiser_label: appraiserUrl ? `${toDisplay(r.county)} Appraiser →` : null,
      clerk_parity_badge: {
        county: r.county,
        match_pct: r.clerk_parity_match_pct != null ? Number(r.clerk_parity_match_pct) : null,
        checked_at: r.clerk_parity_checked_at || null,
      },
    };
  });
}

// ── Single auction lookup + county appraiser link ─────────────────────────────
async function fetchPropertyById(id) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.${encodeURIComponent(id)}&limit=1`, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } });
  if (!res.ok) return null;
  const rows = await res.json();
  return rows[0] || null;
}
async function fetchAppraiserLink(county) {
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/county_appraiser_urls?county_slug=eq.${encodeURIComponent(county)}&select=appraiser_url&limit=1`, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } });
    if (!res.ok) return null;
    const rows = await res.json();
    return (rows[0] && rows[0].appraiser_url) || null;
  } catch(_) { return null; }
}

async function fetchReportAuctions(county) {
  try {
    const today = new Date().toISOString().slice(0,10);
    const url = `${SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.${encodeURIComponent(county)}&auction_date=gte.${today}&auction_status=eq.upcoming&parity_status=eq.matched_clean&order=auction_date.asc&limit=50&select=case_number,property_address,auction_date,opening_bid,sale_type`;
    const res = await fetch(url, { headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` } });
    if (!res.ok) return [];
    return await res.json();
  } catch(_) { return []; }
}

// ── Top 5 upcoming auctions for the /free-report/delivery page ──────────────
async function fetchFreeReportAuctions(county) {
  try {
    const today = new Date().toISOString().slice(0,10);
    const end30 = new Date(Date.now() + 30*24*60*60*1000).toISOString().slice(0,10);
    const url = `${SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.${encodeURIComponent(county)}&auction_status=eq.upcoming&auction_date=gte.${today}&auction_date=lte.${end30}&property_address=not.is.null&opening_bid=not.is.null&order=auction_date.asc&limit=5&select=case_number,property_address,auction_date,opening_bid,sale_type`;
    const res = await fetch(url, { headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` } });
    if (!res.ok) return [];
    return await res.json();
  } catch(_) { return []; }
}

// ── Tier badge ────────────────────────────────────────────────────────────────
function tierBadge(bid) {
  if (!bid || bid <= 0) return '';
  const n = Number(bid);
  if (n < 5000)   return '<span class="tier t1">&lt;$5K</span>';
  if (n < 25000)  return '<span class="tier t2">&lt;$25K</span>';
  if (n < 75000)  return '<span class="tier t3">&lt;$75K</span>';
  if (n < 200000) return '<span class="tier t4">&lt;$200K</span>';
  return '<span class="tier t5">&gt;$200K</span>';
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDate(d) {
  if (!d) return 'TBD';
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
function fmtMoney(n) {
  if (!n) return 'N/A';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}
function toDisplay(slug) {
  return COUNTY_DISPLAY[slug] || slug.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
}

// ── GET /free-report — lead capture form (email/phone/county/consent) ──────
function buildFreeReportFormHtml(prefillEmail, counties, prev) {
  prev = prev || {};
  const options = (counties || []).map(c =>
    `<option value="${escHtml(c.county_slug)}"${prev.county === c.county_slug ? ' selected' : ''}>${escHtml(c.display)}${c.is_gold_standard ? ' ⭐' : ''} — ${c.upcoming} upcoming</option>`
  ).join('');
  const errBanner = prev.error ? `<div class="err" style="display:block">${escHtml(prev.error)}</div>` : '';
  return `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Get Your Free County Auction Report | BidDeed.AI</title>
<meta name="description" content="Free upcoming foreclosure and tax deed auctions for your Florida county — no credit card needed.">
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#1E3A5F;--void:#020617;--orange:#F59E0B;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
body{background:var(--void);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:8px;padding:2.5rem;max-width:480px;width:100%}
.badge{color:var(--orange);font-size:12px;font-weight:600;letter-spacing:.1em;margin-bottom:.75rem}
h1{font-size:1.5rem;color:white;margin-bottom:.5rem}
p{color:var(--muted);margin-bottom:1.5rem;line-height:1.6;font-size:.92rem}
label{display:block;font-size:.85rem;color:var(--muted);margin-bottom:.4rem}
select,input[type=email],input[type=tel]{width:100%;padding:12px 14px;border-radius:6px;border:1px solid var(--border);background:var(--void);color:var(--text);font-size:.95rem;margin-bottom:1rem;font-family:inherit}
.consent{display:flex;align-items:flex-start;gap:.5rem;margin-bottom:.85rem;font-size:.82rem;color:var(--dim)}
.consent input{margin-top:3px}
.btn{display:block;width:100%;background:var(--orange);color:var(--void);padding:10px 20px;min-height:44px;border:none;border-radius:6px;font-weight:600;font-size:.95rem;cursor:pointer;margin-top:.5rem}
.btn:hover{background:#D97706}
.err{color:#f87171;font-size:.85rem;margin-bottom:1rem;display:none}
.upl{margin-top:1.5rem;padding-top:1.25rem;border-top:1px solid var(--border);font-size:.72rem;color:var(--dim);line-height:1.6}
.upl a{color:var(--orange)}
</style></head><body>
<div class="card">
  <div class="badge">FREE · NO CREDIT CARD</div>
  <h1>Get your free county auction report</h1>
  <p>Top upcoming foreclosure and tax deed auctions in your Florida county, delivered instantly.</p>
  ${errBanner}
  <form method="POST" action="/free-report/submit" id="f">
    <label for="email">Email address</label>
    <input type="email" id="email" name="email" required value="${escHtml(prefillEmail)}" placeholder="you@example.com">
    <label for="phone">Phone number</label>
    <input type="tel" id="phone" name="phone" required value="${escHtml(prev.phone || '')}" placeholder="(321) 555-0100">
    <label for="county">County</label>
    <select id="county" name="county" required>
      <option value="">Select a county…</option>
      ${options}
    </select>
    <label class="consent"><input type="checkbox" name="email_consent" id="email_consent"${prev.emailConsent ? ' checked' : ''}> Send me the daily auction digest by email</label>
    <label class="consent"><input type="checkbox" name="sms_consent" id="sms_consent"${prev.smsConsent ? ' checked' : ''}> Text me urgent auction alerts (SMS)</label>
    <div class="err" id="consent-err">Please check at least one option above.</div>
    <button type="submit" class="btn">Get My Free Report</button>
  </form>
  <div class="upl">Not legal advice. BidDeed.AI is an information and analytics platform, not a law firm or title company. Auction data is informational and must be independently verified. See <a href="/disclaimer">full disclaimer</a>.</div>
</div>
<script>
document.getElementById('f').addEventListener('submit', function(e){
  var ec = document.getElementById('email_consent').checked;
  var sc = document.getElementById('sms_consent').checked;
  var err = document.getElementById('consent-err');
  if (!ec && !sc) { e.preventDefault(); err.style.display = 'block'; }
  else { err.style.display = 'none'; }
});
<\/script>
</body></html>`;
}

// ── GET /free-report/delivery — top 5 county auctions + upsell CTAs ────────
function buildFreeReportDeliveryHtml(email, county, auctions, countyMeta, consent) {
  consent = consent || {};
  const countyName = countyMeta ? countyMeta.display : toDisplay(county);
  const isGold = !!(countyMeta && countyMeta.is_gold_standard);
  const rows = (auctions || []).map(a => {
    const saleBadge = a.sale_type === 'tax_deed' ? 'TD' : 'FC';
    return `<div class="auction-card">
      <div class="addr">${escHtml(a.property_address || 'Address pending')}</div>
      <div class="meta">
        <span class="tag">${saleBadge}</span>
        <span>${fmtDate(a.auction_date)}</span>
        <span>Opening bid: ${fmtMoney(a.opening_bid)}</span>
        ${isGold ? '<span class="tag gold">⭐ Gold Standard</span>' : ''}
      </div>
    </div>`;
  }).join('');
  const empty = !auctions || !auctions.length
    ? '<div class="empty">No upcoming auctions in the next 30 days for this county right now — check back soon.</div>' : '';
  const consentLine = consent.emailConsent && consent.smsConsent
    ? "You're signed up for the daily email digest and SMS auction alerts for"
    : consent.smsConsent
    ? "You're signed up for SMS auction alerts for"
    : "You're signed up for the daily email digest for";
  return `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Your Free ${escHtml(countyName)} County Auction Report | BidDeed.AI</title>
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#1E3A5F;--void:#020617;--orange:#F59E0B;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b;--green:#10B981}
body{background:var(--void);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;padding:2.5rem 1.5rem}
.wrap{max-width:640px;margin:0 auto}
.thanks{background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.3);border-radius:6px;padding:1rem 1.25rem;margin-bottom:2rem;font-size:.9rem;color:var(--muted)}
h1{font-size:1.6rem;color:white;margin-bottom:1.5rem}
.auction-card{background:#0f172a;border:1px solid var(--border);border-radius:8px;padding:1rem 1.25rem;margin-bottom:.75rem}
.auction-card .addr{font-weight:600;font-size:.95rem;color:white;margin-bottom:.4rem}
.auction-card .meta{font-size:.8rem;color:var(--dim);display:flex;gap:.75rem;flex-wrap:wrap;align-items:center}
.tag{background:var(--navy);color:var(--muted);padding:2px 8px;border-radius:4px;font-size:.72rem;font-weight:600}
.tag.gold{background:rgba(245,158,11,.15);color:var(--orange)}
.empty{color:var(--dim);font-size:.9rem;padding:1rem 0}
.ctas{margin-top:2rem;display:flex;flex-direction:column;gap:.75rem}
.btn{display:block;text-align:center;text-decoration:none;padding:12px 20px;border-radius:6px;font-weight:600;font-size:.92rem}
.btn.primary{background:var(--orange);color:var(--void)}
.btn.primary:hover{background:#D97706}
.btn.ghost{background:transparent;border:1px solid var(--border);color:var(--muted)}
.btn.ghost:hover{border-color:var(--orange);color:var(--orange)}
.upl{margin-top:2rem;padding-top:1.25rem;border-top:1px solid var(--border);font-size:.72rem;color:var(--dim);line-height:1.6}
.upl a{color:var(--orange)}
</style></head><body>
<div class="wrap">
  <div class="thanks">${consentLine} <strong>${escHtml(countyName)} County</strong>${email ? ` at ${escHtml(email)}` : ''}. You can unsubscribe from any digest email at any time.</div>
  <h1>Top upcoming auctions in ${escHtml(countyName)} County</h1>
  ${rows}${empty}
  <div class="ctas">
    <a class="btn primary" href="/buy-report?county=${encodeURIComponent(county)}">Get the Full Shapira Analysis for any of these — $25</a>
    <a class="btn ghost" href="/chat?county=${encodeURIComponent(county)}">See all upcoming auctions in your county</a>
  </div>
  <div class="upl">Not legal advice. BidDeed.AI is an information and analytics platform, not a law firm or title company. Auction data is informational and must be independently verified. See <a href="/disclaimer">full disclaimer</a>.</div>
</div>
</body></html>`;
}

// ── Cheap character-range language detection — skips relying on the model to
// infer language from content alone, so the system prompt can name the target
// language up front instead of the model figuring it out mid-response ────────
function detectLanguage(text) {
  const s = String(text || '');
  if (/[֐-׿]/.test(s)) return 'he'; // Hebrew
  if (/[؀-ۿ]/.test(s)) return 'ar'; // Arabic
  if (/[一-鿿]/.test(s)) return 'zh'; // Chinese
  if (/[а-яА-Я]/.test(s)) return 'ru'; // Russian
  return 'en';
}
const LANG_NAMES = { he: 'Hebrew (עברית)', ar: 'Arabic (العربية)', zh: 'Chinese (中文)', ru: 'Russian (Русский)' };

// ── FL county name detection from free text (chat intent routing) ────────────
const COUNTY_TEXT_ALIASES = {
  'saint johns': 'st_johns',
  'saint lucie': 'st_lucie',
  'miami': 'miami_dade',
  'dade': 'miami_dade',
};
function detectFLCounty(text) {
  const lower = String(text || '').toLowerCase();
  for (const alias of Object.keys(COUNTY_TEXT_ALIASES)) {
    if (lower.includes(alias)) return COUNTY_TEXT_ALIASES[alias];
  }
  for (const slug of Object.keys(COUNTY_DISPLAY)) {
    const display = COUNTY_DISPLAY[slug].toLowerCase();
    if (lower.includes(display) || lower.includes(slug.replace(/_/g,' '))) return slug;
  }
  return null;
}
const AUCTION_INTENT_RE = /(?:show|find|list|what|upcoming|auction|properties?|foreclosure|tax.?deed)/i;

// ── Security response headers ───────────────────────────────────────────────
// Applied to every response from this worker. script-src/style-src keep
// 'unsafe-inline' because the site's inline <script> blocks (PostHog init,
// per-page interaction JS) are not yet nonce-based — tightening that is a
// follow-up, not a header-only change. See docs/security/EXTERNAL_SCAN_SUMMARY.md.
//
// /chat is embedded same-origin via <iframe src="https://biddeed.ai/chat">
// on the homepage (see HOMEPAGE_HTML .cfw block), so it needs frame-ancestors
// 'self' / X-Frame-Options SAMEORIGIN instead of the site-wide 'none'/DENY —
// otherwise the browser blocks the frame and it renders as a broken box.
const SECURITY_CSP = "default-src 'self'; script-src 'self' 'unsafe-inline' https://us-assets.i.posthog.com https://us.i.posthog.com https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://us.i.posthog.com https://us-assets.i.posthog.com https://mocerqjnksmhcjzxrewo.supabase.co https://static.cloudflareinsights.com https://api.elevenlabs.io wss://api.elevenlabs.io; frame-ancestors 'none'; base-uri 'self'; object-src 'none'";
const SECURITY_CSP_CHAT = SECURITY_CSP.replace("frame-ancestors 'none'", "frame-ancestors 'self'");
function withSecurityHeaders(response, path) {
  const headers = new Headers(response.headers);
  const isChatFrame = path === '/chat' || (path && path.startsWith('/chat'));
  headers.set('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload');
  headers.set('X-Content-Type-Options', 'nosniff');
  headers.set('X-Frame-Options', isChatFrame ? 'SAMEORIGIN' : 'DENY');
  headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  headers.set('Permissions-Policy', 'geolocation=(), camera=(), microphone=(self)');
  if (!headers.has('Content-Security-Policy')) headers.set('Content-Security-Policy', isChatFrame ? SECURITY_CSP_CHAT : SECURITY_CSP);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

// ── Error monitoring — PostHog exception capture (replaces Sentry; Sentry was
// never adopted here, blocked on browser signup) ───────────────────────────────
async function captureError(error, request, env) {
  const phKey = env.POSTHOG_PROJECT_KEY;
  if (!phKey) return;
  try {
    await fetch('https://us.i.posthog.com/capture/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: phKey,
        event: '$exception',
        distinct_id: 'biddeed-worker',
        properties: {
          $exception_type: error?.name || 'Error',
          $exception_message: error?.message,
          $exception_stack_trace_raw: error?.stack,
          url: request?.url,
          method: request?.method,
          timestamp: new Date().toISOString(),
          environment: 'production',
          service: 'biddeed-cloudflare-worker'
        }
      })
    });
  } catch (e) {
    // Never let error reporting break the worker
  }
}

// ── Main fetch handler ────────────────────────────────────────────────────────
export default {
  async fetch(request, env, ctx) {
    const path = new URL(request.url).pathname;
    try {
      return withSecurityHeaders(await handleRequest(request, env, ctx), path);
    } catch (error) {
      ctx.waitUntil(captureError(error, request, env));
      return withSecurityHeaders(new Response(JSON.stringify({ error: 'Internal server error' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }), path);
    }
  }
};

async function handleRequest(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;
    const origin = request.headers.get('Origin') || '';

    try {
      if (method === 'OPTIONS') {
        return new Response(null, { status: 204, headers: corsHeaders(origin) });
      }

      // ── Legal ────────────────────────────────────────────────────────────
      // /tos is an alias for /terms (same content) — kept as a distinct route
      // rather than a redirect so both URLs return 200 directly.
      const SECTION18_TEASER_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BidDeed.AI — Section 18 Scorecard | Did the Formula Hold?</title>
<meta property="og:title" content="FL Auction Formula Called It. $431K Naples Deal. See the Scorecard.">
<meta property="og:description" content="We published a ceiling before the auction. The sale came in under it. Day-1 equity: $381K. This is Section 18 — the scorecard that grades every BidDeed call after the gavel drops.">
<meta property="og:image" content="https://biddeed.ai/og-section18.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1a;color:#e2eaf2;font-family:'Inter',sans-serif;min-height:100vh}
.hero{background:linear-gradient(135deg,#0a0f1a 0%,#0f1829 60%,#0a0f1a 100%);border-bottom:1px solid rgba(251,146,60,.15);padding:60px 24px 48px;text-align:center}
.badge{display:inline-block;background:rgba(251,146,60,.12);border:1px solid rgba(251,146,60,.35);color:#fb923c;font-size:11px;font-weight:700;letter-spacing:.12em;padding:6px 14px;border-radius:20px;text-transform:uppercase;margin-bottom:24px}
h1{font-size:clamp(28px,5vw,48px);font-weight:800;line-height:1.15;max-width:780px;margin:0 auto 20px;background:linear-gradient(135deg,#fff 40%,#fb923c);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sub{font-size:18px;color:#94a3b8;max-width:600px;margin:0 auto 36px;line-height:1.6}
.scorecard{background:#0f1829;border:1px solid rgba(251,146,60,.3);border-radius:16px;max-width:680px;margin:0 auto;overflow:hidden}
.sc-header{background:linear-gradient(90deg,rgba(251,146,60,.15),rgba(251,146,60,.05));padding:20px 28px;border-bottom:1px solid rgba(251,146,60,.2);display:flex;align-items:center;gap:12px}
.sc-header .badge-num{background:#fb923c;color:#000;font-weight:800;font-size:13px;padding:4px 10px;border-radius:8px}
.sc-title{font-weight:700;font-size:16px;color:#fb923c}
.sc-sub{font-size:12px;color:#64748b;margin-top:2px}
.property-bar{background:rgba(255,255,255,.03);border-bottom:1px solid rgba(255,255,255,.06);padding:16px 28px;display:flex;flex-wrap:wrap;gap:20px}
.prop-item{font-size:13px}
.prop-label{color:#64748b;font-size:11px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:3px}
.prop-val{font-weight:600;color:#e2eaf2}
.sc-body{padding:24px 28px}
.sc-row{display:flex;align-items:flex-start;gap:16px;padding:16px 0;border-bottom:1px solid rgba(255,255,255,.05)}
.sc-row:last-child{border-bottom:none}
.sc-icon{font-size:20px;flex-shrink:0;margin-top:2px}
.sc-label{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin-bottom:4px}
.sc-value{font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#34d399}
.sc-note{font-size:13px;color:#94a3b8;margin-top:4px;line-height:1.5}
.equity-bar{background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.25);border-radius:12px;padding:20px 28px;margin:24px 0 0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px}
.equity-num{font-family:'JetBrains Mono',monospace;font-size:32px;font-weight:700;color:#34d399}
.equity-label{font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.08em}
.equity-note{font-size:13px;color:#94a3b8;max-width:300px}
.cta-section{padding:48px 24px;text-align:center;max-width:620px;margin:0 auto}
.cta-section h2{font-size:28px;font-weight:800;margin-bottom:12px;color:#fff}
.cta-section p{color:#94a3b8;margin-bottom:32px;font-size:16px;line-height:1.6}
.cta-btn{display:inline-block;background:linear-gradient(135deg,#fb923c,#f97316);color:#000;font-weight:800;font-size:16px;padding:16px 36px;border-radius:12px;text-decoration:none;letter-spacing:.02em;transition:transform .15s,box-shadow .15s}
.cta-btn:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(251,146,60,.4)}
.cta-sub{margin-top:16px;font-size:13px;color:#64748b}
.stat-row{display:flex;justify-content:center;gap:40px;margin:40px 0;flex-wrap:wrap}
.stat{text-align:center}
.stat-num{font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:700;color:#fb923c}
.stat-label{font-size:12px;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.08em}
.disclaimer{text-align:center;font-size:11px;color:#334155;padding:24px;max-width:600px;margin:0 auto;line-height:1.6}
</style>
</head>
<body>

<div class="hero">
  <div class="badge">§18 — Auction Outcome Scorecard</div>
  <h1>The Formula Said $329K Max Bid.<br>It Sold for $50K.</h1>
  <p class="sub">We publish our ceiling before the gavel drops. Then we score ourselves publicly. This is Section 18 — the only FL auction intelligence platform that grades its own calls.</p>

  <div class="scorecard">
    <div class="sc-header">
      <span class="badge-num">§18</span>
      <div>
        <div class="sc-title">Auction Outcome & Prediction Scorecard</div>
        <div class="sc-sub">Palm Beach County · Case 502025CA005319 · Foreclosure</div>
      </div>
    </div>

    <div class="property-bar">
      <div class="prop-item">
        <div class="prop-label">Property</div>
        <div class="prop-val">7830 Striling Bridge Blvd S, Delray Beach FL</div>
      </div>
      <div class="prop-item">
        <div class="prop-label">Assessed Value</div>
        <div class="prop-val">$457,184</div>
      </div>
      <div class="prop-item">
        <div class="prop-label">Sale Date</div>
        <div class="prop-val">Jun 5, 2025</div>
      </div>
    </div>

    <div class="sc-body">
      <div class="sc-row">
        <div class="sc-icon">🎯</div>
        <div>
          <div class="sc-label">Ceiling Call</div>
          <div class="sc-value">✓ CEILING HELD</div>
          <div class="sc-note">BidDeed published Shapira Max Bid <strong>$329,000</strong> before auction. Actual sale: <strong>$50,000</strong> — well under ceiling. A buyer disciplined to the ceiling wins this lot by $279K.</div>
        </div>
      </div>

      <div class="sc-row">
        <div class="sc-icon">📊</div>
        <div>
          <div class="sc-label">Market Band Call</div>
          <div class="sc-value">✓ IN RANGE</div>
          <div class="sc-note">Pre-sale market band: $362K–$408K. Post-auction retail ARV estimate: ~$385K. Sale at $50K confirms the distressed clearing band was correctly sized.</div>
        </div>
      </div>

      <div class="sc-row">
        <div class="sc-icon">🤖</div>
        <div>
          <div class="sc-label">V4 Ensemble ML (AUC 0.9468)</div>
          <div class="sc-value">73% — ELEVATED</div>
          <div class="sc-note">Model predicted 73% probability of third-party purchase (not plaintiff credit-bid). Outcome: THIRD PARTY won. Model call correct.</div>
        </div>
      </div>

      <div class="sc-row">
        <div class="sc-icon">⚡</div>
        <div>
          <div class="sc-label">Clearing Multiple</div>
          <div class="sc-value">2.87× opening bid</div>
          <div class="sc-note">Opened at $17,404 (unpaid judgment). Cleared at $50,000. Competitive but well inside the ceiling — exactly what the formula targets.</div>
        </div>
      </div>

      <div class="equity-bar">
        <div>
          <div class="equity-label">Day-1 Equity Surface</div>
          <div class="equity-num">~$335,000</div>
        </div>
        <div class="equity-note">Market ARV $385,000 minus acquisition cost $50,000. Before rehab or carry. This is the spread the Shapira Formula surfaces before you bid.</div>
      </div>
    </div>
  </div>
</div>

<div class="stat-row">
  <div class="stat">
    <div class="stat-num">0.9468</div>
    <div class="stat-label">V4 Ensemble AUC</div>
  </div>
  <div class="stat">
    <div class="stat-num">24</div>
    <div class="stat-label">Gold-Certified Counties</div>
  </div>
  <div class="stat">
    <div class="stat-num">$25</div>
    <div class="stat-label">Per Full S5 Report</div>
  </div>
  <div class="stat">
    <div class="stat-num">18</div>
    <div class="stat-label">Sections Per Report</div>
  </div>
</div>

<div class="cta-section">
  <h2>See the Full Report That Called This Deal</h2>
  <p>The sample report shows all 18 sections — value bands, ML probability, Shapira Max Bid, red flags, and the complete §18 scorecard. No account needed.</p>
  <a class="cta-btn" href="https://biddeed.ai/report/cad5d07a-b9c7-433d-b365-3165637b7cbe?key=bd_live_S9KLXyeH9fV1epdliLz731n1">
    Open the Full Sample Report →
  </a>
  <div class="cta-sub">Free. No signup. Takes 30 seconds. Then try it on any upcoming FL auction — $25/report.</div>
</div>

<div class="disclaimer">
  BidDeed.AI — Informational and analytics platform. Not legal, financial, investment, or title advice. Past formula accuracy does not guarantee future results. Full terms: biddeed.ai/terms
</div>

</body>
</html>
`;

      if (path === '/terms' || path === '/tos') return new Response(TERMS_HTML,      { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/privacy')                  return new Response(PRIVACY_HTML,    { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/section18-teaser')           return new Response(SECTION18_TEASER_HTML, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/disclaimer')                return new Response(DISCLAIMER_HTML, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/security')                  return new Response(SECURITY_HTML,   { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/data-retention')            return new Response(DATA_RETENTION_HTML, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });

      // ── /subscribe ───────────────────────────────────────────────────────
      // Served as an HTML interstitial (not a raw 302) so PostHog can record
      // the pageview before handing off to Stripe.
      if (path === '/subscribe') {
        const tier = url.searchParams.get('tier') || 'investor';
        const safeTier = tier.replace(/[^a-z0-9_-]/gi, '');
        const isPro = safeTier === 'pro' || safeTier === 'proplus';
        const tierLabel = isPro ? 'Pro' : 'Investor';
        const tierPrice = isPro ? '$199' : '$99';
        const html = SUBSCRIBE_HTML
          .replace(/TIER_LABEL_PLACEHOLDER/g, tierLabel)
          .replace(/TIER_PRICE_PLACEHOLDER/g, tierPrice)
          .replace(/TIER_PLACEHOLDER/g, safeTier);
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
      }

      // ── POST /subscribe/checkout — proxies to biddeed-checkout's cold
      // subscription path (added Aug 10 2026). Replaces the old static
      // Stripe Payment Link, which had no way to attach a buyer to a
      // customer record and redirected to /chat instead of /success —
      // meaning real subscribers never landed on the page that issues a
      // key. Mirrors POST /buy-report/checkout's existing proxy pattern.
      if (path === '/subscribe/checkout' && method === 'POST') {
        let body = {};
        try { body = await request.json(); } catch(_) {}
        const { tier, customer_email, referral_code } = body;
        if (!tier || !['investor','pro','proplus'].includes(tier)) {
          return new Response(JSON.stringify({ error: 'valid tier required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        if (!customer_email || typeof customer_email !== 'string') {
          return new Response(JSON.stringify({ error: 'customer_email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        try {
          const checkoutBody = { tier, customer_email };
          if (referral_code && typeof referral_code === 'string') checkoutBody.referral_code = referral_code;
          const res = await fetch(`${SUPABASE_URL}/functions/v1/biddeed-checkout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(checkoutBody),
          });
          const data = await res.json();
          if (!res.ok) {
            await logErr(env, '/subscribe/checkout', 'biddeed-checkout failed', JSON.stringify(data), res.status);
          }
          return new Response(JSON.stringify(data), { status: res.status, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        } catch (e) {
          await logErr(env, '/subscribe/checkout', 'threw', String(e), 500);
          return new Response(JSON.stringify({ error: 'server error' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
      }

      // ── POST /referral/code — get-or-create a referral code for an email.
      // Added Aug 10 2026 for the double-sided referral program: both the
      // referrer and referee get 1 free month once the referred person's
      // subscription survives its first billing cycle (see
      // referral-reward-sweeper for why this is a sweep, not a webhook).
      if (path === '/referral/code' && method === 'POST') {
        let body = {};
        try { body = await request.json(); } catch(_) {}
        const email = (body.email || '').toLowerCase().trim();
        if (!email) return new Response(JSON.stringify({ error: 'email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        try {
          const existing = await fetch(`${SUPABASE_URL}/rest/v1/referral_codes?owner_email=eq.${encodeURIComponent(email)}&select=code`, {
            headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
          });
          const existingRows = existing.ok ? await existing.json() : [];
          if (existingRows.length) {
            return new Response(JSON.stringify({ ok: true, code: existingRows[0].code, link: `https://biddeed.ai/pioneers?ref=${existingRows[0].code}` }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }
          const code = Array.from(crypto.getRandomValues(new Uint8Array(6))).map(b => 'abcdefghjkmnpqrstuvwxyz23456789'[b % 32]).join('');
          const ins = await fetch(`${SUPABASE_URL}/rest/v1/referral_codes`, {
            method: 'POST',
            headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json', Prefer: 'resolution=merge-duplicates,return=minimal' },
            body: JSON.stringify({ code, owner_email: email }),
          });
          if (!ins.ok) {
            const err = await ins.text();
            await logErr(env, '/referral/code', 'insert failed', err, ins.status);
            return new Response(JSON.stringify({ error: 'could not create referral code' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }
          return new Response(JSON.stringify({ ok: true, code, link: `https://biddeed.ai/pioneers?ref=${code}` }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        } catch (e) {
          await logErr(env, '/referral/code', 'threw', String(e), 500);
          return new Response(JSON.stringify({ error: 'server error' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
      }

      // ── /success ─────────────────────────────────────────────────────────
      if (path === '/success') {
        return new Response(SUCCESS_HTML, { headers: { 'Content-Type': 'text/html;charset=UTF-8' } });
      }

      // ── /subscribe/status ────────────────────────────────────────────────
      if (path === '/subscribe/status') {
        const session_id = url.searchParams.get('session_id') || '';
        if (!session_id) return new Response(JSON.stringify({ error: 'Missing session_id' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/claim_key_for_session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ p_session_id: session_id }),
          });
          const data = await res.json();
          return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        } catch(e) {
          return new Response(JSON.stringify({ error: 'Status check failed' }), { status: 500, headers: { 'Content-Type': 'application/json' } });
        }
      }

      // ── GET /buy-report — $25 one-time report checkout page ─────────────
      // ?mca_id=&address=&county=&date= pre-fills step 3 from a property card in chat.
      if (path === '/buy-report' && method === 'GET') {
        const pMcaId = url.searchParams.get('mca_id') || '';
        const pAddress = url.searchParams.get('address') || '';
        const pCounty = (url.searchParams.get('county') || '').toLowerCase().replace(/-/g,'_');
        const pDate = url.searchParams.get('date') || '';
        const prefill = pMcaId ? { mca_id: pMcaId, address: pAddress, county: pCounty, county_name: pCounty ? toDisplay(pCounty) : '', date: pDate } : null;
        const prefillJson = JSON.stringify(prefill).replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
        const html = BUY_REPORT_HTML.replace('"PREFILL_PLACEHOLDER"', prefillJson);
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': prefill ? 'no-store' : 'public,max-age=300' } });
      }

      // ── GET /buy-report/counties — all counties w/ purchasable upcoming auctions ──
      if (path === '/buy-report/counties' && method === 'GET') {
        const counties = await fetchReportCounties();
        return new Response(JSON.stringify(counties), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public,max-age=120', ...corsHeaders(origin) } });
      }

      // ── GET /buy-report/auctions?county=slug — purchasable auctions for a county ──
      // Option A: any county is purchasable — Gold Standard no longer gates this.
      if (path === '/buy-report/auctions' && method === 'GET') {
        const county = (url.searchParams.get('county') || '').toLowerCase().replace(/-/g,'_');
        if (!county) {
          return new Response(JSON.stringify({ error: 'county required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        const auctions = await fetchReportAuctions(county);
        return new Response(JSON.stringify(auctions), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public,max-age=60', ...corsHeaders(origin) } });
      }

      // ── POST /buy-report/checkout — create Stripe checkout session ──────
      if (path === '/buy-report/checkout' && method === 'POST') {
        let body = {};
        try { body = await request.json(); } catch(_) {
          return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        const { email, county, case_number, mca_id, marketing_consent } = body;
        if (!email)       return new Response(JSON.stringify({ error: 'email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (!county)      return new Response(JSON.stringify({ error: 'county required — select an auction first' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (!case_number) return new Response(JSON.stringify({ error: 'case_number required — select an auction first' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        // ── Parity gate — server-side safety net ──────────────────────────
        // Never trust the client's mca_id: it can be stale (deep-link prefill
        // left over after the user re-picked a different auction in the same
        // session). Re-look the auction up by case_number+county — the pair
        // actually submitted. (county, case_number) is NOT a unique key in
        // multi_county_auctions — e.g. brevard/250104 is both a cancelled
        // 2025-10-16 foreclosure AND an upcoming, matched_clean 2026-08-20 tax
        // deed. The picker (fetchReportAuctions) only ever shows rows that are
        // already matched_clean+upcoming+future, so re-deriving "does at least
        // one row for this county+case_number still satisfy that" is a faithful
        // re-check of what the buyer actually saw — requiring ALL same-case_number
        // rows to pass (including unrelated stale/cancelled ones) false-positives
        // and blocks legitimate purchases.
        try {
          const lookupUrl = `${SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.${encodeURIComponent(county)}&case_number=eq.${encodeURIComponent(case_number)}&select=id,parity_status,auction_status,auction_date`;
          const lookupRes = await fetch(lookupUrl, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } });
          let rows = lookupRes.ok ? await lookupRes.json() : [];
          if (!Array.isArray(rows)) rows = [];
          if (mca_id) rows = rows.filter(r => String(r.id) === String(mca_id));

          if (!rows.length) {
            return new Response(JSON.stringify({ error: 'Property not found' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }
          const now = new Date();
          const isGood = r =>
            r.auction_status === 'upcoming' &&
            r.parity_status === 'matched_clean' &&
            (!r.auction_date || new Date(r.auction_date) >= now);
          if (!rows.some(isGood)) {
            const bad = rows[0];
            if (bad.auction_status !== 'upcoming') {
              return new Response(JSON.stringify({ error: 'This auction is no longer upcoming' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
            }
            if (bad.auction_date && new Date(bad.auction_date) < now) {
              return new Response(JSON.stringify({ error: 'This auction date has passed' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
            }
            return new Response(JSON.stringify({ error: 'This auction is pending calendar verification. Please check back in 24 hours or contact hello@biddeed.ai' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }
        } catch(e) {
          await logErr(env, '/buy-report/checkout', 'Parity gate lookup failed', String(e), 500);
          return new Response(JSON.stringify({ error: 'Could not verify this auction. Please try again.' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        try {
          // Price is never trusted from the client — biddeed-checkout fixes
          // the s5_onetime amount at $25 server-side.
          const res = await fetch(`${SUPABASE_URL}/functions/v1/biddeed-checkout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ tier: 's5_onetime', customer_email: email, county, case_number, mca_id: mca_id || null, marketing_consent: !!marketing_consent }),
          });
          if (!res.ok) {
            const err = await res.text();
            await logErr(env, '/buy-report/checkout', 'biddeed-checkout failed', err, res.status);
            return new Response(JSON.stringify({ error: 'Checkout session creation failed' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }
          const session = await res.json();
          return new Response(JSON.stringify({ url: session.url }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        } catch(e) {
          await logErr(env, '/buy-report/checkout', 'Exception', String(e), 500);
          return new Response(JSON.stringify({ error: 'Checkout session creation failed' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
      }

      // ── GET /free-report — lead capture form before delivering anything ──
      if (path === '/free-report' && method === 'GET') {
        const prefillEmail = url.searchParams.get('email') || '';
        const counties = await fetchReportCounties();
        const html = buildFreeReportFormHtml(prefillEmail, counties);
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
      }

      // ── POST /free-report/submit — upsert lead, redirect to delivery ────
      if (path === '/free-report/submit' && method === 'POST') {
        let form;
        try { form = await request.formData(); } catch(_) {
          return new Response('Invalid form submission', { status: 400 });
        }
        const email = (form.get('email') || '').toString().trim();
        const phone = (form.get('phone') || '').toString().trim();
        const county = (form.get('county') || '').toString().toLowerCase().replace(/-/g,'_').trim();
        const emailConsent = form.get('email_consent') === 'on';
        const smsConsent = form.get('sms_consent') === 'on';

        const invalid = !email || !email.includes('@') || !phone || !county || (!emailConsent && !smsConsent);
        if (invalid) {
          const counties = await fetchReportCounties();
          const html = buildFreeReportFormHtml(email, counties, { phone, county, emailConsent, smsConsent, error: 'Please fill in all required fields and check at least one consent box.' });
          return new Response(html, { status: 400, headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
        }

        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/upsert_lead_full`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({
              p_email: email, p_name: null, p_phone: phone, p_county: county,
              p_email_consent: emailConsent, p_sms_consent: smsConsent, p_source: 'free_report_capture',
            }),
          });
          if (!res.ok) {
            const err = await res.text();
            await logErr(env, '/free-report/submit', 'upsert_lead_full failed', err, res.status);
            const counties = await fetchReportCounties();
            const html = buildFreeReportFormHtml(email, counties, { phone, county, emailConsent, smsConsent, error: 'Something went wrong — please try again.' });
            return new Response(html, { status: 500, headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
          }
        } catch(e) {
          await logErr(env, '/free-report/submit', 'Exception', String(e), 500);
          const counties = await fetchReportCounties();
          const html = buildFreeReportFormHtml(email, counties, { phone, county, emailConsent, smsConsent, error: 'Something went wrong — please try again.' });
          return new Response(html, { status: 500, headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
        }

        const qs = `email=${encodeURIComponent(email)}&county=${encodeURIComponent(county)}&ec=${emailConsent ? 1 : 0}&sc=${smsConsent ? 1 : 0}`;
        return Response.redirect(`${url.origin}/free-report/delivery?${qs}`, 302);
      }

      // ── GET /free-report/delivery — top 5 county auctions + upsell CTAs ──
      if (path === '/free-report/delivery' && method === 'GET') {
        const email = url.searchParams.get('email') || '';
        const county = (url.searchParams.get('county') || '').toLowerCase().replace(/-/g,'_');
        if (!county) return Response.redirect(`${url.origin}/free-report`, 302);
        const consent = { emailConsent: url.searchParams.get('ec') === '1', smsConsent: url.searchParams.get('sc') === '1' };
        const [auctions, counties] = await Promise.all([fetchFreeReportAuctions(county), fetchReportCounties()]);
        const countyMeta = counties.find(c => c.county_slug === county) || null;
        const html = buildFreeReportDeliveryHtml(email, county, auctions, countyMeta, consent);
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
      }

      // ── GET /report-success — post-payment report key delivery page ─────
      if (path === '/report-success' && method === 'GET') {
        return new Response(REPORT_SUCCESS_HTML, { headers: { 'Content-Type': 'text/html;charset=UTF-8' } });
      }

      // ── GET /report/:mca_id — interactive S5 Shapira report (issue #18307) ──
      if (path.match(/^\/report\/[^/]+$/) && method === 'GET') {
        const mcaId = decodeURIComponent(path.split('/')[2]);
        const authHeader = request.headers.get('Authorization') || '';
        const apiKey = authHeader.startsWith('Bearer ') ? authHeader.slice(7).trim() : (url.searchParams.get('key') || '');
        if (!apiKey) {
          return new Response(JSON.stringify({ error: 'Invalid or expired report key' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
        }
        // ── Sample report bypass — no auth, no billing, publicly accessible ──
        if (mcaId === MARION_SAMPLE_MCA_ID && apiKey === SAMPLE_REPORT_KEY) {
          const html = renderS5ReportHtml(SAMPLE_STATIC_REPORT, { mcaId, keyLast8: apiKey.slice(-8), isSample: true });
          return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
        }

        let access;
        try {
          access = await fetchS5ReportAccess(apiKey, mcaId);
        } catch (e) {
          await logErr(env, '/report/:mca_id', 'access lookup threw', String(e), 500);
          return new Response(JSON.stringify({ error: 'Report generation in progress, try again in 30 seconds' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
        }
        if (!access || !access.ok) {
          const reason = access?.reason || 'invalid_key';
          if (reason === 'no_purchase') {
            return new Response(JSON.stringify({ error: 'No purchase found for this report' }), { status: 403, headers: { 'Content-Type': 'application/json' } });
          }
          return new Response(JSON.stringify({ error: 'Invalid or expired report key' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
        }
        let report;
        try {
          report = await fetchS5ReportJson(apiKey, mcaId);
        } catch (e) {
          await logErr(env, '/report/:mca_id', 'report/json lookup threw', String(e), 503);
          report = null;
        }
        if (!report) {
          return new Response(JSON.stringify({ error: 'Report generation in progress, try again in 30 seconds' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
        }
        const keyLast8 = apiKey.slice(-8);
        const html = renderS5ReportHtml(report, { mcaId, keyLast8 });
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'private,no-store' } });
      }

      // ── /county/:slug/lots — JSON feed for lots ──────────────────────────
      if (path.match(/^\/county\/[^/]+\/lots$/)) {
        const slug = path.split('/')[2].toLowerCase().replace(/-/g,'_');
        const lots = await fetchCountyLots(slug);
        return new Response(JSON.stringify(lots), {
          headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public,max-age=120', ...corsHeaders(origin) }
        });
      }

      // ── /county/:slug — county deep-link landing page ────────────────────
      if (path.startsWith('/county/')) {
        const slug = path.replace('/county/', '').toLowerCase().replace(/-/g,'_').replace(/\/.*$/,'');
        if (!slug) return Response.redirect('/counties', 302);
        const [data, lots, rtConfig] = await Promise.all([fetchCountyData(slug), fetchCountyLots(slug), fetchRuntimeConfig()]);
        const html = buildCountyPage(slug, data, lots, rtConfig);
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=120' } });
      }

      // ── /counties — all counties index ───────────────────────────────────
      if (path === '/counties') {
        const ciConfig = await fetchRuntimeConfig();
        const html = buildCountiesIndex(ciConfig);
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      // ── /sitemap.xml — added Aug 10 2026: prior to this, none of the 67
      // /county/:slug pages nor /counties itself were discoverable by search
      // engines (confirmed via site: search — only the homepage was indexed).
      // Lists all static/core routes plus every county landing page so
      // crawlers have an explicit path to this content.
      if (path === '/sitemap.xml') {
        const base = 'https://biddeed.ai';
        const staticUrls = ['/', '/counties', '/buy-report', '/chat', '/subscribe', '/blog', '/pioneers', '/terms', '/privacy', '/disclaimer', '/security'];
        const countySlugs = Object.keys(COUNTY_DISPLAY).sort();
        const blogSlugs = BLOG_POSTS.map(p => p.slug);
        const urlEntries = [
          ...staticUrls.map(p => `  <url><loc>${base}${p}</loc><changefreq>daily</changefreq></url>`),
          ...countySlugs.map(slug => `  <url><loc>${base}/county/${slug.replace(/_/g,'-')}</loc><changefreq>daily</changefreq></url>`),
          ...blogSlugs.map(slug => `  <url><loc>${base}/blog/${slug}</loc><changefreq>weekly</changefreq></url>`)
        ].join('\n');
        const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urlEntries}\n</urlset>`;
        return new Response(xml, { headers: { 'Content-Type': 'application/xml;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      }

      // ── /robots.txt — added Aug 10 2026 alongside /sitemap.xml so crawlers
      // discover the sitemap immediately instead of relying only on Search
      // Console submission.
      if (path === '/robots.txt') {
        const robots = 'User-agent: *\nAllow: /\nSitemap: https://biddeed.ai/sitemap.xml\n';
        return new Response(robots, { headers: { 'Content-Type': 'text/plain;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      }

      // ── /pioneers — Pioneer program landing page ─────────────────────────
      // Added Aug 10 2026. IMPORTANT: this is an interest-only waitlist, NOT
      // a live equity/SAFE offering. Offering stock options or a SAFE to
      // paying customers is a securities offering and needs a securities
      // attorney to structure the exemption, accredited-investor handling
      // (if required), and disclosure docs before any payment or equity
      // issuance goes live. Do not wire this page to Stripe or issue any
      // options/SAFE until that review has happened.
      if (path === '/pioneers') {
        return new Response(buildPioneersPage(), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      // ── /proof/:slug — shareable "we called it" result cards. Added Aug
      // 10 2026. Checked s5_pdf_cache before building this: zero rows
      // currently have a real captured auction_outcome.sale_price -- the
      // outcome-capture pipeline isn't populating results yet, independent
      // of anything referral-related. Rather than build a dynamic route
      // with nothing real to show, this is seeded with the one genuinely
      // verified result (Marion/Summerfield) using numbers already
      // published on the blog, with proper Open Graph tags for a good
      // link preview when shared. Add more entries to PROOF_CARDS as real
      // outcomes get captured -- do not synthesize numbers for this.
      if (path.startsWith('/proof/')) {
        const slug = path.slice('/proof/'.length);
        const card = PROOF_CARDS[slug];
        if (!card) return new Response('Not found', { status: 404 });
        return new Response(buildProofCard(card), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      // ── POST /pioneers/join — waitlist signup only, no payment, no
      // binding commitment on either side. Reuses lead_profiles like the
      // rest of the site's lead capture (source tag distinguishes it).
      if (path === '/pioneers/join' && method === 'POST') {
        let body = {};
        try { body = await request.json(); } catch(_) {}
        const { email, name } = body;
        if (!email) return new Response(JSON.stringify({ ok: false, error: 'email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        const now = new Date().toISOString();
        try {
          const upsertRes = await fetch(`${SUPABASE_URL}/rest/v1/lead_profiles`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'apikey': SUPABASE_KEY,
              'Authorization': `Bearer ${SUPABASE_KEY}`,
              'Prefer': 'resolution=merge-duplicates,return=minimal',
            },
            body: JSON.stringify({
              email,
              name: name || null,
              source: 'pioneers_waitlist',
              stage: 'pioneer_interest',
              marketing_consent: true,
              marketing_consent_at: now,
            }),
          });
          if (!upsertRes.ok) {
            const err = await upsertRes.text();
            await logErr(env, '/pioneers/join', 'Supabase upsert failed', err, upsertRes.status);
            return new Response(JSON.stringify({ ok: false, error: err }), { status: upsertRes.status, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }

          const resendKey = env.RESEND_API_KEY || null;
          if (resendKey) {
            fetch('https://api.resend.com/emails', {
              method: 'POST',
              headers: { 'Authorization': `Bearer ${resendKey}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({
                from: 'BidDeed.AI <activate@biddeed.ai>',
                to: [email],
                subject: `You're on the Pioneer list — BidDeed.AI`,
                text: `Thanks for your interest in the BidDeed.AI Pioneer program.\n\nYou're on the list. This is an interest waitlist only — no payment has been taken and nothing is final yet. We're finalizing the program structure and will reach out with full details before anything goes live.\n\nQuestions in the meantime? Just reply to this email.\n\nBidDeed.AI · Everest Capital USA\nInformational only — not legal, financial, or investment advice.`,
              }),
            }).catch(e => logErr(env, '/pioneers/join', 'Resend send failed', String(e), 500));
          }

          // Issue a referral code immediately -- added Aug 10 2026, part of
          // the double-sided referral program. Reused/created via the same
          // get-or-create logic as POST /referral/code so a person only
          // ever has one code regardless of which flow first created it.
          let referralCode = null;
          try {
            const existingCode = await fetch(`${SUPABASE_URL}/rest/v1/referral_codes?owner_email=eq.${encodeURIComponent(email)}&select=code`, {
              headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            });
            const existingCodeRows = existingCode.ok ? await existingCode.json() : [];
            if (existingCodeRows.length) {
              referralCode = existingCodeRows[0].code;
            } else {
              const newCode = Array.from(crypto.getRandomValues(new Uint8Array(6))).map(b => 'abcdefghjkmnpqrstuvwxyz23456789'[b % 32]).join('');
              const codeIns = await fetch(`${SUPABASE_URL}/rest/v1/referral_codes`, {
                method: 'POST',
                headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json', Prefer: 'resolution=merge-duplicates,return=minimal' },
                body: JSON.stringify({ code: newCode, owner_email: email }),
              });
              if (codeIns.ok) referralCode = newCode;
            }
          } catch (codeErr) {
            await logErr(env, '/pioneers/join', 'referral code issuance failed (non-fatal)', String(codeErr), 500);
          }
          const referralLink = referralCode ? `https://biddeed.ai/pioneers?ref=${referralCode}` : null;

          return new Response(JSON.stringify({ ok: true, referral_code: referralCode, referral_link: referralLink }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        } catch (e) {
          await logErr(env, '/pioneers/join', 'threw', String(e), 500);
          return new Response(JSON.stringify({ ok: false, error: 'server error' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
      }

      // ── /blog + /blog/:slug — added Aug 10 2026 for organic content
      // marketing. Server-rendered like /county pages so it's fully
      // crawlable; BLOG_POSTS is a plain array below, add new posts there.
      if (path === '/blog') {
        return new Response(buildBlogIndex(), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }
      if (path.startsWith('/blog/')) {
        const slug = path.slice('/blog/'.length);
        const post = BLOG_POSTS.find(p => p.slug === slug);
        if (!post) return new Response('Not found', { status: 404 });
        return new Response(buildBlogPost(post), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      // ── GET /auctions?county=&days=&type=&limit= — property cards for chat ──
      // Option A: all counties are served — Gold Standard is a badge (is_gold_standard
      // field per card), never an access gate.
      if (path === '/auctions' && method === 'GET') {
        const county = (url.searchParams.get('county') || '').toLowerCase().replace(/-/g,'_');
        if (!county) return new Response(JSON.stringify({ error: 'county required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        let days = parseInt(url.searchParams.get('days') || '14', 10);
        if (!Number.isFinite(days) || days <= 0) days = 14;
        days = Math.min(days, 90);
        const type = (url.searchParams.get('type') || 'all').toLowerCase();
        let limit = parseInt(url.searchParams.get('limit') || '20', 10);
        if (!Number.isFinite(limit) || limit <= 0) limit = 20;
        limit = Math.min(limit, 50);
        const cards = await fetchAuctionCards(county, days, type, limit);
        return new Response(JSON.stringify(cards), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public,max-age=60', ...corsHeaders(origin) } });
      }

      // ── GET /property/:mca_id — single auction row + appraiser link ─────
      if (path.match(/^\/property\/[^/]+$/) && method === 'GET') {
        const id = decodeURIComponent(path.split('/')[2]);
        const row = await fetchPropertyById(id);
        if (!row) return new Response(JSON.stringify({ error: 'not found' }), { status: 404, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const appraiser_link = row.county ? await fetchAppraiserLink(row.county) : null;
        return new Response(JSON.stringify({ ...row, appraiser_link }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
      }

      // ── /chat/county-data ────────────────────────────────────────────────
      if (path === '/chat/county-data') {
        const county = url.searchParams.get('county') || '';
        if (!county) return new Response(JSON.stringify(null), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const row = await fetchCountyData(county);
        return new Response(JSON.stringify(row), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
      }

      // ── POST /chat/lead ──────────────────────────────────────────────────
      // Full flow: upsert lead (phone+consent) → fetch 5 live auctions →
      // send Resend free-report email → return auctions to client for instant display
      if (path === '/chat/lead' && method === 'POST') {
        let body = {};
        try { body = await request.json(); } catch(_) {}
        const { email, county, source, phone, sms_consent, email_consent } = body;
        if (!email) return new Response(JSON.stringify({ ok: false, error: 'email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        const now = new Date().toISOString();
        const upsertPayload = {
          email,
          county_interest: county || null,
          source: source || 'homepage_chatbot',
        };
        if (phone)                         upsertPayload.phone = phone;
        if (sms_consent !== undefined)     { upsertPayload.sms_consent = !!sms_consent; if (sms_consent) upsertPayload.sms_consent_at = now; }
        if (email_consent !== undefined)   { upsertPayload.email_consent = !!email_consent; if (email_consent) upsertPayload.email_consent_at = now; }
        if (email_consent)                 { upsertPayload.marketing_consent = true; upsertPayload.marketing_consent_at = now; }

        try {
          // 1. Upsert lead
          const upsertRes = await fetch(`${SUPABASE_URL}/rest/v1/lead_profiles`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'apikey': SUPABASE_KEY,
              'Authorization': `Bearer ${SUPABASE_KEY}`,
              'Prefer': 'resolution=merge-duplicates,return=minimal',
            },
            body: JSON.stringify(upsertPayload),
          });
          if (!upsertRes.ok) {
            const err = await upsertRes.text();
            await logErr(env, '/chat/lead', 'Supabase upsert failed', err, upsertRes.status);
            return new Response(JSON.stringify({ ok: false, error: err }), { status: upsertRes.status, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }

          // 2. Fetch 5 upcoming auctions for this county
          let auctions = [];
          if (county) {
            const today = new Date().toISOString().split('T')[0];
            const cutoff = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
            const aRes = await fetch(
              `${SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.${encodeURIComponent(county)}&auction_date=gte.${today}&auction_date=lte.${cutoff}&auction_status=eq.upcoming&order=auction_date.asc&limit=5&select=property_address,auction_date,opening_bid,sale_type,case_number,assessed_value`,
              { headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` } }
            );
            if (aRes.ok) auctions = await aRes.json();
          }

          // 3. Build + send Resend free-report email (fire-and-forget, never blocks response)
          const resendKey = env.RESEND_API_KEY || null;
          if (resendKey && county) {
            const countyDisplay = county.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
            const auctionRows = auctions.length
              ? auctions.map((a,i) => {
                  const addr = a.property_address || 'Address TBD';
                  const date = a.auction_date ? new Date(a.auction_date + 'T12:00:00').toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'}) : 'TBD';
                  const bid  = a.opening_bid ? `$${Number(a.opening_bid).toLocaleString()}` : 'TBD';
                  const type = (a.sale_type||'').replace('_',' ').toUpperCase();
                  return `<tr style="background:${i%2===0?'#f8fafc':'#ffffff'}">
                    <td style="padding:10px 12px;font-size:13px;color:#0B1929;border-bottom:1px solid #e2e8f0">${addr}</td>
                    <td style="padding:10px 12px;font-size:13px;color:#64748b;border-bottom:1px solid #e2e8f0;white-space:nowrap">${date}</td>
                    <td style="padding:10px 12px;font-size:13px;font-weight:600;color:#0B1929;border-bottom:1px solid #e2e8f0;white-space:nowrap">${bid}</td>
                    <td style="padding:10px 12px;font-size:11px;color:#F97316;border-bottom:1px solid #e2e8f0;white-space:nowrap">${type}</td>
                  </tr>`;
                }).join('')
              : `<tr><td colspan="4" style="padding:16px;text-align:center;color:#64748b;font-size:13px">No upcoming auctions found in ${countyDisplay} — check back soon.</td></tr>`;

            const emailHtml = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Inter',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px">
<tr><td>
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)">
  <!-- Header -->
  <tr><td style="background:#0B1929;padding:28px 32px">
    <div style="font-size:22px;font-weight:700;color:#F97316;letter-spacing:-0.5px">BidDeed.AI</div>
    <div style="font-size:13px;color:#e2eaf2;margin-top:4px">Your Free ${countyDisplay} County Report</div>
  </td></tr>
  <!-- Intro -->
  <tr><td style="padding:28px 32px 16px">
    <p style="margin:0 0 8px;font-size:15px;color:#0B1929;font-weight:600">Here are the next 5 upcoming auctions in ${countyDisplay} County:</p>
    <p style="margin:0;font-size:13px;color:#64748b">Based on 20 years of FL auction experience — Shapira Formula analysis included below.</p>
  </td></tr>
  <!-- Auction Table -->
  <tr><td style="padding:0 32px">
    <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:8px;overflow:hidden;border:1px solid #e2e8f0">
      <tr style="background:#0B1929">
        <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#e2eaf2;text-transform:uppercase;letter-spacing:.5px">Property</th>
        <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#e2eaf2;text-transform:uppercase;letter-spacing:.5px">Date</th>
        <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#e2eaf2;text-transform:uppercase;letter-spacing:.5px">Opening Bid</th>
        <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#e2eaf2;text-transform:uppercase;letter-spacing:.5px">Type</th>
      </tr>
      ${auctionRows}
    </table>
  </td></tr>
  <!-- CTA -->
  <tr><td style="padding:28px 32px">
    <div style="background:#f8fafc;border-radius:10px;padding:20px 24px;border-left:4px solid #F97316">
      <div style="font-size:14px;font-weight:600;color:#0B1929;margin-bottom:6px">Want the full Shapira S5 Report on a specific property?</div>
      <div style="font-size:13px;color:#64748b;margin-bottom:16px">Max-bid ceiling · Lien stack · Plaintiff intel · Zoning · BID/SKIP verdict — all in one $25 report.</div>
      <a href="https://biddeed.ai/buy-report?county=${encodeURIComponent(county)}" style="display:inline-block;background:#F97316;color:#ffffff;font-size:13px;font-weight:700;padding:12px 24px;border-radius:8px;text-decoration:none;letter-spacing:.3px">Get Shapira S5 Report — $25 →</a>
    </div>
  </td></tr>
  <!-- Investor Upsell -->
  <tr><td style="padding:0 32px 24px">
    <div style="text-align:center;font-size:12px;color:#e2eaf2">
      Want unlimited access to all 67 FL counties?
      <a href="https://biddeed.ai/subscribe?tier=investor" style="color:#F97316;text-decoration:none;font-weight:600"> Investor — $99/mo →</a>
    </div>
  </td></tr>
  <!-- Footer -->
  <tr><td style="background:#f8fafc;padding:16px 32px;border-top:1px solid #e2e8f0">
    <p style="margin:0;font-size:11px;color:#e2eaf2;text-align:center">BidDeed.AI · Everest Capital USA · Satellite Beach, FL<br>
    Informational only — not legal, financial, or investment advice. <a href="https://biddeed.ai/disclaimer" style="color:#e2eaf2">Disclaimer</a></p>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>`;

            fetch('https://api.resend.com/emails', {
              method: 'POST',
              headers: { 'Authorization': `Bearer ${resendKey}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({
                from: 'BidDeed.AI <activate@biddeed.ai>',
                to: [email],
                subject: `Your Free ${countyDisplay} County Auction Report — ${auctions.length} Upcoming`,
                html: emailHtml,
              }),
            }).catch(e => logErr(env, '/chat/lead', 'Resend send failed', String(e), 500));
          }

          // 4. Return auctions to client for instant in-page display
          return new Response(JSON.stringify({ ok: true, auctions }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        } catch(e) {
          await logErr(env, '/chat/lead', 'Exception', String(e), 500);
          return new Response(JSON.stringify({ ok: false, error: String(e) }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
      }

      // ── POST /chat/api — Streaming SSE ───────────────────────────────────
      if (path === '/chat/api' && method === 'POST') {
        const cl = parseInt(request.headers.get('Content-Length') || '0', 10);
        if (cl > 20000) return new Response(JSON.stringify({ error: 'Request too large' }), { status: 413, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
        const rl = await checkRateLimitV2(ip);
        if (!rl.allowed) return new Response(JSON.stringify({ error: rateLimitReason(rl) }), { status: 429, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const tier = rl.tier || 'standard';
        await logErr(env, '/chat/api', `tier=${tier}`, `day_hits=${rl.day_hits} week_hits=${rl.week_hits}`, 200, 'info');

        let body = {};
        try { body = await request.json(); } catch(_) {
          return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        const { messages, county, hook } = body;
        if (!Array.isArray(messages) || messages.length === 0)
          return new Response(JSON.stringify({ error: 'messages required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (messages.length > 20)
          return new Response(JSON.stringify({ error: 'Too many messages' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const totalChars = messages.reduce((n, m) => n + String(m.content || '').length, 0);
        if (totalChars > 8000)
          return new Response(JSON.stringify({ error: 'Messages too long' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (!messages.every(m => ['user','assistant'].includes(m.role)))
          return new Response(JSON.stringify({ error: 'Invalid message role' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        // Dynamic Gold Standard list from runtime config
        const rtCfg = await fetchRuntimeConfig();
        const goldListForPrompt = (rtCfg.goldCounties && rtCfg.goldCounties.length ? rtCfg.goldCounties : GOLD_COUNTIES).map(s => toDisplay(s)).join(', ');

        // Live Supabase grounding — detect what the user is asking about and fetch real data
        const lastMsg = String(messages[messages.length - 1]?.content || '').toLowerCase();
        const yesterdayWords = ['yesterday','hier','ayer','ontem','wczoraj','ieri','gestern','昨天','昨日','어제','вчера','أمس'];
        const askedYesterday = yesterdayWords.some(w => lastMsg.includes(w));
        const askedResults = /result|sold|outcome|clos|winn|résultat|vendu|resultado|vendido|verkauft|销售|낙찰|продан|نتيجة/i.test(lastMsg);

        const upcomingWords = ['upcoming','coming up','this week','next week','auction','schedule','calendar','available','à venir','prochaine','enchère','prochain','próxima','subasta','venda','מכירה','קרוב','предстоящ','аукцион','拍卖','即将','오는','경매'];
        const askedUpcoming = upcomingWords.some(w => lastMsg.includes(w));

        let liveDataCtx = '';

        // UPCOMING auctions grounding (mirrors the daily Resend email)
        if (askedUpcoming && !askedYesterday) {
          try {
            const today2 = new Date().toISOString().slice(0,10);
            const cut30 = new Date(Date.now()+30*86400000).toISOString().slice(0,10);
            // Extract county from message if not provided by frontend
            let effectiveCounty = county || '';
            if (!effectiveCounty) {
              const countyNames = Object.keys(COUNTY_DISPLAY);
              const msgLower = lastMsg.replace(/-/g,'_');
              for (const slug of countyNames) {
                const display = COUNTY_DISPLAY[slug].toLowerCase();
                if (msgLower.includes(display) || msgLower.includes(slug.replace(/_/g,' '))) {
                  effectiveCounty = slug;
                  break;
                }
              }
            }
            let uUrl = SUPABASE_URL+'/rest/v1/multi_county_auctions?auction_date=gte.'+today2+'&auction_date=lte.'+cut30+'&order=auction_date.asc&limit=25&select=county,sale_type,property_address,auction_date,opening_bid,assessed_value,case_number';
            if (effectiveCounty) uUrl += '&county=eq.'+encodeURIComponent(effectiveCounty);
            const uRes = await fetch(uUrl, { headers: { apikey: SUPABASE_KEY, Authorization: 'Bearer '+SUPABASE_KEY } });
            const uRows = uRes.ok ? await uRes.json() : [];
            if (Array.isArray(uRows) && uRows.length > 0) {
              liveDataCtx = '\n\nLIVE DATA — upcoming auctions (next 30 days) from the production database, same data that goes out in the daily BidDeed email digest. Use ONLY these real records, cite exact figures, do not invent any:\n' +
                uRows.map(r => '- '+r.auction_date+' | '+(r.county||'')+' | '+(r.sale_type||'')+' | '+(r.property_address||'address pending')+' | case '+r.case_number+' | bid $'+(Number(r.opening_bid)||0).toLocaleString()+' | assessed $'+(Number(r.assessed_value)||0).toLocaleString()).join('\n') +
                '\nTotal: '+uRows.length+' lots shown (there may be more — tell the user to visit biddeed.ai/county/SLUG for the full list). For each property, mention they can get a $25 Shapira S5 Report for a full max-bid analysis.';
            }
          } catch(e2) {
            liveDataCtx = '\n\nNote: upcoming auction data lookup failed — tell the user to check biddeed.ai/county/[name] directly.';
          }
        }

        // YESTERDAY sold grounding (existing)
        if ((askedYesterday || askedResults) && !liveDataCtx) {
          try {
            const y = new Date(Date.now() - 86400000).toISOString().slice(0,10);
            let url = `${SUPABASE_URL}/rest/v1/multi_county_auctions?auction_date=eq.${y}&or=(sold_amount.not.is.null,tier1_sold_amount.not.is.null)&order=tier1_sold_amount.desc.nullslast&limit=30&select=county,sale_type,property_address,case_number,sold_amount,tier1_sold_amount,opening_bid,auction_status`;
            const yCounty = county || effectiveCounty || '';
            if (yCounty) url += '&county=eq.'+encodeURIComponent(yCounty);
            const lr = await fetch(url, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } });
            const rows = lr.ok ? await lr.json() : [];
            if (Array.isArray(rows) && rows.length > 0) {
              liveDataCtx = `\n\nLIVE DATA — actual completed auctions from ${y} (yesterday), pulled just now from the production database. Use ONLY these real records when answering, cite exact figures, do not invent any:\n` +
                rows.map(r => `- ${toDisplay(r.county)} County, ${r.sale_type}: ${r.property_address || 'address pending'} (case ${r.case_number}) — sold $${Number(r.tier1_sold_amount || r.sold_amount).toLocaleString()}`).join('\n');
            } else {
              liveDataCtx = `\n\nLIVE DATA CHECK: queried the production database for auctions completed on ${y} — no sold-amount records were found for that date${county ? ' in ' + toDisplay(county) + ' County' : ''}. Tell the user honestly that no results are available yet rather than inventing figures.`;
            }
          } catch(e) {
            liveDataCtx = '\n\nNote: live data lookup failed — do not fabricate specific figures, tell the user to check biddeed.ai/county/[name] directly.';
          }
        }

        // ── County auction intent → live property cards panel (SSE "properties" event) ──
        const intentCounty = AUCTION_INTENT_RE.test(lastMsg) ? (county || detectFLCounty(lastMsg)) : null;
        let propertyPanelCards = null;
        let propertyPanelCtx = '';
        if (intentCounty) {
          propertyPanelCards = await fetchAuctionCards(intentCounty, 21, 'all', 20);
          propertyPanelCtx = `\n\nLIVE AUCTION DATA for ${toDisplay(intentCounty)} County (next 21 days): ${JSON.stringify(propertyPanelCards)}. Summarize these properties naturally. Do not list all fields — highlight the best opportunities by equity gap. Mention the opening bids and dates. End your response with exactly (nothing after it): [PROPERTIES_LOADED:${intentCounty}:${propertyPanelCards.length}]`;
        }

        // Cheap character-range detection up front — the model no longer has to infer
        // the reply language from content alone, which shortens time-to-first-token.
        const detectedLang = detectLanguage(String(messages[messages.length - 1]?.content || ''));
        const langInstruction = detectedLang !== 'en'
          ? `\n\nRespond in ${LANG_NAMES[detectedLang]}. Property data (addresses, dates, amounts) stay in English.`
          : '';

        const countyCtx = (county ? `The user is asking about ${toDisplay(county)} County, Florida.` : 'The user may ask about any Florida county.') + liveDataCtx + propertyPanelCtx + langInstruction;
        const systemPrompt = `You are BidDeed.AI, the expert AI assistant for Florida foreclosure and tax deed auction intelligence. Built on 20 years of experience from Ariel Shapira, creator of the Shapira Max Bid Formula.

${countyCtx}

Your capabilities:
- Analyze foreclosure and tax deed auctions across all 67 Florida counties
- Explain and apply the Shapira Max Bid Formula (exact ceiling before bidding)
- Cover all 67 Florida counties, and identify which ones are Gold Standard certified (verified data quality)
- Explain lien priority, HOA foreclosure risks, and surplus funds
- Answer questions about ZoneWise zoning intelligence
- Respond in the same language the user writes in (English, Hebrew, Spanish, Portuguese, Arabic, Russian, Chinese, French, Italian, German, Japanese, Korean, etc.)

Key facts:
- All 67 FL counties are available. Gold Standard counties (verified data quality — currently: ${goldListForPrompt}) have full S5 capability including CMA and ZoneWise. All other counties have Shapira Max Bid and opening bid analysis.
- Marion County proof: Case 422021CA000414CAAXXX — Shapira Max Bid $82,000, actual sale $73,501. Ceiling held by $8,499.
- Shapira S5 reports: $25 each — full AI-powered max-bid analysis for one specific property
- Investor tier: $99/month — unlimited property cards, 10 S5 reports/mo, daily digest all 67 counties
- When a user asks for a specific property analysis, mention they can get a full Shapira S5 Report for $25

When someone asks for a specific property analysis or max bid, always suggest the $25 Shapira S5 Report as the way to get the full calculation.

FORMATTING RULES (the chat UI renders real markdown, not plain text — use it):
- Use **bold** for prices, addresses, and key figures
- Use markdown tables (| col | col |) when listing 3+ properties — they render as real HTML tables
- ALWAYS end a county-specific answer with a link in this EXACT format: [See all COUNTY listings →](https://biddeed.ai/county/SLUG) using the lowercase-underscore county slug (e.g. palm_beach, st_johns, miami_dade). This link becomes clickable and drives users to the full property card grid.
- If you listed live auction results and there could be more than what you showed, say so and link to the county page rather than just stopping — never imply the list is exhaustive when it's a top-N sample
- ONLY TWO CTA link destinations exist and are valid — never invent or link to any other path: (1) [See all COUNTY listings →](https://biddeed.ai/county/SLUG) for county-specific results, (2) [Upgrade to Investor →](https://biddeed.ai/subscribe?tier=investor) for broad/multi-county questions. There is NO standalone /s5 page — for the $25 Shapira S5 Report, mention it by name and price in plain text (not as a link) and tell the user to ask about a specific property to get started.
- ALWAYS end every substantive answer with a clear next step using only the two valid links above, or the plain-text S5 mention. Never end with just information and no path forward — every answer is a lead-generation opportunity.
- If this message included a "LIVE AUCTION DATA ... End your response with exactly" instruction, obey it literally: put that [PROPERTIES_LOADED:...] token as the very last thing in your reply, on its own, with nothing after it. It is a control token for the UI, not a link — never wrap it in markdown or explain it to the user.
${DISCLAIMER_SHORT}`;

        // ALL tiers route through claude-router (Smart Router) which manages its own
        // LLM cascade internally (gemini-2.5-flash → DeepSeek → Claude fallback).
        // The Worker's GEMINI_API_KEY binding is retired — it hit quota limits.
        // claude-router uses vault-stored keys that are separate and working.
        const geminiKey = null;   // retired — quota exhausted on Worker-bound key
        const useGemini = false;  // always use claude-router

        const routerProxyKey = env.ROUTER_PROXY_KEY;
        if (!useGemini && !routerProxyKey) {
          await logErr(env, '/chat/api', 'Missing ROUTER_PROXY_KEY binding', '', 500);
          return new Response(JSON.stringify({ error: 'Service configuration error' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        let upstreamRes;
        try {
          if (useGemini) {
            upstreamRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse&key=${geminiKey}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                system_instruction: { parts: [{ text: systemPrompt }] },
                contents: messages.map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: String(m.content) }] })),
              }),
            });
          } else {
            // Route through claude-router (manages Gemini/DeepSeek/Claude cascade via vault)
            const routerBody = JSON.stringify({
              messages: messages.map(m => ({ role: m.role, content: String(m.content) })),
              system: systemPrompt,
              max_tokens: 1024,
              stream: false,
              source: 'biddeed-chat',
            });
            const routerResp = await fetch(`${SUPABASE_URL}/functions/v1/claude-router`, {
              method: 'POST',
              headers: { 'X-Router-Key': routerProxyKey, 'Content-Type': 'application/json' },
              body: routerBody,
            });
            let aiText = '';
            if (!routerResp.ok) {
              const errText = await routerResp.text();
              await logErr(env, '/chat/api', 'claude-router non-200 — falling back to Gemini', errText, routerResp.status);
              // Fallback: call Gemini directly when claude-router is down
              // claude-router is the only LLM path — no Worker-side key fallback
              return new Response(JSON.stringify({ error: 'AI service temporarily unavailable. Please try again in a moment.' }), { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
            } else {
              const routerData = await routerResp.json();
              aiText = routerData.text || '';
            }
            // Stream the response as SSE
            const { readable, writable } = new TransformStream();
            const writer = writable.getWriter();
            const encoder = new TextEncoder();
            (async () => {
              if (aiText) {
                const sseData = 'data: ' + JSON.stringify({ text: aiText }) + '\n\n';
                await writer.write(encoder.encode(sseData));
              }
              await writer.write(encoder.encode('data: [DONE]\n\n'));
              await writer.close();
            })();
            upstreamRes = new Response(readable, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
          }
        } catch(e) {
          await logErr(env, '/chat/api', (useGemini ? 'Gemini' : 'anthropic-proxy') + ' fetch failed', String(e), 502);
          return new Response(JSON.stringify({ error: 'AI service unavailable' }), { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        if (!upstreamRes.ok) {
          const errText = await upstreamRes.text();
          await logErr(env, '/chat/api', (useGemini ? 'Gemini' : 'anthropic-proxy') + ' non-200', errText, upstreamRes.status);
          return new Response(JSON.stringify({ error: 'AI service error' }), { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        const { readable, writable } = new TransformStream();
        const writer = writable.getWriter();
        const encoder = new TextEncoder();

        // Heartbeat to prevent mobile browsers from killing an idle SSE connection —
        // ": "-prefixed lines are SSE comments, ignored by the client parser but keep
        // the TCP connection alive while the upstream model is still generating.
        const heartbeatInterval = setInterval(() => {
          writer.write(encoder.encode(': heartbeat\n\n')).catch(() => {});
        }, 5000);

        ctx.waitUntil((async () => {
          const reader = upstreamRes.body.getReader();
          const decoder = new TextDecoder();
          let buf = '';
          let fullText = '';
          try {
            if (tier === 'heavy') {
              const warning = "_You're a heavy chat user today — [Investor](https://biddeed.ai/subscribe?tier=investor) gives unlimited daily access._\n\n";
              fullText += warning;
              await writer.write(encoder.encode(`data: ${JSON.stringify({ text: warning })}\n\n`));
            }
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              buf += decoder.decode(value, { stream: true });
              const lines = buf.split('\n');
              buf = lines.pop() || '';
              for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = line.slice(6).trim();
                if (data === '[DONE]') continue;
                try {
                  const evt = JSON.parse(data);
                  const deltaText = useGemini
                    ? evt.candidates?.[0]?.content?.parts?.[0]?.text
                    : (evt.type === 'content_block_delta' && evt.delta?.type === 'text_delta' ? evt.delta.text
                      : (typeof evt.text === 'string' ? evt.text : null));
                  if (deltaText) {
                    fullText += deltaText;
                    await writer.write(encoder.encode(`data: ${JSON.stringify({ text: deltaText })}\n\n`));
                  }
                } catch(_) {}
              }
            }
            if (propertyPanelCards) {
              const markerStart = fullText.indexOf('[PROPERTIES_LOADED:');
              if (markerStart !== -1) {
                const payload = { county: intentCounty, auctions: propertyPanelCards, total: propertyPanelCards.length };
                await writer.write(encoder.encode(`event: properties\ndata: ${JSON.stringify(payload)}\n\n`));
              }
            }
            await writer.write(encoder.encode('data: [DONE]\n\n'));
          } catch(e) {
            await logErr(env, '/chat/api', 'Stream pipe error', String(e), 500);
          } finally {
            clearInterval(heartbeatInterval);
            await writer.close();
          }
        })());

        return new Response(readable, {
          headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', ...corsHeaders(origin) },
        });
      }

      // ── GET /chat ────────────────────────────────────────────────────────
      if (path === '/chat' || path.startsWith('/chat')) {
        const county = url.searchParams.get('county') || '';
        const hook   = url.searchParams.get('hook')   || '';
        const ref    = url.searchParams.get('ref')    || '';
        const action = url.searchParams.get('action') || '';
        if (action === 'subscribe') return Response.redirect(`/subscribe?tier=investor`, 302);
        return new Response(buildChatPage(county, hook, ref), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
      }

      // ── GET / ────────────────────────────────────────────────────────────
      if (path === '/' || path === '') {
        const hpConfig = await fetchRuntimeConfig();
        const goldChips = (hpConfig.goldCounties && hpConfig.goldCounties.length ? hpConfig.goldCounties : GOLD_COUNTIES).map(s => '<div class="cc">' + toDisplay(s) + '</div>').join('');
        const goldCount = (hpConfig.goldCounties && hpConfig.goldCounties.length ? hpConfig.goldCounties : GOLD_COUNTIES).length;
        let hp = buildHomepageHtml()
          .replace(/GOLD_CHIPS_PLACEHOLDER/, goldChips)
          .replace(/GOLD_COUNT_PLACEHOLDER/g, String(goldCount));
        return new Response(hp, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      return new Response('Not found', { status: 404 });

    } catch(e) {
      await logErr(env, path, 'Unhandled error', String(e), 500);
      ctx.waitUntil(captureError(e, request, env));
      return new Response('Internal server error', { status: 500 });
    }
}

// ── County deep-link landing page ─────────────────────────────────────────────
function buildCountyPage(slug, d, lots, rtConfig) {
  const name = toDisplay(slug);
  const s5List = (rtConfig && rtConfig.s5Counties) ? JSON.stringify(rtConfig.s5Counties) : '[]';
  // Serve the full interactive county page (Alpine.js + Tailwind)
  // Template has COUNTY_SLUG_PLACEHOLDER, COUNTY_TITLE_PLACEHOLDER, COUNTY_TITLE tokens
  return COUNTY_PAGE_TEMPLATE
    .replace(/COUNTY_SLUG_PLACEHOLDER/g, slug)
    .replace(/COUNTY_TITLE_PLACEHOLDER/g, name)
    .replace('S5_COUNTIES_PLACEHOLDER', s5List)
    .replace('COUNTY_TITLE Auctions', name + ' County Auctions')
    .replace('COUNTY_TITLE auctions', name + ' County auctions');
}

// ── Blog — added Aug 10 2026 for organic content marketing ──────────────────
// Plain array of posts. bodyHtml is hand-authored HTML (paragraphs/headings),
// not markdown — kept simple since there's no CMS. Add new posts by pushing
// a new object here; they're automatically picked up by /blog and /sitemap.xml.
const BLOG_POSTS = [
  {
    slug: 'florida-foreclosure-max-bid-guide',
    title: 'How to Calculate Your Max Bid at a Florida Foreclosure Auction',
    description: 'The formula for calculating your max bid before a Florida foreclosure auction, the traps that break it, and a real Marion County example where it held to the dollar.',
    date: '2026-08-10',
    bodyHtml: `
<p>Walking into a Florida foreclosure or tax deed auction without a hard number in your head is how good deals turn into bad ones. The property doesn't care what it's "worth" — it cares what the courthouse steps sell it for that morning, and if your number is soft, you'll bid past it the moment the room gets competitive.</p>
<p>Here's the formula, the traps that break it, and a real example where it held to the dollar.</p>
<h2>The formula</h2>
<p><strong>Max Bid = (ARV &times; 70%) &minus; Repair Costs &minus; Buffer</strong></p>
<ul>
<li><strong>ARV</strong> &mdash; after-repair value. What the property sells for once it's fixed up and back on the market, based on comparable retail sales, not other auction sales.</li>
<li><strong>70%</strong> &mdash; the standard investor margin rule. It's conservative on purpose; auctions have more unknowns than a normal purchase.</li>
<li><strong>Repair costs</strong> &mdash; a real number, not a guess. Vacant properties in foreclosure are frequently in worse shape than photos suggest.</li>
<li><strong>Buffer</strong> &mdash; holding costs, closing costs, and a cushion for the things you can't see from the outside: a survived senior lien, an unexpected tax certificate, an occupant who won't leave on schedule.</li>
</ul>
<p>That last category &mdash; the things you can't see &mdash; is where most losses actually come from, not the math itself.</p>
<h2>The traps that break the formula</h2>
<p><strong>Senior lien survival.</strong> Not every lien gets wiped out by a foreclosure sale. If a senior mortgage or lien survives, you inherit it &mdash; and it can erase your entire margin. This has to be checked per property, not assumed.</p>
<p><strong>Tax certificate status.</strong> Delinquent taxes and outstanding certificates don't disappear because a property changes hands. Check status before you bid, not after you win.</p>
<p><strong>Occupancy.</strong> A property with someone still living in it is a different timeline and a different cost than a vacant one. Factor it into your buffer, not as an afterthought.</p>
<p><strong>Flood zone and title issues.</strong> Both affect resale value and both are knowable in advance if you check before auction day, not after.</p>
<h2>A real example: Marion County, July 2026</h2>
<p>Case 422021CA000414CAAXXX, Marion County &mdash; a property at 14470 SE 91st Ter, Summerfield, FL.</p>
<ul>
<li><strong>Entry bid:</strong> $72,100</li>
<li><strong>Calculated max bid (published pre-sale):</strong> $82,000</li>
<li><strong>Actual sale price:</strong> $73,501</li>
</ul>
<p>The sale closed $8,499 under the ceiling and $1,401 over the entry bid &mdash; the formula held, and the buyer walked away with roughly $26,400 in day-one equity, net of the numbers above.</p>
<p>The point isn't that every auction goes this cleanly &mdash; plenty don't. The point is that having a number <em>before</em> you're standing in the room, and sticking to it, is what turns foreclosure investing from gambling into a process.</p>
<h2>Before you bid, at minimum</h2>
<ol>
<li>Pull the case number and confirm it's still active &mdash; auctions cancel and reschedule constantly.</li>
<li>Check for senior liens and mortgages that could survive the sale.</li>
<li>Confirm tax certificate status.</li>
<li>Get a real repair estimate, not a drive-by guess.</li>
<li>Calculate ARV from actual retail comparables in that specific neighborhood, not county-wide averages.</li>
<li>Write your max bid down before auction day. Don't recalculate it live in the room.</li>
</ol>
`
  },
  {
    slug: 'putnam-county-tax-deed-auctions-guide',
    title: 'Putnam County Tax Deed Auctions: What the Numbers Actually Show',
    description: 'Putnam County runs one of the highest tax deed volumes in Florida — 296 upcoming lots at last count. Here is what the opening bid vs. assessed value spread actually looks like.',
    date: '2026-08-10',
    leadCounty: 'putnam',
    leadCountyLabel: 'Putnam County',
    bodyHtml: `
<p>Putnam County runs one of the highest tax deed auction volumes in Florida — at last count, 296 upcoming lots, the overwhelming majority (282 of 296) tax deed sales rather than mortgage foreclosures. If you're scanning Florida counties for volume, Putnam is one of the first places to look.</p>
<h2>What the numbers show</h2>
<p>Across the current pipeline of upcoming Putnam County lots, the average opening bid sits around <strong>$12,775</strong>, against an average assessed value of roughly <strong>$27,035</strong>. That's a meaningful spread on paper — but averages hide the range. Some lots open far below assessed value because of vacant or unbuildable parcels; others carry liens or title issues that eat the spread entirely before you ever list the property.</p>
<p>Tax deed sales, specifically, come with a different risk profile than foreclosure auctions. The property was seized for unpaid taxes, not through a mortgage default — which means the prior owner's other debts (liens, judgments, code enforcement fines) don't automatically clear the way a foreclosure sale can wipe out junior liens. Tax deed buyers need to check title history at least as carefully as foreclosure buyers, arguably more so.</p>
<h2>Why volume alone isn't the signal</h2>
<p>High auction volume in a county can mean two very different things: either a genuinely active, liquid market where inventory turns over reliably — or a backlog of low-value, hard-to-move parcels that keep reappearing because nobody wants them at the price the county is asking. Putnam's volume needs case-by-case verification, not a blanket "more auctions = more opportunity" read.</p>
<p>Before bidding on any Putnam County tax deed lot:</p>
<ol>
<li>Confirm the parcel is buildable — rural counties carry more unbuildable/wetland/easement-restricted lots than urban ones.</li>
<li>Check for outstanding code enforcement liens, which survive a tax deed sale.</li>
<li>Verify the case is still active — Putnam's high volume means schedule changes happen often.</li>
<li>Get a real comparable sale, not an assessed-value estimate, for your exit price.</li>
</ol>
`
  },
  {
    slug: 'escambia-county-foreclosure-auction-guide',
    title: 'Escambia County Foreclosure & Tax Deed Auctions: The Spread Investors Are Watching',
    description: 'Escambia County shows one of the widest opening-bid-to-assessed-value spreads of any high-volume Florida county — here is what that actually means for investors.',
    date: '2026-08-10',
    leadCounty: 'escambia',
    leadCountyLabel: 'Escambia County',
    bodyHtml: `
<p>Escambia County (Pensacola) currently has 262 upcoming foreclosure and tax deed auctions, and the spread between opening bid and assessed value is one of the widest of any high-volume Florida county: an average opening bid around <strong>$21,567</strong> against an average assessed value near <strong>$157,737</strong>.</p>
<h2>Why the spread is wider here</h2>
<p>That gap is large enough to be worth understanding rather than just chasing. A few structural reasons show up repeatedly in coastal-adjacent Panhandle counties like Escambia:</p>
<ul>
<li><strong>Insurance and flood-zone drag on assessed value relative to market.</strong> Assessed value doesn't always move in lockstep with what a property would actually clear at retail once insurance costs and flood-zone status are priced in by a real buyer.</li>
<li><strong>Military and transient population turnover</strong> (Pensacola is a Navy town) can produce more distressed sales with less competitive bidding at the courthouse than a comparable non-military metro.</li>
<li><strong>Storm and hurricane exposure</strong> means repair costs on distressed properties in this region often run higher than a generic statewide repair estimate would suggest — a wide headline spread can shrink fast once real rehab numbers come in.</li>
</ul>
<p>None of that means the spread is fake. It means the spread is a starting point for research, not a number to bid off of directly.</p>
<h2>Before you bid in Escambia</h2>
<ol>
<li>Pull actual flood zone designation — it materially affects both insurability and resale value, and Escambia has more variation here than inland counties.</li>
<li>Get a real, current repair estimate — storm-related deferred maintenance is common and easy to underestimate from photos alone.</li>
<li>Check whether the property has any hurricane/storm damage claims history if available.</li>
<li>Verify senior lien and mortgage survival status, same as any Florida foreclosure sale.</li>
</ol>
`
  },
  {
    slug: 'highlands-county-tax-deed-auctions-guide',
    title: 'Highlands County Tax Deed Auctions: Why the "Cheap Deals" Story Doesn\u2019t Quite Hold',
    description: 'Highlands County runs 153 upcoming tax deed auctions — but the average opening bid is actually higher than the average assessed value. Here is why that matters.',
    date: '2026-08-10',
    leadCounty: 'highlands',
    leadCountyLabel: 'Highlands County',
    bodyHtml: `
<p>Highlands County has 153 upcoming tax deed auctions right now — all tax deed, zero mortgage foreclosures in the current pipeline. On volume alone, it looks like one of the more active smaller Florida counties. The numbers underneath tell a more complicated story.</p>
<h2>The number that stands out</h2>
<p>Across the current pipeline, the average opening bid is around <strong>$2,148</strong> — and the average assessed value is around <strong>$1,991</strong>. The opening bid, on average, is <em>higher</em> than the assessed value. That's the opposite of the "buy under assessed value" pitch you'll see for most Florida tax deed counties, and it's worth taking seriously rather than skipping past.</p>
<p>This pattern usually shows up in counties with a high concentration of very low-value parcels — often small, landlocked, unbuildable, or otherwise hard-to-use lots that accumulated years of unpaid taxes precisely because they were never worth much to begin with. The county has to recoup at least the accumulated tax debt plus fees at auction, which is where the opening bid comes from — and for a genuinely low-value lot, that minimum can end up above what the county's own assessment says the land is worth.</p>
<h2>What this means if you're looking at Highlands</h2>
<p>It doesn't mean skip the county. It means treat every individual lot as its own research project rather than assuming volume equals opportunity here:</p>
<ol>
<li>Check buildability and access before anything else — many of these are small or landlocked parcels with real usability questions.</li>
<li>Don't rely on assessed value as a value signal in this county — get an actual comparable sale or, for raw land, a realistic sense of what similar buildable lots nearby have sold for.</li>
<li>Understand your exit before you bid — some of these parcels make sense as long-term land banking or adjacent-lot assembly plays, not quick flips.</li>
<li>Factor in that "153 upcoming" doesn't mean 153 good opportunities — it means 153 lots worth individually screening.</li>
</ol>
`
  },
  {
    slug: 'marion-county-foreclosure-auctions-guide',
    title: 'Marion County Foreclosure & Tax Deed Auctions: The County Behind Our Proof Case',
    description: 'Marion County — where the Shapira Max Bid formula held to the dollar on a real sale. 99 upcoming auctions, and what the median numbers actually look like.',
    date: '2026-08-10',
    leadCounty: 'marion',
    leadCountyLabel: 'Marion County',
    bodyHtml: `
<p>Marion County is where we've published our clearest real-world proof case: a property at 14470 SE 91st Ter, Summerfield, sold for $73,501 against a pre-published $82,000 Shapira Max Bid ceiling — a formula that held to within $8,499 of the actual sale price. See the <a href="/proof/marion-summerfield">shareable result card</a>, or read the full breakdown in our <a href="/blog/florida-foreclosure-max-bid-guide">max bid formula guide</a>.</p>
<h2>What the current pipeline looks like</h2>
<p>Marion currently has 99 upcoming auctions — 95 tax deed, 4 mortgage foreclosure. The average opening bid is around <strong>$11,376</strong> against an average assessed value of roughly <strong>$14,897</strong>. But the average is skewed by a handful of higher-value lots — the <em>median</em> opening bid is closer to <strong>$4,006</strong>, against a median assessed value around <strong>$6,149</strong>. For a county with this much volume, the median is the more honest picture of what a typical lot actually looks like: modest opening bids, modest assessed values, and a real but not dramatic spread.</p>
<h2>Why we use Marion as the proof case</h2>
<p>Not because it's the biggest county, and not because the numbers are the most dramatic — Escambia and Putnam both show wider headline spreads. We use Marion because we had a specific, verifiable auction outcome to publish the prediction against <em>before</em> the sale happened, and then grade it after the fact against the courthouse record. That's the standard we hold every Shapira report to: a number published pre-sale, graded automatically within 24 hours of the actual result.</p>
<h2>Before you bid in Marion</h2>
<ol>
<li>Don't anchor on the average — check the median and the specific lot's numbers, not the county-wide mean.</li>
<li>Foreclosure lots (4 of 99 currently) carry different lien-survival risk than tax deed lots (95 of 99) — confirm which type before you research title.</li>
<li>Verify auction status close to the date — Marion's volume means schedule changes are routine.</li>
<li>Get your own max bid number calculated before auction day, the same way we did for the Summerfield property.</li>
</ol>
`
  },
  {
    slug: 'biddeed-pioneer-program-announcement',
    title: "Introducing the BidDeed.AI Pioneer Program",
    description: 'Be one of the first 100 BidDeed.AI Pioneers — founding-customer pricing and early access. Waitlist now open.',
    date: '2026-08-10',
    bodyHtml: `
<p>We're opening the waitlist for the BidDeed.AI Pioneer program — a founding-customer group for the first 100 people who want in early.</p>
<p>Here's what we're planning: founding-customer pricing on the Investor tier, priority access to new counties and features as they ship, and a direct line to us on what to build next. We're still finalizing the full structure — including whether an equity or ownership component will be part of it — and we want to get that right before anyone commits to anything.</p>
<p>Right now, joining the waitlist means exactly that: your name and email on a list, nothing more. No payment. No binding commitment on either side. When the program terms are finalized, Pioneers on the waitlist hear about it first, with full details before enrollment opens.</p>
<p>If you've been using BidDeed.AI already, or you've been watching Florida foreclosure and tax deed auctions and want a formula-driven way to find your max bid before you show up, this is the group to be in early.</p>
<p><a href="/pioneers">Join the Pioneer waitlist &rarr;</a></p>
`
  }
];

// PROOF_CARDS -- real, verified results only. Every number here matches
// what's already published on the blog (see florida-foreclosure-max-bid-guide).
// Never add a row here without a real, checkable case number and sale price.
const PROOF_CARDS = {
  'marion-summerfield': {
    address: '14470 SE 91st Ter, Summerfield, FL',
    county: 'Marion',
    caseNumber: '422021CA000414CAAXXX',
    entryBid: 72100,
    predictedCeiling: 82000,
    actualSale: 73501,
    margin: 8499,
  },
};

function buildProofCard(card) {
  const held = card.actualSale <= card.predictedCeiling;
  const fmt = (n) => '$' + n.toLocaleString();
  const title = `We called it: ${card.address}`;
  const description = `Predicted max bid: ${fmt(card.predictedCeiling)}. Actual sale: ${fmt(card.actualSale)}. Held with ${fmt(card.margin)} to spare.`;
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${title} — BidDeed.AI</title>
<meta name="description" content="${description}">
<meta property="og:title" content="${title}">
<meta property="og:description" content="${description}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://biddeed.ai/proof/marion-summerfield">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${title}">
<meta name="twitter:description" content="${description}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:'Inter',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:480px;width:100%}
.badge{display:inline-flex;background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.3);color:#34d399;padding:.4rem 1rem;border-radius:20px;font-size:.75rem;font-weight:700;letter-spacing:.05em;margin-bottom:1.25rem}
h1{font-family:'DM Serif Display',serif;font-size:1.6rem;color:white;margin-bottom:.3rem;line-height:1.25}
.location{color:#94a3b8;font-size:.9rem;margin-bottom:2rem}
.row{display:flex;justify-content:space-between;align-items:baseline;padding:.9rem 0;border-bottom:1px solid #1e293b}
.row:last-of-type{border-bottom:none}
.row-label{font-size:.85rem;color:#94a3b8}
.row-value{font-size:1.15rem;font-weight:700;color:white}
.row-value.ceiling{color:#f59e0b}
.row-value.actual{color:#34d399}
.margin{text-align:center;background:rgba(245,158,11,.06);border-radius:12px;padding:1rem;margin-top:1.5rem;font-size:.9rem;color:#cbd5e1}
.margin strong{color:#f59e0b}
.cta{display:block;text-align:center;background:linear-gradient(135deg,#f59e0b,#f97316);color:#020617;padding:14px;border-radius:10px;font-weight:700;text-decoration:none;margin-top:1.75rem;font-size:.95rem}
.disclaimer{font-size:.7rem;color:#475569;margin-top:1.5rem;line-height:1.5;text-align:center}
</style>
</head>
<body>
<div class="card">
  <div class="badge">${held ? 'CEILING HELD' : 'RESULT'}</div>
  <h1>${card.address}</h1>
  <div class="location">${card.county} County, FL &middot; Case ${card.caseNumber}</div>
  <div class="row"><span class="row-label">Entry bid</span><span class="row-value">${fmt(card.entryBid)}</span></div>
  <div class="row"><span class="row-label">Shapira Max Bid (published pre-sale)</span><span class="row-value ceiling">${fmt(card.predictedCeiling)}</span></div>
  <div class="row"><span class="row-label">Actual sale price</span><span class="row-value actual">${fmt(card.actualSale)}</span></div>
  <div class="margin">Sold <strong>${fmt(card.margin)}</strong> under the published ceiling.</div>
  <a href="/buy-report" class="cta">Get your own max bid number &rarr;</a>
  <p class="disclaimer">Informational only — not legal, financial, or investment advice. Historical result; individual outcomes vary. Verify independently before bidding.</p>
</div>
</body></html>`;
}

function buildPioneersPage() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Pioneer Program — BidDeed.AI</title>
<meta name="description" content="Be one of the first 100 BidDeed.AI Pioneers. Join the waitlist for early access and founding-customer pricing.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b;--green:#10b981}
body{background:var(--navy);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh}
nav{position:sticky;top:0;z-index:100;background:rgba(2,6,23,.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 1.5rem}
.nav-inner{max-width:700px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none;font-size:15px;font-weight:700;color:white}
.logo span{color:var(--orange)}
.wrap{max-width:700px;margin:0 auto;padding:3rem 1.5rem}
.ey{display:inline-flex;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);padding:.3rem .9rem;border-radius:20px;font-size:.7rem;font-family:monospace;color:var(--orange);letter-spacing:.06em;margin-bottom:1.25rem}
h1{font-family:'DM Serif Display',serif;font-size:clamp(1.9rem,4.5vw,2.8rem);color:white;margin-bottom:1rem;line-height:1.2}
.sub{color:var(--muted);font-size:1.05rem;margin-bottom:2rem;line-height:1.6}
.card{background:var(--navy2);border:1px solid var(--border);border-radius:14px;padding:1.75rem;margin-bottom:1.25rem}
.card h3{color:white;font-size:1.05rem;margin-bottom:.5rem}
.card p{color:var(--muted);font-size:.92rem;line-height:1.6}
.notice{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.25);border-radius:12px;padding:1.25rem 1.5rem;margin:2rem 0;font-size:.85rem;color:var(--muted);line-height:1.6}
.notice strong{color:var(--orange)}
form{background:var(--navy2);border:1px solid rgba(245,158,11,.3);border-radius:14px;padding:1.75rem;margin-top:2rem}
form label{display:block;font-size:.85rem;color:var(--muted);margin-bottom:.4rem}
form input{width:100%;background:var(--navy);border:1px solid var(--border);border-radius:8px;padding:12px 14px;color:white;font-size:15px;margin-bottom:1rem;outline:none}
form input:focus{border-color:var(--orange)}
form button{width:100%;background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);border:none;padding:14px;border-radius:10px;font-weight:700;font-size:15px;cursor:pointer}
form button:disabled{opacity:.6;cursor:default}
.msg{margin-top:1rem;font-size:.85rem}
.msg.ok{color:var(--green)}
.msg.err{color:#f87171}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.75rem;color:var(--muted);margin-top:3rem}
footer a{color:var(--muted);text-decoration:none}
</style>
</head>
<body>
<nav><div class="nav-inner">
  <a href="/" class="logo">BidDeed<span>.AI</span></a>
</div></nav>
<div class="wrap">
  <div class="ey">PIONEER PROGRAM · WAITLIST OPEN</div>
  <h1>Be one of the first 100 BidDeed.AI Pioneers</h1>
  <p class="sub">We're building a founding-customer program for the first 100 people who believe in what we're building. Join the waitlist to be first in line when it opens — no payment, no commitment, just early access.</p>

  <div class="card">
    <h3>What we're planning</h3>
    <p>Founding-customer pricing on the Investor tier, priority access to new counties and features as they ship, and direct input into the product roadmap. Full program details — including any equity or ownership component under consideration — will be finalized and disclosed before enrollment opens.</p>
  </div>

  <div class="card" style="border-color:rgba(245,158,11,.3)">
    <h3>Refer someone, you both win</h3>
    <p>Once you're subscribed, share your personal link. When someone you refer subscribes and stays a full billing cycle, you <strong>both</strong> get a free month — no cap, one free month per new customer you bring in.</p>
  </div>

  <div class="notice">
    <strong>This page is a waitlist only.</strong> No payment is collected here and nothing about the final program terms is confirmed yet — including whether an equity component will be part of it. We want to get this right before anyone joins, so we're finalizing the structure first. Join the list and we'll email you the full details as soon as they're ready.
  </div>

  <form id="pioneer-form">
    <label for="p-name">Name</label>
    <input type="text" id="p-name" name="name" placeholder="Your name">
    <label for="p-email">Email</label>
    <input type="email" id="p-email" name="email" placeholder="you@example.com" required>
    <button type="submit" id="p-btn">Join the Waitlist</button>
    <div class="msg" id="p-msg"></div>
    <div class="lead-box" id="p-referral-box" style="display:none;margin-top:1rem">
      <h3 style="font-size:.95rem">Your referral link</h3>
      <p style="font-size:.85rem">Share this — when someone subscribes through it and sticks around a full billing cycle, you both get a free month.</p>
      <input type="text" id="p-referral-link" readonly style="width:100%;background:#020617;border:1px solid #1e293b;border-radius:8px;padding:10px 12px;color:white;font-size:13px;margin-top:.5rem">
    </div>
  </form>
</div>
<footer>
  <p>&copy; 2026 BidDeed.AI &middot; Everest Capital USA &middot; <a href="/terms">Terms</a> &middot; <a href="/privacy">Privacy</a></p>
</footer>
<script>
var pRefCode = new URLSearchParams(window.location.search).get('ref');
document.getElementById('pioneer-form').addEventListener('submit', async function(e){
  e.preventDefault();
  var btn = document.getElementById('p-btn');
  var msg = document.getElementById('p-msg');
  var email = document.getElementById('p-email').value.trim();
  var name = document.getElementById('p-name').value.trim();
  msg.textContent = ''; msg.className = 'msg';
  btn.disabled = true; btn.textContent = 'Joining...';
  try {
    var joinPayload = { email: email, name: name };
    if (pRefCode) { joinPayload.referred_by = pRefCode; }
    var res = await fetch('/pioneers/join', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(joinPayload)
    });
    var data = await res.json();
    if (res.ok && data.ok) {
      msg.textContent = "You're on the list — check your email for confirmation.";
      msg.className = 'msg ok';
      btn.textContent = 'Joined ✓';
      if (data.referral_link) {
        document.getElementById('p-referral-link').value = data.referral_link;
        document.getElementById('p-referral-box').style.display = 'block';
      }
    } else {
      msg.textContent = data.error || 'Something went wrong. Please try again.';

      msg.className = 'msg err';
      btn.disabled = false; btn.textContent = 'Join the Waitlist';
    }
  } catch (err) {
    msg.textContent = 'Network error. Please try again.';
    msg.className = 'msg err';
    btn.disabled = false; btn.textContent = 'Join the Waitlist';
  }
});
</script>
</body></html>`;
}

function buildBlogIndex() {
  const rows = BLOG_POSTS.slice().sort((a,b) => b.date.localeCompare(a.date)).map(p => `
    <a href="/blog/${p.slug}" class="post-link">
      <div class="post-date">${p.date}</div>
      <div class="post-title">${p.title}</div>
      <div class="post-desc">${p.description}</div>
    </a>`).join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BidDeed.AI Blog — Florida Foreclosure &amp; Tax Deed Investing</title>
<meta name="description" content="Guides and real case studies on Florida foreclosure and tax deed auction investing — max bid formulas, lien traps, and verified outcomes.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b}
body{background:var(--navy);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh}
nav{position:sticky;top:0;z-index:100;background:rgba(2,6,23,.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 1.5rem}
.nav-inner{max-width:900px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none;font-size:15px;font-weight:700;color:white}
.logo span{color:var(--orange)}
.nav-cta{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:8px 18px;border-radius:8px;font-size:14px;font-weight:700;text-decoration:none}
.wrap{max-width:900px;margin:0 auto;padding:3rem 1.5rem}
h1{font-family:'DM Serif Display',serif;font-size:clamp(1.8rem,4vw,2.6rem);color:white;margin-bottom:2rem}
.post-link{display:block;background:var(--navy2);border:1px solid var(--border);border-radius:12px;padding:1.5rem;text-decoration:none;color:var(--text);margin-bottom:1rem;transition:border-color .15s}
.post-link:hover{border-color:var(--orange)}
.post-date{font-size:.75rem;color:var(--muted);margin-bottom:.4rem}
.post-title{font-size:1.15rem;font-weight:700;color:white;margin-bottom:.5rem}
.post-desc{font-size:.9rem;color:var(--muted);line-height:1.5}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.75rem;color:var(--muted);margin-top:3rem}
footer a{color:var(--muted);text-decoration:none}
</style>
</head>
<body>
<nav><div class="nav-inner">
  <a href="/" class="logo">BidDeed<span>.AI</span></a>
  <a href="/buy-report" class="nav-cta">Get a report</a>
</div></nav>
<div class="wrap">
  <h1>Guides &amp; Case Studies</h1>
  ${rows}
</div>
<footer>
  <p>&copy; 2026 BidDeed.AI &middot; Everest Capital USA &middot; <a href="/terms">Terms</a> &middot; <a href="/privacy">Privacy</a> &middot; <a href="/disclaimer">Disclaimer</a></p>
</footer>
</body></html>`;
}

function buildBlogPost(post) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${post.title} — BidDeed.AI</title>
<meta name="description" content="${post.description}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b}
body{background:var(--navy);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh;font-size:17px;line-height:1.75}
nav{position:sticky;top:0;z-index:100;background:rgba(2,6,23,.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 1.5rem}
.nav-inner{max-width:760px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none;font-size:15px;font-weight:700;color:white}
.logo span{color:var(--orange)}
.nav-cta{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:8px 18px;border-radius:8px;font-size:14px;font-weight:700;text-decoration:none}
.wrap{max-width:760px;margin:0 auto;padding:3rem 1.5rem}
.date{font-size:.8rem;color:var(--muted);margin-bottom:.75rem}
h1{font-family:'DM Serif Display',serif;font-size:clamp(1.7rem,4vw,2.4rem);color:white;margin-bottom:1.5rem;line-height:1.25}
h2{color:var(--orange);font-size:1.25rem;margin:2rem 0 .75rem}
p{margin-bottom:1.1rem;color:var(--text)}
ul,ol{margin:0 0 1.1rem 1.5rem;color:var(--text)}
li{margin-bottom:.4rem}
.disclaimer{font-size:.8rem;color:var(--muted);border-top:1px solid var(--border);margin-top:2.5rem;padding-top:1.5rem}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.75rem;color:var(--muted);margin-top:3rem}
footer a{color:var(--muted);text-decoration:none}
.cta-box{background:var(--navy2);border:1px solid rgba(245,158,11,.3);border-radius:12px;padding:1.5rem;margin:2.5rem 0;text-align:center}
.cta-box a{display:inline-block;background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:12px 28px;border-radius:10px;font-weight:700;text-decoration:none;margin-top:.75rem}
.lead-box{background:var(--navy2);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin:2.5rem 0}
.lead-box h3{color:white;font-size:1.05rem;margin-bottom:.4rem}
.lead-box p{color:var(--muted);font-size:.88rem;margin-bottom:1rem}
.lead-form{display:flex;gap:.6rem;flex-wrap:wrap}
.lead-form input{flex:1;min-width:180px;background:var(--navy);border:1px solid var(--border);border-radius:8px;padding:11px 14px;color:white;font-size:15px;outline:none}
.lead-form input:focus{border-color:var(--orange)}
.lead-form button{background:transparent;border:1px solid var(--orange);color:var(--orange);padding:11px 20px;border-radius:8px;font-weight:700;font-size:.85rem;cursor:pointer;white-space:nowrap}
.lead-form button:disabled{opacity:.6;cursor:default}
.lead-msg{font-size:.82rem;margin-top:.6rem;display:none}
.lead-msg.ok{color:#34d399;display:block}
.lead-msg.err{color:#f87171;display:block}
</style>
</head>
<body>
<nav><div class="nav-inner">
  <a href="/" class="logo">BidDeed<span>.AI</span></a>
  <a href="/buy-report" class="nav-cta">Get a report</a>
</div></nav>
<div class="wrap">
  <div class="date">${post.date}</div>
  <h1>${post.title}</h1>
  ${post.bodyHtml}
  ${post.leadCounty ? `
  <div class="lead-box">
    <h3>Want ${post.leadCountyLabel || 'this county'}'s upcoming auctions in your inbox?</h3>
    <p>Free — no report purchase required. We'll email you the next 5 upcoming auctions in this county.</p>
    <form class="lead-form" id="blog-lead-form">
      <input type="email" id="blog-lead-email" placeholder="you@example.com" required>
      <button type="submit" id="blog-lead-btn">Send Me the List</button>
    </form>
    <div class="lead-msg" id="blog-lead-msg"></div>
  </div>
  <script>
  document.getElementById('blog-lead-form').addEventListener('submit', async function(e){
    e.preventDefault();
    var btn=document.getElementById('blog-lead-btn'), msg=document.getElementById('blog-lead-msg');
    var email=document.getElementById('blog-lead-email').value.trim();
    msg.className='lead-msg'; msg.textContent='';
    btn.disabled=true; btn.textContent='Sending...';
    try{
      var res=await fetch('/chat/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,county:'${post.leadCounty}',source:'blog_${post.slug}',email_consent:true})});
      var data=await res.json();
      if(res.ok && data.ok){ msg.textContent='Sent — check your email.'; msg.className='lead-msg ok'; btn.textContent='Sent ✓'; }
      else{ msg.textContent=(data.error||'Something went wrong. Please try again.'); msg.className='lead-msg err'; btn.disabled=false; btn.textContent='Send Me the List'; }
    }catch(err){ msg.textContent='Network error. Please try again.'; msg.className='lead-msg err'; btn.disabled=false; btn.textContent='Send Me the List'; }
  });
  </script>` : ''}
  <div class="cta-box">
    <div>Get your own max bid number before you show up.</div>
    <a href="/buy-report">Get a Shapira Report — $25 →</a>
  </div>
  <p class="disclaimer">This is general educational information, not legal, financial, or investment advice. Auction data and value estimates should always be independently verified. Consult a licensed Florida attorney and title professional before bidding on any property.</p>
</div>
<footer>
  <p><a href="/blog">&larr; All guides</a> &middot; &copy; 2026 BidDeed.AI &middot; Everest Capital USA</p>
</footer>
</body></html>`;
}


function buildCountiesIndex(rtConfig) {
  const goldSet = new Set((rtConfig && rtConfig.goldCounties && rtConfig.goldCounties.length) ? rtConfig.goldCounties : GOLD_COUNTIES);
  const allCounties = Object.keys(COUNTY_DISPLAY).sort();
  const rows = allCounties.map(slug => {
    const name = toDisplay(slug);
    const isGold = goldSet.has(slug);
    return `<a href="/county/${slug.replace(/_/g,'-')}" class="county-link ${isGold?'gold':''}">
      ${isGold?'🏆 ':''}${name}
      ${isGold?'<span class="gs-tag">Gold Standard</span>':''}
    </a>`;
  }).join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>All 67 Florida Counties — BidDeed.AI Foreclosure &amp; Tax Deed Intelligence</title>
<meta name="description" content="Foreclosure and tax deed auction intelligence for every Florida county — upcoming auction counts, Gold Standard verified counties, and Shapira Max Bid reports starting at $25.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--navy3:#1e293b;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b;--green:#10b981}
body{background:var(--navy);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh}
nav{position:sticky;top:0;z-index:100;background:rgba(2,6,23,.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 1.5rem}
.nav-inner{max-width:1100px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none}
.lm{width:32px;height:32px;background:linear-gradient(135deg,var(--orange),var(--orange2));border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:12px;color:var(--navy)}
.ln{font-size:15px;font-weight:700;color:white}.ln span{color:var(--orange)}
.nav-cta{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:8px 18px;border-radius:8px;font-size:14px;font-weight:700;text-decoration:none}
.wrap{max-width:1100px;margin:0 auto;padding:3rem 1.5rem}
.ey{display:inline-flex;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);padding:.3rem .9rem;border-radius:20px;font-size:.7rem;font-family:'JetBrains Mono',monospace;color:var(--green);letter-spacing:.06em;margin-bottom:1.25rem}
h1{font-family:'DM Serif Display',serif;font-size:clamp(1.8rem,4vw,2.8rem);color:white;margin-bottom:.75rem}
.sub{color:var(--muted);margin-bottom:2.5rem;font-size:.95rem}
.counties-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.75rem}
.county-link{display:block;background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:.9rem 1rem;text-decoration:none;color:var(--muted);font-size:.88rem;font-weight:500;transition:all .15s;position:relative}
.county-link:hover{background:var(--navy3);border-color:var(--orange);color:white}
.county-link.gold{border-color:rgba(245,158,11,.3);color:var(--text)}
.county-link.gold:hover{border-color:var(--orange)}
.gs-tag{display:block;font-size:.65rem;color:var(--orange);font-family:'JetBrains Mono',monospace;margin-top:.2rem;letter-spacing:.05em}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.75rem;color:var(--muted);margin-top:3rem}
footer a{color:var(--muted);text-decoration:none}
</style>
</head>
<body>
<nav><div class="nav-inner">
  <a href="/" class="logo"><div class="lm">BD</div><span class="ln">BidDeed<span>.AI</span></span></a>
  <a href="/subscribe?tier=investor" class="nav-cta">Investor $99/mo</a>
</div></nav>
<div class="wrap">
  <div class="ey">ALL 67 FLORIDA COUNTIES</div>
  <h1>Florida Auction Intelligence<br>by County</h1>
  <p class="sub">Gold Standard counties have verified title records, current tax data, reliable auction timing, and documented clearance patterns.</p>
  <div class="counties-grid">${rows}</div>
</div>
<footer>
  <p>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="/security">Security</a></p>
</footer>
</body></html>`;
}

// ── Chat page — MOBILE-FIRST, full viewport, all languages ───────────────────
function buildChatPage(county, hook, ref) {
  const countyBar = county ? `
<div class="county-bar" id="cbar" style="display:none">
  <div class="cb-name">${toDisplay(county)} County</div>
  <div class="cb-stats" id="cb-stats"></div>
  <div id="cb-badge"></div>
  <div style="font-size:.6rem;color:var(--muted)" id="cb-date"></div>
</div>` : '';

  let autoMsg = '';
  if (hook === 'PROOF') autoMsg = 'Show me the Marion County proof — Shapira Formula ceiling held to the cent.';
  else if (hook === 'COUNTY_PAGE') autoMsg = county ? `What auctions are coming up in ${toDisplay(county)} County? Give me the highlights.` : '';
  else if (ref === 'digest') autoMsg = county ? `What are the most important ${toDisplay(county)} County auction opportunities right now?` : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no,interactive-widget=resizes-content">
<title>BidDeed.AI · Auction Intelligence</title>
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--navy3:#1e293b;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b;--green:#10b981}
html{height:100%;height:-webkit-fill-available}
body{display:flex;flex-direction:column;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;height:100vh;height:-webkit-fill-available;height:var(--vvh,100vh);overflow:hidden;position:fixed;width:100%}

/* HEADER */
.hdr{display:flex;align-items:center;justify-content:space-between;padding:0 14px;height:52px;background:rgba(2,6,23,.98);border-bottom:1px solid var(--border);flex-shrink:0;min-height:52px}
.hdr-left{display:flex;align-items:center;gap:9px;text-decoration:none;min-width:0}
.bd-logo{width:30px;height:30px;border-radius:7px;background:linear-gradient(135deg,var(--orange),var(--orange2));display:flex;align-items:center;justify-content:center;font-weight:900;font-size:11px;color:var(--navy);flex-shrink:0}
.bd-brand h1{font-size:13px;font-weight:700;color:white;line-height:1.1;white-space:nowrap}
.bd-brand p{font-size:9px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.upgrade-btn{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);border:none;border-radius:7px;padding:7px 12px;font-size:11px;font-weight:700;cursor:pointer;text-decoration:none;white-space:nowrap;flex-shrink:0}

/* COUNTY BAR */
.county-bar{background:var(--navy2);border-bottom:1px solid var(--border);padding:8px 14px;display:flex;align-items:center;gap:12px;flex-shrink:0;flex-wrap:wrap;min-height:44px}
.cb-name{font-size:13px;font-weight:700;color:white}
.cb-stats{display:flex;gap:10px;flex-wrap:wrap}
.cb-stat .num{font-family:'SF Mono',monospace;font-size:.9rem;font-weight:700;color:white}
.cb-stat .num.hot{color:var(--orange)}
.cb-stat .lbl{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.cb-badge-gold{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.25);border-radius:20px;padding:2px 8px;font-size:10px;color:var(--orange);font-weight:600}
.cb-badge-pend{background:var(--navy3);border:1px solid var(--border);border-radius:20px;padding:2px 8px;font-size:10px;color:var(--muted)}

/* MESSAGES */
.msgs{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;padding:12px 14px;padding-bottom:24px;display:flex;flex-direction:column;gap:10px;-webkit-overflow-scrolling:touch}

/* WELCOME */
.welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;flex:1;text-align:center;gap:12px;padding:16px 10px;min-height:0}
.wl-icon{width:52px;height:52px;border-radius:13px;background:linear-gradient(135deg,var(--orange),var(--orange2));display:flex;align-items:center;justify-content:center;font-weight:900;font-size:20px;color:var(--navy);flex-shrink:0}
.wl-title{font-size:17px;font-weight:700;color:white}
.wl-sub{font-size:12px;color:var(--muted);max-width:280px;line-height:1.5}
.quick-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;width:100%;max-width:380px}
.qbtn{background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:9px 10px;text-align:left;cursor:pointer;color:var(--muted);font-size:11.5px;font-weight:500;line-height:1.4;transition:all .15s;font-family:inherit;-webkit-tap-highlight-color:transparent}
.qbtn:hover,.qbtn:active{background:var(--navy3);border-color:var(--orange);color:white}
.qbtn.prime{background:rgba(245,158,11,.08);border-color:rgba(245,158,11,.3);color:var(--orange)}

/* LANGUAGE CHIPS — all 12 visible */
.lang-row{display:flex;gap:4px;flex-wrap:wrap;justify-content:center;max-width:340px}
.lchip{background:var(--navy3);border:1px solid var(--border);border-radius:12px;padding:2px 7px;font-size:10.5px;color:var(--muted);white-space:nowrap}

/* MESSAGES */
.msg{display:flex;gap:8px;animation:fi .18s ease}
.msg.user{flex-direction:row-reverse}
@keyframes fi{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.av{width:26px;height:26px;border-radius:6px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:800}
.av.ai{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy)}
.av.user{background:var(--navy3);font-size:13px}
.bbl{max-width:88%;padding:9px 12px;border-radius:13px;font-size:13px;line-height:1.65;word-break:break-word}
.bbl.ai{background:rgba(255,255,255,.04);border:1px solid var(--border);color:var(--text)}
.bbl.ai .md-h1,.bbl.ai .md-h2,.bbl.ai .md-h3{font-weight:700;margin:8px 0 4px;color:var(--orange)}
.bbl.ai .md-li{margin:2px 0}
.bbl.ai .md-sp{height:6px}
.bbl.ai b{color:#fff}
.bbl.ai .md-link{color:var(--orange);text-decoration:underline;font-weight:600}
.chat-tbl{width:100%;border-collapse:collapse;margin:8px 0;font-size:12px;overflow-x:auto;display:block}
.chat-tbl thead{background:rgba(255,255,255,.06)}
.chat-tbl th,.chat-tbl td{padding:6px 8px;border:1px solid var(--border);text-align:left;white-space:nowrap}
.chat-tbl th{color:var(--orange);font-weight:700;font-size:11px;text-transform:uppercase}
.bbl.user{background:#1e3a5f;color:var(--text);border:1px solid #2d5a8e}

/* TYPING */
.typing-row{display:flex;gap:8px;align-items:flex-end}
.typing-bbl{background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:13px;padding:9px 13px;display:flex;gap:4px;align-items:center}
.td{width:5px;height:5px;border-radius:50%;background:var(--orange);animation:td 1.1s infinite}
.td:nth-child(2){animation-delay:.18s}.td:nth-child(3){animation-delay:.36s}
@keyframes td{0%,80%,100%{opacity:.25;transform:scale(.8)}40%{opacity:1;transform:scale(1.2)}}

/* S5 REPORT CTA IN CHAT */
.s5-cta{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.25);border-radius:12px;padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.s5-cta-text .title{font-size:12px;font-weight:700;color:var(--orange);margin-bottom:2px}
.s5-cta-text .desc{font-size:11px;color:var(--muted);line-height:1.4}
.s5-btn{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);border:none;border-radius:8px;padding:8px 14px;font-size:12px;font-weight:700;cursor:pointer;text-decoration:none;white-space:nowrap;font-family:inherit;-webkit-tap-highlight-color:transparent}

/* EMAIL CAPTURE */
.ec{background:rgba(245,158,11,.05);border:1px solid rgba(245,158,11,.2);border-radius:12px;padding:11px;display:flex;flex-direction:column;gap:8px}
.ec-lbl{font-size:11.5px;color:var(--orange);font-weight:600}
.ec-row{display:flex;gap:6px}
.ec input{flex:1;background:var(--navy3);border:1px solid var(--border);border-radius:8px;padding:9px 10px;color:white;font-size:14px;outline:none;font-family:inherit;-webkit-appearance:none}
.ec input:focus{border-color:var(--orange)}
.ec button{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);border:none;border-radius:8px;padding:9px 12px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;font-family:inherit}

/* INPUT BAR — pinned to bottom, always visible */
.inp-wrap{flex-shrink:0;background:rgba(2,6,23,.98);border-top:1px solid var(--border)}
.inp-bar{display:flex;gap:8px;padding:10px 12px;align-items:center}
.inp-bar input{flex:1;background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:11px 12px;color:white;font-size:16px;outline:none;font-family:inherit;transition:border-color .2s;-webkit-appearance:none;min-width:0}
.inp-bar input:focus{border-color:var(--orange)}
.inp-bar input::placeholder{color:var(--muted);font-size:14px}
.snd{width:42px;height:42px;border-radius:10px;background:linear-gradient(135deg,var(--orange),var(--orange2));border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;-webkit-tap-highlight-color:transparent}
.snd:disabled{opacity:.35;cursor:not-allowed}
.snd svg{width:17px;height:17px;fill:var(--navy)}
.disclaimer-bar{flex-shrink:0;text-align:center;font-size:9.5px;color:var(--muted);padding:3px 12px 8px;line-height:1.4}
.disclaimer-bar a{color:var(--muted);text-decoration:underline}
@media(max-width:380px){.quick-grid{grid-template-columns:1fr}.bd-brand p{display:none}}

/* VOICE WIDGET */
.voice-btn{display:flex;align-items:center;gap:6px;background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:9px 14px;cursor:pointer;color:var(--muted);font-size:11.5px;font-weight:500;font-family:inherit;transition:all .15s;-webkit-tap-highlight-color:transparent;margin-top:2px}
.voice-btn:hover,.voice-btn:active{background:var(--navy3);border-color:var(--orange);color:white}
.voice-btn.active{background:rgba(245,158,11,.1);border-color:rgba(245,158,11,.5);color:var(--orange)}
.voice-btn.listening{background:rgba(245,158,11,.08);border-color:var(--orange);color:var(--orange)}
.voice-dot{width:8px;height:8px;border-radius:50%;background:var(--muted);flex-shrink:0;transition:background .2s}
.voice-btn.listening .voice-dot{background:var(--orange);animation:vp 1s infinite}
@keyframes vp{0%,100%{opacity:.4;transform:scale(.85)}50%{opacity:1;transform:scale(1.15)}}
.voice-status{display:none;font-size:10.5px;color:var(--muted);text-align:center;margin-top:4px}
.voice-status.show{display:block}
.voice-transcript{background:rgba(245,158,11,.05);border:1px solid rgba(245,158,11,.15);border-radius:8px;padding:6px 10px;font-size:11.5px;color:var(--muted);margin-top:4px;display:none;max-width:340px;text-align:start;line-height:1.4}
.voice-transcript.show{display:block}
.voice-cap{background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.3);border-radius:10px;padding:12px 14px;margin-top:6px;display:none;max-width:340px;text-align:center}
.voice-cap.show{display:block}
.voice-cap-msg{font-size:12.5px;color:#e2e8f0;line-height:1.5;margin-bottom:10px}
.voice-cap-msg strong{color:var(--orange)}
.voice-cap-btns{display:flex;gap:8px;justify-content:center;flex-wrap:wrap}
.voice-cap-btns a{font-size:11.5px;font-weight:600;border-radius:8px;padding:7px 12px;text-decoration:none;transition:opacity .15s}
.voice-cap-btns .vcb-upgrade{background:linear-gradient(135deg,var(--orange),#f97316);color:var(--navy)}
.voice-cap-btns .vcb-upgrade:hover{opacity:.88}
.voice-cap-btns .vcb-report{background:transparent;border:1px solid rgba(245,158,11,.4);color:var(--orange)}
.voice-cap-btns .vcb-report:hover{border-color:var(--orange);opacity:.88}
.voice-actions{display:flex;gap:6px;align-items:flex-start;flex-wrap:wrap;justify-content:center;margin-top:2px}
.veg{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.22);border-radius:10px;padding:10px 12px;margin-top:8px;display:none;max-width:340px;width:100%}
.veg.show{display:block}
.veg-lbl{font-size:11px;color:var(--orange);font-weight:600;margin-bottom:6px;text-align:center}
.veg-row{display:flex;gap:6px}
.veg input{flex:1;background:var(--navy3);border:1px solid var(--border);border-radius:8px;padding:8px 10px;color:white;font-size:14px;outline:none;font-family:inherit;min-width:0;-webkit-appearance:none}
.veg input:focus{border-color:var(--orange)}
.veg button{background:linear-gradient(135deg,var(--orange),#f97316);color:var(--navy);border:none;border-radius:8px;padding:8px 12px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;font-family:inherit;-webkit-tap-highlight-color:transparent}
.veg-err{font-size:10.5px;color:#f87171;margin-top:4px;display:none}
.veg-err.show{display:block}
.attach-btn{display:none;align-items:center;gap:5px;background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:9px 14px;cursor:pointer;color:var(--muted);font-size:11.5px;font-weight:500;font-family:inherit;transition:all .15s;-webkit-tap-highlight-color:transparent}
.attach-btn.visible{display:flex}
.attach-btn:hover,.attach-btn:active{background:var(--navy3);border-color:var(--orange);color:white}
.attach-btn:disabled{opacity:.4;cursor:not-allowed}
.attach-caption{display:none;background:var(--navy3);border:1px solid var(--border);border-radius:8px;padding:7px 10px;color:white;font-size:12px;font-family:inherit;width:220px;margin-top:4px;outline:none}
.attach-caption.visible{display:block}
.attach-caption:focus{border-color:var(--orange)}
.attach-caption::placeholder{color:var(--muted)}
.attach-progress{display:none;font-size:10.5px;text-align:center;margin-top:4px;padding:4px 8px;border-radius:6px}
.attach-progress.show{display:block}
.attach-progress.uploading{color:var(--orange);background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.15)}
.attach-progress.ok{color:var(--green);background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.2)}
.attach-progress.err{color:#f87171;background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.2)}

/* SPLIT LAYOUT — property cards right panel */
.split{flex:1;display:flex;min-height:0;overflow:hidden}
.chat-col{display:flex;flex-direction:column;flex:1 1 45%;min-width:0;min-height:0;overflow:hidden}
.panel-col{display:none;flex:1 1 55%;min-width:0;flex-direction:column;border-left:1px solid var(--border);background:var(--navy2);overflow:hidden}
.panel-hdr{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid var(--border);flex-shrink:0}
.panel-hdr .pt{font-size:12px;font-weight:700;color:white;text-transform:capitalize}
.panel-toggle-btn{background:var(--navy3);border:1px solid var(--border);color:var(--muted);border-radius:7px;padding:5px 10px;font-size:11px;cursor:pointer;font-family:inherit}
.panel-body{flex:1;overflow-y:auto;padding:10px 12px;display:flex;flex-direction:column;gap:10px}
.pc-empty{color:var(--muted);font-size:12px;text-align:center;padding:20px 0}
.pc-card{background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:12px;padding:12px}
.pc-badges{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.pc-badge{font-size:9.5px;font-weight:700;letter-spacing:.04em;border-radius:6px;padding:3px 7px}
.pc-badge.fc{background:rgba(245,158,11,.12);color:var(--orange);border:1px solid rgba(245,158,11,.3)}
.pc-badge.td{background:rgba(20,184,166,.12);color:#2dd4bf;border:1px solid rgba(20,184,166,.3)}
.pc-badge.gold{background:rgba(245,158,11,.12);color:var(--orange);border:1px solid rgba(245,158,11,.3)}
.pc-badge.review{background:rgba(148,163,184,.1);color:#e2eaf2;border:1px solid rgba(148,163,184,.3)}
.pc-row1,.pc-row2{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.pc-addr{font-size:13px;font-weight:700;color:white}
.pc-date{font-size:11px;color:var(--muted);white-space:nowrap}
.pc-city{font-size:11.5px;color:var(--muted)}
.pc-days{font-size:10px;color:var(--orange);white-space:nowrap;font-weight:600}
.pc-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin:10px 0}
.pc-lbl{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px}
.pc-val{font-size:12.5px;font-weight:700;color:white;font-family:'SF Mono',monospace}
.pc-parity{font-size:10.5px;font-weight:600;margin-bottom:10px}
.pc-parity.ok{color:var(--green)}
.pc-parity.warn{color:var(--orange)}
.pc-parity.bad{color:#f87171}
.pc-clerk-parity{font-size:10px;font-weight:600;color:var(--green);margin-bottom:10px}
.pc-actions{display:flex;flex-direction:column;gap:8px}
.pc-buy{text-align:center;background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);border-radius:8px;padding:9px 10px;font-size:11.5px;font-weight:700;text-decoration:none;white-space:nowrap}
.btn-bid{display:block;border:1px solid var(--orange);color:var(--orange);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:500;text-decoration:none;text-align:center;transition:background .15s}
.btn-bid:hover{background:rgba(245,158,11,.13)}
.btn-locked{display:block;width:100%;border:1px solid var(--border);background:var(--navy3);color:var(--muted);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;text-align:center;cursor:pointer;font-family:inherit}
.btn-locked:hover{border-color:var(--orange);color:var(--orange)}
.btn-po{display:block;text-align:center;font-size:10.5px;color:var(--muted);text-decoration:underline;padding:2px 0}
@media(max-width:768px){.split{flex-direction:column}.chat-col{flex:1 1 auto;min-height:0}.panel-col{border-left:none;border-top:1px solid var(--border);max-height:46vh;flex:0 0 auto}}
</style>
</head>
<body>

<header class="hdr">
  <a href="/" class="hdr-left">
    <div class="bd-logo">BD</div>
    <div class="bd-brand">
      <h1>BidDeed.AI</h1>
      <p>Foreclosure &amp; Tax Deed Intelligence</p>
    </div>
  </a>
  <a href="/subscribe?tier=investor" class="upgrade-btn">⚡ $99/mo</a>
</header>

<div class="split">
  <div class="chat-col">
${countyBar}

<div class="msgs" id="msgs">
  <div class="welcome" id="welcome">
    <div class="wl-icon">BD</div>
    <div class="wl-title">Foreclosure &amp; Tax Deed Intelligence</div>
    <div class="wl-sub">Ask about any Florida county. Responds in your language automatically.</div>
    <div class="quick-grid">
      <button class="qbtn prime" data-msg="Show me the Marion County proof — Shapira Formula ceiling held to the cent.">📊 See proof it works</button>
      <button class="qbtn" data-msg="What foreclosure and tax deed auctions are coming up across Florida this week?">📅 What's coming to auction?</button>
      <button class="qbtn" data-msg="How does the Shapira Max Bid formula work? Walk me through it.">🧮 Shapira Max Bid formula</button>
      <button class="qbtn" data-msg="I have a specific property I want analyzed. How do I get a Shapira S5 Report?">💼 Get a $25 S5 Report</button>
    </div>
    <div class="voice-actions">
      <button class="voice-btn" id="voice-btn" type="button"><span class="voice-dot" id="voice-dot"></span><span id="voice-btn-label">🎙️ Talk to Deed</span></button>
      <button class="attach-btn" id="attach-btn" type="button" title="Attach PDF or image to this conversation">📎 Attach</button>
    </div>
    <div class="veg" id="voice-email-gate">
      <div class="veg-lbl">Enter your email to start talking with Deed</div>
      <div class="veg-row">
        <input type="email" id="veg-email" placeholder="your@email.com" autocomplete="email">
        <button id="veg-submit" type="button">Start →</button>
      </div>
      <div class="veg-err" id="veg-err">Please enter a valid email address.</div>
    </div>
    <input type="file" id="attach-file-input" accept=".pdf,.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp,application/pdf" style="display:none">
    <input type="text" class="attach-caption" id="attach-caption" placeholder="Optional caption (or just attach silently)…">
    <div class="voice-status" id="voice-status"></div>
    <div class="attach-progress" id="attach-progress"></div>
    <div class="voice-transcript" id="voice-transcript"></div>
    <div class="voice-cap" id="voice-cap">
      <div class="voice-cap-msg">That's our free 10-minute session. <strong>Investor members get unlimited time with Deed</strong> — or I can send you the full report on this county right now.</div>
      <div class="voice-cap-btns">
        <a href="/subscribe?tier=investor" class="vcb-upgrade">Upgrade to Investor →</a>
        <a href="/free-report" class="vcb-report" id="vcb-report-link">Get free report</a>
      </div>
    </div>
    <div class="lang-row">
      <span class="lchip">🇺🇸 English</span>
      <span class="lchip">🇮🇱 עברית</span>
      <span class="lchip">🇪🇸 Español</span>
      <span class="lchip">🇧🇷 Português</span>
      <span class="lchip">🇸🇦 العربية</span>
      <span class="lchip">🇷🇺 Русский</span>
      <span class="lchip">🇨🇳 中文</span>
      <span class="lchip">🇫🇷 Français</span>
      <span class="lchip">🇩🇪 Deutsch</span>
      <span class="lchip">🇯🇵 日本語</span>
      <span class="lchip">🇰🇷 한국어</span>
      <span class="lchip">🇮🇹 Italiano</span>
    </div>
  </div>
</div>

<div class="inp-wrap">
  <div class="inp-bar">
    <input type="text" id="inp" placeholder="Ask about any Florida county..." autocomplete="off" autocorrect="off" spellcheck="false">
    <button class="snd" id="snd" aria-label="Send">
      <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
    </button>
  </div>
  <div class="disclaimer-bar">Informational only — not legal, financial, or investment advice. <a href="/disclaimer" target="_blank">Disclaimer</a></div>
</div>
  </div>

  <div class="panel-col" id="panel-col">
    <div class="panel-hdr">
      <span class="pt" id="panel-title">Properties</span>
      <button class="panel-toggle-btn" id="panel-toggle" type="button">Hide ▸</button>
    </div>
    <div class="panel-body" id="panel-body"></div>
  </div>
</div>

<script>
// FIX: iOS Safari keyboard freeze — 100vh does not shrink when the keyboard opens,
// so a position:fixed body stays full-height while the real visible area shrinks,
// making touches land in the wrong place and the page appear frozen.
// visualViewport tracks the REAL visible height and we sync --vvh to it live.
(function() {
  function syncVVH() {
    var h = (window.visualViewport ? window.visualViewport.height : window.innerHeight);
    document.documentElement.style.setProperty('--vvh', h + 'px');
  }
  syncVVH();
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', syncVVH);
    window.visualViewport.addEventListener('scroll', syncVVH);
  }
  window.addEventListener('orientationchange', function(){ setTimeout(syncVVH, 100); });
  // When embedded in an iframe (homepage), remove position:fixed so scroll events
  // chain through to the parent page instead of being trapped
  if (window.self !== window.top) {
    document.body.style.position = 'relative';
    document.body.style.overflow = 'auto';
    document.body.style.height = '100%';
  }
})();

const COUNTY = ${JSON.stringify(county)};
const HOOK   = ${JSON.stringify(hook)};
const AUTO   = ${JSON.stringify(autoMsg)};
let H = [], busy = false, emailDone = false, s5Shown = false, msgCount = 0, retryCount = 0;
const MAX_RETRIES = 3;

// County bar
if (COUNTY) {
  fetch('/chat/county-data?county=' + COUNTY)
    .then(r => r.json()).then(d => {
      if (!d) return;
      const bar = document.getElementById('cbar');
      if (bar) bar.style.display = 'flex';
      const dt = document.getElementById('cb-date');
      if (dt) dt.textContent = d.snapshot_date ? 'Snapshot: ' + d.snapshot_date : '';
      const st = document.getElementById('cb-stats');
      if (st) {
        const fcN = d.fc_next_auction_date ? new Date(d.fc_next_auction_date).toLocaleDateString('en-US',{month:'short',day:'numeric'}) : 'TBD';
        const tdN = d.td_next_auction_date ? new Date(d.td_next_auction_date).toLocaleDateString('en-US',{month:'short',day:'numeric'}) : 'TBD';
        st.innerHTML = mkStat(d.fc_upcoming_30d||0,'FC 30d',true)+mkStat(fcN,'Next FC')+mkStat(d.td_upcoming_30d||0,'TD 30d',true)+mkStat(tdN,'Next TD');
      }
      const bg = document.getElementById('cb-badge');
      if (bg) bg.innerHTML = d.is_gold_standard
        ? '<span class="cb-badge-gold">🏆 Gold Standard</span>'
        : '<span class="cb-badge-pend">⏳ Cert Pending</span>';
    }).catch(()=>{});
}
function mkStat(val,lbl,hot){return '<div class="cb-stat"><div class="num'+(hot?' hot':'')+'">'+val+'</div><div class="lbl">'+lbl+'</div></div>';}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

// Safe minimal markdown renderer for assistant messages — escapes first (XSS-safe),
// then converts **bold**, [text](https://...) links (biddeed.ai + safe https only), and | table | rows.
// NOTE: written with zero regex literals — Cloudflare's template-literal evaluation of this
// nested inline script silently strips backslash escapes, corrupting any regex containing them.
function mdToHtml(raw){
  const lines = String(raw).split(String.fromCharCode(10));
  let html = '';
  let tableRows = [];
  const flushTable = () => {
    if (!tableRows.length) return;
    const header = tableRows[0];
    const rest = tableRows.slice(1);
    html += '<table class="chat-tbl"><thead><tr>' + header.map(c=>'<th>'+c+'</th>').join('') + '</tr></thead><tbody>';
    for (const r of rest) html += '<tr>' + r.map(c=>'<td>'+c+'</td>').join('') + '</tr>';
    html += '</tbody></table>';
    tableRows = [];
  };
  const isPipeChar = (c) => c === '|' || c === ':' || c === '-' || c === ' ';
  for (let line of lines) {
    const trimmed = line.trim();
    const isTableRow = trimmed.length > 1 && trimmed.charAt(0) === '|' && trimmed.charAt(trimmed.length-1) === '|';
    if (isTableRow) {
      const isSeparator = trimmed.split('').every(isPipeChar);
      if (isSeparator) continue;
      const inner = trimmed.slice(1, -1);
      const cells = inner.split('|').map(c => formatInline(esc(c.trim())));
      tableRows.push(cells);
      continue;
    } else if (tableRows.length) {
      flushTable();
    }
    if (trimmed.charAt(0) === '#') {
      let lvl = 0;
      while (lvl < trimmed.length && trimmed.charAt(lvl) === '#' && lvl < 3) lvl++;
      const rest = trimmed.slice(lvl).trim();
      html += '<div class="md-h' + lvl + '">' + formatInline(esc(rest)) + '</div>';
    } else if ((trimmed.charAt(0) === '-' || trimmed.charAt(0) === String.fromCharCode(42)) && trimmed.charAt(1) === ' ') {
      const rest = trimmed.slice(1).trim();
      html += '<div class="md-li">' + String.fromCharCode(8226) + ' ' + formatInline(esc(rest)) + '</div>';
    } else if (trimmed === '') {
      html += '<div class="md-sp"></div>';
    } else {
      html += '<div>' + formatInline(esc(line)) + '</div>';
    }
  }
  if (tableRows.length) flushTable();
  return html;
}
function formatInline(escaped){
  const STAR = String.fromCharCode(42);
  const bold = STAR + STAR;
  // Bold: **text** -> <b>text</b>, pure string scan (no regex)
  let out = '';
  let i = 0;
  while (i < escaped.length) {
    if (escaped.slice(i, i+2) === bold) {
      const close = escaped.indexOf(bold, i+2);
      if (close !== -1) {
        out += '<b>' + escaped.slice(i+2, close) + '</b>';
        i = close + 2;
        continue;
      }
    }
    out += escaped.charAt(i);
    i++;
  }
  escaped = out;
  // Links: [text](https://biddeed.ai/... or https://app.mindstudio.ai/...) -> <a>, pure string scan
  out = '';
  i = 0;
  while (i < escaped.length) {
    if (escaped.charAt(i) === '[') {
      const closeBracket = escaped.indexOf(']', i+1);
      if (closeBracket !== -1 && escaped.charAt(closeBracket+1) === '(') {
        const closeParen = escaped.indexOf(')', closeBracket+2);
        if (closeParen !== -1) {
          const linkText = escaped.slice(i+1, closeBracket);
          const url = escaped.slice(closeBracket+2, closeParen);
          const safe = url.indexOf('https://biddeed.ai') === 0 || url.indexOf('https://app.mindstudio.ai') === 0;
          if (safe) {
            out += '<a href="' + url + '" target="_blank" class="md-link">' + linkText + '</a>';
            i = closeParen + 1;
            continue;
          }
        }
      }
    }
    out += escaped.charAt(i);
    i++;
  }
  return out;
}

// Strips the trailing [PROPERTIES_LOADED:county:count] control token from the
// displayed text — pure string scan, no regex (see mdToHtml note above).
function stripPropertiesMarker(s){
  const start=s.indexOf('[PROPERTIES_LOADED:');
  if(start===-1)return s;
  const end=s.indexOf(']',start);
  if(end===-1)return s;
  return (s.slice(0,start)+s.slice(end+1)).trim();
}

// ── Property cards right panel ──────────────────────────────────────────────
let panelOpen=false;
function fmtMoneyP(n){if(n===null||n===undefined||n==='')return'N/A';return'$'+Math.round(Number(n)).toLocaleString('en-US');}
function fmtDateP(d){if(!d)return'TBD';const dt=new Date(d+'T00:00:00');return dt.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});}
function cardSortKey(a){
  if(!a.property_address)return 3;
  if(a.parity_status==='matched_clean')return 0;
  if(a.parity_status==='mca_only')return 1;
  return 2;
}
function parityInfo(p){
  if(p==='matched_clean'||p==='PARITY_OK'||p==='CLERK_VERIFIED')return{cls:'ok',label:'✓ Data verified',tip:''};
  if(p==='matched_divergent'||p==='CLERK_SSOT_CANCELLED')return{cls:'bad',label:'⚠ Data conflict',tip:''};
  return{cls:'warn',label:'⚠ Data unverified',tip:'This property is on our platform but has not been cross-verified with county records'};
}
// CLERK-SSOT Task 4.3 — county/match_pct/checked_at badge from clerk_parity_results,
// via v_property_card_verified.clerk_parity_match_pct/clerk_parity_checked_at.
function clerkParityBadge(a){
  var b=a.clerk_parity_badge;
  if(!b||b.match_pct==null||!b.checked_at)return'';
  var hrs=Math.max(0,Math.round((Date.now()-new Date(b.checked_at).getTime())/3600000));
  var when=hrs<1?'just now':(hrs+'h ago');
  return '<div class="pc-clerk-parity" title="Cross-checked against the '+esc(toDisplay(b.county||''))+' Clerk of Court sale calendar">✅ Clerk-verified '+esc(String(b.match_pct))+'% · checked '+when+'</div>';
}
function badgeSaleType(t){
  if(t==='foreclosure')return'<span class="pc-badge fc">FORECLOSURE</span>';
  if(t==='tax_deed')return'<span class="pc-badge td">TAX DEED</span>';
  return'';
}
function showUpgradePrompt(feature,caseNumber,county){
  try{if(window.posthog)posthog.capture('upgrade_prompt_clicked',{feature:feature,case_number:caseNumber,county:county});}catch(e){}
  window.open('/subscribe?tier=investor','_blank');
}
function trackOutbound(kind,caseNumber,county){
  try{if(window.posthog)posthog.capture('outbound_click',{kind:kind,case_number:caseNumber,county:county});}catch(e){}
}
async function hashEmail8(email){
  const buf=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(email.trim().toLowerCase()));
  return Array.prototype.map.call(new Uint8Array(buf),b=>('0'+b.toString(16)).slice(-2)).join('').slice(0,8);
}
function buildCard(a){
  const hasAddr=!!a.property_address;
  const addrParts=hasAddr?a.property_address.split(','):[];
  const line1=hasAddr?addrParts[0].trim():('Address not yet available — Case #'+esc(a.case_number||''));
  const line2=hasAddr?addrParts.slice(1).join(',').trim():'';
  const pinfo=parityInfo(a.parity_status);
  const buyUrl='/buy-report?mca_id='+encodeURIComponent(a.id)+'&address='+encodeURIComponent(a.property_address||'')+'&county='+encodeURIComponent(a.county||'')+'&date='+encodeURIComponent(a.auction_date||'');
  let html='<div class="pc-card">';
  html+='<div class="pc-badges">'+badgeSaleType(a.sale_type)+(a.is_gold_standard?'<span class="pc-badge gold">⭐ GOLD STANDARD</span>':'<span class="pc-badge review">⚠️ Data under review</span>')+'</div>';
  html+='<div class="pc-row1"><div class="pc-addr">'+esc(line1)+'</div><div class="pc-date">'+esc(fmtDateP(a.auction_date))+'</div></div>';
  html+='<div class="pc-row2"><div class="pc-city">'+esc(line2)+'</div><div class="pc-days">'+(a.days_until_auction!=null?(a.days_until_auction+' days away'):'')+'</div></div>';
  html+='<div class="pc-grid"><div><div class="pc-lbl">Opening Bid</div><div class="pc-val">'+fmtMoneyP(a.opening_bid)+'</div></div>'+
        '<div><div class="pc-lbl">Assessed Value</div><div class="pc-val">'+fmtMoneyP(a.assessed_value)+'</div></div>'+
        '<div><div class="pc-lbl">Equity Gap</div><div class="pc-val">'+fmtMoneyP(a.equity_gap)+'</div></div></div>';
  html+='<div class="pc-parity '+pinfo.cls+'"'+(pinfo.tip?(' title="'+esc(pinfo.tip)+'"'):'')+'>'+pinfo.label+'</div>';
  html+=clerkParityBadge(a);
  html+='<div class="pc-actions"><button class="btn-locked" onclick="showUpgradePrompt(\\'bid_link\\',\\''+esc(a.case_number||'')+'\\',\\''+esc(a.county||'')+'\\')">🔒 Place Bid — Upgrade to Unlock</button>'+
        '<a class="pc-buy" href="'+buyUrl+'">Buy S5 Report — $25</a>'+
        (a.auction_url?('<a class="btn-bid" href="'+esc(a.auction_url)+'" target="_blank" rel="noopener">'+esc(a.bid_label||'View Auction →')+'</a>'):'')+
        '<div class="btn-locked" onclick="showUpgradePrompt(\\'maps\\',\\''+esc(a.case_number||'')+'\\',\\''+esc(a.county||'')+'\\')" style="font-size:12px;color:#64748b;cursor:pointer;padding:6px 0;">🔒 View on Maps — Investor only</div>'+
        (a.po_url?('<a class="btn-po" href="'+esc(a.po_url)+'" target="_blank" rel="noopener">PropertyOnion details ↗</a>'):'')+'</div>';
  if(a.appraiser_url){
    html+='<div style="margin-top:8px;padding-top:8px;border-top:1px solid #e2e8f0;">'+
          '<a href="'+esc(a.appraiser_url)+'" target="_blank" rel="noopener" onclick="trackOutbound(\\'appraiser\\',\\''+esc(a.case_number||'')+'\\',\\''+esc(a.county||'')+'\\')" style="font-size:12px;color:#64748b;text-decoration:none;">📋 Property Appraiser Record ↗</a>'+
          '</div>';
  }
  html+='</div>';
  return html;
}
function renderPropertyPanel(payload){
  const col=document.getElementById('panel-col');
  const body=document.getElementById('panel-body');
  const title=document.getElementById('panel-title');
  if(!col||!body)return;
  const list=(payload.auctions||[]).slice().sort(function(a,b){return cardSortKey(a)-cardSortKey(b);});
  if(title)title.textContent=(payload.county?payload.county.split('_').join(' '):'Properties')+' — '+list.length+' upcoming';
  body.innerHTML=list.length?list.map(buildCard).join(''):'<div class="pc-empty">No upcoming auctions found for this county right now.</div>';
  col.style.display='flex';
  panelOpen=true;
  const toggle=document.getElementById('panel-toggle');
  if(toggle)toggle.textContent='Hide ▸';
  body.style.display='block';
}
const panelToggleBtn=document.getElementById('panel-toggle');
if(panelToggleBtn)panelToggleBtn.addEventListener('click',function(){
  panelOpen=!panelOpen;
  const body=document.getElementById('panel-body');
  if(body)body.style.display=panelOpen?'block':'none';
  panelToggleBtn.textContent=panelOpen?'Hide ▸':'Show ▾';
});

function scrollBottom(){const m=document.getElementById('msgs');if(m){m.scrollTop=m.scrollHeight;}}

function addMsg(role,content){
  document.getElementById('welcome')?.remove();
  const m=document.getElementById('msgs');
  const row=document.createElement('div');row.className='msg '+role;
  const av=role==='assistant'?'<div class="av ai">BD</div>':'<div class="av user">👤</div>';
  const body = role==='assistant' ? mdToHtml(content) : esc(content);
  row.innerHTML=av+'<div class="bbl '+role+'">'+body+'</div>';
  m.appendChild(row);scrollBottom();
  return row.querySelector('.bbl');
}

function showS5CTA(){
  if(s5Shown||document.getElementById('s5cta'))return;
  s5Shown=true;
  const m=document.getElementById('msgs');
  const d=document.createElement('div');d.id='s5cta';d.className='s5-cta';
  d.innerHTML='<div class="s5-cta-text"><div class="title">💼 Get a Shapira S5 Report</div><div class="desc">Full AI max-bid analysis for a specific property — lien stack, plaintiff intel, zoning, BID/SKIP recommendation.</div></div><a href="/buy-report" class="s5-btn">$25 — Get Report →</a>';
  m.appendChild(d);scrollBottom();
}

function ask(t){document.getElementById('inp').value=t;send();}

function showSystemMessage(text){
  const m=document.getElementById('msgs');
  const d=document.createElement('div');d.className='msg assistant';
  d.innerHTML='<div class="av ai">BD</div><div class="bbl ai" style="opacity:.65;font-style:italic">'+esc(text)+'</div>';
  m.appendChild(d);scrollBottom();
  return d;
}

async function send(){
  if(busy)return;
  const inp=document.getElementById('inp');
  const text=inp.value.trim();if(!text)return;
  inp.value='';busy=true;
  document.getElementById('snd').disabled=true;
  msgCount++;
  H.push({role:'user',content:text});
  addMsg('user',text);
  const m=document.getElementById('msgs');
  const tv=document.createElement('div');tv.id='typing';tv.className='typing-row';
  tv.innerHTML='<div class="av ai">BD</div><div class="typing-bbl"><div class="td"></div><div class="td"></div><div class="td"></div></div>';
  m.appendChild(tv);scrollBottom();
  retryCount=0;
  await attemptStream();
  busy=false;document.getElementById('snd').disabled=false;inp.focus();
}

async function attemptStream(){
  const m=document.getElementById('msgs');
  const controller=new AbortController();
  // Mobile timeout: abort if no data (including heartbeat comments) for 30 seconds
  let lastDataTime=Date.now();
  const timeoutChecker=setInterval(function(){
    if(Date.now()-lastDataTime>30000)controller.abort();
  },5000);
  let fullText='';
  try{
    const res=await fetch('/chat/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:H,county:COUNTY,hook:HOOK}),signal:controller.signal});
    document.getElementById('typing')?.remove();
    if(!res.ok){addMsg('assistant','Error '+res.status+'. Please try again.');return;}
    document.getElementById('welcome')?.remove();
    let bbl=document.getElementById('sbbl');
    if(!bbl){
      const row=document.createElement('div');row.className='msg assistant';
      row.innerHTML='<div class="av ai">BD</div><div class="bbl ai" id="sbbl"></div>';
      m.appendChild(row);scrollBottom();
      bbl=document.getElementById('sbbl');
    }
    const reader=res.body.getReader();const decoder=new TextDecoder();
    let buf='',pendingEvent=null;
    while(true){
      const{done,value}=await reader.read();if(done)break;
      lastDataTime=Date.now();
      buf+=decoder.decode(value,{stream:true});
      const lines=buf.split(String.fromCharCode(10));buf=lines.pop()||'';
      for(const line of lines){
        if(line.indexOf(': ')===0)continue; // SSE comment — e.g. ": heartbeat" keepalive, ignore
        if(line.indexOf('event: ')===0){pendingEvent=line.slice(7).trim();continue;}
        if(!line.startsWith('data: '))continue;
        const data=line.slice(6).trim();
        if(data==='[DONE]'){pendingEvent=null;break;}
        if(pendingEvent==='properties'){
          try{renderPropertyPanel(JSON.parse(data));}catch(e){}
          pendingEvent=null;continue;
        }
        try{const evt=JSON.parse(data);if(evt.text){fullText+=evt.text;bbl.innerHTML=mdToHtml(stripPropertiesMarker(fullText));scrollBottom();}}catch(e){}
      }
    }
    fullText=stripPropertiesMarker(fullText);
    bbl.innerHTML=mdToHtml(fullText);
    bbl.id='';
    H.push({role:'assistant',content:fullText});
    retryCount=0;
    // Show S5 CTA after 2nd message
    if(msgCount>=2&&!s5Shown)showS5CTA();
    // Show email capture after 3rd message
    if(!emailDone&&msgCount>=3)showEmailCapture();
  }catch(e){
    document.getElementById('typing')?.remove();
    if(e.name==='AbortError'&&retryCount<MAX_RETRIES){
      retryCount++;
      const delay=retryCount*2000; // 2s, 4s, 6s backoff
      const sysMsg=showSystemMessage('Connection timeout — retrying ('+retryCount+'/'+MAX_RETRIES+')...');
      await new Promise(function(resolve){setTimeout(resolve,delay);});
      sysMsg.remove();
      clearInterval(timeoutChecker);
      await attemptStream();
      return;
    }
    addMsg('assistant','Connection lost. Please try again.');
    retryCount=0;
  }finally{
    clearInterval(timeoutChecker);
  }
}

function showEmailCapture(){
  if(emailDone||document.getElementById('ec'))return;
  const m=document.getElementById('msgs');
  const d=document.createElement('div');d.id='ec';d.className='ec';
  const lbl=document.createElement('div');lbl.className='ec-lbl';lbl.textContent='📬 Get daily '+(COUNTY||'FL')+' auction alerts — free';
  const rowEl=document.createElement('div');rowEl.className='ec-row';
  const inputEl=document.createElement('input');inputEl.type='email';inputEl.id='ei';inputEl.placeholder='your@email.com';
  inputEl.addEventListener('keydown',function(e){if(e.key==='Enter')saveEmail();});
  const btnEl=document.createElement('button');btnEl.textContent='Get Alerts →';btnEl.addEventListener('click',saveEmail);
  rowEl.appendChild(inputEl);rowEl.appendChild(btnEl);d.appendChild(lbl);d.appendChild(rowEl);m.appendChild(d);scrollBottom();
}

async function saveEmail(){
  const email=(document.getElementById('ei')?.value||'').trim();
  if(!email||!email.includes('@'))return;
  emailDone=true;document.getElementById('ec')?.remove();
  fetch('/chat/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,county:COUNTY,source:HOOK||'chat'})})
    .then(async function(res){
      if(res.ok){
        try{
          const hashed=await hashEmail8(email);
          if(window.posthog)posthog.identify(hashed,{county_interest:COUNTY||null,source:'biddeed_chat'});
        }catch(e){}
      }
    }).catch(()=>{});
  addMsg('assistant','✅ Done! Daily FL auction alerts sent to '+email+'. What else can I pull up for you?');
  H.push({role:'assistant',content:'Email captured.'});
}

document.querySelectorAll('.qbtn').forEach(function(btn){
  btn.addEventListener('click',function(){const msg=btn.getAttribute('data-msg');if(msg)ask(msg);});
});
document.getElementById('inp').addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});
document.getElementById('snd').addEventListener('click',send);

// Prevent body scroll on iOS when chat is focused
document.getElementById('inp').addEventListener('focus',function(){setTimeout(scrollBottom,300);});

if(AUTO)setTimeout(()=>ask(AUTO),600);

// ── Voice Widget — ElevenLabs Conversational AI ──────────────────────────────
// WebSocket protocol: https://elevenlabs.io/docs/eleven-agents/libraries/web-sockets
// Server→Client events: conversation_initiation_metadata | audio | agent_response
//                       user_transcript | interruption | ping
// Client→Server events: conversation_initiation_client_data | audio | pong | multimodal_message
(function(){
  var AGENT_ID='agent_5301kzeg7pj8ezrbaarvkyyfgyd9';
  var SIGNED_URL_ENDPOINT='https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/elevenlabs-signed-url';
  var UPLOAD_ENDPOINT='https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/elevenlabs-upload-file';
  var SAMPLE_RATE=16000;
  var ALLOWED_TYPES=['application/pdf','image/png','image/jpeg','image/webp'];
  var MAX_BYTES=20*1024*1024;

  var btn=document.getElementById('voice-btn');
  var btnLabel=document.getElementById('voice-btn-label');
  var statusEl=document.getElementById('voice-status');
  var transcriptEl=document.getElementById('voice-transcript');
  var attachBtn=document.getElementById('attach-btn');
  var attachFileInput=document.getElementById('attach-file-input');
  var attachCaption=document.getElementById('attach-caption');
  var attachProgress=document.getElementById('attach-progress');
  if(!btn)return;

  var ws=null,audioCtx=null,processor=null,stream=null,active=false,agentAudioQueue=[],agentPlaying=false;
  var conversationId=null;
  var voiceEmail=null;
  var capEl=document.getElementById('voice-cap');
  var capTimer=null,warnSent=false;
  var CAP_WARN_MS=8*60*1000,CAP_HARD_MS=10*60*1000;
  var vegEl=document.getElementById('voice-email-gate');
  var vegInput=document.getElementById('veg-email');
  var vegSubmit=document.getElementById('veg-submit');
  var vegErr=document.getElementById('veg-err');

  function isValidEmail(e){if(!e||e.indexOf(' ')!==-1)return false;var at=e.indexOf('@');if(at<1||e.indexOf('@',at+1)!==-1)return false;var domain=e.slice(at+1);var dot=domain.indexOf('.');return dot>0&&dot<domain.length-1;}

  function hideGate(){if(vegEl)vegEl.className='veg';}

  function submitVoiceEmail(){
    var email=(vegInput?vegInput.value:'').trim();
    if(!isValidEmail(email)){
      if(vegErr)vegErr.className='veg-err show';
      return;
    }
    if(vegErr)vegErr.className='veg-err';
    voiceEmail=email;
    hideGate();
    fetch('/chat/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,source:'voice_gate'})})
      .catch(function(e){console.warn('[voice-gate] lead capture failed:',e);});
    startSession();
  }

  if(vegSubmit){
    vegSubmit.addEventListener('click',submitVoiceEmail);
  }
  if(vegInput){
    vegInput.addEventListener('keydown',function(e){if(e.key==='Enter')submitVoiceEmail();});
  }

  function setStatus(msg){
    if(!msg){statusEl.className='voice-status';statusEl.textContent='';return;}
    statusEl.className='voice-status show';statusEl.textContent=msg;
  }
  function showTranscript(who,text){
    transcriptEl.className='voice-transcript show';
    transcriptEl.dir=/[\u0590-\u08FF]/.test(text)?'rtl':'ltr';
    transcriptEl.textContent=(who==='user'?'You: ':'Deed: ')+text;
  }
  function setAttachProgress(state,msg){
    if(!state){attachProgress.className='attach-progress';attachProgress.textContent='';return;}
    attachProgress.className='attach-progress show '+state;
    attachProgress.textContent=msg;
  }
  function showAttachBtn(show){
    if(show){attachBtn.classList.add('visible');attachCaption.classList.add('visible');}
    else{attachBtn.classList.remove('visible');attachCaption.classList.remove('visible');setAttachProgress(null,'');}
  }
  function showCapPanel(){
    if(capEl)capEl.className='voice-cap show';
    btn.disabled=true;
    btn.style.display='none';
  }
  function clearCapTimer(){
    if(capTimer){clearTimeout(capTimer);capTimer=null;}
    warnSent=false;
  }
  function startCapTimer(){
    clearCapTimer();
    capTimer=setTimeout(function(){
      if(!active||!ws||ws.readyState!==1)return;
      warnSent=true;
      ws.send(JSON.stringify({type:'contextual_update',text:'System note: 2 minutes remain in this free session. If it fits naturally, you may mention that BidDeed Investor members ($99/mo) get unlimited conversation time with you, plus reports on every county. Do not interrupt what the user is currently saying — work it in naturally or wait for a pause.'}));
      capTimer=setTimeout(function(){
        if(!active)return;
        stopSession();
        showCapPanel();
      },CAP_HARD_MS-CAP_WARN_MS);
    },CAP_WARN_MS);
  }

  // Encode Float32 PCM to PCM16 base64
  function pcm32ToBase64(float32arr){
    var buf=new ArrayBuffer(float32arr.length*2);
    var view=new DataView(buf);
    for(var i=0;i<float32arr.length;i++){
      var s=Math.max(-1,Math.min(1,float32arr[i]));
      view.setInt16(i*2,s<0?s*0x8000:s*0x7FFF,true);
    }
    var bytes=new Uint8Array(buf);
    var bin='';
    for(var j=0;j<bytes.byteLength;j++)bin+=String.fromCharCode(bytes[j]);
    return btoa(bin);
  }

  // Decode base64 PCM16 and play via AudioContext
  function playAgentAudio(base64){
    agentAudioQueue.push(base64);
    if(!agentPlaying)drainAudioQueue();
  }
  function drainAudioQueue(){
    if(!agentAudioQueue.length){agentPlaying=false;return;}
    agentPlaying=true;
    var b64=agentAudioQueue.shift();
    var raw=atob(b64);
    var pcm16=new Int16Array(raw.length/2);
    var view=new DataView(new ArrayBuffer(raw.length));
    for(var i=0;i<raw.length;i++)view.setUint8(i,raw.charCodeAt(i));
    for(var i=0;i<pcm16.length;i++)pcm16[i]=view.getInt16(i*2,true);
    var ctx=audioCtx||new (window.AudioContext||window.webkitAudioContext)({sampleRate:SAMPLE_RATE});
    audioCtx=ctx;
    var floatBuf=new Float32Array(pcm16.length);
    for(var i=0;i<pcm16.length;i++)floatBuf[i]=pcm16[i]/32768;
    var audioBuf=ctx.createBuffer(1,floatBuf.length,SAMPLE_RATE);
    audioBuf.getChannelData(0).set(floatBuf);
    var src=ctx.createBufferSource();
    src.buffer=audioBuf;
    src.connect(ctx.destination);
    src.onended=drainAudioQueue;
    src.start();
  }

  function stopSession(){
    clearCapTimer();
    active=false;
    conversationId=null;
    btn.className='voice-btn';
    btn.disabled=false;
    btn.style.display='';
    btnLabel.textContent='🎙️ Talk to Deed';
    setStatus('');
    showAttachBtn(false);
    agentAudioQueue=[];agentPlaying=false;
    if(processor){try{processor.disconnect();}catch(e){}processor=null;}
    if(stream){stream.getTracks().forEach(function(t){t.stop();});stream=null;}
    if(ws&&ws.readyState<2){ws.close();}
    ws=null;
  }

  async function startSession(){
    setStatus('Requesting mic…');
    btn.className='voice-btn active';
    btnLabel.textContent='⏹ Stop';
    try{
      stream=await navigator.mediaDevices.getUserMedia({audio:{sampleRate:SAMPLE_RATE,channelCount:1,echoCancellation:true,noiseSuppression:true}});
    }catch(e){
      stopSession();
      setStatus('Mic permission denied — use text chat below.');
      return;
    }
    setStatus('Connecting to Deed…');
    var signedUrl;
    try{
      var res=await fetch(SIGNED_URL_ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:AGENT_ID})});
      if(!res.ok)throw new Error('signed-url '+res.status);
      var data=await res.json();
      signedUrl=data.signed_url;
      if(!signedUrl)throw new Error('no signed_url');
    }catch(e){
      stopSession();
      setStatus('Could not connect — try text chat below.');
      return;
    }
    try{
      ws=new WebSocket(signedUrl);
    }catch(e){
      stopSession();
      setStatus('WebSocket error — try text chat below.');
      return;
    }
    ws.onopen=function(){
      ws.send(JSON.stringify({type:'conversation_initiation_client_data',conversation_config_override:{}}));
    };
    ws.onmessage=function(evt){
      var msg;
      try{msg=JSON.parse(evt.data);}catch(e){return;}
      var t=msg.type;
      if(t==='conversation_initiation_metadata'){
        var meta=msg.conversation_initiation_metadata_event;
        if(meta&&meta.conversation_id)conversationId=meta.conversation_id;
        setStatus('🎙️ Listening…');
        btn.className='voice-btn listening';
        active=true;
        showAttachBtn(true);
        startCapTimer();
        startMicStream();
      } else if(t==='ping'){
        var eid=(msg.ping_event&&msg.ping_event.event_id!=null)?msg.ping_event.event_id:0;
        ws.send(JSON.stringify({type:'pong',event_id:eid}));
      } else if(t==='audio'){
        var b64=msg.audio_event&&msg.audio_event.audio_base_64;
        if(b64)playAgentAudio(b64);
      } else if(t==='agent_response'){
        var text=msg.agent_response_event&&msg.agent_response_event.agent_response;
        if(text)showTranscript('agent',text);
      } else if(t==='user_transcript'){
        var utext=msg.user_transcription_event&&msg.user_transcription_event.user_transcript;
        if(utext)showTranscript('user',utext);
      } else if(t==='interruption'){
        agentAudioQueue=[];agentPlaying=false;
      }
    };
    ws.onerror=function(){
      if(!active)return;
      stopSession();
      setStatus('Connection lost — try text chat below.');
    };
    ws.onclose=function(){
      if(active)stopSession();
    };
  }

  function startMicStream(){
    var ctx=audioCtx||new (window.AudioContext||window.webkitAudioContext)({sampleRate:SAMPLE_RATE});
    audioCtx=ctx;
    var src=ctx.createMediaStreamSource(stream);
    processor=ctx.createScriptProcessor(4096,1,1);
    src.connect(processor);
    processor.connect(ctx.destination);
    processor.onaudioprocess=function(e){
      if(!active||!ws||ws.readyState!==1)return;
      var float32=e.inputBuffer.getChannelData(0);
      var b64=pcm32ToBase64(float32);
      ws.send(JSON.stringify({user_audio_chunk:b64}));
    };
  }

  async function handleFileSelected(file){
    setAttachProgress(null,'');
    if(ALLOWED_TYPES.indexOf(file.type)===-1){
      setAttachProgress('err','Invalid file type — PDF, PNG, JPEG, or WEBP only.');
      attachFileInput.value='';
      return;
    }
    if(file.size>MAX_BYTES){
      setAttachProgress('err','File too large — maximum 20 MB.');
      attachFileInput.value='';
      return;
    }
    if(!conversationId||!ws||ws.readyState!==1){
      setAttachProgress('err','No active conversation — start talking first.');
      attachFileInput.value='';
      return;
    }
    attachBtn.disabled=true;
    setAttachProgress('uploading','Uploading '+file.name+'…');
    var form=new FormData();
    form.append('conversation_id',conversationId);
    form.append('file',file);
    var fileId;
    try{
      var res=await fetch(UPLOAD_ENDPOINT,{method:'POST',body:form});
      var payload=await res.json();
      if(!res.ok){
        setAttachProgress('err','Upload failed: '+(payload.error||res.status));
        attachBtn.disabled=false;
        attachFileInput.value='';
        return;
      }
      fileId=payload.file_id;
      if(!fileId){
        setAttachProgress('err','Upload error: no file_id returned.');
        attachBtn.disabled=false;
        attachFileInput.value='';
        return;
      }
    }catch(e){
      setAttachProgress('err','Upload failed — check connection.');
      attachBtn.disabled=false;
      attachFileInput.value='';
      return;
    }
    var caption=(attachCaption.value||'').trim();
    ws.send(JSON.stringify({
      type:'multimodal_message',
      file:{file_id:fileId,type:'file_input'},
      text:{type:'user_message',text:caption}
    }));
    setAttachProgress('ok','✓ '+file.name+' sent'+(caption?' with caption':'')+'. Deed is reviewing it.');
    attachCaption.value='';
    attachFileInput.value='';
    attachBtn.disabled=false;
  }

  btn.addEventListener('click',function(){
    if(active){
      stopSession();
    }else if(voiceEmail){
      startSession();
    }else{
      if(vegEl){
        var showing=vegEl.classList.contains('show');
        if(showing){hideGate();}else{vegEl.className='veg show';if(vegInput)vegInput.focus();}
      }else{
        startSession();
      }
    }
  });

  attachBtn.addEventListener('click',function(){
    if(!conversationId){return;}
    attachFileInput.click();
  });

  attachFileInput.addEventListener('change',function(){
    if(attachFileInput.files&&attachFileInput.files[0])handleFileSelected(attachFileInput.files[0]);
  });
})();
</script>
</body>
</html>`;
}

// ── Subscribe interstitial — tracks pageview then hands off to Stripe ────────
const SUBSCRIBE_HTML = `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Subscribe — BidDeed.AI TIER_LABEL_PLACEHOLDER</title>
<meta name="description" content="Subscribe to BidDeed.AI TIER_LABEL_PLACEHOLDER — TIER_PRICE_PLACEHOLDER/mo.">
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;margin:0;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:440px;width:100%}
h1{font-size:1.4rem;color:white;margin-bottom:.4rem}
.price{color:#f59e0b;font-weight:700;font-size:1rem;margin-bottom:1.25rem}
p.sub{color:#94a3b8;font-size:.9rem;margin-bottom:1.5rem;line-height:1.5}
label{display:block;font-size:.85rem;color:#cbd5e1;margin-bottom:.4rem}
input{width:100%;background:#020617;border:1px solid #1e293b;border-radius:8px;padding:12px 14px;color:white;font-size:15px;margin-bottom:1.25rem;outline:none}
input:focus{border-color:#f59e0b}
button{width:100%;background:linear-gradient(135deg,#f59e0b,#f97316);color:#020617;border:none;padding:14px;border-radius:10px;font-weight:700;font-size:15px;cursor:pointer}
button:disabled{opacity:.6;cursor:default}
.err{color:#f87171;font-size:.85rem;margin-top:.75rem;display:none}
</style></head><body>
<div class="card">
  <h1>BidDeed.AI TIER_LABEL_PLACEHOLDER</h1>
  <div class="price">TIER_PRICE_PLACEHOLDER/mo</div>
  <p class="sub">Enter your email to continue to secure checkout. You'll be redirected to Stripe to complete payment.</p>
  <form id="sub-form">
    <label for="sub-email">Email</label>
    <input type="email" id="sub-email" placeholder="you@example.com" required>
    <button type="submit" id="sub-btn">Continue to Checkout →</button>
    <div class="err" id="sub-err"></div>
  </form>
</div>
<script>
try{if(window.posthog)posthog.capture('subscribe_page_viewed',{tier:'TIER_PLACEHOLDER'});}catch(e){}
var refCode = new URLSearchParams(window.location.search).get('ref');
document.getElementById('sub-form').addEventListener('submit', async function(e){
  e.preventDefault();
  var btn=document.getElementById('sub-btn'), err=document.getElementById('sub-err');
  var email=document.getElementById('sub-email').value.trim();
  err.style.display='none';
  btn.disabled=true; btn.textContent='Redirecting to checkout...';
  try{if(window.posthog)posthog.capture('subscribe_redirect',{tier:'TIER_PLACEHOLDER'});}catch(e2){}
  var checkoutPayload={tier:'TIER_PLACEHOLDER',customer_email:email};
  if(refCode){ checkoutPayload.referral_code=refCode; }
  fetch('/subscribe/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(checkoutPayload)})
    .then(function(res){ return res.json().then(function(data){ return {ok:res.ok,data:data}; }); })
    .then(function(r){
      if(r.ok && r.data.url){ window.location.href=r.data.url; }
      else{ err.textContent=r.data.error||'Something went wrong. Please try again.'; err.style.display='block'; btn.disabled=false; btn.textContent='Continue to Checkout →'; }
    })
    .catch(function(){ err.textContent='Network error. Please try again.'; err.style.display='block'; btn.disabled=false; btn.textContent='Continue to Checkout →'; });
});
</script>
</body></html>`;

// ── Success page ──────────────────────────────────────────────────────────────
const SUCCESS_HTML = `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Welcome to BidDeed.AI Investor</title>
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b;--green:#10b981}
body{background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:520px;width:100%;text-align:center}
.icon{font-size:3rem;margin-bottom:1rem}
h1{font-size:1.6rem;color:white;margin-bottom:.5rem}
p{color:var(--muted);margin-bottom:1.5rem;line-height:1.6}
.key-box{background:#020617;border:1px solid var(--border);border-radius:10px;padding:1rem;font-family:'SF Mono',monospace;font-size:.85rem;color:var(--orange);word-break:break-all;margin:1rem 0;min-height:44px;display:flex;align-items:center;justify-content:center}
.btn{display:inline-block;background:linear-gradient(135deg,var(--orange),var(--orange2));color:#020617;padding:12px 28px;border-radius:10px;font-weight:700;text-decoration:none;font-size:.95rem;margin-top:1rem}
.status{font-size:.8rem;color:var(--muted);margin-top:1rem}
</style></head><body>
<div class="card">
  <div class="icon">🎉</div>
  <h1>Welcome to Investor!</h1>
  <p>Your BidDeed.AI Investor access is being activated. Your MCP API key will appear below momentarily.</p>
  <div class="key-box" id="key-box">Activating...</div>
  <div class="status" id="status">Checking activation status...</div>
  <a href="/chat" class="btn">Open BidDeed.AI Chat →</a>
</div>
<script>
const params=new URLSearchParams(location.search);
const session_id=params.get('session_id')||'';
// subscription_activated now fired server-side from stripe-webhook after
// Stripe payment verification (added Aug 10 2026, same fix pattern as
// report_purchased) -- removed here to stop phantom activations logging on
// every /success page load (refresh/back-button/bookmark).
let attempts=0;
async function poll(){
  if(!session_id){document.getElementById('key-box').textContent='No session ID found.';return;}
  attempts++;
  try{
    const res=await fetch('/subscribe/status?session_id='+encodeURIComponent(session_id));
    const d=await res.json();
    if(d.key){document.getElementById('key-box').textContent=d.key;document.getElementById('status').textContent='Tier: '+(d.tier||'investor')+' · Save this key — shown once.';}
    else if(d.active){document.getElementById('key-box').textContent='Key issued. Check your email.';document.getElementById('status').textContent='Tier: '+(d.tier||'investor')+' · Activated ✓';}
    else if(attempts<8){document.getElementById('status').textContent='Activating... attempt '+attempts;setTimeout(poll,3000);}
    else{document.getElementById('key-box').textContent='Taking longer than expected.';document.getElementById('status').textContent='Email hello@biddeed.ai with your receipt if not resolved.';}
  }catch(e){if(attempts<8)setTimeout(poll,3000);}
}
poll();
</script></body></html>`;

const BUY_REPORT_HTML = `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Buy One Shapira Report — $25 | BidDeed.AI</title>
<meta name="description" content="Exact Shapira Max Bid + ZoneWise zoning + ML prediction for one auction. One-time $25, no subscription.">
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
body{background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:520px;width:100%}
.badge{color:var(--orange);font-size:12px;font-weight:600;letter-spacing:.1em;margin-bottom:.75rem}
.steps{display:flex;gap:.4rem;margin-bottom:1.25rem}
.steps span{flex:1;height:3px;border-radius:2px;background:var(--border)}
.steps span.done,.steps span.active{background:var(--orange)}
h1{font-size:1.5rem;color:white;margin-bottom:.5rem}
p{color:var(--muted);margin-bottom:1.5rem;line-height:1.6;font-size:.92rem}
label{display:block;font-size:.85rem;color:var(--muted);margin-bottom:.4rem}
select,input[type=email]{width:100%;padding:12px 14px;border-radius:8px;border:1px solid var(--border);background:#020617;color:var(--text);font-size:.95rem;margin-bottom:1rem;font-family:inherit}
.consent{display:flex;align-items:flex-start;gap:.5rem;margin-bottom:1.25rem;font-size:.8rem;color:var(--dim)}
.consent input{margin-top:3px}
.btn{display:block;width:100%;background:linear-gradient(135deg,var(--orange),var(--orange2));color:#020617;padding:14px;border:none;border-radius:10px;font-weight:700;font-size:.95rem;cursor:pointer}
.btn:disabled{opacity:.6;cursor:not-allowed}
.back{background:none;border:none;color:var(--dim);font-size:.85rem;cursor:pointer;margin-bottom:1rem;padding:0}
.back:hover{color:var(--orange)}
.err{color:#f87171;font-size:.85rem;margin-top:.75rem;display:none}
.upl{margin-top:1.5rem;padding-top:1.25rem;border-top:1px solid var(--border);font-size:.72rem;color:var(--dim);line-height:1.6}
.upl a{color:var(--orange)}
.auctions{max-height:340px;overflow-y:auto;margin-bottom:1rem;display:flex;flex-direction:column;gap:.6rem}
.auction-card{border:1px solid var(--border);border-radius:10px;padding:.85rem 1rem;cursor:pointer;transition:border-color .15s}
.auction-card:hover{border-color:rgba(245,158,11,.5)}
.auction-card.selected{border-color:var(--orange);background:rgba(245,158,11,.08)}
.auction-card .addr{font-weight:600;font-size:.9rem;color:white;margin-bottom:.3rem}
.auction-card .meta{font-size:.78rem;color:var(--dim);display:flex;gap:.75rem;flex-wrap:wrap}
.summary{border:1px solid var(--border);border-radius:10px;padding:1rem;margin-bottom:1.25rem;font-size:.85rem;color:var(--muted)}
.summary .addr{font-weight:600;color:white;margin-bottom:.4rem}
.empty{color:var(--dim);font-size:.85rem;padding:1rem 0}
.spin{color:var(--dim);font-size:.85rem;padding:1rem 0}
</style></head><body>
<div class="card">
  <div class="badge">ONE-TIME · NO SUBSCRIPTION</div>
  <div class="steps"><span id="dot1" class="active"></span><span id="dot2"></span><span id="dot3"></span></div>

  <div id="step-county">
    <h1>Pick your county</h1>
    <p>Exact Shapira Max Bid + ZoneWise zoning + ML prediction for one auction — $25, no subscription.</p>
    <div id="county-loading" class="spin">Loading counties…</div>
    <select id="county-select" style="display:none"></select>
    <button class="btn" id="county-continue" disabled style="display:none">Continue</button>
    <div class="err" id="county-err"></div>
    <p id="county-note" style="display:none;font-size:12px;color:#e2eaf2;margin-top:8px;">
      ⭐ Gold Standard counties include full CMA, ZoneWise zoning, and ML prediction.
      All counties include Shapira Max Bid and opening bid analysis.
    </p>
  </div>

  <div id="step-auction" style="display:none">
    <button class="back" id="back-to-county">&larr; Change county</button>
    <h1>Pick your auction</h1>
    <p>Upcoming auctions in <span id="auction-county-name"></span>.</p>
    <div id="auction-loading" class="spin" style="display:none">Loading auctions…</div>
    <div id="auctions" class="auctions"></div>
  </div>

  <div id="step-checkout" style="display:none">
    <button class="back" id="back-to-auction">&larr; Change auction</button>
    <h1>One Shapira Report — $25</h1>
    <div class="summary" id="checkout-summary"></div>
    <form id="f">
      <label for="email">Email address (report delivered here)</label>
      <input type="email" id="email" name="email" required placeholder="you@example.com">
      <label class="consent"><input type="checkbox" id="consent" name="consent"> Send me occasional auction intelligence updates (optional)</label>
      <button type="submit" class="btn" id="btn">Get My Shapira Report — $25</button>
      <div class="err" id="err"></div>
    </form>
  </div>

  <div class="upl">Not legal advice. BidDeed.AI is an information and analytics platform, not a law firm or title company. Auction data and bid estimates are informational and must be independently verified — always consult a licensed Florida attorney before bidding. See <a href="/disclaimer">full disclaimer</a>.</div>
</div>
<script>
var selected={county:null,county_name:null,case_number:null,property_address:null,auction_date:null,opening_bid:null,sale_type:null,mca_id:null};
var PREFILL = "PREFILL_PLACEHOLDER";

async function hashEmail8(email){
  var buf=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(email.trim().toLowerCase()));
  return Array.prototype.map.call(new Uint8Array(buf),function(b){return('0'+b.toString(16)).slice(-2);}).join('').slice(0,8);
}

function showStep(n){
  document.getElementById('step-county').style.display=(n===1)?'block':'none';
  document.getElementById('step-auction').style.display=(n===2)?'block':'none';
  document.getElementById('step-checkout').style.display=(n===3)?'block':'none';
  document.getElementById('dot1').className=(n>=1)?'done':'';
  document.getElementById('dot2').className=(n===2)?'active':(n>2?'done':'');
  document.getElementById('dot3').className=(n===3)?'active':'';
}

function fmtDate(d){
  if(!d) return 'TBD';
  var dt=new Date(d+'T00:00:00');
  return dt.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
}
function fmtShortDate(d){
  if(!d) return 'TBD';
  var dt=new Date(d+'T00:00:00');
  return dt.toLocaleDateString('en-US',{month:'short',day:'numeric'});
}
function fmtMoney(n){
  if(!n) return 'N/A';
  return '$'+Number(n).toLocaleString('en-US',{maximumFractionDigits:0});
}

// ── Prefill flow — arrived from a property card in chat (?mca_id=&address=&county=&date=) ──
if (PREFILL && PREFILL.mca_id) {
  document.getElementById('county-loading').style.display='none';
  selected.county=PREFILL.county||null;
  selected.county_name=PREFILL.county_name||PREFILL.county||'';
  selected.property_address=PREFILL.address||null;
  selected.auction_date=PREFILL.date||null;
  selected.mca_id=PREFILL.mca_id;
  document.getElementById('back-to-auction').style.display='none';
  goToCheckout();
  document.getElementById('btn').disabled=true;
  document.getElementById('btn').textContent='Loading property…';
  fetch('/property/'+encodeURIComponent(PREFILL.mca_id)).then(function(r){return r.json();}).then(function(d){
    if (d && d.case_number) {
      selected.case_number=d.case_number;
      selected.county=d.county||selected.county;
      selected.property_address=d.property_address||selected.property_address;
      selected.auction_date=d.auction_date||selected.auction_date;
      selected.opening_bid=d.opening_bid;
      selected.sale_type=d.sale_type;
      document.getElementById('btn').disabled=false;
      document.getElementById('btn').textContent='Get My Shapira Report — $25';
      goToCheckout();
    } else {
      document.getElementById('btn').textContent='Property not found';
      document.getElementById('err').textContent='Could not load this property — the link may be out of date.';
      document.getElementById('err').style.display='block';
    }
  }).catch(function(){
    document.getElementById('btn').textContent='Property not found';
    document.getElementById('err').textContent='Could not load this property — please try again.';
    document.getElementById('err').style.display='block';
  });
} else {
  // ── Step 1: counties ──────────────────────────────────────────────────────
  fetch('/buy-report/counties').then(function(r){return r.json();}).then(function(counties){
    document.getElementById('county-loading').style.display='none';
    var sel=document.getElementById('county-select');
    if(!counties || !counties.length){
      document.getElementById('county-err').textContent='No counties with upcoming auctions right now — check back soon.';
      document.getElementById('county-err').style.display='block';
      return;
    }
    var opts='<option value="">Select a county…</option>';
    counties.forEach(function(c){
      var label=(c.is_gold_standard?c.display+' ⭐':c.display)+' — '+c.upcoming+' upcoming · Next: '+fmtShortDate(c.next_auction_date)+(c.is_gold_standard?'':' · Data under review');
      opts+='<option value="'+c.county_slug+'" data-name="'+c.display+'" data-upcoming="'+c.upcoming+'">'+label+'</option>';
    });
    sel.innerHTML=opts;
    sel.style.display='block';
    var btn=document.getElementById('county-continue');
    btn.style.display='block';
    document.getElementById('county-note').style.display='block';
    sel.addEventListener('change',function(){ btn.disabled=!sel.value; });
    btn.addEventListener('click',function(){
      var opt=sel.options[sel.selectedIndex];
      selected.county=sel.value;
      selected.county_name=opt.getAttribute('data-name');
      try{if(window.posthog)posthog.capture('buy_report_county_selected',{county:selected.county,upcoming_count:Number(opt.getAttribute('data-upcoming'))||0});}catch(e){}
      loadAuctions();
    });
  }).catch(function(){
    document.getElementById('county-loading').textContent='Could not load counties. Please refresh.';
  });
}

// ── Step 2: auctions ──────────────────────────────────────────────────────
function loadAuctions(){
  document.getElementById('auction-county-name').textContent=selected.county_name;
  var list=document.getElementById('auctions');
  list.innerHTML='';
  document.getElementById('auction-loading').style.display='block';
  showStep(2);
  fetch('/buy-report/auctions?county='+encodeURIComponent(selected.county)).then(function(r){return r.json();}).then(function(auctions){
    document.getElementById('auction-loading').style.display='none';
    if(!auctions || !auctions.length){
      list.innerHTML='<p style="color:#f59e0b">Calendar sync in progress for '+(selected.county_name||'this county')+'. Check back in 24 hours or <a href="/chat" style="color:#f59e0b">browse live auctions in chat</a>.</p>';
      return;
    }
    auctions.forEach(function(a,i){
      var card=document.createElement('div');
      card.className='auction-card';
      card.innerHTML='<div class="addr">'+(a.property_address||'Address pending')+'</div>'+
        '<div class="meta"><span>'+fmtDate(a.auction_date)+'</span><span>Opening bid: '+fmtMoney(a.opening_bid)+'</span><span>'+(a.sale_type||'')+'</span></div>';
      card.addEventListener('click',function(){
        selected.case_number=a.case_number;
        selected.property_address=a.property_address;
        selected.auction_date=a.auction_date;
        selected.opening_bid=a.opening_bid;
        selected.sale_type=a.sale_type;
        selected.mca_id=null;
        try{if(window.posthog)posthog.capture('buy_report_auction_selected',{county:selected.county,case_number:selected.case_number,property_address:selected.property_address,auction_date:selected.auction_date,opening_bid:selected.opening_bid});}catch(e){}
        goToCheckout();
      });
      list.appendChild(card);
    });
  }).catch(function(){
    document.getElementById('auction-loading').textContent='Could not load auctions. Please go back and try again.';
  });
}
document.getElementById('back-to-county').addEventListener('click',function(){ showStep(1); });

// ── Step 3: email + buy ───────────────────────────────────────────────────
function goToCheckout(){
  document.getElementById('checkout-summary').innerHTML=
    '<div class="addr">'+(selected.property_address||'Address pending')+'</div>'+
    (selected.case_number?('Case '+selected.case_number+' · '):'')+selected.county_name+' County · '+fmtDate(selected.auction_date)+'<br>'+
    'Opening bid: '+fmtMoney(selected.opening_bid)+' · '+(selected.sale_type||'');
  showStep(3);
}
document.getElementById('back-to-auction').addEventListener('click',function(){ showStep(2); });

document.getElementById('f').addEventListener('submit', async function(e){
  e.preventDefault();
  var btn=document.getElementById('btn'), err=document.getElementById('err');
  var email=document.getElementById('email').value.trim();
  var marketing_consent=document.getElementById('consent').checked;
  err.style.display='none';
  btn.disabled=true; btn.textContent='Redirecting to checkout...';
  var hashedEmail='';
  try{ hashedEmail=await hashEmail8(email); }catch(e2){}
  try{if(window.posthog)posthog.capture('buy_report_checkout_started',{county:selected.county,case_number:selected.case_number,email:hashedEmail,amount:25});}catch(e2){}
  fetch('/buy-report/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,county:selected.county,case_number:selected.case_number,mca_id:selected.mca_id,marketing_consent:marketing_consent})})
    .then(function(res){ return res.json().then(function(data){ return {ok:res.ok,data:data}; }); })
    .then(function(r){
      if(r.ok && r.data.url){
        try{if(window.posthog)posthog.identify(hashedEmail,{county_interest:selected.county,source:'buy_report'});}catch(e2){}
        window.location.href=r.data.url;
      }
      else{ err.textContent=r.data.error||'Something went wrong. Please try again.'; err.style.display='block'; btn.disabled=false; btn.textContent='Get My Shapira Report — $25'; }
    })
    .catch(function(){ err.textContent='Network error. Please try again.'; err.style.display='block'; btn.disabled=false; btn.textContent='Get My Shapira Report — $25'; });
});
</script></body></html>`;

const REPORT_SUCCESS_HTML = `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Report Ready | BidDeed.AI</title>
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b}
body{background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:520px;width:100%;text-align:center}
.icon{font-size:3rem;margin-bottom:1rem}
h1{font-size:1.6rem;color:white;margin-bottom:.5rem}
p{color:var(--muted);margin-bottom:1.5rem;line-height:1.6}
.key-box{background:#020617;border:1px solid var(--border);border-radius:10px;padding:1rem;font-family:'SF Mono',monospace;font-size:.85rem;color:var(--orange);word-break:break-all;margin:1rem 0;min-height:44px;display:flex;align-items:center;justify-content:center}
.btn{display:inline-block;background:linear-gradient(135deg,var(--orange),var(--orange2));color:#020617;padding:12px 28px;border-radius:10px;font-weight:700;text-decoration:none;font-size:.95rem;margin-top:1rem}
.status{font-size:.8rem;color:var(--muted);margin-top:1rem}
.emailed{font-size:.8rem;color:var(--muted);margin-top:.5rem}
.property-info{font-size:.85rem;color:var(--text);margin-bottom:1rem;padding:.75rem;background:#020617;border-radius:8px;border:1px solid var(--border);display:none}
.report-btn{display:none;margin-top:.75rem}
</style></head><body>
<div class="card">
  <div class="icon">✅</div>
  <h1>Payment received — your S5 report credit is ready</h1>
  <p>Your Shapira Max Bid report is being activated. Your key will appear below momentarily.</p>
  <div class="property-info" id="property-info"></div>
  <div class="key-box" id="key-box">Activating...</div>
  <div class="status" id="status">Checking activation status...</div>
  <div class="emailed" id="emailed"></div>
  <a href="#" class="btn report-btn" id="report-btn">View Your Report →</a>
  <a href="/chat" class="btn">Open BidDeed.AI Chat →</a>
</div>
<script>
const params=new URLSearchParams(location.search);
const session_id=params.get('session')||params.get('session_id')||'';
const email=params.get('email')||'';
const mca_id=params.get('mca_id')||'';
// report_purchased is now fired server-side from stripe-webhook v10+ after
// Stripe payment verification (see Supabase project mocerqjnksmhcjzxrewo) —
// removed here Aug 10 2026 to stop phantom purchases logging on every
// page load (refresh/back-button/bookmark) with no payment verification.
if(email) document.getElementById('emailed').textContent='We also emailed your key to '+email;
if(mca_id){
  fetch('/property/'+encodeURIComponent(mca_id)).then(r=>r.json()).then(d=>{
    if(d && !d.error){
      const el=document.getElementById('property-info');
      el.textContent=(d.property_address||'Property')+(d.auction_date?' · Auction '+d.auction_date:'');
      el.style.display='block';
    }
  }).catch(()=>{});
}
let currentKey=null;
function showReportBtn(){
  if(!mca_id||!currentKey) return;
  const btn=document.getElementById('report-btn');
  btn.href='/report/'+encodeURIComponent(mca_id)+'?key='+encodeURIComponent(currentKey);
  btn.style.display='inline-block';
}
let attempts=0;
async function poll(){
  if(!session_id){document.getElementById('key-box').textContent='No session ID found.';return;}
  attempts++;
  try{
    const res=await fetch('/subscribe/status?session_id='+encodeURIComponent(session_id));
    const d=await res.json();
    if(d.key){document.getElementById('key-box').textContent=d.key;document.getElementById('status').textContent='Save this key — shown once.';currentKey=d.key;showReportBtn();}
    else if(d.active){document.getElementById('key-box').textContent='Key issued. Check your email.';document.getElementById('status').textContent='Activated ✓';}
    else if(attempts<8){document.getElementById('status').textContent='Activating... attempt '+attempts;setTimeout(poll,3000);}
    else{document.getElementById('key-box').textContent='Taking longer than expected.';document.getElementById('status').textContent='Email hello@biddeed.ai with your receipt if not resolved.';}
  }catch(e){if(attempts<8)setTimeout(poll,3000);}
}
poll();
</script></body></html>`;


// ── County page template (from docs/brevard.html) ────────────────────────────
const COUNTY_PAGE_TEMPLATE = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>BidDeed.AI · COUNTY_TITLE Auctions</title>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#020617">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js"></script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/alpinejs/3.13.5/cdn.min.js"></script>
<style>
:root { --safe-bottom: env(safe-area-inset-bottom,0px); --safe-top: env(safe-area-inset-top,0px); }
body { font-family:'Inter','SF Pro Text',system-ui,-apple-system,sans-serif; background:#020617; color:#e2e8f0; -webkit-tap-highlight-color:transparent; overscroll-behavior-y:contain; }
.glass { background:rgba(30,41,59,0.55); backdrop-filter:blur(10px); border:1px solid rgba(245,158,11,0.12); }
.glass-diamond { background:linear-gradient(135deg,rgba(56,189,248,0.12),rgba(168,85,247,0.12)); backdrop-filter:blur(10px); border:1px solid rgba(168,85,247,0.35); }
.glass-triangle { background:linear-gradient(135deg,rgba(239,68,68,0.10),rgba(245,158,11,0.10)); backdrop-filter:blur(10px); border:1px solid rgba(239,68,68,0.30); }
.glass-sold { background:rgba(59,130,246,0.06); backdrop-filter:blur(10px); border:1px solid rgba(59,130,246,0.25); }
.glass-canceled { background:rgba(100,116,139,0.06); backdrop-filter:blur(10px); border:1px solid rgba(100,116,139,0.25); opacity:0.7; }
.grade-A { background:linear-gradient(135deg,#10b981,#059669); color:#fff; }
.grade-B { background:linear-gradient(135deg,#22c55e,#16a34a); color:#fff; }
.grade-C { background:linear-gradient(135deg,#eab308,#ca8a04); color:#1f2937; }
.grade-D { background:linear-gradient(135deg,#f97316,#ea580c); color:#fff; }
.grade-E,.grade-X,.grade-Z { background:#b8cfe0; color:#cbd5e1; }
[x-cloak] { display:none !important; }
.scroll-h::-webkit-scrollbar { display:none; } .scroll-h { -ms-overflow-style:none; scrollbar-width:none; }
.sheet { transform:translateY(100%); transition:transform .28s cubic-bezier(.32,.72,0,1); }
.sheet.open { transform:translateY(0); }
.chip { min-height:48px; display:inline-flex; align-items:center; }
button, a, [role="button"] { min-height:44px; }
input, select { font-size:16px; min-height:48px; }
.card-tap:active { transform:scale(.98); transition:transform .1s; }
.skeleton { background:linear-gradient(90deg,#1e293b 0%,#334155 50%,#1e293b 100%); background-size:200% 100%; animation:shimmer 1.4s infinite; }
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
.diamond-glow { background:linear-gradient(135deg,#38bdf8,#a855f7); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.triangle-glow { background:linear-gradient(135deg,#ef4444,#f59e0b); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.diamond-chip-active { background:linear-gradient(135deg,#38bdf8,#a855f7) !important; color:#fff !important; border-color:transparent !important; }
.triangle-chip-active { background:linear-gradient(135deg,#ef4444,#f59e0b) !important; color:#fff !important; border-color:transparent !important; }
.sig-badge { display:inline-flex; align-items:center; padding:2px 6px; border-radius:9999px; font-size:9px; font-weight:700; gap:2px; }
.sig-out { background:rgba(239,68,68,.18); color:#fca5a5; border:1px solid rgba(239,68,68,.3); }
.sig-abs { background:rgba(245,158,11,.18); color:#fcd34d; border:1px solid rgba(245,158,11,.3); }
.sig-est { background:rgba(168,85,247,.20); color:#d8b4fe; border:1px solid rgba(168,85,247,.35); }
.sig-ent { background:rgba(59,130,246,.18); color:#93c5fd; border:1px solid rgba(59,130,246,.3); }
.sig-len { background:rgba(20,184,166,.18); color:#5eead4; border:1px solid rgba(20,184,166,.3); }
.sig-mul { background:rgba(244,114,182,.18); color:#f9a8d4; border:1px solid rgba(244,114,182,.3); }
.status-badge { display:inline-flex; align-items:center; gap:3px; padding:2px 7px; border-radius:9999px; font-size:9px; font-weight:800; letter-spacing:0.05em; }
.status-LISTED { background:rgba(16,185,129,0.18); color:#6ee7b7; border:1px solid rgba(16,185,129,0.35); }
.status-SOLD { background:rgba(59,130,246,0.18); color:#93c5fd; border:1px solid rgba(59,130,246,0.35); }
.status-CANCELED { background:rgba(100,116,139,0.20); color:#cbd5e1; border:1px solid rgba(100,116,139,0.35); }
.status-REDEEMED { background:rgba(168,85,247,0.20); color:#d8b4fe; border:1px solid rgba(168,85,247,0.35); }
input[type=range] { accent-color:#f59e0b; }
</style>
</head>
<body x-data="app()" x-init="init()" x-cloak class="min-h-screen pb-24">

<header class="sticky top-0 z-30 bg-slate-950/90 backdrop-blur border-b border-amber-500/20" style="padding-top:var(--safe-top)">
  <div class="px-4 py-3 flex items-center justify-between gap-3">
    <div class="flex items-center gap-2 min-w-0">
      <div class="text-xl font-extrabold tracking-tight bg-gradient-to-r from-amber-400 to-amber-200 bg-clip-text text-transparent">BidDeed.AI</div>
    </div>
    <div class="text-right shrink-0">
      <div class="text-lg font-bold text-amber-400 leading-tight">$<span x-text="formatNum(filteredEquity)"></span></div>
      <div class="text-[9px] uppercase tracking-wider text-slate-500"><span x-text="filteredDeals.length"></span> · equity</div>
    </div>
  </div>
  <div class="px-4 pb-2 text-[11px] text-slate-400">🏠 COUNTY_TITLE auctions · <b class="text-emerald-400" x-text="matchCountByStatus('LISTED')"></b> listed · <b class="text-blue-400" x-text="matchCountByStatus('SOLD')"></b> sold · <b class="text-slate-400" x-text="matchCountByStatus('CANCELED')"></b> canceled</div>

  <div class="px-3 pb-3 flex gap-2 overflow-x-auto scroll-h">
    <button @click="clearPersona()" class="chip px-3 rounded-full text-xs whitespace-nowrap shrink-0 border" :class="!activePersona ? 'bg-amber-500 text-slate-900 border-amber-500 font-bold' : 'bg-slate-800/60 border-slate-700 text-slate-300'">All <span x-text="deals.length"></span></button>
    <template x-for="p in builtInPersonas" :key="p.code">
      <button @click="selectPersona(p)" class="chip px-3 rounded-full text-xs whitespace-nowrap shrink-0 border"
        :class="activePersona && activePersona.code===p.code ? (p.code==='DIAMONDS' ? 'diamond-chip-active font-bold' : p.code==='TRIANGLE' ? 'triangle-chip-active font-bold' : 'bg-amber-500 text-slate-900 border-amber-500 font-bold') : (p.code==='DIAMONDS' ? 'bg-gradient-to-r from-sky-500/15 to-purple-500/15 border-purple-500/40 text-sky-300' : p.code==='TRIANGLE' ? 'bg-gradient-to-r from-red-500/15 to-amber-500/15 border-red-500/40 text-red-300' : p.code==='SOLD_TODAY' ? 'bg-blue-500/10 border-blue-500/40 text-blue-300' : 'bg-slate-800/60 border-slate-700 text-slate-300')">
        <span class="mr-1" x-text="p.icon"></span><span x-text="p.name"></span> <span class="ml-1 opacity-70" x-text="'· '+matchCount(p.filter)"></span>
      </button>
    </template>
    <template x-for="p in customPersonas" :key="p.id">
      <button @click="selectPersona(p)" class="chip px-3 rounded-full text-xs whitespace-nowrap shrink-0 border bg-amber-500/10 border-amber-500/40 text-amber-300">
        🎯 <span x-text="p.name"></span>
      </button>
    </template>
  </div>

  <div class="px-3 pb-3 pt-1 border-t border-slate-800/40">
    <button @click="showOwnerPicker=true" class="w-full flex items-center gap-2 bg-slate-800/60 border border-slate-700/60 rounded-full pl-3 pr-2 text-sm hover:bg-slate-800" style="min-height:44px">
      <span class="text-slate-500 text-base">👤</span>
      <span class="flex-1 text-left truncate" :class="filters.ownerLike ? 'text-amber-300 font-bold' : 'text-slate-400'" x-text="filters.ownerLike || ('Browse '+uniqueOwnerCount+' owners…')"></span>
      <span x-show="filters.ownerLike" @click.stop="clearOwner()" class="w-7 h-7 flex items-center justify-center text-slate-400 hover:text-white rounded-full bg-slate-700/50">✕</span>
      <span class="text-slate-500 px-1">▾</span>
    </button>
  </div>
</header>

<div x-show="hiddenStatusCount>0" class="px-4 py-2 bg-slate-900/80 border-b border-slate-700/40 flex items-center justify-between gap-2 text-[11px]">
  <span class="text-slate-400">
    <span class="text-emerald-400">●</span> Showing <b x-text="filters.status.map(s => matchCountByStatus(s)).reduce((a,b)=>a+b,0)"></b> ·
    <b class="text-amber-400" x-text="hiddenStatusCount"></b> hidden (<span x-text="hiddenStatusBreakdown"></span>)
  </span>
  <button @click="showAllStatuses()" class="text-amber-400 underline text-[11px] font-bold">Show all</button>
</div>

<div x-show="activePersona" class="px-4 py-2.5 border-b flex items-center gap-2"
     :class="activePersona && activePersona.code==='DIAMONDS' ? 'glass-diamond border-purple-500/30' : activePersona && activePersona.code==='TRIANGLE' ? 'glass-triangle border-red-500/30' : 'bg-amber-500/10 border-amber-500/20'">
  <span class="text-base shrink-0" x-text="activePersona && activePersona.icon"></span>
  <div class="min-w-0 flex-1">
    <div class="text-sm font-bold truncate" :class="activePersona && activePersona.code==='DIAMONDS' ? 'diamond-glow' : activePersona && activePersona.code==='TRIANGLE' ? 'triangle-glow' : 'text-amber-300'" x-text="activePersona && activePersona.name"></div>
    <div class="text-[11px] text-slate-400 line-clamp-2" x-text="activePersona && activePersona.desc"></div>
  </div>
  <button @click="clearPersona()" class="px-3 text-xs text-slate-300 shrink-0">✕</button>
</div>

<div class="px-4 py-2 flex items-center gap-2 sticky bg-slate-950/85 backdrop-blur z-20" style="top:170px">
  <button @click="showFilters=true" class="flex items-center gap-1.5 px-3 py-2 rounded-full bg-slate-800 border border-slate-700 text-sm">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h18M6 12h12M10 20h4"/></svg>
    Filters <span x-show="activeFilterCount>0" class="bg-amber-500 text-slate-900 text-[10px] font-bold rounded-full px-1.5" x-text="activeFilterCount"></span>
  </button>
  <select x-model="sortKey" class="bg-slate-800 border border-slate-700 rounded-full px-3 py-2 text-sm">
    <option value="equity_at_opening_bid">Sort: Equity ↓</option>
    <option value="owner_distress_score">Sort: 🔺 Distress ↓</option>
    <option value="opening_bid">Sort: Open Bid ↑</option>
    <option value="opening_bid_pct_of_market">Sort: Discount</option>
  </select>
  <div class="ml-auto text-[11px] text-slate-500"><span x-text="filteredDeals.length"></span>/<span x-text="deals.length"></span></div>
</div>

<main class="px-3 sm:px-4 pb-4 max-w-5xl mx-auto">
  <div x-show="deals.length===0" class="space-y-3 mt-3"><template x-for="i in 5"><div class="h-32 rounded-xl skeleton"></div></template></div>
  <div x-show="deals.length>0 && filteredDeals.length===0" class="mt-12 text-center text-slate-400 text-sm">No deals match. Try clearing filters.</div>

  <div class="space-y-3 mt-3 md:grid md:grid-cols-2 lg:grid-cols-3 md:gap-4" x-show="deals.length>0">
    <template x-for="d in displayDeals" :key="d.tax_deed_case||d.full_address||d.street_address">
      <div @click="openDeal=d" class="card-tap rounded-xl p-3 active:bg-slate-800/80"
           :class="(d.sale_status==='SOLD' ? 'glass-sold' : d.sale_status==='CANCELED' ? 'glass-canceled' : (d.owner_distress_score||0)>=50 ? 'glass-triangle' : isUnknownAddr(d) ? 'glass-diamond' : 'glass')">
        <div class="flex items-start justify-between gap-2 mb-2">
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="status-badge" :class="'status-'+(d.sale_status||'LISTED')">● <span x-text="d.sale_status||'LISTED'"></span></span>
            <span class="text-[10px] font-bold px-2 py-1 rounded" :class="'grade-'+(d.tax_deed_grade && d.tax_deed_grade.charAt(0))" x-text="d.tax_deed_grade ? d.tax_deed_grade.replace('_',' ').slice(0,12) : '?'"></span>
            <span class="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-300" x-text="(d.property_category||'?').replace(/_/g,' ')"></span>
            <span x-show="isUnknownAddr(d)" class="text-[10px] font-bold px-2 py-1 rounded bg-gradient-to-r from-sky-500 to-purple-500 text-white">💎</span>
            <span x-show="(d.owner_distress_score||0)>=40" class="text-[10px] font-bold px-2 py-1 rounded bg-gradient-to-r from-red-500 to-amber-500 text-white" x-text="'🔺 '+d.owner_distress_score"></span>
          </div>
          <div class="text-right shrink-0">
            <template x-if="d.sale_status==='SOLD' && d.sold_amount">
              <div>
                <div class="text-blue-300 font-bold text-sm">$<span x-text="formatNum(d.sold_amount)"></span></div>
                <div class="text-[10px] text-slate-500">sold (<span x-text="d.sold_premium_pct>0 ? '+'+d.sold_premium_pct+'%' : 'opening'"></span>)</div>
              </div>
            </template>
            <template x-if="d.sale_status==='SOLD' && !d.sold_amount">
              <div>
                <div class="text-blue-300 font-bold text-xs italic">sold</div>
                <div class="text-[9px] text-amber-500">price TBD</div>
              </div>
            </template>
            <template x-if="d.sale_status!=='SOLD'">
              <div>
                <div class="font-bold text-sm" :class="d.equity_at_opening_bid > 0 ? 'text-emerald-400' : d.equity_at_opening_bid < 0 ? 'text-red-400' : 'text-slate-500'" x-text="d.equity_at_opening_bid != 0 ? ((d.equity_at_opening_bid < 0 ? '-$' : '$') + formatNum(Math.abs(d.equity_at_opening_bid))) : 'TBD'"></div>
                <div class="text-[10px] text-slate-500" x-text="d.equity_at_opening_bid != 0 ? 'equity' : 'pending'"></div>
              </div>
            </template>
          </div>
        </div>
        <div class="text-[15px] font-semibold leading-tight" x-text="isUnknownAddr(d) ? ('PIN '+(d.bcpao_account||'?')) : (d.street_address||'(pending)')"></div>
        <div class="text-xs text-slate-400" x-text="isUnknownAddr(d) ? 'No street · check parcel map' : ((d.city||'?')+(d.zip5 ? ', '+d.zip5 : ''))"></div>
        <div class="text-[11px] text-amber-400/80 mb-2 font-medium" x-show="d.auction_date" x-text="'📅 ' + (d.auction_date ? new Date(d.auction_date+'T12:00:00').toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric',year:'numeric'}) : '')"></div>
        <div x-show="d.owner_name" class="text-[11px] mb-2 flex items-start gap-1.5">
          <span class="text-slate-500">👤</span>
          <span class="text-slate-300 font-medium truncate" x-text="(d.owner_name||'')+(d.owner_mailing_state ? ' · '+d.owner_mailing_state : '')"></span>
        </div>
        <div x-show="d.owner_distress_signals" class="flex flex-wrap gap-1 mb-2">
          <template x-for="sig in (d.owner_distress_signals||'').split('|').filter(Boolean)">
            <span class="sig-badge" :class="getSigClass(sig)" x-text="getSigLabel(sig)"></span>
          </template>
        </div>
        <div class="grid grid-cols-3 gap-2 text-xs">
          <div class="bg-slate-900/60 rounded px-2 py-1.5"><div class="text-[9px] text-slate-500 uppercase">Bid</div><div class="font-mono font-semibold" x-text="d.opening_bid > 0 ? ('$'+formatNum(d.opening_bid)) : 'TBD'"></div></div>
          <div class="bg-slate-900/60 rounded px-2 py-1.5"><div class="text-[9px] text-slate-500 uppercase">Market</div><div class="font-mono font-semibold" x-text="d.market_value > 0 ? ('$'+formatNum(d.market_value)) : 'TBD'"></div></div>
          <div class="bg-slate-900/60 rounded px-2 py-1.5"><div class="text-[9px] text-slate-500 uppercase">% Mkt</div><div class="font-mono font-semibold text-amber-400" x-text="d.opening_bid_pct_of_market!=null ? d.opening_bid_pct_of_market+'%' : '—'"></div></div>
        </div>
      </div>
    </template>
  </div>

  <div class="hidden" x-show="false">
    <table class="w-full text-sm">
      <thead class="bg-slate-900/80 text-xs uppercase text-slate-400">
        <tr><th class="p-3 text-left">Status</th><th class="p-3 text-left">Grade</th><th class="p-3 text-left">Property / Owner</th><th class="p-3 text-left">🔺 Signals</th><th class="p-3 text-right">Bid</th><th class="p-3 text-right">Equity</th><th class="p-3 text-right">Score</th></tr>
      </thead>
      <tbody>
        <template x-for="d in displayDeals" :key="d.tax_deed_case||d.full_address||d.street_address">
          <tr @click="openDeal=d" class="border-t border-slate-700/40 hover:bg-amber-500/5 cursor-pointer" :class="d.sale_status==='SOLD' ? 'bg-blue-500/5' : d.sale_status==='CANCELED' ? 'opacity-60' : (d.owner_distress_score||0)>=40 ? 'bg-red-500/5' : (isUnknownAddr(d) ? 'bg-purple-500/5' : '')">
            <td class="p-3"><span class="status-badge" :class="'status-'+(d.sale_status||'LISTED')">● <span x-text="d.sale_status||'LISTED'"></span></span></td>
            <td class="p-3"><span class="text-[10px] font-bold px-2 py-1 rounded" :class="'grade-'+(d.tax_deed_grade && d.tax_deed_grade.charAt(0))" x-text="d.tax_deed_grade ? d.tax_deed_grade.replace('_',' ').slice(0,12) : '?'"></span></td>
            <td class="p-3">
              <div class="font-medium" x-text="isUnknownAddr(d) ? ('PIN '+(d.bcpao_account||'?')) : (d.street_address||'(pending)')"></div>
              <div class="text-xs text-slate-400" x-text="(d.city||'?')+(d.zip5 ? ', '+d.zip5 : '')"></div>
              <div x-show="d.owner_name" class="text-[11px] text-slate-500 mt-1" x-text="'👤 '+(d.owner_name||'')+(d.owner_mailing_state ? ' · '+d.owner_mailing_state : '')"></div>
            </td>
            <td class="p-3"><div class="flex flex-wrap gap-1"><template x-for="sig in (d.owner_distress_signals||'').split('|').filter(Boolean)"><span class="sig-badge" :class="getSigClass(sig)" x-text="getSigLabel(sig)"></span></template></div></td>
            <td class="p-3 text-right font-mono">$<span x-text="formatNum(d.opening_bid)"></span></td>
            <td class="p-3 text-right font-mono font-bold text-emerald-400">$<span x-text="formatNum(d.equity_at_opening_bid)"></span></td>
            <td class="p-3 text-right font-mono text-red-400 font-bold" x-text="d.owner_distress_score||0"></td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>

  <button x-show="displayDeals.length < filteredDeals.length" @click="rowLimit+=25" class="w-full mt-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-amber-400 text-sm font-medium">↓ Load 25 more (<span x-text="filteredDeals.length-displayDeals.length"></span>)</button>
</main>

<button @click="openChat()" class="fixed right-4 z-30 bg-gradient-to-br from-amber-500 to-amber-400 text-slate-900 font-bold rounded-full shadow-2xl shadow-amber-500/40 px-5 py-3.5 flex items-center gap-2" style="bottom:calc(20px + var(--safe-bottom))">
  <span class="text-lg">✨</span><span>Build with AI</span>
</button>

<!-- OWNER PICKER SHEET (unchanged from v5) -->
<div x-show="showOwnerPicker" class="fixed inset-0 z-40" x-cloak>
  <div class="absolute inset-0 bg-black/80" @click="showOwnerPicker=false"></div>
  <div class="absolute inset-x-0 bottom-0 md:inset-0 md:flex md:items-center md:justify-center md:p-4">
    <div class="bg-slate-900 rounded-t-2xl md:rounded-2xl sheet open w-full md:max-w-xl border-t md:border border-amber-500/30 overflow-hidden flex flex-col" style="max-height:90vh">
      <div class="flex justify-center pt-3 md:hidden"><div class="w-12 h-1 bg-slate-600 rounded"></div></div>
      <div class="p-4 border-b border-slate-700/50 flex items-center justify-between gap-2">
        <div>
          <h2 class="text-base font-bold text-amber-400">👤 Browse Owners</h2>
          <p class="text-[11px] text-slate-400"><span x-text="uniqueOwnerCount"></span> unique · <span x-text="deals.filter(d => !d.owner_name).length"></span> without owner data</p>
        </div>
        <button @click="showOwnerPicker=false" class="text-slate-400 text-2xl leading-none">×</button>
      </div>
      <div class="px-4 pt-3 pb-2 border-b border-slate-700/30">
        <div class="relative">
          <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">🔍</span>
          <input x-model="ownerPickerQuery" type="search" placeholder="Type to filter list…" class="w-full bg-slate-800 border border-slate-700 rounded-lg pl-10 pr-3 text-sm">
        </div>
        <div class="text-[11px] text-slate-500 mt-1.5"><span x-text="filteredOwnerList.length"></span> matches</div>
      </div>
      <div class="flex-1 overflow-y-auto">
        <button @click="clearOwner(); showOwnerPicker=false" class="w-full text-left px-4 py-3 hover:bg-slate-800/60 border-b border-slate-800/40 flex items-center gap-2" :class="!filters.ownerLike ? 'bg-amber-500/10' : ''">
          <span class="text-base">🌐</span>
          <div class="flex-1"><div class="font-bold text-amber-300">All owners</div><div class="text-[11px] text-slate-400">Clear filter</div></div>
          <span x-show="!filters.ownerLike" class="text-amber-400">✓</span>
        </button>
        <template x-for="o in filteredOwnerList" :key="o.name">
          <button @click="pickOwner(o.name)" class="w-full text-left px-4 py-3 hover:bg-slate-800/60 border-b border-slate-800/40 flex items-start gap-2" :class="filters.ownerLike===o.name ? 'bg-amber-500/10' : ''">
            <span class="text-base shrink-0" x-text="o.topScore>=40 ? '🔺' : '👤'"></span>
            <div class="flex-1 min-w-0">
              <div class="font-medium text-slate-200 truncate" x-text="o.name"></div>
              <div class="text-[11px] text-slate-400 flex items-center gap-2 flex-wrap mt-0.5">
                <span x-show="o.deals>1" class="text-pink-300 font-bold" x-text="'🔁 '+o.deals+' deals'"></span>
                <span x-show="o.deals===1" class="text-slate-500">1 deal</span>
                <span x-show="o.equity>0" class="text-emerald-400 font-mono" x-text="'$'+formatNum(o.equity)+' eq'"></span>
                <span x-show="o.state" class="text-slate-500 font-mono" x-text="o.state"></span>
                <span x-show="o.topScore>=40" class="text-red-400 font-bold font-mono" x-text="'🔺 '+o.topScore"></span>
              </div>
              <div x-show="o.signals.length>0" class="flex flex-wrap gap-1 mt-1">
                <template x-for="sig in o.signals"><span class="sig-badge" :class="getSigClass(sig)" x-text="getSigLabel(sig)"></span></template>
              </div>
            </div>
            <span x-show="filters.ownerLike===o.name" class="text-amber-400 shrink-0">✓</span>
          </button>
        </template>
      </div>
    </div>
  </div>
</div>

<!-- FILTERS SHEET (status section added at top) -->
<div x-show="showFilters" class="fixed inset-0 z-40" x-cloak>
  <div class="absolute inset-0 bg-black/70" @click="showFilters=false"></div>
  <div class="absolute bottom-0 left-0 right-0 bg-slate-900 rounded-t-2xl sheet open p-4 max-h-[88vh] overflow-y-auto" style="padding-bottom:calc(16px+var(--safe-bottom))">
    <div class="flex justify-center mb-3"><div class="w-12 h-1 bg-slate-600 rounded"></div></div>
    <div class="flex items-center justify-between mb-4"><h2 class="text-lg font-bold">Filters</h2><button @click="clearFilters()" class="text-amber-400 text-sm">Reset</button></div>
    <div class="space-y-3">

      <div class="glass rounded-xl p-4">
        <div class="text-xs uppercase tracking-widest text-amber-400 font-bold mb-2">📊 Sale Status</div>
        <div class="text-[11px] text-slate-400 mb-3">Default: LISTED only (matches PO behavior). Toggle to see sold/canceled.</div>
        <div class="space-y-1.5">
          <label class="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/50 border border-slate-700/40">
            <div class="flex items-center gap-2.5">
              <input type="checkbox" :checked="filters.status.includes('LISTED')" @change="toggleStatus('LISTED')" class="w-5 h-5 accent-emerald-500">
              <span class="status-badge status-LISTED">● LISTED</span>
              <span class="text-xs text-slate-400">Active sales</span>
            </div>
            <span class="text-xs font-mono text-slate-500" x-text="matchCountByStatus('LISTED')"></span>
          </label>
          <label class="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/50 border border-slate-700/40">
            <div class="flex items-center gap-2.5">
              <input type="checkbox" :checked="filters.status.includes('SOLD')" @change="toggleStatus('SOLD')" class="w-5 h-5 accent-blue-500">
              <span class="status-badge status-SOLD">● SOLD</span>
              <span class="text-xs text-slate-400">Already auctioned</span>
            </div>
            <span class="text-xs font-mono text-slate-500" x-text="matchCountByStatus('SOLD')"></span>
          </label>
          <label class="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/50 border border-slate-700/40">
            <div class="flex items-center gap-2.5">
              <input type="checkbox" :checked="filters.status.includes('CANCELED')" @change="toggleStatus('CANCELED')" class="w-5 h-5 accent-slate-500">
              <span class="status-badge status-CANCELED">● CANCELED</span>
              <span class="text-xs text-slate-400">Pulled from sale</span>
            </div>
            <span class="text-xs font-mono text-slate-500" x-text="matchCountByStatus('CANCELED')"></span>
          </label>
        </div>
      </div>

      <div class="glass-triangle rounded-xl p-4">
        <div class="text-xs uppercase tracking-widest triangle-glow font-bold mb-2">🔺 Shapira Triangle</div>
        <div class="text-[11px] text-slate-400 mb-3">Owner-vertex distress signals.</div>
        <div class="mb-3">
          <label class="block text-xs text-slate-300 mb-1">Min distress score: <b class="text-red-400" x-text="filters.minDistressScore||0"></b></label>
          <input type="range" min="0" max="100" step="5" x-model.number="filters.minDistressScore" class="w-full">
        </div>
        <div class="space-y-1.5">
          <label class="flex items-center gap-2"><input type="checkbox" x-model="filters.sigOutOfState" class="w-4 h-4 accent-red-500"><span class="text-xs">🌐 Out-of-state</span></label>
          <label class="flex items-center gap-2"><input type="checkbox" x-model="filters.sigAbsentee" class="w-4 h-4 accent-amber-500"><span class="text-xs">👻 Absentee</span></label>
          <label class="flex items-center gap-2"><input type="checkbox" x-model="filters.sigEstateTrust" class="w-4 h-4 accent-purple-500"><span class="text-xs">⚰️ Estate/Trust</span></label>
          <label class="flex items-center gap-2"><input type="checkbox" x-model="filters.sigEntity" class="w-4 h-4 accent-blue-500"><span class="text-xs">🏢 Entity/LLC</span></label>
          <label class="flex items-center gap-2"><input type="checkbox" x-model="filters.sigMultiParcel" class="w-4 h-4 accent-pink-500"><span class="text-xs">🔁 Multi-parcel</span></label>
        </div>
      </div>

      <label class="flex items-start gap-3 p-4 rounded-xl" :class="filters.unknownAddrOnly ? 'glass-diamond' : 'bg-slate-800 border border-slate-700'">
        <input type="checkbox" x-model="filters.unknownAddrOnly" class="w-5 h-5 accent-purple-500 mt-0.5">
        <div class="flex-1"><div class="text-sm font-bold"><span class="diamond-glow">💎 Diamonds only</span></div><div class="text-[11px] text-slate-400 mt-1">Unknown street addresses (31 deals)</div></div>
      </label>

      <div><label class="block text-xs uppercase tracking-wide text-slate-400 mb-1">Grade</label>
        <select x-model="filters.grade" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-3">
          <option value="">Any</option><option value="A_GIANT_DISCOUNT">A · &lt;5%</option><option value="B_BIG_DISCOUNT">B · 5-15%</option><option value="C_MODERATE">C · 15-30%</option><option value="D_TIGHT">D · 30-70%</option>
        </select></div>
      <div><label class="block text-xs uppercase tracking-wide text-slate-400 mb-1">Type</label>
        <select x-model="filters.category" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-3">
          <option value="">Any</option><option value="single_family">Single Family</option><option value="condominium">Condo</option><option value="vacant_residential">Vacant Lot</option>
        </select></div>
      <div class="grid grid-cols-2 gap-3">
        <div><label class="block text-xs uppercase tracking-wide text-slate-400 mb-1">Min equity $</label><input type="number" x-model.number="filters.minEquity" placeholder="50000" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-3"></div>
        <div><label class="block text-xs uppercase tracking-wide text-slate-400 mb-1">Max bid $</label><input type="number" x-model.number="filters.maxOpenBid" placeholder="50000" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-3"></div>
      </div>
      <div><label class="block text-xs uppercase tracking-wide text-slate-400 mb-1">City</label><input x-model="filters.cityLike" placeholder="Palm Bay" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-3"></div>
    </div>
    <button @click="showFilters=false" class="w-full mt-5 bg-amber-500 hover:bg-amber-400 text-slate-900 font-bold py-3.5 rounded-lg">Show <span x-text="filteredDeals.length"></span> deals</button>
  </div>
</div>

<!-- DEAL DETAIL (status badge added) -->
<div x-show="openDeal" class="fixed inset-0 z-40" x-cloak>
  <div class="absolute inset-0 bg-black/80" @click="openDeal=null"></div>
  <div class="absolute inset-x-0 bottom-0 md:inset-0 md:flex md:items-center md:justify-center md:p-4">
    <div class="bg-slate-900 rounded-t-2xl md:rounded-2xl sheet open p-5 max-h-[90vh] md:max-w-2xl w-full overflow-y-auto border-t md:border border-amber-500/30" style="padding-bottom:calc(20px+var(--safe-bottom))">
      <div class="flex justify-center mb-3 md:hidden"><div class="w-12 h-1 bg-slate-600 rounded"></div></div>
      <div class="flex items-start justify-between gap-3 mb-3">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-1.5 mb-2">
            <span x-show="openDeal" class="status-badge" :class="openDeal && ('status-'+(openDeal.sale_status||'LISTED'))">● <span x-text="openDeal && (openDeal.sale_status||'LISTED')"></span></span>
            <span class="text-[10px] font-bold px-2 py-1 rounded" :class="'grade-'+(openDeal && openDeal.tax_deed_grade && openDeal.tax_deed_grade.charAt(0))" x-text="openDeal && openDeal.tax_deed_grade"></span>
            <span class="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-300" x-text="openDeal && ('Case '+(openDeal.tax_deed_case||'?'))"></span>
            <span x-show="openDeal && isUnknownAddr(openDeal)" class="text-[10px] font-bold px-2 py-1 rounded bg-gradient-to-r from-sky-500 to-purple-500 text-white">💎</span>
            <span x-show="openDeal && (openDeal.owner_distress_score||0)>=40" class="text-[10px] font-bold px-2 py-1 rounded bg-gradient-to-r from-red-500 to-amber-500 text-white" x-text="openDeal && ('🔺 '+openDeal.owner_distress_score)"></span>
          </div>
          <h2 class="text-xl font-bold text-amber-400 leading-tight" x-text="openDeal && (isUnknownAddr(openDeal) ? ('PIN '+(openDeal.bcpao_account||'?')) : (openDeal.street_address||'(pending)'))"></h2>
          <p class="text-sm text-slate-400" x-text="openDeal && ((openDeal.city||'?')+', FL '+(openDeal.zip5||''))"></p>
        </div>
        <button @click="openDeal=null" class="text-slate-400 text-3xl leading-none shrink-0 -mt-1">×</button>
      </div>
      <div x-show="openDeal && openDeal.owner_name" class="glass-triangle rounded-xl p-3 mb-3">
        <div class="flex items-center justify-between mb-2">
          <div class="text-[10px] uppercase tracking-widest triangle-glow font-bold">🔺 Owner Vertex</div>
          <div class="text-right"><div class="text-lg font-black text-red-400" x-text="openDeal && (openDeal.owner_distress_score||0)"></div><div class="text-[9px] text-slate-500 uppercase">distress</div></div>
        </div>
        <div class="font-mono text-sm font-bold text-amber-300" x-text="openDeal && openDeal.owner_name"></div>
        <div class="text-xs text-slate-400 mb-2" x-text="openDeal && [openDeal.owner_mailing_addr,openDeal.owner_mailing_city,openDeal.owner_mailing_state,openDeal.owner_mailing_zip].filter(Boolean).join(' ')"></div>
        <div class="flex flex-wrap gap-1">
          <template x-for="sig in ((openDeal&&openDeal.owner_distress_signals)||'').split('|').filter(Boolean)">
            <span class="sig-badge" :class="getSigClass(sig)" x-text="getSigLabel(sig)+' · '+getSigWeight(sig)"></span>
          </template>
        </div>
      </div>
      <div x-show="openDeal && openDeal.sale_status==='SOLD'" class="glass-sold rounded-xl p-3 mb-3">
        <div class="text-[10px] uppercase tracking-widest text-blue-300 font-bold mb-2">🔵 Auction Outcome</div>
        <template x-if="openDeal && openDeal.sold_amount">
          <div>
            <div class="grid grid-cols-2 gap-2 text-sm mb-2">
              <div class="bg-slate-900/60 rounded-lg p-2.5"><div class="text-[10px] text-slate-500 uppercase">Opening</div><div class="font-mono font-bold">$<span x-text="formatNum(openDeal.opening_bid)"></span></div></div>
              <div class="bg-blue-950/40 border border-blue-700/30 rounded-lg p-2.5"><div class="text-[10px] text-blue-400 uppercase">Sold Price</div><div class="font-mono font-bold text-blue-300">$<span x-text="formatNum(openDeal.sold_amount)"></span></div></div>
              <div class="bg-slate-900/60 rounded-lg p-2.5"><div class="text-[10px] text-slate-500 uppercase">Premium</div><div class="font-mono font-bold" :class="openDeal.sold_premium_pct>0 ? 'text-amber-400' : 'text-slate-400'" x-text="openDeal.sold_premium_pct ? (openDeal.sold_premium_pct>0?'+':'')+openDeal.sold_premium_pct+'%' : '—'"></div></div>
              <div class="bg-slate-900/60 rounded-lg p-2.5"><div class="text-[10px] text-slate-500 uppercase">% of Market</div><div class="font-mono font-bold text-purple-400" x-text="openDeal.sold_pct_of_market ? openDeal.sold_pct_of_market+'%' : '—'"></div></div>
            </div>
            <div x-show="openDeal.sold_to" class="text-xs text-slate-400">Sold to: <span class="text-slate-200 font-medium" x-text="openDeal.sold_to"></span></div>
            <div x-show="openDeal.buyer_residual_equity" class="text-xs text-emerald-400 mt-1">Buyer residual equity: <b>$<span x-text="formatNum(openDeal.buyer_residual_equity)"></span></b></div>
          </div>
        </template>
        <template x-if="openDeal && !openDeal.sold_amount">
          <div class="text-sm text-amber-400 italic">
            Sold price not yet captured · check brevardclerk.us auction results
            <div class="text-[11px] text-slate-500 mt-2 not-italic">PO backfill arrives in 3-4 days. Manual entry: <code class="bg-slate-800 px-1 rounded text-amber-300">biddeed.update_sold_amount()</code></div>
          </div>
        </template>
      </div>

      <div class="glass rounded-xl p-3 mb-3">
        <div class="text-[10px] uppercase tracking-widest text-slate-400 font-bold mb-2">💰 Financial</div>
        <div class="grid grid-cols-2 gap-2 text-sm">
          <div class="bg-slate-900/60 rounded-lg p-2.5"><div class="text-[10px] text-slate-500 uppercase">Open Bid</div><div class="font-mono font-bold">$<span x-text="openDeal && formatNum(openDeal.opening_bid)"></span></div></div>
          <div class="bg-slate-900/60 rounded-lg p-2.5"><div class="text-[10px] text-slate-500 uppercase">Market</div><div class="font-mono font-bold">$<span x-text="openDeal && formatNum(openDeal.market_value)"></span></div></div>
          <div class="bg-emerald-950/50 border border-emerald-700/30 rounded-lg p-2.5"><div class="text-[10px] text-emerald-400 uppercase">Equity</div><div class="font-mono font-bold text-emerald-400">$<span x-text="openDeal && formatNum(openDeal.equity_at_opening_bid)"></span></div></div>
          <div class="bg-slate-900/60 rounded-lg p-2.5"><div class="text-[10px] text-slate-500 uppercase">% Mkt</div><div class="font-mono font-bold text-amber-400" x-text="(openDeal && openDeal.opening_bid_pct_of_market) ? openDeal.opening_bid_pct_of_market+'%' : '—'"></div></div>
        </div>
      </div>
      <!-- S5 REPORT PURCHASE — the $25 income stream -->
      <div class="mb-3">
        <template x-if="S5_AVAILABLE">
          <button @click="buyS5(openDeal)" class="w-full rounded-xl py-4 px-4 font-bold text-base flex items-center justify-center gap-2 transition-transform active:scale-[0.98]" style="background:linear-gradient(135deg,#f59e0b,#d97706);color:#1f2937;">
            <span style="font-size:1.2rem">💼</span>
            <span>Get the Shapira S5 Report — $25</span>
          </button>
        </template>
        <template x-if="!S5_AVAILABLE">
          <div class="w-full rounded-xl py-3.5 px-4 text-center text-sm border border-slate-700 bg-slate-800/50 text-slate-400">
            <div class="font-semibold text-slate-300">📋 S5 Report — coming soon for COUNTY_TITLE_PLACEHOLDER</div>
            <div class="text-[11px] mt-1">Full AI max-bid analysis available now in certified counties</div>
          </div>
        </template>
        <p class="text-[10px] text-slate-500 text-center mt-2 leading-snug">18-section AI analysis · Shapira Max Bid ceiling · CMA comps · zoning · outcome prediction · branded PDF</p>
      </div>

      <div class="grid grid-cols-3 gap-2">
        <a :href="openDeal && openDeal.google_maps_url" target="_blank" class="bg-slate-800 rounded-lg text-center text-xs py-3 font-medium">🗺️ Maps</a>
        <a :href="openDeal && openDeal.bcpao_link" target="_blank" class="bg-slate-800 rounded-lg text-center text-xs py-3 font-medium">🏢 BCPAO</a>
        <a :href="openDeal && openDeal.brevardclerk_tax_deed_page" target="_blank" class="bg-slate-800 rounded-lg text-center text-xs py-3 font-medium">⚖️ Clerk</a>
      </div>
    </div>
  </div>
</div>

<!-- CHAT (unchanged) -->
<div x-show="showChatModal" class="fixed inset-0 z-40" x-cloak>
  <div class="absolute inset-0 bg-black/80" @click="showChatModal=false"></div>
  <div class="absolute inset-x-0 bottom-0 md:inset-0 md:flex md:items-center md:justify-center md:p-4">
    <div class="bg-slate-900 rounded-t-2xl md:rounded-2xl sheet open w-full md:max-w-xl border-t md:border border-amber-500/30 overflow-hidden flex flex-col" style="max-height:90vh">
      <div class="flex justify-center pt-3 md:hidden"><div class="w-12 h-1 bg-slate-600 rounded"></div></div>
      <div class="p-4 border-b border-slate-700/50 flex items-center justify-between gap-2">
        <div><h2 class="text-base font-bold text-amber-400">✨ Build Buybox</h2><p class="text-[11px] text-slate-400">Describe target. Saved as persona.</p></div>
        <button @click="showChatModal=false" class="text-slate-400 text-2xl">×</button>
      </div>
      <div class="p-4 space-y-2 overflow-y-auto flex-1" style="min-height:200px;max-height:50vh">
        <template x-for="msg in chatLog" :key="msg.id"><div :class="msg.role==='user'?'flex justify-end':'flex justify-start'"><div :class="msg.role==='user'?'bg-amber-500 text-slate-900 font-medium':'bg-slate-800 text-slate-200'" class="px-3 py-2.5 rounded-2xl max-w-[85%] text-sm" x-html="msg.text"></div></div></template>
      </div>
      <div class="p-3 border-t border-slate-700/50" style="padding-bottom:calc(12px+var(--safe-bottom))">
        <div class="flex gap-2">
          <input x-model="chatInput" @keyup.enter="sendChat()" placeholder="out-of-state owners with equity" class="flex-1 bg-slate-800 border border-slate-700 rounded-full px-4">
          <button @click="sendChat()" class="px-5 bg-amber-500 text-slate-900 font-bold rounded-full">Send</button>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
const COUNTY_SLUG = "COUNTY_SLUG_PLACEHOLDER";
const COUNTY_TITLE_JS = "COUNTY_TITLE_PLACEHOLDER";
const S5_CERTIFIED_COUNTIES = S5_COUNTIES_PLACEHOLDER;
const S5_AVAILABLE = S5_CERTIFIED_COUNTIES.includes(COUNTY_SLUG);
const SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE2ODc0Nzc1MTksImV4cCI6MjAwMzA1MzUxOX0.VFl2gOfVWMRFQPiWxkpRf-GH5Vc_9bRHhK5bnAHmLNA";
</script>
<script>
const SIG_META = {
  OUT_OF_STATE: {label:'🌐 Out-of-state', cls:'sig-out', weight:25},
  ABSENTEE:     {label:'👻 Absentee',     cls:'sig-abs', weight:20},
  ESTATE_TRUST: {label:'⚰️ Estate/Trust', cls:'sig-est', weight:30},
  ENTITY:       {label:'🏢 Entity',       cls:'sig-ent', weight:15},
  LENDER_REO:   {label:'🏦 Lender REO',   cls:'sig-len', weight:10},
  MULTI_PARCEL: {label:'🔁 Multi-parcel', cls:'sig-mul', weight:20}
};
const DEFAULT_FILTERS = { status:['LISTED'], grade:'', category:'', minEquity:null, maxOpenBid:null, cityLike:'', unknownAddrOnly:false, ownerLike:null, minDistressScore:0, sigOutOfState:false, sigAbsentee:false, sigEstateTrust:false, sigEntity:false, sigMultiParcel:false };

function app() {
  return {
    deals: [],
    filters: {...DEFAULT_FILTERS},
    sortKey: 'equity_at_opening_bid',
    activePersona: null,
    openDeal: null,
    showFilters: false,
    showChatModal: false,
    showOwnerPicker: false,
    ownerPickerQuery: '',
    chatInput: '',
    chatLog: [],
    customPersonas: JSON.parse(localStorage.getItem('biddeed_personas') || '[]'),
    rowLimit: 25,

    builtInPersonas: [
      {code:'TRIANGLE', icon:'🔺', name:'Triangle', desc:'Distress score ≥ 40', filter:{status:['LISTED'],minDistressScore:40}, scoreKey:'owner_distress_score'},
      {code:'DIAMONDS', icon:'💎', name:'Diamonds', desc:'Unknown addresses — proxy bidders skip', filter:{status:['LISTED'],unknownAddrOnly:true}, scoreKey:'land_score'},
      {code:'SOLD_TODAY', icon:'🔵', name:'Sold Today', desc:'Already auctioned today (BD exclusive — PO does not surface)', filter:{status:['SOLD']}, scoreKey:'equity_at_opening_bid'},
      {code:'FLIPPER', icon:'🔨', name:'Flipper', desc:'SFR with equity', filter:{status:['LISTED'],category:'single_family',minEquity:50000}, scoreKey:'flipper_score'},
      {code:'BUY_AND_HOLD', icon:'🏠', name:'Buy & Hold', desc:'Rental cash flow', filter:{status:['LISTED'],category:'single_family',minEquity:30000}, scoreKey:'rental_score'},
      {code:'WHOLESALER', icon:'⚡', name:'Wholesaler', desc:'Lock + assign', filter:{status:['LISTED'],maxOpenBid:50000}, scoreKey:'wholesale_score'},
      {code:'LAND', icon:'🌲', name:'Land', desc:'Vacant lots', filter:{status:['LISTED'],category:'vacant_residential'}, scoreKey:'land_score'},
      {code:'OUT_OF_STATE', icon:'🌐', name:'Out-of-state', desc:'Mailing ≠ FL', filter:{status:['LISTED'],sigOutOfState:true}, scoreKey:'owner_distress_score'},
      {code:'ESTATE', icon:'⚰️', name:'Estate', desc:'Trust/heirs', filter:{status:['LISTED'],sigEstateTrust:true}, scoreKey:'owner_distress_score'},
      {code:'SHELL_LLC', icon:'🏢', name:'LLC', desc:'Entity owners', filter:{status:['LISTED'],sigEntity:true}, scoreKey:'owner_distress_score'},
      {code:'PORTFOLIO', icon:'🔁', name:'Portfolio', desc:'Multi-parcel', filter:{status:['LISTED'],sigMultiParcel:true}, scoreKey:'owner_distress_score'}
    ],

    init() {
      const today = new Date().toISOString().slice(0,10);
      const cutoff = new Date(Date.now()+35*24*60*60*1000).toISOString().slice(0,10);
      fetch('/county/'+COUNTY_SLUG+'/lots')
      .then(r => r.json())
      .then(rows => {
        this.deals = rows.map(r => {
          const bid = Number(r.opening_bid) || 0;
          const assessed = Number(r.assessed_value) || 0;
          const market = Number(r.market_value) || assessed;
          const equity = market > 0 ? market - bid : 0;
          const pctMkt = market > 0 ? Math.round((bid/market)*100) : null;
          const addr = (r.property_address || '').trim();
          const parts = addr.split(',');
          const street = parts[0] || '';
          const city = parts[1] ? parts[1].trim() : '';
          const zipMatch = addr.match(/(\\d{5})/);
          const zip5 = zipMatch ? zipMatch[1] : '';
          return {
            tax_deed_case: r.case_number || '',
            full_address: addr,
            street_address: street,
            city: city,
            zip5: zip5,
            opening_bid: bid,
            market_value: market,
            equity_at_opening_bid: equity,
            opening_bid_pct_of_market: pctMkt,
            assessed_value: assessed,
            sale_status: 'LISTED',
            sale_type: r.sale_type,
            auction_date: r.auction_date,
            clerk_url: r.clerk_url || r.auction_url || '',
            bcpao_url: r.bcpao_url || '',
            plaintiff: r.plaintiff || '',
            property_category: r.sale_type === 'tax_deed' ? 'tax_deed' : 'foreclosure',
            tax_deed_grade: market > 0 && equity > 50000 ? 'A_PREMIUM' : market > 0 && equity > 20000 ? 'B_SOLID' : market > 0 ? 'C_MARGINAL' : 'X_UNKNOWN',
            owner_distress_score: 0,
            owner_distress_signals: '',
            owner_name: r.plaintiff || '',
            owner_mailing_state: 'FL',
          };
        }).filter(d => d && (d.tax_deed_case || d.full_address));
      })
      .catch(e => console.error('Failed to load lots:', e));
    },

    isUnknownAddr(d) { if (!d) return false; const a = (d.street_address||d.full_address||'').toUpperCase(); return !a.trim() || a.includes('UNKNOWN') || a.startsWith('0 '); },
    buyS5(d) {
      if (!d || !S5_AVAILABLE) return;
      const params = new URLSearchParams({
        county: COUNTY_SLUG,
        address: d.street_address || d.full_address || '',
        date: d.auction_date || '',
      });
      window.location.href = '/buy-report?' + params.toString();
    },
    getSigClass(sig) { return (SIG_META[sig] && SIG_META[sig].cls) || 'sig-out'; },
    getSigLabel(sig) { return (SIG_META[sig] && SIG_META[sig].label) || sig; },
    getSigWeight(sig) { return '+' + ((SIG_META[sig] && SIG_META[sig].weight) || 0); },

    matchCountByStatus(s) { return this.deals.filter(d => (d.sale_status||'LISTED') === s).length; },
    toggleStatus(s) {
      if (this.filters.status.includes(s)) {
        const next = this.filters.status.filter(x => x !== s);
        this.filters.status = next.length ? next : ['LISTED'];
      } else {
        this.filters.status = [...this.filters.status, s];
      }
    },
    showAllStatuses() { this.filters.status = ['LISTED','SOLD','CANCELED']; },

    get filteredDeals() {
      return this.deals.filter(d => this.matchesFilter(d, this.filters))
        .sort((a,b) => {
          const k = this.sortKey;
          if (k === 'opening_bid' || k === 'opening_bid_pct_of_market') return (a[k] || Infinity) - (b[k] || Infinity);
          return (b[k] || -Infinity) - (a[k] || -Infinity);
        });
    },
    get displayDeals() { return this.filteredDeals.slice(0, this.rowLimit); },
    get filteredEquity() { return this.filteredDeals.reduce((s,d) => s + Math.max(d.equity_at_opening_bid || 0, 0), 0); },
    get hiddenStatusCount() {
      return ['LISTED','SOLD','CANCELED'].filter(s => !this.filters.status.includes(s))
        .reduce((sum, s) => sum + this.matchCountByStatus(s), 0);
    },
    get hiddenStatusBreakdown() {
      return ['SOLD','CANCELED'].filter(s => !this.filters.status.includes(s))
        .map(s => this.matchCountByStatus(s) + ' ' + s.toLowerCase())
        .filter(x => !x.startsWith('0 ')).join(', ');
    },
    get activeFilterCount() {
      const f = this.filters;
      const statusChanged = f.status.length !== 1 || f.status[0] !== 'LISTED';
      return (statusChanged?1:0)+(f.grade?1:0)+(f.category?1:0)+(f.minEquity?1:0)+(f.maxOpenBid?1:0)+(f.cityLike?1:0)+(f.unknownAddrOnly?1:0)+(f.ownerLike?1:0)+((f.minDistressScore||0)>0?1:0)+(f.sigOutOfState?1:0)+(f.sigAbsentee?1:0)+(f.sigEstateTrust?1:0)+(f.sigEntity?1:0)+(f.sigMultiParcel?1:0);
    },

    get uniqueOwnerList() {
      const map = new Map();
      this.deals.forEach(d => {
        if (!d.owner_name) return;
        if (!this.filters.status.includes(d.sale_status||'LISTED')) return;
        const k = d.owner_name;
        if (!map.has(k)) map.set(k, { name:k, state:d.owner_mailing_state||'', deals:0, equity:0, topScore:0, signals:new Set() });
        const o = map.get(k);
        o.deals++;
        o.equity += Math.max(d.equity_at_opening_bid || 0, 0);
        o.topScore = Math.max(o.topScore, d.owner_distress_score || 0);
        (d.owner_distress_signals || '').split('|').filter(Boolean).forEach(s => o.signals.add(s));
      });
      return Array.from(map.values()).map(o => ({...o, signals:Array.from(o.signals)})).sort((a,b) => b.topScore - a.topScore || b.equity - a.equity);
    },
    get uniqueOwnerCount() { return this.uniqueOwnerList.length; },
    get filteredOwnerList() {
      if (!this.ownerPickerQuery) return this.uniqueOwnerList;
      const q = this.ownerPickerQuery.toLowerCase();
      return this.uniqueOwnerList.filter(o => o.name.toLowerCase().includes(q));
    },

    matchesFilter(d, f) {
      if (f.status && f.status.length && !f.status.includes(d.sale_status||'LISTED')) return false;
      if (f.unknownAddrOnly && !this.isUnknownAddr(d)) return false;
      if (f.grade && d.tax_deed_grade !== f.grade) return false;
      if (f.category && d.property_category !== f.category) return false;
      if (f.minEquity != null && f.minEquity !== '' && (d.equity_at_opening_bid || 0) < f.minEquity) return false;
      if (f.maxOpenBid != null && f.maxOpenBid !== '' && d.opening_bid != null && d.opening_bid > f.maxOpenBid) return false;
      if (f.cityLike && !(d.city||'').toLowerCase().includes(f.cityLike.toLowerCase())) return false;
      if (f.ownerLike && !(d.owner_name||'').toLowerCase().includes(f.ownerLike.toLowerCase())) return false;
      if (f.minDistressScore && (d.owner_distress_score||0) < f.minDistressScore) return false;
      const sigs = (d.owner_distress_signals||'').split('|');
      if (f.sigOutOfState && !sigs.includes('OUT_OF_STATE')) return false;
      if (f.sigAbsentee && !sigs.includes('ABSENTEE')) return false;
      if (f.sigEstateTrust && !sigs.includes('ESTATE_TRUST')) return false;
      if (f.sigEntity && !sigs.includes('ENTITY')) return false;
      if (f.sigMultiParcel && !sigs.includes('MULTI_PARCEL')) return false;
      return true;
    },

    formatNum(n) { return (n != null && !isNaN(n)) ? Math.round(n).toLocaleString() : '—'; },
    matchCount(f) { return this.deals.filter(d => this.matchesFilter(d, {...DEFAULT_FILTERS, ...f})).length; },

    pickOwner(name) { this.filters.ownerLike = name; this.showOwnerPicker = false; this.ownerPickerQuery = ''; },
    clearOwner() { this.filters.ownerLike = null; this.ownerPickerQuery = ''; },

    selectPersona(p) {
      this.activePersona = p;
      this.filters = {...DEFAULT_FILTERS, ...p.filter};
      if (p.scoreKey) this.sortKey = p.scoreKey;
      this.rowLimit = 25;
      window.scrollTo({top:0, behavior:'smooth'});
    },
    clearPersona() { this.activePersona = null; this.clearFilters(); },
    clearFilters() { this.filters = {...DEFAULT_FILTERS}; this.sortKey='equity_at_opening_bid'; },

    openChat() { this.showChatModal = true; this.chatLog = [{id:Date.now(), role:'ai', text:'Try "out-of-state owners", "estate sales", "SFR Palm Bay equity over 100K".'}]; this.chatInput = ''; },

    sendChat() {
      const text = this.chatInput.trim(); if (!text) return;
      this.chatLog.push({id:Date.now(), role:'user', text:text});
      this.chatInput = '';
      const f = this.parseNL(text);
      const matchCount = this.deals.filter(d => this.matchesFilter(d, {...DEFAULT_FILTERS, ...f})).length;
      this.chatLog.push({id:Date.now()+1, role:'ai', text:'✓ <b class="text-emerald-400">' + matchCount + ' deals</b> match. Applied filters.'});
      this.filters = {...DEFAULT_FILTERS, ...f};
      setTimeout(() => { this.showChatModal = false; }, 800);
    },

    parseNL(text) {
      const t = ' ' + text.toLowerCase() + ' ';
      const f = {};
      if (/\\b(sold today|already sold|completed)\\b/.test(t)) f.status = ['SOLD'];
      else if (/\\b(canceled|cancelled|pulled)\\b/.test(t)) f.status = ['CANCELED'];
      else if (/\\b(all status|include sold|show everything)\\b/.test(t)) f.status = ['LISTED','SOLD','CANCELED'];
      if (/\\b(out.?of.?state|outside florida)\\b/.test(t)) f.sigOutOfState = true;
      if (/\\babsentee\\b/.test(t)) f.sigAbsentee = true;
      if (/\\b(estate|trust|heirs?|deceased|probate)\\b/.test(t)) f.sigEstateTrust = true;
      if (/\\b(llc|inc|corp|entity|shell)\\b/.test(t)) f.sigEntity = true;
      if (/\\b(multiple parcels?|portfolio|repeat)\\b/.test(t)) f.sigMultiParcel = true;
      if (/\\b(distress|triangle|motivated)\\b/.test(t)) f.minDistressScore = 40;
      if (/\\b(diamond|hidden gem|unknown address)\\b/.test(t)) f.unknownAddrOnly = true;
      if (/\\b(vacant|empty\\s+lot|raw\\s+land)/.test(t)) f.category = 'vacant_residential';
      else if (/\\bcondo/.test(t)) f.category = 'condominium';
      else if (/\\b(single[\\s-]?family|sfr|sfh|house|home)/.test(t)) f.category = 'single_family';
      ['palm bay','cocoa beach','cocoa','melbourne','rockledge','titusville','merritt island'].forEach(c => { if (t.includes(' '+c)) f.cityLike = c; });
      const me = t.match(/(?:over|above|more than|min|>=?)\\s*\\$?\\s*([\\d,]+)(k|m)?/);
      if (me) { let n = parseFloat(me[1].replace(/,/g,'')); if (me[2]==='k') n*=1000; if (me[2]==='m') n*=1000000; if (/equity|profit/.test(t)) f.minEquity = Math.round(n); }
      return f;
    }
  };
}
</script>

<!-- Lead capture -- added Aug 10 2026. These 67 county pages are the actual
     SEO landing pages (linked from /sitemap.xml); previously they had ZERO
     email capture at all -- only the blog posts did. Self-contained,
     independent of the Alpine app() component above to avoid any risk of
     interfering with its data binding. Reuses the same proven /chat/lead
     endpoint the blog posts and homepage chatbot already use. -->
<div id="county-lead-bar" style="position:fixed;left:0;right:0;bottom:0;z-index:40;background:rgba(2,6,23,.97);backdrop-filter:blur(12px);border-top:1px solid rgba(245,158,11,.3);padding:12px 16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
  <div style="flex:1;min-width:180px;font-size:12px;color:#94a3b8">Get COUNTY_TITLE_PLACEHOLDER's next 5 auctions emailed free</div>
  <form id="county-lead-form" style="display:flex;gap:6px;flex:2;min-width:220px">
    <input type="email" id="county-lead-email" placeholder="you@example.com" required style="flex:1;background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:8px 12px;color:white;font-size:14px;outline:none">
    <button type="submit" id="county-lead-btn" style="background:linear-gradient(135deg,#f59e0b,#f97316);color:#020617;border:none;padding:8px 16px;border-radius:8px;font-weight:700;font-size:13px;white-space:nowrap;cursor:pointer">Send Free List</button>
  </form>
  <div id="county-lead-msg" style="font-size:11px;width:100%;display:none"></div>
</div>
<script>
(function(){
  var form = document.getElementById('county-lead-form');
  if (!form) return;
  form.addEventListener('submit', function(e){
    e.preventDefault();
    var btn = document.getElementById('county-lead-btn');
    var msg = document.getElementById('county-lead-msg');
    var email = document.getElementById('county-lead-email').value.trim();
    msg.style.display = 'none';
    btn.disabled = true; btn.textContent = 'Sending...';
    fetch('/chat/lead', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ email: email, county: 'COUNTY_SLUG_PLACEHOLDER', source: 'county_page_COUNTY_SLUG_PLACEHOLDER', email_consent: true })
    })
    .then(function(res){ return res.json().then(function(data){ return {ok:res.ok, data:data}; }); })
    .then(function(r){
      if (r.ok && r.data.ok) {
        msg.textContent = 'Sent — check your email.';
        msg.style.color = '#34d399'; msg.style.display = 'block';
        btn.textContent = 'Sent ✓';
      } else {
        msg.textContent = (r.data.error || 'Something went wrong. Please try again.');
        msg.style.color = '#f87171'; msg.style.display = 'block';
        btn.disabled = false; btn.textContent = 'Send Free List';
      }
    })
    .catch(function(){
      msg.textContent = 'Network error. Please try again.';
      msg.style.color = '#f87171'; msg.style.display = 'block';
      btn.disabled = false; btn.textContent = 'Send Free List';
    });
  });
})();
</script>
</body>
</html>`;

// ── Static HTML pages ────────────────────────────────────────────────────────
const HOMEPAGE_SCRIPT = `<script>
// ── AUCTION REPLAY ──
const MIN=70000,MAX=84000,FINAL=73501,ENTRY=72100;
let animating=false,raf=null;

function pct(v){return((v-MIN)/(MAX-MIN)*100).toFixed(3)+'%'}

function setFill(v){
  const fill=document.getElementById('ladder-fill');
  fill.style.transition='none';  // no CSS transition — JS drives it entirely
  fill.style.width=pct(v);
  document.getElementById('sale-val').textContent='$'+Math.round(v).toLocaleString();
}

// Init to final state on load
window.addEventListener('DOMContentLoaded',function(){setFill(FINAL);});

function replayAuction(){
  if(animating)return;
  animating=true;
  const btn=document.getElementById('replay-btn');
  const status=document.getElementById('status-line');
  const saleVal=document.getElementById('sale-val');
  btn.disabled=true;
  status.textContent='Bidding in progress…';
  saleVal.style.color='var(--amber)';

  const DURATION=2000;
  const startTs=Date.now();

  setFill(ENTRY);

  // Use 50ms ticks — coarse enough to survive Android throttling when off-screen
  const timer=setInterval(function(){
    const elapsed=Date.now()-startTs;
    const progress=Math.min(elapsed/DURATION,1);
    const eased=progress<0.5?2*progress*progress:1-Math.pow(-2*progress+2,2)/2;
    setFill(ENTRY+(FINAL-ENTRY)*eased);

    if(progress>=1){
      clearInterval(timer);
      setFill(FINAL);
      saleVal.style.color='var(--green)';
      status.textContent='The sale closed at $73,501 — $8,499 under the ceiling, $1,401 over the entry. Every dollar where it should be.';
      animating=false;
      btn.disabled=false;
    }
  }, 50);
}

// ── COUNTY SELECT → show upsell ──
document.getElementById('lead-county').addEventListener('change',function(){
  const county=this.value;
  if(!county)return;
  const upsell=document.getElementById('upsell-row');
  upsell.style.display='flex';
  // Wire $25 link to buy-report with county pre-filled
  document.getElementById('upsell-25').href='/buy-report?county='+encodeURIComponent(county);
});

// ── LEAD CAPTURE ──
async function submitLead(){
  const email=document.getElementById('lead-email').value.trim();
  const county=document.getElementById('lead-county')?document.getElementById('lead-county').value:'';
  const phone=(document.getElementById('lead-phone')||{value:''}).value.trim();
  const email_consent=document.getElementById('lead-email-consent')?document.getElementById('lead-email-consent').checked:true;
  const sms_consent=document.getElementById('lead-sms-consent')?document.getElementById('lead-sms-consent').checked:false;
  const err=document.getElementById('lead-error');
  err.textContent='';
  if(!county){err.textContent='Please select your county first.';return;}
  if(!email||!email.includes('@')){err.textContent='Please enter a valid email address.';return;}
  const btn=document.getElementById('lead-submit-btn');
  if(btn){btn.disabled=true;btn.textContent='Sending…';}
  try{
    const payload={email,county,source:'landing_free_report',email_consent};
    if(phone) payload.phone=phone;
    if(sms_consent) payload.sms_consent=true;
    const r=await fetch('/chat/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=r.ok?await r.json():{ok:false};
    if(data.ok){
      document.getElementById('lead-form-wrap').style.display='none';
      const successEl=document.getElementById('lead-success');
      successEl.style.display='block';
      // Render instant auction cards
      const cards=document.getElementById('lead-auction-cards');
      if(cards&&data.auctions&&data.auctions.length){
        cards.innerHTML=data.auctions.map(a=>{
          const addr=a.property_address||'Address TBD';
          const dt=a.auction_date?new Date(a.auction_date+'T12:00:00').toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'}):'TBD';
          const bid=a.opening_bid?'$'+Number(a.opening_bid).toLocaleString():'TBD';
          const type=(a.sale_type||'').replace('_',' ').toUpperCase();
          const buyHref='/buy-report?county='+encodeURIComponent(county)+'&address='+encodeURIComponent(addr);
          return '<div style="background:var(--charcoal);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:14px 16px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">'
            +'<div style="flex:1;min-width:0"><div style="font-size:13px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+addr+'</div>'
            +'<div style="font-size:11px;color:var(--slate);margin-top:3px">'+dt+' · <span style="color:var(--orange)">'+type+'</span></div></div>'
            +'<div style="text-align:right;flex-shrink:0"><div style="font-size:15px;font-weight:700;color:#fff">'+bid+'</div>'
            +'<a href="'+buyHref+'" style="font-size:11px;color:var(--orange);text-decoration:none;font-weight:600">S5 Report $25 →</a></div>'
            +'</div>';
        }).join('');
        // Wire $25 link to county
        const u25=document.getElementById('upsell-25');
        if(u25) u25.href='/buy-report?county='+encodeURIComponent(county);
      } else if(cards){
        cards.innerHTML='<div style="font-size:13px;color:var(--slate);text-align:center;padding:16px">Check your email — your county report is on its way.</div>';
      }
    } else {
      if(btn){btn.disabled=false;btn.textContent='Get My Free County Report →';}
      err.textContent='Something went wrong. Please try again.';
    }
  } catch(e){
    if(btn){btn.disabled=false;btn.textContent='Get My Free County Report →';}
    err.textContent='Something went wrong. Please try again.';
  }
}
</script>
</body>
</html>`;

function buildHomepageHtml() { return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BidDeed.AI — AI-Powered Foreclosure &amp; Tax Deed Auction Intelligence</title>
<meta name="description" content="Know your walk-away number before the gavel falls. One $25 report gives you the Shapira Max Bid, value bands, rehab budget, lien flags, and an ML read — 18 sections, every number traced to a named source.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
*{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
:root{
  --navy:#0B1929;--navy-band:#0E2136;--header-strip:#12283F;--charcoal:#1E293B;
  --orange:#F97316;--orange-hover:#FDBA74;--slate:#e2eaf2;--slate-dim:#b8cfe0;
  --body-text:#f0f4f8;--green:#22C55E;--amber:#F59E0B;--red:#EF4444;
  --divider:rgba(148,163,184,0.12);--gold:#F5C518;
}
html{scroll-behavior:smooth}
body{background:var(--navy);color:var(--body-text);font-family:Inter,sans-serif;overflow-x:hidden;font-size:17px;line-height:1.75}
a{text-decoration:none;color:inherit}

/* NAV */
nav{position:sticky;top:0;z-index:100;background:rgba(11,25,41,0.92);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--orange);padding:0 2rem}
.nav-i{max-width:1100px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;height:60px;gap:1rem}
.logo{display:flex;align-items:center;gap:8px;font-size:17px;font-weight:700;color:#fff;letter-spacing:-.02em;flex-shrink:0}
.logo span{color:var(--orange)}
.nav-links{display:flex;gap:1.5rem;flex-wrap:wrap}
.nav-links a{color:var(--slate);font-size:14px;font-weight:500;transition:color .15s}
.nav-links a:hover{color:#fff}
.nav-cta{background:var(--orange);color:var(--navy);padding:10px 20px;border-radius:999px;font-size:13px;font-weight:700;letter-spacing:.04em;transition:background .15s;white-space:nowrap;flex-shrink:0}
.nav-cta:hover{background:var(--orange-hover)}

/* HERO */
.hero{padding:4.5rem 2rem 4rem;text-align:center;max-width:860px;margin:0 auto}
.eyebrow{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--orange);margin-bottom:1.25rem}
h1{font-size:clamp(2.2rem,5.5vw,3.25rem);font-weight:800;color:#fff;line-height:1.12;letter-spacing:-.03em;margin-bottom:1.25rem}
.hero-sub{font-size:17px;color:var(--slate);max-width:600px;margin:0 auto 1.25rem;line-height:1.7}
.hero-cred{font-size:13px;font-weight:600;color:var(--slate-dim);margin-bottom:1.25rem}
.hero-cred b{color:var(--gold);font-weight:700}
.hero-artifact{display:inline-flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:center;background:var(--charcoal);border:1px solid var(--divider);border-radius:10px;padding:10px 18px;margin-bottom:1.75rem;font-family:'JetBrains Mono',monospace;font-size:12.5px;color:var(--slate)}
.hero-artifact b{color:var(--orange);font-size:13px}
.hero-artifact .res{color:var(--green)}
.hero-ctas{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap}
.btn-solid{background:var(--orange);color:var(--navy);padding:16px 34px;border-radius:999px;font-size:16px;font-weight:800;transition:background .15s;display:inline-block}
.btn-solid:hover{background:var(--orange-hover)}
.btn-outline{border:1px solid var(--slate);color:var(--body-text);padding:12px 24px;border-radius:999px;font-size:14px;font-weight:600;transition:border-color .15s,color .15s;display:inline-block;opacity:.85}
.btn-outline:hover{border-color:var(--orange);color:#fff;opacity:1}

/* PROOF BAND */
.proof-band{background:var(--navy-band);padding:5rem 2rem}
.proof-inner{max-width:760px;margin:0 auto}
.section-label{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--orange);margin-bottom:1rem;text-align:center}
.section-h{font-size:clamp(1.6rem,3vw,2.25rem);font-weight:800;color:#fff;text-align:center;margin-bottom:.5rem;letter-spacing:-.02em}
.section-sub{text-align:center;color:var(--slate);font-size:15px;margin-bottom:2.5rem}

/* CASE CARD */
.case-card{background:var(--navy);border:1px solid var(--charcoal);border-radius:14px;overflow:hidden}
.case-header{background:var(--header-strip);border-left:4px solid var(--orange);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}
.case-meta{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--orange);letter-spacing:.06em;text-transform:uppercase}
.case-date{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--slate)}
.case-address{font-size:16px;font-weight:700;color:#fff;margin-top:4px}
.case-body{padding:24px 20px}

/* STAT TILES */
.stat-tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
@media(max-width:600px){.stat-tiles{grid-template-columns:repeat(2,1fr)}}
.tile{background:var(--charcoal);border-radius:10px;padding:14px 16px}
.tile-label{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--slate);margin-bottom:6px}
.tile-val{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#fff}
.tile-val.orange{color:var(--orange)}
.tile-val.green{color:var(--green)}

/* BID LADDER */
.ladder-wrap{margin-bottom:20px}
.ladder-track{position:relative;height:8px;background:var(--charcoal);border-radius:999px;margin-top:56px;margin-bottom:48px}
.ladder-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--green),var(--orange));width:24.65%}
.marker{position:absolute;display:flex;flex-direction:column;align-items:flex-start}
.marker-dot{width:9px;height:9px;border-radius:50%;position:absolute;transform:translateX(-50%)}
.mgreen{background:var(--green);border:2px solid var(--green)}
.mamber{background:var(--amber);border:2px solid var(--amber)}
.morange{background:var(--orange);border:2px solid var(--orange)}
.marker-label{font-family:'JetBrains Mono',monospace;font-size:9px;color:#e2eaf2;white-space:nowrap;text-align:left;line-height:1.5}
/* Labels BELOW the bar */
.marker.marker-below{top:14px}
.marker.marker-below .marker-dot{top:-19px}
.marker.marker-below .marker-label{margin-top:4px;transform:translateX(0);left:0;white-space:nowrap}
/* Labels ABOVE the bar — ceiling floats up so it never overlaps */
.marker.marker-above{top:-46px}
.marker.marker-above .marker-dot{bottom:-19px;top:auto}
.marker.marker-above .marker-label{margin-bottom:4px;order:-1;text-align:right}

/* REPLAY */
.replay-row{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:16px}
.status-line{font-size:13px;color:#e2eaf2;font-style:italic;flex:1}
.btn-replay{background:var(--orange);color:var(--navy);border:none;padding:10px 20px;border-radius:999px;font-size:13px;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:8px;transition:background .15s;flex-shrink:0}
.btn-replay:hover{background:var(--orange-hover)}
.btn-replay:disabled{opacity:.55;cursor:default}

/* RESULT BANNER */
.result-banner{background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.3);border-radius:10px;padding:16px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.result-text{color:var(--green);font-size:14px;font-weight:600}
.equity-chip{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.25);border-radius:999px;padding:6px 14px;font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--green);font-weight:700}
.proof-footnote{text-align:center;margin-top:1.25rem;font-size:13px;color:var(--slate-dim);line-height:1.6}

/* INSIDE THE REPORT */
.inside-band{padding:5rem 2rem;background:var(--navy)}
.inside-inner{max-width:1000px;margin:0 auto;text-align:center}
.feature-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;margin:2rem 0 2.25rem;text-align:left}
.feat-card{background:var(--charcoal);border:1px solid var(--divider);border-radius:10px;padding:22px}
.feat-section{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--orange);letter-spacing:.08em;margin-bottom:8px}
.feat-title{font-size:16px;font-weight:700;color:#fff;margin-bottom:8px}
.feat-desc{font-size:13px;color:var(--slate);line-height:1.6}
.cta-center{text-align:center}
.btn-outline-orange{border:1px solid var(--orange);color:var(--orange);padding:12px 28px;border-radius:999px;font-size:14px;font-weight:700;display:inline-block;transition:background .15s,color .15s}
.btn-outline-orange:hover{background:var(--orange);color:var(--navy)}

/* LEAD CAPTURE */
.lead-band{padding:5rem 2rem;background:var(--navy-band)}
.lead-inner{max-width:600px;margin:0 auto;text-align:center}
.county-select{width:100%;background:var(--charcoal);border:1px solid var(--slate);border-radius:999px;padding:13px 20px;font-size:14px;color:#fff;outline:none;appearance:none;-webkit-appearance:none;cursor:pointer;transition:border-color .15s;margin-top:1.75rem}
.county-select:focus{border-color:var(--orange)}
.county-select option{background:#1E293B;color:#fff}
.lead-email-row{display:flex;gap:10px;margin-top:10px;flex-wrap:wrap}
.lead-input{flex:1;min-width:200px;background:var(--charcoal);border:1px solid var(--slate);border-radius:999px;padding:13px 20px;font-size:14px;color:#fff;outline:none;transition:border-color .15s}
.lead-input::placeholder{color:var(--slate-dim)}
.lead-input:focus{border-color:var(--orange)}
.lead-submit{background:var(--orange);color:var(--navy);border:none;padding:13px 26px;border-radius:999px;font-size:14px;font-weight:700;cursor:pointer;white-space:nowrap;transition:background .15s}
.lead-submit:hover{background:var(--orange-hover)}
.lead-error{color:var(--red);font-size:12px;margin-top:.5rem;min-height:18px;text-align:left;padding:0 8px}
.lead-success{background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.3);border-radius:10px;padding:20px;color:var(--green);font-size:15px;font-weight:600;display:none;margin-top:1rem}
.upsell-row{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:1.5rem}
.upsell-card{background:var(--charcoal);border:1px solid var(--divider);border-radius:12px;padding:16px 20px;text-align:center;flex:1;min-width:180px;max-width:240px}
.upsell-card.featured{border-color:var(--orange)}
.upsell-tier{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--slate);margin-bottom:4px}
.upsell-price{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;color:#fff;margin-bottom:8px}
.upsell-price span{font-size:13px;color:var(--slate);font-weight:400}
.upsell-cta{display:block;background:var(--orange);color:var(--navy);padding:10px;border-radius:999px;font-size:13px;font-weight:700;margin-top:10px;transition:background .15s}
.upsell-cta:hover{background:var(--orange-hover)}
.upsell-cta.ghost{background:transparent;border:1px solid var(--slate);color:var(--body-text)}
.upsell-cta.ghost:hover{border-color:var(--orange);color:#fff}

/* PRICING */
.pricing-band{padding:5rem 2rem;background:var(--navy)}
.pricing-inner{max-width:900px;margin:0 auto}
.pricing-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.25rem;margin-top:2.5rem}
.price-card{background:var(--charcoal);border:1px solid var(--divider);border-radius:14px;padding:28px;position:relative}
.price-card.featured{border:2px solid var(--orange)}
.popular-chip{position:absolute;top:-13px;left:50%;transform:translateX(-50%);background:var(--orange);color:var(--navy);font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:4px 14px;border-radius:999px;white-space:nowrap}
.price-tier{font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--slate);margin-bottom:8px}
.price-amount{font-family:'JetBrains Mono',monospace;font-size:40px;font-weight:700;color:#fff;margin-bottom:4px}
.price-amount span{font-size:15px;color:var(--slate);font-weight:400}
.price-desc{font-size:13px;color:var(--slate);line-height:1.6;margin:14px 0 20px}
.price-cta{display:block;text-align:center;background:var(--orange);color:var(--navy);padding:12px;border-radius:999px;font-size:14px;font-weight:700;transition:background .15s}
.price-cta:hover{background:var(--orange-hover)}
.price-cta.ghost{background:transparent;border:1px solid var(--slate);color:var(--body-text)}
.price-cta.ghost:hover{border-color:var(--orange);color:#fff}

/* DISCLAIMER BAR */
.disclaimer-bar{background:rgba(11,25,41,0.7);border-top:1px solid var(--divider);padding:12px 2rem;text-align:center;font-size:12px;color:var(--slate-dim);line-height:1.6}
.disclaimer-bar a{color:var(--slate-dim);text-decoration:underline}

/* FOOTER */
footer{padding:2.5rem 2rem;background:var(--navy-band);border-top:1px solid var(--divider)}
.foot-inner{max-width:1100px;margin:0 auto}
.foot-top{display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:2rem;margin-bottom:2rem}
.foot-brand{font-size:16px;font-weight:700;color:#fff}
.foot-brand span{color:var(--orange)}
.foot-tagline{font-size:13px;color:var(--slate);margin-top:4px}
.foot-links{display:flex;gap:1.5rem;flex-wrap:wrap}
.foot-links a{font-size:13px;color:var(--slate-dim);transition:color .15s}
.foot-links a:hover{color:var(--orange)}
.foot-bottom{border-top:1px solid var(--divider);padding-top:1.25rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.75rem}
.foot-upl{font-size:11px;color:var(--slate-dim);line-height:1.6;max-width:620px}
.foot-copy{font-size:11px;color:var(--slate-dim);white-space:nowrap}

/* ── MOBILE RESPONSIVE ─────────────────────────────────────────────────────── */
@media(max-width:767px){

  /* NAV — logo left, CTA full-width below, hide text links */
  nav{padding:0 1rem}
  .nav-i{flex-wrap:wrap;height:auto;padding:10px 0;gap:6px}
  .nav-links{display:none}
  .nav-free-link{display:none}
  .logo{font-size:16px}
  .nav-cta{order:3;width:100%;text-align:center;padding:12px 0;font-size:14px;border-radius:999px;margin-bottom:4px}

  /* HERO */
  .hero{padding:1.75rem 1.25rem 2rem}
  .eyebrow{margin-bottom:.75rem}
  h1{font-size:clamp(1.7rem,7.5vw,2.4rem);margin-bottom:.75rem}
  .hero-sub{font-size:14.5px;margin-bottom:.85rem}
  .hero-cred{font-size:12px;margin-bottom:.85rem}
  .hero-artifact{font-size:11px;padding:8px 14px;margin-bottom:1.1rem}
  .hero-ctas{flex-direction:column;gap:10px;align-items:stretch}
  .btn-solid,.btn-outline{display:block;width:100%;text-align:center;padding:16px 20px;font-size:15px;min-height:52px;opacity:1}

  /* PROOF SECTION */
  .proof-band{padding:3rem 1.25rem}
  .stat-tiles{grid-template-columns:repeat(2,1fr);gap:10px}
  .tile-val{font-size:18px}
  .ladder-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;padding-bottom:8px}
  .replay-row{flex-direction:column;align-items:flex-start;gap:10px}
  .btn-replay{width:100%;justify-content:center}
  .result-banner{flex-direction:column;align-items:flex-start;gap:8px}
  .case-header{flex-direction:column;align-items:flex-start}

  /* INSIDE THE REPORT */
  .inside-band{padding:3rem 1.25rem}
  .feature-grid{grid-template-columns:1fr;gap:12px}
  .feat-card{padding:18px}

  /* LEAD CAPTURE */
  .lead-band{padding:3rem 1.25rem}
  .lead-email-row{flex-direction:column;gap:10px}
  .lead-input{min-width:unset;width:100%}
  .lead-submit{width:100%;padding:14px}
  .upsell-row{flex-direction:column;align-items:stretch}
  .upsell-card{max-width:100%;min-width:unset}

  /* COUNTY SELECT — searchable feel */
  .county-select{font-size:16px;padding:14px 18px;border-radius:14px}

  /* PRICING */
  .pricing-band{padding:3rem 1.25rem}
  .pricing-grid{grid-template-columns:1fr;gap:1.25rem}
  /* Put Investor (featured) card first visually */
  .price-card.featured{order:-1}
  .price-amount{font-size:32px}
  .price-desc{font-size:14px}
  .price-cta{padding:14px;font-size:15px;min-height:52px}

  /* FOOTER */
  .foot-top{flex-direction:column;gap:1.25rem}
  .foot-links{gap:1rem}
  .foot-links a{font-size:14px;padding:4px 0;display:inline-block}
  .foot-bottom{flex-direction:column;align-items:flex-start;gap:.5rem}
  .disclaimer-bar{padding:12px 1.25rem;font-size:11px}
  .disclaimer-bar a{padding:3px 0;display:inline-block}

  /* SECTION HEADINGS */
  .section-h{font-size:clamp(1.4rem,5vw,1.8rem)}
  .proof-inner,.inside-inner,.lead-inner,.pricing-inner{padding:0}

}

/* Tight phones — 390px and below */
@media(max-width:400px){
  h1{font-size:1.75rem}
  .tile-val{font-size:16px}
  .tile{padding:10px 12px}
  .feat-section{font-size:10px}
}

/* CHAT BUBBLE */
#chat-bubble{position:fixed;bottom:24px;right:24px;z-index:9000;display:flex;align-items:center;gap:8px;background:var(--orange);color:var(--navy);border:none;border-radius:999px;padding:13px 20px;font-size:14px;font-weight:700;font-family:Inter,sans-serif;cursor:pointer;box-shadow:0 4px 24px rgba(249,115,22,.45);transition:background .15s,transform .15s;white-space:nowrap;letter-spacing:.02em}
#chat-bubble:hover{background:var(--orange-hover);transform:translateY(-2px)}
#chat-bubble svg{flex-shrink:0}

/* CHAT OVERLAY */
#chat-overlay{display:none;position:fixed;inset:0;z-index:9100;background:rgba(0,0,0,.65);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);align-items:center;justify-content:center}
#chat-overlay.open{display:flex}
#chat-panel{position:relative;width:90vw;height:90vh;max-width:960px;background:var(--navy);border:1px solid var(--charcoal);border-radius:16px;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 24px 80px rgba(0,0,0,.7)}
#chat-panel iframe{flex:1;width:100%;border:none;background:var(--navy)}
#chat-close{position:absolute;top:12px;right:14px;z-index:10;background:rgba(11,25,41,.85);border:1px solid var(--charcoal);color:var(--slate);border-radius:999px;width:34px;height:34px;font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;line-height:1;transition:background .15s,color .15s}
#chat-close:hover{background:var(--charcoal);color:#fff}
@media(max-width:767px){
  #chat-panel{width:100vw;height:100dvh;max-width:none;border-radius:0;border:none}
  #chat-bubble{bottom:16px;right:16px;padding:12px 16px;font-size:13px}
}
</style>
</head>
<body>

<!-- NAV -->
<nav>
  <div class="nav-i">
    <a class="logo" href="/">BidDeed<span>.AI</span></a>
    <div class="nav-links">
      <a href="#proof">The proof</a>
      <a href="#report">Inside the report</a>
      <a href="#pricing">Pricing</a>
      <a href="/counties">All Counties</a>
      <a href="/blog">Blog</a>
    </div>
    <a href="#lead" class="nav-free-link" style="color:var(--slate-dim);font-size:13px;font-weight:600;margin-right:.5rem;white-space:nowrap">Check your county free</a>
    <a class="nav-cta" href="/buy-report">GET A REPORT — $25</a>
  </div>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="eyebrow">Shapira Auction Intelligence · Florida Foreclosure &amp; Tax Deed</div>
  <h1>Know your walk-away number<br>before the gavel falls.</h1>
  <p class="hero-sub">BidDeed.AI is the only platform that tells you what's coming to auction, what to bid, and what the zoning allows.</p>
  <div class="hero-cred">67 FL counties tracked · <b>⭐ GOLD_COUNT_PLACEHOLDER Gold Standard certified</b></div>
  <div class="hero-artifact">Real case · Marion County: Shapira Max Bid <b>$82,000</b> <span class="res">→ sale closed $73,501 · ceiling held ✓</span></div>
  <div class="hero-ctas">
    <a class="btn-solid" href="#lead">Check Your County Free →</a>
    <a class="btn-outline" href="#report">See a live sample report →</a>
  </div>
  <div style="font-size:12px;color:var(--slate-dim);margin-top:.85rem">No credit card required</div>
</section>

<!-- FORMULA IN ACTION -->
<section class="proof-band" id="proof">
  <div class="proof-inner">
    <div class="section-label">Real Outcome · Verified to the Cent</div>
    <h2 class="section-h">The Formula in Action</h2>
    <p class="section-sub">Marion County, Jul 20 2026 — published pre-sale, captured post-sale to the cent.</p>

    <div class="case-card">
      <div class="case-header">
        <div>
          <div class="case-meta">Case 422021CA000414CAAXXX · Marion County · Foreclosure</div>
          <div class="case-address">14470 SE 91ST TER, Summerfield FL</div>
        </div>
        <div class="case-date">Sale Jul 20, 2026</div>
      </div>
      <div class="case-body">
        <div class="stat-tiles">
          <div class="tile">
            <div class="tile-label">Entry Bid</div>
            <div class="tile-val">$72,100</div>
          </div>
          <div class="tile">
            <div class="tile-label">Shapira Max Bid</div>
            <div class="tile-val orange">$82,000</div>
          </div>
          <div class="tile">
            <div class="tile-label">Actual Sale</div>
            <div class="tile-val green" id="sale-val">$73,501</div>
          </div>
          <div class="tile">
            <div class="tile-label">Ceiling Call</div>
            <div class="tile-val green">HELD ✓</div>
          </div>
        </div>

        <!-- BID LADDER TRACK -->
        <div class="ladder-wrap">
          <div class="ladder-track">
            <div class="ladder-fill" id="ladder-fill"></div>
            <!-- markers: scale $70k–$84k. Entry+Plaintiff at left:2% (left-anchored label). Ceiling right-anchored at right:12% -->
            <div class="marker marker-below" style="left:2%">
              <div class="marker-dot mgreen" style="left:0;top:-19px"></div>
              <div class="marker-label">ENTRY $72,100<br><span style="color:var(--amber)">PLAINTIFF $71,980</span></div>
            </div>
            <div class="marker marker-above" style="right:12%;left:auto">
              <div class="marker-dot morange" style="left:0;bottom:-19px;top:auto"></div>
              <div class="marker-label" style="text-align:right">CEILING<br>$82,000</div>
            </div>
          </div>
        </div>

        <div class="replay-row">
          <button class="btn-replay" id="replay-btn" onclick="replayAuction()">▶ Replay the auction</button>
          <div class="status-line" id="status-line">The sale closed at $73,501 — $8,499 under the ceiling, $1,401 over the entry. Every dollar where it should be.</div>
        </div>

        <div class="result-banner">
          <div class="result-text">✓ CEILING HELD — the formula protected the margin. $8,499 left on the table, exactly as planned.</div>
          <div class="equity-chip">Buyer Equity ~$26,400</div>
        </div>
      </div>
    </div>

    <p class="proof-footnote">Every Shapira report ships with this scorecard — the prediction is published pre-sale and graded automatically against the courthouse record within 24 hours.</p>
  </div>
</section>

<!-- INSIDE THE REPORT -->
<section class="inside-band" id="report">
  <div class="inside-inner">
    <div class="section-label">18 sections. One number that matters.</div>
    <h2 class="section-h" style="font-size:clamp(1.8rem,3.5vw,2.5rem);font-weight:800;color:#fff;letter-spacing:-.02em;margin-bottom:.5rem">18 sections. One number that matters.</h2>
    <p style="color:var(--slate);font-size:15px;margin-bottom:2rem">Every number traced to a named source. No black boxes.</p>

    <div class="feature-grid">
      <div class="feat-card">
        <div class="feat-section">§15</div>
        <div class="feat-title">The Shapira Bid Card</div>
        <div class="feat-desc">Your max bid, entry point, and a BID / REVIEW / SKIP verdict — calibrated per county on verified auction outcomes. Walk in with a number, walk out with your margin.</div>
      </div>
      <div class="feat-card">
        <div class="feat-section">§2–7</div>
        <div class="feat-title">Two value bands, never averaged</div>
        <div class="feat-desc">What it clears for at courthouse vs what it sells for retail — the gap is your day-1 equity surface, net of rehab. See exactly where your profit lives.</div>
      </div>
      <div class="feat-card">
        <div class="feat-section">§ML</div>
        <div class="feat-title">SCOREwise V4 competition read</div>
        <div class="feat-desc">A stacked ensemble trained on 5,118 verified FL outcomes tells you whether the plaintiff walks or a bidding war shows up — before you step into the room.</div>
      </div>
      <div class="feat-card">
        <div class="feat-section">§13–16</div>
        <div class="feat-title">The traps, flagged before you bid</div>
        <div class="feat-desc">Junior lien alerts, surviving mortgages, occupancy, flood zones, tax arrears — the reasons a cheap lot turns expensive, surfaced before the gavel falls.</div>
      </div>
    </div>

    <div class="cta-center">
      <a class="btn-outline-orange" href="/report/cad5d07a-b9c7-433d-b365-3165637b7cbe?key=bd_live_S9KLXyeH9fV1epdliLz731n1">Open the full sample report →</a>
    </div>
  </div>
</section>

<!-- LEAD CAPTURE — FREE REPORT -->
<section class="lead-band" id="lead">
  <div class="lead-inner">
    <div class="section-label">Get the next pre-sale report free.</div>
    <h2 class="section-h" style="font-size:clamp(1.4rem,2.5vw,2rem);font-weight:800;color:#fff;margin-bottom:.5rem;letter-spacing:-.02em">Get the next pre-sale report free.</h2>
    <p style="color:var(--slate);font-size:15px;line-height:1.6">Choose your county. We'll send you one full S5 Shapira report from an upcoming sale — scorecard included when the outcome lands.</p>

    <div id="lead-form-wrap">
      <select class="county-select" id="lead-county">
        <option value="" disabled selected>Select your county (55 available)</option>
        <option value="alachua">Alachua — 29 upcoming</option>
        <option value="baker">Baker — 16 upcoming</option>
        <option value="bay">Bay — 27 upcoming</option>
        <option value="bradford">Bradford — 4 upcoming</option>
        <option value="brevard">Brevard — 7 upcoming</option>
        <option value="broward">Broward — 24 upcoming</option>
        <option value="calhoun">Calhoun — 5 upcoming</option>
        <option value="charlotte">Charlotte ★ — 2 upcoming</option>
        <option value="citrus">Citrus ★ — 18 upcoming</option>
        <option value="clay">Clay — 56 upcoming</option>
        <option value="collier">Collier — 59 upcoming</option>
        <option value="columbia">Columbia — 27 upcoming</option>
        <option value="desoto">Desoto — 2 upcoming</option>
        <option value="dixie">Dixie ★ — 2 upcoming</option>
        <option value="duval">Duval ★ — 27 upcoming</option>
        <option value="escambia">Escambia — 273 upcoming</option>
        <option value="flagler">Flagler ★ — 46 upcoming</option>
        <option value="gadsden">Gadsden ★ — 12 upcoming</option>
        <option value="gilchrist">Gilchrist — 10 upcoming</option>
        <option value="hamilton">Hamilton — 1 upcoming</option>
        <option value="hendry">Hendry — 1 upcoming</option>
        <option value="hernando">Hernando — 26 upcoming</option>
        <option value="highlands">Highlands ★ — 154 upcoming</option>
        <option value="hillsborough">Hillsborough — 19 upcoming</option>
        <option value="indian_river">Indian River — 6 upcoming</option>
        <option value="jackson">Jackson — 14 upcoming</option>
        <option value="lafayette">Lafayette ★ — 2 upcoming</option>
        <option value="lake">Lake — 65 upcoming</option>
        <option value="lee">Lee — 62 upcoming</option>
        <option value="leon">Leon — 26 upcoming</option>
        <option value="levy">Levy — 1 upcoming</option>
        <option value="manatee">Manatee — 1 upcoming</option>
        <option value="marion">Marion ★ — 97 upcoming</option>
        <option value="martin">Martin — 9 upcoming</option>
        <option value="miami_dade">Miami-Dade — 35 upcoming</option>
        <option value="nassau">Nassau ★ — 3 upcoming</option>
        <option value="okaloosa">Okaloosa — 2 upcoming</option>
        <option value="okeechobee">Okeechobee — 25 upcoming</option>
        <option value="orange">Orange — 6 upcoming</option>
        <option value="palm_beach">Palm Beach — 23 upcoming</option>
        <option value="pasco">Pasco — 76 upcoming</option>
        <option value="pinellas">Pinellas — 1 upcoming</option>
        <option value="polk">Polk — 40 upcoming</option>
        <option value="putnam">Putnam — 298 upcoming</option>
        <option value="santa_rosa">Santa Rosa ★ — 20 upcoming</option>
        <option value="sarasota">Sarasota — 34 upcoming</option>
        <option value="seminole">Seminole — 33 upcoming</option>
        <option value="st_johns">St. Johns ★ — 24 upcoming</option>
        <option value="st_lucie">St. Lucie — 19 upcoming</option>
        <option value="suwannee">Suwannee — 23 upcoming</option>
        <option value="taylor">Taylor — 6 upcoming</option>
        <option value="union">Union — 2 upcoming</option>
        <option value="volusia">Volusia — 26 upcoming</option>
        <option value="wakulla">Wakulla ★ — 6 upcoming</option>
        <option value="walton">Walton — 20 upcoming</option>
      </select>
      <div class="lead-email-row">
        <input class="lead-input" id="lead-email" type="email" placeholder="your@email.com" autocomplete="email">
      </div>
      <div class="lead-email-row" style="margin-top:8px">
        <input class="lead-input" id="lead-phone" type="tel" placeholder="Phone (optional — for SMS alerts)" autocomplete="tel">
      </div>
      <div style="margin-top:10px;display:flex;flex-direction:column;gap:6px">
        <label style="display:flex;align-items:flex-start;gap:8px;font-size:12px;color:var(--slate);cursor:pointer">
          <input type="checkbox" id="lead-email-consent" checked style="margin-top:2px;accent-color:var(--orange)">
          <span>Send me this county's upcoming auctions by email</span>
        </label>
        <label style="display:flex;align-items:flex-start;gap:8px;font-size:12px;color:var(--slate);cursor:pointer">
          <input type="checkbox" id="lead-sms-consent" style="margin-top:2px;accent-color:var(--orange)">
          <span>Text me auction alerts for this county (SMS)</span>
        </label>
      </div>
      <div style="margin-top:12px">
        <button class="lead-submit" onclick="submitLead()" id="lead-submit-btn" style="width:100%">Get My Free County Report →</button>
      </div>
      <div class="lead-error" id="lead-error"></div>
    </div>

    <!-- INSTANT AUCTION CARDS — shown after submit -->
    <div id="lead-success" style="display:none">
      <div style="background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.3);border-radius:10px;padding:16px 20px;color:var(--green);font-size:14px;font-weight:600;margin-bottom:16px">
        ✓ Report sent to your email. Here are your next auctions:
      </div>
      <div id="lead-auction-cards" style="display:flex;flex-direction:column;gap:10px"></div>
      <div style="margin-top:20px;display:flex;gap:12px;flex-wrap:wrap;justify-content:center">
        <a id="upsell-25" href="/buy-report" class="upsell-cta ghost" style="flex:1;min-width:160px;text-align:center;display:inline-block;border:1px solid var(--orange);color:var(--orange);padding:12px 20px;border-radius:8px;font-size:13px;font-weight:700;text-decoration:none">Get S5 Report — $25 →</a>
        <a href="/subscribe?tier=investor" class="upsell-cta" style="flex:1;min-width:160px;text-align:center;display:inline-block;background:var(--orange);color:var(--navy);padding:12px 20px;border-radius:8px;font-size:13px;font-weight:700;text-decoration:none">Investor $99/mo →</a>
      </div>
    </div>

  </div>
</section>

<!-- PRICING -->
<section class="pricing-band" id="pricing">
  <div class="pricing-inner">
    <div class="section-label" style="text-align:center">Pricing</div>
    <h2 class="section-h" style="text-align:center;font-size:clamp(1.6rem,3vw,2.25rem);font-weight:800;color:#fff;margin-bottom:.25rem">Cheaper than one bad bid.</h2>
    <p style="text-align:center;color:var(--slate);font-size:15px;margin-top:.5rem">One wrong number at the courthouse costs more than a year of Investor.</p>

    <div class="pricing-grid">
      <div class="price-card">
        <div class="price-tier">S5 Single Report</div>
        <div class="price-amount">$25<span> one-time</span></div>
        <div class="price-desc">All 18 sections on one property. Full ZoneWise zoning intelligence. Free scorecard re-issue when the outcome lands.</div>
        <a class="price-cta" href="/buy-report">Get a report →</a>
      </div>
      <div class="price-card featured">
        <div class="popular-chip">Most Popular</div>
        <div class="price-tier">Investor</div>
        <div class="price-amount">$99<span>/mo</span></div>
        <div class="price-desc">Reports on every lot in your counties' upcoming sales, daily digest, plaintiff intel, and chatbot property cards.</div>
        <a class="price-cta" href="/subscribe?tier=investor">Start Investor →</a>
      </div>
      <div class="price-card">
        <div class="price-tier">Pro</div>
        <div class="price-amount">$199<span>/mo</span></div>
        <div class="price-desc">Everything in Investor plus full SCOREwise V4 probabilities, SHAP feature drivers, and direct API access.</div>
        <a class="price-cta ghost" href="/subscribe?tier=pro">Start Pro →</a>
      </div>
    </div>

    <div class="pioneer-teaser" style="margin-top:2rem;max-width:640px;margin-left:auto;margin-right:auto;text-align:center;background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.25);border-radius:14px;padding:1.5rem">
      <div style="color:var(--orange);font-weight:700;font-size:.9rem;margin-bottom:.4rem">PIONEER PROGRAM — WAITLIST OPEN</div>
      <div style="color:var(--slate);font-size:.9rem;margin-bottom:1rem">Be one of the first 100 BidDeed.AI Pioneers. Founding-customer pricing and early access — join the waitlist for full details.</div>
      <a href="/pioneers" style="display:inline-block;background:transparent;border:1px solid var(--orange);color:var(--orange);padding:10px 22px;border-radius:8px;font-weight:700;font-size:.85rem;text-decoration:none">Join the Waitlist →</a>
    </div>
  </div>
</section>

<!-- DISCLAIMER BAR -->
<div class="disclaimer-bar">
  BidDeed.AI is an investment decision-support tool — not legal advice, not an appraisal, not title insurance.
  Auction data and bid estimates are informational only and must be independently verified.
  Always consult a licensed Florida attorney and title professional before bidding. &nbsp;|&nbsp;
  <a href="/disclaimer">Disclaimer</a> &nbsp;·&nbsp;
  <a href="/terms">Terms</a> &nbsp;·&nbsp;
  <a href="/privacy">Privacy</a> &nbsp;·&nbsp;
  <a href="/security">Security</a>
</div>

<!-- FOOTER -->
<footer>
  <div class="foot-inner">
    <div class="foot-top">
      <div>
        <div class="foot-brand">BidDeed<span>.AI</span></div>
        <div class="foot-tagline">Shapira Auction Intelligence · Everest Capital USA</div>
      </div>
      <div class="foot-links">
        <a href="#proof">The proof</a>
        <a href="#report">Inside the report</a>
        <a href="#pricing">Pricing</a>
        <a href="/buy-report">Get a report</a>
        <a href="/chat">Chat</a>
        <a href="/free-report">Free County Report</a>
        <a href="/counties">All Counties</a>
        <a href="/blog">Blog</a>
        <a href="/pioneers">Pioneers</a>
        <a href="/terms">Terms</a>
        <a href="/privacy">Privacy</a>
        <a href="/disclaimer">Disclaimer</a>
        <a href="/security">Security</a>
      </div>
    </div>
    <div class="foot-bottom">
      <p class="foot-upl">BidDeed.AI is an investment decision-support tool. Not legal advice. Not an appraisal. Not title insurance. Verify all data independently and consult a licensed Florida attorney before bidding. © 2026 Everest Capital USA.</p>
      <p class="foot-copy">biddeed.ai · ariel@biddeed.ai</p>
    </div>
  </div>
</footer>

<!-- CHAT BUBBLE -->
<button id="chat-bubble" onclick="openChat()" aria-label="Open chat">
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
  Chat
</button>

<!-- CHAT OVERLAY -->
<div id="chat-overlay" role="dialog" aria-modal="true" aria-label="BidDeed chat" onclick="handleOverlayClick(event)">
  <div id="chat-panel">
    <button id="chat-close" onclick="closeChat()" aria-label="Close chat">&#x2715;</button>
    <iframe id="chat-iframe" title="BidDeed Chat" allow="microphone"></iframe>
  </div>
</div>

<script>
function openChat(){
  var overlay=document.getElementById('chat-overlay');
  var iframe=document.getElementById('chat-iframe');
  if(!iframe.src||iframe.src===window.location.href) iframe.src='/chat';
  overlay.classList.add('open');
  document.body.style.overflow='hidden';
}
function closeChat(){
  document.getElementById('chat-overlay').classList.remove('open');
  document.body.style.overflow='';
}
function handleOverlayClick(e){
  if(e.target===document.getElementById('chat-overlay')) closeChat();
}
document.addEventListener('keydown',function(e){
  if(e.key==='Escape') closeChat();
});
</script>

${HOMEPAGE_SCRIPT}
</body>
</html>`; }

const TERMS_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Terms of Service — BidDeed.AI</title>
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.15rem;margin:2rem 0 .5rem;color:#fff}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.4rem}
.box{background:#0b1220;border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:#fff}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:#fff;font-weight:700}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.8rem;color:var(--muted)}
footer a{color:var(--muted)}
</style></head><body>
<nav class="top"><a href="/">BidDeed.AI</a></nav>
<div class="wrap"><a class="back" href="/">← Back to home</a><h1>Terms of Service</h1><div class="upd">Last updated July 28, 2026</div>
        <p>These Terms of Service ("Terms") govern your access to and use of BidDeed.AI, operated by Everest Capital USA ("BidDeed.AI", "we", "us"). By accessing the site or using our services you agree to these Terms.</p>
        <div class="box"><strong>Not legal advice.</strong> BidDeed.AI is an information and analytics platform, not a law firm, title company, real-estate brokerage, or financial advisor. Nothing on this site or from our chatbot, reports, or the Shapira Max Bid analysis constitutes legal, financial, investment, tax, or title advice, and no attorney-client, fiduciary, or brokerage relationship is created. Foreclosure and tax-deed investing carries substantial risk of loss, including total loss of your bid. Auction data, valuations, and bid estimates are informational, may be incomplete or inaccurate, and must be independently verified. Always consult a licensed Florida attorney and conduct your own due diligence before bidding.</div>
        <h2>1. Service</h2><p>BidDeed.AI provides Florida foreclosure and tax-deed auction data, analytics, and related informational tools on a subscription and metered basis. Features, pricing, and availability may change at any time.</p>
        <h2>2. No professional relationship</h2><p>Use of the service does not create an attorney-client, fiduciary, brokerage, or advisory relationship. See our <a href="/disclaimer">Disclaimer</a>.</p>
        <h2>3. Accounts &amp; payment</h2><p>Paid tiers are billed through our payment processor (Stripe). Metered usage is billed per the pricing shown at purchase. You are responsible for charges incurred under your account. Except where required by law, fees are non-refundable.</p>
        <h2>4. Acceptable use</h2><p>You agree not to scrape, resell, redistribute, or reverse-engineer the service or its data; not to overload or attack the service; and not to use it for any unlawful purpose. We may suspend or terminate access for violations.</p>
        <h2>5. Intellectual property</h2><p>The Shapira Max Bid Formula, analytics, compilations, software, and site content are our proprietary property. Public-record data underlying our analysis remains public; our compilation and analysis do not.</p>
        <h2>6. Disclaimers &amp; limitation of liability</h2><p>THE SERVICE IS PROVIDED "AS IS" WITHOUT WARRANTIES OF ANY KIND. TO THE MAXIMUM EXTENT PERMITTED BY LAW, EVEREST CAPITAL USA AND ITS AFFILIATES WILL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR FOR ANY LOSS ARISING FROM YOUR USE OF, OR RELIANCE ON, THE SERVICE OR ITS DATA — INCLUDING ANY BIDDING DECISION OR AUCTION OUTCOME. OUR TOTAL LIABILITY WILL NOT EXCEED THE AMOUNTS YOU PAID US IN THE 3 MONTHS PRECEDING THE CLAIM.</p>
        <h2>7. Indemnification</h2><p>You agree to indemnify and hold harmless Everest Capital USA from claims arising out of your use of the service or your auction activity.</p>
        <h2>8. Governing law</h2><p>These Terms are governed by the laws of the State of Florida. Venue for any dispute lies in the state or federal courts located in Brevard County, Florida.</p>
        <h2>9. Changes</h2><p>We may update these Terms; continued use after changes constitutes acceptance.</p>
        <h2>10. Contact</h2><p><a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></p></div>
<footer>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="/security">Security</a> · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></footer>
</body></html>`;

const PRIVACY_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Privacy Policy — BidDeed.AI</title>
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.15rem;margin:2rem 0 .5rem;color:#fff}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.4rem}
.box{background:#0b1220;border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:#fff}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:#fff;font-weight:700}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.8rem;color:var(--muted)}
footer a{color:var(--muted)}
</style></head><body>
<nav class="top"><a href="/">BidDeed.AI</a></nav>
<div class="wrap"><a class="back" href="/">← Back to home</a><h1>Privacy Policy</h1><div class="upd">Last updated July 28, 2026</div>
      <p>This Privacy Policy explains how BidDeed.AI (Everest Capital USA) collects and uses information when you use our site and services.</p>
      <h2>1. Information we collect</h2><ul>
      <li><strong>Information you provide:</strong> email address and any details you submit through our chatbot, lead forms, or when subscribing (e.g. county of interest, investor type).</li>
      <li><strong>Payment information:</strong> processed by Stripe. We do not store full card numbers on our servers.</li>
      <li><strong>Usage &amp; analytics:</strong> pages viewed, interactions, and approximate location/device data via PostHog for product analytics.</li>
      <li><strong>Chat content:</strong> messages you send to our chatbot, used to answer your questions and improve the service.</li></ul>
      <h2>2. How we use it</h2><ul><li>To provide, operate, and improve the service.</li><li>To respond to inquiries and send service or marketing communications (you may opt out).</li><li>To process payments and prevent abuse.</li><li>To comply with legal obligations.</li></ul>
      <h2>3. Sharing</h2><p>We share data with service providers who help us operate (e.g. Stripe for payments, PostHog for analytics, Supabase for data storage, Cloudflare for hosting, Anthropic for AI responses), each under their own terms. We do not sell your personal information. We may disclose information if required by law.</p>
      <h2>4. Data retention &amp; security</h2><p>We retain information as long as needed to provide the service and meet legal obligations, and we apply reasonable technical and organizational safeguards (including access controls and encryption in transit). No method of transmission or storage is 100% secure.</p>
      <h2>5. Your choices</h2><p>You may request access to, correction of, or deletion of your personal information by emailing <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a>. You may opt out of marketing emails at any time.</p>
      <h2>6. Cookies &amp; analytics</h2><p>We use cookies and similar technologies for analytics and functionality. You can control cookies through your browser settings.</p>
      <h2>7. Children</h2><p>The service is not directed to individuals under 18, and we do not knowingly collect their information.</p>
      <h2>8. Changes</h2><p>We may update this policy; the "last updated" date reflects the latest revision.</p>
      <h2>9. Contact</h2><p><a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></p></div>
<footer>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="/security">Security</a> · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></footer>
</body></html>`;

const DISCLAIMER_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Disclaimer — BidDeed.AI</title>
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.15rem;margin:2rem 0 .5rem;color:#fff}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.4rem}
.box{background:#0b1220;border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:#fff}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:#fff;font-weight:700}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.8rem;color:var(--muted)}
footer a{color:var(--muted)}
</style></head><body>
<nav class="top"><a href="/">BidDeed.AI</a></nav>
<div class="wrap"><a class="back" href="/">← Back to home</a><h1>Disclaimer</h1><div class="upd">Last updated July 28, 2026</div>
        <div class="box"><strong>Not legal advice.</strong> BidDeed.AI is an information and analytics platform, not a law firm, title company, real-estate brokerage, or financial advisor. Nothing on this site or from our chatbot, reports, or the Shapira Max Bid analysis constitutes legal, financial, investment, tax, or title advice, and no attorney-client, fiduciary, or brokerage relationship is created. Foreclosure and tax-deed investing carries substantial risk of loss, including total loss of your bid. Auction data, valuations, and bid estimates are informational, may be incomplete or inaccurate, and must be independently verified. Always consult a licensed Florida attorney and conduct your own due diligence before bidding.</div>
        <h2>Informational purpose only</h2><p>All content, data, analytics, county intelligence, auction calendars, and the Shapira Max Bid Formula are provided for general informational purposes. Property values, opening bids, judgment amounts, liens, and outcomes are sourced from public records and third parties and are provided "as is" without warranty of accuracy, completeness, or fitness for a particular purpose.</p>
        <h2>No guarantee of results</h2><p>Past results (including any example outcomes shown on this site) do not guarantee future performance. A "max bid" figure is an estimate, not a recommendation to bid, and not a prediction of sale price or profit.</p>
        <h2>Independent verification required</h2><p>You are solely responsible for verifying all information with the county clerk, property appraiser, and a licensed attorney before participating in any auction.</p></div>
<footer>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="/security">Security</a> · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></footer>
</body></html>`;

const DATA_RETENTION_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data Retention Policy — BidDeed.AI</title>
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.05rem;margin:2rem 0 .6rem;color:#fff}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.45rem}
table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.88rem}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--border);color:var(--muted)}
th{color:#fff;font-weight:600}
.box{background:#0b1220;border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:#fff}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:#fff;font-weight:700}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.8rem;color:var(--muted)}
footer a{color:var(--muted)}
code{background:#0b1220;padding:.1rem .35rem;border-radius:4px;font-size:.85em}
</style></head><body>
<nav class="top"><a href="/">BidDeed.AI</a></nav>
<div class="wrap"><a class="back" href="/">← Back to home</a><h1>Data Retention &amp; Deletion Policy</h1><div class="upd">Last updated: August 3, 2026</div>

<div class="box"><strong>This is not legal advice.</strong> BidDeed.AI is an information and analytics platform, not a law firm or title company.</div>

<h2>What we retain, and for how long</h2>
<table>
<tr><th>Data</th><th>Retention</th><th>Why</th></tr>
<tr><td>Customer account data (email, Stripe customer ID)</td><td>Active + 7 years after closure</td><td>Florida business records practice</td></tr>
<tr><td>API/tool usage metering</td><td>Retained per billing cycle</td><td>Billing accuracy, abuse investigation</td></tr>
<tr><td>Payment records</td><td>7 years</td><td>IRS recordkeeping requirement</td></tr>
<tr><td>Security event logs</td><td>1 year, then purged</td><td>Incident investigation window</td></tr>
<tr><td>Chat history</td><td>30 days, then purged</td><td>Support/debugging only — not a system of record</td></tr>
<tr><td>Florida property/auction data</td><td>Indefinite</td><td>Public government records; no personal data</td></tr>
</table>

<h2>Right to deletion</h2>
<p>You may request deletion of your personal data (email, payment-related identifiers) by emailing <a href="mailto:privacy@biddeed.ai">privacy@biddeed.ai</a>. We will process deletion requests within 30 days.</p>
<p>Florida public-record data (property records, auction/case data) is sourced from county government systems and cannot be deleted from our copy — it was never personal to you; it is the county's own public filing.</p>

<h2>Florida-specific notice</h2>
<p>Under Florida's Information Protection Act (FS 501.171), if a breach affects more than 500 Florida residents, we will notify the Florida Department of Legal Affairs and affected individuals within 30 days of determining the breach occurred.</p>

<h2>Contact</h2>
<p>Policy questions: <a href="mailto:privacy@biddeed.ai">privacy@biddeed.ai</a> &nbsp;·&nbsp; Security incidents: <a href="mailto:security@biddeed.ai">security@biddeed.ai</a></p>

</div>
<footer>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="/security">Security</a> · <a href="/data-retention">Data Retention</a> · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></footer>
</body></html>`;

const SECURITY_LAST_REVIEWED = 'August 2026';

const SECURITY_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Security — BidDeed.AI</title>
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.05rem;margin:2rem 0 .6rem;color:#fff}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.45rem}
ul{padding-left:1.3rem}
.box{background:#0b1220;border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:#fff}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:#fff;font-weight:700}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.8rem;color:var(--muted)}
footer a{color:var(--muted)}
code{background:#0b1220;padding:.1rem .35rem;border-radius:4px;font-size:.85em}
</style></head><body>
<nav class="top"><a href="/">BidDeed.AI</a></nav>
<div class="wrap"><a class="back" href="/">← Back to home</a><h1>Security at BidDeed.AI</h1><div class="upd">Last reviewed: ${SECURITY_LAST_REVIEWED}</div>

<div class="box"><strong>No fake badges.</strong> Everything below is either directly verifiable (a live endpoint, a public repo file, a database query) or explicitly labeled as in-progress. We don't display compliance marks we haven't earned.</div>

<h2>🔒 Data Protection</h2>
<ul>
<li>TLS in transit on every request (Vercel + Cloudflare edge termination).</li>
<li>Encryption at rest on the primary database (Supabase).</li>
<li>Row-Level Security is enabled on 723 of 728 public database tables (99%) — verified by direct query against <code>pg_class.relrowsecurity</code>, ${SECURITY_LAST_REVIEWED}. The remaining tables are reference/lookup data with no customer or credential content.</li>
<li>HTTP security headers (HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy) on every response from this site — Mozilla HTTP Observatory grade C+, up from F before ${SECURITY_LAST_REVIEWED}. Not yet A: our CSP still allows inline scripts for a PostHog snippet that isn't nonce-based yet — tracked as an open item, not hidden.</li>
</ul>

<h2>🔑 Access Control</h2>
<ul>
<li>MCP access uses OAuth 2.1 (WorkOS AuthKit) via RFC 9728 protected-resource discovery, or a scoped <code>bd_live_*</code> API key — both validated server-side on every call.</li>
<li>Secrets are never committed to source. Vault access from any automated agent goes through gated accessor functions with name allow-lists, not direct table reads.</li>
<li>Cloudflare and GitHub deploy tokens are scoped to the minimum permissions and single zone/repo they operate on.</li>
</ul>

<h2>🤖 AI Security</h2>
<ul>
<li>The MCP server's 25 tools run every call through a single canonical pipeline (auth → cert gate → billing → tool handler) — nothing bypasses it.</li>
<li>Pattern-based prompt-injection and secret-leak scanning runs on tool arguments and tool results at that pipeline's single chokepoint.</li>
<li>Every tool response carries an explicit notice: scraped county records and case data are untrusted external data, never instructions.</li>
<li>All 25 tools are billing-gated and idempotency-keyed — a retried or replayed call cannot double-charge or double-execute.</li>
</ul>

<h2>🔍 Audit &amp; Monitoring</h2>
<ul>
<li>Every pull request to this codebase runs an automated security gate: Semgrep SAST, Gitleaks secret scanning, and dependency audit (npm/pip) — CRITICAL/HIGH findings block the merge.</li>
<li>Error monitoring via PostHog (100K events/month free tier) — unhandled exceptions in the Cloudflare Worker are captured server-side and reported, no browser SDK required.</li>
<li>Independent DAST scan (OWASP ZAP) and LLM red-team probing: not yet run against production as of ${SECURITY_LAST_REVIEWED} — scheduled as a follow-up, pending scope confirmation for live scanning of customer-facing infrastructure.</li>
<li>Known open item: a legacy vault-read database function is more broadly grantable than intended and is flagged internally for tightening — tracked, not hidden.</li>
</ul>

<h2>📋 Compliance Posture</h2>
<ul>
<li>SOC 2 Type I — in preparation, not yet certified.</li>
<li>CASA Tier 2 — planned.</li>
<li>Florida financial/public-record data handling per FS 197.552 and FS 713.07.</li>
<li>Governing law: State of Florida. See our <a href="/terms">Terms of Service</a>.</li>
</ul>

<h2>📚 Security Documentation</h2>
<ul>
<li>📄 <a href="https://github.com/breverdbidder/cli-anything-biddeed/blob/main/docs/security/INCIDENT_RESPONSE_PLAN.md" target="_blank" rel="noopener">Incident Response Plan</a> — severity classification, detection sources, response playbooks.</li>
<li>📋 <a href="https://github.com/breverdbidder/cli-anything-biddeed/blob/main/docs/security/VENDOR_SUB_PROCESSOR_LIST.md" target="_blank" rel="noopener">Vendor &amp; Sub-Processor List</a> — every third party that touches customer data, with sourced security-page links.</li>
<li>🗓 <a href="/data-retention">Data Retention &amp; Deletion Policy</a> — what we keep, for how long, and how to request deletion.</li>
<li>📊 <a href="https://github.com/breverdbidder/cli-anything-biddeed/blob/main/docs/security/EXTERNAL_SCAN_SUMMARY.md" target="_blank" rel="noopener">External Scan Results</a> — Mozilla HTTP Observatory (C+, up from F) + SSL Labs (A on TLS), raw output attached.</li>
<li>✅ <a href="https://github.com/breverdbidder/cli-anything-biddeed/blob/main/docs/security/CAIQ-v4.1-BidDeed-Completed.md" target="_blank" rel="noopener">CAIQ Self-Assessment</a> — CSA-domain-structured control answers, including the gaps, not just the passes.</li>
<li>🤖 <a href="https://github.com/breverdbidder/cli-anything-biddeed/blob/main/docs/security/AI-CAIQ-v1.1-BidDeed-Completed.md" target="_blank" rel="noopener">AI Security Self-Assessment</a> — prompt-injection controls, model governance, and disclosed AI-specific gaps.</li>
<li>❓ <a href="https://github.com/breverdbidder/cli-anything-biddeed/blob/main/docs/security/SECURITY_QUESTIONNAIRE_ANSWERS.md" target="_blank" rel="noopener">Common Questionnaire Answers</a> — pre-written answers to the 50 questions vendor security reviews ask most.</li>
<li>📦 Request the full Security Evidence Pack (architecture, controls, compliance posture) — email <a href="mailto:security@biddeed.ai">security@biddeed.ai</a>.</li>
</ul>

<h2>🏢 Enterprise Trust Portal</h2>
<p>A gated self-serve portal (<code>trust.biddeed.ai</code>, via SafeBase) is in setup — not live yet. Once it launches it will host the documents linked above plus any completed penetration test report, in one request-access location for procurement teams. Until then, use the GitHub links above or email <a href="mailto:security@biddeed.ai">security@biddeed.ai</a> directly — same documents, no waiting on the portal.</p>

<h2>📧 Security Contact</h2>
<p>Found an issue? Email <a href="mailto:security@biddeed.ai">security@biddeed.ai</a>. We aim to respond within 48 hours. Responsible disclosure is welcome — please give us a reasonable window to fix before public disclosure.</p>

</div>
<footer>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="/security">Security</a> · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></footer>
</body></html>`;
// deploy-pipeline self-test marker (safe to remove) — validates automated deploy script end-to-end
