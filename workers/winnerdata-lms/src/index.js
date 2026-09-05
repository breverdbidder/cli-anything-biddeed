/**
 * Winner Data LMS Worker — workers/winnerdata-lms/src/index.js
 * Built 2026-09-01 for winnerdataai.com client/producer management (LMS).
 * Internal/Ariel-facing only — not exposed to Mariam or any producer without
 * Ariel's explicit go-ahead (see wrangler.toml + README note).
 *
 * Architecture cloned from workers/winnerdata-ff/src/index.js: plain
 * Cloudflare Worker, server-rendered HTML, no build step, no framework, no
 * third-party CRM/LMS code vendored in.
 *
 * DB ACCESS: the winnerdata and finance schemas are not exposed via
 * PostgREST directly (documented platform limitation, same as
 * workers/winnerdata-ff). All reads/writes go through public-schema
 * SECURITY DEFINER RPC functions (see
 * supabase/migrations/20260901_winnerdata_lms_v1.sql +
 * 20260901c_winnerdata_lms_revoke_anon_execute.sql), called via
 * /rest/v1/rpc/<fn>. org_id is validated inside every function.
 *
 * SECURITY FIX (2026-09-01, same-day follow-up): the first version of this
 * file embedded the anon key as a source constant, mirroring
 * workers/winnerdata-ff. Because this repo is PUBLIC, that meant the RPC
 * EXECUTE grant to `anon` + the org_id (also public, committed in this same
 * migration) let anyone on the internet call lms_leads_list /
 * lms_flag_lead / lms_update_producer_note directly against Supabase,
 * bypassing this Worker's Basic Auth entirely — PII read + unaudited writes
 * with zero gate. Fixed by revoking `anon` EXECUTE on all seven lms_*
 * functions (service_role/postgres keep it) and switching this Worker to
 * env.SUPABASE_SERVICE_KEY, a real secret injected via `wrangler secret put`
 * and never committed to source. The human-access boundary (Basic Auth,
 * below) and the data-access boundary (service_role-only RPCs) are now both
 * real gates instead of one real gate plus one that only looked real.
 *
 * AUTH: real login page (username/password form) at /login, gated on
 * env.LMS_AUTH_USER / env.LMS_AUTH_PASS — real secrets set via
 * `wrangler secret put`, never embedded in source. This is the human-access
 * boundary; CF Access/Zero Trust was not chosen because it requires a Zero
 * Trust org already provisioned on this Cloudflare account, unverified as of
 * this build (see #19687 for the follow-up to unify auth with
 * everest-cfo-agent). Every route (including /healthz) requires a valid
 * session. HTTP Basic Auth was retired 2026-09-01: a browser's native Basic
 * Auth dialog is rendered outside the page DOM, so no HTML/link/button can
 * ever appear inside it — the "Forgot Password" affordance could only ever
 * live on the 401 page shown after clicking Cancel, which is confusing and
 * backwards. See the Session cookie section below for the replacement.
 *
 * BILLING: /billing is a READ view onto finance.revenue_ledger via
 * lms_billing_view() — no invoice/Stripe logic is duplicated here.
 *
 * FF BATCH APPROVAL (2026-09-02, issue #19745): unlike every other action in
 * this file, POST /ff-batches/:batch_date/approve does NOT use the shared
 * service-role rpc() helper. It calls public.ff_batch_approve_authenticated()
 * with a real Supabase Auth JWT (see rpcAsAuthenticatedAdmin()/
 * mintAdminAccessToken() below) so the resulting winnerdata.ff_batch_approvals
 * row cannot be forged by a service-role call — closing the exact gap a
 * 2026-09-01 incident exploited (an automated session approved+sent a real
 * batch using the service-role path with no human click involved).
 */

async function rpc(env, fn, body) {
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: {
      apikey: env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`rpc ${fn} failed: ${res.status} ${text}`);
  return text ? JSON.parse(text) : null;
}

