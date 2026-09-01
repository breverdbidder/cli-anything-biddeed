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
 * AUTH: HTTP Basic Auth (Workers-level shared secret), gated on
 * env.LMS_AUTH_USER / env.LMS_AUTH_PASS — real secrets set via
 * `wrangler secret put`, never embedded in source. This is the human-access
 * boundary; CF Access/Zero Trust was not chosen because it requires a Zero
 * Trust org already provisioned on this Cloudflare account, unverified as of
 * this build (see #19687 for the follow-up to unify auth with
 * everest-cfo-agent). Every route (including /healthz) requires auth.
 *
 * BILLING: /billing is a READ view onto finance.revenue_ledger via
 * lms_billing_view() — no invoice/Stripe logic is duplicated here.
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

function checkAuth(request, env) {
  const header = request.headers.get('Authorization') || '';
  if (!header.startsWith('Basic ')) return null;
  let decoded;
  try {
    decoded = atob(header.slice(6));
  } catch {
    return null;
  }
  const idx = decoded.indexOf(':');
  if (idx === -1) return null;
  const user = decoded.slice(0, idx);
  const pass = decoded.slice(idx + 1);
  if (!env.LMS_AUTH_USER || !env.LMS_AUTH_PASS) return null;
  if (timingSafeEqual(user, env.LMS_AUTH_USER) && timingSafeEqual(pass, env.LMS_AUTH_PASS)) {
    return user;
  }
  return null;
}

// The one place custom HTML can appear on a native-Basic-Auth-gated page:
// browsers render this 401 body when the user clicks Cancel on the prompt
// instead of entering credentials. That's the real estate for a Forgot
// Password button — the actual recovery path is
// POST /admin/reset-request, handled before checkAuth() below (see
// export default fetch()), which dispatches the same
// .github/workflows/lms-credential-reset.yml workflow Ariel would otherwise
// have to find and run manually from GitHub Actions (issue #19701).
function authShellPage(message) {
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
  button{font-family:inherit;font-size:.85rem;font-weight:600;background:#1E3A5F;color:#F59E0B;border:none;border-radius:4px;padding:.6rem 1.1rem;cursor:pointer;width:100%}
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

function unauthorized() {
  const body = authShellPage(`
    <p>Authentication required. Clicked Cancel? You'll land here whenever you don't have the current login.</p>
    <form method="POST" action="/admin/reset-request">
      <button type="submit">Forgot password?</button>
    </form>
    <p class="note">Triggers a real credential reset — a new login gets emailed to Ariel. Limited to once per hour.</p>`);
  return new Response(body, {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Winner Data LMS"',
      'content-type': 'text/html; charset=utf-8',
    },
  });
}

function resetResultPage(ok, detail) {
  const message = ok
    ? `<p>Reset triggered — check everestcapital8@gmail.com for the new login. It can take a minute to arrive.</p>`
    : `<p style="color:#F59E0B">${esc(detail)}</p>`;
  return authShellPage(`${message}<p class="note"><a class="link" href="/">Back to login</a></p>`);
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
  header{background:#1E3A5F;padding:1rem 1.5rem;display:flex;align-items:center;justify-content:space-between}
  header h1{color:#F59E0B;font-size:1.1rem;margin:0}
  nav a{color:#94a3b8;text-decoration:none;margin-left:1.25rem;font-size:.9rem;padding-bottom:.2rem}
  nav a:hover{color:#e2e8f0}
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
  return '<span style="color:#64748b">unreviewed</span>';
}

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
      <td>${fmtDate(b.created_at)}</td>
    </tr>`).join('');

  const body = `
    <h2>FF Batches — Review + Approval</h2>
    <p class="footer-note">Approving here calls the same public.ff_approve_batch() the chat-based flow used. Only leads marked <b>approved</b> below are eligible to send — an unreviewed lead is never sent.</p>
    <table>
      <thead><tr><th>Batch Date</th><th>Kind</th><th>Status</th><th>Leads</th><th>Enrichment</th><th>Per-Lead Review</th><th>Built</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="7" class="empty">No FF batches on file.</td></tr>'}</tbody>
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
      <td>${reviewBadge(l.review_decision)}${l.reviewed_by ? `<br><span style="color:#64748b;font-size:.72rem">${esc(l.reviewed_by)}, ${fmtDate(l.reviewed_at)}${l.review_note ? ` — ${esc(l.review_note)}` : ''}</span>` : ''}</td>
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
  await rpc(env, 'lms_ff_approve_batch', { p_batch_date: batchDate, p_actor: request.lmsActor });
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
    // password path (see unauthorized() above), so it must be reachable
    // without Basic Auth. Guarded by a rolling-hour rate limit
    // (lms_reset_request_trigger()) instead of an auth check.
    if (pathname === '/admin/reset-request' && request.method === 'POST') {
      return handleResetRequest(env);
    }

    const actor = checkAuth(request, env);
    if (!actor) return unauthorized();
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

      return new Response('Not found', { status: 404 });
    } catch (err) {
      return new Response(JSON.stringify({ ok: false, error: String(err) }), {
        status: 500,
        headers: { 'content-type': 'application/json' },
      });
    }
  },
};
