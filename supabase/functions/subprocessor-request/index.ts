// subprocessor-request
//
// SUMMIT dispatch b7b02a64: gates the /security page's Vendor & Sub-Processor
// List behind a request form instead of a public link. Called by the CF
// Worker's POST /security/subprocessor-request (worker forwards the already
// field-validated body here with the anon key, same invocation pattern as
// biddeed-checkout / claude-router in src/worker.js).
//
// Logs every request to subprocessor_access_log (service role — the table's
// RLS only grants anon INSERT, so reads/writes beyond the initial insert
// happen here), then emails the requester the sub-processor list and pings
// the internal alerts inbox. Vault access uses the vault_secret() RPC
// (postgres+service_role only — see CLAUDE.md CREDENTIAL HANDLING), same
// pattern as posthog-alert-relay / stripe-webhook.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL');
const SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');

const H = {
  apikey: SERVICE_KEY,
  Authorization: `Bearer ${SERVICE_KEY}`,
  'Content-Type': 'application/json'
};

const VALID_REASONS = ['Due Diligence', 'Compliance Review', 'Vendor Assessment', 'Other'];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

async function rest(path, init = {}) {
  return fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...init,
    headers: { ...H, ...(init.headers ?? {}) }
  });
}

async function vaultSecret(name) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/vault_secret`, {
    method: 'POST',
    headers: H,
    body: JSON.stringify({ p_name: name })
  });
  if (!r.ok) return null;
  const v = await r.json();
  return typeof v === 'string' ? v : null;
}

async function logOps(task, status, severity, evidence) {
  await rest('agent_ops_log', {
    method: 'POST',
    headers: { Prefer: 'return=minimal' },
    body: JSON.stringify({
      dispatch_id: 'b7b02a64-b97f-493e-91fa-75befd64e6e4',
      task,
      status,
      severity,
      evidence: String(evidence).slice(0, 2000)
    })
  }).catch((e) => console.error('logOps failed', e));
}

async function sendEmail(to, subject, html) {
  const resendKey = await vaultSecret('resend_api_key');
  const fromAddr = await vaultSecret('alerts_from_email');
  if (!resendKey || !fromAddr) {
    return { ok: false, error: 'resend_api_key/alerts_from_email not in vault' };
  }
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${resendKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from: fromAddr, to: [to], subject, html })
  });
  if (!r.ok) {
    const errText = await r.text();
    return { ok: false, error: `resend ${r.status}: ${errText}`.slice(0, 500) };
  }
  return { ok: true };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const SUBPROCESSOR_LIST_HTML = `
<h2 style="font-family:Inter,sans-serif;color:#1E3A5F">BidDeed.AI Sub-Processor List</h2>
<table cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-family:Inter,sans-serif;font-size:14px">
<tr style="background:#1E3A5F;color:#fff"><th align="left">Vendor</th><th align="left">Purpose</th><th align="left">Location</th></tr>
<tr><td>Cloudflare</td><td>CDN, Workers, DNS</td><td>USA</td></tr>
<tr><td>Supabase</td><td>Database, Edge Functions</td><td>USA</td></tr>
<tr><td>Resend</td><td>Transactional Email</td><td>USA</td></tr>
<tr><td>Stripe</td><td>Payment Processing</td><td>USA</td></tr>
<tr><td>PostHog</td><td>Analytics, Error Monitoring</td><td>USA/EU</td></tr>
<tr><td>Anthropic</td><td>AI/LLM inference</td><td>USA</td></tr>
<tr><td>GitHub</td><td>Source Control, CI/CD</td><td>USA</td></tr>
<tr><td>Google</td><td>Gemini AI inference</td><td>USA</td></tr>
</table>
<p style="font-family:Inter,sans-serif;font-size:13px;color:#555">This list is current as of August 2026. We will notify you of material changes.</p>
`;

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'POST required' }), { status: 405, headers: { 'Content-Type': 'application/json' } });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'malformed JSON body' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }

  const name = typeof body.name === 'string' ? body.name.trim() : '';
  const company = typeof body.company === 'string' ? body.company.trim() : '';
  const email = typeof body.email === 'string' ? body.email.trim() : '';
  const reason = typeof body.reason === 'string' ? body.reason.trim() : '';
  const ip_hash = typeof body.ip_hash === 'string' ? body.ip_hash.slice(0, 128) : null;

  if (!name || !company || !email || !reason) {
    return new Response(JSON.stringify({ error: 'name, company, email, and reason are all required' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }
  if (!EMAIL_RE.test(email)) {
    return new Response(JSON.stringify({ error: 'invalid email format' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }
  if (!VALID_REASONS.includes(reason)) {
    return new Response(JSON.stringify({ error: 'invalid reason' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }

  const insertRes = await rest('subprocessor_access_log', {
    method: 'POST',
    headers: { Prefer: 'return=minimal' },
    body: JSON.stringify({ name, company, email, reason, ip_hash })
  });
  if (!insertRes.ok) {
    const errText = await insertRes.text();
    await logOps('subprocessor-request-log', 'BLOCKED', 'blocker', `insert failed: ${errText}`);
    return new Response(JSON.stringify({ error: 'could not log request' }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }

  const requesterSend = await sendEmail(
    email,
    'BidDeed.AI Sub-Processor List',
    `<p>Hi ${escapeHtml(name)},</p><p>As requested, here is BidDeed.AI's current sub-processor list.</p>${SUBPROCESSOR_LIST_HTML}`
  );

  const internalToAddr = await vaultSecret('alerts_to_email');
  let internalSend = { ok: false, error: 'alerts_to_email not in vault' };
  if (internalToAddr) {
    internalSend = await sendEmail(
      internalToAddr,
      'New sub-processor list request',
      `<p>New sub-processor list request from ${escapeHtml(name)} at ${escapeHtml(company)} (${escapeHtml(email)}).</p><p>Reason: ${escapeHtml(reason)}</p>`
    );
  }

  if (!requesterSend.ok || !internalSend.ok) {
    await logOps(
      'subprocessor-request-email',
      'BLOCKED',
      'warning',
      `requester=${JSON.stringify(requesterSend)} internal=${JSON.stringify(internalSend)}`
    );
    return new Response(JSON.stringify({ error: 'request logged but email delivery failed' }), { status: 502, headers: { 'Content-Type': 'application/json' } });
  }

  await logOps('subprocessor-request', 'VERIFIED', 'info', `request from ${company} logged + emailed`);
  return new Response(JSON.stringify({ success: true }), { headers: { 'Content-Type': 'application/json' } });
});
