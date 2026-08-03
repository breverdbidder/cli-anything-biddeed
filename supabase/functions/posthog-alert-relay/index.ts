// posthog-alert-relay
//
// Receives PostHog webhook POSTs ($exception or any custom alert event),
// relays to Telegram + email (Resend). Built to unblock issues #17635/#17631
// now that vault.telegram_chat_id, vault.telegram_bot_token and
// vault.posthog_project_key are confirmed live (issue #17634 chain).
//
// Auth: shared-secret header, checked against vault.posthog_webhook_secret.
// Accepts X-PostHog-Webhook-Secret or Authorization: Bearer <secret> — PostHog
// CDP "Fetch" destinations let you set either. Configure whichever the
// destination UI exposes; do not send the secret in the URL query string.
//
// Dedup: DB-backed via ops_alerts (source='posthog-alert-relay', ref=sha256
// of error+url), not in-memory — an in-memory counter resets on every cold
// start / differs per region, which for a low-volume alert relay means it
// would barely dedup anything. ops_alerts already exists and is queried by
// other ops tooling, so this reuses it rather than adding a new table.
//
// Vault access uses the vault_secret() RPC (postgres+service_role only —
// see CLAUDE.md CREDENTIAL HANDLING), same pattern as stripe-webhook.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL');
const SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');

const DEDUP_WINDOW_MS = 5 * 60 * 1000;

const H = {
  apikey: SERVICE_KEY,
  Authorization: `Bearer ${SERVICE_KEY}`,
  'Content-Type': 'application/json'
};

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

async function sha256Hex(s) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return Array.from(new Uint8Array(d)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function logOps(task, status, severity, evidence) {
  await rest('agent_ops_log', {
    method: 'POST',
    headers: { Prefer: 'return=minimal' },
    body: JSON.stringify({
      dispatch_id: '59f3574e-86d9-41f4-8ba9-2bd2a44eaade',
      task,
      status,
      severity,
      evidence: String(evidence).slice(0, 2000)
    })
  }).catch((e) => console.error('logOps failed', e));
}

// ------------------------------------------------------------- payload parse

function pick(...vals) {
  for (const v of vals) {
    if (v !== undefined && v !== null && v !== '') return v;
  }
  return null;
}

function extractAlert(body) {
  // Classic webhook actions POST a flat { event: "$exception", distinct_id,
  // properties, ... } object, where `event` is the event NAME (a string).
  // PostHog CDP "Fetch" destinations can instead nest the full event object
  // under body.event or body.data.event. Only descend into the nested form
  // when that field is actually an object — otherwise `event` is the name
  // and `body` itself is the event.
  let evt = body;
  if (body?.data?.event && typeof body.data.event === 'object') {
    evt = body.data.event;
  } else if (body?.event && typeof body.event === 'object') {
    evt = body.event;
  }
  if (!evt || typeof evt !== 'object') return null;

  const props = evt.properties ?? body.properties ?? {};
  const eventName = typeof evt.event === 'string' ? evt.event : (typeof body.event === 'string' ? body.event : null);
  const eventType = pick(eventName, 'unknown_event');
  const distinctId = pick(evt.distinct_id, body.distinct_id, props.distinct_id, 'unknown');
  const exceptionList = Array.isArray(props.$exception_list) ? props.$exception_list : [];
  const errorMessage = pick(
    props.$exception_message,
    exceptionList[0]?.value,
    props.message,
    props.error,
    evt.message,
    'no error message provided'
  );
  const url = pick(props.$current_url, props.url, evt.url, 'unknown');
  const timestamp = pick(evt.timestamp, body.timestamp, new Date().toISOString());

  return { eventType, distinctId, errorMessage, url, timestamp };
}

// ------------------------------------------------------------------ senders

async function sendTelegram(text) {
  const token = await vaultSecret('telegram_bot_token');
  const chatId = await vaultSecret('telegram_chat_id');
  if (!token || !chatId) return { ok: false, error: 'telegram_bot_token/telegram_chat_id not in vault' };
  const r = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'Markdown' })
  });
  if (!r.ok) {
    const errText = await r.text();
    return { ok: false, error: `telegram ${r.status}: ${errText}`.slice(0, 500) };
  }
  return { ok: true };
}

