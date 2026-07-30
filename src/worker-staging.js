/**
 * BidDeed.AI Cloudflare Worker — src/worker-staging.js
 * Worker name: worker-biddeed-staging
 * Sprint 1: staging.biddeed.ai split-screen shell + county intelligence feed
 *
 * STANDALONE — imports nothing from src/worker.js. Additive only, zero
 * changes to production routes/tables. DEMO_MODE skips Stripe entirely.
 *
 * Routes:
 *   GET  /staging               → Split-screen chat + county feed shell
 *   GET  /staging/county-feed   → JSON top-8 counties from county_twin_snapshot
 *   POST /staging/chat/api      → Streaming SSE chat (Anthropic Haiku)
 *   POST /staging/chat/lead     → Email capture → Supabase demo_lead_profiles
 *   GET  /staging/demo-success  → Fake key delivery page (Stripe skipped)
 *   *    /staging/*             → 404 (anything else under /staging)
 *   *    (everything else)      → 404
 */

const DEMO_MODE = true;

// ── Constants — same values as src/worker.js ────────────────────────────────
const SUPABASE_URL = 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1MzI1MjYsImV4cCI6MjA4MDEwODUyNn0.ySFJIOngWWB0aqYra4PoGFuqcbdHOx1ZV6T9-klKQDw';
const DISCLAIMER_SHORT = 'Informational only — not legal, financial, or investment advice. Verify independently & consult a licensed attorney before bidding.';

const MARION_PROOF = {
  address: '14470 SE 91ST TER',
  city: 'Summerfield',
  soldAmount: 73501,
  maxBid: 82000,
  date: 'Jul 20 2026',
  type: 'Foreclosure',
};

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

// ── County intelligence feed ─────────────────────────────────────────────
async function fetchCountyFeed() {
  try {
    const url = `${SUPABASE_URL}/rest/v1/county_twin_snapshot?order=total_upcoming_30d.desc&limit=8&select=county,is_gold_standard,fc_upcoming_30d,td_upcoming_30d,fc_next_auction_date,td_next_auction_date,fc_avg_opening_bid,fc_min_opening_bid,fc_max_opening_bid,td_avg_opening_bid,td_min_opening_bid,td_max_opening_bid,total_upcoming_30d`;
    const res = await fetch(url, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } });
    if (!res.ok) return [];
    const rows = await res.json();
    return Array.isArray(rows) ? rows.slice(0, 6) : [];
  } catch(_) { return []; }
}

// ── Language detection (first 30 chars of last user message) ────────────
function detectLanguage(text) {
  const sample = String(text || '').slice(0, 30);
  if (/[֐-׿]/.test(sample)) return 'Hebrew';
  if (/[¿¡ñÑ]/.test(sample) || /\b(hola|cómo|como|qué|que|dónde|donde|cuánto|cuanto|gracias|cuándo)\b/i.test(sample)) return 'Spanish';
  return 'English';
}

