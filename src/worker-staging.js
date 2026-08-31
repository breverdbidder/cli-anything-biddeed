/**
 * BidDeed.AI Cloudflare Worker — src/worker-staging.js
 * Worker name: worker-biddeed-staging
 * Full-featured Claude-AI style split-screen rebuild (2026-07-31)
 *
 * STANDALONE — imports nothing from src/worker.js. Additive only, zero
 * changes to production routes/tables. DEMO_MODE skips Stripe entirely;
 * all writes go to demo_ tables.
 *
 * Routes:
 *   GET  /staging                    → Split-screen chat + county/property intelligence shell
 *   GET  /staging/county-feed        → JSON top-8 counties from county_twin_snapshot
 *   GET  /staging/auctions           → JSON property cards for a county (?county=&days=&type=&limit=)
 *   POST /staging/chat/api           → Streaming SSE chat (Anthropic), BidDeed system prompt,
 *                                       county intent detection, [SHOW_COUNTY:x] → "properties" SSE event,
 *                                       optional document (PDF/image) analysis
 *   POST /staging/chat/lead          → Email capture → Supabase demo_lead_profiles
 *   GET  /staging/buy-report         → Demo $25 report checkout page (prefilled from a property card)
 *   POST /staging/buy-report/checkout → DEMO MODE: no real Stripe charge, redirects to demo-success
 *   GET  /staging/demo-success       → "Demo purchase successful" key delivery page
 *   *    /staging/*                  → 404 (anything else under /staging)
 *   *    (everything else)           → 404
 */

const DEMO_MODE = true;

// ── Constants — same values as src/worker.js ────────────────────────────────
const SUPABASE_URL = 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1MzI1MjYsImV4cCI6MjA4MDEwODUyNn0.ySFJIOngWWB0aqYra4PoGFuqcbdHOx1ZV6T9-klKQDw';
const DISCLAIMER_SHORT = 'Informational only — not legal, financial, or investment advice. Verify independently & consult a licensed attorney before bidding.';
const MAX_BODY_BYTES = 14 * 1024 * 1024; // ~14MB — covers a 10MB document upload as base64 + JSON overhead

const COUNTY_DISPLAY = {
  'brevard':'Brevard','broward':'Broward','charlotte':'Charlotte','clay':'Clay',
  'duval':'Duval','franklin':'Franklin','hardee':'Hardee','hendry':'Hendry',
  'hernando':'Hernando','highlands':'Highlands','hillsborough':'Hillsborough',
  'indian_river':'Indian River','jackson':'Jackson','lafayette':'Lafayette',
  'leon':'Leon','monroe':'Monroe','nassau':'Nassau','orange':'Orange',
  'palm_beach':'Palm Beach','pasco':'Pasco','putnam':'Putnam','st_johns':'St. Johns',
  'volusia':'Volusia','washington':'Washington','alachua':'Alachua','baker':'Baker',
  'bay':'Bay','bradford':'Bradford','calhoun':'Calhoun','citrus':'Citrus',
  'columbia':'Columbia','desoto':'DeSoto','dixie':'Dixie','escambia':'Escambia',
  'flagler':'Flagler','gadsden':'Gadsden','gilchrist':'Gilchrist','glades':'Glades',
  'gulf':'Gulf','hamilton':'Hamilton','holmes':'Holmes','jefferson':'Jefferson',
  'lake':'Lake','lee':'Lee','levy':'Levy','liberty':'Liberty','madison':'Madison',
  'manatee':'Manatee','marion':'Marion','martin':'Martin','miami_dade':'Miami-Dade',
  'okaloosa':'Okaloosa','okeechobee':'Okeechobee','osceola':'Osceola',
  'pinellas':'Pinellas','polk':'Polk','santa_rosa':'Santa Rosa','sarasota':'Sarasota',
  'seminole':'Seminole','st_lucie':'St. Lucie','sumter':'Sumter','suwannee':'Suwannee',
  'taylor':'Taylor','union':'Union','wakulla':'Wakulla','walton':'Walton',
};

function toDisplay(slug) {
  return COUNTY_DISPLAY[slug] || String(slug).replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
}
function fmtMoney(n) {
  if (n === null || n === undefined || isNaN(Number(n))) return null;
  return '$' + Math.round(Number(n)).toLocaleString('en-US');
}
function fmtDate(d) {
  if (!d) return 'TBD';
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── CORS ──────────────────────────────────────────────────────────────────
function corsHeaders(origin) {
  const allowed = ['https://staging.biddeed.ai', 'https://worker-biddeed-staging.breverdbidder.workers.dev'];
  const o = allowed.includes(origin) ? origin : allowed[0];
  return {
    'Access-Control-Allow-Origin': o,
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,apikey,x-api-key',
  };
}

// ── FL county name detection from free text (chat intent routing) ─────────
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

// ── County intelligence feed (default right-panel state) ───────────────────
async function fetchCountyFeed() {
  try {
    const url = `${SUPABASE_URL}/rest/v1/county_twin_snapshot?order=total_upcoming_30d.desc&limit=8&select=county,is_gold_standard,fc_upcoming_30d,td_upcoming_30d,fc_next_auction_date,td_next_auction_date,fc_avg_opening_bid,fc_min_opening_bid,fc_max_opening_bid,td_avg_opening_bid,td_min_opening_bid,td_max_opening_bid,total_upcoming_30d`;
    const res = await fetch(url, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } });
    if (!res.ok) return [];
    const rows = await res.json();
    return Array.isArray(rows) ? rows.slice(0, 8) : [];
  } catch(_) { return []; }
}

// ── Property/auction cards — same shape as production /auctions ────────────
// Reads v_property_card_verified (not the raw table) — same fail-closed gate
// as src/worker.js, per CLERK-SSOT Task 4.2 (issue #18647).
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
      clerk_parity_badge: {
        county: r.county,
        match_pct: r.clerk_parity_match_pct != null ? Number(r.clerk_parity_match_pct) : null,
        checked_at: r.clerk_parity_checked_at || null,
      },
    };
  });
}

// ── Language detection (first 60 chars of the user's message) ──────────────
function detectLanguage(text) {
  const sample = String(text || '').slice(0, 60);
  if (/[֐-׿]/.test(sample)) return 'Hebrew';
  if (/[一-鿿]/.test(sample)) return 'Chinese';
  if (/[Ѐ-ӿ]/.test(sample)) return 'Russian';
  if (/[؀-ۿ]/.test(sample)) return 'Arabic';
  if (/[¿¡ñÑ]/.test(sample) || /\b(hola|cómo|como|qué|que|dónde|donde|cuánto|cuanto|gracias|cuándo)\b/i.test(sample)) return 'Spanish';
  if (/\b(olá|obrigad|português|quanto custa)\b/i.test(sample)) return 'Portuguese';
  return null; // English or undetermined — model default-detects
}

