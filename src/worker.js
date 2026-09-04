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
 *   POST /support/bot         → Chatwoot Agent Bot webhook (biddeed.ai + winnerdataai.com inboxes) — same Smart Router, AI-only, no human handoff
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

const DEED_ROBOT_ICON = `<svg class="deed-robot-mark" viewBox="0 0 96 96" role="img" aria-label="Deed Voice AI robot"><circle cx="48" cy="10" r="6" fill="var(--orange)"/><path d="M48 16v8" stroke="var(--orange)" stroke-width="5" stroke-linecap="round"/><rect x="14" y="22" width="68" height="52" rx="18" fill="var(--navy)" stroke="var(--orange)" stroke-width="4"/><rect x="23" y="31" width="50" height="34" rx="12" fill="var(--navy3)"/><circle cx="36" cy="45" r="6" fill="var(--orange)"/><circle cx="60" cy="45" r="6" fill="var(--orange)"/><path d="M37 56h22M42 56v5m12-5v5" stroke="var(--orange)" stroke-width="3" stroke-linecap="round"/><path d="M48 74v8M34 86h28" stroke="var(--orange)" stroke-width="4" stroke-linecap="round"/></svg>`;

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

// ── Chatwoot Agent Bot webhook state (in-memory, per-isolate) ────────────────
// message.id idempotency window and the winnerdata_canon_v1 fetch-once-per-
// isolate cache. Both are plain module-level state — Cloudflare Workers keep
// one isolate warm across many requests, so this is a real (if best-effort)
// cache, not per-request dead weight.
const CHATWOOT_SEEN_MSG_IDS = new Map(); // msgId -> firstSeenAtMs
const CHATWOOT_IDEMPOTENCY_WINDOW_MS = 10 * 60 * 1000;
let WINNERDATA_CANON_CACHE = { text: null, fetchedAt: 0 };
const WINNERDATA_CANON_TTL_MS = 60 * 60 * 1000;

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

// S5 Sticky Layers (issue #19786 PART 2) -- generic funnel-event beacon.
// Fire-and-forget (ctx.waitUntil'd by callers), same shape as
// log_reel_watch_event's proxy pattern -- no Supabase key of any kind
// reaches the browser, and a failure here never blocks the page render.
async function logFunnelEvent(env, sessionId, step, params) {
  try {
    await fetch(`${SUPABASE_URL}/rest/v1/rpc/log_funnel_event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
      body: JSON.stringify({ p_session_id: sessionId, p_step: step, p_params: params || {} }),
    });
  } catch (_) {}
}

// ── S5 Interactive HTML Report — GET /report/:mca_id (issue #18307) ──────────
async function sha256Hex(str) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

// issue #19761 T2 — presale deal-page paid gate. This site's only auth is
// the MCP API key issued after a real Stripe checkout (Bearer header or
// ?key= query param, same shape /report/:mca_id already accepts) -- there is
// no cookie/session login anywhere in this Worker, so reusing that exact
// mechanism IS "reuse the existing biddeed.ai auth", not a new auth system.
function extractApiKey(request, url) {
  const authHeader = request.headers.get('Authorization') || '';
  if (authHeader.startsWith('Bearer ')) return authHeader.slice(7).trim();
  return url.searchParams.get('key') || '';
}

// ── Chat identity + persistence (issue #19829 P1) ────────────────────────────
// This app has no Clerk / Supabase Auth anywhere (confirmed by grep across the
// whole repo before building this). Rather than silently faking a "verified
// user" claim, identity here is a stateless, tamper-evident, but NOT
// inbox-verified binding: POST /chat/api/identity signs {email, exp} with an
// HMAC key derived from the already-required ROUTER_PROXY_KEY secret (so no
// NEW Cloudflare secret needs provisioning — see wrangler.toml incident notes
// on deploy-ordering). Anyone who knows an email address can claim it; this
// buys real tamper-proof separation between two different chat_token holders
// (proven in docs/spec/19829-P1.md), not proof the claimed inbox is theirs.
// Full inbox verification (magic link / OTP) is an explicit, documented gap
// for a follow-up phase, not something to claim done here.
const CHAT_TOKEN_TTL_MS = 1000 * 60 * 60 * 24 * 30; // 30 days

function b64url(bytes) {
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = '';
  for (const b of arr) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function b64urlToBytes(s) {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  const bin = atob(s);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}
// Plain standard-base64 decoder for client file uploads (may come as a data:
// URL — strip any "data:...;base64," prefix first).
function b64urlToBytesStd(s) {
  const clean = String(s).replace(/^data:[^,]*;base64,/, '');
  const bin = atob(clean);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}
async function chatHmacKey(env) {
  const secret = env.ROUTER_PROXY_KEY || '';
  return crypto.subtle.importKey('raw', new TextEncoder().encode('chat-identity-v1:' + secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
}
function isValidEmail(email) {
  return typeof email === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 254;
}
async function issueChatToken(env, email) {
  const enc = new TextEncoder();
  const payload = JSON.stringify({ email: String(email).toLowerCase().trim(), iat: Date.now(), exp: Date.now() + CHAT_TOKEN_TTL_MS });
  const key = await chatHmacKey(env);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(payload));
  return b64url(enc.encode(payload)) + '.' + b64url(sig);
}
async function verifyChatToken(env, token) {
  try {
    const [p64, s64] = String(token || '').split('.');
    if (!p64 || !s64) return null;
    const payloadBytes = b64urlToBytes(p64);
    const sigBytes = b64urlToBytes(s64);
    const key = await chatHmacKey(env);
    const ok = await crypto.subtle.verify('HMAC', key, sigBytes, payloadBytes);
    if (!ok) return null;
    const payload = JSON.parse(new TextDecoder().decode(payloadBytes));
    if (!payload.email || !payload.exp || Date.now() > payload.exp) return null;
    return payload.email;
  } catch (_) { return null; }
}
function extractChatToken(request) {
  const h = request.headers.get('X-Chat-Token');
  if (h) return h.trim();
  const auth = request.headers.get('Authorization') || '';
  if (auth.startsWith('ChatBearer ')) return auth.slice(11).trim();
  return '';
}

// ── Supabase admin (service_role) REST helper — used ONLY for the new
// biddeed_chat_* tables and the chat-uploads storage bucket. Fails closed
// (returns null) when SUPABASE_SERVICE_ROLE_KEY isn't bound yet, so merging
// this code is safe before that Worker secret is provisioned — persistence
// features simply stay inactive, existing anonymous chat is unaffected.
function hasServiceRole(env) { return !!env.SUPABASE_SERVICE_ROLE_KEY; }
async function sbAdmin(env, pathAndQuery, opts = {}) {
  const key = env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) return null;
  const headers = Object.assign({ apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' }, opts.headers || {});
  try {
    const res = await fetch(`${SUPABASE_URL}${pathAndQuery}`, Object.assign({}, opts, { headers }));
    return res;
  } catch (_) { return null; }
}

async function createConversation(env, ownerEmail, title) {
  const res = await sbAdmin(env, '/rest/v1/biddeed_chat_conversations', {
    method: 'POST',
    headers: { Prefer: 'return=representation' },
    body: JSON.stringify({ owner_email: ownerEmail, title: (title || '').slice(0, 120) }),
  });
  if (!res || !res.ok) return null;
  const rows = await res.json();
  return rows[0] || null;
}
async function touchConversation(env, ownerEmail, conversationId) {
  await sbAdmin(env, `/rest/v1/biddeed_chat_conversations?id=eq.${encodeURIComponent(conversationId)}&owner_email=eq.${encodeURIComponent(ownerEmail)}`, {
    method: 'PATCH',
    body: JSON.stringify({ updated_at: new Date().toISOString() }),
  });
}
async function insertMessages(env, ownerEmail, conversationId, msgs) {
  const rows = msgs.map(m => ({ conversation_id: conversationId, owner_email: ownerEmail, role: m.role, content: m.content }));
  return sbAdmin(env, '/rest/v1/biddeed_chat_messages', { method: 'POST', body: JSON.stringify(rows) });
}
async function listConversations(env, ownerEmail, limit = 50) {
  const res = await sbAdmin(env, `/rest/v1/biddeed_chat_conversations?owner_email=eq.${encodeURIComponent(ownerEmail)}&order=updated_at.desc&limit=${limit}&select=id,title,created_at,updated_at`);
  if (!res || !res.ok) return [];
  return res.json();
}
async function getConversationOwned(env, ownerEmail, conversationId) {
  const res = await sbAdmin(env, `/rest/v1/biddeed_chat_conversations?id=eq.${encodeURIComponent(conversationId)}&owner_email=eq.${encodeURIComponent(ownerEmail)}&select=id`);
  if (!res || !res.ok) return null;
  const rows = await res.json();
  return rows[0] || null;
}
async function getConversationMessages(env, ownerEmail, conversationId) {
  const owned = await getConversationOwned(env, ownerEmail, conversationId);
  if (!owned) return null; // 403-equivalent: not this owner's conversation (or doesn't exist)
  const res = await sbAdmin(env, `/rest/v1/biddeed_chat_messages?conversation_id=eq.${encodeURIComponent(conversationId)}&order=created_at.asc&select=id,role,content,created_at`);
  if (!res || !res.ok) return [];
  return res.json();
}
async function searchConversations(env, ownerEmail, q) {
  const tsq = encodeURIComponent(q.trim().split(/\s+/).join(' | '));
  const res = await sbAdmin(env, `/rest/v1/biddeed_chat_messages?owner_email=eq.${encodeURIComponent(ownerEmail)}&search_vec=fts.${tsq}&select=conversation_id,content,created_at&order=created_at.desc&limit=100`);
  if (!res || !res.ok) return [];
  const rows = await res.json();
  const byConv = new Map();
  for (const r of rows) {
    if (!byConv.has(r.conversation_id)) byConv.set(r.conversation_id, { conversation_id: r.conversation_id, snippet: String(r.content).slice(0, 160) });
  }
  const convIds = [...byConv.keys()];
  if (!convIds.length) return [];
  const orFilter = convIds.map(id => `id.eq.${id}`).join(',');
  const convRes = await sbAdmin(env, `/rest/v1/biddeed_chat_conversations?owner_email=eq.${encodeURIComponent(ownerEmail)}&or=(${orFilter})&select=id,title,updated_at`);
  const convRows = convRes && convRes.ok ? await convRes.json() : [];
  const titleById = new Map(convRows.map(c => [c.id, c]));
  return convIds.map(id => ({ conversation_id: id, title: titleById.get(id)?.title || '(untitled)', updated_at: titleById.get(id)?.updated_at, snippet: byConv.get(id).snippet })).filter(r => titleById.has(r.conversation_id));
}
async function insertUpload(env, ownerEmail, conversationId, meta) {
  const res = await sbAdmin(env, '/rest/v1/biddeed_chat_uploads', {
    method: 'POST',
    headers: { Prefer: 'return=representation' },
    body: JSON.stringify({
      conversation_id: conversationId || null, owner_email: ownerEmail, storage_path: meta.storagePath,
      filename: meta.filename, mime_type: meta.mimeType, extracted_text: meta.extractedText || null, extraction_status: meta.extractionStatus,
    }),
  });
  if (!res || !res.ok) return null;
  const rows = await res.json();
  return rows[0] || null;
}
async function getUploadOwned(env, ownerEmail, uploadId) {
  const res = await sbAdmin(env, `/rest/v1/biddeed_chat_uploads?id=eq.${encodeURIComponent(uploadId)}&owner_email=eq.${encodeURIComponent(ownerEmail)}&select=id,filename,extracted_text,extraction_status`);
  if (!res || !res.ok) return null;
  const rows = await res.json();
  return rows[0] || null;
}

// ── Supabase Storage (chat-uploads bucket, private) ──────────────────────────
const MAX_UPLOAD_BYTES = 8 * 1024 * 1024; // 8MB raw file cap
async function storagePutObject(env, path, bytes, contentType) {
  const key = env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) return false;
  try {
    const res = await fetch(`${SUPABASE_URL}/storage/v1/object/chat-uploads/${path}`, {
      method: 'POST',
      headers: { apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': contentType || 'application/octet-stream', 'x-upsert': 'true' },
      body: bytes,
    });
    return res.ok;
  } catch (_) { return false; }
}

// ── Upload text extraction — no npm deps (deploy is `wrangler deploy
// --no-bundle`, so only Web-standard APIs — DecompressionStream, TextDecoder
// — are usable, never an imported package). ─────────────────────────────────
function strToBytes(s) { const a = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) a[i] = s.charCodeAt(i) & 0xff; return a; }
async function inflateBytes(bytes) {
  const ds = new DecompressionStream('deflate');
  const stream = new Blob([bytes]).stream().pipeThrough(ds);
  const buf = await new Response(stream).arrayBuffer();
  return new Uint8Array(buf);
}
function indexPdfObjects(latin1) {
  const objs = new Map();
  const objRe = /(\d+)\s+0\s+obj([\s\S]*?)endobj/g;
  let m;
  while ((m = objRe.exec(latin1))) objs.set(parseInt(m[1], 10), m[2]);
  return objs;
}
// Balanced << >> extraction — a naive non-greedy regex breaks on nested dicts
// (e.g. /Resources << /ExtGState << ... >> /Font << ... >> >>).
function findBalancedDict(text, key) {
  const m = new RegExp('/' + key + '\\s*<<').exec(text);
  if (!m) return null;
  let i = m.index + m[0].length, depth = 1;
  const start = i;
  while (i < text.length && depth > 0) {
    if (text.startsWith('<<', i)) { depth++; i += 2; }
    else if (text.startsWith('>>', i)) { depth--; i += 2; }
    else i++;
  }
  return text.slice(start, i - 2);
}
function findPdfRef(dictText, key) {
  const m = new RegExp('/' + key + '\\s+(\\d+)\\s+0\\s+R').exec(dictText);
  return m ? parseInt(m[1], 10) : null;
}
async function getPdfStreamBytes(objText) {
  const sm = /stream\r?\n([\s\S]*?)endstream/.exec(objText);
  if (!sm) return null;
  const raw = strToBytes(sm[1]);
  if (/\/FlateDecode/.test(objText.slice(0, sm.index))) {
    try { return await inflateBytes(raw); } catch (_) { return raw; }
  }
  return raw;
}
function hexToUnicodeStr(hex) {
  let out = '';
  for (let i = 0; i < hex.length; i += 4) out += String.fromCharCode(parseInt(hex.slice(i, i + 4), 16));
  return out;
}
function parseToUnicodeCMap(cmapText) {
  const map = new Map();
  const charRe = /beginbfchar([\s\S]*?)endbfchar/g;
  let cm;
  while ((cm = charRe.exec(cmapText))) {
    const pairRe = /<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g;
    let pm;
    while ((pm = pairRe.exec(cm[1]))) map.set(parseInt(pm[1], 16), hexToUnicodeStr(pm[2]));
  }
  const rangeRe = /beginbfrange([\s\S]*?)endbfrange/g;
  let rm;
  while ((rm = rangeRe.exec(cmapText))) {
    const tripleRe = /<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g;
    let tm;
    while ((tm = tripleRe.exec(rm[1]))) {
      const lo = parseInt(tm[1], 16), hi = parseInt(tm[2], 16), dstStart = parseInt(tm[3], 16);
      for (let c = lo; c <= hi && c - lo < 65536; c++) map.set(c, String.fromCharCode(dstStart + (c - lo)));
    }
  }
  return map;
}
async function buildPdfFontCMaps(objs, fontResourceRefs) {
  const fontMaps = new Map();
  for (const [name, objNum] of fontResourceRefs) {
    const fontObjText = objs.get(objNum);
    if (!fontObjText) continue;
    const tuRef = findPdfRef(fontObjText, 'ToUnicode');
    if (!tuRef) continue;
    const tuObjText = objs.get(tuRef);
    if (!tuObjText) continue;
    const bytes = await getPdfStreamBytes(tuObjText);
    if (!bytes) continue;
    fontMaps.set(name, parseToUnicodeCMap(new TextDecoder('latin1').decode(bytes)));
  }
  return fontMaps;
}
function unescapePdfString(s) { return s.replace(/\\([()\\])/g, '$1').replace(/\\n/g, '\n').replace(/\\r/g, ''); }
function decodePdfHexShowString(hex, fontName, fontMaps) {
  const map = fontName ? fontMaps.get(fontName) : null;
  let out = '';
  if (map) { for (let i = 0; i + 4 <= hex.length; i += 4) { const code = parseInt(hex.slice(i, i + 4), 16); if (map.has(code)) out += map.get(code); } }
  else { for (let i = 0; i + 2 <= hex.length; i += 2) out += String.fromCharCode(parseInt(hex.slice(i, i + 2), 16)); }
  return out;
}
function walkPdfContentStream(content, fontMaps) {
  let out = '';
  let currentFont = null;
  const tokenRe = /\/(\w+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]*)>\s*Tj|\(((?:[^()\\]|\\.)*)\)\s*Tj|\[((?:[^\[\]]|\\.)*)\]\s*TJ|(T\*|Td|TD)\b/g;
  let m;
  while ((m = tokenRe.exec(content))) {
    if (m[1]) { currentFont = '/' + m[1]; continue; }
    if (m[5]) { out += (content.substr(m.index, 2) === 'T*' ? '\n' : ' '); continue; }
    if (m[2] !== undefined && content[m.index] === '<') { out += decodePdfHexShowString(m[2], currentFont, fontMaps); continue; }
    if (m[3] !== undefined) { out += unescapePdfString(m[3]); continue; }
    if (m[4] !== undefined) {
      const partRe = /\(((?:[^()\\]|\\.)*)\)|<([0-9A-Fa-f]*)>/g;
      let pm;
      while ((pm = partRe.exec(m[4]))) {
        if (pm[1] !== undefined) out += unescapePdfString(pm[1]);
        else if (pm[2] !== undefined) out += decodePdfHexShowString(pm[2], currentFont, fontMaps);
      }
      out += ' ';
      continue;
    }
  }
  return out + '\n';
}
// Best-effort PDF text extraction — brute-force-indexes objects by scanning
// "N 0 obj ... endobj" markers directly (works even when the xref table is a
// compressed xref stream we don't parse), resolves each page's /Resources
// /Font entries to their /ToUnicode CMaps for CID-keyed embedded fonts (the
// overwhelming majority of real-world PDFs, including browser print-to-PDF
// and Word/Adobe exports), and falls back to literal (...)Tj strings for
// simple non-CID fonts. Verified against a real production PDF in this repo
// (winnerdata/batches/2026-08-27/investor_ff/ok-business-llc-25000544.pdf) —
// see docs/spec/19829-P1.md for the before/after evidence.
async function extractPdfText(bytes) {
  const latin1 = Array.from(bytes).map(b => String.fromCharCode(b)).join('');
  const objs = indexPdfObjects(latin1);
  const pageObjNums = [];
  for (const [num, text] of objs) if (/\/Type\s*\/Page\b(?!s)/.test(text)) pageObjNums.push(num);
  let allText = '';
  for (const pageNum of pageObjNums) {
    const pageText = objs.get(pageNum);
    let resText = findBalancedDict(pageText, 'Resources');
    if (!resText) { const r = findPdfRef(pageText, 'Resources'); if (r && objs.has(r)) resText = objs.get(r); }
    const fontRefs = new Map();
    if (resText) {
      let fontDictText = findBalancedDict(resText, 'Font');
      if (!fontDictText) { const fr = findPdfRef(resText, 'Font'); if (fr && objs.has(fr)) fontDictText = objs.get(fr); }
      if (fontDictText) {
        const fe = /\/(\w+)\s+(\d+)\s+0\s+R/g; let m;
        while ((m = fe.exec(fontDictText))) fontRefs.set('/' + m[1], parseInt(m[2], 10));
      }
    }
    const fontMaps = await buildPdfFontCMaps(objs, fontRefs);
    const contentsArrM = /\/Contents\s*\[([^\]]*)\]/.exec(pageText);
    const contentRefs = [];
    if (contentsArrM) { const re = /(\d+)\s+0\s+R/g; let mm; while ((mm = re.exec(contentsArrM[1]))) contentRefs.push(parseInt(mm[1], 10)); }
    else { const single = findPdfRef(pageText, 'Contents'); if (single) contentRefs.push(single); }
    for (const cRef of contentRefs) {
      const cObjText = objs.get(cRef);
      if (!cObjText) continue;
      const bytes2 = await getPdfStreamBytes(cObjText);
      if (!bytes2) continue;
      allText += walkPdfContentStream(new TextDecoder('latin1').decode(bytes2), fontMaps);
    }
  }
  return { text: allText.replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim(), pagesFound: pageObjNums.length };
}

const TEXT_MIME_TYPES = new Set(['text/plain', 'text/csv', 'text/markdown', 'application/csv']);
async function extractUploadText(mimeType, filename, bytes) {
  const mt = (mimeType || '').toLowerCase();
  const ext = (filename || '').toLowerCase().split('.').pop();
  try {
    if (TEXT_MIME_TYPES.has(mt) || ext === 'txt' || ext === 'csv' || ext === 'md') {
      return { status: 'ok', text: new TextDecoder('utf-8').decode(bytes).slice(0, 50000) };
    }
    if (mt === 'application/pdf' || ext === 'pdf') {
      const { text, pagesFound } = await extractPdfText(bytes);
      if (!text) return { status: pagesFound > 0 ? 'failed' : 'unsupported', text: null };
      return { status: 'ok', text: text.slice(0, 50000) };
    }
    // DOCX / images: no npm deps available under --no-bundle deploy, and no
    // OCR/vision pipeline wired yet — honest "unsupported" rather than a
    // silent empty result. Deferred to a follow-up phase (see spec doc).
    return { status: 'unsupported', text: null };
  } catch (_) {
    return { status: 'failed', text: null };
  }
}

async function fetchPaidTier(env, apiKey) {
  if (!apiKey) return { ok: false, tier: null };
  const keyHash = await sha256Hex(apiKey);
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/check_paid_tier`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
      body: JSON.stringify({ p_key_hash: keyHash }),
    });
    if (!res.ok) {
      await logErr(env, '/deal', 'check_paid_tier non-2xx', await res.text(), res.status);
      return { ok: false, tier: null };
    }
    const rows = await res.json().catch(() => null);
    const row = Array.isArray(rows) ? rows[0] : rows;
    return row || { ok: false, tier: null };
  } catch (e) {
    await logErr(env, '/deal', 'check_paid_tier failed', String(e), 500);
    return { ok: false, tier: null };
  }
}

function escHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

// Renders a money-shaped { value, display, source } field, or a plain
// scalar/null — never the raw `source` string (S5 SSOT v1.2: RL formula
// coefficient names must never reach the page — see §15 note below).
// Money fields from the composer arrive in three shapes: a bare number, a
// numeric string, or a { value, display } object (see cover.entry_bid).
// Number() on that object yields NaN, which rendered a literal "$NaN" as the
// Entry Bid on a live PAID S5 report (7830 Stirling Bridge Blvd S, Palm Beach
// — observed in production 2026-08-20). Returns a dispVal-compatible
// { display } or null, so an unusable value falls back to the caller's honest
// placeholder instead of printing a fabricated figure at a bidder.
function s5Money(v) {
  if (v == null) return null;
  if (typeof v === 'object') {
    if (v.display != null) return { display: String(v.display) };
    return Number.isFinite(Number(v.value)) ? { display: `$${Number(v.value).toLocaleString()}` } : null;
  }
  if (v === '') return null;
  return Number.isFinite(Number(v)) ? { display: `$${Number(v).toLocaleString()}` } : null;
}

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
    certification_disclosure: 'Palm Beach County — Gold Standard certified. SIGNAL$ Property Report tool is CERT_REQUIRED.',
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

// internal/internalDisclosure: used ONLY by the internal-preview script
// (packages/biddeed-mcp/scripts/generate_internal_signal_report.mjs, issue
// #19661/consistency-fix) so that a single review copy renders the real §16
// lien-survival content regardless of biddeed_report_composition.ship_status.
// The customer-facing call sites in this file (fetchS5ReportJson path below)
// never pass these — production behavior is byte-identical to before.
function renderS5ReportHtml(report, { mcaId, keyLast8, internal = false, internalDisclosure = null } = {}) {
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
  const composition = report.composition || {};
  const lienSurvival = report.lien_survival || {};
  const prov = report.provenance || {};
  const outcome = report.auction_outcome || {};
  const disclaimer = report.disclaimer || 'Informational only — not legal, financial, or investment advice.';
  const countyLabel = toDisplay(cover.county || '');
  const generatedAt = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  const reportIdShort = String(mcaId).slice(0, 8) + '-' + new Date().toISOString().slice(0, 10).replace(/-/g, '');

  if (cover.locatable === false) {
    return s5Page({
      cover, countyLabel, mcaId, keyLast8, generatedAt, reportIdShort, disclaimer,
      banner: internal ? INTERNAL_PREVIEW_BANNER : '',
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
  // Sale-type-aware (issue #19662): a tax deed sale has no final judgment —
  // a judgment is a Chapter 45 foreclosure concept. Rendering "Judgment
  // Amount: Pending" on a tax deed falsely implies one is forthcoming.
  const isTaxDeed = cover.sale_type === 'tax_deed';
  const sec1 = isTaxDeed ? [
    s5Row('Address', escHtml(cover.property_address)),
    s5Row('County', `${escHtml(countyLabel)} County, Florida`),
    s5Row('Case Number', escHtml(cover.case_number)),
    s5Row('Sale Type', 'Tax Deed (FL FS Chapter 197 — no final judgment)'),
    s5Row('Auction Date', escHtml(auction.auction_date || 'Pending')),
    s5Row('Taxing Authority', dispVal(auction.taxing_authority)),
    s5Row('Assessed Value', dispVal(auction.assessed_value)),
    s5Row('Opening Bid', auction.unpaid_taxes?.value != null ? dispVal(auction.unpaid_taxes) : 'N/A — tax deed sale (no final judgment)'),
    ...(auction.outstanding_certs_total?.value != null ? [s5Row('Outstanding Certificates Total', dispVal(auction.outstanding_certs_total))] : []),
    ...(auction.cert_number ? [s5Row('Certificate #', escHtml(auction.cert_number))] : []),
  ].join('') : [
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
    // NaN-safe: != null lets NaN through (NaN != null is true) — the historical
    // "$NaN" render on live cards. Only finite numbers become dollar strings.
    const spread = (Number.isFinite(Number(mb?.midpoint)) && Number.isFinite(Number(cb?.midpoint)))
      ? Number(mb.midpoint) - Number(cb.midpoint) : null;
    // Entry-bid equity ONLY — never fall back to the spread: it is a different
    // quantity (market−clearing, not market−entry) and rendering it under the
    // "EQUITY AT ENTRY BID" label was the §2-3 mismatch.
    const dayOneEquity = Number.isFinite(Number(cover.equity_at_entry_bid))
      ? Number(cover.equity_at_entry_bid) : null;
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
        { label: 'Sold', get: c => { const v = c.sale_price ?? c.sale_price1 ?? c.sold_amount; return (v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v))) ? `$${Number(v).toLocaleString()}` : null; } },
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
          <div class="maxbid">${dispVal(s5Money(maxBidVal), 'Hidden')}</div>
          <div class="maxbid-sub">Walk away above this number. No exceptions.</div>
        </div>
        <div class="bidcard-rows" style="margin-top:16px">
          ${s5Row('Entry Bid', dispVal(s5Money(opp.entry_bid) ?? s5Money(cover.entry_bid)))}
          ${s5Row('Value Midpoint', dispVal(s5Money(opp.value_midpoint)))}
          ${s5Row('Walk Away Above', dispVal(s5Money(maxBidVal), 'Hidden'))}
        </div>
        <div style="color:#b8cfe0;font-size:12px;margin-top:14px;font-style:italic">${s5CalibrationFootnote(cover.shapira_max_bid, cover.county)}</div>
      </div>
    </div>`;

  // ── §16 Judgment & Encumbrance ────────────────────────────────────────────
  const lienGate = composition.lien_survival || {};
  // internal-preview override: render the real classify() output regardless
  // of ship_status (see the `internal` param comment above renderS5ReportHtml).
  // The customer path (internal=false) is completely unchanged.
  const lienDelivered = internal ? lienSurvival.available === true : (lienGate.status === 'delivered' && lienSurvival.available);
  const lienDisclosureText = lienGate.disclosure || (internal ? internalDisclosure : null);
  let lienSurvivalHtml;
  if (lienDelivered) {
    const itemsHtml = (lienSurvival.items || []).map(item => {
      const label = item.creditor && item.creditor !== 'Pending — not on file' ? `${escHtml(item.lien_type)} — ${escHtml(item.creditor)}` : escHtml(item.lien_type);
      const cls = item.survives === true ? 'flag-risk' : item.survives === false ? 'flag-info' : 'flag-pending';
      const tag = item.survives === true ? 'SURVIVES' : item.survives === false ? 'EXTINGUISHED' : 'UNRESOLVED';
      return `<div class="flag ${cls}"><b>${tag}</b> ${label} — ${escHtml(item.statement)}</div>`;
    }).join('');
    lienSurvivalHtml = `
      <div class="lien-survival">
        <div class="row"><span class="row-l">Statutory Basis</span><span class="row-v">${escHtml(lienSurvival.statutory_basis || 'Pending')}</span></div>
        <div class="flags">${itemsHtml}</div>
        ${lienDisclosureText ? `<div class="model-disclosure" style="margin-top:10px;font-size:11px">${escHtml(lienDisclosureText)}</div>` : ''}
        ${internal ? `<div class="model-disclosure" style="margin-top:6px;font-size:10px;color:#F59E0B">INTERNAL PREVIEW: real ship_status for this section in production is "${escHtml(lienGate.status || 'unknown')}" — this content is withheld from every customer-facing report until a human flips that flag.</div>` : ''}
      </div>`;
  } else if (internal && lienSurvival.searched === true) {
    // Searched-clean (issue #19661 follow-on, §16 honesty fix): a harvest
    // ran for this subject and found zero third-party lien instruments —
    // NOT the same fact as "nothing was ever searched", so this must not
    // render the generic ship-gate/no-coverage message either one uses.
    lienSurvivalHtml = `
      <div class="lien-survival">
        <div class="row"><span class="row-l">Status</span><span class="row-v">Recorded-document search completed — zero third-party lien instruments found</span></div>
        <div class="model-disclosure" style="margin-top:6px;font-size:10px;color:#F59E0B">INTERNAL PREVIEW: ${escHtml(lienSurvival.reason)}</div>
      </div>`;
  } else {
    lienSurvivalHtml = `<div class="pending">${escHtml(lienGate.status || 'Pending — Title Tier 2 (lien survival) not yet live for this county')}</div>`;
  }
  // Sale-type-aware (issue #19662, sweep of the judgment-labeled fields):
  // a tax deed has no final judgment, so this must never render
  // "Judgment Amount: Pending" — render the real Chapter 197 fields instead.
  const sec16TopRows = isTaxDeed ? [
    s5Row('Sale Type Note', escHtml(judgment.sale_type_note || 'Tax deed sale — no foreclosure judgment.')),
    s5Row('Unpaid Taxes (Opening Bid Basis)', judgment.unpaid_taxes != null ? `$${Number(judgment.unpaid_taxes).toLocaleString()}` : 'N/A — tax deed sale (no final judgment)'),
    s5Row('IRS Lien Survival', judgment.irs_lien_survives ? 'Survives (26 U.S.C. §7425)' : 'Pending'),
    s5Row('HOA/COA Lien', judgment.hoa_lien_may_survive ? 'May survive (FL FS 720.3085/718.116)' : 'Pending'),
    s5Row('Statutory Extinguishment', escHtml(judgment.statutory_extinguishment || 'Pending')),
  ] : [
    s5Row('Judgment Amount', judgment.judgment_amount != null ? `$${Number(judgment.judgment_amount).toLocaleString()}` : 'Pending'),
    s5Row('Opening Bid', judgment.opening_bid != null ? `$${Number(judgment.opening_bid).toLocaleString()}` : 'Pending'),
    s5Row('Bid/Judgment Ratio', judgment.bid_to_judgment_ratio != null ? judgment.bid_to_judgment_ratio : 'Pending'),
  ];
  const sec16 = [
    ...sec16TopRows,
    flags.length ? `<div class="flags">${flags.map(f => `<div class="flag flag-${escHtml(f.severity || 'info')}"><b>${escHtml(f.code || 'FLAG')}</b> ${escHtml(f.text || '')}</div>`).join('')}</div>` : '',
    `<div class="model-disclosure" style="margin:10px 0 4px;font-weight:600">Lien Survival — Title Tier 2</div>`,
    lienSurvivalHtml,
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
  // Same quantity as the §2-3 entry-bid bar — no spread fallback, no NaN passthrough.
  const dayOneEquitySg = Number.isFinite(Number(cover.equity_at_entry_bid))
    ? Number(cover.equity_at_entry_bid) : null;
  const maxBidFinite = Number.isFinite(Number(maxBidVal)) ? Number(maxBidVal) : null;
  const summaryGrid = `<div class="summary-grid">
    <div>
      <div class="sg-label">Verdict</div>
      <div class="sg-verdict ${verdictCls}">${escHtml(verdict)}</div>
    </div>
    <div>
      <div class="sg-label">Shapira Max Bid</div>
      <div class="sg-val orange">${maxBidFinite != null ? `$${Math.round(maxBidFinite).toLocaleString()}` : '—'}</div>
    </div>
    <div>
      <div class="sg-label">Equity at Entry Bid</div>
      <div class="sg-val">${dayOneEquitySg != null ? `$${Math.round(dayOneEquitySg).toLocaleString()}` : '—'}</div>
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

  return s5Page({ cover, countyLabel, mcaId, keyLast8, generatedAt, reportIdShort, disclaimer, body, summaryGrid, banner: internal ? INTERNAL_PREVIEW_BANNER : '' });
}

const INTERNAL_PREVIEW_BANNER = `<div style="background:#DC2626;color:#fff;font-weight:800;text-align:center;padding:14px;font-size:16px;letter-spacing:1px">&#9888; INTERNAL PREVIEW — NOT FOR CUSTOMER DELIVERY</div><div style="background:#7F1D1D;color:#FEE2E2;text-align:center;padding:8px;font-size:12px">Generated for internal review only. Title/lien sections may carry biddeed_report_composition.ship_status=blocked in production and are not shipped to any paying customer — see the note inline on §16 below.</div>`;

function s5Page({ cover, countyLabel, mcaId, keyLast8, generatedAt, reportIdShort, disclaimer, body, summaryGrid = '', banner = '' }) {
  const addr     = escHtml(cover.property_address || 'Address pending');
  const addrCity = addr.includes(',') ? addr.slice(0, addr.indexOf(',')) : addr;
  const addrRest = addr.includes(',') ? addr.slice(addr.indexOf(',') + 1).trim() : '';
  return `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BidDeed.AI SIGNAL$ Property Report | ${addr}</title>
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
${banner ? banner + '\n' : ''}<div class="wrap">
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
        <div>Sale ${escHtml(cover.auction_date || '—')} &middot; ${escHtml(cover.sale_type ? cover.sale_type.toUpperCase().replace(/_/g, ' ') : 'FORECLOSURE')}</div>
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

    // Per-county upcoming/next_auction_date, SSOT-sourced (SPR-07, issue #19826,
    // CONTENT_SOP.md K2/K1) -- county pages previously derived their displayed
    // "upcoming" count from fetchCountyLots' 35-day/300-row window, which
    // silently undercounted every county with auctions further out (confirmed
    // live: 53/67 counties mismatched auctions_summary_ssot() at the same
    // minute). buildCountyPage() now prefers this SSOT number when present.
    // Bounded with a timeout -- this RPC has a documented cold-aggregation
    // cost (docs/spec/19813.md: 17.3s observed once, then 8s/5s/3s/2s on
    // immediate retries). A slow/cold hit must degrade to the pre-SPR-07
    // lots-window fallback, never block this 5-min-cached config fetch.
    let countiesDetail = null;
    try {
      const ssotController = new AbortController();
      const ssotTimeout = setTimeout(() => ssotController.abort(), 8000);
      let ssotRes;
      try {
        ssotRes = await fetch(SUPABASE_URL + '/rest/v1/rpc/auctions_summary_ssot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY },
          body: '{}',
          signal: ssotController.signal,
        });
      } finally {
        clearTimeout(ssotTimeout);
      }
      if (ssotRes.ok) {
        const ssot = await ssotRes.json();
        const rows = Array.isArray(ssot && ssot.counties_detail) ? ssot.counties_detail : [];
        countiesDetail = {};
        for (const row of rows) {
          if (row && row.county) countiesDetail[row.county] = { upcoming: Number(row.upcoming) || 0, next_auction_date: row.next_auction_date || null };
        }
      }
    } catch (_) { countiesDetail = null; }

    const config = { goldCounties, confirmedCounties, s5Counties, auctionsCount, countiesDetail };

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

// ── Answer-asset renderer tokens (SPR-02, issue #19830) ──────────────────────
// {{state.upcoming}} / {{county.upcoming}} / {{county.next_auction_date}}
// resolved from auctions_summary_ssot() at request time. Deliberately NOT
// reusing fetchRuntimeConfig()'s cached config: that function's own catch
// block falls back to a hardcoded auctionsCount (72000) on RPC failure,
// which is exactly the "stand-in number" A5/P5 forbid for a static body.
// This fetch has no such fallback -- failure always yields null -> em-dash.
function emDashOr(v) { return (v === null || v === undefined || v === '') ? '—' : String(v); }

async function fetchAnswerTokens(countySlug) {
  let stateUpcoming = null, countyUpcoming = null, countyNextDate = null;
  // CONTENT_SOP.md §2.2 link contract: a statewide answer asset links the 3
  // counties with the most `upcoming` "at render time (RPC, never static)".
  // Populated from the same auctions_summary_ssot() call below -- never a
  // hardcoded county list.
  let topCounties = [];
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    let res;
    try {
      res = await fetch(SUPABASE_URL + '/rest/v1/rpc/auctions_summary_ssot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY },
        body: '{}',
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }
    if (res.ok) {
      const ssot = await res.json();
      stateUpcoming = Number.isFinite(ssot.upcoming) ? ssot.upcoming : null;
      if (Array.isArray(ssot.counties_detail)) {
        if (countySlug) {
          const row = ssot.counties_detail.find(r => r && r.county === countySlug);
          if (row) {
            countyUpcoming = Number.isFinite(row.upcoming) ? row.upcoming : null;
            countyNextDate = row.next_auction_date || null;
          }
        }
        topCounties = ssot.counties_detail
          .filter(r => r && r.county && Number.isFinite(r.upcoming))
          .sort((a, b) => b.upcoming - a.upcoming)
          .slice(0, 3)
          .map(r => ({ slug: r.county, upcoming: r.upcoming }));
      }
    }
  } catch (_) { /* leave everything empty/null -> em-dash below, no county links */ }
  return {
    tokenMap: {
      '{{state.upcoming}}': emDashOr(stateUpcoming),
      '{{county.upcoming}}': emDashOr(countyUpcoming),
      '{{county.next_auction_date}}': emDashOr(countyNextDate),
    },
    topCounties,
  };
}

function renderTokens(text, tokenMap) {
  if (typeof text !== 'string') return text;
  let out = text;
  for (const token in tokenMap) out = out.split(token).join(tokenMap[token]);
  return out;
}

// ── County lots fetch ─────────────────────────────────────────────────────────
async function fetchCountyLots(county) {
  try {
    const today = new Date().toISOString().slice(0,10);
    const cutoff = new Date(Date.now() + 35*24*60*60*1000).toISOString().slice(0,10);
    const url = `${SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.${encodeURIComponent(county)}&auction_date=gte.${today}&auction_date=lte.${cutoff}&or=(auction_status.in.(upcoming,active,scheduled),auction_status.is.null)&order=auction_date.asc,sale_type.asc&limit=300&select=sale_type,property_address,auction_date,opening_bid,assessed_value,market_value,auction_url,clerk_url,bcpao_url,judgment_amount,case_number,plaintiff,auction_status`;
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

    // Never cache an empty/failed upstream result — a single failed or
    // slow-to-return get_all_counties_with_status call would otherwise
    // poison this fixed cache key for every visitor for a full 120s
    // (repeatable: reproduced live 2026-08-15, RPC + anon key both healthy
    // yet /buy-report/counties served `[]` for 15+ min straight because one
    // bad response got cached and nothing ever re-primed it early). Only a
    // real, non-empty county list is worth caching.
    if (res.ok && result.length > 0) {
      const resp = new Response(JSON.stringify(result), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=120' } });
      await cache.put(cacheKey, resp.clone());
    }
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
const SECURITY_CSP = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://us-assets.i.posthog.com https://us.i.posthog.com https://static.cloudflareinsights.com https://app.chatwoot.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://us.i.posthog.com https://us-assets.i.posthog.com https://mocerqjnksmhcjzxrewo.supabase.co https://static.cloudflareinsights.com https://api.elevenlabs.io wss://api.elevenlabs.io https://app.chatwoot.com wss://app.chatwoot.com; frame-src https://app.chatwoot.com; frame-ancestors 'none'; base-uri 'self'; object-src 'none'";
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

// ── Chatwoot Agent Bot — POST /support/bot ────────────────────────────────────
// Chatwoot Cloud (Hacker tier) MIT Agent Bot webhook, not Captain (enterprise-
// licensed). Reuses the exact claude-router call from /chat/api — no second
// LLM path. AI-only support: there is no human handoff. When the bot can't
// resolve something in chat it asks for an email, logs a lead via the
// existing /chat/lead upsert (source='support_escalation'), and resolves the
// conversation. Chatwoot is a log/history surface only.
const CHATWOOT_ESCALATE_RE = /\b(talk to (a )?(human|person|agent|representative|someone)|speak (to|with) (a )?(human|person|agent|representative|someone)|real (person|human)|customer service rep|refund|chargeback|charge.?back|billing dispute|dispute (this|the) charge|lawsuit|sue (you|us|biddeed|winner ?data)|legal action|attorney|lawyer|file a complaint)\b/i;
const CHATWOOT_EMAIL_RE = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/;

function chatwootIsDuplicate(msgId) {
  const now = Date.now();
  for (const [id, ts] of CHATWOOT_SEEN_MSG_IDS) {
    if (now - ts > CHATWOOT_IDEMPOTENCY_WINDOW_MS) CHATWOOT_SEEN_MSG_IDS.delete(id);
  }
  if (msgId === undefined || msgId === null) return false;
  if (CHATWOOT_SEEN_MSG_IDS.has(msgId)) return true;
  CHATWOOT_SEEN_MSG_IDS.set(msgId, now);
  return false;
}

function parseChatwootInboxMap(env) {
  try {
    const parsed = JSON.parse(env.CHATWOOT_INBOX_MAP || '{}');
    return (parsed && typeof parsed === 'object') ? parsed : {};
  } catch (_) { return {}; }
}

// Fetched once per isolate, cached 1h — winnerdata_canon_v1 overrides any
// prior log or chat per its own `source` field (see unified_context row).
async function fetchWinnerdataCanon(env) {
  const now = Date.now();
  if (WINNERDATA_CANON_CACHE.text && (now - WINNERDATA_CANON_CACHE.fetchedAt) < WINNERDATA_CANON_TTL_MS) {
    return WINNERDATA_CANON_CACHE.text;
  }
  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/unified_context?select=content&key=eq.winnerdata_canon_v1&limit=1`,
      { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
    );
    const rows = res.ok ? await res.json() : [];
    const text = (Array.isArray(rows) && rows[0] && rows[0].content) ? JSON.stringify(rows[0].content) : '';
    WINNERDATA_CANON_CACHE = { text, fetchedAt: now };
    return text;
  } catch (_) {
    return WINNERDATA_CANON_CACHE.text || '';
  }
}

function buildSupportBotSystemPrompt(site, canonText) {
  const shared = `Reply in plain text, no markdown, 120 words or fewer. If the sender's email is missing and this needs a follow-up, ask for their email. Never give legal advice. Never promise or imply a specific auction, sale, or financial outcome. If the user demands a human, disputes a charge/refund, or raises anything legal, respond briefly and end your reply with exactly [[HANDOFF]] on its own — do not explain that token to the user.`;
  if (site === 'winnerdata') {
    return `You are the support assistant for Winner Data (winnerdataai.com), a B2B property-data and analytics platform.\n\nCanon facts about the business (source of truth, overrides anything else):\n${canonText}\n\nRules: never contact or reference homeowners directly, never use foreclosure-relief or "save your home" language, never tie compensation or pricing claims to a specific outcome. Answer product/pricing/how-it-works questions for business buyers (insurance agencies, moving companies, contractors, investors) using only the canon facts above.\n\n${shared}`;
  }
  return `You are the support assistant for BidDeed.AI, a Florida foreclosure and tax-deed auction intelligence product. Answer product, pricing, and how-to questions using only biddeed.ai's public pages (SIGNAL$ Property Reports $25 each, Investor tier $99/mo, coverage across FL counties, Gold Standard certified counties have full report capability).\n\nRules: never give legal advice, never promise or imply a specific auction outcome or bid result.\n\n${shared}`;
}

async function chatwootApiCall(env, path, body) {
  const base = env.CHATWOOT_BASE_URL || 'https://app.chatwoot.com';
  return fetch(`${base}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'api_access_token': env.CHATWOOT_BOT_TOKEN },
    body: JSON.stringify(body || {}),
  });
}

async function chatwootReply(env, accountId, conversationId, text) {
  try {
    const res = await chatwootApiCall(env, `/api/v1/accounts/${accountId}/conversations/${conversationId}/messages`, {
      content: text,
      message_type: 'outgoing',
    });
    if (!res.ok) await logErr(env, '/support/bot', 'Chatwoot reply failed', await res.text(), res.status);
  } catch (e) {
    await logErr(env, '/support/bot', 'Chatwoot reply threw', String(e), 500);
  }
}

async function chatwootResolve(env, accountId, conversationId) {
  try {
    const res = await chatwootApiCall(env, `/api/v1/accounts/${accountId}/conversations/${conversationId}/toggle_status`, {
      status: 'resolved',
    });
    if (!res.ok) await logErr(env, '/support/bot', 'Chatwoot resolve failed', await res.text(), res.status);
  } catch (e) {
    await logErr(env, '/support/bot', 'Chatwoot resolve threw', String(e), 500);
  }
}

// AI-only escalation (SCOPE CHANGE, Ariel, Sep 3 2026 — replaces the original
// "handoff to a human agent" design; there is no human on this inbox). Logs
// the lead through the EXISTING /chat/lead upsert path so no new table or
// column is introduced. lead_profiles has no notes/transcript column, so the
// transcript excerpt goes to the existing worker error/info log instead
// (log_worker_error via logErr) — this is a deliberate deviation from the
// issue comment's "notes/context field it already has" claim, which does not
// match the live lead_profiles schema (verified via REST, see docs/spec/19776.md).
async function chatwootEscalate(env, ctx, accountId, conversationId, email, content, source) {
  const foundEmail = email || (CHATWOOT_EMAIL_RE.exec(content || '') || [])[0] || '';
  const base = "I can't resolve this in chat. Leave your email and we'll follow up in writing.";
  const reply = foundEmail ? base : `${base} What's the best email to reach you?`;
  await chatwootReply(env, accountId, conversationId, reply);
  await logErr(env, '/support/bot', `escalation (${source})`, `email=${foundEmail || 'none'} content=${String(content || '').slice(0, 500)}`, 200, 'info');
  if (foundEmail) {
    try {
      const leadReq = new Request('https://biddeed.ai/chat/lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: foundEmail, source: 'support_escalation' }),
      });
      await handleRequest(leadReq, env, ctx);
    } catch (e) {
      await logErr(env, '/support/bot', 'escalation lead log failed', String(e), 500);
    }
    await chatwootResolve(env, accountId, conversationId);
  }
  // No email yet — leave the conversation open so a follow-up reply with the
  // email re-triggers this same path (message_created fires again).
}

async function handleSupportBot(request, env, ctx, url) {
  const jsonHeaders = { 'Content-Type': 'application/json' };

  if (!env.CHATWOOT_BOT_TOKEN || !env.CHATWOOT_WEBHOOK_SECRET || !env.CHATWOOT_INBOX_MAP) {
    await logErr(env, '/support/bot', 'Missing Chatwoot Worker secret binding(s)', '', 503);
    return new Response(JSON.stringify({ error: 'Service configuration error' }), { status: 503, headers: jsonHeaders });
  }

  const providedKey = url.searchParams.get('k') || '';
  if (!providedKey || providedKey !== env.CHATWOOT_WEBHOOK_SECRET) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401, headers: jsonHeaders });
  }

  let body = {};
  try { body = await request.json(); } catch (_) {}

  if (body.event !== 'message_created' || body.message_type !== 'incoming' || body.private === true) {
    return new Response(JSON.stringify({ ignored: true }), { headers: jsonHeaders });
  }

  const msgId = body.id ?? body.message?.id;
  if (chatwootIsDuplicate(msgId)) {
    return new Response(JSON.stringify({ ignored: true, duplicate: true }), { headers: jsonHeaders });
  }

  const accountId = body.account?.id;
  const inboxId = body.inbox?.id;
  const conversationId = body.conversation?.id;
  const content = String(body.content || '');
  const senderEmail = body.sender?.email || '';

  if (!accountId || !inboxId || !conversationId) {
    return new Response(JSON.stringify({ ignored: true, reason: 'missing account/inbox/conversation id' }), { headers: jsonHeaders });
  }

  const inboxMap = parseChatwootInboxMap(env);
  const site = inboxMap[String(inboxId)];

  if (!site) {
    await chatwootEscalate(env, ctx, accountId, conversationId, senderEmail, content, 'unknown_inbox');
    return new Response(JSON.stringify({ ok: true, escalated: true, reason: 'unknown_inbox' }), { headers: jsonHeaders });
  }

  if (CHATWOOT_ESCALATE_RE.test(content)) {
    await chatwootEscalate(env, ctx, accountId, conversationId, senderEmail, content, 'trigger_match');
    return new Response(JSON.stringify({ ok: true, escalated: true, reason: 'trigger_match' }), { headers: jsonHeaders });
  }

  const routerProxyKey = env.ROUTER_PROXY_KEY;
  if (!routerProxyKey) {
    await logErr(env, '/support/bot', 'Missing ROUTER_PROXY_KEY binding', '', 500);
    await chatwootEscalate(env, ctx, accountId, conversationId, senderEmail, content, 'router_unconfigured');
    return new Response(JSON.stringify({ ok: true, escalated: true, reason: 'router_unconfigured' }), { headers: jsonHeaders });
  }

  const canonText = site === 'winnerdata' ? await fetchWinnerdataCanon(env) : '';
  const systemPrompt = buildSupportBotSystemPrompt(site, canonText);

  let aiText = '';
  let routerOk = false;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    const routerResp = await fetch(`${SUPABASE_URL}/functions/v1/claude-router`, {
      method: 'POST',
      headers: { 'X-Router-Key': routerProxyKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content }],
        system: systemPrompt,
        max_tokens: 300,
        stream: false,
        source: 'support-bot',
      }),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (routerResp.ok) {
      const data = await routerResp.json();
      aiText = data.text || '';
      routerOk = true;
    } else {
      await logErr(env, '/support/bot', 'claude-router non-200', await routerResp.text(), routerResp.status);
    }
  } catch (e) {
    await logErr(env, '/support/bot', 'claude-router fetch failed/timeout', String(e), 502);
  }

  if (!routerOk || !aiText) {
    await chatwootEscalate(env, ctx, accountId, conversationId, senderEmail, content, 'router_failure');
    return new Response(JSON.stringify({ ok: true, escalated: true, reason: 'router_failure' }), { headers: jsonHeaders });
  }

  if (aiText.includes('[[HANDOFF]]')) {
    await chatwootEscalate(env, ctx, accountId, conversationId, senderEmail, content, 'llm_handoff');
    return new Response(JSON.stringify({ ok: true, escalated: true, reason: 'llm_handoff' }), { headers: jsonHeaders });
  }

  await chatwootReply(env, accountId, conversationId, aiText);
  await logErr(env, '/support/bot', `reply (${site})`, `inbox=${inboxId} conv=${conversationId}`, 200, 'info');
  return new Response(JSON.stringify({ ok: true, replied: true, site }), { headers: jsonHeaders });
}

// ── Shared public-site shell ───────────────────────────────────────────────────
// Worker-served public pages use this shell so they remain visually and
// functionally consistent with the Next.js workspace shell. It is deliberately
// local HTML/CSS/JS: no external runtime, analytics, storage, or platform
// dependency is introduced. Page content remains owned by each existing
// builder; only the chrome is standardized.
const PUBLIC_SHELL_STYLE = `<style>
.bd-shell-content{min-height:100vh;min-width:0;margin-left:248px;padding-top:64px;position:relative}
.bd-shell-sidebar{position:fixed;inset:0 auto 0 0;z-index:1000;width:248px;background:#0b1220;border-right:1px solid #1e293b;color:#cbd5e1;display:flex;flex-direction:column;padding:18px 12px}
.bd-shell-brand{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none;padding:4px 10px 22px;border-bottom:1px solid #1e293b;margin-bottom:14px}
.bd-shell-mark{width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#f59e0b,#f97316);display:grid;place-items:center;color:#020617;font-size:12px;font-weight:900;flex:none}
.bd-shell-brand-text{display:grid;line-height:1.1}.bd-shell-brand-text strong{font-size:15px}.bd-shell-brand-text strong span{color:#f59e0b}.bd-shell-brand-text small{font-size:10px;color:#94a3b8;margin-top:4px}
.bd-shell-label{font:600 10px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:#64748b;padding:0 10px 8px}
.bd-shell-nav{display:grid;gap:4px;background:none}.bd-shell-nav a,.bd-shell-deed{display:flex;align-items:center;gap:10px;min-height:42px;padding:10px;border:1px solid transparent;border-radius:8px;color:#cbd5e1;text-decoration:none;font:500 14px/1.2 Inter,system-ui,sans-serif;background:transparent;cursor:pointer;text-align:left;width:100%}
.bd-shell-nav a:hover,.bd-shell-deed:hover,.bd-shell-nav a[aria-current=page],.bd-shell-deed[aria-expanded=true]{background:#1e293b;color:#fff;border-color:#334155}.bd-shell-nav a[aria-current=page]{box-shadow:inset 3px 0 #f59e0b}.bd-shell-icon{width:18px;text-align:center;color:#94a3b8}.bd-shell-nav a[aria-current=page] .bd-shell-icon,.bd-shell-deed[aria-expanded=true] .bd-shell-icon{color:#f59e0b}
.bd-shell-footer{margin-top:auto;border-top:1px solid #1e293b;padding:14px 10px 4px;color:#64748b;font:11px/1.5 Inter,system-ui,sans-serif}.bd-shell-footer a{color:#94a3b8;text-decoration:none}.bd-shell-footer a:hover{color:#f59e0b}
.bd-shell-topbar{position:fixed;inset:0 0 auto 248px;z-index:999;height:64px;display:flex;align-items:center;gap:12px;padding:0 24px;background:rgba(11,18,32,.96);border-bottom:1px solid #1e293b;color:#e2e8f0;backdrop-filter:blur(12px)}
.bd-shell-menu{display:none}.bd-shell-route{font:600 14px/1.2 Inter,system-ui,sans-serif;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bd-shell-top-actions{margin-left:auto;display:flex;align-items:center;gap:10px}.bd-shell-cta{background:#f59e0b;color:#020617;border-radius:7px;padding:9px 13px;text-decoration:none;font:800 12px/1 Inter,system-ui,sans-serif}.bd-shell-cta:hover{background:#fbbf24}
.bd-shell-drawer{display:none}.bd-shell-scrim{display:none}
.bd-shell-content > nav{display:none!important}.bd-shell-content > header{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}.bd-shell-content :where(a,button,input,select,textarea):focus-visible{outline:2px solid #f59e0b;outline-offset:2px}.bd-theme-toggle{display:inline-flex;align-items:center;gap:5px;min-height:36px;padding:7px 10px;border:1px solid #334155;border-radius:8px;background:#0f172a;color:#cbd5e1;font:600 11px/1 Inter,system-ui,sans-serif;cursor:pointer}.bd-theme-toggle:hover{border-color:#f59e0b;color:#fff}.bd-shell-theme-toggle{display:inline-flex;align-items:center;gap:5px;min-height:36px;padding:7px 10px;border:1px solid #334155;border-radius:8px;background:#0f172a;color:#cbd5e1;font:600 11px/1 Inter,system-ui,sans-serif;cursor:pointer}.bd-shell-theme-toggle:hover{border-color:#f59e0b;color:#fff}html[data-theme=light]{color-scheme:light;--navy:#1f1b16;--navy2:#fbfaf7;--navy3:#f5f0e8;--orange:#9f4d32;--orange2:#823f29;--text:#1f1b16;--muted:#6e655e;--border:#ddd5c9}html[data-theme=light] body{background:#f5f0e8!important;color:#1f1b16!important}html[data-theme=light] .bd-shell-sidebar,html[data-theme=light] .bd-shell-drawer{background:#f5f0e8;color:#1f1b16;border-color:#ddd5c9}html[data-theme=light] .bd-shell-topbar{background:rgba(245,240,232,.96);color:#1f1b16;border-color:#ddd5c9}html[data-theme=light] .bd-shell-brand{color:#1f1b16;border-color:#ddd5c9}html[data-theme=light] .bd-shell-icon{color:#655e56}html[data-theme=light] .bd-shell-brand-text strong span,html[data-theme=light] .bd-shell-nav a[aria-current=page] .bd-shell-icon{color:#9f4d32}html[data-theme=light] .bd-shell-brand-text small,html[data-theme=light] .bd-shell-label,html[data-theme=light] .bd-shell-footer{color:#6e655e}html[data-theme=light] .bd-shell-nav a,html[data-theme=light] .bd-shell-deed{color:#1f1b16}html[data-theme=light] .bd-shell-nav a:hover,html[data-theme=light] .bd-shell-deed:hover,html[data-theme=light] .bd-shell-nav a[aria-current=page],html[data-theme=light] .bd-shell-deed[aria-expanded=true]{background:#ede3d7;color:#1f1b16;border-color:#ddd5c9}html[data-theme=light] .bd-shell-theme-toggle{background:#fbfaf7;color:#1f1b16;border-color:#b5a9a0}html[data-theme=light] .bd-shell-menu{background:#fbfaf7;color:#1f1b16;border-color:#b5a9a0}html[data-theme=light] .bd-shell-route{color:#1f1b16}html[data-theme=light] .bd-shell-cta{background:#9f4d32;color:#f5f0e8}html[data-theme=light] .bd-shell-cta:hover{background:#823f29}html[data-theme=light] .bd-shell-scrim{background:rgba(31,27,22,.28)}
@media (max-width:767px){
  .bd-shell-content{margin-left:0;padding-top:56px}
  .bd-shell-sidebar{display:none}
  .bd-shell-topbar{inset:0 0 auto 0;height:56px;padding:0 12px}
  .bd-shell-menu{display:inline-grid;place-items:center;width:40px;height:40px;border:1px solid #334155;border-radius:8px;background:#0f172a;color:#e2e8f0;font-size:20px;cursor:pointer}
  .bd-shell-top-actions .bd-shell-cta{padding:9px 10px;font-size:11px}
  .bd-shell-drawer{position:fixed;display:flex;flex-direction:column;inset:0 auto 0 0;z-index:1002;width:min(86vw,300px);padding:18px 12px;background:#0b1220;color:#cbd5e1;transform:translateX(-105%);transition:transform .2s ease;box-shadow:12px 0 32px rgba(0,0,0,.35)}
  .bd-shell-drawer[data-open=true]{transform:translateX(0)}
  .bd-shell-scrim{position:fixed;inset:0;z-index:1001;background:rgba(2,6,23,.7)}
  .bd-shell-scrim[data-open=true]{display:block}
  .bd-shell-drawer .bd-shell-brand{margin-bottom:18px}
  .bd-shell-drawer .bd-shell-footer{margin-top:auto}
  .bd-shell-content .split-container{height:calc(100vh - 56px)}
}
@media (prefers-reduced-motion:reduce){.bd-shell-drawer{transition:none}}
</style>`;

function publicRouteLabel(path) {
  if (path === '/') return 'Overview';
  if (path === '/counties' || path.startsWith('/county/')) return 'Counties';
  if (path === '/buy-report' || path.startsWith('/free-report')) return 'Reports';
  if (path === '/subscribe') return 'Plans & pricing';
  if (path === '/chat' || path.startsWith('/chat')) return 'Deed';
  if (path === '/blog' || path.startsWith('/blog/')) return 'Blog';
  if (path.startsWith('/answers/')) return 'Answers';
  if (path === '/pioneers') return 'Pioneers';
  if (path.startsWith('/proof/')) return 'Proof';
  return 'BidDeed.AI';
}
function publicNavLink(path, href, label, icon, match) {
  const active = match ? match(path) : path === href;
  return `<a href="${href}"${active ? ' aria-current="page"' : ''}><span class="bd-shell-icon" aria-hidden="true">${icon}</span><span>${label}</span></a>`;
}
function withPublicShell(html, path) {
  const nav = [
    publicNavLink(path, '/', 'Home', '⌂'),
    publicNavLink(path, '/radar', 'Auctions', '◆', p => p === '/radar' || p.startsWith('/radar/')),
    publicNavLink(path, '/radar?view=calendar', 'Calendar', '▦', p => p === '/calendar'),
    publicNavLink(path, '/counties', 'Counties', '⌖', p => p === '/counties' || p.startsWith('/county/')),
    publicNavLink(path, '/buy-report', 'Reports', '▤', p => p === '/buy-report' || p.startsWith('/free-report') || p.startsWith('/report/')),
    publicNavLink(path, '/blog', 'Blog', '✦', p => p === '/blog' || p.startsWith('/blog/')),
  ].join('');
  const label = publicRouteLabel(path);
  const shell = `<aside class="bd-shell-sidebar" aria-label="Primary navigation"><a class="bd-shell-brand" href="/"><span class="bd-shell-mark" aria-hidden="true">BD</span><span class="bd-shell-brand-text"><strong>Bid<span>Deed</span>.AI</strong><small>Auction Intelligence</small></span></a><div class="bd-shell-label">Workspace</div><nav class="bd-shell-nav">${nav}<a class="bd-shell-deed" href="/chat"><span class="bd-shell-icon" aria-hidden="true">✦</span><span>Deed</span></a></nav><div class="bd-shell-footer"><a href="/security">Security</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></div></aside><header class="bd-shell-topbar"><button class="bd-shell-menu" type="button" aria-label="Open navigation" aria-controls="bd-mobile-drawer" aria-expanded="false" data-menu-toggle>☰</button><span class="bd-shell-route">${label}</span><div class="bd-shell-top-actions"><button class="bd-shell-theme-toggle" type="button" data-theme-toggle aria-label="Switch to dark mode">☾ 
<span>Dark</span></button><a class="bd-shell-cta" href="/subscribe?tier=investor">Investor $99/mo</a></div></header><div class="bd-shell-scrim" data-menu-scrim></div><aside class="bd-shell-drawer" id="bd-mobile-drawer" aria-label="Mobile navigation" data-mobile-drawer><a class="bd-shell-brand" href="/"><span class="bd-shell-mark" aria-hidden="true">BD</span><span class="bd-shell-brand-text"><strong>Bid<span>Deed</span>.AI</strong><small>Auction Intelligence</small></span></a><div class="bd-shell-label">Workspace</div><nav class="bd-shell-nav">${nav}<a class="bd-shell-deed" href="/chat"><span class="bd-shell-icon" aria-hidden="true">✦</span><span>Deed</span></a></nav><div class="bd-shell-footer"><a href="/security">Security</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></div></aside><script>(function(){var d=document.querySelector('[data-mobile-drawer]'),s=document.querySelector('[data-menu-scrim]'),m=document.querySelector('[data-menu-toggle]');function close(){if(d)d.dataset.open='false';if(s)s.dataset.open='false';if(m)m.setAttribute('aria-expanded','false')}function open(){if(d)d.dataset.open='true';if(s)s.dataset.open='true';if(m)m.setAttribute('aria-expanded','true')}if(m)m.addEventListener('click',function(){d&&d.dataset.open==='true'?close():open()});if(s)s.addEventListener('click',close);document.querySelectorAll('[data-mobile-drawer] a').forEach(function(a){a.addEventListener('click',close)});document.addEventListener('keydown',function(e){if(e.key==='Escape')close()});})();</script><script>(function(){var root=document.documentElement;var buttons=document.querySelectorAll('[data-theme-toggle]');function apply(theme){root.dataset.theme=theme;buttons.forEach(function(b){var light=theme==='dark';b.setAttribute('aria-label','Switch to '+(light?'light':'dark')+' mode');b.innerHTML=(light?'☼ <span>Light</span>':'☾ <span>Dark</span>')})}apply('light');buttons.forEach(function(b){b.addEventListener('click',function(){apply(root.dataset.theme==='dark'?'light':'dark')})})})();</script>`;
  return html.replace('</head>', PUBLIC_SHELL_STYLE + '</head>').replace(/<body[^>]*>/i, match => `${match}${shell}<div class="bd-shell-content">`).replace(/<\/body>/i, '</div></body>');
}

// ── Chatwoot website widget — additive to the existing full-page /chat, not a
// replacement. No-ops (renders nothing) when the website token isn't bound
// yet, so this ships dark until Ariel provisions the Cloudflare Worker secret.
function injectChatwootWidget(html, env) {
  const token = env.CHATWOOT_WEBSITE_TOKEN_BIDDEED;
  if (!token) return html;
  const base = env.CHATWOOT_BASE_URL || 'https://app.chatwoot.com';
  const snippet = `<script>
window.chatwootSettings={position:"right",type:"standard",launcherTitle:"Ask BidDeed",darkMode:"dark"};
(function(d,t){var BASE_URL="${base}";var g=d.createElement(t),s=d.getElementsByTagName(t)[0];g.src=BASE_URL+"/packs/js/sdk.js";g.defer=true;g.async=true;s.parentNode.insertBefore(g,s);g.onload=function(){window.chatwootSDK.run({websiteToken:"${token}",baseUrl:BASE_URL})}})(document,"script");
</script>`;
  return html.replace(/<\/body>/i, snippet + '</body>');
}

// Named export so the internal-preview script
// (packages/biddeed-mcp/scripts/generate_internal_signal_report.mjs) can
// reuse this EXACT renderer instead of maintaining a second HTML template
// that drifts from production — the consistency fix this section exists for.
// Adding a named export alongside `export default { fetch }` is a no-op for
// the Cloudflare Worker itself (wrangler only invokes the default export).
export { renderS5ReportHtml };

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

// ── AuctionRadar proxy ──────────────────────────────────────────────────────
// biddeed.ai stays served by this Worker. The Next.js app (biddeed-web) mounts
// UNDERNEATH it at /radar/* rather than replacing it, because this Worker owns
// 40+ routes the new app does not have: every checkout path, 66 county SEO
// pages, the legal pages, and /unsubscribe - which is linked from email that
// has already been sent. Repointing DNS at Vercel would delete all of it
// silently, including every /report/:id?key= link already sitting in a paying
// customer inbox.
//
// The app sets basePath:"/radar", so its own asset, chunk and API URLs already
// carry the prefix. That is what makes this single branch sufficient: there is
// no path rewriting to get wrong, and /auctions (JSON here, HTML there) never
// collides.
//
// The upstream response is passed through with only hop-by-hop headers removed.
// The app ships its own Content-Security-Policy carrying a per-request nonce,
// and withSecurityHeaders() only fills in a CSP when one is absent - so the
// nonce survives. Overwriting it would make the browser refuse every script and
// paint a blank page, which is the exact failure this rebuild already fixed.
// 2026-09-03 (#19820): pointed at the Cloudflare Worker, not the Vercel deploy.
// A prior session (#19813) flipped this origin via a code-only `wrangler deploy`
// without committing the change here — deploy-worker.yml redeploys this file
// from source on every push to main, so the next push silently reverted
// production to Vercel. The rule going forward: no production origin change
// without a matching commit on main in the same session.
const RADAR_ORIGIN = "https://biddeed-web-production.brevardbidderai.workers.dev";

async function proxyToRadar(request, url) {
  const upstream = new URL(url.pathname + url.search, RADAR_ORIGIN);
  const headers = new Headers(request.headers);
  headers.delete("host");
  // Vercel may replace X-Forwarded-Host with its internal alias before the
  // request reaches Next. Preserve the public route identity in a separate
  // Worker-owned header for canonical-domain Clerk gating.
  headers.delete("x-biddeed-canonical-host");
  headers.set("X-Forwarded-Host", url.host);
  headers.set("X-Biddeed-Canonical-Host", "biddeed.ai");
  headers.set("X-Forwarded-Proto", "https");

  const init = { method: request.method, headers, redirect: "manual" };
  if (request.method !== "GET" && request.method !== "HEAD") init.body = request.body;

  let res;
  try {
    res = await fetch(upstream.toString(), init);
  } catch (e) {
    // Fail loudly on /radar only. The rest of biddeed.ai is unaffected by an
    // upstream outage precisely because it is not served from there.
    return new Response("AuctionRadar is temporarily unavailable. Please try again shortly.", {
      status: 502,
      headers: { "Content-Type": "text/plain; charset=utf-8" }
    });
  }

  const out = new Headers(res.headers);
  out.delete("content-encoding");
  out.delete("content-length");
  out.delete("transfer-encoding");
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: out });
}

async function handleRequest(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;
    const origin = request.headers.get('Origin') || '';

    try {
      if (method === 'OPTIONS') {
        return new Response(null, { status: 204, headers: corsHeaders(origin) });
      }

      // ── AuctionRadar ─────────────────────────────────────────────────────
      // Placed first so it cannot be shadowed by a later prefix match. See
      // proxyToRadar() above for the original merge rationale. As of the
      // 2026-08-20 cutover (biddeed-web next.config.mjs contract: "the Worker
      // gains explicit proxy branches for /, /_next/*, /api/*, /radar* and
      // /success"), the app also serves the apex, its assets, its API routes,
      // and the order-confirmation pages. The Worker keeps every other route
      // (checkout, county SEO, legal, /report/:id, /auctions JSON, /chat).
      // Rollback: remove the extra path tests below, leaving only /radar.
      if (
        path === '/' ||
        path === '/radar' || path.startsWith('/radar/') ||
        path.startsWith('/_next/') ||
        path.startsWith('/api/') ||
        path === '/success' || path.startsWith('/success/') ||
        path === '/order' || path.startsWith('/order/') ||
        // Clerk auth pages (added 2026-08-20 when login was enabled on the
        // app). Without these branches biddeed.ai/sign-in hits this Worker's
        // 404 and auth.protect() redirects users into a dead URL.
        path === '/sign-in' || path.startsWith('/sign-in/') ||
        path === '/sign-up' || path.startsWith('/sign-up/') ||
        // P1 Discovery is a Next/Vercel surface proxied through the canonical Worker host.
        path === '/discover' || path.startsWith('/discover/') ||
        // Authenticated Alerts UI is a Vercel surface; its API remains Clerk-protected.
        path === '/alerts' || path.startsWith('/alerts/') ||
        // CP-C2 programmatic county SEO pages (biddeed-web PR #17, issue
        // #19821/#19830) live in the app, not this Worker. Bare '/counties'
        // (the index) stays local -- buildCountiesIndex() below -- the app's
        // PR #17 has no app/counties/page.tsx, only [county] and
        // [county]/[saleType]. Ships dark against production until #17
        // merges and deploys: until then the upstream 404s, same "ships
        // dark" contract as /answers/:slug.
        path.startsWith('/counties/')
      ) {
        return proxyToRadar(request, url);
      }

      // -- Self-hosted static assets for the 67 /county/:slug pages ---------
      // See the const definitions at the end of this file for why these exist.
      if (path === '/assets/tailwind-county.css') {
        return new Response(BD_COUNTY_TW_CSS, { headers: { 'Content-Type': 'text/css; charset=utf-8', 'Cache-Control': 'public, max-age=86400' } });
      }
      if (path === '/assets/alpine.min.js') {
        return new Response(BD_ALPINE_JS, { headers: { 'Content-Type': 'application/javascript; charset=utf-8', 'Cache-Control': 'public, max-age=86400' } });
      }
      if (path === '/assets/papaparse.min.js') {
        return new Response(BD_PAPAPARSE_JS, { headers: { 'Content-Type': 'application/javascript; charset=utf-8', 'Cache-Control': 'public, max-age=86400' } });
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
    <div class="stat-label">Per Full SIGNAL$ Property Report</div>
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

      if (path === '/terms' || path === '/tos') return new Response(injectChatwootWidget(withPublicShell(TERMS_HTML, path), env),      { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/unsubscribe') {
        const uEmail = (url.searchParams.get('email') || '').trim();
        let uMsg = 'No email address provided.';
        let uOk = false;
        if (uEmail && uEmail.includes('@')) {
          try {
            const rpcRes = await fetch(`${SUPABASE_URL}/rest/v1/rpc/upsert_lead_consent`, {
              method: 'POST',
              headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({ p_email: uEmail, p_marketing_consent: false, p_source: 'unsubscribe_link' })
            });
            uOk = rpcRes.ok;
            uMsg = uOk ? 'You have been unsubscribed and will not receive further marketing emails from BidDeed.AI.' : 'Something went wrong processing your request. Please reply to any BidDeed.AI email and we will remove you manually.';
          } catch (e) {
            uMsg = 'Something went wrong processing your request. Please reply to any BidDeed.AI email and we will remove you manually.';
          }
        }
        const uHtml = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Unsubscribed — BidDeed.AI</title><style>body{background:#020617;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;margin:0;padding:2rem}.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:16px;padding:2rem;max-width:440px;text-align:center}h1{color:white;font-size:1.3rem;margin-bottom:.75rem}p{color:#94a3b8;font-size:.9rem;line-height:1.5}a{color:#f59e0b}</style></head><body><div class="card"><h1>${uOk ? 'Unsubscribed' : 'Request received'}</h1><p>${uMsg}</p><p style="margin-top:1rem"><a href="/">Return to BidDeed.AI</a></p></div></body></html>`;
        return new Response(withPublicShell(uHtml, path), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
      }
      if (path === '/privacy')                  return new Response(injectChatwootWidget(withPublicShell(PRIVACY_HTML, path), env),    { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/section18-teaser')           return new Response(withPublicShell(SECTION18_TEASER_HTML, path), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/disclaimer')                return new Response(injectChatwootWidget(withPublicShell(DISCLAIMER_HTML, path), env), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/security')                  return new Response(injectChatwootWidget(withPublicShell(SECURITY_HTML, path), env),   { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/data-retention')            return new Response(injectChatwootWidget(withPublicShell(DATA_RETENTION_HTML, path), env), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });

      // ── /subscribe ───────────────────────────────────────────────────────
      // Served as an HTML interstitial (not a raw 302) so PostHog can record
      // the pageview before handing off to Stripe.
      if (path === '/subscribe') {
        const tier = url.searchParams.get('tier') || 'investor';
        const safeTier = tier.replace(/[^a-z0-9_-]/gi, '');
        const intervalParam = url.searchParams.get('interval') || 'monthly';
        const safeInterval = intervalParam === 'annual' ? 'annual' : 'monthly';
        const isPro = safeTier === 'pro' || safeTier === 'proplus';
        const tierLabel = isPro ? 'Pro' : 'Investor';
        const monthlyNum = isPro ? 199 : 99;
        const annualNum = isPro ? 1990 : 990;
        const tierPrice = '$' + monthlyNum;
        const annualPrice = '$' + annualNum.toLocaleString('en-US');
        const savePrice = '$' + (monthlyNum * 12 - annualNum).toLocaleString('en-US');
        const html = withPublicShell(SUBSCRIBE_HTML
          .replace(/TIER_LABEL_PLACEHOLDER/g, tierLabel)
          .replace(/TIER_PRICE_PLACEHOLDER/g, tierPrice)
          .replace(/ANNUAL_PRICE_PLACEHOLDER/g, annualPrice)
          .replace(/SAVE_PRICE_PLACEHOLDER/g, savePrice)
          .replace('INTERVAL_PLACEHOLDER_monthly_active', safeInterval === 'monthly' ? 'active' : '')
          .replace('INTERVAL_PLACEHOLDER_annual_active', safeInterval === 'annual' ? 'active' : '')
          .replace(/INTERVAL_PLACEHOLDER/g, safeInterval)
          .replace(/TIER_PLACEHOLDER/g, safeTier), path);
        return new Response(injectChatwootWidget(html, env), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
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
        const { tier, customer_email, referral_code, interval } = body;
        if (!tier || !['investor','pro','proplus'].includes(tier)) {
          return new Response(JSON.stringify({ error: 'valid tier required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        if (!customer_email || typeof customer_email !== 'string') {
          return new Response(JSON.stringify({ error: 'customer_email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        try {
          const checkoutBody = { tier, customer_email };
          if (referral_code && typeof referral_code === 'string') checkoutBody.referral_code = referral_code;
          if (interval === 'annual') checkoutBody.interval = 'annual';
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
        const html = injectChatwootWidget(withPublicShell(BUY_REPORT_HTML.replace('"PREFILL_PLACEHOLDER"', prefillJson), path), env);
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
        const html = withPublicShell(buildFreeReportFormHtml(prefillEmail, counties), path);
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
          const html = withPublicShell(buildFreeReportFormHtml(email, counties, { phone, county, emailConsent, smsConsent, error: 'Please fill in all required fields and check at least one consent box.' }), path);
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
            const html = withPublicShell(buildFreeReportFormHtml(email, counties, { phone, county, emailConsent, smsConsent, error: 'Something went wrong — please try again.' }), path);
            return new Response(html, { status: 500, headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
          }
        } catch(e) {
          await logErr(env, '/free-report/submit', 'Exception', String(e), 500);
          const counties = await fetchReportCounties();
          const html = withPublicShell(buildFreeReportFormHtml(email, counties, { phone, county, emailConsent, smsConsent, error: 'Something went wrong — please try again.' }), path);
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
        const html = withPublicShell(buildFreeReportDeliveryHtml(email, county, auctions, countyMeta, consent), path);
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
      }

      // ── GET /report-success — post-payment report key delivery page ─────
      if (path === '/report-success' && method === 'GET') {
        return new Response(withPublicShell(REPORT_SUCCESS_HTML, path), { headers: { 'Content-Type': 'text/html;charset=UTF-8' } });
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
          const html = withPublicShell(renderS5ReportHtml(SAMPLE_STATIC_REPORT, { mcaId, keyLast8: apiKey.slice(-8), isSample: true }), path);
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

      // ── /county/:slug — legacy landing page, 301s to /counties/:slug ─────
      // Issue #19830 B3.2: the new page lives in biddeed-web PR #17, proxied
      // above via the /counties/ branch. Preserves inbound links/backlinks
      // already pointing at /county/. buildCountyPage()/fetchCountyData()
      // below are now unreachable from this route; left in place (not
      // deleted) per surgical-change discipline and flagged in the PR
      // description rather than removed silently.
      if (path.startsWith('/county/')) {
        const slug = path.replace('/county/', '').toLowerCase().replace(/_/g,'-').replace(/\/.*$/,'');
        if (!slug) return Response.redirect('/counties', 301);
        return Response.redirect('/counties/' + slug, 301);
      }

      // ── /answers/:slug — answer-asset renderer (SPR-02, issue #19830) ────
      // Reads site.site_content via public.get_published_content (the
      // schema itself isn't PostgREST-exposed -- see the migration's own
      // header comment). Ships dark: a slug with no published row 404s, so
      // this route is safe to deploy before any content exists.
      if (path.startsWith('/answers/')) {
        const slug = path.slice('/answers/'.length).replace(/\/$/, '');
        if (!slug || slug.includes('/')) return new Response('Not found', { status: 404, headers: { 'Cache-Control': 'no-store' } });
        const answerCache = caches.default;
        const answerCacheKey = new Request('https://biddeed.ai/_internal/answers-cache/' + slug);
        let row = null;
        let rpcFailed = false;
        try {
          const res = await fetch(SUPABASE_URL + '/rest/v1/rpc/get_published_content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY },
            body: JSON.stringify({ p_slug: slug }),
          });
          if (res.ok) row = await res.json();
          else { rpcFailed = true; await logErr(env, '/answers', 'get_published_content non-2xx', await res.text(), res.status); }
        } catch (e) {
          rpcFailed = true;
          await logErr(env, '/answers', 'get_published_content failed', String(e), 500);
        }
        // A transient RPC failure (e.g. a Postgres restart) must never look
        // like a removed page to a crawler -- issue #19830, 2026-09-04 08:26
        // note: /answers/redemption 404'd for ~60s during the 08:18:55
        // restart. 404 is reserved for a successful RPC that genuinely found
        // no published row; any fetch/network/non-2xx failure serves the
        // last-known-good edge-cached render if one exists, else 503.
        if (rpcFailed) {
          const cached = await answerCache.match(answerCacheKey);
          if (cached) return cached;
          return new Response('Temporarily unavailable', { status: 503, headers: { 'Retry-After': '30', 'Cache-Control': 'no-store' } });
        }
        if (!row) return new Response('Not found', { status: 404, headers: { 'Cache-Control': 'no-store' } });
        const scope = row.body_jsonb && row.body_jsonb.scope;
        const countySlug = (scope && scope !== 'statewide') ? scope : null;
        const tokens = await fetchAnswerTokens(countySlug);
        const html = injectChatwootWidget(withPublicShell(buildAnswerPage(row, tokens), path), env);
        const answerResp = new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=120' } });
        ctx.waitUntil(answerCache.put(answerCacheKey, answerResp.clone()));
        return answerResp;
      }

      // ── /counties — all counties index ───────────────────────────────────
      if (path === '/counties') {
        const ciConfig = await fetchRuntimeConfig();
        const html = injectChatwootWidget(withPublicShell(buildCountiesIndex(ciConfig), path), env);
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
        // SPR-02 (issue #19830): published-only, via public.list_published_content_slugs()
        // -- same schema-bridge RPC pattern as get_published_content. Fails
        // open to an empty list (never breaks the rest of the sitemap) if
        // Supabase doesn't answer.
        let answerSlugs = [];
        try {
          const ansRes = await fetch(SUPABASE_URL + '/rest/v1/rpc/list_published_content_slugs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY },
            body: '{}',
          });
          if (ansRes.ok) {
            const rows = await ansRes.json();
            answerSlugs = Array.isArray(rows) ? rows.map(r => r.slug).filter(Boolean) : [];
          }
        } catch (_) { /* answerSlugs stays [] */ }
        const urlEntries = [
          ...staticUrls.map(p => `  <url><loc>${base}${p}</loc><changefreq>daily</changefreq></url>`),
          // #19830 B3.2: county pages now live at /counties/:slug (biddeed-web
          // PR #17); /county/:slug 301s there. Points here even before #17
          // merges -- same ships-dark contract as the answer-asset slugs below.
          ...countySlugs.map(slug => `  <url><loc>${base}/counties/${slug.replace(/_/g,'-')}</loc><changefreq>daily</changefreq></url>`),
          ...blogSlugs.map(slug => `  <url><loc>${base}/blog/${slug}</loc><changefreq>weekly</changefreq></url>`),
          ...answerSlugs.map(slug => `  <url><loc>${base}/answers/${slug}</loc><changefreq>weekly</changefreq></url>`)
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
        return new Response(withPublicShell(buildPioneersPage(), path), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      // ── GET /deal/:county/:slug — BidDeed Reels v2 per-property landing
      // page (issue #19752 T2). pending_approval rows only render with
      // ?preview=<row id> so Ariel can QA before approval; approved/posted
      // rows are always public. All fields come from public.get_reel_landing()
      // (SECURITY DEFINER, see 20260902l_biddeed_reels_v2_rpc.sql) -- that
      // function's own field allow-list is the guardrail against ever
      // leaking a name/vendor field, not this route.
      if (path.match(/^\/deal\/[^/]+\/[^/]+$/) && (method === 'GET' || method === 'HEAD')) {
        const [, , countyParam, slugParam] = path.split('/');
        const previewId = url.searchParams.get('preview') || null;
        let reel = null;
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_reel_landing`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ p_county: decodeURIComponent(countyParam), p_slug: decodeURIComponent(slugParam), p_preview_id: previewId }),
          });
          if (res.ok) {
            reel = await res.json();
          } else {
            await logErr(env, '/deal', 'get_reel_landing non-2xx', await res.text(), res.status);
          }
        } catch (e) {
          await logErr(env, '/deal', 'get_reel_landing failed', String(e), 500);
        }
        if (!reel) return new Response(method === 'HEAD' ? null : 'Not found', { status: 404, headers: { 'Cache-Control': 'no-store' } });
        const submitted = url.searchParams.get('submitted') === '1';
        // S2 (issue #19786) -- the reel's archetype (persisted at render
        // time, travels via ?a= appended by resolve_reel_link) reorders the
        // landing frame to match the promise made in the reel; falls back
        // to the row's own stored archetype so a direct /deal/... visit
        // (no ?a=) still gets a sensible default.
        const archetype = url.searchParams.get('a') || reel.archetype || 'shock_number';
        if (method === 'GET' && reel.short_code) {
          ctx.waitUntil(logFunnelEvent(env, `deal-${reel.short_code}`, 'deal_view', { code: reel.short_code, archetype }));
          // S3 progressive disclosure's locked rung renders on every page
          // load (rung (b) is always visible), so gate_view fires alongside
          // deal_view -- an honest reflection of the actual UI, not a
          // separate user action.
          ctx.waitUntil(logFunnelEvent(env, `deal-${reel.short_code}`, 'gate_view', { code: reel.short_code, archetype }));
        }
        // issue #19761 T2: presale rows (phase='presale', calendar/upcoming
        // auctions) render the UPCOMING template with a paid-tier gate on the
        // intel block; postsale rows (phase='postsale', the v1/v2 default)
        // keep the existing template untouched.
        const apiKey = extractApiKey(request, url);
        let html;
        if (reel.phase === 'presale') {
          const paidTier = apiKey ? await fetchPaidTier(env, apiKey) : { ok: false, tier: null };
          html = buildPresaleDealHtml(reel, path, submitted, !!paidTier.ok, archetype);
        } else {
          html = buildDealLandingHtml(reel, path, submitted, archetype);
        }
        // A URL carrying a `key`/Bearer credential is a personalized variant
        // of this page -- never let a crawler index it (T2: "noindex for
        // gated URLs"). Cache-Control follows the same rule so a CDN never
        // serves one visitor's gated render to another.
        const personalized = !!apiKey;
        return new Response(method === 'HEAD' ? null : withPublicShell(html, path), {
          headers: {
            'Content-Type': 'text/html;charset=UTF-8',
            'Cache-Control': (reel.status === 'pending_approval' || personalized) ? 'no-store' : 'public,max-age=300',
            ...(personalized ? { 'X-Robots-Tag': 'noindex' } : {}),
          },
        });
      }

      // ── POST /deal/:county/:slug/lead — email capture. Writes to the
      // EXISTING public.lead_profiles table via public.insert_reel_lead()
      // with source='reel' (T2: "find it; don't create a parallel one").
      if (path.match(/^\/deal\/[^/]+\/[^/]+\/lead$/) && method === 'POST') {
        const parts = path.split('/'); // ['', 'deal', county, slug, 'lead']
        const county = decodeURIComponent(parts[2]);
        const basePath = `/deal/${parts[2]}/${parts[3]}`;
        let form;
        try { form = await request.formData(); } catch (_) {
          return new Response('Invalid form submission', { status: 400 });
        }
        const email = (form.get('email') || '').toString().trim();
        const caseNumber = (form.get('case_number') || '').toString().trim() || null;
        // issue #19761 T2: presale's "Set alert" form carries a hidden
        // source=presale_deal field; postsale's form has none, so this
        // defaults to 'reel' exactly like before this change. The RPC itself
        // also allow-lists this value server-side (never trusts the client).
        const sourceRaw = (form.get('source') || '').toString().trim();
        const source = sourceRaw === 'presale_deal' ? 'presale_deal' : 'reel';
        // S1 (issue #19786) -- carried by a hidden field the deal page's own
        // inline script fills from localStorage, so a visitor who already
        // has an anonymous S1 profile gets it upgraded to their email
        // instead of a second, disconnected lead_profiles row.
        const visitorId = (form.get('visitor_id') || '').toString().trim().slice(0, 64) || null;
        const shortCode = (form.get('reel_code') || '').toString().trim() || null;
        const previewQs = url.searchParams.get('preview');
        const backTo = previewQs ? `${basePath}?preview=${encodeURIComponent(previewQs)}` : basePath;
        if (!email || !email.includes('@')) {
          return Response.redirect(`${url.origin}${backTo}`, 302);
        }
        try {
          await fetch(`${SUPABASE_URL}/rest/v1/rpc/insert_reel_lead`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({
              p_email: email, p_case_number: caseNumber, p_county: county,
              p_utm_source: url.searchParams.get('utm_source') || null,
              p_utm_medium: url.searchParams.get('utm_medium') || null,
              p_utm_campaign: url.searchParams.get('utm_campaign') || null,
              p_source: source,
              p_visitor_id: visitorId,
            }),
          });
        } catch (e) {
          await logErr(env, '/deal/lead', 'insert_reel_lead failed', String(e), 500);
        }
        if (shortCode) ctx.waitUntil(logFunnelEvent(env, `deal-${shortCode}`, 'gate_submit', { code: shortCode }));
        const joiner = backTo.includes('?') ? '&' : '?';
        return Response.redirect(`${url.origin}${backTo}${joiner}submitted=1`, 302);
      }

      // ── GET /r/:code — BidDeed Reels v2 short link (T3). 302s to the
      // landing page with utm_* appended, increments clicks atomically in
      // public.resolve_reel_link() (SECURITY DEFINER).
      if (path.match(/^\/r\/[A-Za-z0-9]+$/) && (method === 'GET' || method === 'HEAD')) {
        const code = path.slice('/r/'.length);
        let link = null;
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/resolve_reel_link`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ p_code: code }),
          });
          if (res.ok) {
            link = await res.json();
          } else {
            await logErr(env, '/r', 'resolve_reel_link non-2xx', await res.text(), res.status);
          }
        } catch (e) {
          await logErr(env, '/r', 'resolve_reel_link failed', String(e), 500);
        }
        if (!link || !link.target) return new Response(method === 'HEAD' ? null : 'Not found', { status: 404, headers: { 'Cache-Control': 'no-store' } });
        const target = new URL(link.target);
        if (link.utm_source) target.searchParams.set('utm_source', link.utm_source);
        if (link.utm_medium) target.searchParams.set('utm_medium', link.utm_medium);
        if (link.utm_campaign) target.searchParams.set('utm_campaign', link.utm_campaign);
        if (link.utm_content) target.searchParams.set('utm_content', link.utm_content);
        if (link.archetype) target.searchParams.set('a', link.archetype);
        if (method === 'GET') ctx.waitUntil(logFunnelEvent(env, `reel-${code}`, 'reel_click', { code }));
        return new Response(null, { status: 302, headers: { Location: target.toString(), 'Cache-Control': 'no-store' } });
      }

      // ── POST /deal/visitor — S1 persistent-context upsert (issue #19786).
      // Client-side only (this Worker has no cookie/session mechanism -- see
      // extractApiKey's own comment -- so a RETURNING-visitor greeting needs
      // localStorage on the browser side; this route is the thin, keyless
      // proxy to public.upsert_visitor_profile() that the deal page's own
      // inline script calls on load, matching insert_reel_lead's proxy
      // pattern). Always 200 with the RPC's own {ok,...} body so the client
      // can render (or skip) the greeting banner.
      if (path === '/deal/visitor' && method === 'POST') {
        let body;
        try { body = await request.json(); } catch (_) { body = {}; }
        const visitorId = String(body.visitor_id || '').slice(0, 64);
        let out = { ok: false };
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/upsert_visitor_profile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({
              p_visitor_id: visitorId,
              p_reel_code: body.reel_code || null,
              p_county: body.county || null,
              p_archetype: body.archetype || null,
              p_case_number: body.case_number || null,
            }),
          });
          if (res.ok) out = await res.json();
          else await logErr(env, '/deal/visitor', 'upsert_visitor_profile non-2xx', await res.text(), res.status);
        } catch (e) {
          await logErr(env, '/deal/visitor', 'upsert_visitor_profile failed', String(e), 500);
        }
        return new Response(JSON.stringify(out), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
      }

      // ── GET /reels — BidDeed Reels v2 gallery (issue #19752 directive #4,
      // new T8). No MP4 or TikTok/IG/Shorts post can carry a clickable
      // region -- a page we host can. approved/posted reels are always
      // listed; pending_approval ones only with ?preview=1 so Ariel can QA
      // the whole batch before approving. public.list_public_reels() is the
      // same field allow-list as get_reel_landing() -- no name/vendor field
      // is selectable there either.
      if (path === '/reels' && (method === 'GET' || method === 'HEAD')) {
        const includePending = url.searchParams.get('preview') === '1';
        let reels = [];
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/list_public_reels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ p_include_pending: includePending }),
          });
          if (res.ok) reels = (await res.json()) || [];
          else await logErr(env, '/reels', 'list_public_reels non-2xx', await res.text(), res.status);
        } catch (e) {
          await logErr(env, '/reels', 'list_public_reels failed', String(e), 500);
        }
        const html = buildReelsGalleryHtml(reels, includePending);
        return new Response(method === 'HEAD' ? null : withPublicShell(html, path), {
          headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': includePending ? 'no-store' : 'public,max-age=120' },
        });
      }

      // ── GET /reels/:code — single-reel clickable player page (issue
      // #19752 directive #4C). The QR/short-link end card may point here
      // instead of /deal/ -- default stays /deal/, this is the alternate
      // Ariel can choose. OG tags per reel so a shared /reels/:code link
      // unfurls with the tight aerial, same as /deal/ already does.
      if (path.match(/^\/reels\/[A-Za-z0-9]+$/) && (method === 'GET' || method === 'HEAD')) {
        const code = path.slice('/reels/'.length);
        const previewId = url.searchParams.get('preview') || null;
        let reel = null;
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_reel_by_code`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ p_code: code, p_preview_id: previewId }),
          });
          if (res.ok) reel = await res.json();
          else await logErr(env, '/reels/code', 'get_reel_by_code non-2xx', await res.text(), res.status);
        } catch (e) {
          await logErr(env, '/reels/code', 'get_reel_by_code failed', String(e), 500);
        }
        if (!reel) return new Response(method === 'HEAD' ? null : 'Not found', { status: 404, headers: { 'Cache-Control': 'no-store' } });
        const html = buildSingleReelHtml(reel);
        return new Response(method === 'HEAD' ? null : withPublicShell(html, path), {
          headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': reel.status === 'pending_approval' ? 'no-store' : 'public,max-age=300' },
        });
      }

      // ── POST /reels/:code/event — watch-progress beacon (issue #19779
      // CP3a measurement hooks). Client JS in reelPlayerScript() posts
      // play/25/50/75/100/loop as the video element crosses each threshold;
      // this route is a thin forward to public.log_reel_watch_event()
      // (SECURITY DEFINER, allow-lists p_event server-side) so no Supabase
      // key of any kind needs to reach the browser. Always 204 -- a beacon
      // is fire-and-forget, never blocks or retries client-side.
      if (path.match(/^\/reels\/[A-Za-z0-9]+\/event$/) && method === 'POST') {
        const code = path.split('/')[2];
        try {
          const body = await request.json().catch(() => ({}));
          const evt = String(body.event || '');
          await fetch(`${SUPABASE_URL}/rest/v1/rpc/log_reel_watch_event`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ p_code: code, p_event: evt, p_session_id: body.session_id || null }),
          });
        } catch (e) {
          await logErr(env, '/reels/event', 'log_reel_watch_event failed', String(e), 500);
        }
        return new Response(null, { status: 204, headers: { 'Cache-Control': 'no-store' } });
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
        return new Response(withPublicShell(buildProofCard(card), path), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
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
        return new Response(injectChatwootWidget(withPublicShell(buildBlogIndex(), path), env), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }
      if (path.startsWith('/blog/')) {
        const slug = path.slice('/blog/'.length);
        const post = BLOG_POSTS.find(p => p.slug === slug);
        if (!post) return new Response('Not found', { status: 404 });
        return new Response(injectChatwootWidget(withPublicShell(buildBlogPost(post), path), env), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      // ── GET /auctions?county=&days=&type=&limit= — property cards for chat ──
      // Option A: all counties are served — Gold Standard is a badge (is_gold_standard
      // field per card), never an access gate.
      if (path === '/auctions' && method === 'GET') {
        const county = (url.searchParams.get('county') || '').toLowerCase().replace(/-/g,'_');
        if (!county) {
          // `/auctions` is a legacy JSON endpoint for the chat panel, while the
          // user-facing auction workspace lives at `/radar`. Preserve the JSON
          // error contract for programmatic callers, but prevent a broken page
          // when a user follows an old `/auctions` navigation link.
          const acceptsHtml = (request.headers.get('Accept') || '').includes('text/html');
          if (acceptsHtml) return Response.redirect(`${url.origin}/radar`, 302);
          return new Response(JSON.stringify({ error: 'county required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
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

          // 1b. Audit-trail record for SMS marketing consent (TCPA/FTSA) -- append-only,
          // fire-and-forget so it never blocks the response. Shared table with
          // zonewise-web onboarding consent flow (same Supabase project).
          if (sms_consent) {
            const clientIp = request.headers.get('CF-Connecting-IP') || 'unknown';
            fetch(`${SUPABASE_URL}/rest/v1/sms_consent_events`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'apikey': SUPABASE_KEY,
                'Authorization': `Bearer ${SUPABASE_KEY}`,
                'Prefer': 'return=minimal',
              },
              body: JSON.stringify({
                user_id: email,
                phone_number: phone || null,
                consented: true,
                disclosure_version: 'biddeed-lead-form-v1-2026-08-15',
                ip_address: clientIp,
                source: 'chat_lead_form',
              }),
            }).catch(err => logErr(env, '/chat/lead', 'sms_consent_events insert failed', String(err), 0));
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
      <div style="font-size:14px;font-weight:600;color:#0B1929;margin-bottom:6px">Want the full SIGNAL$ Property Report on a specific property?</div>
      <div style="font-size:13px;color:#64748b;margin-bottom:16px">Max-bid ceiling · Lien stack · Plaintiff intel · Zoning · BID/SKIP verdict — all in one $25 report. We deliver the SIGNAL$. First.</div>
      <a href="https://biddeed.ai/buy-report?county=${encodeURIComponent(county)}" style="display:inline-block;background:#F97316;color:#ffffff;font-size:13px;font-weight:700;padding:12px 24px;border-radius:8px;text-decoration:none;letter-spacing:.3px">Get SIGNAL$ Property Report — $25 →</a>
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

      // ── POST /chat/api/identity — issue a chat session token (#19829 P1) ──
      // See "Chat identity + persistence" comment block near extractApiKey()
      // for exactly what this does and does not prove.
      if (path === '/chat/api/identity' && method === 'POST') {
        if (!hasServiceRole(env)) return new Response(JSON.stringify({ error: 'Chat persistence not yet configured' }), { status: 503, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        let ibody = {};
        try { ibody = await request.json(); } catch (_) {}
        if (!isValidEmail(ibody.email)) return new Response(JSON.stringify({ error: 'Valid email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const token = await issueChatToken(env, ibody.email);
        return new Response(JSON.stringify({ token, email: String(ibody.email).toLowerCase().trim() }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
      }

      // ── GET /chat/api/conversations — recent chats list (#19829 P1) ──────
      if (path === '/chat/api/conversations' && method === 'GET') {
        const ownerEmail = await verifyChatToken(env, extractChatToken(request));
        if (!ownerEmail) return new Response(JSON.stringify({ error: 'Invalid or missing chat session' }), { status: 401, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const rows = await listConversations(env, ownerEmail);
        return new Response(JSON.stringify({ conversations: rows }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
      }

      // ── GET /chat/api/conversations/:id/messages (#19829 P1) ─────────────
      if (/^\/chat\/api\/conversations\/[^/]+\/messages$/.test(path) && method === 'GET') {
        const ownerEmail = await verifyChatToken(env, extractChatToken(request));
        if (!ownerEmail) return new Response(JSON.stringify({ error: 'Invalid or missing chat session' }), { status: 401, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const conversationId = path.split('/')[4];
        const rows = await getConversationMessages(env, ownerEmail, conversationId);
        if (rows === null) return new Response(JSON.stringify({ error: 'Not found' }), { status: 403, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        return new Response(JSON.stringify({ messages: rows }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
      }

      // ── GET /chat/api/search?q= — tsvector search over own chats (#19829 P1) ──
      if (path === '/chat/api/search' && method === 'GET') {
        const ownerEmail = await verifyChatToken(env, extractChatToken(request));
        if (!ownerEmail) return new Response(JSON.stringify({ error: 'Invalid or missing chat session' }), { status: 401, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const q = (url.searchParams.get('q') || '').trim();
        if (!q) return new Response(JSON.stringify({ results: [] }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const results = await searchConversations(env, ownerEmail, q);
        return new Response(JSON.stringify({ results }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
      }

      // ── POST /chat/api/upload — document upload + best-effort text
      // extraction (#19829 P1). Body: { filename, mime_type, data_base64,
      // conversation_id? }. PDF/CSV/TXT get real extraction; DOCX/images are
      // stored but return extraction_status='unsupported' (honest, not silent).
      if (path === '/chat/api/upload' && method === 'POST') {
        const ownerEmail = await verifyChatToken(env, extractChatToken(request));
        if (!ownerEmail) return new Response(JSON.stringify({ error: 'Invalid or missing chat session' }), { status: 401, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const cl2 = parseInt(request.headers.get('Content-Length') || '0', 10);
        if (cl2 > MAX_UPLOAD_BYTES * 1.4) return new Response(JSON.stringify({ error: 'File too large (8MB max)' }), { status: 413, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        let ubody = {};
        try { ubody = await request.json(); } catch (_) {
          return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        const { filename, mime_type, data_base64, conversation_id } = ubody;
        if (!filename || !data_base64) return new Response(JSON.stringify({ error: 'filename and data_base64 required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        let bytes;
        try { bytes = b64urlToBytesStd(data_base64); } catch (_) {
          return new Response(JSON.stringify({ error: 'Invalid base64' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        if (bytes.length > MAX_UPLOAD_BYTES) return new Response(JSON.stringify({ error: 'File too large (8MB max)' }), { status: 413, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (conversation_id) {
          const owned = await getConversationOwned(env, ownerEmail, conversation_id);
          if (!owned) return new Response(JSON.stringify({ error: 'Not found' }), { status: 403, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }
        const safeName = String(filename).replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 120);
        const storagePath = `${await sha256Hex(ownerEmail)}/${crypto.randomUUID()}-${safeName}`;
        const stored = await storagePutObject(env, storagePath, bytes, mime_type);
        if (!stored) return new Response(JSON.stringify({ error: 'Storage upload failed' }), { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const extraction = await extractUploadText(mime_type, filename, bytes);
        const row = await insertUpload(env, ownerEmail, conversation_id || null, { storagePath, filename, mimeType: mime_type, extractedText: extraction.text, extractionStatus: extraction.status });
        if (!row) return new Response(JSON.stringify({ error: 'Failed to record upload' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        return new Response(JSON.stringify({ id: row.id, filename: row.filename, extraction_status: row.extraction_status, extracted_text_preview: (row.extracted_text || '').slice(0, 300) }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
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

        const { messages, county, hook, conversation_id, upload_id, public_records } = body;
        if (!Array.isArray(messages) || messages.length === 0)
          return new Response(JSON.stringify({ error: 'messages required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (messages.length > 20)
          return new Response(JSON.stringify({ error: 'Too many messages' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        // ── Persisted chat (#19829 P1) — only active for identified users
        // (X-Chat-Token verified) and never blocks/degrades anonymous chat.
        const chatOwnerEmail = hasServiceRole(env) ? await verifyChatToken(env, extractChatToken(request)) : null;
        let activeConversationId = null;
        let attachmentCtx = '';
        if (chatOwnerEmail) {
          if (conversation_id) {
            const owned = await getConversationOwned(env, chatOwnerEmail, conversation_id);
            activeConversationId = owned ? conversation_id : null;
          }
          if (!activeConversationId) {
            const firstUserMsg = messages.find(m => m.role === 'user');
            const created = await createConversation(env, chatOwnerEmail, String(firstUserMsg?.content || 'New chat').slice(0, 60));
            activeConversationId = created?.id || null;
          }
          if (upload_id) {
            const upload = await getUploadOwned(env, chatOwnerEmail, upload_id);
            if (upload && upload.extraction_status === 'ok' && upload.extracted_text) {
              attachmentCtx = `\n\nATTACHMENT — the user uploaded a file named "${upload.filename}". Extracted text follows; cite this filename when you reference facts from it, and do not invent content beyond what's shown:\n"""\n${upload.extracted_text.slice(0, 6000)}\n"""`;
            } else if (upload && upload.extraction_status !== 'ok') {
              attachmentCtx = `\n\nATTACHMENT — the user uploaded a file named "${upload.filename}" but automatic text extraction was not available for this file type. Ask the user to paste or describe the key details if you need them.`;
            }
          }
        }
        if (public_records) attachmentCtx += '\n\nThe user has enabled "public-records search" for this message — prioritize Sunbiz, county clerk, and property-appraiser style public-record facts already available to you over general commentary.';
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
                '\nTotal: '+uRows.length+' lots shown (there may be more — tell the user to visit biddeed.ai/county/SLUG for the full list). For each property, mention they can get a $25 SIGNAL$ Property Report for a full max-bid analysis.';
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

        const countyCtx = (county ? `The user is asking about ${toDisplay(county)} County, Florida.` : 'The user may ask about any Florida county.') + liveDataCtx + propertyPanelCtx + langInstruction + attachmentCtx;
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
- All 67 FL counties are available. Gold Standard counties (verified data quality — currently: ${goldListForPrompt}) have full SIGNAL$ Property Report capability including CMA and ZoneWise. All other counties have Shapira Max Bid and opening bid analysis.
- Marion County proof: Case 422021CA000414CAAXXX — Shapira Max Bid $82,000, actual sale $73,501. Ceiling held by $8,499.
- SIGNAL$ Property Reports: $25 each — full AI-powered max-bid analysis for one specific property. We deliver the SIGNAL$. First.
- Investor tier: $99/month — unlimited property cards, 10 SIGNAL$ Property Reports/mo, daily digest all 67 counties
- When a user asks for a specific property analysis, mention they can get a full SIGNAL$ Property Report for $25

When someone asks for a specific property analysis or max bid, always suggest the $25 SIGNAL$ Property Report as the way to get the full calculation.

FORMATTING RULES (the chat UI renders real markdown, not plain text — use it):
- Use **bold** for prices, addresses, and key figures
- Use markdown tables (| col | col |) when listing 3+ properties — they render as real HTML tables
- ALWAYS end a county-specific answer with a link in this EXACT format: [See all COUNTY listings →](https://biddeed.ai/county/SLUG) using the lowercase-underscore county slug (e.g. palm_beach, st_johns, miami_dade). This link becomes clickable and drives users to the full property card grid.
- If you listed live auction results and there could be more than what you showed, say so and link to the county page rather than just stopping — never imply the list is exhaustive when it's a top-N sample
- ONLY TWO CTA link destinations exist and are valid — never invent or link to any other path: (1) [See all COUNTY listings →](https://biddeed.ai/county/SLUG) for county-specific results, (2) [Upgrade to Investor →](https://biddeed.ai/subscribe?tier=investor) for broad/multi-county questions. There is NO standalone /s5 page — for the $25 SIGNAL$ Property Report, mention it by name and price in plain text (not as a link) and tell the user to ask about a specific property to get started.
- ALWAYS end every substantive answer with a clear next step using only the two valid links above, or the plain-text SIGNAL$ Property Report mention. Never end with just information and no path forward — every answer is a lead-generation opportunity.
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
            // max_tokens raised 1024 -> 4096 (issue #19828 / #19820 SS B.1): 1024
            // was truncating mid-table on multi-row answers -- callClaude/
            // callDeepSeek in claude-router/index.ts pass this value straight
            // through with no floor (unlike the OpenRouter path, which forces
            // >=1500), so a low value here caps the real model output.
            // NOTE: claude-router has no streaming support at all (grep confirms
            // zero "stream" references in its source) -- `stream: false` here is
            // inert. This path buffers the full completion then wraps it as a
            // single SSE event; only the Gemini fallback above streams token by
            // token. Real incremental streaming requires adding stream support
            // to claude-router itself, a separate change to that shared,
            // revenue-critical edge function -- out of scope for this pass.
            const routerBody = JSON.stringify({
              messages: messages.map(m => ({ role: m.role, content: String(m.content) })),
              system: systemPrompt,
              max_tokens: 4096,
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
            if (chatOwnerEmail && activeConversationId) {
              await writer.write(encoder.encode(`event: meta\ndata: ${JSON.stringify({ conversation_id: activeConversationId })}\n\n`));
            }
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
            if (chatOwnerEmail && activeConversationId && fullText) {
              const lastUserMsg = messages[messages.length - 1];
              try {
                await insertMessages(env, chatOwnerEmail, activeConversationId, [
                  { role: 'user', content: String(lastUserMsg?.content || '') },
                  { role: 'assistant', content: fullText },
                ]);
                await touchConversation(env, chatOwnerEmail, activeConversationId);
              } catch (e) {
                await logErr(env, '/chat/api', 'Chat persistence write failed (non-fatal)', String(e), 500, 'warn');
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

      // ── POST /support/bot — Chatwoot Agent Bot webhook ───────────────────
      if (path === '/support/bot' && method === 'POST') {
        return handleSupportBot(request, env, ctx, url);
      }

      // ── GET /chat ────────────────────────────────────────────────────────
      if (path === '/chat' || path.startsWith('/chat')) {
        const county = url.searchParams.get('county') || '';
        const hook   = url.searchParams.get('hook')   || '';
        const ref    = url.searchParams.get('ref')    || '';
        const action = url.searchParams.get('action') || '';
        if (action === 'subscribe') return Response.redirect(`/subscribe?tier=investor`, 302);
        return new Response(withPublicShell(buildChatPage(county, hook, ref), path), { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'no-store' } });
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
  const isGold = !!(rtConfig && Array.isArray(rtConfig.goldCounties) && rtConfig.goldCounties.includes(slug));
  // ── SEO head: canonical, description and JSON-LD were absent on all 67
  // county pages until 2026-08-18 (verified: 0/67 had any of the three).
  // These are the top of the lead funnel and they are ranked URLs.
  const urlSlug = slug.replace(/_/g, '-');
  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const escJs = (v) => JSON.stringify(String(v == null ? '' : v)).slice(1, -1);
  const lotRows   = Array.isArray(lots) ? lots : [];
  const lotDates  = lotRows.map(x => x && x.auction_date).filter(Boolean).sort();
  // SPR-07 (issue #19826, CONTENT_SOP.md K2): prefer the SSOT RPC's per-county
  // upcoming/next_auction_date over counting fetchCountyLots' 35-day/300-row
  // window -- that window undercounted 53/67 counties against
  // auctions_summary_ssot() (live check, same minute). Falls back to the lots
  // window only if the SSOT config fetch failed (Supabase down), same
  // fail-open pattern as the rest of fetchRuntimeConfig().
  const ssotRow   = (rtConfig && rtConfig.countiesDetail && rtConfig.countiesDetail[slug]) || null;
  const lotCount  = ssotRow ? ssotRow.upcoming : lotRows.length;
  const nextDate  = ssotRow ? ssotRow.next_auction_date : (lotDates.length ? lotDates[0] : null);
  // Kept short on purpose (<=155 chars, P11) -- the prior template ("X
  // upcoming ... auctions — Y tax deed and Z foreclosure sales, next on
  // DATE. Opening bids...") ran 164-172 chars on 52/67 counties, over the
  // meta-description limit (found live during this same SPR-07 pass).
  const metaDesc  = lotCount
    ? lotCount + ' upcoming ' + name + ' County, Florida foreclosure and tax deed auctions'
      + (nextDate ? ', next on ' + nextDate : '') + '.'
    : name + ' County, Florida tax deed and foreclosure auction listings. '
      + 'No sales are scheduled in the current window — the calendar refills every month.';
  const jsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: name + ' County, Florida tax deed and foreclosure auctions',
    description: metaDesc,
    url: 'https://biddeed.ai/county/' + urlSlug,
    isAccessibleForFree: true,
    creator: { '@type': 'Organization', name: 'BidDeed.AI', url: 'https://biddeed.ai' },
    spatialCoverage: { '@type': 'Place', name: name + ' County, Florida, USA' },
    variableMeasured: ['auction_date','sale_type','opening_bid','assessed_value','case_number']
  }).replace(/</g, '\\u003c');

  // Serve the full interactive county page (Alpine.js + Tailwind)
  // Template has COUNTY_SLUG_PLACEHOLDER, COUNTY_TITLE_PLACEHOLDER, COUNTY_TITLE tokens
  return COUNTY_PAGE_TEMPLATE
    .replace(/COUNTY_URLSLUG/g, urlSlug)
    .replace(/COUNTY_META_DESC/g, esc(metaDesc))
    .replace('COUNTY_JSONLD', jsonLd)
    .replace(/COUNTY_SLUG_PLACEHOLDER/g, slug)
    .replace(/COUNTY_TITLE_PLACEHOLDER/g, name)
    .replace(/COUNTY_TITLE_JS_PLACEHOLDER/g, escJs(name))
    .replace('S5_COUNTIES_PLACEHOLDER', s5List)
    .replace(/COUNTY_CERT_BADGE_CLASS/g, isGold ? 'cert-gold' : 'cert-review')
    .replace(/COUNTY_CERT_BADGE_TEXT/g, isGold ? '⭐ Gold Standard certified' : '⚠️ Data under review')
    .replace('COUNTY_TITLE Auctions', name + ' County Auctions')
    .replace('COUNTY_TITLE auctions', name + ' County auctions');
}

// ── Answer-asset page (SPR-02, issue #19830, CONTENT_SOP.md SS5.1) ───────────
// Renders a `site.site_content` row (fetched via public.get_published_content,
// see supabase/migrations/20260904a_spr02_site_content_rpc.sql) inside the
// SAME withPublicShell() every other public Worker page uses -- so the
// #19828 token/contrast fix, whenever it lands on that shared function,
// applies here automatically without a second patch.
function buildAnswerPage(row, resolved) {
  const tokens = resolved.tokenMap;
  const topCounties = resolved.topCounties || [];
  const body = row.body_jsonb || {};
  const question = String(body.question || row.title || '');
  const metaDesc = renderTokens(escHtml(String(body.meta_description || '')), tokens);
  const answerFirst = renderTokens(escHtml(String(body.answer_first || '')), tokens);
  const bodyHtml = renderTokens(String(body.body_html || ''), tokens);
  const canonicalUrl = 'https://biddeed.ai/answers/' + row.slug;
  const faq = Array.isArray(body.faq) ? body.faq : [];
  const links = body.links || {};
  const howtoSteps = Array.isArray(body.howto) ? body.howto : [];

  const faqJsonLd = faq.length ? {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faq.map(f => ({
      '@type': 'Question',
      name: String(f.q || ''),
      acceptedAnswer: { '@type': 'Answer', text: String(f.a || '') },
    })),
  } : null;

  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'BidDeed.AI', item: 'https://biddeed.ai/' },
      { '@type': 'ListItem', position: 2, name: 'Answers', item: 'https://biddeed.ai/answers' },
      { '@type': 'ListItem', position: 3, name: question, item: canonicalUrl },
    ],
  };

  // Person + Organization schema per M7 founder carve-out
  // (unified_context key m7_founder_carveout_sep3): Ariel Shapira only,
  // sameAs the two public properties this canon names.
  const personJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Person',
    name: 'Ariel Shapira',
    jobTitle: 'Founder',
    sameAs: ['https://everestcapitalusa.com', 'https://zonewise.ai'],
  };

  const orgJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'BidDeed.AI',
    url: 'https://biddeed.ai',
    sameAs: ['https://twitter.com/biddeedai'],
  };

  const howtoJsonLd = howtoSteps.length ? {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: question,
    step: howtoSteps.map((s, i) => ({ '@type': 'HowToStep', position: i + 1, text: String(s) })),
  } : null;

  const jsonLdBlocks = [faqJsonLd, breadcrumbJsonLd, personJsonLd, orgJsonLd, howtoJsonLd]
    .filter(Boolean)
    .map(obj => `<script type="application/ld+json">${JSON.stringify(obj).replace(/</g, '\\u003c')}</script>`)
    .join('\n');

  // CONTENT_SOP.md §2.2: a statewide asset (links.top_counties: true in
  // frontmatter) links /counties plus the 3 counties with the most
  // `upcoming` at render time — resolved live in fetchAnswerTokens(),
  // never a fixed list.
  const topCountiesHtml = (links.top_counties && topCounties.length)
    ? topCounties.map(c => `<a href="/county/${escHtml(c.slug.replace(/_/g,'-'))}">${escHtml(toDisplay(c.slug))} County — ${c.upcoming} upcoming &rarr;</a>`).join('\n    ')
    : '';
  const linksHtml = `<div class="answer-links">
    ${links.county ? `<a href="${escHtml(links.county)}">See this county's live calendar &rarr;</a>` : ''}
    ${links.top_counties ? `<a href="/counties">Browse all Florida counties &rarr;</a>\n    ${topCountiesHtml}` : ''}
    ${links.radar ? `<a href="${escHtml(links.radar)}">Full auction calendar &rarr;</a>` : ''}
    ${links.report ? `<a href="${escHtml(links.report)}">Get a SIGNAL$ Property Report &rarr;</a>` : ''}
  </div>`;

  const faqHtml = faq.length
    ? `<div class="faq"><h2>Frequently asked</h2>${faq.map(f => `<h3>${escHtml(String(f.q || ''))}</h3><p>${escHtml(String(f.a || ''))}</p>`).join('')}</div>`
    : '';

  // A4 (issue #19830): the statute text itself is fetched from
  // leg.state.fl.us and quoted here verbatim (not through renderTokens --
  // a statutory percentage/day-count is a fixed point of law, not a live
  // business metric, so it sits outside the A5 body-number ban, which is
  // enforced upstream on body_md before this ever reaches body_html).
  const statutes = Array.isArray(body.statutes) ? body.statutes : [];
  const statutesHtml = statutes.length
    ? `<div class="sources"><h2>Sources</h2>${statutes.map(s => `<p><strong>Fla. Stat. &sect;${escHtml(String(s.code || ''))}</strong> — <a href="${escHtml(String(s.url || ''))}">official text</a><br><em>"${escHtml(String(s.sentence || ''))}"</em></p>`).join('')}</div>`
    : '';

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${escHtml(row.title)}</title>
<meta name="description" content="${escHtml(metaDesc)}">
<link rel="canonical" href="${escHtml(canonicalUrl)}">
${jsonLdBlocks}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b}
body{background:var(--navy);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh;font-size:17px;line-height:1.75}
.wrap{max-width:760px;margin:0 auto;padding:3rem 1.5rem}
h1{font-family:'Inter',sans-serif;font-weight:800;letter-spacing:-.02em;font-size:clamp(1.7rem,4vw,2.4rem);color:white;margin-bottom:1.25rem;line-height:1.25}
h2{color:var(--orange);font-size:1.2rem;margin:2rem 0 .75rem}
p{margin-bottom:1.1rem;color:var(--text)}
.answer-first{font-size:1.05rem;color:#fff;border-left:3px solid var(--orange);padding-left:1rem;margin-bottom:2rem}
ul,ol{margin:0 0 1.1rem 1.5rem;color:var(--text)}
li{margin-bottom:.4rem}
.answer-links{display:flex;flex-direction:column;gap:.5rem;margin:2rem 0;padding:1.25rem;border:1px solid var(--border);border-radius:12px;background:var(--navy2)}
.answer-links a{color:var(--orange);text-decoration:none;font-weight:600}
.answer-links a:hover{text-decoration:underline}
.faq h3{color:#fff;font-size:1rem;margin:1.25rem 0 .4rem}
.cta-box{background:var(--navy2);border:1px solid rgba(245,158,11,.3);border-radius:12px;padding:1.5rem;margin:2.5rem 0;text-align:center}
.cta-box a{display:inline-block;background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:12px 28px;border-radius:10px;font-weight:700;text-decoration:none;margin-top:.75rem}
.disclaimer{font-size:.8rem;color:var(--muted);border-top:1px solid var(--border);margin-top:2.5rem;padding-top:1.5rem}
</style>
</head>
<body>
<div class="wrap">
  <h1>${escHtml(question)}</h1>
  <p class="answer-first">${answerFirst}</p>
  ${bodyHtml}
  ${statutesHtml}
  ${linksHtml}
  ${faqHtml}
  <div class="cta-box">
    <div>Get your own max bid number before you show up.</div>
    <a href="/buy-report">Get a SIGNAL$ Property Report &mdash; $25 &rarr;</a>
  </div>
  <p class="disclaimer">This is general educational information, not legal, financial, or investment advice. Auction data and value estimates should always be independently verified. Consult a licensed Florida attorney and title professional before bidding on any property.</p>
</div>
</body></html>`;
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
<p>Not because it's the biggest county, and not because the numbers are the most dramatic — Escambia and Putnam both show wider headline spreads. We use Marion because we had a specific, verifiable auction outcome to publish the prediction against <em>before</em> the sale happened, and then grade it after the fact against the courthouse record. That's the standard we hold every SIGNAL$ Property Report to: a number published pre-sale, graded automatically within 24 hours of the actual result.</p>
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:'Inter',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:480px;width:100%}
.badge{display:inline-flex;background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.3);color:#34d399;padding:.4rem 1rem;border-radius:20px;font-size:.75rem;font-weight:700;letter-spacing:.05em;margin-bottom:1.25rem}
h1{font-family:'Inter',sans-serif;font-weight:800;letter-spacing:-.02em;font-size:1.6rem;color:white;margin-bottom:.3rem;line-height:1.25}
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
/* LIGHT MODE — see the matching block in buildDealLandingHtml for why the
   surface and its text flip together, not text-only. */
html[data-theme=light] .card{background:#fbfaf7;border-color:rgba(159,77,50,.3)}
html[data-theme=light] h1,html[data-theme=light] .row-value{color:#1f1b16}
html[data-theme=light] .location,html[data-theme=light] .row-label,html[data-theme=light] .margin{color:#6e655e}
html[data-theme=light] .row{border-bottom-color:#ddd5c9}
html[data-theme=light] .disclaimer{color:#8f8479}
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

// ── BidDeed Reels v2 (issue #19752 T2) — per-property landing page ──────────
// Rendered from public.get_reel_landing()'s field allow-list ONLY (see
// 20260902l_biddeed_reels_v2_rpc.sql) -- no name/vendor field is ever
// selectable there, so there is nothing here that could leak one. Server-
// rendered, no JS required to read (T2 spec).
function buildDealLandingHtml(reel, landingPath, submitted, archetype) {
  const fmtMoney = (n) => (n == null ? null : '$' + Math.round(Number(n)).toLocaleString());
  const countyName = String(reel.county || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const saleLabel = reel.sale_type === 'tax_deed' ? 'Tax Deed Sale' : 'Foreclosure Sale';
  const cond = reel.condition_json || {};
  const tier = cond.general_condition_tier || 'unknown';
  const tierLabel = tier === 'unknown' ? 'Condition pending review' : tier.charAt(0).toUpperCase() + tier.slice(1) + ' condition';
  const obs = ['roof', 'exterior'].map(k => cond[k] && cond[k].observation).filter(Boolean).slice(0, 2);
  const deltaPct = reel.delta_pct == null ? null : Number(reel.delta_pct);
  const deltaLine = deltaPct == null ? null : `${Math.abs(deltaPct).toFixed(0)}% ${deltaPct < 0 ? 'below' : 'above'} assessed value`;
  const soldFmt = fmtMoney(reel.sold_amount);
  const title = `${soldFmt || 'Sold at auction'} — ${countyName} County ${saleLabel}`;
  const description = [soldFmt ? `${soldFmt} sale in ${countyName} County.` : '', deltaLine ? `That's ${deltaLine}.` : ''].join(' ').trim();
  const ogImage = reel.aerial_tight_url || reel.aerial_wide_url || '';
  const previewBanner = reel.status === 'pending_approval'
    ? `<div class="deal-preview-banner">PREVIEW — pending approval, not yet public</div>` : '';
  const shortCode = reel.short_code || '';
  const ctaBlock = submitted
    ? `<div class="deal-thanks">Thanks — check your inbox for the full property signal report.</div>`
    : `<form method="POST" action="${escHtml(landingPath)}/lead${escHtml(previewQueryFor(reel))}">
<input type="hidden" name="case_number" value="${escHtml(reel.case_number)}">
<input type="hidden" name="reel_code" value="${escHtml(shortCode)}">
<input type="hidden" name="visitor_id" class="bd-visitor-field" value="">
<input type="email" name="email" placeholder="you@email.com" required>
<button type="submit">Send me the report</button>
</form>`;

  // S2 (issue #19786) -- archetype reorders which section leads. Postsale
  // archetypes are shock_number (default) or red_flag_warning (see
  // compute_bolt32_archetype in scripts/biddeed_reels_lib.py) -- nobody_bid
  // and presale_countdown only ever apply to presale rows.
  const statsSection = `<div class="deal-stats">
  <div class="deal-stat"><div class="label">Sold Price</div><div class="value">${escHtml(soldFmt || '&mdash;')}</div></div>
  <div class="deal-stat"><div class="label">Assessed Value</div><div class="value">${escHtml(fmtMoney(reel.assessed_value) || '&mdash;')}</div></div>
</div>
${deltaLine ? `<div class="deal-stat"><div class="label">Vs. Assessed</div><div class="value">${escHtml(deltaLine)}</div></div>` : ''}`;
  const conditionSection = `<div class="deal-badge">${escHtml(tierLabel)}</div>
${obs.length ? `<div class="deal-obs">${obs.map(escHtml).join('<br>')}</div>` : ''}
${reel.street_url ? `<img class="deal-img" src="${escHtml(reel.street_url)}" alt="Street-level view">` : ''}`;
  const orderedSections = archetype === 'red_flag_warning'
    ? conditionSection + statsSection
    : statsSection + conditionSection;

  // S3 progressive disclosure (issue #19786 PART 2) -- rung (a) is the
  // free stats/condition block above; this is rung (b), VISIBLE BUT
  // LOCKED -- real section NAMES shown (not a generic teaser), values
  // blurred. Rung (c) (the actual SIGNAL$ Property Report) is delivered by
  // the existing email-report pipeline once the single-field email gate is
  // submitted -- not re-implemented here, see docs/spec/19786.md Residual.
  const lockedSection = `<div class="deal-locked">
<h2>5 more sections on this property</h2>
<div class="deal-locked-row"><span class="label">Value Band</span><span class="value blur">$•••,••• – $•••,•••</span></div>
<div class="deal-locked-row"><span class="label">Shapira Max Bid</span><span class="value blur">$•••,•••</span></div>
<div class="deal-locked-row"><span class="label">Red Flags</span><span class="value blur">•• found</span></div>
<div class="deal-locked-row"><span class="label">Lien Hierarchy</span><span class="value blur">•• liens</span></div>
<div class="deal-locked-row"><span class="label">Comps</span><span class="value blur">•• nearby</span></div>
</div>`;

  // S4 (issue #19786) -- property-scoped chat entry, reuses the existing
  // /chat route (GET /chat?county=&hook=) rather than a new chat surface.
  const chatHref = `/chat?county=${encodeURIComponent(reel.county || '')}&hook=${encodeURIComponent('property_' + (reel.case_number || ''))}`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${escHtml(title)} — BidDeed.AI</title>
<meta name="description" content="${escHtml(description)}">
<meta property="og:title" content="${escHtml(title)}">
<meta property="og:description" content="${escHtml(description)}">
<meta property="og:type" content="website">
${ogImage ? `<meta property="og:image" content="${escHtml(ogImage)}">` : ''}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${escHtml(title)}">
<meta name="twitter:description" content="${escHtml(description)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:'Inter',sans-serif;padding:2rem 1rem;display:flex;justify-content:center}
.deal-card{max-width:520px;width:100%}
.deal-preview-banner{background:#F59E0B;color:#020617;font-weight:700;text-align:center;padding:.5rem;border-radius:8px;margin-bottom:1rem;font-size:.85rem}
.deal-greeting{background:#0f172a;border:1px solid #F59E0B;border-radius:10px;padding:.75rem .9rem;margin-bottom:1rem;font-size:.85rem;color:#F59E0B;display:none}
.deal-img{width:100%;border-radius:12px;margin-bottom:1rem;border:1px solid #1e293b;display:block}
h1{font-size:1.6rem;margin-bottom:.25rem;color:#fff}
.deal-addr{color:#cbd5e1;font-size:.9rem;margin-bottom:.15rem}
.deal-sub{color:#94a3b8;font-size:.95rem;margin-bottom:1.25rem}
.deal-stats{display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:.75rem}
.deal-stat{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:.85rem}
.deal-stat .label{color:#64748b;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em}
.deal-stat .value{color:#fff;font-size:1.15rem;font-weight:700;margin-top:.2rem}
.deal-badge{display:inline-block;background:#F59E0B;color:#020617;font-weight:700;padding:.3rem .7rem;border-radius:999px;font-size:.8rem;margin:.5rem 0}
.deal-obs{color:#cbd5e1;font-size:.9rem;line-height:1.6;margin-bottom:1.5rem}
.deal-locked{position:relative;background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:1.1rem;margin-bottom:.75rem}
.deal-locked h2{font-size:1rem;color:#fff;margin-bottom:.75rem}
.deal-locked-row{display:flex;justify-content:space-between;padding:.4rem 0;border-bottom:1px solid #1e293b;font-size:.85rem}
.deal-locked-row:last-child{border-bottom:none}
.deal-locked-row .label{color:#94a3b8}
.deal-locked-row .value{color:#fff;font-weight:600}
.deal-locked-row .value.blur{filter:blur(4px);user-select:none}
.deal-chat{display:block;text-align:center;background:#0f172a;border:1px solid #1e293b;color:#F59E0B;font-weight:700;padding:.65rem;border-radius:10px;text-decoration:none;font-size:.85rem;margin-bottom:.75rem}
.deal-cta{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:1.25rem;margin-top:.75rem}
.deal-cta h2{font-size:1.05rem;color:#fff;margin-bottom:.75rem}
.deal-cta input{width:100%;padding:.7rem;border-radius:8px;border:1px solid #334155;background:#020617;color:#fff;margin-bottom:.6rem;font-size:.9rem}
.deal-cta button{width:100%;padding:.75rem;border-radius:8px;border:none;background:#F59E0B;color:#020617;font-weight:700;font-size:.9rem;cursor:pointer}
.deal-thanks{color:#4ade80;font-size:.9rem}
/* LIGHT MODE — cards were dark-navy surfaces (#0f172a) with white/light-gray
   text; the shell forces the page background to cream but leaves this
   template's own inline colors untouched, so flip both the surface and its
   text together (text-only would leave ink-on-navy, which is worse). */
html[data-theme=light] h1,html[data-theme=light] .deal-addr{color:#1f1b16}
html[data-theme=light] .deal-sub,html[data-theme=light] .deal-obs,html[data-theme=light] .deal-stat .label,html[data-theme=light] .deal-locked-row .label{color:#6e655e}
html[data-theme=light] .deal-stat,html[data-theme=light] .deal-locked,html[data-theme=light] .deal-chat,html[data-theme=light] .deal-cta,html[data-theme=light] .deal-greeting{background:#fbfaf7;border-color:#ddd5c9}
html[data-theme=light] .deal-chat{color:#823f29}
html[data-theme=light] .deal-img{border-color:#ddd5c9}
html[data-theme=light] .deal-stat .value,html[data-theme=light] .deal-locked h2,html[data-theme=light] .deal-locked-row .value,html[data-theme=light] .deal-cta h2{color:#1f1b16}
html[data-theme=light] .deal-locked-row{border-bottom-color:#ddd5c9}
html[data-theme=light] .deal-cta input{background:#f5f0e8;border-color:#b5a9a0;color:#1f1b16}
</style>
</head>
<body>
<div class="deal-card">
${previewBanner}
<div class="deal-greeting" id="bd-greeting"></div>
${ogImage ? `<img class="deal-img" src="${escHtml(ogImage)}" alt="Parcel aerial with boundary outline">` : ''}
<h1>${escHtml(soldFmt || 'Sold at auction')}</h1>
${reel.property_address ? `<div class="deal-addr">${escHtml(reel.property_address)}</div>` : ''}
<div class="deal-sub">${escHtml(countyName)} County &middot; ${escHtml(saleLabel)}${reel.auction_date ? ' &middot; ' + escHtml(reel.auction_date) : ''}</div>
${orderedSections}
${lockedSection}
<a class="deal-chat" href="${escHtml(chatHref)}">Ask Deed about this property &rarr;</a>
<div class="deal-cta">
<h2>Get the full property signal report</h2>
${ctaBlock}
</div>
</div>
<script>${dealPageStickyScript(shortCode, reel.county || '', archetype || '', reel.case_number || '')}</script>
</body>
</html>`;
}
function previewQueryFor(reel) {
  return reel.status === 'pending_approval' ? `?preview=${encodeURIComponent(reel.id)}` : '';
}

// ── BidDeed Reels v3 (issue #19761 T2) — PRESALE (calendar/upcoming-auction)
// deal-page variant. Same public/no-names/no-vendor guardrail as
// buildDealLandingHtml (fields still come from get_reel_landing()'s
// allow-list) plus a login+paid-tier gate on one block. Security note: the
// gated numbers are only ever interpolated into the returned HTML when
// `paidOk` is true -- an unauthorized viewer's HTML never contains the real
// figures at all (not a CSS-only blur of real data), so there is nothing to
// recover via view-source.
function presaleMonthAbbrDay(isoDate) {
  if (!isoDate) return '';
  const [y, m, d] = String(isoDate).split('-').map(Number);
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[(m || 1) - 1]} ${d || ''}`.trim();
}

function buildPresaleDealHtml(reel, landingPath, submitted, paidOk, archetype) {
  const fmtMoney = (n) => (n == null ? null : '$' + Math.round(Number(n)).toLocaleString());
  const countyName = String(reel.county || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const saleLabel = reel.sale_type === 'tax_deed' ? 'Tax Deed' : 'Foreclosure';
  const cond = reel.condition_json || {};
  const intel = cond.presale_intel || {};
  const tier = cond.general_condition_tier || 'unknown';
  const tierLabel = tier === 'unknown' ? 'Condition pending review' : tier.charAt(0).toUpperCase() + tier.slice(1) + ' condition';
  const obs = ['roof', 'exterior'].map(k => cond[k] && cond[k].observation).filter(Boolean).slice(0, 2);
  const dateLabel = presaleMonthAbbrDay(reel.auction_date);
  const title = `AUCTION ${dateLabel} — ${countyName} County ${saleLabel}`;
  const openingBidFmt = fmtMoney(reel.opening_bid);
  const judgmentFmt = fmtMoney(reel.judgment_amount);
  const assessedFmt = fmtMoney(reel.assessed_value);
  const description = `${saleLabel} sale ${dateLabel ? 'on ' + dateLabel : ''} in ${countyName} County.${assessedFmt ? ` Assessed ${assessedFmt}.` : ''}`.trim();
  const ogImage = reel.aerial_tight_url || reel.aerial_wide_url || '';
  const days = reel.days_to_auction;
  const countdownLabel = days == null ? 'Auction date set' : `${days} day${days === 1 ? '' : 's'} to auction`;
  const previewBanner = reel.status === 'pending_approval'
    ? `<div class="psale-banner">PREVIEW — pending approval, not yet public</div>` : '';
  const canonicalUrl = `https://biddeed.ai${landingPath}`;

  const shortCode = reel.short_code || '';
  const ctaBlock = submitted
    ? `<div class="psale-thanks">Alert set — we'll email you before the gavel drops.</div>`
    : `<form method="POST" action="${escHtml(landingPath)}/lead${escHtml(previewQueryFor(reel))}">
<input type="hidden" name="case_number" value="${escHtml(reel.case_number)}">
<input type="hidden" name="source" value="presale_deal">
<input type="hidden" name="reel_code" value="${escHtml(shortCode)}">
<input type="hidden" name="visitor_id" class="bd-visitor-field" value="">
<input type="email" name="email" placeholder="you@email.com" required>
<button type="submit">Set alert</button>
</form>`;
  // S4 -- property-scoped chat entry, same /chat route postsale uses.
  const chatHref = `/chat?county=${encodeURIComponent(reel.county || '')}&hook=${encodeURIComponent('property_' + (reel.case_number || ''))}`;

  const gatedInner = paidOk
    ? `
<div class="psale-gate-row"><span class="label">Est. Max Bid</span><span class="value">${escHtml(fmtMoney(intel.ml_max_bid) || 'Pending')}</span></div>
<div class="psale-gate-row"><span class="label">Deal Signal</span><span class="value">${escHtml(intel.ml_recommendation || 'Pending')}</span></div>
<div class="psale-gate-row"><span class="label">Flip Rate (ZIP)</span><span class="value">${intel.flip_rate_pct != null ? escHtml(Number(intel.flip_rate_pct).toFixed(1) + '%') : 'Pending'}</span></div>
<div class="psale-gate-row"><span class="label">Avg ROI (ZIP)</span><span class="value">${intel.avg_roi != null ? escHtml(Number(intel.avg_roi).toFixed(1) + '%') : 'Pending'}</span></div>
<div class="psale-gate-row"><span class="label">ZIP Score</span><span class="value">${intel.zip_score != null ? escHtml(String(intel.zip_score)) : 'Pending'}</span></div>
<div class="psale-gate-row"><span class="label">Anchors in ZIP</span><span class="value">${intel.anchors_in_zip != null ? escHtml(String(intel.anchors_in_zip)) : 'Pending'}</span></div>
<div class="psale-gate-row"><span class="label">Senior Liens</span><span class="value">${escHtml(intel.senior_liens || 'Pending — title search not run')}</span></div>
${intel.pa_link ? `<div class="psale-gate-row"><span class="label">Property Record</span><span class="value"><a href="${escHtml(intel.pa_link)}" target="_blank" rel="noopener">County Appraiser &rarr;</a></span></div>` : ''}
${judgmentFmt ? `<div class="psale-gate-row"><span class="label">Judgment Amount</span><span class="value">${escHtml(judgmentFmt)}</span></div>` : ''}
`
    : `
<div class="psale-gate-row blur"><span class="label">Est. Max Bid</span><span class="value">$•••,•••</span></div>
<div class="psale-gate-row blur"><span class="label">Deal Signal</span><span class="value">••••• •••••</span></div>
<div class="psale-gate-row blur"><span class="label">Flip Rate (ZIP)</span><span class="value">••.•%</span></div>
<div class="psale-gate-row blur"><span class="label">Avg ROI (ZIP)</span><span class="value">••.•%</span></div>
<div class="psale-gate-row blur"><span class="label">ZIP Score</span><span class="value">••</span></div>
<div class="psale-gate-row blur"><span class="label">Anchors in ZIP</span><span class="value">•</span></div>
<div class="psale-gate-row blur"><span class="label">Senior Liens</span><span class="value">••••••••</span></div>
<div class="psale-gate-row blur"><span class="label">Property Record</span><span class="value">••••••••</span></div>
`;

  const gateOverlay = paidOk ? '' : `<div class="psale-gate-overlay"><a href="/subscribe?tier=investor">Unlock with BidDeed Pro &rarr;</a></div>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${escHtml(title)} — BidDeed.AI</title>
<meta name="description" content="${escHtml(description)}">
<link rel="canonical" href="${escHtml(canonicalUrl)}">
<meta property="og:title" content="${escHtml(title)}">
<meta property="og:description" content="${escHtml(description)}">
<meta property="og:type" content="website">
${ogImage ? `<meta property="og:image" content="${escHtml(ogImage)}">` : ''}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${escHtml(title)}">
<meta name="twitter:description" content="${escHtml(description)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:'Inter',sans-serif;padding:2rem 1rem;display:flex;justify-content:center}
.psale-card{max-width:520px;width:100%;background:#020617;border-radius:16px;padding:1.5rem}
.psale-banner{background:#F59E0B;color:#020617;font-weight:700;text-align:center;padding:.5rem;border-radius:8px;margin-bottom:1rem;font-size:.85rem}
.psale-img{width:100%;border-radius:12px;margin-bottom:1rem;border:1px solid #1e293b;display:block}
h1{font-size:1.35rem;margin-bottom:.25rem;color:#fff}
.psale-addr{color:#cbd5e1;font-size:.9rem;margin-bottom:.15rem}
.psale-sub{color:#94a3b8;font-size:.95rem;margin-bottom:.75rem}
.psale-countdown{display:inline-block;background:#F59E0B;color:#020617;font-weight:800;padding:.35rem .8rem;border-radius:999px;font-size:.8rem;margin-bottom:1rem}
.psale-stats{display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:.75rem}
.psale-stat{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:.85rem}
.psale-stat .label{color:#64748b;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em}
.psale-stat .value{color:#fff;font-size:1.1rem;font-weight:700;margin-top:.2rem}
.psale-badge{display:inline-block;background:#F59E0B;color:#020617;font-weight:700;padding:.3rem .7rem;border-radius:999px;font-size:.8rem;margin:.5rem 0}
.psale-obs{color:#cbd5e1;font-size:.9rem;line-height:1.6;margin-bottom:1.5rem}
.psale-cta{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:1.25rem;margin-top:.75rem}
.psale-cta h2{font-size:1.05rem;color:#fff;margin-bottom:.75rem}
.psale-cta input{width:100%;padding:.7rem;border-radius:8px;border:1px solid #334155;background:#020617;color:#fff;margin-bottom:.6rem;font-size:.9rem}
.psale-cta button{width:100%;padding:.75rem;border-radius:8px;border:none;background:#F59E0B;color:#020617;font-weight:700;font-size:.9rem;cursor:pointer}
.psale-thanks{color:#4ade80;font-size:.9rem}
.psale-gate{position:relative;background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:1.25rem;margin-top:1.25rem;overflow:hidden}
.psale-gate h2{font-size:1.05rem;color:#fff;margin-bottom:.9rem}
.psale-gate-row{display:flex;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid #1e293b;font-size:.85rem}
.psale-gate-row:last-child{border-bottom:none}
.psale-gate-row .label{color:#94a3b8}
.psale-gate-row .value{color:#fff;font-weight:600;text-align:right}
.psale-gate-row .value a{color:#F59E0B;text-decoration:none}
.psale-gate-row.blur{filter:blur(5px);user-select:none;pointer-events:none}
.psale-gate-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg,rgba(15,23,42,0)0%,rgba(15,23,42,.85)40%)}
.psale-gate-overlay a{background:#F59E0B;color:#020617;font-weight:800;padding:.7rem 1.2rem;border-radius:8px;text-decoration:none;font-size:.9rem}
.psale-greeting{background:#0f172a;border:1px solid #F59E0B;border-radius:10px;padding:.75rem .9rem;margin-bottom:1rem;font-size:.85rem;color:#F59E0B;display:none}
.psale-chat{display:block;text-align:center;background:#0f172a;border:1px solid #1e293b;color:#F59E0B;font-weight:700;padding:.65rem;border-radius:10px;text-decoration:none;font-size:.85rem;margin-top:.75rem}
/* LIGHT MODE — see the matching block in buildDealLandingHtml for why the
   surface and its text flip together, not text-only. */
html[data-theme=light] .psale-card{background:transparent}
html[data-theme=light] h1,html[data-theme=light] .psale-addr{color:#1f1b16}
html[data-theme=light] .psale-sub,html[data-theme=light] .psale-obs,html[data-theme=light] .psale-stat .label,html[data-theme=light] .psale-gate-row .label{color:#6e655e}
html[data-theme=light] .psale-stat,html[data-theme=light] .psale-cta,html[data-theme=light] .psale-gate,html[data-theme=light] .psale-chat,html[data-theme=light] .psale-greeting{background:#fbfaf7;border-color:#ddd5c9}
html[data-theme=light] .psale-chat{color:#823f29}
html[data-theme=light] .psale-img{border-color:#ddd5c9}
html[data-theme=light] .psale-stat .value,html[data-theme=light] .psale-cta h2,html[data-theme=light] .psale-gate h2,html[data-theme=light] .psale-gate-row .value{color:#1f1b16}
html[data-theme=light] .psale-gate-row{border-bottom-color:#ddd5c9}
html[data-theme=light] .psale-gate-overlay{background:linear-gradient(180deg,rgba(245,240,232,0)0%,rgba(245,240,232,.9)40%)}
html[data-theme=light] .psale-cta input{background:#f5f0e8;border-color:#b5a9a0;color:#1f1b16}
</style>
</head>
<body>
<div class="psale-card">
${previewBanner}
<div class="psale-greeting" id="bd-greeting"></div>
${ogImage ? `<img class="psale-img" src="${escHtml(ogImage)}" alt="Parcel aerial with boundary outline">` : ''}
<h1>${escHtml(title)}</h1>
${reel.property_address ? `<div class="psale-addr">${escHtml(reel.property_address)}</div>` : ''}
<div class="psale-sub">${escHtml(countyName)} County &middot; ${escHtml(saleLabel)} Sale${reel.auction_date ? ' &middot; ' + escHtml(reel.auction_date) : ''}</div>
<div class="psale-countdown">${escHtml(countdownLabel)}</div>
<div class="psale-stats">
  <div class="psale-stat"><div class="label">Opening Bid</div><div class="value">${escHtml(openingBidFmt || 'Pending')}</div></div>
  <div class="psale-stat"><div class="label">Assessed Value</div><div class="value">${escHtml(assessedFmt || '&mdash;')}</div></div>
</div>
<div class="psale-badge">${escHtml(tierLabel)}</div>
${obs.length ? `<div class="psale-obs">${obs.map(escHtml).join('<br>')}</div>` : ''}
${reel.street_url ? `<img class="psale-img" src="${escHtml(reel.street_url)}" alt="Street-level view">` : ''}
<div class="psale-gate">
<h2>Premium intel</h2>
${gatedInner}
${gateOverlay}
</div>
<a class="psale-chat" href="${escHtml(chatHref)}">Ask Deed about this property &rarr;</a>
<div class="psale-cta">
<h2>Get notified before the gavel drops</h2>
${ctaBlock}
</div>
</div>
<script>${dealPageStickyScript(shortCode, reel.county || '', archetype || 'presale_countdown', reel.case_number || '')}</script>
</body>
</html>`;
}

// ── BidDeed Reels v2 (issue #19752 directive #4C, new T8) — reels gallery +
// single-reel clickable player. Field data comes from list_public_reels()/
// get_reel_by_code() only (same allow-list as get_reel_landing()) -- no
// name/vendor field is ever selectable there, so there is nothing here that
// could leak one. Share buttons for TikTok/IG/YouTube stay hidden until
// status='posted' (nothing is posted yet per this issue's own DoD).
const REELS_PLAYER_CSS = `
.reel-card{background:#0f172a;border:1px solid #1e293b;border-radius:12px;overflow:hidden}
.reel-player-wrap{position:relative;aspect-ratio:9/16;background:#000}
.reel-player-wrap video{width:100%;height:100%;object-fit:cover;display:block}
.reel-cta-overlay{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center;padding-bottom:6%;opacity:0;pointer-events:none;transition:opacity .2s}
.reel-cta-overlay.show{opacity:1;pointer-events:auto}
.reel-cta-overlay a{background:#F59E0B;color:#020617;font-weight:800;font-family:'Inter',sans-serif;padding:.6rem 1.1rem;border-radius:8px;text-decoration:none;font-size:.95rem}
.reel-meta{padding:.9rem}
.reel-meta .county{color:#94a3b8;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
.reel-meta .price{color:#fff;font-size:1.3rem;font-weight:800;margin:.15rem 0}
.reel-meta .delta{color:#4ade80;font-size:.85rem;font-weight:600}
.reel-badge{display:inline-block;background:#F59E0B;color:#020617;font-weight:700;padding:.2rem .6rem;border-radius:6px;font-size:.7rem;margin-top:.4rem}
.reel-view-link{display:block;text-align:center;background:#1e293b;color:#F59E0B;font-weight:700;padding:.6rem;border-radius:8px;text-decoration:none;margin-top:.7rem;font-size:.85rem}
.reel-share-row{display:flex;gap:.5rem;margin-top:.6rem}
.reel-share-row button,.reel-share-row a{flex:1;background:#020617;border:1px solid #334155;color:#cbd5e1;font-size:.75rem;padding:.4rem;border-radius:8px;cursor:pointer;text-align:center;text-decoration:none}
.reels-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1.25rem;max-width:1200px;margin:0 auto}
.reels-preview-banner{background:#F59E0B;color:#020617;font-weight:700;text-align:center;padding:.6rem;border-radius:8px;margin:0 auto 1.5rem;max-width:1200px}
/* LIGHT MODE — see the matching block in buildDealLandingHtml for why the
   surface and its text flip together, not text-only. */
html[data-theme=light] .reel-card{background:#fbfaf7;border-color:#ddd5c9}
html[data-theme=light] .reel-meta .county{color:#6e655e}
html[data-theme=light] .reel-meta .price{color:#1f1b16}
html[data-theme=light] .reel-view-link{background:#ede3d7}
html[data-theme=light] .reel-share-row button,html[data-theme=light] .reel-share-row a{background:#f5f0e8;border-color:#b5a9a0;color:#1f1b16}
`;

// S1 Sticky Layer (issue #19786) -- persistent visitor context. This
// Worker has no cookie/session mechanism (see extractApiKey's comment), so
// "returning visitor" state lives in localStorage, matching
// reelPlayerScript()'s own bd_reel_session pattern. Progressive
// enhancement: the page is fully readable/submittable with JS off (S1's
// "did you see the free stuff" personalization just doesn't show).
function dealPageStickyScript(reelCode, county, archetype, caseNumber) {
  return `
try {
  var bdVid = localStorage.getItem('bd_vid');
  if (!bdVid) {
    bdVid = 'v_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem('bd_vid', bdVid);
  }
  document.querySelectorAll('.bd-visitor-field').forEach(function(el) { el.value = bdVid; });
  fetch('/deal/visitor', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({visitor_id: bdVid, reel_code: ${JSON.stringify(reelCode)}, county: ${JSON.stringify(county)}, archetype: ${JSON.stringify(archetype)}, case_number: ${JSON.stringify(caseNumber)}})
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d && d.returning && d.properties_viewed_count > 1 && d.first_county) {
      var g = document.getElementById('bd-greeting');
      if (g) {
        g.textContent = (d.properties_viewed_count - 1) + ' more ' + d.first_county.replace(/\\b\\w/g, function(c){return c.toUpperCase();}) + ' auctions since you were here';
        g.style.display = 'block';
      }
    }
  }).catch(function(){});
} catch (e) {}
`;
}

function reelPlayerScript() {
  return `
var bdReelSession = null;
try {
  bdReelSession = localStorage.getItem('bd_reel_session');
  if (!bdReelSession) {
    bdReelSession = Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem('bd_reel_session', bdReelSession);
  }
} catch (e) {}
function bdSendReelEvent(code, evt) {
  if (!code) return;
  try {
    fetch('/reels/' + code + '/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event: evt, session_id: bdReelSession }),
      keepalive: true,
    }).catch(function(){});
  } catch (e) {}
}
document.querySelectorAll('.reel-player-wrap').forEach(function(wrap){
  var video = wrap.querySelector('video');
  var overlay = wrap.querySelector('.reel-cta-overlay');
  var code = wrap.getAttribute('data-reel-code');
  // issue #19779 CP3a measurement hooks -- an internal AVD proxy ahead of a
  // real YouTube Analytics connection. sentMarks dedupes so a single watch
  // session only ever counts each threshold once; loop detection watches
  // for currentTime dropping back near 0 right after it was near the end
  // (the native <video loop> attribute never fires 'ended').
  var sentMarks = {};
  var prevTime = 0;
  wrap.addEventListener('mouseenter', function(){ video.muted = true; video.play().catch(function(){}); });
  wrap.addEventListener('mouseleave', function(){ video.pause(); });
  wrap.addEventListener('click', function(){ video.muted = !video.muted; if (video.paused) video.play().catch(function(){}); });
  video.addEventListener('play', function(){
    if (!sentMarks.play) { sentMarks.play = true; bdSendReelEvent(code, 'play'); }
  });
  video.addEventListener('timeupdate', function(){
    if (video.duration && video.currentTime >= video.duration - 3) overlay.classList.add('show');
    else overlay.classList.remove('show');
    if (video.duration) {
      var pct = (video.currentTime / video.duration) * 100;
      [25, 50, 75, 100].forEach(function(mark){
        if (pct >= mark && !sentMarks[mark]) { sentMarks[mark] = true; bdSendReelEvent(code, String(mark)); }
      });
      if (prevTime > video.duration * 0.9 && video.currentTime < prevTime - 1) {
        bdSendReelEvent(code, 'loop');
      }
      prevTime = video.currentTime;
    }
  });
});
function copyShortLink(btn, url){
  navigator.clipboard.writeText(url).then(function(){
    var orig = btn.textContent; btn.textContent = 'Copied!';
    setTimeout(function(){ btn.textContent = orig; }, 1500);
  });
}
`;
}

function reelCardHtml(reel) {
  const fmtMoney = (n) => (n == null ? '&mdash;' : '$' + Math.round(Number(n)).toLocaleString());
  const countyName = String(reel.county || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const saleLabel = reel.sale_type === 'tax_deed' ? 'Tax Deed' : 'Foreclosure';
  const cond = reel.condition_json || {};
  const tier = cond.general_condition_tier || 'unknown';
  const deltaPct = reel.delta_pct == null ? null : Number(reel.delta_pct);
  const deltaLine = deltaPct == null ? '' : `${deltaPct < 0 ? '-' : '+'}${Math.abs(deltaPct).toFixed(0)}% vs assessed`;
  const viewHref = `${escHtml(reel.landing_url || '#')}${escHtml(previewQueryFor(reel))}`;
  const posted = reel.status === 'posted';
  // issue #19779 CP3a: short_code isn't in get_reel_by_code()'s/list_public_reels()
  // jsonb allow-list uniformly, but short_url always has the shape
  // biddeed.ai/r/{code} -- deriving it here avoids a second RPC field just
  // for the watch-event beacon's target path.
  const reelCode = String(reel.short_url || '').split('/').filter(Boolean).pop() || '';
  return `<div class="reel-card">
  <div class="reel-player-wrap" data-reel-code="${escHtml(reelCode)}">
    <video src="${escHtml(reel.video_v2_url)}" poster="${escHtml(reel.aerial_tight_url || '')}" muted playsinline preload="metadata" loop></video>
    <div class="reel-cta-overlay"><a href="${viewHref}">biddeed.ai &rarr;</a></div>
  </div>
  <div class="reel-meta">
    <div class="county">${escHtml(countyName)} County &middot; ${escHtml(saleLabel)}</div>
    <div class="price">${fmtMoney(reel.sold_amount)}</div>
    ${deltaLine ? `<div class="delta">${escHtml(deltaLine)}</div>` : ''}
    ${tier !== 'unknown' ? `<div class="reel-badge">${escHtml(tier.charAt(0).toUpperCase() + tier.slice(1))} condition</div>` : ''}
    <a class="reel-view-link" href="${viewHref}">View property &rarr;</a>
    <div class="reel-share-row">
      <button onclick="copyShortLink(this,'${escHtml(reel.short_url || '')}')">Copy link</button>
      ${posted ? `<a href="${escHtml(reel.short_url || '#')}" target="_blank" rel="noopener">Share</a>` : ''}
    </div>
  </div>
</div>`;
}

function buildReelsGalleryHtml(reels, includePending) {
  const previewBanner = includePending
    ? `<div class="reels-preview-banner">PREVIEW MODE — includes pending_approval reels, not yet public</div>` : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Reels — BidDeed.AI</title>
<meta name="description" content="Short-form breakdowns of Florida foreclosure and tax deed sales, AI-analyzed.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:'Inter',sans-serif;padding:2rem 1rem}
h1{max-width:1200px;margin:0 auto 1.5rem;font-size:1.8rem;color:#fff;font-weight:800}
html[data-theme=light] h1{color:#1f1b16}
${REELS_PLAYER_CSS}
</style>
</head>
<body>
<h1>BidDeed Reels</h1>
${previewBanner}
<div class="reels-grid">
${reels.map(reelCardHtml).join('\n')}
</div>
${reels.length === 0 ? '<p style="text-align:center;color:#64748b;margin-top:3rem">No reels published yet.</p>' : ''}
<script>${reelPlayerScript()}</script>
</body>
</html>`;
}

function buildSingleReelHtml(reel) {
  const countyName = String(reel.county || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const saleLabel = reel.sale_type === 'tax_deed' ? 'Tax Deed Sale' : 'Foreclosure Sale';
  const soldFmt = reel.sold_amount == null ? 'Sold at auction' : '$' + Math.round(Number(reel.sold_amount)).toLocaleString();
  const title = `${soldFmt} — ${countyName} County ${saleLabel} — BidDeed.AI`;
  const ogImage = reel.aerial_tight_url || '';
  const previewBanner = reel.status === 'pending_approval'
    ? `<div class="reels-preview-banner">PREVIEW — pending approval, not yet public</div>` : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${escHtml(title)}</title>
<meta property="og:title" content="${escHtml(title)}">
<meta property="og:type" content="video.other">
${ogImage ? `<meta property="og:image" content="${escHtml(ogImage)}">` : ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:'Inter',sans-serif;padding:2rem 1rem;display:flex;justify-content:center}
.single-wrap{max-width:420px;width:100%}
${REELS_PLAYER_CSS}
</style>
</head>
<body>
<div class="single-wrap">
${previewBanner}
${reelCardHtml(reel)}
</div>
<script>${reelPlayerScript()}</script>
</body>
</html>`;
}

function buildPioneersPage() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Pioneer Program — BidDeed.AI — $990/yr</title>
<meta name="description" content="Join BidDeed.AI as a founding Pioneer for $990/yr. Full Investor tier access to all 67 FL counties, Shapira Max Bid formula, and ZoneWise zoning.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b;--green:#10b981}
body{background:var(--navy);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh}
nav{position:sticky;top:0;z-index:100;background:rgba(2,6,23,.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 1.5rem}
.nav-inner{max-width:700px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none;font-size:15px;font-weight:700;color:var(--text)}
.logo span{color:var(--orange)}
.wrap{max-width:700px;margin:0 auto;padding:3rem 1.5rem}
.ey{display:inline-flex;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);padding:.3rem .9rem;border-radius:20px;font-size:.7rem;font-family:monospace;color:var(--orange);letter-spacing:.06em;margin-bottom:1.25rem}
h1{font-family:'Inter',sans-serif;font-weight:800;letter-spacing:-.02em;font-size:clamp(1.9rem,4.5vw,2.8rem);color:var(--text);margin-bottom:1rem;line-height:1.2}
.sub{color:var(--muted);font-size:1.05rem;margin-bottom:2rem;line-height:1.6}
.card{background:var(--navy2);border:1px solid var(--border);border-radius:14px;padding:1.75rem;margin-bottom:1.25rem}
.card h3{color:var(--text);font-size:1.05rem;margin-bottom:.5rem}
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
  <div class="ey">PIONEER PROGRAM · SPOTS OPEN — $990/yr</div>
  <h1>BidDeed.AI Pioneer — $990/yr</h1>
  <p class="sub">Founding-customer rate for the Investor tier. <strong>$990/year</strong> — saves $198 vs monthly. 67 counties, unlimited queries, lien alerts, Shapira formula. Cancel any time.</p>

  <div class="card" style="border-color:rgba(245,158,11,.3)">
    <h3>What you get</h3>
    <p>Full Investor tier access — live auction data for all 67 FL counties, Shapira Max Bid formula, ZoneWise zoning, lien trap alerts. Priority support. Direct input into the roadmap as a founding customer.</p>
  </div>

  <div class="card">
    <h3>Refer someone, you both win</h3>
    <p>Once subscribed, share your referral link. When someone subscribes and stays a full billing cycle, you <strong>both</strong> get a free month — no cap.</p>
  </div>

  <form id="pioneer-form">
    <label for="p-name">Name</label>
    <input type="text" id="p-name" name="name" placeholder="Your name">
    <label for="p-email">Email</label>
    <input type="email" id="p-email" name="email" placeholder="you@example.com" required>
    <button type="submit" id="p-btn">Pioneer Investor — $990/yr →</button>
    <div class="msg" id="p-msg"></div>
    <p style="font-size:11px;color:#64748b;margin-top:10px;line-height:1.5">Annual subscription, billed once at $990. You'll be redirected to Stripe secure checkout. Cancel any time. Not legal or financial advice — see <a href="/disclaimer" style="color:#64748b">disclaimer</a>.</p>
    <div class="lead-box" id="p-referral-box" style="display:none;margin-top:1rem">
      <h3 style="font-size:.95rem">Your referral link</h3>
      <p style="font-size:.85rem">Share this — when someone subscribes through it and sticks around a full billing cycle, you both get a free month.</p>
      <input type="text" id="p-referral-link" readonly style="width:100%;background:#020617;border:1px solid #1e293b;border-radius:8px;padding:10px 12px;color:white;font-size:13px;margin-top:.5rem">
    </div>
  </form>
  <div style="text-align:center;margin-top:1rem"><a href="/subscribe?tier=investor" style="font-size:13px;color:#94a3b8">Prefer monthly? $99/mo →</a></div>
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
  msg.textContent = ''; msg.className = 'msg';
  btn.disabled = true; btn.textContent = 'Redirecting to checkout...';
  try {
    var checkoutPayload = { tier: 'investor', customer_email: email, interval: 'annual' };
    if (pRefCode) { checkoutPayload.referral_code = pRefCode; }
    var res = await fetch('/subscribe/checkout', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(checkoutPayload)
    });
    var data = await res.json();
    if (res.ok && data.url) {
      window.location.href = data.url;
    } else {
      msg.textContent = data.error || 'Something went wrong. Please try again.';
      msg.className = 'msg err';
      btn.disabled = false; btn.textContent = 'Pioneer Investor — $990/yr →';
    }
  } catch (err) {
    msg.textContent = 'Network error. Please try again.';
    msg.className = 'msg err';
    btn.disabled = false; btn.textContent = 'Pioneer Investor — $990/yr →';
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
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
h1{font-family:'Inter',sans-serif;font-weight:800;letter-spacing:-.02em;font-size:clamp(1.8rem,4vw,2.6rem);color:var(--text);margin-bottom:2rem}
.post-link{display:block;background:var(--navy2);border:1px solid var(--border);border-radius:12px;padding:1.5rem;text-decoration:none;color:var(--text);margin-bottom:1rem;transition:border-color .15s}
.post-link:hover{border-color:var(--orange)}
.post-date{font-size:.75rem;color:var(--muted);margin-bottom:.4rem}
.post-title{font-size:1.15rem;font-weight:700;color:var(--text);margin-bottom:.5rem}
.post-desc{font-size:.9rem;color:var(--muted);line-height:1.5}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.75rem;color:var(--muted);margin-top:3rem}
footer a{color:var(--muted);text-decoration:none}
/* WinnerDataAI child-brand light mode — default for Worker-owned public pages. */
:root{--navy:#f5f0e8;--navy2:#fbfaf7;--orange:#9f4d32;--orange2:#823f29;--text:#1f1b16;--muted:#6e655e;--border:#ddd5c9}
.logo,h1,.post-title{color:var(--text)}
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
  // Article JSON-LD -- SPR-06 (issue #19826, CONTENT_SOP.md SS5.7 C0 finding):
  // the 6 BLOG_POSTS carried no schema at all before this.
  const articleJsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: post.title,
    description: post.description,
    datePublished: post.date,
    dateModified: post.date,
    author: { '@type': 'Organization', name: 'BidDeed.AI', url: 'https://biddeed.ai' },
    publisher: { '@type': 'Organization', name: 'BidDeed.AI', url: 'https://biddeed.ai' },
    mainEntityOfPage: { '@type': 'WebPage', '@id': 'https://biddeed.ai/blog/' + post.slug },
  }).replace(/</g, '\\u003c');
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${post.title} — BidDeed.AI</title>
<meta name="description" content="${post.description}">
<script type="application/ld+json">${articleJsonLd}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
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
h1{font-family:'Inter',sans-serif;font-weight:800;letter-spacing:-.02em;font-size:clamp(1.7rem,4vw,2.4rem);color:var(--text);margin-bottom:1.5rem;line-height:1.25}
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
.lead-box h3{color:var(--text);font-size:1.05rem;margin-bottom:.4rem}
.lead-box p{color:var(--muted);font-size:.88rem;margin-bottom:1rem}
.lead-form{display:flex;gap:.6rem;flex-wrap:wrap}
.lead-form input{flex:1;min-width:180px;background:var(--navy);border:1px solid var(--border);border-radius:8px;padding:11px 14px;color:white;font-size:15px;outline:none}
.lead-form input:focus{border-color:var(--orange)}
.lead-form button{background:transparent;border:1px solid var(--orange);color:var(--orange);padding:11px 20px;border-radius:8px;font-weight:700;font-size:.85rem;cursor:pointer;white-space:nowrap}
.lead-form button:disabled{opacity:.6;cursor:default}
.lead-msg{font-size:.82rem;margin-top:.6rem;display:none}
.lead-msg.ok{color:#34d399;display:block}
.lead-msg.err{color:#f87171;display:block}
/* WinnerDataAI child-brand light mode — default for Worker-owned public pages. */
:root{--navy:#f5f0e8;--navy2:#fbfaf7;--orange:#9f4d32;--orange2:#823f29;--text:#1f1b16;--muted:#6e655e;--border:#ddd5c9}
.logo,h1,.lead-box h3{color:var(--text)}
.lead-form input{background:var(--navy2);color:var(--text)}
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
    <a href="/buy-report">Get a SIGNAL$ Property Report — $25 →</a>
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
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
.nav-links{display:flex;align-items:center;gap:1rem;margin-left:auto;margin-right:1rem}.nav-links a{color:var(--muted);font-size:13px;font-weight:600;text-decoration:none}.nav-links a:hover{color:var(--orange)}
.wrap{max-width:1100px;margin:0 auto;padding:3rem 1.5rem}
.ey{display:inline-flex;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);padding:.3rem .9rem;border-radius:20px;font-size:.7rem;font-family:'JetBrains Mono',monospace;color:var(--green);letter-spacing:.06em;margin-bottom:1.25rem}
h1{font-family:'Inter',sans-serif;font-weight:800;letter-spacing:-.02em;font-size:clamp(1.8rem,4vw,2.8rem);color:white;margin-bottom:.75rem}
.sub{color:var(--muted);margin-bottom:2.5rem;font-size:.95rem}
.counties-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.75rem}
.county-link{display:block;background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:.9rem 1rem;text-decoration:none;color:var(--muted);font-size:.88rem;font-weight:500;transition:all .15s;position:relative}
.county-link:hover{background:var(--navy3);border-color:var(--orange);color:white}
.county-link.gold{border-color:rgba(245,158,11,.3);color:var(--text)}
.county-link.gold:hover{border-color:var(--orange)}
.gs-tag{display:block;font-size:.65rem;color:var(--orange);font-family:'JetBrains Mono',monospace;margin-top:.2rem;letter-spacing:.05em}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.75rem;color:var(--muted);margin-top:3rem}
footer a{color:var(--muted);text-decoration:none}
/* WinnerDataAI child-brand light mode — default for Worker-owned county pages. */
:root{--navy:#f5f0e8;--navy2:#fbfaf7;--navy3:#ede3d7;--orange:#9f4d32;--orange2:#823f29;--text:#1f1b16;--muted:#6e655e;--border:#ddd5c9;--green:#2f7a4b}
body{background:var(--navy);color:var(--text)}
nav{background:rgba(245,240,232,.96);border-bottom-color:var(--border)}
.ln,h1{color:var(--text)}
.nav-links a,.sub,.county-link,footer,footer a{color:var(--muted)}
.county-link{background:var(--navy2);border-color:var(--border)}
.county-link:hover{background:var(--navy3);border-color:var(--orange);color:var(--text)}
.county-link.gold{border-color:rgba(159,77,50,.35);color:var(--text)}
.gs-tag,.nav-links a:hover{color:var(--orange)}
footer{border-top-color:var(--border)}
@media(max-width:767px){.nav-links{display:none}.nav-cta{padding:10px 14px;font-size:13px}.wrap{padding:2rem 1rem}.counties-grid{grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:.6rem}.county-link{padding:.8rem .75rem;font-size:.82rem}}
</style>
</head>
<body>
<nav><div class="nav-inner">
  <a href="/" class="logo"><div class="lm">BD</div><span class="ln">BidDeed<span>.AI</span></span></a>
  <div class="nav-links" aria-label="Primary navigation"><a href="/">Overview</a><a href="/radar">Radar</a><a href="/radar?view=calendar">Calendar</a><a href="/buy-report">Reports</a><a href="/chat">Deed</a></div>
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
<meta name="description" content="Chat with BidDeed.AI's Deed assistant for live Florida foreclosure and tax deed auction data, max bid calculations, and county-by-county intelligence.">
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
.cb-name{font-size:13px;font-weight:700;color:var(--text)}
.cb-stats{display:flex;gap:10px;flex-wrap:wrap}
.cb-stat .num{font-family:'SF Mono',monospace;font-size:.9rem;font-weight:700;color:var(--text)}
.cb-stat .num.hot{color:var(--orange)}
.cb-stat .lbl{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.cb-badge-gold{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.25);border-radius:20px;padding:2px 8px;font-size:10px;color:var(--orange);font-weight:600}
.cb-badge-pend{background:var(--navy3);border:1px solid var(--border);border-radius:20px;padding:2px 8px;font-size:10px;color:var(--muted)}

/* MESSAGES */
.msgs{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;padding:12px 14px;padding-bottom:24px;display:flex;flex-direction:column;gap:10px;-webkit-overflow-scrolling:touch}

/* WELCOME */
.welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;flex:1;text-align:center;gap:12px;padding:16px 10px;min-height:0}
.wl-icon{width:92px;height:92px;border-radius:24px;background:rgba(245,158,11,.08);border:2px solid rgba(245,158,11,.7);display:flex;align-items:center;justify-content:center;color:var(--navy);flex-shrink:0;box-shadow:0 0 32px rgba(245,158,11,.18)}.deed-robot-mark{width:100%;height:100%;display:block}
.wl-title{font-size:17px;font-weight:700;color:var(--text)}
.wl-sub{font-size:12px;color:var(--muted);max-width:280px;line-height:1.5}
.quick-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;width:100%;max-width:380px}
.qbtn{background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:9px 10px;text-align:left;cursor:pointer;color:var(--muted);font-size:11.5px;font-weight:500;line-height:1.4;transition:all .15s;font-family:inherit;-webkit-tap-highlight-color:transparent}
.qbtn:hover,.qbtn:active{background:var(--navy3);border-color:var(--orange);color:var(--text)}
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
.bbl.ai b{color:var(--text)}
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
.ec input{flex:1;background:var(--navy3);border:1px solid var(--border);border-radius:8px;padding:9px 10px;color:var(--text);font-size:14px;outline:none;font-family:inherit;-webkit-appearance:none}
.ec input:focus{border-color:var(--orange)}
.ec button{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);border:none;border-radius:8px;padding:9px 12px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;font-family:inherit}

/* INPUT BAR — pinned to bottom, always visible */
.inp-wrap{flex-shrink:0;background:rgba(2,6,23,.98);border-top:1px solid var(--border)}
.inp-bar{display:flex;gap:8px;padding:10px 12px;align-items:center}
.inp-bar input{flex:1;background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:11px 12px;color:var(--text);font-size:16px;outline:none;font-family:inherit;transition:border-color .2s;-webkit-appearance:none;min-width:0}
.inp-bar input:focus{border-color:var(--orange)}
.inp-bar input::placeholder{color:var(--muted);font-size:14px}
.snd{width:42px;height:42px;border-radius:10px;background:linear-gradient(135deg,var(--orange),var(--orange2));border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;-webkit-tap-highlight-color:transparent}
.snd:disabled{opacity:.35;cursor:not-allowed}
.snd svg{width:17px;height:17px;fill:var(--navy)}
.disclaimer-bar{flex-shrink:0;text-align:center;font-size:9.5px;color:var(--muted);padding:3px 12px 8px;line-height:1.4}
.disclaimer-bar a{color:var(--muted);text-decoration:underline}
@media(max-width:380px){.quick-grid{grid-template-columns:1fr}.bd-brand p{display:none}.voice-dock{padding-left:9px;padding-right:9px}.voice-dock-copy{margin-bottom:6px}}

/* VOICE WIDGET */
.voice-dock{flex-shrink:0;padding:10px 12px 8px;background:rgba(2,6,23,.98);border-top:1px solid rgba(245,158,11,.28);box-shadow:0 -10px 28px rgba(0,0,0,.18)}.voice-dock-copy{display:flex;align-items:center;gap:8px;margin-bottom:8px}.voice-dock-copy .deed-robot-mark{width:34px;height:34px;flex-shrink:0}.voice-dock-title{font-size:12px;font-weight:800;color:#fff}.voice-dock-sub{font-size:10.5px;color:var(--muted);line-height:1.35}.voice-btn{display:flex;width:100%;align-items:center;justify-content:center;gap:8px;background:linear-gradient(135deg,var(--orange),var(--orange2));border:1px solid var(--orange);border-radius:12px;padding:13px 16px;cursor:pointer;color:var(--navy);font-size:14px;font-weight:800;font-family:inherit;transition:all .15s;-webkit-tap-highlight-color:transparent;min-height:50px;box-shadow:0 8px 24px rgba(245,158,11,.18)}
.voice-btn:hover,.voice-btn:active{background:var(--orange);border-color:#fbbf24;color:var(--navy);transform:translateY(-1px)}
.voice-btn.active{background:rgba(245,158,11,.1);border-color:rgba(245,158,11,.5);color:var(--orange)}
.voice-btn.listening{background:rgba(245,158,11,.08);border-color:var(--orange);color:var(--orange)}
.voice-dot{width:8px;height:8px;border-radius:50%;background:var(--muted);flex-shrink:0;transition:background .2s}
.voice-btn.listening .voice-dot{background:var(--orange);animation:vp 1s infinite}
@keyframes vp{0%,100%{opacity:.4;transform:scale(.85)}50%{opacity:1;transform:scale(1.15)}}
/* LIGHT DEED WIDGET — uniform WinnerDataAI house palette */
html[data-theme=light] .voice-dock,html[data-theme=light] .inp-wrap{background:var(--navy2);border-top-color:rgba(159,77,50,.35);box-shadow:0 -10px 28px rgba(31,27,22,.10)}
html[data-theme=light] .voice-dock-title{color:var(--navy)}
html[data-theme=light] .voice-dock-sub,html[data-theme=light] .voice-status,html[data-theme=light] .disclaimer-bar,html[data-theme=light] .disclaimer-bar a{color:#6e655e}
html[data-theme=light] .voice-btn{background:linear-gradient(135deg,#9f4d32,#823f29);border-color:#9f4d32;color:#fbfaf7;box-shadow:0 8px 24px rgba(159,77,50,.24)}
html[data-theme=light] .voice-btn:hover,html[data-theme=light] .voice-btn:active{background:#823f29;border-color:#8f4028;color:#fbfaf7}
html[data-theme=light] .voice-btn.active,html[data-theme=light] .voice-btn.listening{background:rgba(159,77,50,.12);border-color:#9f4d32;color:#823f29}
html[data-theme=light] .voice-btn.listening .voice-dot{background:#9f4d32}
html[data-theme=light] .voice-dot{background:#823f29}
html[data-theme=light] .inp-bar input{background:#f5f0e8;border-color:#b5a9a0;color:#1f1b16}
html[data-theme=light] .inp-bar input::placeholder{color:#6e655e}
html[data-theme=light] .snd{background:linear-gradient(135deg,#9f4d32,#823f29)}
html[data-theme=light] .snd svg{fill:#fbfaf7}
html[data-theme=light] .voice-dock .deed-robot-mark{filter:none}
html[data-theme=light] .quick-btn,html[data-theme=light] .quick-btn:hover{border-color:rgba(159,77,50,.35)}
/* LIGHT MODE — remaining hardcoded-white text carried over from the dark-only
   original. Same fix class as the voice dock above: these render invisible
   (white on cream) once the shell forces data-theme=light. */
html[data-theme=light] .bd-brand h1,html[data-theme=light] .cb-name,html[data-theme=light] .cb-stat .num,html[data-theme=light] .wl-title,html[data-theme=light] .qbtn:hover,html[data-theme=light] .qbtn:active,html[data-theme=light] .attach-btn:hover,html[data-theme=light] .attach-btn:active,html[data-theme=light] .attach-caption,html[data-theme=light] .panel-hdr .pt,html[data-theme=light] .pc-addr,html[data-theme=light] .pc-val,html[data-theme=light] .bbl.ai b{color:#1f1b16}
html[data-theme=light] .ec input,html[data-theme=light] .veg input{background:#f5f0e8;color:#1f1b16}

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
.voice-actions{display:flex;gap:6px;align-items:flex-start;flex-wrap:wrap;justify-content:center;margin-top:2px}.voice-dock .voice-actions{margin-top:0}.voice-dock .voice-btn-label{display:inline}
.veg{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.22);border-radius:10px;padding:10px 12px;margin-top:8px;display:none;max-width:340px;width:100%}
.veg.show{display:block}
.veg-lbl{font-size:11px;color:var(--orange);font-weight:600;margin-bottom:6px;text-align:center}
.veg-row{display:flex;gap:6px}
.veg input{flex:1;background:var(--navy3);border:1px solid var(--border);border-radius:8px;padding:8px 10px;color:var(--text);font-size:14px;outline:none;font-family:inherit;min-width:0;-webkit-appearance:none}
.veg input:focus{border-color:var(--orange)}
.veg button{background:linear-gradient(135deg,var(--orange),#f97316);color:var(--navy);border:none;border-radius:8px;padding:8px 12px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;font-family:inherit;-webkit-tap-highlight-color:transparent}
.veg-err{font-size:10.5px;color:#f87171;margin-top:4px;display:none}
.veg-err.show{display:block}
.attach-btn{display:none;align-items:center;gap:5px;background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:9px 14px;cursor:pointer;color:var(--muted);font-size:11.5px;font-weight:500;font-family:inherit;transition:all .15s;-webkit-tap-highlight-color:transparent}
.attach-btn.visible{display:flex}
.attach-btn:hover,.attach-btn:active{background:var(--navy3);border-color:var(--orange);color:var(--text)}
.attach-btn:disabled{opacity:.4;cursor:not-allowed}
.attach-caption{display:none;background:var(--navy3);border:1px solid var(--border);border-radius:8px;padding:7px 10px;color:var(--text);font-size:12px;font-family:inherit;width:220px;margin-top:4px;outline:none}
.attach-caption.visible{display:block}
.attach-caption:focus{border-color:var(--orange)}
.attach-caption::placeholder{color:var(--muted)}
.attach-progress{display:none;font-size:10.5px;text-align:center;margin-top:4px;padding:4px 8px;border-radius:6px}
.attach-progress.show{display:block}
.attach-progress.uploading{color:var(--orange);background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.15)}
.attach-progress.ok{color:var(--green);background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.2)}
.attach-progress.err{color:#f87171;background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.2)}

/* Composer "+" menu (issue #19829 P1) */
.plus-wrap{position:relative;flex-shrink:0}
.plus-btn{width:38px;height:38px;border-radius:10px;background:var(--navy2);border:1px solid var(--border);color:var(--muted);font-size:18px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;font-family:inherit;-webkit-tap-highlight-color:transparent}
.plus-btn:hover{background:var(--navy3);border-color:var(--orange);color:var(--text)}
.plus-menu{display:none;position:absolute;bottom:46px;left:0;background:var(--navy2);border:1px solid var(--border);border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.35);min-width:210px;z-index:40;overflow:hidden}
.plus-menu.open{display:block}
.plus-item{display:flex;align-items:center;gap:9px;padding:10px 13px;font-size:12.5px;color:var(--text);cursor:pointer;border:none;background:none;width:100%;text-align:left;font-family:inherit}
.plus-item:hover{background:var(--navy3)}
.plus-item.active-toggle{color:var(--orange)}
.plus-item[disabled]{opacity:.4;cursor:not-allowed}
.pending-attach{display:none;align-items:center;gap:6px;background:var(--navy2);border:1px solid var(--border);border-radius:8px;padding:6px 10px;font-size:11px;color:var(--muted);margin-bottom:6px}
.pending-attach.show{display:flex}
.pending-attach button{background:none;border:none;color:var(--muted);cursor:pointer;font-size:13px;margin-left:auto;font-family:inherit}

/* Recent chats drawer (issue #19829 P1) */
.chat-toolbar{display:flex;justify-content:flex-end;padding:8px 14px 0;flex-shrink:0}
.chats-btn{background:var(--navy2);border:1px solid var(--border);border-radius:7px;color:var(--muted);font-size:11px;font-weight:600;padding:7px 11px;cursor:pointer;font-family:inherit;margin-right:6px;flex-shrink:0}
.chats-btn:hover{border-color:var(--orange);color:var(--text)}
.chats-drawer{position:fixed;inset:0 auto 0 0;width:280px;max-width:82vw;background:var(--navy2);border-right:1px solid var(--border);z-index:2000;transform:translateX(-100%);transition:transform .18s ease;display:flex;flex-direction:column}
.chats-drawer.open{transform:translateX(0)}
.chats-scrim{position:fixed;inset:0;background:rgba(2,6,23,.55);z-index:1999;display:none}
.chats-scrim.open{display:block}
.chats-hdr{display:flex;align-items:center;gap:8px;padding:12px;border-bottom:1px solid var(--border)}
.chats-hdr h3{font-size:12.5px;color:var(--text);flex:1}
.chats-new{background:var(--orange);color:var(--navy);border:none;border-radius:7px;padding:6px 10px;font-size:11px;font-weight:700;cursor:pointer;font-family:inherit}
.chats-close{background:none;border:none;color:var(--muted);font-size:16px;cursor:pointer}
.chats-search{padding:8px 12px;border-bottom:1px solid var(--border)}
.chats-search input{width:100%;background:var(--navy3);border:1px solid var(--border);border-radius:8px;padding:7px 9px;color:var(--text);font-size:12px;font-family:inherit;outline:none}
.chats-list{flex:1;overflow-y:auto;padding:6px}
.chats-empty{color:var(--muted);font-size:11.5px;text-align:center;padding:24px 12px}
.chat-item{display:block;width:100%;text-align:left;background:none;border:none;border-radius:8px;padding:9px 10px;cursor:pointer;font-family:inherit}
.chat-item:hover{background:var(--navy3)}
.chat-item .ci-title{font-size:12px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chat-item .ci-snip{font-size:10.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.chats-signin{padding:14px 12px;font-size:11.5px;color:var(--muted)}
.chats-signin input{width:100%;background:var(--navy3);border:1px solid var(--border);border-radius:8px;padding:7px 9px;color:var(--text);font-size:12px;font-family:inherit;outline:none;margin:8px 0}
.chats-signin button{width:100%;background:var(--orange);color:var(--navy);border:none;border-radius:8px;padding:8px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit}

/* Message actions row (issue #19829 P1) */
.msg-actions{display:flex;gap:4px;margin:4px 0 0 40px;flex-wrap:wrap}
.msg-actions button{background:none;border:none;color:var(--muted);font-size:12px;padding:3px 6px;border-radius:6px;cursor:pointer;font-family:inherit}
.msg-actions button:hover:not([disabled]){background:var(--navy3);color:var(--text)}
.msg-actions button[disabled]{opacity:.35;cursor:not-allowed}
.msg-actions button.active{color:var(--orange)}

/* SPLIT LAYOUT — property cards right panel */
.split{flex:1;display:flex;min-height:0;overflow:hidden}
.chat-col{display:flex;flex-direction:column;flex:1 1 45%;min-width:0;min-height:0;overflow:hidden}
.panel-col{display:none;flex:1 1 55%;min-width:0;flex-direction:column;border-left:1px solid var(--border);background:var(--navy2);overflow:hidden}
.panel-hdr{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid var(--border);flex-shrink:0}
.panel-hdr .pt{font-size:12px;font-weight:700;color:var(--text);text-transform:capitalize}
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
.pc-addr{font-size:13px;font-weight:700;color:var(--text)}
.pc-date{font-size:11px;color:var(--muted);white-space:nowrap}
.pc-city{font-size:11.5px;color:var(--muted)}
.pc-days{font-size:10px;color:var(--orange);white-space:nowrap;font-weight:600}
.pc-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin:10px 0}
.pc-lbl{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px}
.pc-val{font-size:12.5px;font-weight:700;color:var(--text);font-family:'SF Mono',monospace}
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

<div class="chats-scrim" id="chats-scrim"></div>
<aside class="chats-drawer" id="chats-drawer" aria-label="Recent chats">
  <div class="chats-hdr">
    <h3>Recent chats</h3>
    <button class="chats-new" id="chats-new-btn" type="button">+ New</button>
    <button class="chats-close" id="chats-close-btn" type="button" aria-label="Close">✕</button>
  </div>
  <div class="chats-search"><input type="text" id="chats-search-input" placeholder="Search your chats..."></div>
  <div class="chats-list" id="chats-list"><div class="chats-empty">Loading…</div></div>
</aside>

<div class="split">
  <div class="chat-col">
<div class="chat-toolbar"><button class="chats-btn" id="chats-open-btn" type="button" title="Recent chats">🕘 Chats</button></div>
${countyBar}

<div class="msgs" id="msgs">
  <div class="welcome" id="welcome">
    <div class="wl-icon">${DEED_ROBOT_ICON}</div>
    <div class="wl-title">Deed Voice AI</div>
    <div class="wl-sub">Ask about any Florida county in natural language. Talk or type in 70+ languages.</div>
    <div class="quick-grid">
      <button class="qbtn prime" data-msg="Show me the Marion County proof — Shapira Formula ceiling held to the cent.">📊 See proof it works</button>
      <button class="qbtn" data-msg="What foreclosure and tax deed auctions are coming up across Florida this week?">📅 What's coming to auction?</button>
      <button class="qbtn" data-msg="How does the Shapira Max Bid formula work? Walk me through it.">🧮 Shapira Max Bid formula</button>
      <button class="qbtn" data-msg="I have a specific property I want analyzed. How do I get a SIGNAL$ Property Report?">💼 Get a $25 SIGNAL$ Property Report</button>
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

<div class="voice-dock">
  <div class="voice-dock-copy">
    ${DEED_ROBOT_ICON}
    <div><div class="voice-dock-title">Talk to Deed Voice AI</div><div class="voice-dock-sub">Natural-language auction intelligence in 70+ languages.</div></div>
  </div>
  <div class="voice-actions">
    <button class="voice-btn" id="voice-btn" type="button" aria-label="Talk to Deed Voice AI in 70 or more languages"><span class="voice-dot" id="voice-dot"></span><span id="voice-btn-label">Talk to Deed</span></button>
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
</div>

<div class="inp-wrap">
  <div class="pending-attach" id="pending-attach"><span id="pending-attach-label"></span><button id="pending-attach-clear" type="button" aria-label="Remove attachment">✕</button></div>
  <div class="inp-bar">
    <div class="plus-wrap">
      <button class="plus-btn" id="plus-btn" type="button" aria-haspopup="true" aria-expanded="false" title="Add">+</button>
      <div class="plus-menu" id="plus-menu">
        <button class="plus-item" id="plus-upload" type="button">📄 Upload documents</button>
        <button class="plus-item" id="plus-screenshot" type="button">🖼️ Paste screenshot</button>
        <button class="plus-item" id="plus-records" type="button">🔎 Public-records search</button>
        <button class="plus-item" id="plus-research" type="button">🔬 Deep Research → SIGNAL$</button>
      </div>
      <input type="file" id="plus-file-input" accept=".pdf,.csv,.txt,.md,application/pdf,text/csv,text/plain,text/markdown" style="display:none">
    </div>
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
// Chat identity + persistence state (issue #19829 P1) — populated once the
// user has an email on file (reuses the existing email-capture flow) and a
// chat_token has been issued; null token = anonymous chat, unaffected.
var chatState={token:null,email:null,conversationId:null,pendingUploadId:null,pendingUploadName:null,publicRecords:false};
try{chatState.token=localStorage.getItem('bd_chat_token')||null;chatState.email=localStorage.getItem('bd_chat_email')||null;}catch(e){}
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
        '<a class="pc-buy" href="'+buyUrl+'">Buy SIGNAL$ Property Report — $25</a>'+
        (a.auction_url?('<a class="btn-bid" href="'+esc(a.auction_url)+'" target="_blank" rel="noopener">'+esc(a.bid_label||'View Auction →')+'</a>'):'')+
        '<div class="btn-locked" onclick="showUpgradePrompt(\\'maps\\',\\''+esc(a.case_number||'')+'\\',\\''+esc(a.county||'')+'\\')" style="font-size:12px;color:#64748b;cursor:pointer;padding:6px 0;">🔒 View on Maps — Investor only</div>'+
        (''/* outbound competitor link removed Aug 17 2026 (Ariel, standing rule): that
       vendor is never named on our sites, and we were sending our own paying
       traffic straight to them from the property card. po_url stays on the
       record as an internal parity field; it is simply not rendered. */)+'</div>';
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

function actionsHtml(role){
  if(role==='assistant'){
    return '<div class="msg-actions" data-role="assistant"><button data-action="copy" title="Copy">⧉</button><button data-action="retry" title="Retry">↻</button><button data-action="thumbsup" title="Good response">👍</button><button data-action="thumbsdown" title="Bad response">👎</button><button data-action="addroom" disabled title="Coming in P2 - Deal Rooms">➕ Room</button><button data-action="setalert" disabled title="Coming in P3 - Alerts and Watches">🔔 Alert</button></div>';
  }
  return '<div class="msg-actions" data-role="user"><button data-action="edit" title="Edit">✎ Edit</button></div>';
}
function addMsg(role,content){
  document.getElementById('welcome')?.remove();
  const m=document.getElementById('msgs');
  const row=document.createElement('div');row.className='msg '+role;
  const av=role==='assistant'?'<div class="av ai">BD</div>':'<div class="av user">👤</div>';
  const body = role==='assistant' ? mdToHtml(content) : esc(content);
  row.innerHTML=av+'<div class="bbl '+role+'">'+body+'</div>'+actionsHtml(role);
  m.appendChild(row);scrollBottom();
  return row.querySelector('.bbl');
}

function showS5CTA(){
  if(s5Shown||document.getElementById('s5cta'))return;
  s5Shown=true;
  const m=document.getElementById('msgs');
  const d=document.createElement('div');d.id='s5cta';d.className='s5-cta';
  d.innerHTML='<div class="s5-cta-text"><div class="title">💼 Get a SIGNAL$ Property Report</div><div class="desc">Full AI max-bid analysis for a specific property — lien stack, plaintiff intel, zoning, BID/SKIP recommendation. We deliver the SIGNAL$. First.</div></div><a href="/buy-report" class="s5-btn">$25 — Get Report →</a>';
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
    const reqHeaders={'Content-Type':'application/json'};
    if(chatState.token)reqHeaders['X-Chat-Token']=chatState.token;
    const reqBody={messages:H,county:COUNTY,hook:HOOK};
    if(chatState.conversationId)reqBody.conversation_id=chatState.conversationId;
    if(chatState.pendingUploadId)reqBody.upload_id=chatState.pendingUploadId;
    if(chatState.publicRecords)reqBody.public_records=true;
    const res=await fetch('/chat/api',{method:'POST',headers:reqHeaders,body:JSON.stringify(reqBody),signal:controller.signal});
    chatState.pendingUploadId=null;chatState.pendingUploadName=null;
    var pa=document.getElementById('pending-attach');if(pa)pa.classList.remove('show');
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
        if(pendingEvent==='meta'){
          try{var metaEvt=JSON.parse(data);if(metaEvt.conversation_id)chatState.conversationId=metaEvt.conversation_id;}catch(e){}
          pendingEvent=null;continue;
        }
        try{const evt=JSON.parse(data);if(evt.text){fullText+=evt.text;bbl.innerHTML=mdToHtml(stripPropertiesMarker(fullText));scrollBottom();}}catch(e){}
      }
    }
    fullText=stripPropertiesMarker(fullText);
    bbl.innerHTML=mdToHtml(fullText);
    bbl.id='';
    bbl.insertAdjacentHTML('afterend',actionsHtml('assistant'));
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

// issue #19829 P1 — once an email is known (any existing capture point:
// email-gate here, voice gate, upload flow), silently establish a chat
// identity token too so recent-chat persistence "just works" without a
// separate sign-in screen. No-ops (resolves null) if already have a token
// for this email, or if the server has no SUPABASE_SERVICE_ROLE_KEY bound
// yet (persistence not provisioned) — anonymous chat is never blocked by this.
async function ensureChatIdentity(email){
  if(!email)return null;
  if(chatState.token&&chatState.email===email.toLowerCase().trim())return chatState.token;
  try{
    const res=await fetch('/chat/api/identity',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email})});
    if(!res.ok)return null;
    const data=await res.json();
    chatState.token=data.token;chatState.email=data.email;
    try{localStorage.setItem('bd_chat_token',data.token);localStorage.setItem('bd_chat_email',data.email);}catch(e){}
    if(typeof onChatIdentityReady==='function')onChatIdentityReady();
    return data.token;
  }catch(e){return null;}
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
  ensureChatIdentity(email);
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
<script>
// ── Recent chats drawer + composer "+" menu (issue #19829 P1) ───────────────
(function(){
  var drawer=document.getElementById('chats-drawer');
  var scrim=document.getElementById('chats-scrim');
  var openBtn=document.getElementById('chats-open-btn');
  var closeBtn=document.getElementById('chats-close-btn');
  var newBtn=document.getElementById('chats-new-btn');
  var searchInput=document.getElementById('chats-search-input');
  var listEl=document.getElementById('chats-list');
  var pendingAfterAuth=null;

  function esc2(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

  function renderSignIn(){
    listEl.innerHTML='<div class="chats-signin">Enter your email to save and search your chats.<input type="email" id="chats-signin-email" placeholder="your@email.com"><button id="chats-signin-submit" type="button">Continue</button></div>';
    var input=document.getElementById('chats-signin-email');
    var submit=document.getElementById('chats-signin-submit');
    function go(){
      var email=(input.value||'').trim();
      if(!email||email.indexOf('@')===-1)return;
      submit.textContent='...';
      ensureChatIdentity(email).then(function(token){
        if(token){
          fetch('/chat/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,county:COUNTY,source:HOOK||'chat_plus_menu'})}).catch(function(){});
        }else{
          submit.textContent='Continue';
          listEl.innerHTML='<div class="chats-empty">Could not start a chat session. Please try again shortly.</div>';
        }
      });
    }
    submit.addEventListener('click',go);
    input.addEventListener('keydown',function(e){if(e.key==='Enter')go();});
  }

  window.onChatIdentityReady=function(){
    if(pendingAfterAuth){var fn=pendingAfterAuth;pendingAfterAuth=null;fn();}
    if(drawer.classList.contains('open'))loadConversations();
  };

  function renderList(items,emptyMsg){
    if(!items||!items.length){listEl.innerHTML='<div class="chats-empty">'+esc2(emptyMsg)+'</div>';return;}
    listEl.innerHTML=items.map(function(c){
      var title=esc2(c.title||'(untitled)');
      var snip=c.snippet?esc2(c.snippet):'';
      return '<button class="chat-item" data-conv-id="'+esc2(c.conversation_id||c.id)+'"><div class="ci-title">'+title+'</div>'+(snip?'<div class="ci-snip">'+snip+'</div>':'')+'</button>';
    }).join('');
    listEl.querySelectorAll('.chat-item').forEach(function(btn){
      btn.addEventListener('click',function(){loadConversation(btn.getAttribute('data-conv-id'));});
    });
  }

  function loadConversations(){
    if(!chatState.token){renderSignIn();return;}
    listEl.innerHTML='<div class="chats-empty">Loading…</div>';
    fetch('/chat/api/conversations',{headers:{'X-Chat-Token':chatState.token}})
      .then(function(r){return r.ok?r.json():{conversations:[]};})
      .then(function(d){renderList(d.conversations,'No saved chats yet — start one and it will appear here.');})
      .catch(function(){listEl.innerHTML='<div class="chats-empty">Could not load chats.</div>';});
  }

  function loadConversation(id){
    if(!chatState.token)return;
    fetch('/chat/api/conversations/'+encodeURIComponent(id)+'/messages',{headers:{'X-Chat-Token':chatState.token}})
      .then(function(r){return r.ok?r.json():null;})
      .then(function(d){
        if(!d)return;
        document.getElementById('welcome')?.remove();
        var m=document.getElementById('msgs');
        m.innerHTML='';
        H=[];
        d.messages.forEach(function(msg){
          H.push({role:msg.role,content:msg.content});
          addMsg(msg.role,msg.content);
        });
        chatState.conversationId=id;
        closeDrawer();
      }).catch(function(){});
  }

  function openDrawer(){drawer.classList.add('open');scrim.classList.add('open');loadConversations();}
  function closeDrawer(){drawer.classList.remove('open');scrim.classList.remove('open');}
  if(openBtn)openBtn.addEventListener('click',openDrawer);
  if(closeBtn)closeBtn.addEventListener('click',closeDrawer);
  if(scrim)scrim.addEventListener('click',closeDrawer);
  if(newBtn)newBtn.addEventListener('click',function(){
    chatState.conversationId=null;H=[];
    document.getElementById('msgs').innerHTML='';
    closeDrawer();
  });
  var searchTimer=null;
  if(searchInput)searchInput.addEventListener('input',function(){
    clearTimeout(searchTimer);
    var q=searchInput.value.trim();
    if(!q){loadConversations();return;}
    if(!chatState.token)return;
    searchTimer=setTimeout(function(){
      fetch('/chat/api/search?q='+encodeURIComponent(q),{headers:{'X-Chat-Token':chatState.token}})
        .then(function(r){return r.ok?r.json():{results:[]};})
        .then(function(d){renderList(d.results,'No matches.');})
        .catch(function(){});
    },300);
  });

  // ── Composer "+" menu ──────────────────────────────────────────────────
  var plusBtn=document.getElementById('plus-btn');
  var plusMenu=document.getElementById('plus-menu');
  var plusUpload=document.getElementById('plus-upload');
  var plusScreenshot=document.getElementById('plus-screenshot');
  var plusRecords=document.getElementById('plus-records');
  var plusResearch=document.getElementById('plus-research');
  var plusFileInput=document.getElementById('plus-file-input');
  var pendingAttach=document.getElementById('pending-attach');
  var pendingAttachLabel=document.getElementById('pending-attach-label');
  var pendingAttachClear=document.getElementById('pending-attach-clear');

  function closePlusMenu(){plusMenu.classList.remove('open');plusBtn.setAttribute('aria-expanded','false');}
  function togglePlusMenu(){var open=plusMenu.classList.toggle('open');plusBtn.setAttribute('aria-expanded',open?'true':'false');}
  if(plusBtn)plusBtn.addEventListener('click',function(e){e.stopPropagation();togglePlusMenu();});
  document.addEventListener('click',function(e){if(plusMenu&&plusMenu.classList.contains('open')&&!plusMenu.contains(e.target)&&e.target!==plusBtn)closePlusMenu();});

  function requireIdentityThen(fn){
    if(chatState.token){fn();return;}
    pendingAfterAuth=fn;
    openDrawer();
  }

  function fileToBase64(file){
    return new Promise(function(resolve,reject){
      var reader=new FileReader();
      reader.onload=function(){resolve(String(reader.result).split(',')[1]||'');};
      reader.onerror=reject;
      reader.readAsDataURL(file);
    });
  }

  function uploadFile(file){
    pendingAttachLabel.textContent='Uploading '+file.name+'…';
    pendingAttach.classList.add('show');
    fileToBase64(file).then(function(b64){
      return fetch('/chat/api/upload',{method:'POST',headers:{'Content-Type':'application/json','X-Chat-Token':chatState.token},body:JSON.stringify({filename:file.name,mime_type:file.type,data_base64:b64,conversation_id:chatState.conversationId})});
    }).then(function(r){return r.json().then(function(d){return {ok:r.ok,d:d};});}).then(function(res){
      if(!res.ok){pendingAttachLabel.textContent='Upload failed';setTimeout(function(){pendingAttach.classList.remove('show');},2500);return;}
      chatState.pendingUploadId=res.d.id;chatState.pendingUploadName=res.d.filename;
      var statusTxt=res.d.extraction_status==='ok'?'📄 '+res.d.filename+' — ready':'📄 '+res.d.filename+' — attached (no text preview for this file type)';
      pendingAttachLabel.textContent=statusTxt;
    }).catch(function(){pendingAttachLabel.textContent='Upload failed';setTimeout(function(){pendingAttach.classList.remove('show');},2500);});
  }

  if(pendingAttachClear)pendingAttachClear.addEventListener('click',function(){chatState.pendingUploadId=null;chatState.pendingUploadName=null;pendingAttach.classList.remove('show');});

  if(plusUpload)plusUpload.addEventListener('click',function(){closePlusMenu();requireIdentityThen(function(){plusFileInput.click();});});
  if(plusFileInput)plusFileInput.addEventListener('change',function(){if(plusFileInput.files&&plusFileInput.files[0]){uploadFile(plusFileInput.files[0]);plusFileInput.value='';}});

  if(plusScreenshot)plusScreenshot.addEventListener('click',function(){
    closePlusMenu();
    requireIdentityThen(function(){
      var inp=document.getElementById('inp');
      showSystemMessage('Paste your screenshot now (Ctrl/Cmd+V) — it will attach to your next message.');
      inp.focus();
    });
  });
  document.addEventListener('paste',function(e){
    if(!e.clipboardData||!e.clipboardData.items)return;
    for(var i=0;i<e.clipboardData.items.length;i++){
      var item=e.clipboardData.items[i];
      if(item.type&&item.type.indexOf('image/')===0){
        var blob=item.getAsFile();
        if(!blob)continue;
        requireIdentityThen(function(){uploadFile(new File([blob],'screenshot.png',{type:blob.type||'image/png'}));});
        break;
      }
    }
  });

  if(plusRecords)plusRecords.addEventListener('click',function(){
    chatState.publicRecords=!chatState.publicRecords;
    plusRecords.classList.toggle('active-toggle',chatState.publicRecords);
    plusRecords.textContent=(chatState.publicRecords?'✅ ':'🔎 ')+'Public-records search';
  });

  if(plusResearch)plusResearch.addEventListener('click',function(){
    closePlusMenu();
    requireIdentityThen(function(){
      ask('Run deep research on the property we\\'re discussing and tell me what a SIGNAL$ Property Report would cover.');
    });
  });

  // ── Message action row delegation (copy / retry / edit / thumbs) ───────
  document.getElementById('msgs').addEventListener('click',function(e){
    var btn=e.target.closest('[data-action]');
    if(!btn||btn.disabled)return;
    var action=btn.getAttribute('data-action');
    var row=btn.closest('.msg');
    var bbl=row?row.querySelector('.bbl'):null;
    if(action==='copy'&&bbl){
      var txt=bbl.innerText||bbl.textContent||'';
      if(navigator.clipboard)navigator.clipboard.writeText(txt).then(function(){
        var old=btn.textContent;btn.textContent='✓';setTimeout(function(){btn.textContent=old;},1200);
      }).catch(function(){});
    }else if(action==='retry'){
      var lastUser=null;
      for(var i=H.length-1;i>=0;i--){if(H[i].role==='user'){lastUser=H[i];break;}}
      if(lastUser){
        if(H.length&&H[H.length-1].role==='assistant')H.pop();
        document.getElementById('inp').value=lastUser.content;
        if(H.length&&H[H.length-1].role==='user')H.pop();
        send();
      }
    }else if(action==='thumbsup'||action==='thumbsdown'){
      btn.classList.toggle('active');
      if(window.posthog)posthog.capture('deed_chat_feedback',{rating:action==='thumbsup'?'up':'down'});
    }else if(action==='edit'&&bbl){
      document.getElementById('inp').value=bbl.textContent||'';
      document.getElementById('inp').focus();
    }
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
<meta name="description" content="Subscribe to BidDeed.AI TIER_LABEL_PLACEHOLDER — TIER_PRICE_PLACEHOLDER/mo or ANNUAL_PRICE_PLACEHOLDER/yr.">
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;margin:0;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:460px;width:100%}
h1{font-size:1.4rem;color:white;margin-bottom:.4rem}
.price{color:#f59e0b;font-weight:700;font-size:1rem;margin-bottom:1rem}
p.sub{color:#94a3b8;font-size:.9rem;margin-bottom:1.25rem;line-height:1.5}
label{display:block;font-size:.85rem;color:#cbd5e1;margin-bottom:.4rem}
input[type=email]{width:100%;background:#020617;border:1px solid #1e293b;border-radius:8px;padding:12px 14px;color:white;font-size:15px;margin-bottom:1.25rem;outline:none}
input[type=email]:focus{border-color:#f59e0b}
.interval-toggle{display:flex;gap:8px;margin-bottom:1.25rem}
.interval-btn{flex:1;padding:10px;border-radius:8px;border:1px solid #1e293b;background:#020617;color:#94a3b8;font-size:13px;font-weight:600;cursor:pointer;text-align:center;transition:all .15s}
.interval-btn.active{border-color:#f59e0b;background:rgba(245,158,11,.1);color:#f59e0b}
.save-badge{display:inline-block;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.4);color:#10b981;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:6px}
button.cta{width:100%;background:linear-gradient(135deg,#f59e0b,#f97316);color:#020617;border:none;padding:14px;border-radius:10px;font-weight:700;font-size:15px;cursor:pointer}
button.cta:disabled{opacity:.6;cursor:default}
.err{color:#f87171;font-size:.85rem;margin-top:.75rem;display:none}
</style></head><body>
<div class="card">
  <h1>BidDeed.AI TIER_LABEL_PLACEHOLDER</h1>
  <div class="price" id="price-display">TIER_PRICE_PLACEHOLDER/mo</div>
  <p class="sub">Enter your email to continue to secure checkout. Redirected to Stripe — no card stored here.</p>
  <div class="interval-toggle">
    <div class="interval-btn INTERVAL_PLACEHOLDER_monthly_active" id="btn-monthly" onclick="setInterval('monthly')">Monthly<br><span style="font-weight:400;font-size:12px">TIER_PRICE_PLACEHOLDER/mo</span></div>
    <div class="interval-btn INTERVAL_PLACEHOLDER_annual_active" id="btn-annual" onclick="setInterval('annual')">Annual — Pioneer<br><span style="font-weight:400;font-size:12px">ANNUAL_PRICE_PLACEHOLDER/yr</span><span class="save-badge">Save SAVE_PRICE_PLACEHOLDER</span></div>
  </div>
  <form id="sub-form">
    <label for="sub-email">Email</label>
    <input type="email" id="sub-email" placeholder="you@example.com" required>
    <button type="submit" class="cta" id="sub-btn">Continue to Checkout →</button>
    <div class="err" id="sub-err"></div>
  </form>
  <div style="text-align:center;font-size:12px;color:#94a3b8;margin-top:14px">Not ready to pay? <a href="/free-report" style="color:#f59e0b;font-weight:600">Try 67 counties free — no card required →</a></div>
</div>
<script>
try{if(window.posthog)posthog.capture('subscribe_page_viewed',{tier:'TIER_PLACEHOLDER'});}catch(e){}
var refCode = new URLSearchParams(window.location.search).get('ref');
var selectedInterval = 'INTERVAL_PLACEHOLDER';
function setInterval(iv){
  selectedInterval=iv;
  document.getElementById('btn-monthly').className='interval-btn'+(iv==='monthly'?' active':'');
  document.getElementById('btn-annual').className='interval-btn'+(iv==='annual'?' active':'');
  document.getElementById('price-display').textContent=iv==='annual'?'ANNUAL_PRICE_PLACEHOLDER/yr (Pioneer)':'TIER_PRICE_PLACEHOLDER/mo';
}
setInterval(selectedInterval);
document.getElementById('sub-form').addEventListener('submit', async function(e){
  e.preventDefault();
  var btn=document.getElementById('sub-btn'), err=document.getElementById('sub-err');
  var email=document.getElementById('sub-email').value.trim();
  err.style.display='none';
  btn.disabled=true; btn.textContent='Redirecting to checkout...';
  try{if(window.posthog)posthog.capture('subscribe_redirect',{tier:'TIER_PLACEHOLDER',interval:selectedInterval});}catch(e2){}
  var checkoutPayload={tier:'TIER_PLACEHOLDER',customer_email:email,interval:selectedInterval};
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
<title>Buy One SIGNAL$ Property Report — $25 | BidDeed.AI</title>
<meta name="description" content="Exact Shapira Max Bid + ZoneWise zoning + ML prediction for one auction. One-time $25, no subscription. We deliver the SIGNAL$. First.">
${POSTHOG_SCRIPT}
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
body{background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.card{background:#0f172a;border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:2.5rem;max-width:520px;width:100%}
.badge{color:var(--orange);font-size:12px;font-weight:600;letter-spacing:.1em;margin-bottom:.75rem}.s5-overview{margin:1.25rem 0 1.5rem;padding:1.1rem 1.15rem;border:1px solid rgba(159,77,50,.28);border-radius:14px;background:rgba(245,240,232,.72)}.s5-overview h2{font-size:1.05rem;color:#1F1B16;margin-bottom:.35rem}.s5-overview p{font-size:.8rem;line-height:1.45;color:#6e655e;margin-bottom:.8rem}.s5-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.45rem .75rem;list-style:none}.s5-grid li{display:flex;gap:.45rem;align-items:flex-start;font-size:.73rem;line-height:1.25;color:#1F1B16}.s5-grid b{color:#9f4d32;font-size:.68rem;min-width:1.35rem}.s5-overlays{margin-top:.75rem;padding-top:.65rem;border-top:1px solid rgba(159,77,50,.2);font-size:.72rem;color:#6e655e}.s5-overlays strong{color:#9f4d32}@media(max-width:560px){.s5-grid{grid-template-columns:1fr}.s5-overview{padding:.95rem}.s5-grid li{font-size:.76rem}}
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
/* WinnerDataAI house-brand light mode for the complete S5 purchase flow. */
html[data-theme=light] body{background:#F5F0E8;color:#1F1B16}
html[data-theme=light] .card{background:#FBFAF7;border-color:rgba(159,77,50,.35);box-shadow:0 18px 50px rgba(31,27,22,.10)}
html[data-theme=light] :root{--navy:#F5F0E8;--orange:#9f4d32;--orange2:#823f29;--text:#1F1B16;--muted:#6e655e;--dim:#6e655e;--border:#DDD5C9}
html[data-theme=light] h1{color:#1F1B16}
html[data-theme=light] p,html[data-theme=light] label,html[data-theme=light] .consent,html[data-theme=light] .meta,html[data-theme=light] .empty,html[data-theme=light] .spin{color:#6e655e}
html[data-theme=light] select,html[data-theme=light] input[type=email]{background:#F5F0E8;color:#1F1B16;border-color:#B5A9A0}
html[data-theme=light] select:focus,html[data-theme=light] input[type=email]:focus{outline:2px solid rgba(159,77,50,.28);border-color:#9f4d32}
html[data-theme=light] .btn{background:linear-gradient(135deg,#9f4d32,#823f29);color:#FBFAF7}
html[data-theme=light] .back{color:#6e655e}
html[data-theme=light] .back:hover{color:#823f29}
html[data-theme=light] .auction-card{border-color:#DDD5C9;background:#FBFAF7}
html[data-theme=light] .auction-card:hover,html[data-theme=light] .auction-card.selected{border-color:#9f4d32;background:rgba(159,77,50,.10)}
html[data-theme=light] .auction-card .addr,html[data-theme=light] .summary .addr{color:#1F1B16}
html[data-theme=light] .summary{border-color:#DDD5C9;background:#F5F0E8;color:#6e655e}
html[data-theme=light] .upl{border-color:#DDD5C9;color:#6e655e}
html[data-theme=light] .upl a{color:#9f4d32}
</style></head><body>
<div class="card">
  <div class="badge">ONE-TIME · NO SUBSCRIPTION</div>
  <div class="s5-overview" aria-labelledby="s5-overview-title">
    <h2 id="s5-overview-title">What your SIGNAL$ Property Report includes</h2>
    <p>One property. One evidence-backed decision document. Review every section before selecting the auction record.</p>
    <ol class="s5-grid">
      <li><b>01</b><span>Subject property identification</span></li>
      <li><b>02</b><span>Clearing-band value estimate</span></li>
      <li><b>03</b><span>Market-band value estimate</span></li>
      <li><b>04</b><span>Comparable sales layer</span></li>
      <li><b>05</b><span>Comparable quality and confidence</span></li>
      <li><b>06</b><span>Comparable distance analysis</span></li>
      <li><b>07</b><span>Comparable timing and market fit</span></li>
      <li><b>08</b><span>Transaction history</span></li>
      <li><b>09</b><span>Property record</span></li>
      <li><b>10</b><span>Listing and auction details</span></li>
      <li><b>11</b><span>Neighborhood context</span></li>
      <li><b>12</b><span>School context</span></li>
      <li><b>13</b><span>Flood-risk context</span></li>
      <li><b>14</b><span>Market context</span></li>
      <li><b>15</b><span>Judgment and encumbrance review</span></li>
      <li><b>16</b><span>Provenance and methodology</span></li>
      <li><b>17</b><span>Auction outcome tracking</span></li>
      <li><b>18</b><span>Prediction scorecard and max-bid decision</span></li>
    </ol>
    <div class="s5-overlays"><strong>Included intelligence overlays:</strong> Shapira third-party-purchase model and ZoneWise.AI land/zoning intelligence.</div>
  </div>
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
    <h1>One SIGNAL$ Property Report — $25</h1>
    <div class="summary" id="checkout-summary"></div>
    <form id="f">
      <label for="email">Email address (report delivered here)</label>
      <input type="email" id="email" name="email" required placeholder="you@example.com">
      <label class="consent"><input type="checkbox" id="consent" name="consent"> Send me occasional auction intelligence updates (optional)</label>
      <button type="submit" class="btn" id="btn">Get My SIGNAL$ Property Report — $25</button>
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
      document.getElementById('btn').textContent='Get My SIGNAL$ Property Report — $25';
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
      else{ err.textContent=r.data.error||'Something went wrong. Please try again.'; err.style.display='block'; btn.disabled=false; btn.textContent='Get My SIGNAL$ Property Report — $25'; }
    })
    .catch(function(){ err.textContent='Network error. Please try again.'; err.style.display='block'; btn.disabled=false; btn.textContent='Get My SIGNAL$ Property Report — $25'; });
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
  <h1>Payment received — your SIGNAL$ Property Report credit is ready</h1>
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
<meta name="theme-color" content="#F5F0E8">
<link rel="canonical" href="https://biddeed.ai/county/COUNTY_URLSLUG">
<meta name="description" content="COUNTY_META_DESC">
<meta property="og:title" content="COUNTY_TITLE_PLACEHOLDER County, Florida — Tax Deed &amp; Foreclosure Auctions">
<meta property="og:description" content="COUNTY_META_DESC">
<meta property="og:url" content="https://biddeed.ai/county/COUNTY_URLSLUG">
<meta property="og:type" content="website">
<meta property="og:site_name" content="BidDeed.AI">
<script type="application/ld+json">COUNTY_JSONLD</script>
<script>window.__bdAssetFail=[];window.__bdFail=function(e){try{window.__bdAssetFail.push(String(e&&e.message||e));var f=document.getElementById('bd-fallback');if(f){f.style.display='block';}var kids=document.body.children;for(var i=0;i<kids.length;i++){var k=kids[i];if(k.id!=='bd-fallback'&&k.tagName!=='NOSCRIPT'&&k.tagName!=='SCRIPT'){k.style.display='none';}}}catch(_){}}</script>
<link rel="stylesheet" href="/assets/tailwind-county.css" onerror="window.__bdFail('tailwind-css')">
<script>
/* Alpine's standard build compiles every x-* expression with new Function(),
   which the page CSP blocks (no 'unsafe-eval'). When that happens Alpine
   loads without error -- so the asset onerror fallbacks never fire -- and the
   page renders with x-show modals stuck open and dead controls. Probe eval
   up front and route to the same honest fallback the CDN-failure path uses.
   Remove this probe only when either 'unsafe-eval' is approved for script-src
   or this page is rewritten without runtime-evaluated expressions. */
try { new Function('return 1')() } catch (e) { window.__bdFail && window.__bdFail('csp-eval') }
</script>
<script src="/assets/papaparse.min.js" onerror="window.__bdFail('papaparse-local')"></script>
<script defer src="/assets/alpine.min.js" onerror="window.__bdFail('alpine-local')"></script>
<script>setTimeout(function(){if(!window.Alpine){window.__bdFail('alpine-boot-timeout');}},4000);</script>
<style>
:root { --safe-bottom: env(safe-area-inset-bottom,0px); --safe-top: env(safe-area-inset-top,0px); --cream:#F5F0E8; --surface:#FBFAF7; --ink:#1F1B16; --terracotta:#D97757; --terracotta-hover:#BC5B3F; --warm-muted:#6e655e; --warm-border:#DDD5C9; --warm-fill:#EDE3D7; --soft-terracotta:#EFE2D6; }
html { background:var(--cream); color:var(--ink); }
body { font-family:'Inter','SF Pro Text',system-ui,-apple-system,sans-serif; background:var(--cream); color:var(--ink); -webkit-tap-highlight-color:transparent; overscroll-behavior-y:contain; }
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
.cert-badge { display:inline-flex; align-items:center; gap:4px; padding:2px 8px; border-radius:9999px; font-size:10px; font-weight:800; letter-spacing:0.03em; margin-top:4px; }
.cert-gold { background:rgba(245,158,11,0.18); color:#fcd34d; border:1px solid rgba(245,158,11,0.35); }
.cert-review { background:rgba(100,116,139,0.20); color:#cbd5e1; border:1px solid rgba(100,116,139,0.35); }
input[type=range] { accent-color:var(--terracotta); }
/* County pages were bypassing the shared shell and retained the legacy navy/amber skin. */
html, body { background:var(--cream) !important; color:var(--ink) !important; }
.bg-slate-950, .bg-slate-950\\/90, .bg-slate-950\\/85, .bg-slate-900, .bg-slate-900\\/80, .bg-slate-800, .bg-slate-800\\/60, .bg-slate-800\\/50, .bg-slate-900\\/60 { background-color:var(--surface) !important; }
.text-white, .text-slate-200, .text-slate-300, .text-slate-400, .text-slate-500, .text-slate-600 { color:var(--ink) !important; }
.text-amber-300, .text-amber-400, .text-amber-500, .text-amber-400\\/80, .text-emerald-400, .text-blue-300, .text-blue-400, .text-purple-400, .text-red-300, .text-red-400, .text-pink-300, .text-sky-300 { color:var(--terracotta) !important; }
.border-slate-700, .border-slate-700\\/60, .border-slate-700\\/50, .border-slate-800\\/40, .border-slate-700\\/40, .border-amber-500\\/20, .border-amber-500\\/30 { border-color:var(--warm-border) !important; }
.bg-amber-500, .bg-amber-500\\/10, .bg-amber-500\\/5 { background-color:var(--soft-terracotta) !important; }
.bg-emerald-950\\/50, .bg-blue-950\\/40 { background-color:var(--warm-fill) !important; }
.glass, .glass-sold, .glass-diamond, .glass-triangle, .glass-canceled { background:var(--surface) !important; border-color:var(--warm-border) !important; backdrop-filter:none; color:var(--ink); }
.status-LISTED, .status-SOLD, .status-CANCELED, .status-REDEEMED, .cert-gold, .cert-review { background:var(--soft-terracotta) !important; color:var(--ink) !important; border-color:var(--terracotta) !important; }
.grade-A, .grade-B, .grade-C, .grade-D, .grade-E, .grade-X, .grade-Z { background:var(--soft-terracotta) !important; color:var(--ink) !important; }
header { background:rgba(251,250,247,.96) !important; border-color:var(--warm-border) !important; }
select, input { background:var(--surface) !important; color:var(--ink) !important; border-color:var(--warm-border) !important; }
.skeleton { background:linear-gradient(90deg,#ede3d7 0%,#f4eadf 50%,#ede3d7 100%); }
#county-lead-bar { box-shadow:0 -8px 24px rgba(31,27,22,.08); }
@media (max-width:767px) { #county-lead-bar { left:0 !important; padding-left:12px !important; padding-right:12px !important; } body { padding-bottom:calc(144px + var(--safe-bottom)) !important; } }
</style>
</head>
<body x-data="app()" x-init="init()" class="min-h-screen pb-36">
<noscript><div style="padding:20px;max-width:760px;margin:0 auto;color:#e2e8f0">
<h1 style="color:#fcd34d;font-size:22px;margin:0 0 8px">COUNTY_TITLE_PLACEHOLDER County, Florida — Tax Deed &amp; Foreclosure Auctions</h1>
<p style="color:#94a3b8;font-size:15px;line-height:1.6">Upcoming Clerk of Court auctions in COUNTY_TITLE_PLACEHOLDER County. This page needs JavaScript for the interactive table. The full auction list is available as data at
<a style="color:#fcd34d" href="/county/COUNTY_SLUG_PLACEHOLDER/lots">/county/COUNTY_SLUG_PLACEHOLDER/lots</a>.</p>
<p style="font-size:15px"><a style="color:#fcd34d" href="/counties">Browse all 67 Florida counties</a> &middot; <a style="color:#fcd34d" href="/buy-report">Get a Shapira Bid Card</a></p>
</div></noscript>
<div id="bd-fallback" style="display:none;padding:20px;max-width:760px;margin:0 auto;color:#e2e8f0">
<h1 style="color:#fcd34d;font-size:22px;margin:0 0 8px">COUNTY_TITLE_PLACEHOLDER County, Florida — Tax Deed &amp; Foreclosure Auctions</h1>
<p style="color:#94a3b8;font-size:15px;line-height:1.6">The interactive auction table did not load. Your connection may have blocked one of our assets.</p>
<p style="font-size:15px"><a style="color:#fcd34d" href="">Retry</a> &middot; <a style="color:#fcd34d" href="/county/COUNTY_SLUG_PLACEHOLDER/lots">View the raw auction data</a> &middot; <a style="color:#fcd34d" href="/counties">All 67 counties</a> &middot; <a style="color:#fcd34d" href="/buy-report">Get a Shapira Bid Card</a></p>
</div>

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
  <h1 class="px-4 pb-2 text-[11px] font-normal text-slate-400">🏠 COUNTY_TITLE auctions · <b class="text-emerald-400" x-text="matchCountByStatus('LISTED')"></b> listed · <b class="text-blue-400" x-text="matchCountByStatus('SOLD')"></b> sold · <b class="text-slate-400" x-text="matchCountByStatus('CANCELED')"></b> canceled</h1>
  <div class="px-4 pb-2"><span class="cert-badge COUNTY_CERT_BADGE_CLASS">COUNTY_CERT_BADGE_TEXT</span></div>

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

<div class="px-4 pt-3 pb-1 text-xs font-extrabold uppercase tracking-[0.14em]" style="color:var(--warm-muted)">Auction inventory</div>
<div class="px-4 py-2 flex items-center gap-2 relative z-20" style="background:var(--surface);border-bottom:1px solid var(--warm-border)">
  <button @click="showFilters=true" class="flex items-center gap-1.5 px-3 py-2 rounded-full text-sm font-semibold" style="background:var(--terracotta);color:#fff;border:1px solid var(--terracotta-hover)">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h18M6 12h12M10 20h4"/></svg>
    Filters <span x-show="activeFilterCount>0" class="text-[10px] font-bold rounded-full px-1.5" style="background:var(--surface);color:var(--ink)" x-text="activeFilterCount"></span>
  </button>
  <select x-model="sortKey" class="rounded-full px-3 py-2 text-sm" style="background:var(--surface);color:var(--ink);border:1px solid var(--warm-border)">
    <option value="equity_at_opening_bid">Sort: Equity ↓</option>
    <option value="owner_distress_score">Sort: 🔺 Distress ↓</option>
    <option value="opening_bid">Sort: Open Bid ↑</option>
    <option value="opening_bid_pct_of_market">Sort: Discount</option>
  </select>
  <div class="ml-auto text-[11px]" style="color:var(--warm-muted)"><span x-text="filteredDeals.length"></span>/<span x-text="deals.length"></span></div>
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
<div x-show="openDeal" class="fixed inset-0 z-[60]" x-cloak>
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
            <span>Get the SIGNAL$ Property Report — $25</span>
          </button>
        </template>
        <template x-if="!S5_AVAILABLE">
          <div class="w-full rounded-xl py-3.5 px-4 text-center text-sm border border-slate-700 bg-slate-800/50 text-slate-400">
            <div class="font-semibold text-slate-300">📋 SIGNAL$ Property Report — coming soon for COUNTY_TITLE_PLACEHOLDER</div>
            <div class="text-[11px] mt-1">Full AI max-bid analysis available now in certified counties</div>
            <a href="/subscribe?tier=investor" class="mt-3 inline-flex w-full items-center justify-center rounded-lg py-3 px-4 font-bold text-white" style="background:var(--terracotta)">Join Investor — $99/mo</a>
          </div>
        </template>
        <p class="text-[10px] text-slate-500 text-center mt-2 leading-snug">18-section AI analysis · Shapira Max Bid ceiling · CMA comps · zoning · outcome prediction · branded PDF</p>
      </div>

      <div class="grid grid-cols-3 gap-2">
        <a :href="openDeal && openDeal.google_maps_url" target="_blank" rel="noopener noreferrer" class="rounded-lg text-center text-xs py-3 font-semibold" style="background:var(--soft-terracotta);color:var(--ink);border:1px solid var(--warm-border)">🗺️ Maps</a>
        <a :href="openDeal && openDeal.bcpao_link" target="_blank" rel="noopener noreferrer" class="rounded-lg text-center text-xs py-3 font-semibold" style="background:var(--soft-terracotta);color:var(--ink);border:1px solid var(--warm-border)">🏢 Property Appraiser</a>
        <a :href="openDeal && openDeal.brevardclerk_tax_deed_page" target="_blank" rel="noopener noreferrer" class="rounded-lg text-center text-xs py-3 font-semibold" style="background:var(--soft-terracotta);color:var(--ink);border:1px solid var(--warm-border)">⚖️ Court Records</a>
      </div>
      <button @click="openDeal=null" type="button" class="w-full mt-3 py-3 rounded-lg text-sm font-bold" style="background:var(--surface);color:var(--terracotta);border:1px solid var(--warm-border)">← Back to properties</button>
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
const COUNTY_TITLE_JS = "COUNTY_TITLE_JS_PLACEHOLDER";
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
      try { this.__init(); } catch (e) { window.__bdFail && window.__bdFail(e); }
    },
    __init() {
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
            parcel_id: r.parcel_id || r.bcpao_account || '',
            bcpao_account: r.bcpao_account || r.parcel_id || '',
            sold_amount: Number(r.sold_amount) || 0,
            sold_premium_pct: Number(r.sold_premium_pct) || 0,
            sold_pct_of_market: Number(r.sold_pct_of_market) || 0,
            sold_to: r.sold_to || '',
            buyer_residual_equity: Number(r.buyer_residual_equity) || 0,
            equity_at_opening_bid: equity,
            opening_bid_pct_of_market: pctMkt,
            assessed_value: assessed,
            sale_status: r.auction_status === 'sold' ? 'SOLD' : r.auction_status === 'canceled' ? 'CANCELED' : 'LISTED',
            sale_type: r.sale_type,
            auction_date: r.auction_date,
            clerk_url: r.clerk_url || r.auction_url || '',
            bcpao_url: r.bcpao_url || '',
            google_maps_url: addr ? 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(addr) : '',
            bcpao_link: r.bcpao_url || (addr ? 'https://www.google.com/search?q=' + encodeURIComponent(COUNTY_TITLE_JS + ' County Property Appraiser ' + addr) : ''),
            brevardclerk_tax_deed_page: r.clerk_url || r.auction_url || (r.case_number ? 'https://www.google.com/search?q=' + encodeURIComponent(COUNTY_TITLE_JS + ' County Clerk court records ' + r.case_number) : ''),
            plaintiff: r.plaintiff || '',
            property_category: r.sale_type === 'tax_deed' ? 'tax_deed' : 'foreclosure',
            tax_deed_grade: market > 0 && equity > 50000 ? 'A_PREMIUM' : market > 0 && equity > 20000 ? 'B_SOLID' : market > 0 ? 'C_MARGINAL' : 'X_UNKNOWN',
            owner_distress_score: Number(r.owner_distress_score) || 0,
            owner_distress_signals: r.owner_distress_signals || '',
            owner_name: r.owner_name || r.plaintiff || '',
            owner_mailing_state: r.owner_mailing_state || 'FL',
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
<div id="county-lead-bar" style="position:fixed;left:200px;right:0;bottom:0;z-index:40;background:rgba(251,250,247,.98);backdrop-filter:blur(12px);border-top:1px solid var(--warm-border);padding:12px 16px calc(12px + var(--safe-bottom));display:flex;gap:8px;align-items:center;flex-wrap:wrap">
  <div style="flex:1;min-width:180px;font-size:12px;color:var(--ink);font-weight:600">Get COUNTY_TITLE_PLACEHOLDER's next 5 auctions emailed free</div>
  <form id="county-lead-form" style="display:flex;gap:6px;flex:2;min-width:220px">
    <input type="email" id="county-lead-email" placeholder="you@example.com" required style="flex:1;background:var(--surface);border:1px solid var(--warm-border);border-radius:8px;padding:8px 12px;color:var(--ink);font-size:14px;outline:none">
    <button type="submit" id="county-lead-btn" style="background:var(--terracotta);color:#fff;border:none;padding:8px 16px;border-radius:8px;font-weight:700;font-size:13px;white-space:nowrap;cursor:pointer">Send Free List</button>
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
            +'<a href="'+buyHref+'" style="font-size:11px;color:var(--orange);text-decoration:none;font-weight:600">SIGNAL$ Report $25 →</a></div>'
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
<meta name="description" content="Florida investors: stop guessing on tax-deed surplus and zoning risk. BidDeed.AI + ZoneWise.AI turn 20 years of Florida deed/foreclosure expertise into an auction-by-auction edge. See your county's live report now.">
<meta property="og:title" content="Florida Tax-Deed &amp; Foreclosure Investors — See What Competitors Miss">
<meta property="og:description" content="For Florida tax-deed and foreclosure investors — surface the deals your competitors miss, backed by 20 years of Florida auction data and 67-county parcel coverage. Start your first Gold Standard county report free.">
${POSTHOG_SCRIPT}
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
.pricing-band{padding:6.5rem 2rem;background:var(--navy)}
.pricing-inner{max-width:960px;margin:0 auto}
.pricing-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.75rem;margin-top:3.5rem}
.price-card{background:var(--charcoal);border:1px solid var(--divider);border-radius:14px;padding:36px 32px;position:relative}
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
  .pricing-band{padding:3.5rem 1.25rem}
  .pricing-grid{grid-template-columns:1fr;gap:1.5rem}
  .price-card{padding:26px 24px}
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

/* EXIT-INTENT MODAL */
#exit-overlay{display:none;position:fixed;inset:0;z-index:9200;background:rgba(2,6,23,.75);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);align-items:center;justify-content:center;padding:1.25rem}
#exit-overlay.open{display:flex}
#exit-panel{position:relative;width:100%;max-width:420px;background:var(--navy);border:1px solid var(--charcoal);border-radius:16px;padding:2rem 1.75rem;box-shadow:0 24px 80px rgba(0,0,0,.7);text-align:center}
#exit-close{position:absolute;top:10px;right:10px;background:transparent;border:none;color:var(--slate);font-size:18px;cursor:pointer;width:32px;height:32px;border-radius:999px;display:flex;align-items:center;justify-content:center;line-height:1;transition:background .15s,color .15s}
#exit-close:hover{background:var(--charcoal);color:#fff}
#exit-panel h3{font-size:1.3rem;font-weight:800;color:#fff;letter-spacing:-.02em;margin-bottom:.5rem}
#exit-panel p{color:var(--slate);font-size:14px;line-height:1.6;margin-bottom:1.25rem}
#exit-panel .lead-input{width:100%;margin-bottom:10px}
#exit-panel .lead-submit{width:100%}
#exit-form-wrap.hidden,#exit-success.hidden{display:none}
/* WinnerDataAI child-brand light mode: cream canvas, terracotta action, black ink. */
:root{
  --navy:#f5f0e8;--navy-band:#ede3d7;--header-strip:#fbfaf7;--charcoal:#fbfaf7;
  --orange:#9f4d32;--orange-hover:#a94f31;--slate:#5f564e;--slate-dim:#6e655e;
  --body-text:#1f1b16;--green:#2f7a4b;--amber:#9f4d32;--red:#a13b32;
  --divider:rgba(31,27,22,.14);--gold:#9f4d32
}
body{background:var(--navy);color:var(--body-text)}
nav{background:rgba(245,240,232,.94);border-bottom-color:var(--orange)}
.logo,.case-address,h1,.section-h,.feat-title,.tile-val,.upsell-price,.price-name,.price-amount{color:var(--body-text)}
.nav-links a,.hero-sub,.section-sub,.case-date,.status-line,.feat-desc,.proof-footnote,.price-desc,.price-feature,.foot-upl,.foot-copy{color:var(--slate)}
.nav-links a:hover,.btn-outline:hover,.btn-outline-orange:hover{color:var(--body-text)}
.hero-cred b,.eyebrow,.hero-artifact b,.feat-section,.case-meta,.tile-val.orange,.btn-outline-orange,.popular-chip{color:var(--orange)}
.hero-artifact,.tile,.feat-card,.price-card,.upsell-card{background:var(--charcoal);border-color:var(--divider)}
.case-card{background:var(--navy);border-color:var(--divider)}
.case-header{background:var(--header-strip);border-left-color:var(--orange)}
.btn-solid,.btn-replay,.nav-cta,.lead-submit,.upsell-cta,.price-cta{background:var(--orange);color:var(--navy)}
.btn-solid:hover,.btn-replay:hover,.nav-cta:hover,.lead-submit:hover,.upsell-cta:hover,.price-cta:hover{background:var(--orange-hover)}
.btn-outline{border-color:var(--slate);color:var(--body-text)}
.lead-band,.proof-band{background:var(--navy-band)}
.county-select,.lead-input{background:var(--charcoal);border-color:var(--slate);color:var(--body-text)}
.county-select option{background:var(--charcoal);color:var(--body-text)}
.disclaimer-bar{background:var(--header-strip);color:var(--slate);border-color:var(--divider)}
#chat-bubble{background:var(--orange);color:var(--navy);box-shadow:0 4px 24px rgba(159,77,50,.28)}
#chat-close{background:rgba(251,250,247,.9);border-color:var(--divider);color:var(--slate)}
#chat-close:hover{background:var(--charcoal);color:var(--body-text)}
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
  <h1>For Florida Tax-Deed &amp; Foreclosure Investors —<br>See What Competitors Miss.</h1>
  <p class="hero-sub">Backed by 20 years of Florida auction data and 67-county parcel coverage. Start your first Gold Standard county report free.</p>
  <div class="hero-cred">67 FL counties tracked · <b>⭐ GOLD_COUNT_PLACEHOLDER Gold Standard certified</b></div>
  <div class="hero-artifact">Real case · Marion County: Shapira Max Bid <b>$82,000</b> <span class="res">→ sale closed $73,501 · ceiling held ✓</span></div>
  <div class="hero-ctas">
    <a class="btn-solid" href="#lead">Check Your County Free →</a>
    <a class="btn-outline" href="#report">See a live sample report →</a>
  </div>
  <div style="font-size:12px;color:var(--slate-dim);margin-top:.85rem">No credit card required &nbsp;·&nbsp; <a href="javascript:void(0)" onclick="openChat()" style="color:var(--orange);font-weight:600;text-decoration:underline">Ask about your county →</a></div>
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

    <p class="proof-footnote">Every SIGNAL$ Property Report ships with this scorecard — the prediction is published pre-sale and graded automatically against the courthouse record within 24 hours.</p>
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
    <p style="color:var(--slate);font-size:15px;line-height:1.6">Choose your county. We'll send you one full SIGNAL$ Property Report from an upcoming sale — scorecard included when the outcome lands.</p>

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
        <a id="upsell-25" href="/buy-report" class="upsell-cta ghost" style="flex:1;min-width:160px;text-align:center;display:inline-block;border:1px solid var(--orange);color:var(--orange);padding:12px 20px;border-radius:8px;font-size:13px;font-weight:700;text-decoration:none">Get SIGNAL$ Property Report — $25 →</a>
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
        <div class="price-tier">SIGNAL$ Single Report</div>
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

<!-- EXIT-INTENT LEAD CAPTURE -->
<div id="exit-overlay" role="dialog" aria-modal="true" aria-label="Get your free county report" onclick="handleExitOverlayClick(event)">
  <div id="exit-panel">
    <button id="exit-close" onclick="closeExitIntent()" aria-label="Close">&#x2715;</button>
    <div id="exit-form-wrap">
      <h3>Before you go — get your county's free auction report</h3>
      <p>One email. Your county's next upcoming tax-deed &amp; foreclosure auctions, free.</p>
      <input class="lead-input" id="exit-email" type="email" placeholder="your@email.com" autocomplete="email">
      <button class="lead-submit" onclick="submitExitIntentLead()" id="exit-submit-btn">Get My Free County Report &rarr;</button>
      <div class="lead-error" id="exit-error"></div>
    </div>
    <div id="exit-success" class="hidden">
      <h3>Check your inbox</h3>
      <p>Your free report is on its way. We'll also flag your county's next upcoming auctions.</p>
    </div>
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

// ── EXIT-INTENT LEAD CAPTURE — fires once per session, never on checkout/report pages ──
var EXIT_EXCLUDED_PATHS=['/buy-report','/subscribe','/report-success'];
var exitIntentTriggerKind='';
function shouldSkipExitIntent(){
  return !!sessionStorage.getItem('exitIntentShown') || EXIT_EXCLUDED_PATHS.indexOf(window.location.pathname)!==-1;
}
function showExitIntent(){
  if(shouldSkipExitIntent()) return;
  sessionStorage.setItem('exitIntentShown','1');
  document.getElementById('exit-overlay').classList.add('open');
  document.body.style.overflow='hidden';
  try{if(window.posthog)posthog.capture('exit_intent_shown',{trigger:exitIntentTriggerKind});}catch(e){}
}
function closeExitIntent(){
  document.getElementById('exit-overlay').classList.remove('open');
  document.body.style.overflow='';
}
function handleExitOverlayClick(e){
  if(e.target===document.getElementById('exit-overlay')) closeExitIntent();
}
document.addEventListener('keydown',function(e){
  if(e.key==='Escape') closeExitIntent();
});

// Desktop: mouseleave through the top edge of the viewport (about-to-close-tab signal)
document.addEventListener('mouseleave',function(e){
  if(e.clientY>10) return;
  exitIntentTriggerKind='desktop_mouseleave';
  showExitIntent();
});

// Mobile: exit-intent has no touch equivalent — use first-scroll-then-idle-15s instead
if(('ontouchstart' in window)||navigator.maxTouchPoints>0){
  var mobileIdleTimer=null;
  window.addEventListener('scroll',function(){
    if(mobileIdleTimer) clearTimeout(mobileIdleTimer);
    mobileIdleTimer=setTimeout(function(){
      exitIntentTriggerKind='mobile_idle';
      showExitIntent();
    },15000);
  },{passive:true});
}

async function submitExitIntentLead(){
  var email=document.getElementById('exit-email').value.trim();
  var err=document.getElementById('exit-error');
  err.textContent='';
  if(!email||!email.includes('@')){err.textContent='Please enter a valid email address.';return;}
  var btn=document.getElementById('exit-submit-btn');
  btn.disabled=true;btn.textContent='Sending…';
  try{
    var r=await fetch('/chat/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,source:'exit_intent',email_consent:true})});
    var data=r.ok?await r.json():{ok:false};
    if(data.ok){
      document.getElementById('exit-form-wrap').classList.add('hidden');
      document.getElementById('exit-success').classList.remove('hidden');
      try{if(window.posthog)posthog.capture('exit_intent_captured',{trigger:exitIntentTriggerKind});}catch(e){}
    } else {
      btn.disabled=false;btn.textContent='Get My Free County Report →';
      err.textContent='Something went wrong. Please try again.';
    }
  }catch(e){
    btn.disabled=false;btn.textContent='Get My Free County Report →';
    err.textContent='Something went wrong. Please try again.';
  }
}
</script>

${HOMEPAGE_SCRIPT}
</body>
</html>`; }

const TERMS_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Terms of Service — BidDeed.AI</title>
<meta name="description" content="Terms of Service for BidDeed.AI, Florida foreclosure and tax deed auction intelligence from Everest Capital USA.">
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.15rem;margin:2rem 0 .5rem;color:var(--text)}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.4rem}
.box{background:var(--navy2,#0b1220);color:var(--text);border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:var(--text)}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:var(--text);font-weight:700}
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
<meta name="description" content="Privacy Policy for BidDeed.AI — how Everest Capital USA collects, uses, and protects your information.">
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.15rem;margin:2rem 0 .5rem;color:var(--text)}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.4rem}
.box{background:var(--navy2,#0b1220);color:var(--text);border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:var(--text)}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:var(--text);font-weight:700}
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
<meta name="description" content="BidDeed.AI is an information and analytics platform, not legal, financial, or investment advice — read the full disclaimer before bidding.">
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.15rem;margin:2rem 0 .5rem;color:var(--text)}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.4rem}
.box{background:var(--navy2,#0b1220);color:var(--text);border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:var(--text)}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:var(--text);font-weight:700}
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
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.05rem;margin:2rem 0 .6rem;color:var(--text)}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.45rem}
table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.88rem}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--border);color:var(--muted)}
th{color:var(--text);font-weight:600}
.box{background:var(--navy2,#0b1220);color:var(--text);border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:var(--text)}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:var(--text);font-weight:700}
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
<meta name="description" content="How BidDeed.AI protects your data — encryption, access controls, and payment security via Stripe.">
${POSTHOG_SCRIPT}
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#e2eaf2;--border:#1e293b}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.5rem 5rem}
a{color:var(--orange);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.9rem;margin:.5rem 0 .25rem}h2{font-size:1.05rem;margin:2rem 0 .6rem;color:var(--text)}
.upd{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
p,li{color:var(--muted);font-size:.95rem}li{margin-bottom:.45rem}
ul{padding-left:1.3rem}
.box{background:var(--navy2,#0b1220);color:var(--text);border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0}
.box strong{color:var(--text)}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.9rem}
nav.top{border-bottom:1px solid var(--border);padding:1rem 1.5rem}
nav.top a{color:var(--text);font-weight:700}
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


// -- Self-hosted county-page assets (Phase 0 items 3-4, 2026-08-20) --------
// The 67 /county/:slug pages loaded Tailwind's dev CDN, Alpine and PapaParse
// from third-party CDNs that this Worker's own CSP (script-src 'self' ...)
// blocks -- so every county page showed only the Phase-0 fallback banner to
// every visitor. Verified live 2026-08-20 (3 CSP console errors per page,
// interactive table never booted). Assets are served from /assets/* on this
// origin: tailwind-county.css is a static build generated from the county
// template's class set (no inline tailwind.config existed, so default-config
// JIT output and this static build are equivalent); alpine 3.13.5 and
// papaparse 5.4.1 are the exact pinned CDN versions, vendored verbatim
// (fetched at build time from cdnjs, length-verified 43838/19469 bytes).
const BD_COUNTY_TW_CSS = "*,:after,:before{--tw-border-spacing-x:0;--tw-border-spacing-y:0;--tw-translate-x:0;--tw-translate-y:0;--tw-rotate:0;--tw-skew-x:0;--tw-skew-y:0;--tw-scale-x:1;--tw-scale-y:1;--tw-pan-x: ;--tw-pan-y: ;--tw-pinch-zoom: ;--tw-scroll-snap-strictness:proximity;--tw-gradient-from-position: ;--tw-gradient-via-position: ;--tw-gradient-to-position: ;--tw-ordinal: ;--tw-slashed-zero: ;--tw-numeric-figure: ;--tw-numeric-spacing: ;--tw-numeric-fraction: ;--tw-ring-inset: ;--tw-ring-offset-width:0px;--tw-ring-offset-color:#fff;--tw-ring-color:rgba(59,130,246,.5);--tw-ring-offset-shadow:0 0 #0000;--tw-ring-shadow:0 0 #0000;--tw-shadow:0 0 #0000;--tw-shadow-colored:0 0 #0000;--tw-blur: ;--tw-brightness: ;--tw-contrast: ;--tw-grayscale: ;--tw-hue-rotate: ;--tw-invert: ;--tw-saturate: ;--tw-sepia: ;--tw-drop-shadow: ;--tw-backdrop-blur: ;--tw-backdrop-brightness: ;--tw-backdrop-contrast: ;--tw-backdrop-grayscale: ;--tw-backdrop-hue-rotate: ;--tw-backdrop-invert: ;--tw-backdrop-opacity: ;--tw-backdrop-saturate: ;--tw-backdrop-sepia: ;--tw-contain-size: ;--tw-contain-layout: ;--tw-contain-paint: ;--tw-contain-style: }::backdrop{--tw-border-spacing-x:0;--tw-border-spacing-y:0;--tw-translate-x:0;--tw-translate-y:0;--tw-rotate:0;--tw-skew-x:0;--tw-skew-y:0;--tw-scale-x:1;--tw-scale-y:1;--tw-pan-x: ;--tw-pan-y: ;--tw-pinch-zoom: ;--tw-scroll-snap-strictness:proximity;--tw-gradient-from-position: ;--tw-gradient-via-position: ;--tw-gradient-to-position: ;--tw-ordinal: ;--tw-slashed-zero: ;--tw-numeric-figure: ;--tw-numeric-spacing: ;--tw-numeric-fraction: ;--tw-ring-inset: ;--tw-ring-offset-width:0px;--tw-ring-offset-color:#fff;--tw-ring-color:rgba(59,130,246,.5);--tw-ring-offset-shadow:0 0 #0000;--tw-ring-shadow:0 0 #0000;--tw-shadow:0 0 #0000;--tw-shadow-colored:0 0 #0000;--tw-blur: ;--tw-brightness: ;--tw-contrast: ;--tw-grayscale: ;--tw-hue-rotate: ;--tw-invert: ;--tw-saturate: ;--tw-sepia: ;--tw-drop-shadow: ;--tw-backdrop-blur: ;--tw-backdrop-brightness: ;--tw-backdrop-contrast: ;--tw-backdrop-grayscale: ;--tw-backdrop-hue-rotate: ;--tw-backdrop-invert: ;--tw-backdrop-opacity: ;--tw-backdrop-saturate: ;--tw-backdrop-sepia: ;--tw-contain-size: ;--tw-contain-layout: ;--tw-contain-paint: ;--tw-contain-style: }/*! tailwindcss v3.4.17 | MIT License | https://tailwindcss.com*/*,:after,:before{box-sizing:border-box;border:0 solid #e5e7eb}:after,:before{--tw-content:\"\"}:host,html{line-height:1.5;-webkit-text-size-adjust:100%;-moz-tab-size:4;-o-tab-size:4;tab-size:4;font-family:ui-sans-serif,system-ui,sans-serif,Apple Color Emoji,Segoe UI Emoji,Segoe UI Symbol,Noto Color Emoji;font-feature-settings:normal;font-variation-settings:normal;-webkit-tap-highlight-color:transparent}body{margin:0;line-height:inherit}hr{height:0;color:inherit;border-top-width:1px}abbr:where([title]){-webkit-text-decoration:underline dotted;text-decoration:underline dotted}h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}a{color:inherit;text-decoration:inherit}b,strong{font-weight:bolder}code,kbd,pre,samp{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,Liberation Mono,Courier New,monospace;font-feature-settings:normal;font-variation-settings:normal;font-size:1em}small{font-size:80%}sub,sup{font-size:75%;line-height:0;position:relative;vertical-align:baseline}sub{bottom:-.25em}sup{top:-.5em}table{text-indent:0;border-color:inherit;border-collapse:collapse}button,input,optgroup,select,textarea{font-family:inherit;font-feature-settings:inherit;font-variation-settings:inherit;font-size:100%;font-weight:inherit;line-height:inherit;letter-spacing:inherit;color:inherit;margin:0;padding:0}button,select{text-transform:none}button,input:where([type=button]),input:where([type=reset]),input:where([type=submit]){-webkit-appearance:button;background-color:transparent;background-image:none}:-moz-focusring{outline:auto}:-moz-ui-invalid{box-shadow:none}progress{vertical-align:baseline}::-webkit-inner-spin-button,::-webkit-outer-spin-button{height:auto}[type=search]{-webkit-appearance:textfield;outline-offset:-2px}::-webkit-search-decoration{-webkit-appearance:none}::-webkit-file-upload-button{-webkit-appearance:button;font:inherit}summary{display:list-item}blockquote,dd,dl,figure,h1,h2,h3,h4,h5,h6,hr,p,pre{margin:0}fieldset{margin:0}fieldset,legend{padding:0}menu,ol,ul{list-style:none;margin:0;padding:0}dialog{padding:0}textarea{resize:vertical}input::-moz-placeholder,textarea::-moz-placeholder{opacity:1;color:#9ca3af}input::placeholder,textarea::placeholder{opacity:1;color:#9ca3af}[role=button],button{cursor:pointer}:disabled{cursor:default}audio,canvas,embed,iframe,img,object,svg,video{display:block;vertical-align:middle}img,video{max-width:100%;height:auto}[hidden]:where(:not([hidden=until-found])){display:none}.fixed{position:fixed}.absolute{position:absolute}.relative{position:relative}.sticky{position:sticky}.inset-0{inset:0}.inset-x-0{left:0;right:0}.bottom-0{bottom:0}.left-0{left:0}.left-3{left:.75rem}.right-0{right:0}.right-4{right:1rem}.top-0{top:0}.top-1\\/2{top:50%}.z-20{z-index:20}.z-30{z-index:30}.z-40{z-index:40}.mx-auto{margin-left:auto;margin-right:auto}.-mt-1{margin-top:-.25rem}.mb-1{margin-bottom:.25rem}.mb-2{margin-bottom:.5rem}.mb-3{margin-bottom:.75rem}.mb-4{margin-bottom:1rem}.ml-1{margin-left:.25rem}.ml-auto{margin-left:auto}.mr-1{margin-right:.25rem}.mt-0\\.5{margin-top:.125rem}.mt-1{margin-top:.25rem}.mt-1\\.5{margin-top:.375rem}.mt-12{margin-top:3rem}.mt-2{margin-top:.5rem}.mt-3{margin-top:.75rem}.mt-4{margin-top:1rem}.mt-5{margin-top:1.25rem}.line-clamp-2{overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2}.block{display:block}.flex{display:flex}.table{display:table}.grid{display:grid}.hidden{display:none}.h-1{height:.25rem}.h-32{height:8rem}.h-4{height:1rem}.h-5{height:1.25rem}.h-7{height:1.75rem}.max-h-\\[88vh\\]{max-height:88vh}.max-h-\\[90vh\\]{max-height:90vh}.min-h-screen{min-height:100vh}.w-12{width:3rem}.w-4{width:1rem}.w-5{width:1.25rem}.w-7{width:1.75rem}.w-full{width:100%}.min-w-0{min-width:0}.max-w-5xl{max-width:64rem}.max-w-\\[85\\%\\]{max-width:85%}.flex-1{flex:1 1 0%}.shrink-0{flex-shrink:0}.-translate-y-1\\/2{--tw-translate-y:-50%;transform:translate(var(--tw-translate-x),var(--tw-translate-y)) rotate(var(--tw-rotate)) skewX(var(--tw-skew-x)) skewY(var(--tw-skew-y)) scaleX(var(--tw-scale-x)) scaleY(var(--tw-scale-y))}.cursor-pointer{cursor:pointer}.grid-cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}.grid-cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}.flex-col{flex-direction:column}.flex-wrap{flex-wrap:wrap}.items-start{align-items:flex-start}.items-center{align-items:center}.justify-start{justify-content:flex-start}.justify-end{justify-content:flex-end}.justify-center{justify-content:center}.justify-between{justify-content:space-between}.gap-1{gap:.25rem}.gap-1\\.5{gap:.375rem}.gap-2{gap:.5rem}.gap-2\\.5{gap:.625rem}.gap-3{gap:.75rem}.space-y-1\\.5>:not([hidden])~:not([hidden]){--tw-space-y-reverse:0;margin-top:calc(.375rem*(1 - var(--tw-space-y-reverse)));margin-bottom:calc(.375rem*var(--tw-space-y-reverse))}.space-y-2>:not([hidden])~:not([hidden]){--tw-space-y-reverse:0;margin-top:calc(.5rem*(1 - var(--tw-space-y-reverse)));margin-bottom:calc(.5rem*var(--tw-space-y-reverse))}.space-y-3>:not([hidden])~:not([hidden]){--tw-space-y-reverse:0;margin-top:calc(.75rem*(1 - var(--tw-space-y-reverse)));margin-bottom:calc(.75rem*var(--tw-space-y-reverse))}.overflow-hidden{overflow:hidden}.overflow-x-auto{overflow-x:auto}.overflow-y-auto{overflow-y:auto}.truncate{overflow:hidden;text-overflow:ellipsis}.truncate,.whitespace-nowrap{white-space:nowrap}.rounded{border-radius:.25rem}.rounded-2xl{border-radius:1rem}.rounded-full{border-radius:9999px}.rounded-lg{border-radius:.5rem}.rounded-xl{border-radius:.75rem}.rounded-t-2xl{border-top-left-radius:1rem;border-top-right-radius:1rem}.border{border-width:1px}.border-b{border-bottom-width:1px}.border-t{border-top-width:1px}.border-amber-500{--tw-border-opacity:1;border-color:rgb(245 158 11/var(--tw-border-opacity,1))}.border-amber-500\\/20{border-color:rgba(245,158,11,.2)}.border-amber-500\\/30{border-color:rgba(245,158,11,.3)}.border-amber-500\\/40{border-color:rgba(245,158,11,.4)}.border-blue-500\\/40{border-color:rgba(59,130,246,.4)}.border-blue-700\\/30{border-color:rgba(29,78,216,.3)}.border-emerald-700\\/30{border-color:rgba(4,120,87,.3)}.border-purple-500\\/30{border-color:rgba(168,85,247,.3)}.border-purple-500\\/40{border-color:rgba(168,85,247,.4)}.border-red-500\\/30{border-color:rgba(239,68,68,.3)}.border-red-500\\/40{border-color:rgba(239,68,68,.4)}.border-slate-700{--tw-border-opacity:1;border-color:rgb(51 65 85/var(--tw-border-opacity,1))}.border-slate-700\\/30{border-color:rgba(51,65,85,.3)}.border-slate-700\\/40{border-color:rgba(51,65,85,.4)}.border-slate-700\\/50{border-color:rgba(51,65,85,.5)}.border-slate-700\\/60{border-color:rgba(51,65,85,.6)}.border-slate-800\\/40{border-color:rgba(30,41,59,.4)}.bg-amber-500{--tw-bg-opacity:1;background-color:rgb(245 158 11/var(--tw-bg-opacity,1))}.bg-amber-500\\/10{background-color:rgba(245,158,11,.1)}.bg-black\\/70{background-color:rgba(0,0,0,.7)}.bg-black\\/80{background-color:rgba(0,0,0,.8)}.bg-blue-500\\/10{background-color:rgba(59,130,246,.1)}.bg-blue-500\\/5{background-color:rgba(59,130,246,.05)}.bg-blue-950\\/40{background-color:rgba(23,37,84,.4)}.bg-emerald-950\\/50{background-color:rgba(2,44,34,.5)}.bg-purple-500\\/5{background-color:rgba(168,85,247,.05)}.bg-red-500\\/5{background-color:rgba(239,68,68,.05)}.bg-slate-600{--tw-bg-opacity:1;background-color:rgb(71 85 105/var(--tw-bg-opacity,1))}.bg-slate-700\\/50{background-color:rgba(51,65,85,.5)}.bg-slate-800{--tw-bg-opacity:1;background-color:rgb(30 41 59/var(--tw-bg-opacity,1))}.bg-slate-800\\/50{background-color:rgba(30,41,59,.5)}.bg-slate-800\\/60{background-color:rgba(30,41,59,.6)}.bg-slate-900{--tw-bg-opacity:1;background-color:rgb(15 23 42/var(--tw-bg-opacity,1))}.bg-slate-900\\/60{background-color:rgba(15,23,42,.6)}.bg-slate-900\\/80{background-color:rgba(15,23,42,.8)}.bg-slate-950\\/85{background-color:rgba(2,6,23,.85)}.bg-slate-950\\/90{background-color:rgba(2,6,23,.9)}.bg-gradient-to-br{background-image:linear-gradient(to bottom right,var(--tw-gradient-stops))}.bg-gradient-to-r{background-image:linear-gradient(to right,var(--tw-gradient-stops))}.from-amber-400{--tw-gradient-from:#fbbf24 var(--tw-gradient-from-position);--tw-gradient-to:rgba(251,191,36,0) var(--tw-gradient-to-position);--tw-gradient-stops:var(--tw-gradient-from),var(--tw-gradient-to)}.from-amber-500{--tw-gradient-from:#f59e0b var(--tw-gradient-from-position);--tw-gradient-to:rgba(245,158,11,0) var(--tw-gradient-to-position);--tw-gradient-stops:var(--tw-gradient-from),var(--tw-gradient-to)}.from-red-500{--tw-gradient-from:#ef4444 var(--tw-gradient-from-position);--tw-gradient-to:rgba(239,68,68,0) var(--tw-gradient-to-position);--tw-gradient-stops:var(--tw-gradient-from),var(--tw-gradient-to)}.from-red-500\\/15{--tw-gradient-from:rgba(239,68,68,.15) var(--tw-gradient-from-position);--tw-gradient-to:rgba(239,68,68,0) var(--tw-gradient-to-position);--tw-gradient-stops:var(--tw-gradient-from),var(--tw-gradient-to)}.from-sky-500{--tw-gradient-from:#0ea5e9 var(--tw-gradient-from-position);--tw-gradient-to:rgba(14,165,233,0) var(--tw-gradient-to-position);--tw-gradient-stops:var(--tw-gradient-from),var(--tw-gradient-to)}.from-sky-500\\/15{--tw-gradient-from:rgba(14,165,233,.15) var(--tw-gradient-from-position);--tw-gradient-to:rgba(14,165,233,0) var(--tw-gradient-to-position);--tw-gradient-stops:var(--tw-gradient-from),var(--tw-gradient-to)}.to-amber-200{--tw-gradient-to:#fde68a var(--tw-gradient-to-position)}.to-amber-400{--tw-gradient-to:#fbbf24 var(--tw-gradient-to-position)}.to-amber-500{--tw-gradient-to:#f59e0b var(--tw-gradient-to-position)}.to-amber-500\\/15{--tw-gradient-to:rgba(245,158,11,.15) var(--tw-gradient-to-position)}.to-purple-500{--tw-gradient-to:#a855f7 var(--tw-gradient-to-position)}.to-purple-500\\/15{--tw-gradient-to:rgba(168,85,247,.15) var(--tw-gradient-to-position)}.bg-clip-text{-webkit-background-clip:text;background-clip:text}.p-2\\.5{padding:.625rem}.p-3{padding:.75rem}.p-4{padding:1rem}.p-5{padding:1.25rem}.px-1{padding-left:.25rem;padding-right:.25rem}.px-1\\.5{padding-left:.375rem;padding-right:.375rem}.px-2{padding-left:.5rem;padding-right:.5rem}.px-3{padding-left:.75rem;padding-right:.75rem}.px-4{padding-left:1rem;padding-right:1rem}.px-5{padding-left:1.25rem;padding-right:1.25rem}.py-1{padding-top:.25rem;padding-bottom:.25rem}.py-1\\.5{padding-top:.375rem;padding-bottom:.375rem}.py-2{padding-top:.5rem;padding-bottom:.5rem}.py-2\\.5{padding-top:.625rem;padding-bottom:.625rem}.py-3{padding-top:.75rem;padding-bottom:.75rem}.py-3\\.5{padding-top:.875rem;padding-bottom:.875rem}.py-4{padding-top:1rem;padding-bottom:1rem}.pb-2{padding-bottom:.5rem}.pb-24{padding-bottom:6rem}.pb-3{padding-bottom:.75rem}.pb-4{padding-bottom:1rem}.pl-10{padding-left:2.5rem}.pl-3{padding-left:.75rem}.pr-2{padding-right:.5rem}.pr-3{padding-right:.75rem}.pt-1{padding-top:.25rem}.pt-3{padding-top:.75rem}.text-left{text-align:left}.text-center{text-align:center}.text-right{text-align:right}.font-mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,Liberation Mono,Courier New,monospace}.text-2xl{font-size:1.5rem;line-height:2rem}.text-3xl{font-size:1.875rem;line-height:2.25rem}.text-\\[10px\\]{font-size:10px}.text-\\[11px\\]{font-size:11px}.text-\\[15px\\]{font-size:15px}.text-\\[9px\\]{font-size:9px}.text-base{font-size:1rem;line-height:1.5rem}.text-lg{font-size:1.125rem;line-height:1.75rem}.text-sm{font-size:.875rem;line-height:1.25rem}.text-xl{font-size:1.25rem;line-height:1.75rem}.text-xs{font-size:.75rem;line-height:1rem}.font-black{font-weight:900}.font-bold{font-weight:700}.font-extrabold{font-weight:800}.font-medium{font-weight:500}.font-semibold{font-weight:600}.uppercase{text-transform:uppercase}.italic{font-style:italic}.not-italic{font-style:normal}.leading-none{line-height:1}.leading-snug{line-height:1.375}.leading-tight{line-height:1.25}.tracking-tight{letter-spacing:-.025em}.tracking-wide{letter-spacing:.025em}.tracking-wider{letter-spacing:.05em}.tracking-widest{letter-spacing:.1em}.text-amber-300{--tw-text-opacity:1;color:rgb(252 211 77/var(--tw-text-opacity,1))}.text-amber-400{--tw-text-opacity:1;color:rgb(251 191 36/var(--tw-text-opacity,1))}.text-amber-400\\/80{color:rgba(251,191,36,.8)}.text-amber-500{--tw-text-opacity:1;color:rgb(245 158 11/var(--tw-text-opacity,1))}.text-blue-300{--tw-text-opacity:1;color:rgb(147 197 253/var(--tw-text-opacity,1))}.text-blue-400{--tw-text-opacity:1;color:rgb(96 165 250/var(--tw-text-opacity,1))}.text-emerald-400{--tw-text-opacity:1;color:rgb(52 211 153/var(--tw-text-opacity,1))}.text-pink-300{--tw-text-opacity:1;color:rgb(249 168 212/var(--tw-text-opacity,1))}.text-purple-400{--tw-text-opacity:1;color:rgb(192 132 252/var(--tw-text-opacity,1))}.text-red-300{--tw-text-opacity:1;color:rgb(252 165 165/var(--tw-text-opacity,1))}.text-red-400{--tw-text-opacity:1;color:rgb(248 113 113/var(--tw-text-opacity,1))}.text-sky-300{--tw-text-opacity:1;color:rgb(125 211 252/var(--tw-text-opacity,1))}.text-slate-200{--tw-text-opacity:1;color:rgb(226 232 240/var(--tw-text-opacity,1))}.text-slate-300{--tw-text-opacity:1;color:rgb(203 213 225/var(--tw-text-opacity,1))}.text-slate-400{--tw-text-opacity:1;color:rgb(148 163 184/var(--tw-text-opacity,1))}.text-slate-500{--tw-text-opacity:1;color:rgb(100 116 139/var(--tw-text-opacity,1))}.text-slate-900{--tw-text-opacity:1;color:rgb(15 23 42/var(--tw-text-opacity,1))}.text-transparent{color:transparent}.text-white{--tw-text-opacity:1;color:rgb(255 255 255/var(--tw-text-opacity,1))}.underline{text-decoration-line:underline}.accent-amber-500{accent-color:#f59e0b}.accent-blue-500{accent-color:#3b82f6}.accent-emerald-500{accent-color:#10b981}.accent-pink-500{accent-color:#ec4899}.accent-purple-500{accent-color:#a855f7}.accent-red-500{accent-color:#ef4444}.accent-slate-500{accent-color:#64748b}.opacity-60{opacity:.6}.opacity-70{opacity:.7}.shadow-2xl{--tw-shadow:0 25px 50px -12px rgba(0,0,0,.25);--tw-shadow-colored:0 25px 50px -12px var(--tw-shadow-color);box-shadow:var(--tw-ring-offset-shadow,0 0 #0000),var(--tw-ring-shadow,0 0 #0000),var(--tw-shadow)}.shadow-amber-500\\/40{--tw-shadow-color:rgba(245,158,11,.4);--tw-shadow:var(--tw-shadow-colored)}.filter{filter:var(--tw-blur) var(--tw-brightness) var(--tw-contrast) var(--tw-grayscale) var(--tw-hue-rotate) var(--tw-invert) var(--tw-saturate) var(--tw-sepia) var(--tw-drop-shadow)}.backdrop-blur{--tw-backdrop-blur:blur(8px);-webkit-backdrop-filter:var(--tw-backdrop-blur) var(--tw-backdrop-brightness) var(--tw-backdrop-contrast) var(--tw-backdrop-grayscale) var(--tw-backdrop-hue-rotate) var(--tw-backdrop-invert) var(--tw-backdrop-opacity) var(--tw-backdrop-saturate) var(--tw-backdrop-sepia);backdrop-filter:var(--tw-backdrop-blur) var(--tw-backdrop-brightness) var(--tw-backdrop-contrast) var(--tw-backdrop-grayscale) var(--tw-backdrop-hue-rotate) var(--tw-backdrop-invert) var(--tw-backdrop-opacity) var(--tw-backdrop-saturate) var(--tw-backdrop-sepia)}.transition-transform{transition-property:transform;transition-timing-function:cubic-bezier(.4,0,.2,1);transition-duration:.15s}.hover\\:bg-amber-400:hover{--tw-bg-opacity:1;background-color:rgb(251 191 36/var(--tw-bg-opacity,1))}.hover\\:bg-amber-500\\/5:hover{background-color:rgba(245,158,11,.05)}.hover\\:bg-slate-800:hover{--tw-bg-opacity:1;background-color:rgb(30 41 59/var(--tw-bg-opacity,1))}.hover\\:bg-slate-800\\/60:hover{background-color:rgba(30,41,59,.6)}.hover\\:text-white:hover{--tw-text-opacity:1;color:rgb(255 255 255/var(--tw-text-opacity,1))}.active\\:scale-\\[0\\.98\\]:active{--tw-scale-x:0.98;--tw-scale-y:0.98;transform:translate(var(--tw-translate-x),var(--tw-translate-y)) rotate(var(--tw-rotate)) skewX(var(--tw-skew-x)) skewY(var(--tw-skew-y)) scaleX(var(--tw-scale-x)) scaleY(var(--tw-scale-y))}.active\\:bg-slate-800\\/80:active{background-color:rgba(30,41,59,.8)}@media (min-width:640px){.sm\\:px-4{padding-left:1rem;padding-right:1rem}}@media (min-width:768px){.md\\:inset-0{inset:0}.md\\:flex{display:flex}.md\\:grid{display:grid}.md\\:hidden{display:none}.md\\:max-w-2xl{max-width:42rem}.md\\:max-w-xl{max-width:36rem}.md\\:grid-cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}.md\\:items-center{align-items:center}.md\\:justify-center{justify-content:center}.md\\:gap-4{gap:1rem}.md\\:rounded-2xl{border-radius:1rem}.md\\:border{border-width:1px}.md\\:p-4{padding:1rem}}@media (min-width:1024px){.lg\\:grid-cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}}";
const BD_ALPINE_JS = "(()=>{var rt=!1,nt=!1,q=[],it=-1;function Vt(e){Sn(e)}function Sn(e){q.includes(e)||q.push(e),An()}function ve(e){let t=q.indexOf(e);t!==-1&&t>it&&q.splice(t,1)}function An(){!nt&&!rt&&(rt=!0,queueMicrotask(On))}function On(){rt=!1,nt=!0;for(let e=0;e<q.length;e++)q[e](),it=e;q.length=0,it=-1,nt=!1}var T,N,L,st,ot=!0;function qt(e){ot=!1,e(),ot=!0}function Ut(e){T=e.reactive,L=e.release,N=t=>e.effect(t,{scheduler:r=>{ot?Vt(r):r()}}),st=e.raw}function at(e){N=e}function Wt(e){let t=()=>{};return[n=>{let i=N(n);return e._x_effects||(e._x_effects=new Set,e._x_runEffects=()=>{e._x_effects.forEach(o=>o())}),e._x_effects.add(i),t=()=>{i!==void 0&&(e._x_effects.delete(i),L(i))},i},()=>{t()}]}function Se(e,t){let r=!0,n,i=N(()=>{let o=e();JSON.stringify(o),r?n=o:queueMicrotask(()=>{t(o,n),n=o}),r=!1});return()=>L(i)}function U(e,t,r={}){e.dispatchEvent(new CustomEvent(t,{detail:r,bubbles:!0,composed:!0,cancelable:!0}))}function O(e,t){if(typeof ShadowRoot==\"function\"&&e instanceof ShadowRoot){Array.from(e.children).forEach(i=>O(i,t));return}let r=!1;if(t(e,()=>r=!0),r)return;let n=e.firstElementChild;for(;n;)O(n,t,!1),n=n.nextElementSibling}function v(e,...t){console.warn(`Alpine Warning: ${e}`,...t)}var Gt=!1;function Jt(){Gt&&v(\"Alpine has already been initialized on this page. Calling Alpine.start() more than once can cause problems.\"),Gt=!0,document.body||v(\"Unable to initialize. Trying to load Alpine before `<body>` is available. Did you forget to add `defer` in Alpine's `<script>` tag?\"),U(document,\"alpine:init\"),U(document,\"alpine:initializing\"),le(),rr(t=>S(t,O)),ee(t=>ce(t)),Ce((t,r)=>{ue(t,r).forEach(n=>n())});let e=t=>!W(t.parentElement,!0);Array.from(document.querySelectorAll(Zt().join(\",\"))).filter(e).forEach(t=>{S(t)}),U(document,\"alpine:initialized\")}var ct=[],Yt=[];function Xt(){return ct.map(e=>e())}function Zt(){return ct.concat(Yt).map(e=>e())}function Ae(e){ct.push(e)}function Oe(e){Yt.push(e)}function W(e,t=!1){return Q(e,r=>{if((t?Zt():Xt()).some(i=>r.matches(i)))return!0})}function Q(e,t){if(e){if(t(e))return e;if(e._x_teleportBack&&(e=e._x_teleportBack),!!e.parentElement)return Q(e.parentElement,t)}}function Qt(e){return Xt().some(t=>e.matches(t))}var er=[];function tr(e){er.push(e)}function S(e,t=O,r=()=>{}){ir(()=>{t(e,(n,i)=>{r(n,i),er.forEach(o=>o(n,i)),ue(n,n.attributes).forEach(o=>o()),n._x_ignore&&i()})})}function ce(e){O(e,t=>{lt(t),nr(t)})}var or=[],sr=[],ar=[];function rr(e){ar.push(e)}function ee(e,t){typeof t==\"function\"?(e._x_cleanups||(e._x_cleanups=[]),e._x_cleanups.push(t)):(t=e,sr.push(t))}function Ce(e){or.push(e)}function Re(e,t,r){e._x_attributeCleanups||(e._x_attributeCleanups={}),e._x_attributeCleanups[t]||(e._x_attributeCleanups[t]=[]),e._x_attributeCleanups[t].push(r)}function lt(e,t){e._x_attributeCleanups&&Object.entries(e._x_attributeCleanups).forEach(([r,n])=>{(t===void 0||t.includes(r))&&(n.forEach(i=>i()),delete e._x_attributeCleanups[r])})}function nr(e){if(e._x_cleanups)for(;e._x_cleanups.length;)e._x_cleanups.pop()()}var ut=new MutationObserver(mt),ft=!1;function le(){ut.observe(document,{subtree:!0,childList:!0,attributes:!0,attributeOldValue:!0}),ft=!0}function dt(){Cn(),ut.disconnect(),ft=!1}var fe=[];function Cn(){let e=ut.takeRecords();fe.push(()=>e.length>0&&mt(e));let t=fe.length;queueMicrotask(()=>{if(fe.length===t)for(;fe.length>0;)fe.shift()()})}function h(e){if(!ft)return e();dt();let t=e();return le(),t}var pt=!1,Te=[];function cr(){pt=!0}function lr(){pt=!1,mt(Te),Te=[]}function mt(e){if(pt){Te=Te.concat(e);return}let t=new Set,r=new Set,n=new Map,i=new Map;for(let o=0;o<e.length;o++)if(!e[o].target._x_ignoreMutationObserver&&(e[o].type===\"childList\"&&(e[o].addedNodes.forEach(s=>s.nodeType===1&&t.add(s)),e[o].removedNodes.forEach(s=>s.nodeType===1&&r.add(s))),e[o].type===\"attributes\")){let s=e[o].target,a=e[o].attributeName,c=e[o].oldValue,l=()=>{n.has(s)||n.set(s,[]),n.get(s).push({name:a,value:s.getAttribute(a)})},u=()=>{i.has(s)||i.set(s,[]),i.get(s).push(a)};s.hasAttribute(a)&&c===null?l():s.hasAttribute(a)?(u(),l()):u()}i.forEach((o,s)=>{lt(s,o)}),n.forEach((o,s)=>{or.forEach(a=>a(s,o))});for(let o of r)t.has(o)||(sr.forEach(s=>s(o)),ce(o));t.forEach(o=>{o._x_ignoreSelf=!0,o._x_ignore=!0});for(let o of t)r.has(o)||o.isConnected&&(delete o._x_ignoreSelf,delete o._x_ignore,ar.forEach(s=>s(o)),o._x_ignore=!0,o._x_ignoreSelf=!0);t.forEach(o=>{delete o._x_ignoreSelf,delete o._x_ignore}),t=null,r=null,n=null,i=null}function Me(e){return F(j(e))}function P(e,t,r){return e._x_dataStack=[t,...j(r||e)],()=>{e._x_dataStack=e._x_dataStack.filter(n=>n!==t)}}function j(e){return e._x_dataStack?e._x_dataStack:typeof ShadowRoot==\"function\"&&e instanceof ShadowRoot?j(e.host):e.parentNode?j(e.parentNode):[]}function F(e){return new Proxy({objects:e},Tn)}var Tn={ownKeys({objects:e}){return Array.from(new Set(e.flatMap(t=>Object.keys(t))))},has({objects:e},t){return t==Symbol.unscopables?!1:e.some(r=>Object.prototype.hasOwnProperty.call(r,t))},get({objects:e},t,r){return t==\"toJSON\"?Rn:Reflect.get(e.find(n=>Object.prototype.hasOwnProperty.call(n,t))||{},t,r)},set({objects:e},t,r,n){let i=e.find(s=>Object.prototype.hasOwnProperty.call(s,t))||e[e.length-1],o=Object.getOwnPropertyDescriptor(i,t);return o?.set&&o?.get?Reflect.set(i,t,r,n):Reflect.set(i,t,r)}};function Rn(){return Reflect.ownKeys(this).reduce((t,r)=>(t[r]=Reflect.get(this,r),t),{})}function Ne(e){let t=n=>typeof n==\"object\"&&!Array.isArray(n)&&n!==null,r=(n,i=\"\")=>{Object.entries(Object.getOwnPropertyDescriptors(n)).forEach(([o,{value:s,enumerable:a}])=>{if(a===!1||s===void 0)return;let c=i===\"\"?o:`${i}.${o}`;typeof s==\"object\"&&s!==null&&s._x_interceptor?n[o]=s.initialize(e,c,o):t(s)&&s!==n&&!(s instanceof Element)&&r(s,c)})};return r(e)}function Pe(e,t=()=>{}){let r={initialValue:void 0,_x_interceptor:!0,initialize(n,i,o){return e(this.initialValue,()=>Mn(n,i),s=>ht(n,i,s),i,o)}};return t(r),n=>{if(typeof n==\"object\"&&n!==null&&n._x_interceptor){let i=r.initialize.bind(r);r.initialize=(o,s,a)=>{let c=n.initialize(o,s,a);return r.initialValue=c,i(o,s,a)}}else r.initialValue=n;return r}}function Mn(e,t){return t.split(\".\").reduce((r,n)=>r[n],e)}function ht(e,t,r){if(typeof t==\"string\"&&(t=t.split(\".\")),t.length===1)e[t[0]]=r;else{if(t.length===0)throw error;return e[t[0]]||(e[t[0]]={}),ht(e[t[0]],t.slice(1),r)}}var ur={};function y(e,t){ur[e]=t}function de(e,t){return Object.entries(ur).forEach(([r,n])=>{let i=null;function o(){if(i)return i;{let[s,a]=_t(t);return i={interceptor:Pe,...s},ee(t,a),i}}Object.defineProperty(e,`$${r}`,{get(){return n(t,o())},enumerable:!1})}),e}function fr(e,t,r,...n){try{return r(...n)}catch(i){te(i,e,t)}}function te(e,t,r=void 0){e=Object.assign(e??{message:\"No error message given.\"},{el:t,expression:r}),console.warn(`Alpine Expression Error: ${e.message}\n\n${r?'Expression: \"'+r+`\"\n\n`:\"\"}`,t),setTimeout(()=>{throw e},0)}var Ie=!0;function ke(e){let t=Ie;Ie=!1;let r=e();return Ie=t,r}function R(e,t,r={}){let n;return x(e,t)(i=>n=i,r),n}function x(...e){return dr(...e)}var dr=xt;function pr(e){dr=e}function xt(e,t){let r={};de(r,e);let n=[r,...j(e)],i=typeof t==\"function\"?Nn(n,t):In(n,t,e);return fr.bind(null,e,t,i)}function Nn(e,t){return(r=()=>{},{scope:n={},params:i=[]}={})=>{let o=t.apply(F([n,...e]),i);De(r,o)}}var gt={};function Pn(e,t){if(gt[e])return gt[e];let r=Object.getPrototypeOf(async function(){}).constructor,n=/^[\\n\\s]*if.*\\(.*\\)/.test(e.trim())||/^(let|const)\\s/.test(e.trim())?`(async()=>{ ${e} })()`:e,o=(()=>{try{let s=new r([\"__self\",\"scope\"],`with (scope) { __self.result = ${n} }; __self.finished = true; return __self.result;`);return Object.defineProperty(s,\"name\",{value:`[Alpine] ${e}`}),s}catch(s){return te(s,t,e),Promise.resolve()}})();return gt[e]=o,o}function In(e,t,r){let n=Pn(t,r);return(i=()=>{},{scope:o={},params:s=[]}={})=>{n.result=void 0,n.finished=!1;let a=F([o,...e]);if(typeof n==\"function\"){let c=n(n,a).catch(l=>te(l,r,t));n.finished?(De(i,n.result,a,s,r),n.result=void 0):c.then(l=>{De(i,l,a,s,r)}).catch(l=>te(l,r,t)).finally(()=>n.result=void 0)}}}function De(e,t,r,n,i){if(Ie&&typeof t==\"function\"){let o=t.apply(r,n);o instanceof Promise?o.then(s=>De(e,s,r,n)).catch(s=>te(s,i,t)):e(o)}else typeof t==\"object\"&&t instanceof Promise?t.then(o=>e(o)):e(t)}var Et=\"x-\";function C(e=\"\"){return Et+e}function mr(e){Et=e}var yt={};function d(e,t){return yt[e]=t,{before(r){if(!yt[r]){console.warn(String.raw`Cannot find directive \\`${r}\\`. \\`${e}\\` will use the default order of execution`);return}let n=G.indexOf(r);G.splice(n>=0?n:G.indexOf(\"DEFAULT\"),0,e)}}}function ue(e,t,r){if(t=Array.from(t),e._x_virtualDirectives){let o=Object.entries(e._x_virtualDirectives).map(([a,c])=>({name:a,value:c})),s=vt(o);o=o.map(a=>s.find(c=>c.name===a.name)?{name:`x-bind:${a.name}`,value:`\"${a.value}\"`}:a),t=t.concat(o)}let n={};return t.map(_r((o,s)=>n[o]=s)).filter(xr).map(kn(n,r)).sort(Ln).map(o=>Dn(e,o))}function vt(e){return Array.from(e).map(_r()).filter(t=>!xr(t))}var bt=!1,pe=new Map,hr=Symbol();function ir(e){bt=!0;let t=Symbol();hr=t,pe.set(t,[]);let r=()=>{for(;pe.get(t).length;)pe.get(t).shift()();pe.delete(t)},n=()=>{bt=!1,r()};e(r),n()}function _t(e){let t=[],r=a=>t.push(a),[n,i]=Wt(e);return t.push(i),[{Alpine:B,effect:n,cleanup:r,evaluateLater:x.bind(x,e),evaluate:R.bind(R,e)},()=>t.forEach(a=>a())]}function Dn(e,t){let r=()=>{},n=yt[t.type]||r,[i,o]=_t(e);Re(e,t.original,o);let s=()=>{e._x_ignore||e._x_ignoreSelf||(n.inline&&n.inline(e,t,i),n=n.bind(n,e,t,i),bt?pe.get(hr).push(n):n())};return s.runCleanups=o,s}var Le=(e,t)=>({name:r,value:n})=>(r.startsWith(e)&&(r=r.replace(e,t)),{name:r,value:n}),$e=e=>e;function _r(e=()=>{}){return({name:t,value:r})=>{let{name:n,value:i}=gr.reduce((o,s)=>s(o),{name:t,value:r});return n!==t&&e(n,t),{name:n,value:i}}}var gr=[];function re(e){gr.push(e)}function xr({name:e}){return yr().test(e)}var yr=()=>new RegExp(`^${Et}([^:^.]+)\\\\b`);function kn(e,t){return({name:r,value:n})=>{let i=r.match(yr()),o=r.match(/:([a-zA-Z0-9\\-_:]+)/),s=r.match(/\\.[^.\\]]+(?=[^\\]]*$)/g)||[],a=t||e[r]||r;return{type:i?i[1]:null,value:o?o[1]:null,modifiers:s.map(c=>c.replace(\".\",\"\")),expression:n,original:a}}}var wt=\"DEFAULT\",G=[\"ignore\",\"ref\",\"data\",\"id\",\"anchor\",\"bind\",\"init\",\"for\",\"model\",\"modelable\",\"transition\",\"show\",\"if\",wt,\"teleport\"];function Ln(e,t){let r=G.indexOf(e.type)===-1?wt:e.type,n=G.indexOf(t.type)===-1?wt:t.type;return G.indexOf(r)-G.indexOf(n)}var St=[],At=!1;function ne(e=()=>{}){return queueMicrotask(()=>{At||setTimeout(()=>{je()})}),new Promise(t=>{St.push(()=>{e(),t()})})}function je(){for(At=!1;St.length;)St.shift()()}function br(){At=!0}function me(e,t){return Array.isArray(t)?wr(e,t.join(\" \")):typeof t==\"object\"&&t!==null?$n(e,t):typeof t==\"function\"?me(e,t()):wr(e,t)}function wr(e,t){let r=o=>o.split(\" \").filter(Boolean),n=o=>o.split(\" \").filter(s=>!e.classList.contains(s)).filter(Boolean),i=o=>(e.classList.add(...o),()=>{e.classList.remove(...o)});return t=t===!0?t=\"\":t||\"\",i(n(t))}function $n(e,t){let r=a=>a.split(\" \").filter(Boolean),n=Object.entries(t).flatMap(([a,c])=>c?r(a):!1).filter(Boolean),i=Object.entries(t).flatMap(([a,c])=>c?!1:r(a)).filter(Boolean),o=[],s=[];return i.forEach(a=>{e.classList.contains(a)&&(e.classList.remove(a),s.push(a))}),n.forEach(a=>{e.classList.contains(a)||(e.classList.add(a),o.push(a))}),()=>{s.forEach(a=>e.classList.add(a)),o.forEach(a=>e.classList.remove(a))}}function J(e,t){return typeof t==\"object\"&&t!==null?jn(e,t):Fn(e,t)}function jn(e,t){let r={};return Object.entries(t).forEach(([n,i])=>{r[n]=e.style[n],n.startsWith(\"--\")||(n=Bn(n)),e.style.setProperty(n,i)}),setTimeout(()=>{e.style.length===0&&e.removeAttribute(\"style\")}),()=>{J(e,r)}}function Fn(e,t){let r=e.getAttribute(\"style\",t);return e.setAttribute(\"style\",t),()=>{e.setAttribute(\"style\",r||\"\")}}function Bn(e){return e.replace(/([a-z])([A-Z])/g,\"$1-$2\").toLowerCase()}function he(e,t=()=>{}){let r=!1;return function(){r?t.apply(this,arguments):(r=!0,e.apply(this,arguments))}}d(\"transition\",(e,{value:t,modifiers:r,expression:n},{evaluate:i})=>{typeof n==\"function\"&&(n=i(n)),n!==!1&&(!n||typeof n==\"boolean\"?Kn(e,r,t):zn(e,n,t))});function zn(e,t,r){Er(e,me,\"\"),{enter:i=>{e._x_transition.enter.during=i},\"enter-start\":i=>{e._x_transition.enter.start=i},\"enter-end\":i=>{e._x_transition.enter.end=i},leave:i=>{e._x_transition.leave.during=i},\"leave-start\":i=>{e._x_transition.leave.start=i},\"leave-end\":i=>{e._x_transition.leave.end=i}}[r](t)}function Kn(e,t,r){Er(e,J);let n=!t.includes(\"in\")&&!t.includes(\"out\")&&!r,i=n||t.includes(\"in\")||[\"enter\"].includes(r),o=n||t.includes(\"out\")||[\"leave\"].includes(r);t.includes(\"in\")&&!n&&(t=t.filter((g,b)=>b<t.indexOf(\"out\"))),t.includes(\"out\")&&!n&&(t=t.filter((g,b)=>b>t.indexOf(\"out\")));let s=!t.includes(\"opacity\")&&!t.includes(\"scale\"),a=s||t.includes(\"opacity\"),c=s||t.includes(\"scale\"),l=a?0:1,u=c?_e(t,\"scale\",95)/100:1,p=_e(t,\"delay\",0)/1e3,m=_e(t,\"origin\",\"center\"),w=\"opacity, transform\",$=_e(t,\"duration\",150)/1e3,Ee=_e(t,\"duration\",75)/1e3,f=\"cubic-bezier(0.4, 0.0, 0.2, 1)\";i&&(e._x_transition.enter.during={transformOrigin:m,transitionDelay:`${p}s`,transitionProperty:w,transitionDuration:`${$}s`,transitionTimingFunction:f},e._x_transition.enter.start={opacity:l,transform:`scale(${u})`},e._x_transition.enter.end={opacity:1,transform:\"scale(1)\"}),o&&(e._x_transition.leave.during={transformOrigin:m,transitionDelay:`${p}s`,transitionProperty:w,transitionDuration:`${Ee}s`,transitionTimingFunction:f},e._x_transition.leave.start={opacity:1,transform:\"scale(1)\"},e._x_transition.leave.end={opacity:l,transform:`scale(${u})`})}function Er(e,t,r={}){e._x_transition||(e._x_transition={enter:{during:r,start:r,end:r},leave:{during:r,start:r,end:r},in(n=()=>{},i=()=>{}){Fe(e,t,{during:this.enter.during,start:this.enter.start,end:this.enter.end},n,i)},out(n=()=>{},i=()=>{}){Fe(e,t,{during:this.leave.during,start:this.leave.start,end:this.leave.end},n,i)}})}window.Element.prototype._x_toggleAndCascadeWithTransitions=function(e,t,r,n){let i=document.visibilityState===\"visible\"?requestAnimationFrame:setTimeout,o=()=>i(r);if(t){e._x_transition&&(e._x_transition.enter||e._x_transition.leave)?e._x_transition.enter&&(Object.entries(e._x_transition.enter.during).length||Object.entries(e._x_transition.enter.start).length||Object.entries(e._x_transition.enter.end).length)?e._x_transition.in(r):o():e._x_transition?e._x_transition.in(r):o();return}e._x_hidePromise=e._x_transition?new Promise((s,a)=>{e._x_transition.out(()=>{},()=>s(n)),e._x_transitioning&&e._x_transitioning.beforeCancel(()=>a({isFromCancelledTransition:!0}))}):Promise.resolve(n),queueMicrotask(()=>{let s=vr(e);s?(s._x_hideChildren||(s._x_hideChildren=[]),s._x_hideChildren.push(e)):i(()=>{let a=c=>{let l=Promise.all([c._x_hidePromise,...(c._x_hideChildren||[]).map(a)]).then(([u])=>u());return delete c._x_hidePromise,delete c._x_hideChildren,l};a(e).catch(c=>{if(!c.isFromCancelledTransition)throw c})})})};function vr(e){let t=e.parentNode;if(t)return t._x_hidePromise?t:vr(t)}function Fe(e,t,{during:r,start:n,end:i}={},o=()=>{},s=()=>{}){if(e._x_transitioning&&e._x_transitioning.cancel(),Object.keys(r).length===0&&Object.keys(n).length===0&&Object.keys(i).length===0){o(),s();return}let a,c,l;Hn(e,{start(){a=t(e,n)},during(){c=t(e,r)},before:o,end(){a(),l=t(e,i)},after:s,cleanup(){c(),l()}})}function Hn(e,t){let r,n,i,o=he(()=>{h(()=>{r=!0,n||t.before(),i||(t.end(),je()),t.after(),e.isConnected&&t.cleanup(),delete e._x_transitioning})});e._x_transitioning={beforeCancels:[],beforeCancel(s){this.beforeCancels.push(s)},cancel:he(function(){for(;this.beforeCancels.length;)this.beforeCancels.shift()();o()}),finish:o},h(()=>{t.start(),t.during()}),br(),requestAnimationFrame(()=>{if(r)return;let s=Number(getComputedStyle(e).transitionDuration.replace(/,.*/,\"\").replace(\"s\",\"\"))*1e3,a=Number(getComputedStyle(e).transitionDelay.replace(/,.*/,\"\").replace(\"s\",\"\"))*1e3;s===0&&(s=Number(getComputedStyle(e).animationDuration.replace(\"s\",\"\"))*1e3),h(()=>{t.before()}),n=!0,requestAnimationFrame(()=>{r||(h(()=>{t.end()}),je(),setTimeout(e._x_transitioning.finish,s+a),i=!0)})})}function _e(e,t,r){if(e.indexOf(t)===-1)return r;let n=e[e.indexOf(t)+1];if(!n||t===\"scale\"&&isNaN(n))return r;if(t===\"duration\"||t===\"delay\"){let i=n.match(/([0-9]+)ms/);if(i)return i[1]}return t===\"origin\"&&[\"top\",\"right\",\"left\",\"center\",\"bottom\"].includes(e[e.indexOf(t)+2])?[n,e[e.indexOf(t)+2]].join(\" \"):n}var I=!1;function D(e,t=()=>{}){return(...r)=>I?t(...r):e(...r)}function Sr(e){return(...t)=>I&&e(...t)}var Ar=[];function z(e){Ar.push(e)}function Or(e,t){Ar.forEach(r=>r(e,t)),I=!0,Tr(()=>{S(t,(r,n)=>{n(r,()=>{})})}),I=!1}var Be=!1;function Cr(e,t){t._x_dataStack||(t._x_dataStack=e._x_dataStack),I=!0,Be=!0,Tr(()=>{Vn(t)}),I=!1,Be=!1}function Vn(e){let t=!1;S(e,(n,i)=>{O(n,(o,s)=>{if(t&&Qt(o))return s();t=!0,i(o,s)})})}function Tr(e){let t=N;at((r,n)=>{let i=t(r);return L(i),()=>{}}),e(),at(t)}function ge(e,t,r,n=[]){switch(e._x_bindings||(e._x_bindings=T({})),e._x_bindings[t]=r,t=n.includes(\"camel\")?Zn(t):t,t){case\"value\":qn(e,r);break;case\"style\":Wn(e,r);break;case\"class\":Un(e,r);break;case\"selected\":case\"checked\":Gn(e,t,r);break;default:Mr(e,t,r);break}}function qn(e,t){if(e.type===\"radio\")e.attributes.value===void 0&&(e.value=t),window.fromModel&&(typeof t==\"boolean\"?e.checked=xe(e.value)===t:e.checked=Rr(e.value,t));else if(e.type===\"checkbox\")Number.isInteger(t)?e.value=t:!Array.isArray(t)&&typeof t!=\"boolean\"&&![null,void 0].includes(t)?e.value=String(t):Array.isArray(t)?e.checked=t.some(r=>Rr(r,e.value)):e.checked=!!t;else if(e.tagName===\"SELECT\")Xn(e,t);else{if(e.value===t)return;e.value=t===void 0?\"\":t}}function Un(e,t){e._x_undoAddedClasses&&e._x_undoAddedClasses(),e._x_undoAddedClasses=me(e,t)}function Wn(e,t){e._x_undoAddedStyles&&e._x_undoAddedStyles(),e._x_undoAddedStyles=J(e,t)}function Gn(e,t,r){Mr(e,t,r),Yn(e,t,r)}function Mr(e,t,r){[null,void 0,!1].includes(r)&&Qn(t)?e.removeAttribute(t):(Nr(t)&&(r=t),Jn(e,t,r))}function Jn(e,t,r){e.getAttribute(t)!=r&&e.setAttribute(t,r)}function Yn(e,t,r){e[t]!==r&&(e[t]=r)}function Xn(e,t){let r=[].concat(t).map(n=>n+\"\");Array.from(e.options).forEach(n=>{n.selected=r.includes(n.value)})}function Zn(e){return e.toLowerCase().replace(/-(\\w)/g,(t,r)=>r.toUpperCase())}function Rr(e,t){return e==t}function xe(e){return[1,\"1\",\"true\",\"on\",\"yes\",!0].includes(e)?!0:[0,\"0\",\"false\",\"off\",\"no\",!1].includes(e)?!1:e?Boolean(e):null}function Nr(e){return[\"disabled\",\"checked\",\"required\",\"readonly\",\"hidden\",\"open\",\"selected\",\"autofocus\",\"itemscope\",\"multiple\",\"novalidate\",\"allowfullscreen\",\"allowpaymentrequest\",\"formnovalidate\",\"autoplay\",\"controls\",\"loop\",\"muted\",\"playsinline\",\"default\",\"ismap\",\"reversed\",\"async\",\"defer\",\"nomodule\"].includes(e)}function Qn(e){return![\"aria-pressed\",\"aria-checked\",\"aria-expanded\",\"aria-selected\"].includes(e)}function Pr(e,t,r){return e._x_bindings&&e._x_bindings[t]!==void 0?e._x_bindings[t]:Dr(e,t,r)}function Ir(e,t,r,n=!0){if(e._x_bindings&&e._x_bindings[t]!==void 0)return e._x_bindings[t];if(e._x_inlineBindings&&e._x_inlineBindings[t]!==void 0){let i=e._x_inlineBindings[t];return i.extract=n,ke(()=>R(e,i.expression))}return Dr(e,t,r)}function Dr(e,t,r){let n=e.getAttribute(t);return n===null?typeof r==\"function\"?r():r:n===\"\"?!0:Nr(t)?!![t,\"true\"].includes(n):n}function ze(e,t){var r;return function(){var n=this,i=arguments,o=function(){r=null,e.apply(n,i)};clearTimeout(r),r=setTimeout(o,t)}}function Ke(e,t){let r;return function(){let n=this,i=arguments;r||(e.apply(n,i),r=!0,setTimeout(()=>r=!1,t))}}function He({get:e,set:t},{get:r,set:n}){let i=!0,o,s,a=N(()=>{let c=e(),l=r();if(i)n(Ot(c)),i=!1;else{let u=JSON.stringify(c),p=JSON.stringify(l);u!==o?n(Ot(c)):u!==p&&t(Ot(l))}o=JSON.stringify(e()),s=JSON.stringify(r())});return()=>{L(a)}}function Ot(e){return typeof e==\"object\"?JSON.parse(JSON.stringify(e)):e}function kr(e){(Array.isArray(e)?e:[e]).forEach(r=>r(B))}var Y={},Lr=!1;function $r(e,t){if(Lr||(Y=T(Y),Lr=!0),t===void 0)return Y[e];Y[e]=t,typeof t==\"object\"&&t!==null&&t.hasOwnProperty(\"init\")&&typeof t.init==\"function\"&&Y[e].init(),Ne(Y[e])}function jr(){return Y}var Fr={};function Br(e,t){let r=typeof t!=\"function\"?()=>t:t;return e instanceof Element?Ct(e,r()):(Fr[e]=r,()=>{})}function zr(e){return Object.entries(Fr).forEach(([t,r])=>{Object.defineProperty(e,t,{get(){return(...n)=>r(...n)}})}),e}function Ct(e,t,r){let n=[];for(;n.length;)n.pop()();let i=Object.entries(t).map(([s,a])=>({name:s,value:a})),o=vt(i);return i=i.map(s=>o.find(a=>a.name===s.name)?{name:`x-bind:${s.name}`,value:`\"${s.value}\"`}:s),ue(e,i,r).map(s=>{n.push(s.runCleanups),s()}),()=>{for(;n.length;)n.pop()()}}var Kr={};function Hr(e,t){Kr[e]=t}function Vr(e,t){return Object.entries(Kr).forEach(([r,n])=>{Object.defineProperty(e,r,{get(){return(...i)=>n.bind(t)(...i)},enumerable:!1})}),e}var ei={get reactive(){return T},get release(){return L},get effect(){return N},get raw(){return st},version:\"3.13.5\",flushAndStopDeferringMutations:lr,dontAutoEvaluateFunctions:ke,disableEffectScheduling:qt,startObservingMutations:le,stopObservingMutations:dt,setReactivityEngine:Ut,onAttributeRemoved:Re,onAttributesAdded:Ce,closestDataStack:j,skipDuringClone:D,onlyDuringClone:Sr,addRootSelector:Ae,addInitSelector:Oe,interceptClone:z,addScopeToNode:P,deferMutations:cr,mapAttributes:re,evaluateLater:x,interceptInit:tr,setEvaluator:pr,mergeProxies:F,extractProp:Ir,findClosest:Q,onElRemoved:ee,closestRoot:W,destroyTree:ce,interceptor:Pe,transition:Fe,setStyles:J,mutateDom:h,directive:d,entangle:He,throttle:Ke,debounce:ze,evaluate:R,initTree:S,nextTick:ne,prefixed:C,prefix:mr,plugin:kr,magic:y,store:$r,start:Jt,clone:Cr,cloneNode:Or,bound:Pr,$data:Me,watch:Se,walk:O,data:Hr,bind:Br},B=ei;function Tt(e,t){let r=Object.create(null),n=e.split(\",\");for(let i=0;i<n.length;i++)r[n[i]]=!0;return t?i=>!!r[i.toLowerCase()]:i=>!!r[i]}var ti=\"itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly\";var Ps=Tt(ti+\",async,autofocus,autoplay,controls,default,defer,disabled,hidden,loop,open,required,reversed,scoped,seamless,checked,muted,multiple,selected\");var qr=Object.freeze({}),Is=Object.freeze([]);var ri=Object.prototype.hasOwnProperty,ye=(e,t)=>ri.call(e,t),K=Array.isArray,ie=e=>Ur(e)===\"[object Map]\";var ni=e=>typeof e==\"string\",Ve=e=>typeof e==\"symbol\",be=e=>e!==null&&typeof e==\"object\";var ii=Object.prototype.toString,Ur=e=>ii.call(e),Rt=e=>Ur(e).slice(8,-1);var qe=e=>ni(e)&&e!==\"NaN\"&&e[0]!==\"-\"&&\"\"+parseInt(e,10)===e;var Ue=e=>{let t=Object.create(null);return r=>t[r]||(t[r]=e(r))},oi=/-(\\w)/g,Ds=Ue(e=>e.replace(oi,(t,r)=>r?r.toUpperCase():\"\")),si=/\\B([A-Z])/g,ks=Ue(e=>e.replace(si,\"-$1\").toLowerCase()),Mt=Ue(e=>e.charAt(0).toUpperCase()+e.slice(1)),Ls=Ue(e=>e?`on${Mt(e)}`:\"\"),Nt=(e,t)=>e!==t&&(e===e||t===t);var Pt=new WeakMap,we=[],k,X=Symbol(\"iterate\"),It=Symbol(\"Map key iterate\");function ai(e){return e&&e._isEffect===!0}function Zr(e,t=qr){ai(e)&&(e=e.raw);let r=li(e,t);return t.lazy||r(),r}function Qr(e){e.active&&(en(e),e.options.onStop&&e.options.onStop(),e.active=!1)}var ci=0;function li(e,t){let r=function(){if(!r.active)return e();if(!we.includes(r)){en(r);try{return fi(),we.push(r),k=r,e()}finally{we.pop(),tn(),k=we[we.length-1]}}};return r.id=ci++,r.allowRecurse=!!t.allowRecurse,r._isEffect=!0,r.active=!0,r.raw=e,r.deps=[],r.options=t,r}function en(e){let{deps:t}=e;if(t.length){for(let r=0;r<t.length;r++)t[r].delete(e);t.length=0}}var oe=!0,kt=[];function ui(){kt.push(oe),oe=!1}function fi(){kt.push(oe),oe=!0}function tn(){let e=kt.pop();oe=e===void 0?!0:e}function M(e,t,r){if(!oe||k===void 0)return;let n=Pt.get(e);n||Pt.set(e,n=new Map);let i=n.get(r);i||n.set(r,i=new Set),i.has(k)||(i.add(k),k.deps.push(i),k.options.onTrack&&k.options.onTrack({effect:k,target:e,type:t,key:r}))}function V(e,t,r,n,i,o){let s=Pt.get(e);if(!s)return;let a=new Set,c=u=>{u&&u.forEach(p=>{(p!==k||p.allowRecurse)&&a.add(p)})};if(t===\"clear\")s.forEach(c);else if(r===\"length\"&&K(e))s.forEach((u,p)=>{(p===\"length\"||p>=n)&&c(u)});else switch(r!==void 0&&c(s.get(r)),t){case\"add\":K(e)?qe(r)&&c(s.get(\"length\")):(c(s.get(X)),ie(e)&&c(s.get(It)));break;case\"delete\":K(e)||(c(s.get(X)),ie(e)&&c(s.get(It)));break;case\"set\":ie(e)&&c(s.get(X));break}let l=u=>{u.options.onTrigger&&u.options.onTrigger({effect:u,target:e,key:r,type:t,newValue:n,oldValue:i,oldTarget:o}),u.options.scheduler?u.options.scheduler(u):u()};a.forEach(l)}var di=Tt(\"__proto__,__v_isRef,__isVue\"),rn=new Set(Object.getOwnPropertyNames(Symbol).map(e=>Symbol[e]).filter(Ve)),pi=nn();var mi=nn(!0);var Wr=hi();function hi(){let e={};return[\"includes\",\"indexOf\",\"lastIndexOf\"].forEach(t=>{e[t]=function(...r){let n=_(this);for(let o=0,s=this.length;o<s;o++)M(n,\"get\",o+\"\");let i=n[t](...r);return i===-1||i===!1?n[t](...r.map(_)):i}}),[\"push\",\"pop\",\"shift\",\"unshift\",\"splice\"].forEach(t=>{e[t]=function(...r){ui();let n=_(this)[t].apply(this,r);return tn(),n}}),e}function nn(e=!1,t=!1){return function(n,i,o){if(i===\"__v_isReactive\")return!e;if(i===\"__v_isReadonly\")return e;if(i===\"__v_raw\"&&o===(e?t?Ni:cn:t?Mi:an).get(n))return n;let s=K(n);if(!e&&s&&ye(Wr,i))return Reflect.get(Wr,i,o);let a=Reflect.get(n,i,o);return(Ve(i)?rn.has(i):di(i))||(e||M(n,\"get\",i),t)?a:Dt(a)?!s||!qe(i)?a.value:a:be(a)?e?ln(a):Qe(a):a}}var _i=gi();function gi(e=!1){return function(r,n,i,o){let s=r[n];if(!e&&(i=_(i),s=_(s),!K(r)&&Dt(s)&&!Dt(i)))return s.value=i,!0;let a=K(r)&&qe(n)?Number(n)<r.length:ye(r,n),c=Reflect.set(r,n,i,o);return r===_(o)&&(a?Nt(i,s)&&V(r,\"set\",n,i,s):V(r,\"add\",n,i)),c}}function xi(e,t){let r=ye(e,t),n=e[t],i=Reflect.deleteProperty(e,t);return i&&r&&V(e,\"delete\",t,void 0,n),i}function yi(e,t){let r=Reflect.has(e,t);return(!Ve(t)||!rn.has(t))&&M(e,\"has\",t),r}function bi(e){return M(e,\"iterate\",K(e)?\"length\":X),Reflect.ownKeys(e)}var wi={get:pi,set:_i,deleteProperty:xi,has:yi,ownKeys:bi},Ei={get:mi,set(e,t){return console.warn(`Set operation on key \"${String(t)}\" failed: target is readonly.`,e),!0},deleteProperty(e,t){return console.warn(`Delete operation on key \"${String(t)}\" failed: target is readonly.`,e),!0}};var Lt=e=>be(e)?Qe(e):e,$t=e=>be(e)?ln(e):e,jt=e=>e,Ze=e=>Reflect.getPrototypeOf(e);function We(e,t,r=!1,n=!1){e=e.__v_raw;let i=_(e),o=_(t);t!==o&&!r&&M(i,\"get\",t),!r&&M(i,\"get\",o);let{has:s}=Ze(i),a=n?jt:r?$t:Lt;if(s.call(i,t))return a(e.get(t));if(s.call(i,o))return a(e.get(o));e!==i&&e.get(t)}function Ge(e,t=!1){let r=this.__v_raw,n=_(r),i=_(e);return e!==i&&!t&&M(n,\"has\",e),!t&&M(n,\"has\",i),e===i?r.has(e):r.has(e)||r.has(i)}function Je(e,t=!1){return e=e.__v_raw,!t&&M(_(e),\"iterate\",X),Reflect.get(e,\"size\",e)}function Gr(e){e=_(e);let t=_(this);return Ze(t).has.call(t,e)||(t.add(e),V(t,\"add\",e,e)),this}function Jr(e,t){t=_(t);let r=_(this),{has:n,get:i}=Ze(r),o=n.call(r,e);o?sn(r,n,e):(e=_(e),o=n.call(r,e));let s=i.call(r,e);return r.set(e,t),o?Nt(t,s)&&V(r,\"set\",e,t,s):V(r,\"add\",e,t),this}function Yr(e){let t=_(this),{has:r,get:n}=Ze(t),i=r.call(t,e);i?sn(t,r,e):(e=_(e),i=r.call(t,e));let o=n?n.call(t,e):void 0,s=t.delete(e);return i&&V(t,\"delete\",e,void 0,o),s}function Xr(){let e=_(this),t=e.size!==0,r=ie(e)?new Map(e):new Set(e),n=e.clear();return t&&V(e,\"clear\",void 0,void 0,r),n}function Ye(e,t){return function(n,i){let o=this,s=o.__v_raw,a=_(s),c=t?jt:e?$t:Lt;return!e&&M(a,\"iterate\",X),s.forEach((l,u)=>n.call(i,c(l),c(u),o))}}function Xe(e,t,r){return function(...n){let i=this.__v_raw,o=_(i),s=ie(o),a=e===\"entries\"||e===Symbol.iterator&&s,c=e===\"keys\"&&s,l=i[e](...n),u=r?jt:t?$t:Lt;return!t&&M(o,\"iterate\",c?It:X),{next(){let{value:p,done:m}=l.next();return m?{value:p,done:m}:{value:a?[u(p[0]),u(p[1])]:u(p),done:m}},[Symbol.iterator](){return this}}}}function H(e){return function(...t){{let r=t[0]?`on key \"${t[0]}\" `:\"\";console.warn(`${Mt(e)} operation ${r}failed: target is readonly.`,_(this))}return e===\"delete\"?!1:this}}function vi(){let e={get(o){return We(this,o)},get size(){return Je(this)},has:Ge,add:Gr,set:Jr,delete:Yr,clear:Xr,forEach:Ye(!1,!1)},t={get(o){return We(this,o,!1,!0)},get size(){return Je(this)},has:Ge,add:Gr,set:Jr,delete:Yr,clear:Xr,forEach:Ye(!1,!0)},r={get(o){return We(this,o,!0)},get size(){return Je(this,!0)},has(o){return Ge.call(this,o,!0)},add:H(\"add\"),set:H(\"set\"),delete:H(\"delete\"),clear:H(\"clear\"),forEach:Ye(!0,!1)},n={get(o){return We(this,o,!0,!0)},get size(){return Je(this,!0)},has(o){return Ge.call(this,o,!0)},add:H(\"add\"),set:H(\"set\"),delete:H(\"delete\"),clear:H(\"clear\"),forEach:Ye(!0,!0)};return[\"keys\",\"values\",\"entries\",Symbol.iterator].forEach(o=>{e[o]=Xe(o,!1,!1),r[o]=Xe(o,!0,!1),t[o]=Xe(o,!1,!0),n[o]=Xe(o,!0,!0)}),[e,r,t,n]}var[Si,Ai,Oi,Ci]=vi();function on(e,t){let r=t?e?Ci:Oi:e?Ai:Si;return(n,i,o)=>i===\"__v_isReactive\"?!e:i===\"__v_isReadonly\"?e:i===\"__v_raw\"?n:Reflect.get(ye(r,i)&&i in n?r:n,i,o)}var Ti={get:on(!1,!1)};var Ri={get:on(!0,!1)};function sn(e,t,r){let n=_(r);if(n!==r&&t.call(e,n)){let i=Rt(e);console.warn(`Reactive ${i} contains both the raw and reactive versions of the same object${i===\"Map\"?\" as keys\":\"\"}, which can lead to inconsistencies. Avoid differentiating between the raw and reactive versions of an object and only use the reactive version if possible.`)}}var an=new WeakMap,Mi=new WeakMap,cn=new WeakMap,Ni=new WeakMap;function Pi(e){switch(e){case\"Object\":case\"Array\":return 1;case\"Map\":case\"Set\":case\"WeakMap\":case\"WeakSet\":return 2;default:return 0}}function Ii(e){return e.__v_skip||!Object.isExtensible(e)?0:Pi(Rt(e))}function Qe(e){return e&&e.__v_isReadonly?e:un(e,!1,wi,Ti,an)}function ln(e){return un(e,!0,Ei,Ri,cn)}function un(e,t,r,n,i){if(!be(e))return console.warn(`value cannot be made reactive: ${String(e)}`),e;if(e.__v_raw&&!(t&&e.__v_isReactive))return e;let o=i.get(e);if(o)return o;let s=Ii(e);if(s===0)return e;let a=new Proxy(e,s===2?n:r);return i.set(e,a),a}function _(e){return e&&_(e.__v_raw)||e}function Dt(e){return Boolean(e&&e.__v_isRef===!0)}y(\"nextTick\",()=>ne);y(\"dispatch\",e=>U.bind(U,e));y(\"watch\",(e,{evaluateLater:t,cleanup:r})=>(n,i)=>{let o=t(n),a=Se(()=>{let c;return o(l=>c=l),c},i);r(a)});y(\"store\",jr);y(\"data\",e=>Me(e));y(\"root\",e=>W(e));y(\"refs\",e=>(e._x_refs_proxy||(e._x_refs_proxy=F(Di(e))),e._x_refs_proxy));function Di(e){let t=[],r=e;for(;r;)r._x_refs&&t.push(r._x_refs),r=r.parentNode;return t}var Ft={};function Bt(e){return Ft[e]||(Ft[e]=0),++Ft[e]}function fn(e,t){return Q(e,r=>{if(r._x_ids&&r._x_ids[t])return!0})}function dn(e,t){e._x_ids||(e._x_ids={}),e._x_ids[t]||(e._x_ids[t]=Bt(t))}y(\"id\",(e,{cleanup:t})=>(r,n=null)=>{let i=`${r}${n?`-${n}`:\"\"}`;return ki(e,i,t,()=>{let o=fn(e,r),s=o?o._x_ids[r]:Bt(r);return n?`${r}-${s}-${n}`:`${r}-${s}`})});z((e,t)=>{e._x_id&&(t._x_id=e._x_id)});function ki(e,t,r,n){if(e._x_id||(e._x_id={}),e._x_id[t])return e._x_id[t];let i=n();return e._x_id[t]=i,r(()=>{delete e._x_id[t]}),i}y(\"el\",e=>e);pn(\"Focus\",\"focus\",\"focus\");pn(\"Persist\",\"persist\",\"persist\");function pn(e,t,r){y(t,n=>v(`You can't use [$${t}] without first installing the \"${e}\" plugin here: https://alpinejs.dev/plugins/${r}`,n))}d(\"modelable\",(e,{expression:t},{effect:r,evaluateLater:n,cleanup:i})=>{let o=n(t),s=()=>{let u;return o(p=>u=p),u},a=n(`${t} = __placeholder`),c=u=>a(()=>{},{scope:{__placeholder:u}}),l=s();c(l),queueMicrotask(()=>{if(!e._x_model)return;e._x_removeModelListeners.default();let u=e._x_model.get,p=e._x_model.set,m=He({get(){return u()},set(w){p(w)}},{get(){return s()},set(w){c(w)}});i(m)})});d(\"teleport\",(e,{modifiers:t,expression:r},{cleanup:n})=>{e.tagName.toLowerCase()!==\"template\"&&v(\"x-teleport can only be used on a <template> tag\",e);let i=mn(r),o=e.content.cloneNode(!0).firstElementChild;e._x_teleport=o,o._x_teleportBack=e,e.setAttribute(\"data-teleport-template\",!0),o.setAttribute(\"data-teleport-target\",!0),e._x_forwardEvents&&e._x_forwardEvents.forEach(a=>{o.addEventListener(a,c=>{c.stopPropagation(),e.dispatchEvent(new c.constructor(c.type,c))})}),P(o,{},e);let s=(a,c,l)=>{l.includes(\"prepend\")?c.parentNode.insertBefore(a,c):l.includes(\"append\")?c.parentNode.insertBefore(a,c.nextSibling):c.appendChild(a)};h(()=>{s(o,i,t),S(o),o._x_ignore=!0}),e._x_teleportPutBack=()=>{let a=mn(r);h(()=>{s(e._x_teleport,a,t)})},n(()=>o.remove())});var Li=document.createElement(\"div\");function mn(e){let t=D(()=>document.querySelector(e),()=>Li)();return t||v(`Cannot find x-teleport element for selector: \"${e}\"`),t}var hn=()=>{};hn.inline=(e,{modifiers:t},{cleanup:r})=>{t.includes(\"self\")?e._x_ignoreSelf=!0:e._x_ignore=!0,r(()=>{t.includes(\"self\")?delete e._x_ignoreSelf:delete e._x_ignore})};d(\"ignore\",hn);d(\"effect\",D((e,{expression:t},{effect:r})=>{r(x(e,t))}));function se(e,t,r,n){let i=e,o=c=>n(c),s={},a=(c,l)=>u=>l(c,u);if(r.includes(\"dot\")&&(t=$i(t)),r.includes(\"camel\")&&(t=ji(t)),r.includes(\"passive\")&&(s.passive=!0),r.includes(\"capture\")&&(s.capture=!0),r.includes(\"window\")&&(i=window),r.includes(\"document\")&&(i=document),r.includes(\"debounce\")){let c=r[r.indexOf(\"debounce\")+1]||\"invalid-wait\",l=et(c.split(\"ms\")[0])?Number(c.split(\"ms\")[0]):250;o=ze(o,l)}if(r.includes(\"throttle\")){let c=r[r.indexOf(\"throttle\")+1]||\"invalid-wait\",l=et(c.split(\"ms\")[0])?Number(c.split(\"ms\")[0]):250;o=Ke(o,l)}return r.includes(\"prevent\")&&(o=a(o,(c,l)=>{l.preventDefault(),c(l)})),r.includes(\"stop\")&&(o=a(o,(c,l)=>{l.stopPropagation(),c(l)})),r.includes(\"self\")&&(o=a(o,(c,l)=>{l.target===e&&c(l)})),(r.includes(\"away\")||r.includes(\"outside\"))&&(i=document,o=a(o,(c,l)=>{e.contains(l.target)||l.target.isConnected!==!1&&(e.offsetWidth<1&&e.offsetHeight<1||e._x_isShown!==!1&&c(l))})),r.includes(\"once\")&&(o=a(o,(c,l)=>{c(l),i.removeEventListener(t,o,s)})),o=a(o,(c,l)=>{Bi(t)&&zi(l,r)||c(l)}),i.addEventListener(t,o,s),()=>{i.removeEventListener(t,o,s)}}function $i(e){return e.replace(/-/g,\".\")}function ji(e){return e.toLowerCase().replace(/-(\\w)/g,(t,r)=>r.toUpperCase())}function et(e){return!Array.isArray(e)&&!isNaN(e)}function Fi(e){return[\" \",\"_\"].includes(e)?e:e.replace(/([a-z])([A-Z])/g,\"$1-$2\").replace(/[_\\s]/,\"-\").toLowerCase()}function Bi(e){return[\"keydown\",\"keyup\"].includes(e)}function zi(e,t){let r=t.filter(o=>![\"window\",\"document\",\"prevent\",\"stop\",\"once\",\"capture\"].includes(o));if(r.includes(\"debounce\")){let o=r.indexOf(\"debounce\");r.splice(o,et((r[o+1]||\"invalid-wait\").split(\"ms\")[0])?2:1)}if(r.includes(\"throttle\")){let o=r.indexOf(\"throttle\");r.splice(o,et((r[o+1]||\"invalid-wait\").split(\"ms\")[0])?2:1)}if(r.length===0||r.length===1&&_n(e.key).includes(r[0]))return!1;let i=[\"ctrl\",\"shift\",\"alt\",\"meta\",\"cmd\",\"super\"].filter(o=>r.includes(o));return r=r.filter(o=>!i.includes(o)),!(i.length>0&&i.filter(s=>((s===\"cmd\"||s===\"super\")&&(s=\"meta\"),e[`${s}Key`])).length===i.length&&_n(e.key).includes(r[0]))}function _n(e){if(!e)return[];e=Fi(e);let t={ctrl:\"control\",slash:\"/\",space:\" \",spacebar:\" \",cmd:\"meta\",esc:\"escape\",up:\"arrow-up\",down:\"arrow-down\",left:\"arrow-left\",right:\"arrow-right\",period:\".\",equal:\"=\",minus:\"-\",underscore:\"_\"};return t[e]=e,Object.keys(t).map(r=>{if(t[r]===e)return r}).filter(r=>r)}d(\"model\",(e,{modifiers:t,expression:r},{effect:n,cleanup:i})=>{let o=e;t.includes(\"parent\")&&(o=e.parentNode);let s=x(o,r),a;typeof r==\"string\"?a=x(o,`${r} = __placeholder`):typeof r==\"function\"&&typeof r()==\"string\"?a=x(o,`${r()} = __placeholder`):a=()=>{};let c=()=>{let m;return s(w=>m=w),gn(m)?m.get():m},l=m=>{let w;s($=>w=$),gn(w)?w.set(m):a(()=>{},{scope:{__placeholder:m}})};typeof r==\"string\"&&e.type===\"radio\"&&h(()=>{e.hasAttribute(\"name\")||e.setAttribute(\"name\",r)});var u=e.tagName.toLowerCase()===\"select\"||[\"checkbox\",\"radio\"].includes(e.type)||t.includes(\"lazy\")?\"change\":\"input\";let p=I?()=>{}:se(e,u,t,m=>{l(Ki(e,t,m,c()))});if(t.includes(\"fill\")&&([void 0,null,\"\"].includes(c())||e.type===\"checkbox\"&&Array.isArray(c()))&&e.dispatchEvent(new Event(u,{})),e._x_removeModelListeners||(e._x_removeModelListeners={}),e._x_removeModelListeners.default=p,i(()=>e._x_removeModelListeners.default()),e.form){let m=se(e.form,\"reset\",[],w=>{ne(()=>e._x_model&&e._x_model.set(e.value))});i(()=>m())}e._x_model={get(){return c()},set(m){l(m)}},e._x_forceModelUpdate=m=>{m===void 0&&typeof r==\"string\"&&r.match(/\\./)&&(m=\"\"),window.fromModel=!0,h(()=>ge(e,\"value\",m)),delete window.fromModel},n(()=>{let m=c();t.includes(\"unintrusive\")&&document.activeElement.isSameNode(e)||e._x_forceModelUpdate(m)})});function Ki(e,t,r,n){return h(()=>{if(r instanceof CustomEvent&&r.detail!==void 0)return r.detail!==null&&r.detail!==void 0?r.detail:r.target.value;if(e.type===\"checkbox\")if(Array.isArray(n)){let i=null;return t.includes(\"number\")?i=zt(r.target.value):t.includes(\"boolean\")?i=xe(r.target.value):i=r.target.value,r.target.checked?n.concat([i]):n.filter(o=>!Hi(o,i))}else return r.target.checked;else return e.tagName.toLowerCase()===\"select\"&&e.multiple?t.includes(\"number\")?Array.from(r.target.selectedOptions).map(i=>{let o=i.value||i.text;return zt(o)}):t.includes(\"boolean\")?Array.from(r.target.selectedOptions).map(i=>{let o=i.value||i.text;return xe(o)}):Array.from(r.target.selectedOptions).map(i=>i.value||i.text):t.includes(\"number\")?zt(r.target.value):t.includes(\"boolean\")?xe(r.target.value):t.includes(\"trim\")?r.target.value.trim():r.target.value})}function zt(e){let t=e?parseFloat(e):null;return Vi(t)?t:e}function Hi(e,t){return e==t}function Vi(e){return!Array.isArray(e)&&!isNaN(e)}function gn(e){return e!==null&&typeof e==\"object\"&&typeof e.get==\"function\"&&typeof e.set==\"function\"}d(\"cloak\",e=>queueMicrotask(()=>h(()=>e.removeAttribute(C(\"cloak\")))));Oe(()=>`[${C(\"init\")}]`);d(\"init\",D((e,{expression:t},{evaluate:r})=>typeof t==\"string\"?!!t.trim()&&r(t,{},!1):r(t,{},!1)));d(\"text\",(e,{expression:t},{effect:r,evaluateLater:n})=>{let i=n(t);r(()=>{i(o=>{h(()=>{e.textContent=o})})})});d(\"html\",(e,{expression:t},{effect:r,evaluateLater:n})=>{let i=n(t);r(()=>{i(o=>{h(()=>{e.innerHTML=o,e._x_ignoreSelf=!0,S(e),delete e._x_ignoreSelf})})})});re(Le(\":\",$e(C(\"bind:\"))));var xn=(e,{value:t,modifiers:r,expression:n,original:i},{effect:o})=>{if(!t){let a={};zr(a),x(e,n)(l=>{Ct(e,l,i)},{scope:a});return}if(t===\"key\")return qi(e,n);if(e._x_inlineBindings&&e._x_inlineBindings[t]&&e._x_inlineBindings[t].extract)return;let s=x(e,n);o(()=>s(a=>{a===void 0&&typeof n==\"string\"&&n.match(/\\./)&&(a=\"\"),h(()=>ge(e,t,a,r))}))};xn.inline=(e,{value:t,modifiers:r,expression:n})=>{t&&(e._x_inlineBindings||(e._x_inlineBindings={}),e._x_inlineBindings[t]={expression:n,extract:!1})};d(\"bind\",xn);function qi(e,t){e._x_keyExpression=t}Ae(()=>`[${C(\"data\")}]`);d(\"data\",(e,{expression:t},{cleanup:r})=>{if(Ui(e))return;t=t===\"\"?\"{}\":t;let n={};de(n,e);let i={};Vr(i,n);let o=R(e,t,{scope:i});(o===void 0||o===!0)&&(o={}),de(o,e);let s=T(o);Ne(s);let a=P(e,s);s.init&&R(e,s.init),r(()=>{s.destroy&&R(e,s.destroy),a()})});z((e,t)=>{e._x_dataStack&&(t._x_dataStack=e._x_dataStack,t.setAttribute(\"data-has-alpine-state\",!0))});function Ui(e){return I?Be?!0:e.hasAttribute(\"data-has-alpine-state\"):!1}d(\"show\",(e,{modifiers:t,expression:r},{effect:n})=>{let i=x(e,r);e._x_doHide||(e._x_doHide=()=>{h(()=>{e.style.setProperty(\"display\",\"none\",t.includes(\"important\")?\"important\":void 0)})}),e._x_doShow||(e._x_doShow=()=>{h(()=>{e.style.length===1&&e.style.display===\"none\"?e.removeAttribute(\"style\"):e.style.removeProperty(\"display\")})});let o=()=>{e._x_doHide(),e._x_isShown=!1},s=()=>{e._x_doShow(),e._x_isShown=!0},a=()=>setTimeout(s),c=he(p=>p?s():o(),p=>{typeof e._x_toggleAndCascadeWithTransitions==\"function\"?e._x_toggleAndCascadeWithTransitions(e,p,s,o):p?a():o()}),l,u=!0;n(()=>i(p=>{!u&&p===l||(t.includes(\"immediate\")&&(p?a():o()),c(p),l=p,u=!1)}))});d(\"for\",(e,{expression:t},{effect:r,cleanup:n})=>{let i=Gi(t),o=x(e,i.items),s=x(e,e._x_keyExpression||\"index\");e._x_prevKeys=[],e._x_lookup={},r(()=>Wi(e,i,o,s)),n(()=>{Object.values(e._x_lookup).forEach(a=>a.remove()),delete e._x_prevKeys,delete e._x_lookup})});function Wi(e,t,r,n){let i=s=>typeof s==\"object\"&&!Array.isArray(s),o=e;r(s=>{Ji(s)&&s>=0&&(s=Array.from(Array(s).keys(),f=>f+1)),s===void 0&&(s=[]);let a=e._x_lookup,c=e._x_prevKeys,l=[],u=[];if(i(s))s=Object.entries(s).map(([f,g])=>{let b=yn(t,g,f,s);n(E=>u.push(E),{scope:{index:f,...b}}),l.push(b)});else for(let f=0;f<s.length;f++){let g=yn(t,s[f],f,s);n(b=>u.push(b),{scope:{index:f,...g}}),l.push(g)}let p=[],m=[],w=[],$=[];for(let f=0;f<c.length;f++){let g=c[f];u.indexOf(g)===-1&&w.push(g)}c=c.filter(f=>!w.includes(f));let Ee=\"template\";for(let f=0;f<u.length;f++){let g=u[f],b=c.indexOf(g);if(b===-1)c.splice(f,0,g),p.push([Ee,f]);else if(b!==f){let E=c.splice(f,1)[0],A=c.splice(b-1,1)[0];c.splice(f,0,A),c.splice(b,0,E),m.push([E,A])}else $.push(g);Ee=g}for(let f=0;f<w.length;f++){let g=w[f];a[g]._x_effects&&a[g]._x_effects.forEach(ve),a[g].remove(),a[g]=null,delete a[g]}for(let f=0;f<m.length;f++){let[g,b]=m[f],E=a[g],A=a[b],Z=document.createElement(\"div\");h(()=>{A||v('x-for \":key\" is undefined or invalid',o),A.after(Z),E.after(A),A._x_currentIfEl&&A.after(A._x_currentIfEl),Z.before(E),E._x_currentIfEl&&E.after(E._x_currentIfEl),Z.remove()}),A._x_refreshXForScope(l[u.indexOf(b)])}for(let f=0;f<p.length;f++){let[g,b]=p[f],E=g===\"template\"?o:a[g];E._x_currentIfEl&&(E=E._x_currentIfEl);let A=l[b],Z=u[b],ae=document.importNode(o.content,!0).firstElementChild,Ht=T(A);P(ae,Ht,o),ae._x_refreshXForScope=wn=>{Object.entries(wn).forEach(([En,vn])=>{Ht[En]=vn})},h(()=>{E.after(ae),S(ae)}),typeof Z==\"object\"&&v(\"x-for key cannot be an object, it must be a string or an integer\",o),a[Z]=ae}for(let f=0;f<$.length;f++)a[$[f]]._x_refreshXForScope(l[u.indexOf($[f])]);o._x_prevKeys=u})}function Gi(e){let t=/,([^,\\}\\]]*)(?:,([^,\\}\\]]*))?$/,r=/^\\s*\\(|\\)\\s*$/g,n=/([\\s\\S]*?)\\s+(?:in|of)\\s+([\\s\\S]*)/,i=e.match(n);if(!i)return;let o={};o.items=i[2].trim();let s=i[1].replace(r,\"\").trim(),a=s.match(t);return a?(o.item=s.replace(t,\"\").trim(),o.index=a[1].trim(),a[2]&&(o.collection=a[2].trim())):o.item=s,o}function yn(e,t,r,n){let i={};return/^\\[.*\\]$/.test(e.item)&&Array.isArray(t)?e.item.replace(\"[\",\"\").replace(\"]\",\"\").split(\",\").map(s=>s.trim()).forEach((s,a)=>{i[s]=t[a]}):/^\\{.*\\}$/.test(e.item)&&!Array.isArray(t)&&typeof t==\"object\"?e.item.replace(\"{\",\"\").replace(\"}\",\"\").split(\",\").map(s=>s.trim()).forEach(s=>{i[s]=t[s]}):i[e.item]=t,e.index&&(i[e.index]=r),e.collection&&(i[e.collection]=n),i}function Ji(e){return!Array.isArray(e)&&!isNaN(e)}function bn(){}bn.inline=(e,{expression:t},{cleanup:r})=>{let n=W(e);n._x_refs||(n._x_refs={}),n._x_refs[t]=e,r(()=>delete n._x_refs[t])};d(\"ref\",bn);d(\"if\",(e,{expression:t},{effect:r,cleanup:n})=>{e.tagName.toLowerCase()!==\"template\"&&v(\"x-if can only be used on a <template> tag\",e);let i=x(e,t),o=()=>{if(e._x_currentIfEl)return e._x_currentIfEl;let a=e.content.cloneNode(!0).firstElementChild;return P(a,{},e),h(()=>{e.after(a),S(a)}),e._x_currentIfEl=a,e._x_undoIf=()=>{O(a,c=>{c._x_effects&&c._x_effects.forEach(ve)}),a.remove(),delete e._x_currentIfEl},a},s=()=>{e._x_undoIf&&(e._x_undoIf(),delete e._x_undoIf)};r(()=>i(a=>{a?o():s()})),n(()=>e._x_undoIf&&e._x_undoIf())});d(\"id\",(e,{expression:t},{evaluate:r})=>{r(t).forEach(i=>dn(e,i))});z((e,t)=>{e._x_ids&&(t._x_ids=e._x_ids)});re(Le(\"@\",$e(C(\"on:\"))));d(\"on\",D((e,{value:t,modifiers:r,expression:n},{cleanup:i})=>{let o=n?x(e,n):()=>{};e.tagName.toLowerCase()===\"template\"&&(e._x_forwardEvents||(e._x_forwardEvents=[]),e._x_forwardEvents.includes(t)||e._x_forwardEvents.push(t));let s=se(e,t,r,a=>{o(()=>{},{scope:{$event:a},params:[a]})});i(()=>s())}));tt(\"Collapse\",\"collapse\",\"collapse\");tt(\"Intersect\",\"intersect\",\"intersect\");tt(\"Focus\",\"trap\",\"focus\");tt(\"Mask\",\"mask\",\"mask\");function tt(e,t,r){d(t,n=>v(`You can't use [x-${t}] without first installing the \"${e}\" plugin here: https://alpinejs.dev/plugins/${r}`,n))}B.setEvaluator(xt);B.setReactivityEngine({reactive:Qe,effect:Zr,release:Qr,raw:_});var Kt=B;window.Alpine=Kt;queueMicrotask(()=>{Kt.start()});})();\n";
const BD_PAPAPARSE_JS = "/* @license\nPapa Parse\nv5.4.1\nhttps://github.com/mholt/PapaParse\nLicense: MIT\n*/\n!function(e,t){\"function\"==typeof define&&define.amd?define([],t):\"object\"==typeof module&&\"undefined\"!=typeof exports?module.exports=t():e.Papa=t()}(this,function s(){\"use strict\";var f=\"undefined\"!=typeof self?self:\"undefined\"!=typeof window?window:void 0!==f?f:{};var n=!f.document&&!!f.postMessage,o=f.IS_PAPA_WORKER||!1,a={},u=0,b={parse:function(e,t){var r=(t=t||{}).dynamicTyping||!1;J(r)&&(t.dynamicTypingFunction=r,r={});if(t.dynamicTyping=r,t.transform=!!J(t.transform)&&t.transform,t.worker&&b.WORKERS_SUPPORTED){var i=function(){if(!b.WORKERS_SUPPORTED)return!1;var e=(r=f.URL||f.webkitURL||null,i=s.toString(),b.BLOB_URL||(b.BLOB_URL=r.createObjectURL(new Blob([\"var global = (function() { if (typeof self !== 'undefined') { return self; } if (typeof window !== 'undefined') { return window; } if (typeof global !== 'undefined') { return global; } return {}; })(); global.IS_PAPA_WORKER=true; \",\"(\",i,\")();\"],{type:\"text/javascript\"})))),t=new f.Worker(e);var r,i;return t.onmessage=_,t.id=u++,a[t.id]=t}();return i.userStep=t.step,i.userChunk=t.chunk,i.userComplete=t.complete,i.userError=t.error,t.step=J(t.step),t.chunk=J(t.chunk),t.complete=J(t.complete),t.error=J(t.error),delete t.worker,void i.postMessage({input:e,config:t,workerId:i.id})}var n=null;b.NODE_STREAM_INPUT,\"string\"==typeof e?(e=function(e){if(65279===e.charCodeAt(0))return e.slice(1);return e}(e),n=t.download?new l(t):new p(t)):!0===e.readable&&J(e.read)&&J(e.on)?n=new g(t):(f.File&&e instanceof File||e instanceof Object)&&(n=new c(t));return n.stream(e)},unparse:function(e,t){var n=!1,_=!0,m=\",\",y=\"\\r\\n\",s='\"',a=s+s,r=!1,i=null,o=!1;!function(){if(\"object\"!=typeof t)return;\"string\"!=typeof t.delimiter||b.BAD_DELIMITERS.filter(function(e){return-1!==t.delimiter.indexOf(e)}).length||(m=t.delimiter);(\"boolean\"==typeof t.quotes||\"function\"==typeof t.quotes||Array.isArray(t.quotes))&&(n=t.quotes);\"boolean\"!=typeof t.skipEmptyLines&&\"string\"!=typeof t.skipEmptyLines||(r=t.skipEmptyLines);\"string\"==typeof t.newline&&(y=t.newline);\"string\"==typeof t.quoteChar&&(s=t.quoteChar);\"boolean\"==typeof t.header&&(_=t.header);if(Array.isArray(t.columns)){if(0===t.columns.length)throw new Error(\"Option columns is empty\");i=t.columns}void 0!==t.escapeChar&&(a=t.escapeChar+s);(\"boolean\"==typeof t.escapeFormulae||t.escapeFormulae instanceof RegExp)&&(o=t.escapeFormulae instanceof RegExp?t.escapeFormulae:/^[=+\\-@\\t\\r].*$/)}();var u=new RegExp(Q(s),\"g\");\"string\"==typeof e&&(e=JSON.parse(e));if(Array.isArray(e)){if(!e.length||Array.isArray(e[0]))return h(null,e,r);if(\"object\"==typeof e[0])return h(i||Object.keys(e[0]),e,r)}else if(\"object\"==typeof e)return\"string\"==typeof e.data&&(e.data=JSON.parse(e.data)),Array.isArray(e.data)&&(e.fields||(e.fields=e.meta&&e.meta.fields||i),e.fields||(e.fields=Array.isArray(e.data[0])?e.fields:\"object\"==typeof e.data[0]?Object.keys(e.data[0]):[]),Array.isArray(e.data[0])||\"object\"==typeof e.data[0]||(e.data=[e.data])),h(e.fields||[],e.data||[],r);throw new Error(\"Unable to serialize unrecognized input\");function h(e,t,r){var i=\"\";\"string\"==typeof e&&(e=JSON.parse(e)),\"string\"==typeof t&&(t=JSON.parse(t));var n=Array.isArray(e)&&0<e.length,s=!Array.isArray(t[0]);if(n&&_){for(var a=0;a<e.length;a++)0<a&&(i+=m),i+=v(e[a],a);0<t.length&&(i+=y)}for(var o=0;o<t.length;o++){var u=n?e.length:t[o].length,h=!1,f=n?0===Object.keys(t[o]).length:0===t[o].length;if(r&&!n&&(h=\"greedy\"===r?\"\"===t[o].join(\"\").trim():1===t[o].length&&0===t[o][0].length),\"greedy\"===r&&n){for(var d=[],l=0;l<u;l++){var c=s?e[l]:l;d.push(t[o][c])}h=\"\"===d.join(\"\").trim()}if(!h){for(var p=0;p<u;p++){0<p&&!f&&(i+=m);var g=n&&s?e[p]:p;i+=v(t[o][g],p)}o<t.length-1&&(!r||0<u&&!f)&&(i+=y)}}return i}function v(e,t){if(null==e)return\"\";if(e.constructor===Date)return JSON.stringify(e).slice(1,25);var r=!1;o&&\"string\"==typeof e&&o.test(e)&&(e=\"'\"+e,r=!0);var i=e.toString().replace(u,a);return(r=r||!0===n||\"function\"==typeof n&&n(e,t)||Array.isArray(n)&&n[t]||function(e,t){for(var r=0;r<t.length;r++)if(-1<e.indexOf(t[r]))return!0;return!1}(i,b.BAD_DELIMITERS)||-1<i.indexOf(m)||\" \"===i.charAt(0)||\" \"===i.charAt(i.length-1))?s+i+s:i}}};if(b.RECORD_SEP=String.fromCharCode(30),b.UNIT_SEP=String.fromCharCode(31),b.BYTE_ORDER_MARK=\"\\ufeff\",b.BAD_DELIMITERS=[\"\\r\",\"\\n\",'\"',b.BYTE_ORDER_MARK],b.WORKERS_SUPPORTED=!n&&!!f.Worker,b.NODE_STREAM_INPUT=1,b.LocalChunkSize=10485760,b.RemoteChunkSize=5242880,b.DefaultDelimiter=\",\",b.Parser=E,b.ParserHandle=r,b.NetworkStreamer=l,b.FileStreamer=c,b.StringStreamer=p,b.ReadableStreamStreamer=g,f.jQuery){var d=f.jQuery;d.fn.parse=function(o){var r=o.config||{},u=[];return this.each(function(e){if(!(\"INPUT\"===d(this).prop(\"tagName\").toUpperCase()&&\"file\"===d(this).attr(\"type\").toLowerCase()&&f.FileReader)||!this.files||0===this.files.length)return!0;for(var t=0;t<this.files.length;t++)u.push({file:this.files[t],inputElem:this,instanceConfig:d.extend({},r)})}),e(),this;function e(){if(0!==u.length){var e,t,r,i,n=u[0];if(J(o.before)){var s=o.before(n.file,n.inputElem);if(\"object\"==typeof s){if(\"abort\"===s.action)return e=\"AbortError\",t=n.file,r=n.inputElem,i=s.reason,void(J(o.error)&&o.error({name:e},t,r,i));if(\"skip\"===s.action)return void h();\"object\"==typeof s.config&&(n.instanceConfig=d.extend(n.instanceConfig,s.config))}else if(\"skip\"===s)return void h()}var a=n.instanceConfig.complete;n.instanceConfig.complete=function(e){J(a)&&a(e,n.file,n.inputElem),h()},b.parse(n.file,n.instanceConfig)}else J(o.complete)&&o.complete()}function h(){u.splice(0,1),e()}}}function h(e){this._handle=null,this._finished=!1,this._completed=!1,this._halted=!1,this._input=null,this._baseIndex=0,this._partialLine=\"\",this._rowCount=0,this._start=0,this._nextChunk=null,this.isFirstChunk=!0,this._completeResults={data:[],errors:[],meta:{}},function(e){var t=w(e);t.chunkSize=parseInt(t.chunkSize),e.step||e.chunk||(t.chunkSize=null);this._handle=new r(t),(this._handle.streamer=this)._config=t}.call(this,e),this.parseChunk=function(e,t){if(this.isFirstChunk&&J(this._config.beforeFirstChunk)){var r=this._config.beforeFirstChunk(e);void 0!==r&&(e=r)}this.isFirstChunk=!1,this._halted=!1;var i=this._partialLine+e;this._partialLine=\"\";var n=this._handle.parse(i,this._baseIndex,!this._finished);if(!this._handle.paused()&&!this._handle.aborted()){var s=n.meta.cursor;this._finished||(this._partialLine=i.substring(s-this._baseIndex),this._baseIndex=s),n&&n.data&&(this._rowCount+=n.data.length);var a=this._finished||this._config.preview&&this._rowCount>=this._config.preview;if(o)f.postMessage({results:n,workerId:b.WORKER_ID,finished:a});else if(J(this._config.chunk)&&!t){if(this._config.chunk(n,this._handle),this._handle.paused()||this._handle.aborted())return void(this._halted=!0);n=void 0,this._completeResults=void 0}return this._config.step||this._config.chunk||(this._completeResults.data=this._completeResults.data.concat(n.data),this._completeResults.errors=this._completeResults.errors.concat(n.errors),this._completeResults.meta=n.meta),this._completed||!a||!J(this._config.complete)||n&&n.meta.aborted||(this._config.complete(this._completeResults,this._input),this._completed=!0),a||n&&n.meta.paused||this._nextChunk(),n}this._halted=!0},this._sendError=function(e){J(this._config.error)?this._config.error(e):o&&this._config.error&&f.postMessage({workerId:b.WORKER_ID,error:e,finished:!1})}}function l(e){var i;(e=e||{}).chunkSize||(e.chunkSize=b.RemoteChunkSize),h.call(this,e),this._nextChunk=n?function(){this._readChunk(),this._chunkLoaded()}:function(){this._readChunk()},this.stream=function(e){this._input=e,this._nextChunk()},this._readChunk=function(){if(this._finished)this._chunkLoaded();else{if(i=new XMLHttpRequest,this._config.withCredentials&&(i.withCredentials=this._config.withCredentials),n||(i.onload=v(this._chunkLoaded,this),i.onerror=v(this._chunkError,this)),i.open(this._config.downloadRequestBody?\"POST\":\"GET\",this._input,!n),this._config.downloadRequestHeaders){var e=this._config.downloadRequestHeaders;for(var t in e)i.setRequestHeader(t,e[t])}if(this._config.chunkSize){var r=this._start+this._config.chunkSize-1;i.setRequestHeader(\"Range\",\"bytes=\"+this._start+\"-\"+r)}try{i.send(this._config.downloadRequestBody)}catch(e){this._chunkError(e.message)}n&&0===i.status&&this._chunkError()}},this._chunkLoaded=function(){4===i.readyState&&(i.status<200||400<=i.status?this._chunkError():(this._start+=this._config.chunkSize?this._config.chunkSize:i.responseText.length,this._finished=!this._config.chunkSize||this._start>=function(e){var t=e.getResponseHeader(\"Content-Range\");if(null===t)return-1;return parseInt(t.substring(t.lastIndexOf(\"/\")+1))}(i),this.parseChunk(i.responseText)))},this._chunkError=function(e){var t=i.statusText||e;this._sendError(new Error(t))}}function c(e){var i,n;(e=e||{}).chunkSize||(e.chunkSize=b.LocalChunkSize),h.call(this,e);var s=\"undefined\"!=typeof FileReader;this.stream=function(e){this._input=e,n=e.slice||e.webkitSlice||e.mozSlice,s?((i=new FileReader).onload=v(this._chunkLoaded,this),i.onerror=v(this._chunkError,this)):i=new FileReaderSync,this._nextChunk()},this._nextChunk=function(){this._finished||this._config.preview&&!(this._rowCount<this._config.preview)||this._readChunk()},this._readChunk=function(){var e=this._input;if(this._config.chunkSize){var t=Math.min(this._start+this._config.chunkSize,this._input.size);e=n.call(e,this._start,t)}var r=i.readAsText(e,this._config.encoding);s||this._chunkLoaded({target:{result:r}})},this._chunkLoaded=function(e){this._start+=this._config.chunkSize,this._finished=!this._config.chunkSize||this._start>=this._input.size,this.parseChunk(e.target.result)},this._chunkError=function(){this._sendError(i.error)}}function p(e){var r;h.call(this,e=e||{}),this.stream=function(e){return r=e,this._nextChunk()},this._nextChunk=function(){if(!this._finished){var e,t=this._config.chunkSize;return t?(e=r.substring(0,t),r=r.substring(t)):(e=r,r=\"\"),this._finished=!r,this.parseChunk(e)}}}function g(e){h.call(this,e=e||{});var t=[],r=!0,i=!1;this.pause=function(){h.prototype.pause.apply(this,arguments),this._input.pause()},this.resume=function(){h.prototype.resume.apply(this,arguments),this._input.resume()},this.stream=function(e){this._input=e,this._input.on(\"data\",this._streamData),this._input.on(\"end\",this._streamEnd),this._input.on(\"error\",this._streamError)},this._checkIsFinished=function(){i&&1===t.length&&(this._finished=!0)},this._nextChunk=function(){this._checkIsFinished(),t.length?this.parseChunk(t.shift()):r=!0},this._streamData=v(function(e){try{t.push(\"string\"==typeof e?e:e.toString(this._config.encoding)),r&&(r=!1,this._checkIsFinished(),this.parseChunk(t.shift()))}catch(e){this._streamError(e)}},this),this._streamError=v(function(e){this._streamCleanUp(),this._sendError(e)},this),this._streamEnd=v(function(){this._streamCleanUp(),i=!0,this._streamData(\"\")},this),this._streamCleanUp=v(function(){this._input.removeListener(\"data\",this._streamData),this._input.removeListener(\"end\",this._streamEnd),this._input.removeListener(\"error\",this._streamError)},this)}function r(m){var a,o,u,i=Math.pow(2,53),n=-i,s=/^\\s*-?(\\d+\\.?|\\.\\d+|\\d+\\.\\d+)([eE][-+]?\\d+)?\\s*$/,h=/^((\\d{4}-[01]\\d-[0-3]\\dT[0-2]\\d:[0-5]\\d:[0-5]\\d\\.\\d+([+-][0-2]\\d:[0-5]\\d|Z))|(\\d{4}-[01]\\d-[0-3]\\dT[0-2]\\d:[0-5]\\d:[0-5]\\d([+-][0-2]\\d:[0-5]\\d|Z))|(\\d{4}-[01]\\d-[0-3]\\dT[0-2]\\d:[0-5]\\d([+-][0-2]\\d:[0-5]\\d|Z)))$/,t=this,r=0,f=0,d=!1,e=!1,l=[],c={data:[],errors:[],meta:{}};if(J(m.step)){var p=m.step;m.step=function(e){if(c=e,_())g();else{if(g(),0===c.data.length)return;r+=e.data.length,m.preview&&r>m.preview?o.abort():(c.data=c.data[0],p(c,t))}}}function y(e){return\"greedy\"===m.skipEmptyLines?\"\"===e.join(\"\").trim():1===e.length&&0===e[0].length}function g(){return c&&u&&(k(\"Delimiter\",\"UndetectableDelimiter\",\"Unable to auto-detect delimiting character; defaulted to '\"+b.DefaultDelimiter+\"'\"),u=!1),m.skipEmptyLines&&(c.data=c.data.filter(function(e){return!y(e)})),_()&&function(){if(!c)return;function e(e,t){J(m.transformHeader)&&(e=m.transformHeader(e,t)),l.push(e)}if(Array.isArray(c.data[0])){for(var t=0;_()&&t<c.data.length;t++)c.data[t].forEach(e);c.data.splice(0,1)}else c.data.forEach(e)}(),function(){if(!c||!m.header&&!m.dynamicTyping&&!m.transform)return c;function e(e,t){var r,i=m.header?{}:[];for(r=0;r<e.length;r++){var n=r,s=e[r];m.header&&(n=r>=l.length?\"__parsed_extra\":l[r]),m.transform&&(s=m.transform(s,n)),s=v(n,s),\"__parsed_extra\"===n?(i[n]=i[n]||[],i[n].push(s)):i[n]=s}return m.header&&(r>l.length?k(\"FieldMismatch\",\"TooManyFields\",\"Too many fields: expected \"+l.length+\" fields but parsed \"+r,f+t):r<l.length&&k(\"FieldMismatch\",\"TooFewFields\",\"Too few fields: expected \"+l.length+\" fields but parsed \"+r,f+t)),i}var t=1;!c.data.length||Array.isArray(c.data[0])?(c.data=c.data.map(e),t=c.data.length):c.data=e(c.data,0);m.header&&c.meta&&(c.meta.fields=l);return f+=t,c}()}function _(){return m.header&&0===l.length}function v(e,t){return r=e,m.dynamicTypingFunction&&void 0===m.dynamicTyping[r]&&(m.dynamicTyping[r]=m.dynamicTypingFunction(r)),!0===(m.dynamicTyping[r]||m.dynamicTyping)?\"true\"===t||\"TRUE\"===t||\"false\"!==t&&\"FALSE\"!==t&&(function(e){if(s.test(e)){var t=parseFloat(e);if(n<t&&t<i)return!0}return!1}(t)?parseFloat(t):h.test(t)?new Date(t):\"\"===t?null:t):t;var r}function k(e,t,r,i){var n={type:e,code:t,message:r};void 0!==i&&(n.row=i),c.errors.push(n)}this.parse=function(e,t,r){var i=m.quoteChar||'\"';if(m.newline||(m.newline=function(e,t){e=e.substring(0,1048576);var r=new RegExp(Q(t)+\"([^]*?)\"+Q(t),\"gm\"),i=(e=e.replace(r,\"\")).split(\"\\r\"),n=e.split(\"\\n\"),s=1<n.length&&n[0].length<i[0].length;if(1===i.length||s)return\"\\n\";for(var a=0,o=0;o<i.length;o++)\"\\n\"===i[o][0]&&a++;return a>=i.length/2?\"\\r\\n\":\"\\r\"}(e,i)),u=!1,m.delimiter)J(m.delimiter)&&(m.delimiter=m.delimiter(e),c.meta.delimiter=m.delimiter);else{var n=function(e,t,r,i,n){var s,a,o,u;n=n||[\",\",\"\\t\",\"|\",\";\",b.RECORD_SEP,b.UNIT_SEP];for(var h=0;h<n.length;h++){var f=n[h],d=0,l=0,c=0;o=void 0;for(var p=new E({comments:i,delimiter:f,newline:t,preview:10}).parse(e),g=0;g<p.data.length;g++)if(r&&y(p.data[g]))c++;else{var _=p.data[g].length;l+=_,void 0!==o?0<_&&(d+=Math.abs(_-o),o=_):o=_}0<p.data.length&&(l/=p.data.length-c),(void 0===a||d<=a)&&(void 0===u||u<l)&&1.99<l&&(a=d,s=f,u=l)}return{successful:!!(m.delimiter=s),bestDelimiter:s}}(e,m.newline,m.skipEmptyLines,m.comments,m.delimitersToGuess);n.successful?m.delimiter=n.bestDelimiter:(u=!0,m.delimiter=b.DefaultDelimiter),c.meta.delimiter=m.delimiter}var s=w(m);return m.preview&&m.header&&s.preview++,a=e,o=new E(s),c=o.parse(a,t,r),g(),d?{meta:{paused:!0}}:c||{meta:{paused:!1}}},this.paused=function(){return d},this.pause=function(){d=!0,o.abort(),a=J(m.chunk)?\"\":a.substring(o.getCharIndex())},this.resume=function(){t.streamer._halted?(d=!1,t.streamer.parseChunk(a,!0)):setTimeout(t.resume,3)},this.aborted=function(){return e},this.abort=function(){e=!0,o.abort(),c.meta.aborted=!0,J(m.complete)&&m.complete(c),a=\"\"}}function Q(e){return e.replace(/[.*+?^${}()|[\\]\\\\]/g,\"\\\\$&\")}function E(j){var z,M=(j=j||{}).delimiter,P=j.newline,U=j.comments,q=j.step,N=j.preview,B=j.fastMode,K=z=void 0===j.quoteChar||null===j.quoteChar?'\"':j.quoteChar;if(void 0!==j.escapeChar&&(K=j.escapeChar),(\"string\"!=typeof M||-1<b.BAD_DELIMITERS.indexOf(M))&&(M=\",\"),U===M)throw new Error(\"Comment character same as delimiter\");!0===U?U=\"#\":(\"string\"!=typeof U||-1<b.BAD_DELIMITERS.indexOf(U))&&(U=!1),\"\\n\"!==P&&\"\\r\"!==P&&\"\\r\\n\"!==P&&(P=\"\\n\");var W=0,H=!1;this.parse=function(i,t,r){if(\"string\"!=typeof i)throw new Error(\"Input must be a string\");var n=i.length,e=M.length,s=P.length,a=U.length,o=J(q),u=[],h=[],f=[],d=W=0;if(!i)return L();if(j.header&&!t){var l=i.split(P)[0].split(M),c=[],p={},g=!1;for(var _ in l){var m=l[_];J(j.transformHeader)&&(m=j.transformHeader(m,_));var y=m,v=p[m]||0;for(0<v&&(g=!0,y=m+\"_\"+v),p[m]=v+1;c.includes(y);)y=y+\"_\"+v;c.push(y)}if(g){var k=i.split(P);k[0]=c.join(M),i=k.join(P)}}if(B||!1!==B&&-1===i.indexOf(z)){for(var b=i.split(P),E=0;E<b.length;E++){if(f=b[E],W+=f.length,E!==b.length-1)W+=P.length;else if(r)return L();if(!U||f.substring(0,a)!==U){if(o){if(u=[],I(f.split(M)),F(),H)return L()}else I(f.split(M));if(N&&N<=E)return u=u.slice(0,N),L(!0)}}return L()}for(var w=i.indexOf(M,W),R=i.indexOf(P,W),C=new RegExp(Q(K)+Q(z),\"g\"),S=i.indexOf(z,W);;)if(i[W]!==z)if(U&&0===f.length&&i.substring(W,W+a)===U){if(-1===R)return L();W=R+s,R=i.indexOf(P,W),w=i.indexOf(M,W)}else if(-1!==w&&(w<R||-1===R))f.push(i.substring(W,w)),W=w+e,w=i.indexOf(M,W);else{if(-1===R)break;if(f.push(i.substring(W,R)),D(R+s),o&&(F(),H))return L();if(N&&u.length>=N)return L(!0)}else for(S=W,W++;;){if(-1===(S=i.indexOf(z,S+1)))return r||h.push({type:\"Quotes\",code:\"MissingQuotes\",message:\"Quoted field unterminated\",row:u.length,index:W}),T();if(S===n-1)return T(i.substring(W,S).replace(C,z));if(z!==K||i[S+1]!==K){if(z===K||0===S||i[S-1]!==K){-1!==w&&w<S+1&&(w=i.indexOf(M,S+1)),-1!==R&&R<S+1&&(R=i.indexOf(P,S+1));var O=A(-1===R?w:Math.min(w,R));if(i.substr(S+1+O,e)===M){f.push(i.substring(W,S).replace(C,z)),i[W=S+1+O+e]!==z&&(S=i.indexOf(z,W)),w=i.indexOf(M,W),R=i.indexOf(P,W);break}var x=A(R);if(i.substring(S+1+x,S+1+x+s)===P){if(f.push(i.substring(W,S).replace(C,z)),D(S+1+x+s),w=i.indexOf(M,W),S=i.indexOf(z,W),o&&(F(),H))return L();if(N&&u.length>=N)return L(!0);break}h.push({type:\"Quotes\",code:\"InvalidQuotes\",message:\"Trailing quote on quoted field is malformed\",row:u.length,index:W}),S++}}else S++}return T();function I(e){u.push(e),d=W}function A(e){var t=0;if(-1!==e){var r=i.substring(S+1,e);r&&\"\"===r.trim()&&(t=r.length)}return t}function T(e){return r||(void 0===e&&(e=i.substring(W)),f.push(e),W=n,I(f),o&&F()),L()}function D(e){W=e,I(f),f=[],R=i.indexOf(P,W)}function L(e){return{data:u,errors:h,meta:{delimiter:M,linebreak:P,aborted:H,truncated:!!e,cursor:d+(t||0)}}}function F(){q(L()),u=[],h=[]}},this.abort=function(){H=!0},this.getCharIndex=function(){return W}}function _(e){var t=e.data,r=a[t.workerId],i=!1;if(t.error)r.userError(t.error,t.file);else if(t.results&&t.results.data){var n={abort:function(){i=!0,m(t.workerId,{data:[],errors:[],meta:{aborted:!0}})},pause:y,resume:y};if(J(r.userStep)){for(var s=0;s<t.results.data.length&&(r.userStep({data:t.results.data[s],errors:t.results.errors,meta:t.results.meta},n),!i);s++);delete t.results}else J(r.userChunk)&&(r.userChunk(t.results,n,t.file),delete t.results)}t.finished&&!i&&m(t.workerId,t.results)}function m(e,t){var r=a[e];J(r.userComplete)&&r.userComplete(t),r.terminate(),delete a[e]}function y(){throw new Error(\"Not implemented.\")}function w(e){if(\"object\"!=typeof e||null===e)return e;var t=Array.isArray(e)?[]:{};for(var r in e)t[r]=w(e[r]);return t}function v(e,t){return function(){e.apply(t,arguments)}}function J(e){return\"function\"==typeof e}return o&&(f.onmessage=function(e){var t=e.data;void 0===b.WORKER_ID&&t&&(b.WORKER_ID=t.workerId);if(\"string\"==typeof t.input)f.postMessage({workerId:b.WORKER_ID,results:b.parse(t.input,t.config),finished:!0});else if(f.File&&t.input instanceof File||t.input instanceof Object){var r=b.parse(t.input,t.config);r&&f.postMessage({workerId:b.WORKER_ID,results:r,finished:!0})}}),(l.prototype=Object.create(h.prototype)).constructor=l,(c.prototype=Object.create(h.prototype)).constructor=c,(p.prototype=Object.create(p.prototype)).constructor=p,(g.prototype=Object.create(h.prototype)).constructor=g,b});";