// ── HTML: split-screen shell ─────────────────────────────────────────────
function buildStagingShell() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BidDeed.AI — Staging</title>
<meta name="robots" content="noindex,nofollow">
<style>
  :root{--navy:#1E3A5F;--amber:#F59E0B;--void:#020617;}
  *{box-sizing:border-box;}
  body{margin:0;font-family:Inter,system-ui,-apple-system,sans-serif;height:100vh;overflow:hidden;}
  .shell{display:flex;height:100vh;width:100vw;}
  .left{width:45%;background:var(--void);color:#e2e8f0;display:flex;flex-direction:column;min-width:320px;}
  .right{width:55%;background:#f8fafc;color:#0f172a;display:flex;flex-direction:column;overflow:hidden;}
  .logo{padding:20px 24px 10px;font-size:20px;font-weight:800;color:#fff;}
  .logo span{color:var(--amber);}
  .chat{flex:1;overflow-y:auto;padding:10px 24px;display:flex;flex-direction:column;gap:12px;}
  .msg{max-width:88%;padding:10px 14px;border-radius:10px;line-height:1.5;font-size:14px;white-space:pre-wrap;}
  .msg.user{align-self:flex-end;background:var(--navy);color:#fff;}
  .msg.assistant{align-self:flex-start;background:#0f2137;color:#e2e8f0;border:1px solid #1e3a5f;}
  .msg a{color:var(--amber);}
  .quick{display:flex;flex-wrap:wrap;gap:8px;padding:0 24px 10px;}
  .quick button{background:transparent;border:1px solid #334155;color:#cbd5e1;border-radius:20px;padding:6px 12px;font-size:12px;cursor:pointer;}
  .quick button:hover{border-color:var(--amber);color:var(--amber);}
  .input-bar{display:flex;align-items:center;gap:8px;padding:14px 24px 20px;border-top:1px solid #1e293b;}
  .input-bar input{flex:1;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:8px;padding:10px 12px;font-size:14px;outline:none;}
  .input-bar input:focus{border-color:var(--amber);}
  .clip,.send{background:transparent;border:none;color:#94a3b8;cursor:pointer;font-size:18px;padding:6px;}
  .send{background:var(--amber);color:#020617;border-radius:8px;padding:8px 14px;font-weight:700;font-size:13px;}
  .feed-header{display:flex;align-items:center;justify-content:space-between;padding:18px 24px;border-bottom:1px solid #e2e8f0;background:#fff;}
  .feed-title{display:flex;align-items:center;gap:8px;font-weight:700;font-size:15px;}
  .dot{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 1.6s infinite;}
  @keyframes pulse{0%{opacity:1;}50%{opacity:.3;}100%{opacity:1;}}
  #refresh{background:var(--navy);color:#fff;border:none;border-radius:6px;padding:6px 12px;font-size:12px;cursor:pointer;}
  .feed{flex:1;overflow-y:auto;padding:18px 24px;display:grid;grid-template-columns:1fr 1fr;gap:14px;align-content:start;}
  .card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px;}
  .card h3{margin:0 0 6px;font-size:15px;}
  .badge{color:var(--amber);}
  .card .row{font-size:12px;color:#475569;margin:2px 0;}
  .marion{grid-column:1/-1;background:#f0fdf4;border:1px solid #bbf7d0;border-left:4px solid #16a34a;border-radius:10px;padding:14px;margin-top:4px;}
  .marion .ceiling{color:#16a34a;font-weight:800;font-size:13px;}
  .marion .detail{font-size:12px;color:#334155;margin-top:4px;}
  .empty{color:#94a3b8;font-size:13px;padding:8px;}
</style>
</head>
<body>
<div class="shell">
  <div class="left">
    <div class="logo">BidDeed<span>.AI</span></div>
    <div id="chat" class="chat"></div>
    <div class="quick">
      <button data-msg="Tell me about upcoming Putnam tax deed auctions">Putnam tax deeds</button>
      <button data-msg="What Brevard foreclosures are coming up?">Brevard foreclosures</button>
      <button data-msg="How does BidDeed.AI work?">How does it work?</button>
      <button data-msg="Tell me about the Marion County proof">Marion proof</button>
    </div>
    <div class="input-bar">
      <button class="clip" title="Attach (coming soon)">📎</button>
      <input id="inp" placeholder="Ask about any Florida county..." autocomplete="off">
      <button class="send" id="snd">Send</button>
    </div>
  </div>
  <div class="right">
    <div class="feed-header">
      <div class="feed-title"><span class="dot"></span> County Intelligence Feed · Live</div>
      <button id="refresh">Refresh</button>
    </div>
    <div id="feed" class="feed"><div class="empty">Loading counties…</div></div>
  </div>
</div>
<script>
var H = [];
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function mdToHtml(s){
  return esc(s)
    .replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>')
    .replace(/\\[(.+?)\\]\\((https?:[^)]+)\\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\\n/g,'<br>');
}
function scrollBottom(){var c=document.getElementById('chat');c.scrollTop=c.scrollHeight;}
function addMsg(role,text){
  var d=document.createElement('div');
  d.className='msg '+role;
  d.innerHTML=mdToHtml(text);
  document.getElementById('chat').appendChild(d);
  scrollBottom();
  return d;
}
function send(){
  var inp=document.getElementById('inp');
  var text=inp.value.trim();
  if(!text)return;
  inp.value='';
  ask(text);
}
function ask(text){
  addMsg('user',text);
  H.push({role:'user',content:text});
  var bubble=addMsg('assistant','');
  var acc='';
  fetch('/staging/chat/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:H})})
    .then(function(res){
      var reader=res.body.getReader();
      var decoder=new TextDecoder();
      var buf='';
      function pump(){
        return reader.read().then(function(r){
          if(r.done)return;
          buf+=decoder.decode(r.value,{stream:true});
          var lines=buf.split('\\n');
          buf=lines.pop()||'';
          lines.forEach(function(line){
            if(line.indexOf('data: ')!==0)return;
            var data=line.slice(6).trim();
            if(data==='[DONE]')return;
            try{
              var evt=JSON.parse(data);
              if(evt.text){acc+=evt.text;bubble.innerHTML=mdToHtml(acc);scrollBottom();}
              if(evt.error){acc+='[error: '+evt.error+']';bubble.innerHTML=mdToHtml(acc);}
            }catch(e){}
          });
          return pump();
        });
      }
      return pump();
    })
    .then(function(){H.push({role:'assistant',content:acc});})
    .catch(function(e){bubble.innerHTML=mdToHtml('Connection error — please try again.');});
}
document.getElementById('snd').addEventListener('click',send);
document.getElementById('inp').addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();send();}});
document.querySelectorAll('.quick button').forEach(function(btn){
  btn.addEventListener('click',function(){ask(btn.getAttribute('data-msg'));});
});

function renderFeed(rows){
  var feed=document.getElementById('feed');
  if(!rows||!rows.length){feed.innerHTML='<div class="empty">No county data available.</div>';return;}
  var html=rows.map(function(r){
    var name=r.countyDisplay;
    var badge=r.isGold?' <span class="badge">⭐</span>':'';
    var bidRange=r.bidRange?('<div class="row">Avg opening bid: '+r.bidRange+'</div>'):'';
    return '<div class="card"><h3>'+esc(name)+badge+'</h3>'+
      '<div class="row">'+r.fc+' foreclosures / '+r.td+' tax deeds (30d)</div>'+
      '<div class="row">Next FC: '+esc(r.fcNext)+' · Next TD: '+esc(r.tdNext)+'</div>'+
      bidRange+
      '</div>';
  }).join('');
  html += '<div class="marion"><div class="ceiling">CEILING HELD</div><div class="detail">$73,501 sold · $82,000 max bid · 14470 SE 91ST TER · Jul 20 2026 · Foreclosure</div></div>';
  feed.innerHTML=html;
}
function loadFeed(){
  document.getElementById('feed').innerHTML='<div class="empty">Loading counties…</div>';
  fetch('/staging/county-feed').then(function(r){return r.json();}).then(function(rows){renderFeed(rows);}).catch(function(){
    document.getElementById('feed').innerHTML='<div class="empty">Feed unavailable.</div>';
  });
}
document.getElementById('refresh').addEventListener('click',loadFeed);
loadFeed();
</script>
</body>
</html>`;
}

// ── HTML: demo success page ──────────────────────────────────────────────
function buildDemoSuccessHtml() {
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>BidDeed.AI Staging — Demo Key</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Inter,system-ui,sans-serif;background:#020617;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}
.card{background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:40px;max-width:480px;text-align:center;}
h1{color:#F59E0B;font-size:20px;}
.key{font-family:'JetBrains Mono',monospace;background:#020617;border:1px solid #334155;border-radius:8px;padding:14px;margin:16px 0;font-size:16px;color:#22c55e;}
p{color:#94a3b8;font-size:13px;}
</style></head>
<body><div class="card">
<h1>DEMO MODE — Stripe checkout skipped</h1>
<div class="key">bd_staging_DEMO</div>
<p>This is a staging environment. In production, this key would be delivered after a real Stripe payment. No charge was made.</p>
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

      // ── GET /staging/demo-success ────────────────────────────────────
      if (path === '/staging/demo-success' && method === 'GET') {
        if (!DEMO_MODE) return new Response('Not found', { status: 404 });
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

      // ── POST /staging/chat/api — Streaming SSE (same Haiku pattern) ──
      if (path === '/staging/chat/api' && method === 'POST') {
        const cl = parseInt(request.headers.get('Content-Length') || '0', 10);
        if (cl > 20000) return new Response(JSON.stringify({ error: 'Request too large' }), { status: 413, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        let body = {};
        try { body = await request.json(); } catch(_) {
          return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        }

        const { messages } = body;
        if (!Array.isArray(messages) || messages.length === 0)
          return new Response(JSON.stringify({ error: 'messages required' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (messages.length > 20)
          return new Response(JSON.stringify({ error: 'Too many messages' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        const totalChars = messages.reduce((n, m) => n + String(m.content || '').length, 0);
        if (totalChars > 8000)
          return new Response(JSON.stringify({ error: 'Messages too long' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });
        if (!messages.every(m => ['user','assistant'].includes(m.role)))
          return new Response(JSON.stringify({ error: 'Invalid message role' }), { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } });

        const lastUserMsg = String([...messages].reverse().find(m => m.role === 'user')?.content || '');
        const lang = detectLanguage(lastUserMsg);
        const langInstruction = lang === 'English'
          ? 'Respond in English.'
          : `Respond in ${lang} — the user's message appears to be written in ${lang}.`;

        const systemPrompt = `You are BidDeed.AI, the Shapira Formula auction intelligence platform for Florida foreclosure and tax deed auctions. You have access to 13 counties with full S5 card capability. The Marion proof: 14470 SE 91ST TER Summerfield sold $73,501 on Jul 20 2026, our Shapira Max Bid was $82,000 — CEILING HELD. Help users understand Florida auction intelligence. Be direct and specific. When a user asks about a specific property or county, tell them what you know. UPL disclaimer: you provide information only, not legal or investment advice.

${langInstruction}
${DISCLAIMER_SHORT}`;

        const anthropicKey = env.ANTHROPIC_KEY;
        if (!anthropicKey) {
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
