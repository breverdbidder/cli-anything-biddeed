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
 * DB ACCESS: same pattern as workers/winnerdata-ff — the winnerdata and
 * finance schemas are not exposed via PostgREST directly (documented
 * platform limitation).
 * All reads/writes go through public-schema SECURITY DEFINER RPC functions
 * (see supabase/migrations/20260901_winnerdata_lms_v1.sql), called via
 * /rest/v1/rpc/<fn> with the embedded anon key. org_id is validated inside
 * every function.
 *
 * AUTH: HTTP Basic Auth (Workers-level shared secret), gated on
 * env.LMS_AUTH_USER / env.LMS_AUTH_PASS — real secrets set via
 * `wrangler secret put`, never embedded in source. This is the human-access
 * boundary; CF Access/Zero Trust was not chosen because it requires a Zero
 * Trust org already provisioned on this Cloudflare account, unverified as of
 * this build. Every route (including /healthz) requires auth.
 *
 * BILLING: /billing is a READ view onto finance.revenue_ledger via
 * lms_billing_view() — no invoice/Stripe logic is duplicated here.
 */

const SUPABASE_URL = 'https://mocerqjnksmhcjzxrewo.supabase.co';
// Anon key — safe to embed, same as workers/winnerdata-ff. RPC-body org_id
// validation is the actual data boundary; Basic Auth above is the human
// access boundary.
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1MzI1MjYsImV4cCI6MjA4MDEwODUyNn0.ySFJIOngWWB0aqYra4PoGFuqcbdHOx1ZV6T9-klKQDw';

async function rpc(fn, body) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
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

function unauthorized() {
  return new Response('Authentication required', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="Winner Data LMS"' },
  });
}

// --- Layout --------------------------------------------------------------

function layout(title, activeNav, orgId, body) {
  const nav = [
    ['orgs', '/orgs', 'Clients'],
    ['leads', '/leads', 'Leads'],
    ['producers', '/producers', 'Producers'],
    ['billing', '/billing', 'Billing'],
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

async function viewOrgs() {
  const data = await rpc('lms_orgs_list', {});
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

async function viewOrgDetail(orgId) {
  const data = await rpc('lms_org_detail', { p_org_id: orgId });
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

async function viewLeads(orgId, params) {
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
  const data = await rpc('lms_leads_list', rpcParams);
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

async function viewProducers(orgId) {
  if (!orgId) {
    return layout('Producers', 'producers', null, '<p class="empty">Select a client from <a class="link" href="/orgs">Clients</a> first.</p>');
  }
  const data = await rpc('lms_producer_performance', { p_org_id: orgId });
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

async function viewBilling(orgId, params) {
  if (!orgId) {
    return layout('Billing', 'billing', null, '<p class="empty">Select a client from <a class="link" href="/orgs">Clients</a> first.</p>');
  }
  const status = params.get('status') || null;
  const data = await rpc('lms_billing_view', { p_org_id: orgId, p_status: status });
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

// --- Handlers ----------------------------------------------------------

async function handleFlag(request, leadId) {
  const form = await request.formData();
  const orgId = form.get('org_id');
  const reason = form.get('reason');
  await rpc('lms_flag_lead', { p_org_id: orgId, p_lead_id: leadId, p_actor: request.lmsActor, p_reason: reason });
  return Response.redirect(new URL(`/leads?org_id=${encodeURIComponent(orgId)}`, 'https://lms.winnerdataai.com').toString(), 303);
}

async function handleNote(request, producerId) {
  const form = await request.formData();
  const orgId = form.get('org_id');
  const note = form.get('note');
  await rpc('lms_update_producer_note', { p_org_id: orgId, p_producer_id: producerId, p_actor: request.lmsActor, p_note: note });
  return Response.redirect(new URL(`/producers?org_id=${encodeURIComponent(orgId)}`, 'https://lms.winnerdataai.com').toString(), 303);
}

async function handleHealthz() {
  const data = await rpc('lms_orgs_list', {});
  return new Response(JSON.stringify({ ok: true, orgs: (data.orgs || []).length }), {
    headers: { 'content-type': 'application/json' },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname, searchParams } = url;

    const actor = checkAuth(request, env);
    if (!actor) return unauthorized();
    request.lmsActor = actor;

    const orgId = searchParams.get('org_id');

    try {
      if (pathname === '/healthz') return handleHealthz();
      if (pathname === '/' || pathname === '/orgs') return new Response(await viewOrgs(), { headers: { 'content-type': 'text/html; charset=utf-8' } });

      const orgDetailMatch = pathname.match(/^\/orgs\/([0-9a-fA-F-]{36})$/);
      if (orgDetailMatch) return new Response(await viewOrgDetail(orgDetailMatch[1]), { headers: { 'content-type': 'text/html; charset=utf-8' } });

      if (pathname === '/leads' && request.method === 'GET') return new Response(await viewLeads(orgId, searchParams), { headers: { 'content-type': 'text/html; charset=utf-8' } });
      if (pathname === '/producers' && request.method === 'GET') return new Response(await viewProducers(orgId), { headers: { 'content-type': 'text/html; charset=utf-8' } });
      if (pathname === '/billing' && request.method === 'GET') return new Response(await viewBilling(orgId, searchParams), { headers: { 'content-type': 'text/html; charset=utf-8' } });

      const flagMatch = pathname.match(/^\/leads\/([0-9a-fA-F-]{36})\/flag$/);
      if (flagMatch && request.method === 'POST') return handleFlag(request, flagMatch[1]);

      const noteMatch = pathname.match(/^\/producers\/([0-9a-fA-F-]{36})\/note$/);
      if (noteMatch && request.method === 'POST') return handleNote(request, noteMatch[1]);

      return new Response('Not found', { status: 404 });
    } catch (err) {
      return new Response(JSON.stringify({ ok: false, error: String(err) }), {
        status: 500,
        headers: { 'content-type': 'application/json' },
      });
    }
  },
};