// ── Anthropic message builder (adds document/image content block if present) ──
function buildAnthropicMessages(messages, document) {
  const mapped = messages.map(m => ({ role: m.role, content: String(m.content) }));
  if (document && document.data && document.media_type && mapped.length) {
    let lastUserIdx = -1;
    for (let i = mapped.length - 1; i >= 0; i--) { if (mapped[i].role === 'user') { lastUserIdx = i; break; } }
    const isPdf = document.media_type === 'application/pdf';
    const isImage = document.media_type.indexOf('image/') === 0;
    if (lastUserIdx !== -1 && (isPdf || isImage)) {
      const block = isPdf
        ? { type: 'document', source: { type: 'base64', media_type: document.media_type, data: document.data } }
        : { type: 'image', source: { type: 'base64', media_type: document.media_type, data: document.data } };
      mapped[lastUserIdx] = { role: 'user', content: [ { type: 'text', text: mapped[lastUserIdx].content }, block ] };
    }
  }
  return mapped;
}

// ── HTML: split-screen shell (40% chat / 60% intelligence feed) ────────────
function buildStagingShell() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,interactive-widget=resizes-content">
<title>BidDeed.AI — Staging</title>
<meta name="robots" content="noindex,nofollow">
<meta name="description" content="BidDeed.AI foreclosure and tax deed auction intelligence for all 67 Florida counties — Shapira Max Bid formula, live county feed, $25 SIGNAL$ Property Reports, $99/mo Investor tier. Staging environment — demo mode, no real charges.">
<meta name="theme-color" content="#020617">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23f59e0b'/%3E%3Ctext x='16' y='22' font-family='Inter,sans-serif' font-size='13' font-weight='900' text-anchor='middle' fill='%23020617'%3EBD%3C/text%3E%3C/svg%3E">
<style>
:root {
  --navy: #020617;
  --orange: #f59e0b;
  --orange2: #f97316;
  --green: #10b981;
  --surface: #f8fafc;
  --border: #e2e8f0;
  --text-muted: #e2eaf2;
}
*{box-sizing:border-box;margin:0;padding:0;font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif}
*:focus-visible{outline:2px solid var(--orange);outline-offset:2px}
html,body{height:100%}
body{overflow:hidden}
.split-container{display:flex;height:100vh;overflow:hidden}
.left-panel{width:40%;background:var(--navy);display:flex;flex-direction:column;min-width:300px;border-right:1px solid #1e3a5f;min-height:0}
.right-panel{width:60%;background:var(--surface);overflow-y:auto;display:flex;flex-direction:column;min-height:0}

/* Logo */
.logo{padding:18px 22px 8px;font-size:19px;font-weight:800;color:#fff;flex-shrink:0}
.logo span{color:var(--orange)}

/* Chat column */
.chat-messages{flex:1;overflow-y:auto;padding:8px 20px;display:flex;flex-direction:column;gap:10px;min-height:0;-webkit-overflow-scrolling:touch}
.welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;flex:1;text-align:center;gap:12px;padding:16px 8px}
.wl-icon{width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,var(--orange),var(--orange2));display:flex;align-items:center;justify-content:center;font-weight:900;font-size:18px;color:var(--navy);flex-shrink:0}
.wl-title{font-size:16px;font-weight:700;color:#fff}
.wl-sub{font-size:12px;color:var(--text-muted);max-width:280px;line-height:1.5}
.lang-row{display:flex;gap:4px;flex-wrap:wrap;justify-content:center;max-width:320px}
.lchip{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:2px 7px;font-size:10px;color:#cbd5e1;white-space:nowrap}
.chat-tbl{width:100%;border-collapse:collapse;margin:8px 0;font-size:12px}
.chat-tbl thead{background:rgba(255,255,255,.06)}
.chat-tbl th,.chat-tbl td{padding:6px 8px;border:1px solid #1e3a5f;text-align:left}
.chat-tbl th{color:var(--orange);font-weight:700;font-size:10.5px;text-transform:uppercase}
.msg-user{background:#1e3a5f;color:#e2e8f0;padding:10px 14px;border-radius:12px 12px 4px 12px;margin-left:auto;max-width:80%;font-size:14px;line-height:1.55;white-space:pre-wrap;word-break:break-word}
.msg-ai{background:#0f2744;color:#e2e8f0;padding:10px 14px;border-radius:12px 12px 12px 4px;margin-right:auto;max-width:90%;font-size:14px;line-height:1.7;word-break:break-word}
.msg-ai a{color:var(--orange);text-decoration:underline;font-weight:600}
.msg-ai b{color:#fff}
.msg-ai .md-li{margin:2px 0}
.msg-ai .md-sp{height:6px}
.typing-row{margin-right:auto;background:#0f2744;padding:10px 14px;border-radius:12px 12px 12px 4px;display:flex;gap:4px;align-items:center;font-size:12px;color:var(--text-muted)}
.td-dot{width:5px;height:5px;border-radius:50%;background:var(--orange);animation:tdp 1.1s infinite}
.td-dot:nth-child(2){animation-delay:.18s}.td-dot:nth-child(3){animation-delay:.36s}
@keyframes tdp{0%,80%,100%{opacity:.25;transform:scale(.8)}40%{opacity:1;transform:scale(1.2)}}

/* Quick pills */
.quick-pills{display:flex;flex-wrap:wrap;gap:7px;padding:0 20px 10px;flex-shrink:0}
.quick-pills button{background:transparent;border:1px solid #334155;color:#cbd5e1;border-radius:20px;padding:6px 12px;font-size:12px;cursor:pointer;font-family:inherit}
.quick-pills button:hover{border-color:var(--orange);color:var(--orange)}

/* Email capture */
.email-capture{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.25);border-radius:10px;padding:10px;margin:0 20px 10px;display:flex;flex-direction:column;gap:6px;flex-shrink:0}
.email-capture .ec-lbl{font-size:11px;color:var(--orange);font-weight:600}
.email-capture .ec-row{display:flex;gap:6px}
.email-capture input{flex:1;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:8px 10px;color:#fff;font-size:13px;outline:none}
.email-capture button{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);border:none;border-radius:8px;padding:8px 12px;font-size:12px;font-weight:700;cursor:pointer}

/* Input bar */
.input-bar-wrap{flex-shrink:0;border-top:1px solid #1e293b;background:rgba(2,6,23,.98)}
.file-pill{display:none;align-items:center;gap:6px;background:#1e3a5f;color:#e2e8f0;border-radius:14px;padding:4px 10px;font-size:11px;margin:8px 20px 0;width:fit-content}
.file-pill button{background:none;border:none;color:#cbd5e1;cursor:pointer;font-size:13px;line-height:1;padding:0}
.input-bar{display:flex;align-items:center;gap:8px;padding:10px 20px}
.clip-btn{background:transparent;border:none;color:#e2eaf2;cursor:pointer;font-size:18px;padding:6px;flex-shrink:0}
.clip-btn:hover{color:var(--orange)}
.input-bar input[type=text]{flex:1;min-width:0;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:8px;padding:11px 12px;font-size:16px;outline:none;font-family:inherit}
.input-bar input[type=text]:focus{border-color:var(--orange)}
.send-btn{background:var(--orange);color:var(--navy);border:none;border-radius:8px;padding:11px 16px;font-weight:700;font-size:13px;cursor:pointer;flex-shrink:0;font-family:inherit}
.send-btn:disabled{opacity:.4;cursor:not-allowed}
.disclaimer-text{text-align:center;font-size:9.5px;color:var(--text-muted);padding:0 20px 10px;line-height:1.4}

/* Right panel */
.panel-header{display:flex;align-items:center;justify-content:space-between;padding:16px 22px;border-bottom:1px solid var(--border);background:#fff;flex-shrink:0}
.panel-title{display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;color:#0f172a}
.live-dot{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulsep 1.6s infinite;flex-shrink:0}
@keyframes pulsep{0%{opacity:1}50%{opacity:.3}100%{opacity:1}}
#refresh-btn{background:var(--navy);color:#fff;border:none;border-radius:6px;padding:7px 14px;font-size:12px;cursor:pointer;font-family:inherit}
.panel-body{flex:1;overflow-y:auto;padding:18px 22px;min-height:0}
.panel-subtitle{font-size:12px;font-weight:700;color:#b8cfe0;text-transform:uppercase;letter-spacing:.04em;margin-bottom:10px}
.cards-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-content:start}
.empty{color:var(--text-muted);font-size:13px;padding:16px 0;grid-column:1/-1}

/* County cards */
.county-card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px}
.county-name{font-size:15px;font-weight:700;color:#0f172a;margin-bottom:4px}
.county-stats,.county-next,.county-bids{font-size:12px;color:#b8cfe0;margin:2px 0}
.county-card button{margin-top:10px;width:100%;background:var(--navy);color:#fff;border:none;border-radius:8px;padding:9px 10px;font-size:12.5px;font-weight:600;cursor:pointer;font-family:inherit}
.county-card button:hover{background:#0f2744}

/* Property cards */
.property-card{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px;grid-column:span 1}
.badges{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.badge{font-size:11px;font-weight:700;letter-spacing:.03em;padding:2px 8px;border-radius:20px}
.badge.foreclosure{background:#dbeafe;color:#1e40af}
.badge.tax-deed{background:#d1fae5;color:#065f46}
.badge.gold{background:#fef3c7;color:#92400e}
.address{font-weight:700;font-size:14px;color:#0f172a;margin-bottom:2px}
.auction-date{font-size:12px;color:#64748b;margin-bottom:10px}
.financials{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px}
.financials label{display:block;font-size:9px;color:#e2eaf2;text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px}
.financials value{display:block;font-size:12.5px;font-weight:700;color:#0f172a;font-family:'SF Mono',monospace}
.parity{font-size:11px;font-weight:600;margin-bottom:10px}
.parity.ok{color:var(--green)}
.parity.warn{color:var(--orange)}
.parity.bad{color:#dc2626}
.clerk-parity{font-size:10px;font-weight:600;color:var(--green);margin-bottom:10px}
.actions{display:flex;gap:8px;flex-wrap:wrap}
.btn-buy{flex:1;text-align:center;background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:9px 10px;border-radius:8px;font-weight:700;font-size:12px;text-decoration:none;white-space:nowrap}
.btn-maps{flex:1;text-align:center;background:#f1f5f9;border:1px solid var(--border);color:#334155;border-radius:8px;padding:9px 10px;font-size:12px;font-weight:600;text-decoration:none;white-space:nowrap}

/* Marion proof — pinned always */
.marion-proof{grid-column:1/-1;background:#f0fdf4;border:1px solid #bbf7d0;border-left:4px solid #16a34a;border-radius:10px;padding:14px;margin-top:14px}
.marion-title{color:#16a34a;font-weight:800;font-size:13px;letter-spacing:.03em}
.marion-detail{font-size:12px;color:#334155;margin-top:4px}

/* Upgrade banner — always visible */
.upgrade-banner{grid-column:1/-1;background:#fff;border:1px solid rgba(245,158,11,.35);border-radius:10px;padding:14px;margin-top:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.upgrade-text{font-size:13px;font-weight:600;color:#0f172a}
.upgrade-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.btn-investor{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:9px 16px;border-radius:8px;font-weight:700;font-size:12.5px;text-decoration:none;white-space:nowrap}
.upgrade-actions .or{font-size:11px;color:#e2eaf2}
.btn-report{background:#f1f5f9;border:1px solid var(--border);color:#334155;padding:9px 16px;border-radius:8px;font-weight:600;font-size:12.5px;text-decoration:none;white-space:nowrap}

@media (max-width: 768px) {
  .split-container{flex-direction:column;height:100vh;height:-webkit-fill-available}
  .right-panel{width:100%;order:1;flex:0 0 auto;max-height:55vh}
  .left-panel{width:100%;min-width:unset;order:2;flex:1;min-height:0;border-right:none;border-top:1px solid #1e3a5f}
  .cards-grid{grid-template-columns:1fr}
  .input-bar input[type=text]{font-size:16px}
}
</style>
</head>
<body>
<div style="background:#f59e0b;color:#020617;text-align:center;padding:6px 12px;font-size:13px;font-weight:600;letter-spacing:.02em;">🧪 STAGING — No real charges · <a href="https://biddeed.ai" style="color:#020617;text-decoration:underline;">Go to live site</a></div>
<div class="split-container">
  <div class="left-panel">
    <div class="logo">BidDeed<span>.AI</span></div>
    <div class="chat-messages" id="chat">
      <div class="welcome" id="welcome">
        <div class="wl-icon">BD</div>
        <div class="wl-title">Foreclosure &amp; Tax Deed Intelligence</div>
        <div class="wl-sub">Ask about any Florida county. Responds in your language automatically. Attach a document with the paperclip for AI analysis.</div>
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
    <div class="quick-pills">
      <button data-msg="Tell me about upcoming Putnam tax deed auctions">Putnam tax deeds</button>
      <button data-msg="What Brevard foreclosures are coming up in the next few weeks?">Brevard foreclosures</button>
      <button data-msg="How does BidDeed.AI work?">How does it work?</button>
      <button data-msg="Show me the Marion County proof — Shapira Formula ceiling held to the cent.">Marion proof</button>
    </div>
    <div id="email-capture-slot"></div>
    <div class="input-bar-wrap">
      <div class="file-pill" id="filePill"><span id="filePillName"></span><button id="filePillRemove" type="button" aria-label="Remove attachment">×</button></div>
      <div class="input-bar">
        <input type="file" id="fileInput" accept=".pdf,image/*" style="display:none">
        <button class="clip-btn" id="clipBtn" type="button" title="Attach a document (paperclip) — PDF or image" aria-label="Attach a document">📎</button>
        <input type="text" id="inp" placeholder="Ask about any Florida county..." autocomplete="off" autocorrect="off" spellcheck="false" aria-label="Chat message">
        <button class="send-btn" id="snd" type="button" aria-label="Send message">Send</button>
      </div>
      <div class="disclaimer-text">${DISCLAIMER_SHORT}</div>
    </div>
  </div>

  <div class="right-panel">
    <div class="panel-header">
      <div class="panel-title"><span class="live-dot" aria-hidden="true"></span> County Intelligence Feed · Live</div>
      <button id="refresh-btn" type="button" title="Reload the county feed from the production database" aria-label="Refresh county feed">Refresh</button>
    </div>
    <div class="panel-body" id="panel-body"><div class="empty">Loading counties…</div></div>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────
var H = [];                       // chat history sent to /staging/chat/api
var busy = false;
var msgCount = 0;
var emailDone = false;
var pendingFile = null;           // { name, media_type, data (base64, no prefix) }
var rightPanelState = 'COUNTY_FEED'; // COUNTY_FEED | PROPERTY_LIST
var MAX_FILE_BYTES = 10 * 1024 * 1024;

var MARION_HTML = '<div class="marion-proof"><div class="marion-title">CEILING HELD</div><div class="marion-detail">$73,501 sold · $82,000 max bid · 14470 SE 91ST TER · Jul 20 2026</div></div>';
var UPGRADE_HTML = '<div class="upgrade-banner"><div class="upgrade-text">Unlock the Shapira Max Bid on every property</div><div class="upgrade-actions"><a href="https://biddeed.ai/subscribe?tier=investor" class="btn-investor">Investor $99/mo →</a><span class="or">or</span><a href="/staging/buy-report" class="btn-report">One Report $25 →</a></div></div>';

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function toDisplayClient(slug){return String(slug||'').split('_').map(function(w){return w.charAt(0).toUpperCase()+w.slice(1);}).join(' ');}

// ── Minimal safe markdown (bold + safe links + bullets). Zero-regex on the
// escape-sensitive parts — Cloudflare's template-literal evaluation of this
// nested inline script has been seen to strip backslash escapes elsewhere,
// so bold/link parsing here uses pure string scans, not regex literals.
function formatInline(escaped){
  var STAR = String.fromCharCode(42);
  var bold = STAR + STAR;
  var out = '', i = 0;
  while (i < escaped.length) {
    if (escaped.slice(i, i+2) === bold) {
      var close = escaped.indexOf(bold, i+2);
      if (close !== -1) { out += '<b>' + escaped.slice(i+2, close) + '</b>'; i = close + 2; continue; }
    }
    out += escaped.charAt(i); i++;
  }
  escaped = out; out = ''; i = 0;
  while (i < escaped.length) {
    if (escaped.charAt(i) === '[') {
      var closeBracket = escaped.indexOf(']', i+1);
      if (closeBracket !== -1 && escaped.charAt(closeBracket+1) === '(') {
        var closeParen = escaped.indexOf(')', closeBracket+2);
        if (closeParen !== -1) {
          var linkText = escaped.slice(i+1, closeBracket);
          var url = escaped.slice(closeBracket+2, closeParen);
          var safe = url.indexOf('https://biddeed.ai') === 0 || url.indexOf('https://staging.biddeed.ai') === 0;
          if (safe) { out += '<a href="' + url + '" target="_blank">' + linkText + '</a>'; i = closeParen + 1; continue; }
        }
      }
    }
    out += escaped.charAt(i); i++;
  }
  return out;
}
function mdToHtml(raw){
  var lines = String(raw).split(String.fromCharCode(10));
  var html = '';
  var tableRows = [];
  var isPipeChar = function(c){ return c === '|' || c === ':' || c === '-' || c === ' '; };
  var flushTable = function(){
    if (!tableRows.length) return;
    var header = tableRows[0];
    var rest = tableRows.slice(1);
    html += '<table class="chat-tbl"><thead><tr>' + header.map(function(c){ return '<th>'+c+'</th>'; }).join('') + '</tr></thead><tbody>';
    for (var r = 0; r < rest.length; r++) html += '<tr>' + rest[r].map(function(c){ return '<td>'+c+'</td>'; }).join('') + '</tr>';
    html += '</tbody></table>';
    tableRows = [];
  };
  for (var idx = 0; idx < lines.length; idx++) {
    var line = lines[idx];
    var trimmed = line.trim();
    var isTableRow = trimmed.length > 1 && trimmed.charAt(0) === '|' && trimmed.charAt(trimmed.length-1) === '|';
    if (isTableRow) {
      var isSeparator = true;
      for (var k = 0; k < trimmed.length; k++) { if (!isPipeChar(trimmed.charAt(k))) { isSeparator = false; break; } }
      if (isSeparator) continue;
      var inner = trimmed.slice(1, -1);
      var cells = inner.split('|').map(function(c){ return formatInline(esc(c.trim())); });
      tableRows.push(cells);
      continue;
    } else if (tableRows.length) {
      flushTable();
    }
    if (trimmed === '') { html += '<div class="md-sp"></div>'; continue; }
    if ((trimmed.charAt(0) === '-' || trimmed.charAt(0) === String.fromCharCode(42)) && trimmed.charAt(1) === ' ') {
      html += '<div class="md-li">' + String.fromCharCode(8226) + ' ' + formatInline(esc(trimmed.slice(1).trim())) + '</div>';
    } else {
      html += '<div>' + formatInline(esc(line)) + '</div>';
    }
  }
  if (tableRows.length) flushTable();
  return html;
}
function stripShowCountyMarker(s){
  var start = s.indexOf('[SHOW_COUNTY:');
  if (start === -1) return s;
  var end = s.indexOf(']', start);
  if (end === -1) return s;
  return (s.slice(0, start) + s.slice(end+1)).trim();
}

function scrollBottom(){ var c = document.getElementById('chat'); c.scrollTop = c.scrollHeight; }
function addMsg(role, text){
  var welcomeEl = document.getElementById('welcome');
  if (welcomeEl) welcomeEl.remove();
  var d = document.createElement('div');
  d.className = role === 'user' ? 'msg-user' : 'msg-ai';
  d.innerHTML = role === 'user' ? esc(text) : mdToHtml(text);
  document.getElementById('chat').appendChild(d);
  scrollBottom();
  return d;
}

// ── Paperclip / document upload ──────────────────────────────────────────
document.getElementById('clipBtn').addEventListener('click', function(){ document.getElementById('fileInput').click(); });
document.getElementById('fileInput').addEventListener('change', function(e){
  var file = e.target.files && e.target.files[0];
  if (!file) return;
  if (file.size > MAX_FILE_BYTES) { alert('File too large — 10MB max.'); e.target.value = ''; return; }
  var reader = new FileReader();
  reader.onload = function(){
    var result = String(reader.result || '');
    var comma = result.indexOf(',');
    var base64 = comma !== -1 ? result.slice(comma+1) : result;
    pendingFile = { name: file.name, media_type: file.type || 'application/octet-stream', data: base64 };
    document.getElementById('filePillName').textContent = file.name;
    document.getElementById('filePill').style.display = 'flex';
  };
  reader.readAsDataURL(file);
});
document.getElementById('filePillRemove').addEventListener('click', function(){
  pendingFile = null;
  document.getElementById('fileInput').value = '';
  document.getElementById('filePill').style.display = 'none';
});

// ── Send / SSE stream ─────────────────────────────────────────────────────
function ask(text){ document.getElementById('inp').value = text; send(); }
function askAboutCounty(county){ ask('Show me upcoming ' + toDisplayClient(county) + ' auctions'); }

function send(){
  if (busy) return;
  var inp = document.getElementById('inp');
  var text = inp.value.trim();
  if (!text && !pendingFile) return;
  inp.value = '';
  busy = true;
  document.getElementById('snd').disabled = true;
  msgCount++;
  var docForRequest = pendingFile;
  H.push({ role: 'user', content: text || ('Analyze this document: ' + (docForRequest ? docForRequest.name : '')) });
  addMsg('user', text || ('📎 ' + (docForRequest ? docForRequest.name : 'document')));
  pendingFile = null;
  document.getElementById('fileInput').value = '';
  document.getElementById('filePill').style.display = 'none';

  var chat = document.getElementById('chat');
  var typingRow = document.createElement('div');
  typingRow.id = 'typing';
  typingRow.className = 'typing-row';
  typingRow.textContent = docForRequest ? 'Analyzing document...' : '';
  if (!docForRequest) typingRow.innerHTML = '<div class="td-dot"></div><div class="td-dot"></div><div class="td-dot"></div>';
  chat.appendChild(typingRow);
  scrollBottom();

  var payload = { messages: H };
  if (docForRequest) payload.document = { media_type: docForRequest.media_type, data: docForRequest.data };

  fetch('/staging/chat/api', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then(function(res){
      document.getElementById('typing') && document.getElementById('typing').remove();
      if (!res.ok) { addMsg('assistant', 'Error ' + res.status + '. Please try again.'); busy = false; document.getElementById('snd').disabled = false; return; }
      var bubble = addMsg('assistant', '');
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var buf = '', fullText = '', pendingEvent = null;
      function pump(){
        return reader.read().then(function(r){
          if (r.done) { finish(); return; }
          buf += decoder.decode(r.value, { stream: true });
          var lines = buf.split(String.fromCharCode(10));
          buf = lines.pop() || '';
          for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.indexOf('event: ') === 0) { pendingEvent = line.slice(7).trim(); continue; }
            if (line.indexOf('data: ') !== 0) continue;
            var data = line.slice(6).trim();
            if (data === '[DONE]') { pendingEvent = null; continue; }
            if (pendingEvent === 'properties') {
              try { renderPropertyCards(JSON.parse(data)); } catch(e) {}
              pendingEvent = null; continue;
            }
            try {
              var evt = JSON.parse(data);
              if (evt.text) { fullText += evt.text; bubble.innerHTML = mdToHtml(stripShowCountyMarker(fullText)); scrollBottom(); }
            } catch(e) {}
          }
          return pump();
        });
      }
      function finish(){
        fullText = stripShowCountyMarker(fullText);
        bubble.innerHTML = mdToHtml(fullText);
        H.push({ role: 'assistant', content: fullText });
        if (!emailDone && msgCount >= 3) showEmailCapture();
        busy = false;
        document.getElementById('snd').disabled = false;
      }
      return pump();
    })
    .catch(function(e){
      document.getElementById('typing') && document.getElementById('typing').remove();
      addMsg('assistant', 'Connection error. Check your internet and try again.');
      busy = false;
      document.getElementById('snd').disabled = false;
    });
}

function showEmailCapture(){
  if (emailDone) return;
  emailDone = true;
  var slot = document.getElementById('email-capture-slot');
  slot.innerHTML = '<div class="email-capture"><div class="ec-lbl">📬 Get daily FL auction alerts — free</div><div class="ec-row"><input type="email" id="ec-input" placeholder="your@email.com"><button id="ec-btn">Get Alerts →</button></div></div>';
  document.getElementById('ec-btn').addEventListener('click', saveEmail);
  document.getElementById('ec-input').addEventListener('keydown', function(e){ if (e.key === 'Enter') saveEmail(); });
}
function saveEmail(){
  var email = (document.getElementById('ec-input').value || '').trim();
  if (!email || email.indexOf('@') === -1) return;
  document.getElementById('email-capture-slot').innerHTML = '';
  fetch('/staging/chat/lead', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email, source: 'staging_demo' }) }).catch(function(){});
  addMsg('assistant', '✅ Done! Daily FL auction alerts sent to ' + email + '.');
}

document.getElementById('snd').addEventListener('click', send);
document.getElementById('inp').addEventListener('keydown', function(e){ if (e.key === 'Enter') { e.preventDefault(); send(); } });
document.querySelectorAll('.quick-pills button').forEach(function(btn){
  btn.addEventListener('click', function(){ ask(btn.getAttribute('data-msg')); });
});

// ── Right panel: county feed (default) / property list (after intent) ────
function setPanelBody(cardsHtml){ document.getElementById('panel-body').innerHTML = cardsHtml + MARION_HTML + UPGRADE_HTML; }

function buildCountyCard(r){
  var star = r.isGold ? ' ⭐' : '';
  return '<div class="county-card">' +
    '<div class="county-name">' + esc(r.countyDisplay) + star + '</div>' +
    '<div class="county-stats">' + r.fc + ' FC / ' + r.td + ' TD (30d)</div>' +
    '<div class="county-next">Next FC: ' + esc(r.fcNext) + ' · Next TD: ' + esc(r.tdNext) + '</div>' +
    (r.bidRange ? ('<div class="county-bids">Avg bid: ' + esc(r.bidRange) + '</div>') : '') +
    '<button data-county="' + esc(r.county) + '">Explore ' + esc(r.countyDisplay) + ' →</button>' +
  '</div>';
}
document.getElementById('panel-body').addEventListener('click', function(e){
  var btn = e.target.closest('button[data-county]');
  if (btn) askAboutCounty(btn.getAttribute('data-county'));
});
function renderCountyFeed(rows){
  var html = (rows && rows.length) ? rows.map(buildCountyCard).join('') : '<div class="empty">No county data available.</div>';
  setPanelBody('<div class="cards-grid">' + html + '</div>');
  rightPanelState = 'COUNTY_FEED';
}
function loadCountyFeed(){
  document.getElementById('panel-body').innerHTML = '<div class="empty">Loading counties…</div>';
  fetch('/staging/county-feed').then(function(r){ return r.json(); }).then(renderCountyFeed).catch(function(){
    document.getElementById('panel-body').innerHTML = '<div class="empty">Feed unavailable.</div>';
  });
}
document.getElementById('refresh-btn').addEventListener('click', loadCountyFeed);
loadCountyFeed();

function fmtMoneyP(n){ if (n === null || n === undefined || n === '') return 'N/A'; return '$' + Math.round(Number(n)).toLocaleString('en-US'); }
function fmtDateP(d){ if (!d) return 'TBD'; var dt = new Date(d + 'T00:00:00'); return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
function saleBadge(t){
  if (t === 'tax_deed') return '<span class="badge tax-deed">TAX DEED</span>';
  if (t === 'foreclosure') return '<span class="badge foreclosure">FORECLOSURE</span>';
  return '';
}
function parityInfo(p){
  if (p === 'matched_clean' || p === 'PARITY_OK' || p === 'CLERK_VERIFIED') return { cls: 'ok', text: '✓ Data verified' };
  if (p === 'matched_divergent' || p === 'CLERK_SSOT_CANCELLED') return { cls: 'bad', text: '⚠ Data conflict' };
  return { cls: 'warn', text: '⚠ Data unverified' };
}
function clerkParityBadge(a){
  var b = a.clerk_parity_badge;
  if (!b || b.match_pct == null || !b.checked_at) return '';
  var hrs = Math.max(0, Math.round((Date.now() - new Date(b.checked_at).getTime()) / 3600000));
  var when = hrs < 1 ? 'just now' : (hrs + 'h ago');
  return '<div class="clerk-parity" title="Cross-checked against the ' + esc(toDisplayClient(b.county || '')) + ' Clerk of Court sale calendar">✅ Clerk-verified ' + esc(String(b.match_pct)) + '% · checked ' + when + '</div>';
}
function buildPropertyCard(a){
  var hasAddr = !!a.property_address;
  var addr = hasAddr ? a.property_address : ('Address pending — Case #' + esc(a.case_number || ''));
  var p = parityInfo(a.parity_status);
  var mapsUrl = hasAddr ? ('https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(a.property_address)) : '';
  var buyUrl = '/staging/buy-report?mca_id=' + encodeURIComponent(a.id) + '&address=' + encodeURIComponent(a.property_address || '') + '&county=' + encodeURIComponent(a.county || '') + '&date=' + encodeURIComponent(a.auction_date || '');
  var html = '<div class="property-card">';
  html += '<div class="badges">' + saleBadge(a.sale_type) + (a.is_gold_standard ? '<span class="badge gold">⭐ GOLD STANDARD</span>' : '') + '</div>';
  html += '<div class="address">' + esc(addr) + '</div>';
  html += '<div class="auction-date">' + esc(fmtDateP(a.auction_date)) + (a.days_until_auction != null ? (' · ' + a.days_until_auction + ' days away') : '') + '</div>';
  html += '<div class="financials"><div><label>Opening Bid</label><value>' + fmtMoneyP(a.opening_bid) + '</value></div>' +
          '<div><label>Assessed Value</label><value>' + fmtMoneyP(a.assessed_value) + '</value></div>' +
          '<div><label>Equity Gap</label><value>' + fmtMoneyP(a.equity_gap) + '</value></div></div>';
  html += '<div class="parity ' + p.cls + '">' + p.text + '</div>';
  html += clerkParityBadge(a);
  html += '<div class="actions"><a class="btn-buy" href="' + buyUrl + '">Buy SIGNAL$ Property Report — $25</a>' +
          (hasAddr ? ('<a class="btn-maps" href="' + mapsUrl + '" target="_blank" rel="noopener">View on Maps ↗</a>') : '') + '</div>';
  html += '</div>';
  return html;
}
function renderPropertyCards(payload){
  var list = payload.auctions || [];
  var title = (payload.county ? toDisplayClient(payload.county) : 'Properties') + ' — ' + list.length + ' upcoming';
  var cardsHtml = list.length ? list.map(buildPropertyCard).join('') : '<div class="empty">No upcoming auctions found for this county right now.</div>';
  setPanelBody('<div class="panel-subtitle">' + esc(title) + '</div><div class="cards-grid">' + cardsHtml + '</div>');
  rightPanelState = 'PROPERTY_LIST';
}
</script>
</body>
</html>`;
}

// ── HTML: demo $25 report checkout page (prefilled from a property card) ───
function buildBuyReportHtml(prefill) {
  const hasPrefill = !!prefill.mcaId;
  const countyName = prefill.county ? toDisplay(prefill.county) : '';
  const summary = hasPrefill
    ? `<div class="summary"><div class="addr">${esc(prefill.address || 'Selected property')}</div><div class="meta">${esc(countyName)} County${prefill.date ? ' · ' + esc(fmtDate(prefill.date)) : ''}</div></div>`
    : `<div class="empty">No property selected. <a href="/staging">Go back to chat</a> and ask about a county to pick one.</div>`;
  const prefillJson = JSON.stringify({ mcaId: prefill.mcaId || '', address: prefill.address || '', county: prefill.county || '' })
    .replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Buy SIGNAL$ Property Report — $25 (DEMO) | BidDeed.AI Staging</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:Inter,system-ui,-apple-system,sans-serif}
:root{--navy:#020617;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#e2eaf2;--border:#1e293b}
body{background:var(--navy);color:var(--text);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:480px;width:100%}
.badge{color:var(--orange);font-size:12px;font-weight:700;letter-spacing:.08em;margin-bottom:.75rem}
h1{font-size:1.4rem;color:#fff;margin-bottom:.75rem}
.summary{border:1px solid var(--border);border-radius:10px;padding:1rem;margin-bottom:1.25rem;font-size:.85rem}
.summary .addr{font-weight:700;color:#fff;margin-bottom:.3rem}
.summary .meta{color:var(--muted)}
.empty{color:var(--muted);font-size:.85rem;margin-bottom:1.25rem;line-height:1.6}
.empty a{color:var(--orange)}
label{display:block;font-size:.85rem;color:var(--muted);margin-bottom:.4rem}
input[type=email]{width:100%;padding:12px 14px;border-radius:8px;border:1px solid var(--border);background:#020617;color:var(--text);font-size:.95rem;margin-bottom:1.25rem;font-family:inherit}
.btn{display:block;width:100%;background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:14px;border:none;border-radius:10px;font-weight:700;font-size:.95rem;cursor:pointer}
.btn:disabled{opacity:.6;cursor:not-allowed}
.err{color:#f87171;font-size:.85rem;margin-top:.75rem;min-height:1em}
.upl{margin-top:1.5rem;padding-top:1.25rem;border-top:1px solid var(--border);font-size:.72rem;color:var(--muted);line-height:1.6}
</style></head>
<body>
<div class="card">
  <div class="badge">ONE-TIME · $25 · DEMO MODE — NO REAL CHARGE</div>
  <h1>SIGNAL$ Property Report</h1>
  ${summary}
  ${hasPrefill ? `<label for="br-email">Email for report delivery</label><input type="email" id="br-email" placeholder="your@email.com">
  <button class="btn" id="br-submit">Buy Report — $25 (DEMO)</button>
  <div class="err" id="br-err"></div>` : ''}
  <div class="upl">${DISCLAIMER_SHORT}</div>
</div>
<script>
var PREFILL = ${prefillJson};
var btn = document.getElementById('br-submit');
if (btn) {
  btn.addEventListener('click', function(){
    var errEl = document.getElementById('br-err');
    var email = (document.getElementById('br-email').value || '').trim();
    if (!email || email.indexOf('@') === -1) { errEl.textContent = 'Enter a valid email.'; return; }
    errEl.textContent = '';
    btn.disabled = true; btn.textContent = 'Processing…';
    fetch('/staging/buy-report/checkout', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, county: PREFILL.county, mca_id: PREFILL.mcaId, address: PREFILL.address })
    }).then(function(res){
      if (res.redirected) { location.href = res.url; return; }
      if (res.ok) { location.href = '/staging/demo-success'; return; }
      return res.json().then(function(d){ throw new Error((d && d.error) || 'Checkout failed'); });
    }).catch(function(e){
      errEl.textContent = e.message || 'Network error — try again.';
      btn.disabled = false; btn.textContent = 'Buy Report — $25 (DEMO)';
    });
  });
}
</script>
</body></html>`;
}

// ── HTML: demo success page ──────────────────────────────────────────────
function buildDemoSuccessHtml() {
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>BidDeed.AI Staging — Demo Purchase Successful</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<style>
body{font-family:Inter,system-ui,sans-serif;background:#020617;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}
.card{background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:40px;max-width:480px;text-align:center;}
h1{color:#F59E0B;font-size:20px;}
.key{font-family:'JetBrains Mono',monospace;background:#020617;border:1px solid #334155;border-radius:8px;padding:14px;margin:16px 0;font-size:16px;color:#22c55e;}
p{color:#e2eaf2;font-size:13px;}
a{color:#F59E0B}
</style></head>
<body><div class="card">
<h1>Demo purchase successful — Stripe checkout skipped</h1>
<div class="key">bd_staging_DEMO</div>
<p>This is a staging environment. In production, this key would be delivered after a real Stripe payment. No charge was made.</p>
<p style="margin-top:14px"><a href="/staging">&larr; Back to BidDeed.AI Staging</a></p>
</div></body></html>`;
}

// ── Main fetch handler ────────────────────────────────────────────────────
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;
    const origin = request.headers.get('Origin') || '';

    try {
      if (method === 'OPTIONS') {
        return new Response(null, { status: 204, headers: corsHeaders(origin) });
      }

      // ── GET /staging — split-screen shell ────────────────────────────
      if (path === '/staging' && method === 'GET') {
        return new Response(buildStagingShell(), {
          headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' },
        });
      }

      // ── GET /staging/county-feed — top 8 by upcoming_30d ─────────────
      if (path === '/staging/county-feed' && method === 'GET') {
        const rows = await fetchCountyFeed();
        const out = rows.map(r => {
          const fcRange = (r.fc_min_opening_bid || r.fc_max_opening_bid)
            ? `${fmtMoney(r.fc_min_opening_bid) || '?'}–${fmtMoney(r.fc_max_opening_bid) || '?'}`
            : null;
          const tdRange = (r.td_min_opening_bid || r.td_max_opening_bid)
            ? `${fmtMoney(r.td_min_opening_bid) || '?'}–${fmtMoney(r.td_max_opening_bid) || '?'}`
            : null;
          return {
            county: r.county,
            countyDisplay: toDisplay(r.county),
            isGold: !!r.is_gold_standard,
            fc: r.fc_upcoming_30d || 0,
            td: r.td_upcoming_30d || 0,
            fcNext: fmtDate(r.fc_next_auction_date),
            tdNext: fmtDate(r.td_next_auction_date),
            bidRange: fcRange || tdRange,
            totalUpcoming30d: r.total_upcoming_30d || 0,
          };
        });
        return new Response(JSON.stringify(out), {
          headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public,max-age=120', ...corsHeaders(origin) },
        });
      }

      // ── GET /staging/auctions?county=&days=&type=&limit= — property cards ──
      if (path === '/staging/auctions' && method === 'GET') {
        const county = (url.searchParams.get('county') || '').toLowerCase().replace(/-/g,'_');
        if (!county) return new Response(JSON.stringify({ error: 'county required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        let days = parseInt(url.searchParams.get('days') || '21', 10);
        if (!Number.isFinite(days) || days <= 0) days = 21;
        days = Math.min(days, 90);
        const type = (url.searchParams.get('type') || 'all').toLowerCase();
        let limit = parseInt(url.searchParams.get('limit') || '15', 10);
        if (!Number.isFinite(limit) || limit <= 0) limit = 15;
        limit = Math.min(limit, 50);
        const cards = await fetchAuctionCards(county, days, type, limit);
        return new Response(JSON.stringify(cards), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public,max-age=60', ...corsHeaders(origin) } });
      }

      // ── GET /staging/buy-report — demo checkout page ─────────────────
      if (path === '/staging/buy-report' && method === 'GET') {
        const prefill = {
          mcaId: url.searchParams.get('mca_id') || '',
          address: url.searchParams.get('address') || '',
          county: (url.searchParams.get('county') || '').toLowerCase().replace(/-/g,'_'),
          date: url.searchParams.get('date') || '',
        };
        return new Response(buildBuyReportHtml(prefill), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
      }

      // ── POST /staging/buy-report/checkout — DEMO MODE, no real Stripe ──
      if (path === '/staging/buy-report/checkout' && method === 'POST') {
        let body = {};
        try { body = await request.json(); } catch(_) {
          return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        if (!body.email) return new Response(JSON.stringify({ error: 'email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (DEMO_MODE) {
          return Response.redirect(`${url.origin}/staging/demo-success`, 302);
        }
        return new Response(JSON.stringify({ error: 'Live checkout not available in staging' }), { status: 501, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
      }

      // ── GET /staging/demo-success ────────────────────────────────────
      if (path === '/staging/demo-success' && method === 'GET') {
        return new Response(buildDemoSuccessHtml(), {
          headers: { 'Content-Type': 'text/html;charset=UTF-8', ...corsHeaders(origin) },
        });
      }

      // ── POST /staging/chat/lead ───────────────────────────────────────
      if (path === '/staging/chat/lead' && method === 'POST') {
        let body = {};
        try { body = await request.json(); } catch(_) {}
        const { email, county, source } = body;
        if (!email) return new Response(JSON.stringify({ ok: false, error: 'email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/demo_lead_profiles`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'apikey': SUPABASE_KEY,
              'Authorization': `Bearer ${SUPABASE_KEY}`,
              'Prefer': 'resolution=merge-duplicates,return=minimal',
            },
            body: JSON.stringify({ email, county_interest: county || null, source: source || 'staging_demo' }),
          });
          if (!res.ok) {
            const err = await res.text();
            return new Response(JSON.stringify({ ok: false, error: err }), { status: res.status, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }
          return new Response(JSON.stringify({ ok: true }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        } catch(e) {
          return new Response(JSON.stringify({ ok: false, error: String(e) }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
      }

      // ── POST /staging/chat/api — Streaming SSE (BidDeed system prompt) ──
      if (path === '/staging/chat/api' && method === 'POST') {
        const cl = parseInt(request.headers.get('Content-Length') || '0', 10);
        if (cl > MAX_BODY_BYTES) return new Response(JSON.stringify({ error: 'Request too large' }), { status: 413, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        let body = {};
        try { body = await request.json(); } catch(_) {
          return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        const { messages, document } = body;
        if (!Array.isArray(messages) || messages.length === 0)
          return new Response(JSON.stringify({ error: 'messages required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (messages.length > 20)
          return new Response(JSON.stringify({ error: 'Too many messages' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const totalChars = messages.reduce((n, m) => n + String(m.content || '').length, 0);
        if (totalChars > 8000)
          return new Response(JSON.stringify({ error: 'Messages too long' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (!messages.every(m => ['user','assistant'].includes(m.role)))
          return new Response(JSON.stringify({ error: 'Invalid message role' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (document && (typeof document.data !== 'string' || typeof document.media_type !== 'string'))
          return new Response(JSON.stringify({ error: 'Invalid document payload' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        const lastUserMsg = String([...messages].reverse().find(m => m.role === 'user')?.content || '');

        // ── County intent detection → live property cards for the right panel ──
        const intentCounty = detectFLCounty(lastUserMsg);
        let propertyCards = null;
        let liveDataCtx = '';
        if (intentCounty) {
          propertyCards = await fetchAuctionCards(intentCounty, 21, 'all', 15);
          liveDataCtx = `\n\nLIVE AUCTION DATA for ${toDisplay(intentCounty)} County (next 21 days, live from the production database): ${JSON.stringify(propertyCards)}\nSummarize the best opportunities naturally — highlight equity gap and bid range, don't list every field. Then, on its own line with nothing after it, end your response with exactly: [SHOW_COUNTY:${intentCounty}]`;
        }

        const lang = detectLanguage(lastUserMsg);
        const langNote = lang ? `\n\nThe user's message appears to be written in ${lang} — respond in ${lang}.` : '';

        const SYSTEM_PROMPT = `You are BidDeed.AI, the Shapira Formula auction intelligence platform for Florida foreclosure and tax deed auctions. You have live access to 67 Florida counties with 72,000+ tracked auctions.

Your knowledge of BidDeed data is current and real-time — you are NOT a general AI with a knowledge cutoff. You have live auction schedules, opening bids, and property data.

The Marion proof: 14470 SE 91ST TER, Summerfield FL sold $73,501 on Jul 20 2026. Our Shapira Max Bid ceiling was $82,000. CEILING HELD — the property sold BELOW our max bid, confirming our model.

Gold Standard counties (full SIGNAL$ Property Report capability): Brevard, Putnam, Hillsborough, Palm Beach, Duval, Indian River, St Johns, Nassau, Charlotte, Hernando, Pasco, Monroe, Volusia, Leon, Orange.

When a user asks about auctions in a specific county, tell them what you know: upcoming counts, next auction dates, opening bid ranges. End your response with [SHOW_COUNTY:county_slug] so the system can display property cards.

Always be direct and data-specific. Never say you cannot access real-time data — you can.

FORMATTING: the chat UI renders real markdown. Use **bold** for prices and addresses. Use a markdown table (| col | col |) when listing 3+ properties — it renders as a real HTML table.

Respond in the same language the user writes in (English, Hebrew, Spanish, Portuguese, Arabic, Russian, Chinese, French, etc.).
${liveDataCtx}${langNote}

${DISCLAIMER_SHORT}`;

        // Routed through the anthropic-proxy Supabase edge function (Claude Max
        // OAuth tier 1, Gemini fallback tier 2) — never api.anthropic.com
        // directly with an ANTHROPIC_API_KEY. Same fix as src/worker.js /chat/api.
        const routerProxyKey = env.ROUTER_PROXY_KEY;
        if (!routerProxyKey) {
          return new Response(JSON.stringify({ error: 'Service configuration error' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        let anthropicRes;
        try {
          anthropicRes = await fetch(`${SUPABASE_URL}/functions/v1/anthropic-proxy/v1/messages`, {
            method: 'POST',
            headers: { 'x-api-key': routerProxyKey, 'Content-Type': 'application/json' },
            body: JSON.stringify({
              model: 'claude-haiku-4-5-20251001',
              max_tokens: 1024,
              stream: true,
              system: SYSTEM_PROMPT,
              messages: buildAnthropicMessages(messages, document),
            }),
          });
        } catch(e) {
          return new Response(JSON.stringify({ error: 'AI service unavailable' }), { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        if (!anthropicRes.ok) {
          return new Response(JSON.stringify({ error: 'AI service error' }), { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        const { readable, writable } = new TransformStream();
        const writer = writable.getWriter();
        const encoder = new TextEncoder();

        ctx.waitUntil((async () => {
          const reader = anthropicRes.body.getReader();
          const decoder = new TextDecoder();
          let buf = '';
          let fullText = '';
          try {
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
                  if (evt.type === 'content_block_delta' && evt.delta?.type === 'text_delta') {
                    fullText += evt.delta.text;
                    await writer.write(encoder.encode(`data: ${JSON.stringify({ text: evt.delta.text })}\n\n`));
                  }
                } catch(_) {}
              }
            }
            if (propertyCards) {
              const markerStart = fullText.indexOf('[SHOW_COUNTY:');
              if (markerStart !== -1) {
                const payload = { county: intentCounty, auctions: propertyCards, total: propertyCards.length };
                await writer.write(encoder.encode(`event: properties\ndata: ${JSON.stringify(payload)}\n\n`));
              }
            }
            await writer.write(encoder.encode('data: [DONE]\n\n'));
          } catch(e) {
          } finally {
            await writer.close();
          }
        })());

        return new Response(readable, {
          headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', ...corsHeaders(origin) },
        });
      }

      // ── /staging/* fallback ────────────────────────────────────────────
      if (path.startsWith('/staging')) {
        return new Response('Not found', { status: 404 });
      }

      return new Response('Not found', { status: 404 });

    } catch(e) {
      return new Response('Internal server error', { status: 500 });
    }
  }
};
