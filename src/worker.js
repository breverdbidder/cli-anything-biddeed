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
 *   POST /chat/api            → Streaming SSE chat (Anthropic)
 *   POST /chat/lead           → Email capture → Supabase lead_profiles
 *   GET  /chat/county-data    → County card JSON
 *   GET  /subscribe           → Stripe checkout redirect
 *   GET  /success             → Post-payment key delivery page
 *   GET  /subscribe/status    → Poll for API key after payment
 *   GET  /terms               → Terms of Service
 *   GET  /privacy             → Privacy Policy
 *   GET  /disclaimer          → Disclaimer
 */

// ── Constants ─────────────────────────────────────────────────────────────────
const SUPABASE_URL = 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE2ODc0Nzc1MTksImV4cCI6MjAwMzA1MzUxOX0.VFl2gOfVWMRFQPiWxkpRf-GH5Vc_9bRHhK5bnAHmLNA';
const STRIPE_INVESTOR_URL = 'https://buy.stripe.com/00w3cwc401zZ7eEape3wQ00';
const MINDSTUDIO_S5_URL = 'https://app.mindstudio.ai/agents/64fc28ea-edaa-40d7-a0ab-1b79d721e427';
const DISCLAIMER_SHORT = 'Informational only — not legal, financial, or investment advice. Verify independently & consult a licensed attorney before bidding.';

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
async function logErr(env, endpoint, message, detail, status) {
  try {
    await fetch(`${SUPABASE_URL}/rest/v1/rpc/log_worker_error`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` },
      body: JSON.stringify({ p_severity: 'error', p_endpoint: endpoint, p_message: message, p_detail: String(detail || ''), p_status: status || 500 }),
    });
  } catch(_) {}
}

// ── Rate limit ────────────────────────────────────────────────────────────────
async function checkRateLimit(ip, limit = 15) {
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/chat_rate_check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` },
      body: JSON.stringify({ p_ip: ip, p_limit: limit }),
    });
    if (!res.ok) return true;
    return await res.json() === true;
  } catch(_) { return true; }
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