async function sendEmail(subject, html) {
  const resendKey = await vaultSecret('resend_api_key');
  const fromAddr = await vaultSecret('alerts_from_email');
  const toAddr = await vaultSecret('alerts_to_email');
  if (!resendKey || !fromAddr || !toAddr) {
    return { ok: false, error: 'resend_api_key/alerts_from_email/alerts_to_email not in vault' };
  }
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${resendKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from: fromAddr, to: [toAddr], subject, html })
  });
  if (!r.ok) {
    const errText = await r.text();
    return { ok: false, error: `resend ${r.status}: ${errText}`.slice(0, 500) };
  }
  return { ok: true };
}

// -------------------------------------------------------------------- dedup

async function isDuplicate(sig) {
  const since = new Date(Date.now() - DEDUP_WINDOW_MS).toISOString();
  const r = await rest(
    `ops_alerts?source=eq.posthog-alert-relay&ref=eq.${encodeURIComponent(sig)}&created_at=gte.${encodeURIComponent(since)}&select=id&limit=1`
  );
  if (!r.ok) return false; // fail open — don't block alerting on a read error
  const rows = await r.json();
  return Array.isArray(rows) && rows.length > 0;
}

async function recordAlert(sig, severity, message) {
  await rest('ops_alerts', {
    method: 'POST',
    headers: { Prefer: 'return=minimal' },
    body: JSON.stringify({ source: 'posthog-alert-relay', severity, ref: sig, message: message.slice(0, 2000) })
  }).catch((e) => console.error('ops_alerts insert failed', e));
}

// --------------------------------------------------------------------- main

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'POST required' }), { status: 405, headers: { 'Content-Type': 'application/json' } });
  }

  const configuredSecret = await vaultSecret('posthog_webhook_secret');
  if (!configuredSecret) {
    await logOps('posthog-alert-relay-deploy', 'BLOCKED', 'blocker', 'posthog_webhook_secret missing from vault at request time');
    return new Response(JSON.stringify({ error: 'webhook secret not configured' }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }

  const authHeader = req.headers.get('Authorization') ?? '';
  const bearerSecret = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
  const suppliedSecret = req.headers.get('X-PostHog-Webhook-Secret') ?? bearerSecret ?? '';
  if (suppliedSecret !== configuredSecret) {
    return new Response(JSON.stringify({ error: 'invalid webhook secret' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'malformed JSON body' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }

  const alert = extractAlert(body);
  if (!alert) {
    return new Response(JSON.stringify({ error: 'malformed payload — no event object found' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }

  const sig = await sha256Hex(`${alert.errorMessage}|${alert.url}`);
  if (await isDuplicate(sig)) {
    return new Response(JSON.stringify({ received: true, duplicate: true }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }

  const text = [
    `🚨 *PostHog Alert*`,
    `*Event:* ${alert.eventType}`,
    `*User:* ${alert.distinctId}`,
    `*Error:* ${alert.errorMessage}`,
    `*URL:* ${alert.url}`,
    `*Time:* ${alert.timestamp}`
  ].join('\n');

  const html = `<h2>PostHog Alert — ${alert.eventType}</h2>
<table style="font-family:sans-serif;font-size:14px;">
<tr><td><b>User:</b></td><td>${alert.distinctId}</td></tr>
<tr><td><b>Error:</b></td><td>${alert.errorMessage}</td></tr>
<tr><td><b>URL:</b></td><td>${alert.url}</td></tr>
<tr><td><b>Time:</b></td><td>${alert.timestamp}</td></tr>
</table>`;

  const [tg, email] = await Promise.all([
    sendTelegram(text),
    sendEmail(`PostHog Alert: ${alert.eventType} — ${alert.errorMessage}`.slice(0, 150), html)
  ]);

  await recordAlert(sig, tg.ok && email.ok ? 'info' : 'warn', `event=${alert.eventType} telegram_ok=${tg.ok} email_ok=${email.ok}${tg.error ? ' tg_err=' + tg.error : ''}${email.error ? ' email_err=' + email.error : ''}`);

  if (!tg.ok && !email.ok) {
    await logOps('posthog-alert-relay-deliver', 'BLOCKED', 'blocker', `both channels failed: telegram=${tg.error} email=${email.error}`);
  }

  return new Response(
    JSON.stringify({ received: true, telegram: tg.ok, email: email.ok }),
    { status: 200, headers: { 'Content-Type': 'application/json' } }
  );
});