// --- Authenticated approval path (issue #19745) ---------------------------
// public.ff_batch_approve_authenticated() is EXECUTE-granted to
// `authenticated` only (not service_role) and internally requires
// auth.uid()/auth.email() to be non-null and allow-listed in
// winnerdata.lms_admins -- see
// supabase/migrations/20260902i_winnerdata_ff_batch_approvals_gate.sql.
// The service-role `rpc()` helper above cannot satisfy that: a service-role
// JWT carries no `sub` claim, so auth.uid() is null and the RPC (and its
// underlying table's BEFORE INSERT trigger) reject it outright. This is the
// entire point -- it is what makes the 2026-09-01 incident (an automated
// session approving+sending via the service-role path with nobody having
// clicked anything) structurally impossible going forward.
//
// LMS_SUPABASE_AUTH_EMAIL/LMS_SUPABASE_AUTH_PASSWORD are a DEDICATED
// Supabase Auth identity (ariel+lms-admin@everestcapitalusa.com, provisioned
// 2026-09-02) held only as Worker secrets -- never sent to the browser, never
// logged. Signing in here, server-side, immediately after this Worker's own
// session-cookie gate has already confirmed a real human passed /login, is
// what "auth.uid() captured server-side" (the issue's own phrasing) means in
// practice: the click is real (gated by checkSession() below), and the JWT
// that click's approve request carries to Postgres is also real.
async function mintAdminAccessToken(env) {
  const res = await fetch(`${env.SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: { apikey: env.SUPABASE_ANON_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: env.LMS_SUPABASE_AUTH_EMAIL, password: env.LMS_SUPABASE_AUTH_PASSWORD }),
  });
  if (!res.ok) throw new Error(`admin sign-in failed: ${res.status}`);
  const data = await res.json();
  if (!data.access_token) throw new Error('admin sign-in returned no access_token');
  return data.access_token;
}

async function rpcAsAuthenticatedAdmin(env, fn, body) {
  const accessToken = await mintAdminAccessToken(env);
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: {
      apikey: env.SUPABASE_ANON_KEY,
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`rpc ${fn} (authenticated) failed: ${res.status} ${text}`);
  return text ? JSON.parse(text) : null;
}

function esc(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function money(cents) {
  if (cents === null || cents === undefined) return '$0.00';
  return `$${(Number(cents) / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(d) {
  if (!d) return '—';
  return String(d).slice(0, 10);
}

// --- Auth --------------------------------------------------------------

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

function verifyCredentials(user, pass, env) {
  if (!env.LMS_AUTH_USER || !env.LMS_AUTH_PASS) return false;
  return timingSafeEqual(user, env.LMS_AUTH_USER) && timingSafeEqual(pass, env.LMS_AUTH_PASS);
}

// --- Session cookie ------------------------------------------------------
// A signed, httpOnly, short-lived cookie issued on successful login (see
// handleLogin() below) so a visitor isn't re-prompted for credentials on
// every navigation. The HMAC key is derived from LMS_AUTH_USER/LMS_AUTH_PASS
// themselves (SHA-256 via Web Crypto) instead of a new secret — needs no
// extra `wrangler secret put` provisioning, and a credential reset (the
// existing /admin/reset-request flow) automatically invalidates every
// outstanding session, which is the correct behavior after a reset.
const SESSION_COOKIE = 'lms_session';
const SESSION_TTL_SECONDS = 4 * 60 * 60; // 4 hours

function base64url(bytes) {
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64urlDecode(s) {
  const pad = s.length % 4 === 0 ? '' : '='.repeat(4 - (s.length % 4));
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/') + pad);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

async function sessionSign(env, payload) {
  const enc = new TextEncoder();
  const keyDigest = await crypto.subtle.digest('SHA-256', enc.encode(`${env.LMS_AUTH_USER}:${env.LMS_AUTH_PASS}:lms-session-v1`));
  const key = await crypto.subtle.importKey('raw', keyDigest, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sigBuf = await crypto.subtle.sign('HMAC', key, enc.encode(payload));
  return base64url(new Uint8Array(sigBuf));
}

async function createSessionCookie(env, username) {
  const exp = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
  const payload = `${username}|${exp}`;
  const sig = await sessionSign(env, payload);
  const value = `${base64url(new TextEncoder().encode(payload))}.${sig}`;
  return `${SESSION_COOKIE}=${value}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${SESSION_TTL_SECONDS}`;
}

async function checkSession(request, env) {
  const cookieHeader = request.headers.get('Cookie') || '';
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${SESSION_COOKIE}=([^;]+)`));
  if (!match) return null;
  const [payloadB64, sig] = match[1].split('.');
  if (!payloadB64 || !sig) return null;
  let payload;
  try {
    payload = new TextDecoder().decode(base64urlDecode(payloadB64));
  } catch {
    return null;
  }
  const expectedSig = await sessionSign(env, payload);
  if (!timingSafeEqual(sig, expectedSig)) return null;
  const idx = payload.lastIndexOf('|');
  if (idx === -1) return null;
  const username = payload.slice(0, idx);
  const exp = Number(payload.slice(idx + 1));
  if (!username || !Number.isFinite(exp) || Math.floor(Date.now() / 1000) > exp) return null;
  return username;
}

// Shared brand shell for the pre-login pages (login form + reset result) —
// same card layout Basic Auth's 401 page used, now reused for a real login
// form instead of a browser popup.
function standalonePage(message) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Winner Data LMS</title>
<style>
  *{box-sizing:border-box}
  body{font-family:Inter,Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:0;display:flex;align-items:center;justify-content:center;min-height:100vh}
  .card{background:#0f172a;border:1px solid #1e3a5f;border-radius:8px;padding:2rem 2.25rem;max-width:380px;text-align:center}
  h1{color:#F59E0B;font-size:1.1rem;margin:0 0 .75rem}
  p{color:#94a3b8;font-size:.9rem;line-height:1.5;margin:0 0 1.25rem}
  label{display:block;text-align:left;font-size:.72rem;color:#64748b;margin:.6rem 0 .25rem}
  input{width:100%;font-family:inherit;font-size:.88rem;background:#020617;color:#e2e8f0;border:1px solid #1e3a5f;border-radius:4px;padding:.5rem .6rem}
  button{font-family:inherit;font-size:.85rem;font-weight:600;background:#1E3A5F;color:#F59E0B;border:none;border-radius:4px;padding:.6rem 1.1rem;cursor:pointer;width:100%;margin-top:1rem}
  .card form + form{margin-top:1rem}
  .link-btn{background:none;color:#F59E0B;text-decoration:underline;font-weight:400;width:auto;padding:0;font-size:.82rem;margin-top:0}
  .error{color:#f87171;font-size:.82rem;margin:.75rem 0 0;text-align:left}
  a.link{color:#F59E0B;text-decoration:none}
  .note{margin-top:1rem;font-size:.72rem;color:#475569}
</style>
</head><body>
  <div class="card">
    <h1>Winner Data LMS</h1>
    ${message}
  </div>
</body></html>`;
}

function loginPage(error) {
  return standalonePage(`
    <form method="POST" action="/login">
      <label for="username">Username</label>
      <input id="username" type="text" name="username" required autofocus autocomplete="username">
      <label for="password">Password</label>
      <input id="password" type="password" name="password" required autocomplete="current-password">
      ${error ? `<p class="error">${esc(error)}</p>` : ''}
      <button type="submit">Log in</button>
    </form>
    <form method="POST" action="/admin/reset-request">
      <button type="submit" class="link-btn">Forgot login?</button>
    </form>
    <p class="note">Triggers a real credential reset — a new username and password get emailed to Ariel. Limited to once per hour.</p>`);
}

async function handleLogin(request, env) {
  const form = await request.formData();
  const username = String(form.get('username') || '');
  const password = String(form.get('password') || '');
  if (!verifyCredentials(username, password, env)) {
    return new Response(loginPage('Incorrect username or password.'), {
      status: 401,
      headers: { 'content-type': 'text/html; charset=utf-8' },
    });
  }
  const cookie = await createSessionCookie(env, username);
  return new Response(null, {
    status: 303,
    headers: { Location: '/', 'Set-Cookie': cookie },
  });
}

function resetResultPage(ok, detail) {
  const message = ok
    ? `<p>Reset triggered — check everestcapital8@gmail.com for the new login. It can take a minute to arrive.</p>`
    : `<p style="color:#F59E0B">${esc(detail)}</p>`;
  return standalonePage(`${message}<p class="note"><a class="link" href="/login">Back to login</a></p>`);
}

// GH repo/workflow this endpoint dispatches — same one built for issue
// #19701 (.github/workflows/lms-credential-reset.yml), so there is a single
// reset path whether Ariel runs it from Actions directly or a visitor (or
// Ariel himself) hits this button.
const RESET_GH_REPO = 'breverdbidder/cli-anything-biddeed';
const RESET_WORKFLOW_FILE = 'lms-credential-reset.yml';

async function handleResetRequest(env) {
  let rl;
  try {
    rl = await rpc(env, 'lms_reset_request_trigger', {});
  } catch {
    return new Response(
      resetResultPage(false, 'Could not check the reset rate limit right now. Try again shortly.'),
      { status: 500, headers: { 'content-type': 'text/html; charset=utf-8' } },
    );
  }

  if (!rl.ok) {
    const mins = Math.max(1, Math.ceil((rl.retry_after_seconds || 0) / 60));
    return new Response(
      resetResultPage(false, `A reset was already triggered in the last hour. Try again in about ${mins} minute${mins === 1 ? '' : 's'}.`),
      { status: 429, headers: { 'content-type': 'text/html; charset=utf-8' } },
    );
  }

  try {
    const ghPat = await rpc(env, 'cli_anything_get_secret', { p_name: 'everest_gh_pat' });
    if (!ghPat) throw new Error('secret_unavailable');
    const dispatchRes = await fetch(
      `https://api.github.com/repos/${RESET_GH_REPO}/actions/workflows/${RESET_WORKFLOW_FILE}/dispatches`,
      {
        method: 'POST',
        headers: {
          Authorization: `token ${ghPat}`,
          Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'User-Agent': 'winnerdata-lms-worker',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ref: 'main' }),
      },
    );
    if (dispatchRes.status !== 204) {
      return new Response(
        resetResultPage(false, 'Could not start the reset workflow. Try again shortly, or ask Ariel to run it from GitHub Actions directly.'),
        { status: 502, headers: { 'content-type': 'text/html; charset=utf-8' } },
      );
    }
  } catch {
    return new Response(
      resetResultPage(false, 'Could not start the reset workflow. Try again shortly.'),
      { status: 502, headers: { 'content-type': 'text/html; charset=utf-8' } },
    );
  }

  return new Response(resetResultPage(true), { headers: { 'content-type': 'text/html; charset=utf-8' } });
}

// --- Layout --------------------------------------------------------------

function layout(title, activeNav, orgId, body) {
  const nav = [
    ['orgs', '/orgs', 'Clients'],
    ['leads', '/leads', 'Leads'],
    ['producers', '/producers', 'Producers'],
    ['billing', '/billing', 'Billing'],
    ['ff-batches', '/ff-batches', 'FF Batches'],
    ['reels', '/reels', 'Reels'],
  ].map(([key, path, label]) => {
    const href = orgId ? `${path}?org_id=${encodeURIComponent(orgId)}` : path;
    const active = key === activeNav ? ' style="color:#F59E0B;border-bottom:2px solid #F59E0B"' : '';
    return `<a href="${href}"${active}>${label}</a>`;
  }).join('');

  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>${esc(title)} — Winner Data LMS</title>
<style>
  *{box-sizing:border-box}
  body{font-family:Inter,Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:0}
  header{background:#1E3A5F;padding:1rem 1.5rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem}
  header h1{color:#F59E0B;font-size:1.1rem;margin:0}
  nav{display:flex;flex-wrap:wrap}
  nav a{color:#94a3b8;text-decoration:none;margin-left:1.25rem;font-size:.9rem;padding-bottom:.2rem}
  nav a:hover{color:#e2e8f0}
  @media (max-width:480px){ nav a{margin-left:0;margin-right:.9rem} main{padding:.85rem} }
  main{padding:1.5rem;max-width:1200px;margin:0 auto}
  table{width:100%;border-collapse:collapse;margin-top:1rem}
  th{background:#1E3A5F;color:#F59E0B;text-align:left;padding:.55rem .75rem;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em}
  td{padding:.6rem .75rem;border-bottom:1px solid #1e293b;font-size:.88rem}
  a.link{color:#F59E0B;text-decoration:none}
  .stat{display:inline-block;background:#1E3A5F;border-radius:6px;padding:.6rem 1.1rem;margin:.25rem .5rem .25rem 0;text-align:center}
  .stat-num{font-size:1.4rem;font-weight:700;color:#F59E0B;display:block}
  .stat-label{font-size:.72rem;color:#64748b}
  .badge{padding:.1rem .5rem;border-radius:4px;font-size:.72rem;font-weight:600}
  .badge-hot{background:#f87171;color:#020617}
  .badge-warm{background:#F59E0B;color:#020617}
  .badge-cold{background:#334155;color:#e2e8f0}
  form.inline{display:inline}
  input,select,button{font-family:inherit;font-size:.82rem;background:#0f172a;color:#e2e8f0;border:1px solid #1e3a5f;padding:.35rem .5rem;border-radius:4px}
  button{background:#1E3A5F;color:#F59E0B;cursor:pointer;border:none;padding:.4rem .8rem;border-radius:4px;font-weight:600}
  .filters{background:#0f172a;padding:1rem;border-radius:6px;margin-bottom:1rem;display:flex;gap:.75rem;flex-wrap:wrap;align-items:end}
  .filters label{display:block;font-size:.72rem;color:#64748b;margin-bottom:.25rem}
  .empty{color:#64748b;text-align:center;padding:2rem}
  .footer-note{color:#475569;font-size:.75rem;margin-top:1.5rem}
  .reel-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem;margin-top:1rem}
  .reel-card{background:#0f172a;border:1px solid #1e3a5f;border-radius:8px;padding:.85rem;display:flex;flex-direction:column;gap:.5rem}
  .reel-card video{width:100%;border-radius:6px;background:#000;max-height:320px}
  .reel-card h3{margin:0;font-size:.95rem;line-height:1.35;color:#e2e8f0}
  .reel-meta{font-size:.75rem;color:#94a3b8}
  .reel-actions{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.25rem}
  .reel-actions button{flex:1;min-width:80px}
  .btn-approve{background:#14532d;color:#4ade80}
  .btn-reject{background:#450a0a;color:#f87171}
  .btn-improve{background:#1E3A5F;color:#F59E0B}
  .day-group{margin-top:2rem}
  .day-group h2{color:#F59E0B;font-size:1rem;border-bottom:1px solid #1e3a5f;padding-bottom:.4rem}
  @media (max-width:480px){ .reel-grid{grid-template-columns:1fr} }
</style>
</head><body>
<header>
  <h1>Winner Data LMS</h1>
  <nav>${nav}</nav>
</header>
<main>${body}</main>
</body></html>`;
}

function temperatureBadge(t) {
  if (!t) return '—';
  return `<span class="badge badge-${esc(t)}">${esc(t).toUpperCase()}</span>`;
}

// --- Views -----------------------------------------------------------------

async function viewOrgs(env) {
  const data = await rpc(env, 'lms_orgs_list', {});
  const orgs = data.orgs || [];
  const rows = orgs.map((o) => `
    <tr>
      <td><a class="link" href="/orgs/${esc(o.org_id)}">${esc(o.name)}</a></td>
      <td>${o.is_internal ? 'Internal' : 'External'}</td>
      <td>${o.producer_count}</td>
      <td>${o.active_producer_count}</td>
      <td>${o.lead_count}</td>
      <td>${money(o.platform_fee_cents)}</td>
      <td>${fmtDate(o.created_at)}</td>
    </tr>`).join('');

  const body = `
    <h2>Clients / Organizations</h2>
    <table>
      <thead><tr><th>Org</th><th>Type</th><th>Producers</th><th>Active</th><th>Leads</th><th>Platform Fee</th><th>Created</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="7" class="empty">No organizations on file.</td></tr>'}</tbody>
    </table>`;
  return layout('Clients', 'orgs', null, body);
}

async function viewOrgDetail(env, orgId) {
  const data = await rpc(env, 'lms_org_detail', { p_org_id: orgId });
  if (!data.ok) {
    return layout('Client not found', 'orgs', null, `<p class="empty">${esc(data.reason)}</p>`);
  }
  const org = data.org;
  const producers = data.producers || [];
  const vol = data.lead_volume || {};

  const producerRows = producers.map((p) => `
    <tr>
      <td>${esc(p.full_name)}<br><span style="color:#64748b;font-size:.78rem">${esc(p.email) || 'no email on file'}</span></td>
      <td>${p.active ? '<span style="color:#22c55e">Active</span>' : '<span style="color:#64748b">Inactive</span>'}</td>
      <td style="font-size:.78rem">${(p.active_lines || []).join(', ') || '—'}</td>
      <td>${(p.license_states || []).join(', ') || '—'}</td>
      <td>${p.leads_routed_total}</td>
      <td>${p.win_rate_pct}%</td>
    </tr>`).join('');

  const body = `
    <p><a class="link" href="/orgs">&larr; All clients</a></p>
    <h2>${esc(org.name)}</h2>
    <div>
      <div class="stat"><span class="stat-num">${vol.total || 0}</span><span class="stat-label">Total Leads</span></div>
      <div class="stat"><span class="stat-num">${vol.last_30d || 0}</span><span class="stat-label">Last 30 Days</span></div>
      <div class="stat"><span class="stat-num" style="color:${vol.sla_breach_count > 0 ? '#f87171' : '#22c55e'}">${vol.sla_breach_count || 0}</span><span class="stat-label">SLA Breaches</span></div>
      <div class="stat"><span class="stat-num">${producers.length}</span><span class="stat-label">Producers</span></div>
    </div>
    <p style="margin-top:1rem">
      <a class="link" href="/leads?org_id=${esc(org.org_id)}">View leads &rarr;</a> &middot;
      <a class="link" href="/producers?org_id=${esc(org.org_id)}">View producer performance &rarr;</a> &middot;
      <a class="link" href="/billing?org_id=${esc(org.org_id)}">View billing &rarr;</a>
    </p>
    <h3 style="color:#94a3b8;font-size:.95rem;margin-top:1.5rem">Producers</h3>
    <table>
      <thead><tr><th>Producer</th><th>Status</th><th>Active Lines</th><th>Licensed</th><th>Leads Routed</th><th>Win Rate</th></tr></thead>
      <tbody>${producerRows || '<tr><td colspan="6" class="empty">No producers on file.</td></tr>'}</tbody>
    </table>`;
  return layout(org.name, 'orgs', org.org_id, body);
}

async function viewLeads(env, orgId, params) {
  if (!orgId) {
    return layout('Leads', 'leads', null, '<p class="empty">Select a client from <a class="link" href="/orgs">Clients</a> first.</p>');
  }
  const rpcParams = {
    p_org_id: orgId,
    p_producer_id: params.get('producer_id') || null,
    p_product_line: params.get('product_line') || null,
    p_date_from: params.get('date_from') || null,
    p_date_to: params.get('date_to') || null,
    p_limit: 200,
    p_offset: 0,
  };
  const data = await rpc(env, 'lms_leads_list', rpcParams);
  const leads = data.leads || [];

  const rows = leads.map((l) => `
    <tr>
      <td>${esc(l.entity_name || l.contact_name)}<br><span style="color:#64748b;font-size:.78rem">${esc(l.parcel_id) || 'no parcel'}</span></td>
      <td>${esc(l.product_line)}</td>
      <td>${temperatureBadge(l.temperature)}</td>
      <td>${esc(l.consent_status)}</td>
      <td>${l.sla_breach ? '<span style="color:#f87171">Breach</span>' : '<span style="color:#64748b">OK</span>'}</td>
      <td>${esc(l.producer_name) || '<span style="color:#64748b">unassigned</span>'}</td>
      <td>${fmtDate(l.created_at)}</td>
      <td>${l.flagged_at ? `<span style="color:#F59E0B" title="${esc(l.flagged_reason)}">Flagged</span>` : `
        <form class="inline" method="POST" action="/leads/${esc(l.lead_id)}/flag">
          <input type="hidden" name="org_id" value="${esc(orgId)}">
          <input type="text" name="reason" placeholder="reason" style="width:90px">
          <button type="submit">Flag</button>
        </form>`}</td>
    </tr>`).join('');

  const body = `
    <p><a class="link" href="/orgs/${esc(orgId)}">&larr; Client</a></p>
    <h2>Leads (${data.total || 0} total, showing ${leads.length})</h2>
    <form class="filters" method="GET" action="/leads">
      <input type="hidden" name="org_id" value="${esc(orgId)}">
      <div><label>Product line</label>
        <select name="product_line">
          <option value="">All</option>
          ${['auto','home','flood','umbrella','dwelling_landlord','commercial_bop','workers_comp','general_liability','builders_risk','other']
            .map((pl) => `<option value="${pl}"${params.get('product_line') === pl ? ' selected' : ''}>${pl}</option>`).join('')}
        </select>
      </div>
      <div><label>From</label><input type="date" name="date_from" value="${esc(params.get('date_from'))}"></div>
      <div><label>To</label><input type="date" name="date_to" value="${esc(params.get('date_to'))}"></div>
      <div><button type="submit">Filter</button></div>
    </form>
    <table>
      <thead><tr><th>Lead</th><th>Product</th><th>Temp</th><th>Consent</th><th>SLA</th><th>Producer</th><th>Created</th><th>Flag</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="8" class="empty">No leads match these filters.</td></tr>'}</tbody>
    </table>`;
  return layout('Leads', 'leads', orgId, body);
}

async function viewProducers(env, orgId) {
  if (!orgId) {
    return layout('Producers', 'producers', null, '<p class="empty">Select a client from <a class="link" href="/orgs">Clients</a> first.</p>');
  }
  const data = await rpc(env, 'lms_producer_performance', { p_org_id: orgId });
  const producers = data.producers || [];

  const rows = producers.map((p) => `
    <tr>
      <td>${esc(p.full_name)}<br><span style="color:#64748b;font-size:.78rem">${esc(p.email) || 'no email'}</span></td>
      <td>${p.active ? '<span style="color:#22c55e">Active</span>' : '<span style="color:#64748b">Inactive</span>'}</td>
      <td>${p.leads_routed_total}</td>
      <td>${p.leads_bound}</td>
      <td>${p.win_rate_pct}%</td>
      <td>${p.sla_breaches}</td>
      <td>${esc(p.notes) || '<span style="color:#64748b">—</span>'}</td>
      <td>
        <form class="inline" method="POST" action="/producers/${esc(p.producer_id)}/note">
          <input type="hidden" name="org_id" value="${esc(orgId)}">
          <input type="text" name="note" placeholder="add note" style="width:110px">
          <button type="submit">Save</button>
        </form>
      </td>
    </tr>`).join('');

  const body = `
    <p><a class="link" href="/orgs/${esc(orgId)}">&larr; Client</a></p>
    <h2>Producer Performance</h2>
    <table>
      <thead><tr><th>Producer</th><th>Status</th><th>Leads Routed</th><th>Bound</th><th>Win Rate</th><th>SLA Breaches</th><th>Notes</th><th></th></tr></thead>
      <tbody>${rows || '<tr><td colspan="8" class="empty">No producers on file.</td></tr>'}</tbody>
    </table>`;
  return layout('Producers', 'producers', orgId, body);
}

async function viewBilling(env, orgId, params) {
  if (!orgId) {
    return layout('Billing', 'billing', null, '<p class="empty">Select a client from <a class="link" href="/orgs">Clients</a> first.</p>');
  }
  const status = params.get('status') || null;
  const data = await rpc(env, 'lms_billing_view', { p_org_id: orgId, p_status: status });
  const events = data.events || [];
  const summary = data.summary || {};

  const rows = events.map((e) => `
    <tr>
      <td>${fmtDate(e.delivered_at)}</td>
      <td>${money(e.scenario_a_delivery_fee_cents)}${e.bound_at ? ` + ${money(e.scenario_a_success_fee_cents)} bind` : ''}</td>
      <td>${e.ledger_status ? `<span class="badge badge-${e.ledger_status === 'pending' ? 'warm' : 'cold'}">${esc(e.ledger_status).toUpperCase()}</span>` : '<span style="color:#f87171">no ledger row</span>'}</td>
      <td>${e.revenue_ledger_id ? money(e.amount_cents) : '—'}</td>
      <td>${esc((e.monetization_basis || {}).case_number) || '—'}</td>
    </tr>`).join('');

  const body = `
    <p><a class="link" href="/orgs/${esc(orgId)}">&larr; Client</a></p>
    <h2>Billing — read-only view of finance.revenue_ledger</h2>
    <div>
      <div class="stat"><span class="stat-num">${summary.total_events || 0}</span><span class="stat-label">Billable Events</span></div>
      <div class="stat"><span class="stat-num" style="color:#F59E0B">${money(summary.pending_cents)}</span><span class="stat-label">Pending</span></div>
      <div class="stat"><span class="stat-num">${money(summary.invoiced_cents)}</span><span class="stat-label">Invoiced</span></div>
      <div class="stat"><span class="stat-num" style="color:#22c55e">${money(summary.paid_cents)}</span><span class="stat-label">Paid</span></div>
    </div>
    <table>
      <thead><tr><th>Delivered</th><th>Fee</th><th>Ledger Status</th><th>Ledger Amount</th><th>Case #</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5" class="empty">No billable events for this client.</td></tr>'}</tbody>
    </table>
    <p class="footer-note">Sourced directly from finance.revenue_ledger via lms_billing_view() — no invoice math is duplicated here.</p>`;
  return layout('Billing', 'billing', orgId, body);
}

// FF Worker's own view route is /ff/<lead_id> (workers/winnerdata-ff/src/index.js).
// Same fallback URL as scripts/winnerdata_ff_digest_lib.py's FF_BASE_URL — keep
// both in sync. ff.winnerdataai.com is still NXDOMAIN (CF_API_TOKEN lacks
// Zone:DNS:Edit, see wrangler.toml in both winnerdata-ff and winnerdata-lms);
// workers.dev is the only live-verified reachable base as of 2026-09-01.
// Flip this back to https://ff.winnerdataai.com/ff once DNS is fixed.
const FF_BASE_URL = 'https://winnerdata-ff.brevardbidderai.workers.dev/ff';

function reviewBadge(decision) {
  if (decision === 'approved') return '<span style="color:#22c55e;font-weight:600">APPROVED</span>';
  if (decision === 'rejected') return '<span style="color:#f87171;font-weight:600">REJECTED</span>';
  if (decision === 'improvement_requested') return '<span style="color:#F59E0B;font-weight:600">IMPROVEMENT REQUESTED</span>';
  if (decision === 'fix_ready') return '<span style="color:#22c55e;font-weight:600">READY FOR RE-REVIEW</span>';
  return '<span style="color:#64748b">unreviewed</span>';
}

// GitHub commit link for a fix_ready row's fix_commit sha -- same repo every
// auto-dispatched fix issue lands in (winnerdata.ff_review_dispatch_sweep()
// only ever opens issues against breverdbidder/cli-anything-biddeed).
const FIX_COMMIT_REPO = 'https://github.com/breverdbidder/cli-anything-biddeed/commit/';

async function viewFFBatches(env) {
  const data = await rpc(env, 'lms_ff_batches_list', {});
  const batches = data.batches || [];

  const rows = batches.map((b) => `
    <tr>
      <td><a class="link" href="/ff-batches/${esc(b.batch_date)}">${esc(b.batch_date)}</a></td>
      <td>${esc(b.batch_kind)}</td>
      <td>${b.status === 'pending_approval' ? `<span style="color:#F59E0B;font-weight:600">PENDING APPROVAL</span>` : esc(b.status).toUpperCase()}</td>
      <td>${b.lead_count}</td>
      <td>${esc(b.enrichment_status)}</td>
      <td>${b.approved_count} approved / ${b.rejected_count} rejected / ${b.improvement_count} improvement / ${b.reviewed_count} of ${b.lead_count} reviewed</td>
      <td>${b.fix_ready_count > 0 ? `<span style="color:#22c55e;font-weight:600">${b.fix_ready_count} READY FOR RE-REVIEW</span>` : '—'}</td>
      <td>${fmtDate(b.created_at)}</td>
    </tr>`).join('');

  const body = `
    <h2>FF Batches — Review + Approval</h2>
    <p class="footer-note">Approving here signs in as a dedicated admin identity and calls public.ff_batch_approve_authenticated() with that real session's JWT (issue #19745) — the resulting approval record cannot be forged by any service-role/automated call. Only leads marked <b>approved</b> below are eligible to send — an unreviewed lead is never sent, and the send step independently re-verifies this approval record before it will send anything.</p>
    <table>
      <thead><tr><th>Batch Date</th><th>Kind</th><th>Status</th><th>Leads</th><th>Enrichment</th><th>Per-Lead Review</th><th>Ready for re-review</th><th>Built</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="8" class="empty">No FF batches on file.</td></tr>'}</tbody>
    </table>`;
  return layout('FF Batches', 'ff-batches', null, body);
}

async function viewFFBatchDetail(env, batchDate) {
  const data = await rpc(env, 'lms_ff_batch_detail', { p_batch_date: batchDate });
  if (!data.ok) {
    return layout('Batch not found', 'ff-batches', null, `<p class="empty">${esc(data.reason)}</p>`);
  }
  const batch = data.batch;
  const leads = data.leads || [];
  const canApprove = batch.status === 'pending_approval';
  const approvedCount = leads.filter((l) => l.review_decision === 'approved').length;

  const rows = leads.map((l) => {
    const ffLink = l.lead_id
      ? `<a class="link" href="${esc(FF_BASE_URL)}/${esc(l.lead_id)}" target="_blank" rel="noopener">View FF &rarr;</a>`
      : (l.pa_link ? `<a class="link" href="${esc(l.pa_link)}" target="_blank" rel="noopener">PA Link &rarr;</a>` : '<span style="color:#64748b">no link</span>');
    const caseNum = l.case_number;
    const reviewForm = caseNum ? `
      <form class="inline" method="POST" action="/ff-batches/${esc(batchDate)}/leads/${encodeURIComponent(caseNum)}/review">
        <select name="decision">
          <option value="approved"${l.review_decision === 'approved' ? ' selected' : ''}>Approve</option>
          <option value="rejected"${l.review_decision === 'rejected' ? ' selected' : ''}>Reject</option>
          <option value="improvement_requested"${l.review_decision === 'improvement_requested' ? ' selected' : ''}>Request improvement</option>
        </select>
        <input type="text" name="note" placeholder="note (optional)" value="${esc(l.review_note)}" style="width:130px">
        <button type="submit">Save</button>
      </form>` : '<span style="color:#64748b">no case_number — cannot review</span>';

    return `
    <tr>
      <td>${esc(l.entity_name)}<br><span style="color:#64748b;font-size:.78rem">${esc(l.county)} &middot; ${esc(l.sale_type)}</span></td>
      <td style="font-size:.78rem">${esc(caseNum) || '—'}</td>
      <td>${esc(l.confidence_tier) || 'not available'}</td>
      <td>${ffLink}</td>
      <td>${reviewBadge(l.review_decision)}${l.reviewed_by ? `<br><span style="color:#64748b;font-size:.72rem">${esc(l.reviewed_by)}, ${fmtDate(l.reviewed_at)}${l.review_note ? ` — ${esc(l.review_note)}` : ''}</span>` : ''}${l.review_decision === 'fix_ready' ? `<br><span style="color:#64748b;font-size:.72rem">${esc(l.fix_summary) || '(no summary)'}${l.fix_commit ? ` — <a class="link" href="${esc(FIX_COMMIT_REPO)}${esc(l.fix_commit)}" target="_blank" rel="noopener">${esc(String(l.fix_commit).slice(0, 7))}</a>` : ''}${l.issue_number ? ` (#${l.issue_number})` : ''}</span>` : ''}${l.review_decision === 'improvement_requested' && l.issue_number ? `<br><span style="color:#64748b;font-size:.72rem">dispatched as #${l.issue_number}</span>` : ''}</td>
      <td>${reviewForm}</td>
    </tr>`;
  }).join('');

  const body = `
    <p><a class="link" href="/ff-batches">&larr; All batches</a></p>
    <h2>FF Batch — ${esc(batch.batch_date)} (${esc(batch.batch_kind)})</h2>
    <div>
      <div class="stat"><span class="stat-num">${batch.lead_count}</span><span class="stat-label">Total Leads</span></div>
      <div class="stat"><span class="stat-num" style="color:#22c55e">${approvedCount}</span><span class="stat-label">Approved for Send</span></div>
      <div class="stat"><span class="stat-num" style="color:${batch.status === 'pending_approval' ? '#F59E0B' : '#94a3b8'}">${esc(batch.status).toUpperCase()}</span><span class="stat-label">Batch Status</span></div>
      <div class="stat"><span class="stat-num" style="color:#22c55e">${batch.fix_ready_count || 0}</span><span class="stat-label">Ready for re-review</span></div>
    </div>
    <p style="margin-top:1rem">
      ${canApprove
        ? `<form method="POST" action="/ff-batches/${esc(batchDate)}/approve" onsubmit="return confirm('Approve batch ${esc(batchDate)}? Only leads marked Approved above will be eligible to send — unreviewed/rejected leads are excluded.');">
             <button type="submit">Approve Batch (${approvedCount} of ${batch.lead_count} leads eligible to send)</button>
           </form>`
        : `<span class="footer-note">Batch is ${esc(batch.status)} — approval is only available while pending_approval.</span>`}
    </p>
    <table>
      <thead><tr><th>Buyer / Entity</th><th>Case #</th><th>Confidence</th><th>FF Link</th><th>Review</th><th>Set Review</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="6" class="empty">No leads in this batch.</td></tr>'}</tbody>
    </table>`;
  return layout(`Batch ${batch.batch_date}`, 'ff-batches', null, body);
}

// --- Reel/variant review (issue #20029) ---------------------------------
// Same authenticated-approval posture as FF batches (issue #19745): reads go
// through the shared service-role rpc() helper (public.lms_reel_variants_list,
// EXECUTE granted to service_role only); every write (approve/reject/
// improvement, single or batch) goes through rpcAsAuthenticatedAdmin() so the
// resulting winnerdata.reel_variant_review row carries a real auth.email(),
// never a service-role-forged decided_by (see
// supabase/migrations/20260905a_lms_reel_variant_review_20029.sql).
// winnerdata.reel_variant_review is Ariel's ground truth -- this Worker is
// the only place a row is ever written, and only when a real click hits one
// of the two POST routes below.

function decisionBadge(decision) {
  if (decision === 'approved') return '<span style="color:#22c55e;font-weight:600">APPROVED</span>';
  if (decision === 'rejected') return '<span style="color:#f87171;font-weight:600">REJECTED</span>';
  if (decision === 'improvement_requested') return '<span style="color:#F59E0B;font-weight:600">IMPROVEMENT REQUESTED</span>';
  return '<span style="color:#64748b">unreviewed</span>';
}

function qaSummary(v) {
  if (v.is_draft) return '<span style="color:#94a3b8">draft (pre-final-voice)</span>';
  if (v.qa_pass === true) return '<span style="color:#22c55e;font-weight:600">QA PASS</span>';
  if (v.qa_pass === false) {
    const failed = Object.entries(v.qa_scores || {}).filter(([, s]) => s && s.pass === false).map(([k]) => k);
    return `<span style="color:#f87171;font-weight:600">QA FAIL</span>${failed.length ? `<br><span style="color:#64748b;font-size:.7rem">${esc(failed.join(', '))}</span>` : ''}`;
  }
  return '<span style="color:#64748b">no QA yet</span>';
}

async function viewReelVariants(env) {
  const data = await rpc(env, 'lms_reel_variants_list', {});
  const variants = data.variants || [];

  const groups = new Map();
  for (const v of variants) {
    const key = `${v.auction_date}|${v.county}|${v.sale_type}|${v.reel_id}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(v);
  }

  const pendingIds = variants.filter((v) => !v.decision).map((v) => v.variant_id);

  const body = Array.from(groups.entries()).map(([key, vs]) => {
    const [auctionDate, county, saleType] = key.split('|');
    const cards = vs.map((v) => `
      <div class="reel-card">
        <video src="${esc(v.video_url)}" preload="metadata" controls playsinline muted></video>
        <h3>${esc(v.title)}</h3>
        <div class="reel-meta">variant ${esc(v.variant_key)} &middot; ${esc(v.archetype)} &middot; <a class="link" href="${esc(v.short_url)}" target="_blank" rel="noopener">${esc(v.short_url)}</a></div>
        <div class="reel-meta">QA: ${qaSummary(v)}</div>
        <div class="reel-meta">Status: ${decisionBadge(v.decision)}${v.decided_by ? `<br><span style="color:#64748b;font-size:.7rem">${esc(v.decided_by)}, ${fmtDate(v.decided_at)}</span>` : ''}</div>
        <form class="reel-actions" method="POST" action="/reels/${esc(v.variant_id)}/review">
          <input type="hidden" name="decision" value="approved">
          <button type="submit" class="btn-approve">Approve</button>
        </form>
        <form class="reel-actions" method="POST" action="/reels/${esc(v.variant_id)}/review">
          <input type="hidden" name="decision" value="rejected">
          <button type="submit" class="btn-reject">Reject</button>
        </form>
        <form class="reel-actions" method="POST" action="/reels/${esc(v.variant_id)}/review">
          <input type="hidden" name="decision" value="improvement_requested">
          <button type="submit" class="btn-improve">Request improvement</button>
        </form>
      </div>`).join('');

    return `
      <div class="day-group">
        <h2>${esc(fmtDate(auctionDate))} &middot; ${esc(county)} &middot; ${esc(saleType)}</h2>
        <div class="reel-grid">${cards}</div>
      </div>`;
  }).join('') || '<p class="empty">No reel variants on file.</p>';

  const batchForm = pendingIds.length
    ? `<form method="POST" action="/reels/batch-approve" onsubmit="return confirm('Approve all ${pendingIds.length} unreviewed variants shown below?');">
         ${pendingIds.map((id) => `<input type="hidden" name="variant_id" value="${esc(id)}">`).join('')}
         <button type="submit">Batch approve all ${pendingIds.length} unreviewed</button>
       </form>`
    : '<span class="footer-note">Every variant on this page already has a decision.</span>';

  const header = `
    <h2>Reels &amp; Variants — Review</h2>
    <p class="footer-note">Approve/reject/request-improvement here signs in as the same dedicated admin identity used for FF batches (issue #19745 pattern) and calls public.reel_variant_review_authenticated() — the resulting winnerdata.reel_variant_review row cannot be forged by any service-role/automated call. Only variants marked <b>Approve</b> can ever reach winnerdata.youtube_publish_queue (also requires qa_pass=true, a non-draft render, and a live 200 deal page — see docs/gtm/GTM_SOP_v1.md §5).</p>
    <div>${batchForm}</div>`;

  return layout('Reels & Variants', 'reels', null, header + body);
}

async function handleReelVariantReview(env, request, variantId) {
  const form = await request.formData();
  const decision = String(form.get('decision') || '');
  let result;
  try {
    result = await rpcAsAuthenticatedAdmin(env, 'reel_variant_review_authenticated', { p_variant_id: variantId, p_decision: decision, p_note: null });
  } catch (err) {
    return new Response(`Review failed: could not establish an authenticated admin session (${esc(String(err))}). Nothing was recorded.`, {
      status: 502, headers: { 'content-type': 'text/plain; charset=utf-8' },
    });
  }
  if (!result || !result.ok) {
    return new Response(`Review rejected: ${esc(JSON.stringify(result))}`, { status: 403, headers: { 'content-type': 'text/plain; charset=utf-8' } });
  }
  return Response.redirect(new URL('/reels', request.url).toString(), 303);
}

async function handleReelVariantBatchApprove(env, request) {
  const form = await request.formData();
  const variantIds = form.getAll('variant_id').map(String);
  let result;
  try {
    result = await rpcAsAuthenticatedAdmin(env, 'reel_variant_batch_approve_authenticated', { p_variant_ids: variantIds });
  } catch (err) {
    return new Response(`Batch approve failed: could not establish an authenticated admin session (${esc(String(err))}). Nothing was recorded.`, {
      status: 502, headers: { 'content-type': 'text/plain; charset=utf-8' },
    });
  }
  if (!result || !result.ok) {
    return new Response(`Batch approve rejected: ${esc(JSON.stringify(result))}`, { status: 403, headers: { 'content-type': 'text/plain; charset=utf-8' } });
  }
  return Response.redirect(new URL('/reels', request.url).toString(), 303);
}

// --- Handlers ----------------------------------------------------------

async function handleFlag(env, request, leadId) {
  const form = await request.formData();
  const orgId = form.get('org_id');
  const reason = form.get('reason');
  await rpc(env, 'lms_flag_lead', { p_org_id: orgId, p_lead_id: leadId, p_actor: request.lmsActor, p_reason: reason });
  // Redirect relative to the request's own origin, not a hardcoded domain —
  // lms.winnerdataai.com doesn't resolve yet (see wrangler.toml), so a
  // hardcoded origin would break this on the only currently-live workers.dev URL.
  return Response.redirect(new URL(`/leads?org_id=${encodeURIComponent(orgId)}`, request.url).toString(), 303);
}

async function handleNote(env, request, producerId) {
  const form = await request.formData();
  const orgId = form.get('org_id');
  const note = form.get('note');
  await rpc(env, 'lms_update_producer_note', { p_org_id: orgId, p_producer_id: producerId, p_actor: request.lmsActor, p_note: note });
  return Response.redirect(new URL(`/producers?org_id=${encodeURIComponent(orgId)}`, request.url).toString(), 303);
}

async function handleFFBatchLeadReview(env, request, batchDate, caseNumber) {
  const form = await request.formData();
  const decision = form.get('decision');
  const note = form.get('note') || null;
  await rpc(env, 'lms_ff_batch_lead_review', {
    p_batch_date: batchDate, p_case_number: caseNumber, p_decision: decision,
    p_actor: request.lmsActor, p_note: note,
  });
  return Response.redirect(new URL(`/ff-batches/${encodeURIComponent(batchDate)}`, request.url).toString(), 303);
}

async function handleFFBatchApprove(env, request, batchDate) {
  // issue #19745: approval must go through public.ff_batch_approve_authenticated()
  // with a real Supabase Auth JWT, not the old service-role
  // lms_ff_approve_batch() call -- that RPC being service-role-callable at
  // all (regardless of who/what called it) was the exact hole the 2026-09-01
  // incident exploited. If minting the admin JWT fails, this must surface as
  // a hard error, never a silent fall-back to the service-role path.
  let result;
  try {
    result = await rpcAsAuthenticatedAdmin(env, 'ff_batch_approve_authenticated', { p_batch_date: batchDate });
  } catch (err) {
    return new Response(
      `Approval failed: could not establish an authenticated admin session (${esc(String(err))}). `
      + 'Nothing was approved -- this is a hard failure, not a silent skip. Try again, or check '
      + 'LMS_SUPABASE_AUTH_EMAIL/LMS_SUPABASE_AUTH_PASSWORD Worker secrets.',
      { status: 502, headers: { 'content-type': 'text/plain; charset=utf-8' } },
    );
  }
  if (!result || !result.ok) {
    return new Response(
      `Approval rejected: ${esc(JSON.stringify(result))}`,
      { status: 403, headers: { 'content-type': 'text/plain; charset=utf-8' } },
    );
  }
  return Response.redirect(new URL(`/ff-batches/${encodeURIComponent(batchDate)}`, request.url).toString(), 303);
}

async function handleHealthz(env) {
  const data = await rpc(env, 'lms_orgs_list', {});
  return new Response(JSON.stringify({ ok: true, orgs: (data.orgs || []).length }), {
    headers: { 'content-type': 'application/json' },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname, searchParams } = url;

    // Public, unauthenticated recovery endpoint — this IS the forgot-
    // password path (see loginPage() above), so it must be reachable without
    // a session. Guarded by a rolling-hour rate limit
    // (lms_reset_request_trigger()) instead of an auth check.
    if (pathname === '/admin/reset-request' && request.method === 'POST') {
      return handleResetRequest(env);
    }

    if (pathname === '/login' && request.method === 'GET') {
      const existing = await checkSession(request, env);
      if (existing) return Response.redirect(new URL('/', request.url).toString(), 302);
      return new Response(loginPage(), { headers: { 'content-type': 'text/html; charset=utf-8' } });
    }
    if (pathname === '/login' && request.method === 'POST') {
      return handleLogin(request, env);
    }

    const actor = await checkSession(request, env);
    if (!actor) return Response.redirect(new URL('/login', request.url).toString(), 302);
    request.lmsActor = actor;

    const orgId = searchParams.get('org_id');

    try {
      if (pathname === '/healthz') return handleHealthz(env);
      if (pathname === '/' || pathname === '/orgs') return new Response(await viewOrgs(env), { headers: { 'content-type': 'text/html; charset=utf-8' } });

      const orgDetailMatch = pathname.match(/^\/orgs\/([0-9a-fA-F-]{36})$/);
      if (orgDetailMatch) return new Response(await viewOrgDetail(env, orgDetailMatch[1]), { headers: { 'content-type': 'text/html; charset=utf-8' } });

      if (pathname === '/leads' && request.method === 'GET') return new Response(await viewLeads(env, orgId, searchParams), { headers: { 'content-type': 'text/html; charset=utf-8' } });
      if (pathname === '/producers' && request.method === 'GET') return new Response(await viewProducers(env, orgId), { headers: { 'content-type': 'text/html; charset=utf-8' } });
      if (pathname === '/billing' && request.method === 'GET') return new Response(await viewBilling(env, orgId, searchParams), { headers: { 'content-type': 'text/html; charset=utf-8' } });
      if (pathname === '/ff-batches' && request.method === 'GET') return new Response(await viewFFBatches(env), { headers: { 'content-type': 'text/html; charset=utf-8' } });
      if (pathname === '/reels' && request.method === 'GET') return new Response(await viewReelVariants(env), { headers: { 'content-type': 'text/html; charset=utf-8' } });

      const flagMatch = pathname.match(/^\/leads\/([0-9a-fA-F-]{36})\/flag$/);
      if (flagMatch && request.method === 'POST') return handleFlag(env, request, flagMatch[1]);

      const noteMatch = pathname.match(/^\/producers\/([0-9a-fA-F-]{36})\/note$/);
      if (noteMatch && request.method === 'POST') return handleNote(env, request, noteMatch[1]);

      const ffBatchDetailMatch = pathname.match(/^\/ff-batches\/(\d{4}-\d{2}-\d{2})$/);
      if (ffBatchDetailMatch && request.method === 'GET') return new Response(await viewFFBatchDetail(env, ffBatchDetailMatch[1]), { headers: { 'content-type': 'text/html; charset=utf-8' } });

      const ffBatchApproveMatch = pathname.match(/^\/ff-batches\/(\d{4}-\d{2}-\d{2})\/approve$/);
      if (ffBatchApproveMatch && request.method === 'POST') return handleFFBatchApprove(env, request, ffBatchApproveMatch[1]);

      const ffBatchReviewMatch = pathname.match(/^\/ff-batches\/(\d{4}-\d{2}-\d{2})\/leads\/([^/]+)\/review$/);
      if (ffBatchReviewMatch && request.method === 'POST') return handleFFBatchLeadReview(env, request, ffBatchReviewMatch[1], decodeURIComponent(ffBatchReviewMatch[2]));

      if (pathname === '/reels/batch-approve' && request.method === 'POST') return handleReelVariantBatchApprove(env, request);

      const reelReviewMatch = pathname.match(/^\/reels\/([0-9a-fA-F-]{36})\/review$/);
      if (reelReviewMatch && request.method === 'POST') return handleReelVariantReview(env, request, reelReviewMatch[1]);

      return new Response('Not found', { status: 404 });
    } catch (err) {
      return new Response(JSON.stringify({ ok: false, error: String(err) }), {
        status: 500,
        headers: { 'content-type': 'application/json' },
      });
    }
  },
};