// ── Main fetch handler ────────────────────────────────────────────────────────
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

      // ── Legal ────────────────────────────────────────────────────────────
      if (path === '/terms')      return new Response(TERMS_HTML,      { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/privacy')    return new Response(PRIVACY_HTML,    { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });
      if (path === '/disclaimer') return new Response(DISCLAIMER_HTML, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=3600' } });

      // ── /subscribe ───────────────────────────────────────────────────────
      if (path === '/subscribe') {
        return Response.redirect(STRIPE_INVESTOR_URL, 302);
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

      // ── /county/:slug — county deep-link landing page ────────────────────
      if (path.startsWith('/county/')) {
        const slug = path.replace('/county/', '').toLowerCase().replace(/-/g,'_');
        if (!slug) return Response.redirect('/counties', 302);
        const data = await fetchCountyData(slug);
        const html = buildCountyPage(slug, data);
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      // ── /counties — all counties index ───────────────────────────────────
      if (path === '/counties') {
        const html = buildCountiesIndex();
        return new Response(html, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      // ── /chat/county-data ────────────────────────────────────────────────
      if (path === '/chat/county-data') {
        const county = url.searchParams.get('county') || '';
        if (!county) return new Response(JSON.stringify(null), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const row = await fetchCountyData(county);
        return new Response(JSON.stringify(row), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
      }

      // ── POST /chat/lead ──────────────────────────────────────────────────
      if (path === '/chat/lead' && method === 'POST') {
        let body = {};
        try { body = await request.json(); } catch(_) {}
        const { email, county, source } = body;
        if (!email) return new Response(JSON.stringify({ ok: false, error: 'email required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/lead_profiles`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'apikey': SUPABASE_KEY,
              'Authorization': `Bearer ${SUPABASE_KEY}`,
              'Prefer': 'resolution=merge-duplicates,return=minimal',
            },
            body: JSON.stringify({ email, county_interest: county || null, source: source || 'homepage_chatbot' }),
          });
          if (!res.ok) {
            const err = await res.text();
            await logErr(env, '/chat/lead', 'Supabase upsert failed', err, res.status);
            return new Response(JSON.stringify({ ok: false, error: err }), { status: res.status, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
          }
          return new Response(JSON.stringify({ ok: true }), { headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
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
        const allowed = await checkRateLimit(ip, 15);
        if (!allowed) return new Response(JSON.stringify({ error: 'Rate limit exceeded. Try again in a minute.' }), { status: 429, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

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

        const countyCtx = county ? `The user is asking about ${toDisplay(county)} County, Florida.` : 'The user may ask about any Florida county.';
        const systemPrompt = `You are BidDeed.AI, the expert AI assistant for Florida foreclosure and tax deed auction intelligence. Built on 20 years of experience from Ariel Shapira, creator of the Shapira Max Bid Formula.

${countyCtx}

Your capabilities:
- Analyze foreclosure and tax deed auctions across all 67 Florida counties
- Explain and apply the Shapira Max Bid Formula (exact ceiling before bidding)
- Identify Gold Standard certified counties (verified data quality)
- Explain lien priority, HOA foreclosure risks, and surplus funds
- Answer questions about ZoneWise zoning intelligence
- Respond in the same language the user writes in (English, Hebrew, Spanish, Portuguese, Arabic, Russian, Chinese, French, Italian, German, Japanese, Korean, etc.)

Key facts:
- 24 Gold Standard certified counties: Brevard, Broward, Charlotte, Clay, Duval, Franklin, Hardee, Hendry, Hernando, Highlands, Hillsborough, Indian River, Jackson, Lafayette, Leon, Monroe, Nassau, Orange, Palm Beach, Pasco, Putnam, St. Johns, Volusia, Washington
- Marion County proof: Case 422021CA000414CAAXXX — Shapira Max Bid $82,000, actual sale $73,501. Ceiling held by $8,499.
- Shapira S5 reports: $25 each — full AI-powered max-bid analysis for one specific property
- Investor tier: $99/month — unlimited property cards, 10 S5 reports/mo, daily digest all 67 counties
- When a user asks for a specific property analysis, mention they can get a full Shapira S5 Report for $25

When someone asks for a specific property analysis or max bid, always suggest the $25 Shapira S5 Report as the way to get the full calculation. ${DISCLAIMER_SHORT}`;

        const anthropicKey = env.ANTHROPIC_KEY;
        if (!anthropicKey) {
          await logErr(env, '/chat/api', 'Missing ANTHROPIC_KEY binding', '', 500);
          return new Response(JSON.stringify({ error: 'Service configuration error' }), { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        let anthropicRes;
        try {
          anthropicRes = await fetch('https://api.anthropic.com/v1/messages', {
            method: 'POST',
            headers: { 'x-api-key': anthropicKey, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json' },
            body: JSON.stringify({
              model: 'claude-haiku-4-5',
              max_tokens: 1024,
              stream: true,
              system: systemPrompt,
              messages: messages.map(m => ({ role: m.role, content: String(m.content) })),
            }),
          });
        } catch(e) {
          await logErr(env, '/chat/api', 'Anthropic fetch failed', String(e), 502);
          return new Response(JSON.stringify({ error: 'AI service unavailable' }), { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        if (!anthropicRes.ok) {
          const errText = await anthropicRes.text();
          await logErr(env, '/chat/api', 'Anthropic non-200', errText, anthropicRes.status);
          return new Response(JSON.stringify({ error: 'AI service error' }), { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        const { readable, writable } = new TransformStream();
        const writer = writable.getWriter();
        const encoder = new TextEncoder();

        ctx.waitUntil((async () => {
          const reader = anthropicRes.body.getReader();
          const decoder = new TextDecoder();
          let buf = '';
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
                    await writer.write(encoder.encode(`data: ${JSON.stringify({ text: evt.delta.text })}\n\n`));
                  }
                } catch(_) {}
              }
            }
            await writer.write(encoder.encode('data: [DONE]\n\n'));
          } catch(e) {
            await logErr(env, '/chat/api', 'Stream pipe error', String(e), 500);
          } finally {
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
        return new Response(HOMEPAGE_HTML, { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': 'public,max-age=300' } });
      }

      return new Response('Not found', { status: 404 });

    } catch(e) {
      await logErr(env, path, 'Unhandled error', String(e), 500);
      return new Response('Internal server error', { status: 500 });
    }
  }
};

// ── County deep-link landing page ─────────────────────────────────────────────
function buildCountyPage(slug, d) {
  const name = toDisplay(slug);
  const isGold = d ? d.is_gold_standard : GOLD_COUNTIES.includes(slug);
  const fcCount = d?.fc_upcoming_30d || 0;
  const tdCount = d?.td_upcoming_30d || 0;
  const fcNext  = fmtDate(d?.fc_next_auction_date);
  const tdNext  = fmtDate(d?.td_next_auction_date);
  const fcAvg   = fmtMoney(d?.fc_avg_opening_bid);
  const tdAvg   = fmtMoney(d?.td_avg_opening_bid);
  const total   = fcCount + tdCount;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${name} County Foreclosure &amp; Tax Deed Auctions — BidDeed.AI</title>
<meta name="description" content="${name} County FL: ${total} upcoming auctions. AI-powered max bid analysis. Gold Standard certified data.">
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
.nav-cta{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:8px 18px;border-radius:8px;font-size:13px;font-weight:700;text-decoration:none}
.hero{padding:3rem 1.5rem 2rem;max-width:1100px;margin:0 auto}
.breadcrumb{font-size:.78rem;color:var(--muted);margin-bottom:1rem}
.breadcrumb a{color:var(--muted);text-decoration:none}.breadcrumb a:hover{color:var(--orange)}
.county-header{display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:1rem;margin-bottom:2rem}
.county-title h1{font-family:'DM Serif Display',serif;font-size:clamp(1.8rem,4vw,2.8rem);color:white;line-height:1.15}
.county-title p{color:var(--muted);margin-top:.5rem;font-size:.95rem}
.gold-badge{display:inline-flex;align-items:center;gap:.4rem;background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);border-radius:20px;padding:.4rem 1rem;font-size:.8rem;color:var(--orange);font-weight:600}
.pend-badge{display:inline-flex;align-items:center;gap:.4rem;background:var(--navy3);border:1px solid var(--border);border-radius:20px;padding:.4rem 1rem;font-size:.8rem;color:var(--muted);font-weight:600}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1rem;margin-bottom:2rem}
.stat-card{background:var(--navy2);border:1px solid var(--border);border-radius:12px;padding:1.25rem}
.stat-num{font-family:'JetBrains Mono',monospace;font-size:1.6rem;font-weight:600;color:white}
.stat-num.hot{color:var(--orange)}
.stat-lbl{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:.25rem}
.main-grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:2rem}
@media(max-width:700px){.main-grid{grid-template-columns:1fr}}
.type-card{background:var(--navy2);border:1px solid var(--border);border-radius:14px;padding:1.5rem}
.type-card.fc{border-left:3px solid var(--orange)}
.type-card.td{border-left:3px solid var(--green)}
.type-label{font-family:'JetBrains Mono',monospace;font-size:.65rem;letter-spacing:.1em;margin-bottom:.75rem;font-weight:700}
.type-label.fc{color:var(--orange)}.type-label.td{color:var(--green)}
.type-title{font-size:1.1rem;font-weight:700;color:white;margin-bottom:1rem}
.type-row{display:flex;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:.85rem}
.type-row:last-child{border-bottom:none}
.type-row .lbl{color:var(--muted)}.type-row .val{color:white;font-weight:600;font-family:'JetBrains Mono',monospace;font-size:.82rem}
.chat-section{background:var(--navy2);border:1px solid rgba(245,158,11,.2);border-radius:16px;overflow:hidden;margin-bottom:2rem}
.chat-header{background:var(--navy3);padding:1rem 1.5rem;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:.75rem}
.chat-header h2{font-size:1rem;font-weight:700;color:white}
.chat-header p{font-size:.8rem;color:var(--muted)}
.report-cta{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.25);border-radius:14px;padding:1.5rem;margin-bottom:2rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.report-cta-left h3{font-size:1rem;font-weight:700;color:white;margin-bottom:.3rem}
.report-cta-left p{font-size:.82rem;color:var(--muted);line-height:1.5}
.report-btn{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:12px 24px;border-radius:10px;font-size:.9rem;font-weight:700;text-decoration:none;white-space:nowrap;flex-shrink:0}
.counties-link{text-align:center;padding:2rem;font-size:.85rem;color:var(--muted)}
.counties-link a{color:var(--orange);text-decoration:none;font-weight:600}
footer{border-top:1px solid var(--border);padding:1.5rem;text-align:center;font-size:.75rem;color:var(--muted)}
footer a{color:var(--muted);text-decoration:none}
@media(max-width:600px){.county-header{flex-direction:column}.stats-grid{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<nav><div class="nav-inner">
  <a href="/" class="logo"><div class="lm">BD</div><span class="ln">BidDeed<span>.AI</span></span></a>
  <a href="/subscribe?tier=investor" class="nav-cta">Investor $99/mo</a>
</div></nav>

<div class="hero">
  <div class="breadcrumb"><a href="/">BidDeed.AI</a> › <a href="/counties">Counties</a> › ${name}</div>

  <div class="county-header">
    <div class="county-title">
      <h1>${name} County, Florida</h1>
      <p>Foreclosure &amp; Tax Deed Auction Intelligence</p>
    </div>
    <div>${isGold
      ? '<div class="gold-badge">🏆 Gold Standard Certified</div>'
      : '<div class="pend-badge">⏳ Certification Pending</div>'
    }</div>
  </div>

  <div class="stats-grid">
    <div class="stat-card"><div class="stat-num hot">${fcCount}</div><div class="stat-lbl">FC Auctions (30 days)</div></div>
    <div class="stat-card"><div class="stat-num hot">${tdCount}</div><div class="stat-lbl">TD Auctions (30 days)</div></div>
    <div class="stat-card"><div class="stat-num">${fcNext}</div><div class="stat-lbl">Next FC Auction</div></div>
    <div class="stat-card"><div class="stat-num">${tdNext}</div><div class="stat-lbl">Next TD Auction</div></div>
  </div>

  <div class="main-grid">
    <div class="type-card fc">
      <div class="type-label fc">FORECLOSURE AUCTIONS</div>
      <div class="type-title">Foreclosure Sales</div>
      <div class="type-row"><span class="lbl">Upcoming (30d)</span><span class="val">${fcCount}</span></div>
      <div class="type-row"><span class="lbl">Next Auction</span><span class="val">${fcNext}</span></div>
      <div class="type-row"><span class="lbl">Avg Opening Bid</span><span class="val">${fcAvg}</span></div>
      <div class="type-row"><span class="lbl">Data Quality</span><span class="val">${isGold ? '🏆 Gold Standard' : '⏳ Pending'}</span></div>
    </div>
    <div class="type-card td">
      <div class="type-label td">TAX DEED AUCTIONS</div>
      <div class="type-title">Tax Deed Sales</div>
      <div class="type-row"><span class="lbl">Upcoming (30d)</span><span class="val">${tdCount}</span></div>
      <div class="type-row"><span class="lbl">Next Auction</span><span class="val">${tdNext}</span></div>
      <div class="type-row"><span class="lbl">Avg Opening Bid</span><span class="val">${tdAvg}</span></div>
      <div class="type-row"><span class="lbl">Data Quality</span><span class="val">${isGold ? '🏆 Gold Standard' : '⏳ Pending'}</span></div>
    </div>
  </div>

  <div class="report-cta">
    <div class="report-cta-left">
      <h3>💼 Get a Shapira S5 Report — $25</h3>
      <p>Full AI-powered analysis for any ${name} property: exact max bid ceiling, lien stack, plaintiff intel, ZoneWise zoning, and BID/SKIP recommendation. Verified to the cent.</p>
    </div>
    <a href="${MINDSTUDIO_S5_URL}" target="_blank" class="report-btn">Get Report — $25 →</a>
  </div>

  <div class="chat-section">
    <div class="chat-header">
      <div>
        <h2>Ask BidDeed.AI about ${name} County</h2>
        <p>Live auction data · Shapira Formula · Responds in your language</p>
      </div>
    </div>
    <iframe src="/chat?county=${encodeURIComponent(slug)}&hook=COUNTY_PAGE" width="100%" height="580" style="display:block;border:none" allow="clipboard-write" loading="lazy" title="BidDeed.AI ${name} County Chat"></iframe>
  </div>

  <div class="counties-link"><a href="/counties">← View all 67 Florida counties</a></div>
</div>

<footer>
  <p>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a></p>
  <p style="margin-top:.5rem;font-size:.7rem;max-width:800px;margin-left:auto;margin-right:auto">${DISCLAIMER_SHORT}</p>
</footer>
</body></html>`;
}

// ── Counties index ────────────────────────────────────────────────────────────
function buildCountiesIndex() {
  const goldSet = new Set(GOLD_COUNTIES);
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
.nav-cta{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:8px 18px;border-radius:8px;font-size:13px;font-weight:700;text-decoration:none}
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
  <p>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a></p>
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
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>BidDeed.AI · Auction Intelligence</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--navy3:#1e293b;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--border:#1e293b;--green:#10b981}
html{height:100%;height:-webkit-fill-available}
body{display:flex;flex-direction:column;background:var(--navy);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;height:100vh;height:-webkit-fill-available;overflow:hidden;position:fixed;width:100%}

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
.msgs{flex:1;overflow-y:auto;overflow-x:hidden;padding:12px 14px;display:flex;flex-direction:column;gap:10px;-webkit-overflow-scrolling:touch;overscroll-behavior:contain}

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
.bbl.ai{background:rgba(255,255,255,.04);border:1px solid var(--border);color:var(--text);white-space:pre-wrap}
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

<script>
const COUNTY = ${JSON.stringify(county)};
const HOOK   = ${JSON.stringify(hook)};
const AUTO   = ${JSON.stringify(autoMsg)};
const S5_URL = ${JSON.stringify(MINDSTUDIO_S5_URL)};
let H = [], busy = false, emailDone = false, s5Shown = false, msgCount = 0;

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
function scrollBottom(){const m=document.getElementById('msgs');if(m){m.scrollTop=m.scrollHeight;}}

function addMsg(role,content){
  document.getElementById('welcome')?.remove();
  const m=document.getElementById('msgs');
  const row=document.createElement('div');row.className='msg '+role;
  const av=role==='assistant'?'<div class="av ai">BD</div>':'<div class="av user">👤</div>';
  row.innerHTML=av+'<div class="bbl '+role+'">'+esc(content)+'</div>';
  m.appendChild(row);scrollBottom();
  return row.querySelector('.bbl');
}

function showS5CTA(){
  if(s5Shown||document.getElementById('s5cta'))return;
  s5Shown=true;
  const m=document.getElementById('msgs');
  const d=document.createElement('div');d.id='s5cta';d.className='s5-cta';
  d.innerHTML='<div class="s5-cta-text"><div class="title">💼 Get a Shapira S5 Report</div><div class="desc">Full AI max-bid analysis for a specific property — lien stack, plaintiff intel, zoning, BID/SKIP recommendation.</div></div><a href="'+S5_URL+'" target="_blank" class="s5-btn">$25 — Get Report →</a>';
  m.appendChild(d);scrollBottom();
}

function ask(t){document.getElementById('inp').value=t;send();}

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
  try{
    const res=await fetch('/chat/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:H,county:COUNTY,hook:HOOK})});
    document.getElementById('typing')?.remove();
    if(!res.ok){addMsg('assistant','Error '+res.status+'. Please try again.');busy=false;document.getElementById('snd').disabled=false;inp.focus();return;}
    document.getElementById('welcome')?.remove();
    const row=document.createElement('div');row.className='msg assistant';
    row.innerHTML='<div class="av ai">BD</div><div class="bbl ai" id="sbbl"></div>';
    m.appendChild(row);scrollBottom();
    const bbl=document.getElementById('sbbl');
    const reader=res.body.getReader();const decoder=new TextDecoder();
    let fullText='',buf='';
    while(true){
      const{done,value}=await reader.read();if(done)break;
      buf+=decoder.decode(value,{stream:true});
      const lines=buf.split('\n');buf=lines.pop()||'';
      for(const line of lines){
        if(!line.startsWith('data: '))continue;
        const data=line.slice(6).trim();if(data==='[DONE]')break;
        try{const evt=JSON.parse(data);if(evt.text){fullText+=evt.text;bbl.textContent=fullText;scrollBottom();}}catch(e){}
      }
    }
    bbl.id='';
    H.push({role:'assistant',content:fullText});
    // Show S5 CTA after 2nd message
    if(msgCount>=2&&!s5Shown)showS5CTA();
    // Show email capture after 3rd message
    if(!emailDone&&msgCount>=3)showEmailCapture();
  }catch(e){
    document.getElementById('typing')?.remove();
    addMsg('assistant','Connection error. Check your internet and try again.');
  }
  busy=false;document.getElementById('snd').disabled=false;inp.focus();
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
  fetch('/chat/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,county:COUNTY,source:HOOK||'chat'})}).catch(()=>{});
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
</script>
</body>
</html>`;
}

// ── Success page ──────────────────────────────────────────────────────────────
const SUCCESS_HTML = `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Welcome to BidDeed.AI Investor</title>
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


// ── Static HTML pages ────────────────────────────────────────────────────────
const HOMEPAGE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BidDeed.AI — AI-Powered Foreclosure &amp; Tax Deed Auction Intelligence</title>
<meta name="description" content="The only platform that tells you what's coming to auction, what to bid, and what the zoning allows — before you bid online or walk into the courthouse.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#020617;--navy2:#0f172a;--navy3:#1e293b;--orange:#f59e0b;--orange2:#f97316;--text:#e2e8f0;--muted:#cbd5e1;--dim:#94a3b8;--border:#1e293b;--green:#10b981}
html{scroll-behavior:smooth}
body{background:var(--navy);color:var(--text);font-family:'Inter',sans-serif;overflow-x:hidden}
nav{position:sticky;top:0;z-index:100;background:rgba(2,6,23,.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 2rem}
.nav-inner{max-width:1100px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;height:64px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none}
.lm{width:34px;height:34px;background:linear-gradient(135deg,var(--orange),var(--orange2));border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:13px;color:var(--navy);flex-shrink:0}
.ln{font-size:16px;font-weight:700;color:white;letter-spacing:-.02em}.ln span{color:var(--orange)}
.nav-links{display:flex;gap:1.5rem}.nav-links a{color:#e2e8f0;text-decoration:none;font-size:14px;font-weight:500}.nav-links a:hover{color:white}
.nav-cta{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:9px 20px;border-radius:8px;font-size:14px;font-weight:700;text-decoration:none}
.hero{padding:5rem 2rem 4rem;text-align:center;max-width:860px;margin:0 auto}
.hbadge{display:inline-flex;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);padding:.35rem 1rem;border-radius:20px;font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--orange);margin-bottom:1.5rem;letter-spacing:.06em}
h1.hh1{font-family:'DM Serif Display',serif;font-size:clamp(2.2rem,5vw,3.6rem);color:white;line-height:1.15;letter-spacing:-.02em;margin-bottom:1.25rem}
h1.hh1 em{color:var(--orange);font-style:normal}
.hsub{font-size:1.1rem;color:var(--muted);max-width:560px;margin:0 auto 2rem;line-height:1.7}
.hact{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;margin-bottom:3rem}
.bp{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy);padding:14px 28px;border-radius:10px;font-size:15px;font-weight:700;text-decoration:none;display:inline-block}
.bs{background:transparent;color:var(--text);padding:14px 28px;border-radius:10px;font-size:15px;font-weight:600;text-decoration:none;border:1px solid var(--border);display:inline-block}
.hstats{display:flex;gap:2.5rem;justify-content:center;flex-wrap:wrap}
.st .sn{font-family:'JetBrains Mono',monospace;font-size:1.6rem;font-weight:600;color:white}.st .sn span{color:var(--orange)}
.st .sl{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:.2rem}
.moat{padding:1.5rem 2rem;background:var(--navy2);border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
.moat-i{max-width:1100px;margin:0 auto;display:flex;align-items:center;justify-content:center;gap:2rem;flex-wrap:wrap}
.mi{display:flex;align-items:center;gap:.6rem;font-size:.85rem;color:var(--muted)}.mi strong{color:white}
.msep{width:1px;height:20px;background:var(--border)}
.sec{padding:4rem 2rem;max-width:1100px;margin:0 auto}
.ey{display:inline-flex;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);padding:.3rem .9rem;border-radius:20px;font-size:.7rem;font-family:'JetBrains Mono',monospace;color:var(--green);letter-spacing:.06em;margin-bottom:1.25rem}
.st2{font-family:'DM Serif Display',serif;font-size:clamp(1.6rem,3vw,2.4rem);color:white;margin-bottom:.75rem;line-height:1.2}
.ss{color:var(--muted);font-size:.95rem;margin-bottom:2rem;max-width:520px}
.lps{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1.25rem}
.lp{background:var(--navy3);border:1px solid var(--border);border-radius:20px;padding:.25rem .75rem;font-size:.72rem;color:var(--muted)}
.cfw{background:var(--navy2);border:1px solid rgba(245,158,11,.15);border-radius:16px;overflow:hidden;box-shadow:0 0 60px rgba(245,158,11,.04)}
.cfb{background:var(--navy3);padding:10px 18px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--border)}
.cfd{width:10px;height:10px;border-radius:50%}
.cfl{font-family:'JetBrains Mono',monospace;font-size:.68rem;color:var(--muted);margin-left:auto}
.cn{text-align:center;margin-top:1rem;font-size:.8rem;color:var(--muted)}.cn a{color:var(--orange);text-decoration:none;font-weight:600}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1rem;margin-top:2rem}
.sg{background:var(--navy2);border:1px solid var(--border);border-radius:12px;padding:1.25rem}
.sn2{font-family:'JetBrains Mono',monospace;font-size:.65rem;color:var(--orange);letter-spacing:.08em;margin-bottom:.5rem}
.sna{font-size:.95rem;font-weight:600;color:white;margin-bottom:.35rem}
.sd{font-size:.8rem;color:var(--muted);line-height:1.5}
.cgrid{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.5rem}
.cc{background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.2);border-radius:6px;padding:.3rem .75rem;font-size:.78rem;color:var(--green);font-weight:500}
.cc::before{content:'✓ ';font-weight:700}
.pc{background:var(--navy2);border:1px solid var(--border);border-left:3px solid var(--orange);border-radius:16px;padding:2rem}
.pl{font-family:'JetBrains Mono',monospace;font-size:.65rem;color:var(--orange);letter-spacing:.08em;margin-bottom:.75rem}
.pcase{font-size:1rem;font-weight:600;color:white;margin-bottom:1.25rem}
.pgr{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:1rem}
.pi label{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.pi value{display:block;font-family:'JetBrains Mono',monospace;font-size:.95rem;font-weight:600;color:white;margin-top:.15rem}
.pi value.g{color:var(--green)}.pi value.o{color:var(--orange)}
.pv{margin-top:1.5rem;background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.2);border-radius:8px;padding:.75rem 1rem;font-size:.85rem;color:var(--green);font-weight:600}
.prgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1.25rem;margin-top:2rem}
.pln{background:var(--navy2);border:1px solid var(--border);border-radius:16px;padding:1.75rem;position:relative}
.pln.live{border-color:rgba(245,158,11,.4)}.pln.coming{opacity:1}
.pbadge{position:absolute;top:-11px;left:50%;transform:translateX(-50%);font-size:.65rem;font-weight:800;padding:.25rem .9rem;border-radius:20px;white-space:nowrap}
.pbadge.hot{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy)}
.pbadge.soon{background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.3)}
.pname{font-size:.8rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.4rem}
.pprice{font-family:'DM Serif Display',serif;font-size:2.2rem;color:white;margin-bottom:.2rem}
.pprice sub{font-family:'Inter',sans-serif;font-size:.85rem;color:var(--muted);font-weight:400}
.pdesc{font-size:.8rem;color:var(--muted);margin-bottom:1.25rem;line-height:1.5}
.pfeats{list-style:none;margin-bottom:1.5rem}
.pfeats li{font-size:.83rem;color:var(--muted);padding:.35rem 0;border-bottom:1px solid rgba(255,255,255,.04);display:flex;align-items:flex-start;gap:.5rem}
.pln.coming .pfeats li{color:rgba(255,255,255,.75)}
.pln.coming .pname{color:rgba(255,255,255,.8)}
.pln.coming .pprice{color:white}
.pfeats li::before{content:'→';color:var(--orange);flex-shrink:0;font-weight:700}
.pfeats li.sf::before{content:'⏳';font-size:.75rem}.pfeats li.sf{color:var(--muted)}
.pcta{display:block;text-align:center;padding:12px;border-radius:10px;font-size:.88rem;font-weight:700;text-decoration:none}
.pcta.hot{background:linear-gradient(135deg,var(--orange),var(--orange2));color:var(--navy)}
.pcta.off{background:var(--navy3);color:var(--muted);cursor:default;border:1px solid var(--border)}
.pfree{background:var(--navy2);border:1px solid var(--border);border-radius:16px;padding:1.25rem 1.75rem;margin-top:1rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem}
.pft strong{color:white;display:block;font-size:.95rem}.pft span{font-size:.8rem;color:var(--muted)}
.fgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:1.25rem;margin-top:2rem}
.fi{background:var(--navy2);border:1px solid var(--border);border-radius:12px;padding:1.5rem}
.fi-ic{font-size:1.5rem;margin-bottom:.75rem}
.fi-t{font-size:.95rem;font-weight:700;color:white;margin-bottom:.5rem}
.fi-d{font-size:.82rem;color:var(--muted);line-height:1.6}
.fcta{padding:5rem 2rem;text-align:center}
.fcta h2{font-family:'DM Serif Display',serif;font-size:clamp(1.8rem,4vw,2.8rem);color:white;margin-bottom:1rem}
.fcta p{color:var(--muted);margin-bottom:2rem}
.crow{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap}
footer{border-top:1px solid var(--border);padding:1.5rem 2rem;text-align:center;font-size:.78rem;color:var(--muted)}
footer a{color:var(--muted);text-decoration:none}
hr.dv{border:none;border-top:1px solid var(--border);max-width:1100px;margin:0 auto}
@media(max-width:640px){.nav-links{display:none}.msep{display:none}}
</style>
<script>!function(t,e){window.posthog=e,e._i=[],e.init=function(i,s){var p=t.createElement("script");p.async=!0,p.src="https://us-assets.i.posthog.com/static/array.js",t.head.appendChild(p),e._i.push([i,s])}}(document,window.posthog||[]);posthog.init("phc_zUQGNqDUYXbpJn7RGKt2wwnHfP8GXge2MZsYAJXTs14",{api_host:"https://us.i.posthog.com"});</script>
</head>
<body>
<nav><div class="nav-inner">
  <a href="/" class="logo"><div class="lm">BD</div><span class="ln">BidDeed<span>.AI</span></span></a>
  <div class="nav-links"><a href="#chat">Try Free</a><a href="#how-it-works">How It Works</a><a href="#gold-standard">Gold Standard</a><a href="#pricing">Pricing</a></div>
  <a href="/subscribe?tier=investor" class="nav-cta">Investor $99/mo</a>
</div></nav>

<section class="hero">
  <div class="hbadge">AI AGENTS · ALL 67 FLORIDA COUNTIES</div>
  <h1 class="hh1">AI-Powered Foreclosure &amp;<br><em>Tax Deed Auction Intelligence</em></h1>
  <p class="hsub">The only platform that tells you what's coming to auction, what to bid, and what the zoning allows — before you bid online or walk into the courthouse.</p>
  <div class="hact"><a href="#chat" class="bp">Try It Free — No Signup</a><a href="#pricing" class="bs">See Pricing</a></div>
  <div class="hstats">
    <div class="st"><div class="sn">67<span>+</span></div><div class="sl">Florida Counties</div></div>
    <div class="st"><div class="sn">24<span>✓</span></div><div class="sl">Gold Standard</div></div>
    <div class="st"><div class="sn">21<span>K+</span></div><div class="sl">Auctions Analyzed</div></div>
    <div class="st"><div class="sn">$25</div><div class="sl">Per Shapira Report</div></div>
  </div>
</section>

<div class="moat"><div class="moat-i">
  <div class="mi">🔍 <strong>Foreclosure + Tax Deed</strong> — both types, every county</div>
  <div class="msep"></div>
  <div class="mi">🧮 <strong>Shapira Max Bid Formula</strong> — exact ceiling before you bid</div>
  <div class="msep"></div>
  <div class="mi">🗺️ <strong>ZoneWise Zoning</strong> — setbacks, FAR, land use on every property</div>
</div></div>

<section class="sec" id="chat">
  <div class="ey">LIVE · FREE · NO SIGNUP</div>
  <h2 class="st2">Ask BidDeed.AI Anything</h2>
  <p class="ss">Real auction data. Shapira Formula. Responds in your language automatically.</p>
  <div class="lps">
    <span class="lp">🇺🇸 English</span><span class="lp">🇮🇱 עברית</span><span class="lp">🇪🇸 Español</span>
    <span class="lp">🇧🇷 Português</span><span class="lp">🇸🇦 العربية</span><span class="lp">🇷🇺 Русский</span><span class="lp">🇨🇳 中文</span>
  </div>
  <div class="cfw">
    <div class="cfb">
      <div class="cfd" style="background:#ef4444"></div>
      <div class="cfd" style="background:var(--orange);margin-left:5px"></div>
      <div class="cfd" style="background:var(--green);margin-left:5px"></div>
      <div class="cfl">BidDeed.AI · Streaming Auction Intelligence</div>
    </div>
    <iframe src="https://biddeed.ai/chat" width="100%" height="620" style="display:block;border:none" allow="clipboard-write" loading="lazy" title="BidDeed.AI Chat"></iframe>
  </div>
  <p class="cn">Free · No credit card · <a href="/subscribe?tier=investor">Upgrade to Investor $99/mo →</a></p>
</section>

<hr class="dv">

<section class="sec" id="proof">
  <div class="ey">REAL OUTCOME · VERIFIED TO THE CENT</div>
  <h2 class="st2">The Formula in Action</h2>
  <p class="ss">Marion County, Jul 20 2026 — published pre-sale, captured post-sale to the cent.</p>
  <div class="pc">
    <div class="pl">CASE 422021CA000414CAAXXX · MARION COUNTY · FORECLOSURE</div>
    <div class="pcase">14470 SE 91ST TER, Summerfield FL — Sale Jul 20, 2026</div>
    <div class="pgr">
      <div class="pi"><label>Entry Bid</label><value>$72,100</value></div>
      <div class="pi"><label>Shapira Max Bid</label><value class="o">$82,000</value></div>
      <div class="pi"><label>Actual Sale</label><value class="g">$73,501</value></div>
      <div class="pi"><label>Ceiling Call</label><value class="g">HELD ✓</value></div>
      <div class="pi"><label>Plaintiff Intel</label><value>$71,980</value></div>
      <div class="pi"><label>Buyer Equity</label><value class="g">~$26,400</value></div>
    </div>
    <div class="pv">✓ CEILING HELD — sale $8,499 below Shapira Max Bid. Disciplined bidder wins this lot.</div>
  </div>
</section>

<hr class="dv">

<section class="sec" id="how-it-works">
  <div class="ey">THE EVEREST ASCENT™</div>
  <h2 class="st2">12 Stages. Zero Guesswork.</h2>
  <p class="ss">AI agents handle every step — from courthouse docket to max bid decision.</p>
  <div class="pgrid">
    <div class="sg"><div class="sn2">STAGE 01</div><div class="sna">DiscoverWise</div><div class="sd">Scrape foreclosure + tax deed dockets from all 67 FL counties.</div></div>
    <div class="sg"><div class="sn2">STAGE 02</div><div class="sna">ScrapeWise</div><div class="sd">Pull property details, tax assessor data, and case information.</div></div>
    <div class="sg"><div class="sn2">STAGE 03</div><div class="sna">TitleWise</div><div class="sd">Search recorded documents — mortgages, liens, judgments.</div></div>
    <div class="sg"><div class="sn2">STAGE 04</div><div class="sna">LienWise</div><div class="sd">Analyze lien priority. Detect senior mortgage survival risk.</div></div>
    <div class="sg"><div class="sn2">STAGE 05</div><div class="sna">TaxWise</div><div class="sd">Check tax certificate status and delinquent amounts.</div></div>
    <div class="sg"><div class="sn2">STAGE 06</div><div class="sna">ZoneWise</div><div class="sd">Land use, zoning compatibility, density restrictions on every property.</div></div>
    <div class="sg"><div class="sn2">STAGE 07</div><div class="sna">ScoreWise</div><div class="sd">XGBoost ML predicts third-party purchase probability.</div></div>
    <div class="sg"><div class="sn2">STAGE 08</div><div class="sna">BidWise</div><div class="sd">Calculate your exact Shapira Max Bid ceiling before you bid.</div></div>
    <div class="sg"><div class="sn2">STAGE 09</div><div class="sna">DecisionWise</div><div class="sd">BID / REVIEW / SKIP with full reasoning chain and audit trail.</div></div>
    <div class="sg"><div class="sn2">STAGE 10</div><div class="sna">CMAwiser</div><div class="sd">Comparable market analysis with verified FL sale history.</div></div>
    <div class="sg"><div class="sn2">STAGE 11</div><div class="sna">DispoWise</div><div class="sd">Track disposition — flip, hold, wholesale, or pass.</div></div>
    <div class="sg"><div class="sn2">STAGE 12</div><div class="sna">VaultWise</div><div class="sd">Archive to database. Feed ML model for the next cycle.</div></div>
  </div>
</section>

<hr class="dv">

<section class="sec" id="gold-standard">
  <div class="ey">GOLD STANDARD CERTIFIED</div>
  <h2 class="st2">24 Florida Counties — Verified &amp; Ready</h2>
  <p class="ss">Verified title records, current tax data, reliable auction timing, documented clearance patterns. More counties certified weekly.</p>
  <div class="cgrid">
    <div class="cc">Brevard</div><div class="cc">Broward</div><div class="cc">Charlotte</div><div class="cc">Clay</div>
    <div class="cc">Duval</div><div class="cc">Franklin</div><div class="cc">Hardee</div><div class="cc">Hendry</div>
    <div class="cc">Hernando</div><div class="cc">Highlands</div><div class="cc">Hillsborough</div><div class="cc">Indian River</div>
    <div class="cc">Jackson</div><div class="cc">Lafayette</div><div class="cc">Leon</div><div class="cc">Monroe</div>
    <div class="cc">Nassau</div><div class="cc">Orange</div><div class="cc">Palm Beach</div><div class="cc">Pasco</div>
    <div class="cc">Putnam</div><div class="cc">St. Johns</div><div class="cc">Volusia</div><div class="cc">Washington</div>
  </div>
  <p style="margin-top:1.25rem;font-size:.8rem;color:var(--muted)">Uncertified county? <a href="mailto:hello@biddeed.ai" style="color:var(--orange)">hello@biddeed.ai</a></p>
</section>

<hr class="dv">

<section class="sec" id="pricing">
  <div class="ey">PRICING</div>
  <h2 class="st2">Start Free. Upgrade When Ready.</h2>
  <p class="ss">No credit card for free tier. Shapira reports $25 each, bundled by tier.</p>
  <div class="prgrid">
    <div class="pln live">
      <div class="pbadge hot">⚡ LIVE NOW</div>
      <div class="pname">Investor</div><div class="pprice">$99<sub>/month</sub></div>
      <div class="pdesc">Exact max bids, plaintiff intel, skip traces.</div>
      <ul class="pfeats">
        <li>Exact Shapira Max Bid</li><li>Unlimited property cards</li>
        <li>Plaintiff identity + max bid intel</li><li>Outcome scorecard</li>
        <li>10 Shapira S5 reports/mo</li><li>3 skip traces/mo</li>
        <li>1 county monitor</li><li>Daily digest all 67 counties</li>
      </ul>
      <a href="/subscribe?tier=investor" class="pcta hot">Start Investor — $99/mo</a>
    </div>
    <div class="pln coming">
      <div class="pbadge soon">COMING SOON</div>
      <div class="pname">Pro</div><div class="pprice">$199<sub>/month</sub></div>
      <div class="pdesc">Investor + full ZoneWise zoning on every property.</div>
      <ul class="pfeats">
        <li>Everything in Investor</li><li>Full ZoneWise zoning</li>
        <li>Setbacks, parking, height, FAR</li><li>10 Shapira reports/mo</li>
        <li>15 skip traces</li><li>3 monitors</li>
        <li class="sf">Lien stack + title chain (coming)</li>
      </ul>
      <span class="pcta off">Notify Me When Live</span>
    </div>
    <div class="pln coming">
      <div class="pbadge soon">COMING SOON</div>
      <div class="pname">Pro Plus</div><div class="pprice">$299<sub>/month</sub></div>
      <div class="pdesc">For serious deal hunters and firms.</div>
      <ul class="pfeats">
        <li>Everything in Pro</li><li>25 Shapira reports/mo</li>
        <li>Entitlement feasibility</li><li>50 skip traces</li><li>10 monitors</li>
        <li class="sf">Due diligence title report (coming)</li>
      </ul>
      <span class="pcta off">Notify Me When Live</span>
    </div>
  </div>
  <div class="pfree">
    <div class="pft"><strong>Free Forever — No Credit Card</strong><span>30-day snapshot · 3 previews/county · Blurred max bid · Daily email · AI chat any language</span></div>
    <a href="#chat" class="bp" style="font-size:.85rem;padding:10px 20px">Try Free Now</a>
  </div>
</section>

<hr class="dv">

<section class="sec">
  <div class="ey">PLATFORM CAPABILITIES</div>
  <h2 class="st2">Built by an Investor, for Investors</h2>
  <div class="fgrid">
    <div class="fi"><div class="fi-ic">🔍</div><div class="fi-t">Lien Discovery Agent</div><div class="fi-d">Searches actual recorded documents. Detects HOA foreclosures where senior mortgages survive.</div></div>
    <div class="fi"><div class="fi-ic">🧮</div><div class="fi-t">Shapira Max Bid Formula</div><div class="fi-d">20 years of auction experience. Exact ceiling from judgment, CMA, and county clearance priors.</div></div>
    <div class="fi"><div class="fi-ic">🗺️</div><div class="fi-t">ZoneWise Zoning</div><div class="fi-d">Setbacks, parking, height limits, FAR, land use, permitted uses, overlay districts on every property.</div></div>
    <div class="fi"><div class="fi-ic">🤖</div><div class="fi-t">ML Prediction Engine</div><div class="fi-d">XGBoost trained on 21,138 verified FL outcomes. Predicts third-party probability and clearing range.</div></div>
    <div class="fi"><div class="fi-ic">📊</div><div class="fi-t">Outcome Scorecard</div><div class="fi-d">Every Shapira report graded post-sale. Ceiling held or missed. Verified to the cent.</div></div>
    <div class="fi"><div class="fi-ic">🌐</div><div class="fi-t">Multilingual AI</div><div class="fi-d">English, Hebrew, Spanish, Portuguese, Arabic, Russian, Chinese — responds in your language automatically.</div></div>
  </div>
</section>

<section class="fcta">
  <h2>Stop Guessing.<br>Start Bidding Smart.</h2>
  <p>Florida's most advanced foreclosure and tax deed auction intelligence platform.</p>
  <div class="crow">
    <a href="#chat" class="bp">Try Free — No Signup</a>
    <a href="/subscribe?tier=investor" class="bs">Get Investor Access — $99/mo</a>
  </div>
</section>

<footer><p>© 2026 BidDeed.AI · Everest Capital USA · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a> &nbsp;·&nbsp; <a href="#pricing">Pricing</a> &nbsp;·&nbsp; <a href="/terms">Terms</a> &nbsp;·&nbsp; <a href="/privacy">Privacy</a> &nbsp;·&nbsp; <a href="/disclaimer">Disclaimer</a></p><p style="margin-top:.6rem;font-size:.72rem;color:var(--muted);max-width:820px;margin-left:auto;margin-right:auto">BidDeed.AI is an information and analytics platform, not a law firm or financial advisor. Nothing here is legal, financial, or investment advice. Foreclosure and tax-deed investing carries risk of loss. Verify all data independently and consult a licensed Florida attorney before bidding.</p></footer>
</body></html>`;

const TERMS_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Terms of Service — BidDeed.AI</title>
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#94a3b8;--border:#1e293b}
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
<footer>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></footer>
</body></html>`;

const PRIVACY_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Privacy Policy — BidDeed.AI</title>
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#94a3b8;--border:#1e293b}
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
<footer>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></footer>
</body></html>`;

const DISCLAIMER_HTML = `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Disclaimer — BidDeed.AI</title>
<style>
:root{--navy:#020617;--orange:#f59e0b;--text:#e2e8f0;--muted:#cbd5e1;--dim:#94a3b8;--border:#1e293b}
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
<footer>© 2026 BidDeed.AI · Everest Capital USA · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a> · <a href="mailto:hello@biddeed.ai">hello@biddeed.ai</a></footer>
</body></html>`;
