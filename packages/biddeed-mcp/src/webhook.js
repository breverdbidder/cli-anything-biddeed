// BidDeed Stripe webhook handler — verifies signature, logs to stripe_webhook_events.
// Exported for the Vercel serverless function at api/stripe/webhook.js
// (biddeed.ai/api/stripe/webhook — the URL registered via scripts/stripe-setup.js).
//
// Idempotent: event_id is the stripe_webhook_events primary key, so Stripe
// retries/re-deliveries upsert rather than duplicate.
import Stripe from 'stripe';
import { predict_auction_outcome } from './tools/shapira.js';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

const WEBSITE_FIX_DISPATCH_ID = '93fc7abd-0189-4062-ae6f-934bc6ba3188';

let stripeClient = null;
function getStripe() {
  if (stripeClient) return stripeClient;
  stripeClient = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2024-06-20' });
  return stripeClient;
}

function readRawBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

async function sbFetch(path, opts = {}) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...opts,
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json',
      Prefer: 'return=minimal,resolution=merge-duplicates',
      ...(opts.headers || {}),
    },
  });
  if (res.status >= 300) throw new Error(`Supabase ${path} → HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`);
}

async function getVaultSecret(name) {
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_vault_secret_mcp`, {
      method: 'POST',
      headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ p_name: name }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data || null;
  } catch (_) { return null; }
}

async function logOpsResult(caseNumber, sessionId, status, severity, evidence) {
  await sbFetch('agent_ops_log', {
    method: 'POST',
    body: JSON.stringify({
      dispatch_id: WEBSITE_FIX_DISPATCH_ID,
      task: 's5_onetime_delivery',
      status,
      severity,
      evidence: `case_number=${caseNumber} session=${sessionId}: ${String(evidence).slice(0, 400)}`,
    }),
  }).catch(() => {});
}

async function resolveCustomerId(stripeCustomerId) {
  if (!stripeCustomerId) return null;
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/mcp_customers?stripe_customer_id=eq.${encodeURIComponent(stripeCustomerId)}&select=customer_id&limit=1`,
    { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
  );
  if (!res.ok) return null;
  const rows = await res.json();
  return rows[0]?.customer_id || null;
}

// SPRINT3 P0-3 — trial→paid upgrade completion. `stripe_checkout_sessions` rows
// are written by supabase/functions/biddeed-checkout at session-creation time
// with metadata (customer_id, tier_id) we trust here — the Checkout Session
// itself only echoes that same metadata back, so this never trusts anything
// Stripe didn't get directly from our own checkout-creation call.
async function processCheckoutCompletion(session) {
  const sessionId = session.id;
  const tierId = session.metadata?.tier_id;
  const customerId = session.metadata?.customer_id;
  if (!tierId || !customerId) return;

  await sbFetch(`stripe_checkout_sessions?session_id=eq.${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    body: JSON.stringify({
      status: 'complete',
      completed_at: new Date().toISOString(),
      stripe_customer_id: session.customer || null,
      stripe_subscription_id: session.subscription || null,
    }),
  });

  await sbFetch(`mcp_api_keys?customer_id=eq.${encodeURIComponent(customerId)}`, {
    method: 'PATCH',
    body: JSON.stringify({
      tier: tierId,
      stripe_customer_id: session.customer || null,
      expires_at: null,
      is_active: true,
      active: true,
      revoked_at: null,
    }),
  });
}

// WEBSITE-FIX (dispatch 93fc7abd) — the $25 one-time Shapira report purchase.
// Calls predict_auction_outcome's underlying report pipeline (composer.js +
// pdf.js) directly, NOT through the MCP billing wrapper — this purchase was
// already paid via Stripe Checkout, so it must never touch the taxi-meter.
async function processS5OnetimeCompletion(session) {
  const metadata = session.metadata || {};
  if (metadata.product !== 's5_onetime') return;

  // biddeed-checkout inserts the queue row at Checkout Session *creation*
  // time, when session.payment_intent is always still null — Stripe only
  // attaches it once the session completes. Filtering on payment_intent here
  // therefore never matches the stored (always-null) value and silently
  // no-ops every PATCH below (PostgREST returns 200 on a zero-row match).
  // session.id is the only key guaranteed to match the inserted row.
  const paymentIntent = session.payment_intent || null;
  const filter = `stripe_session_id=eq.${encodeURIComponent(session.id)}`;

  await sbFetch(`report_delivery_queue?${filter}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'paid', stripe_payment_intent: paymentIntent }),
  });

  const caseNumber = metadata.case_number;
  const county = metadata.county;
  const email = metadata.customer_email;
  if (!caseNumber || !county || !email) {
    await sbFetch(`report_delivery_queue?${filter}`, { method: 'PATCH', body: JSON.stringify({ status: 'failed', error: 'missing metadata on checkout session' }) });
    await logOpsResult(caseNumber || 'unknown', session.id, 'BLOCKED', 'blocker', 'missing case_number/county/customer_email metadata');
    return;
  }

  let result;
  try {
    result = await predict_auction_outcome({ case_number: caseNumber, county });
  } catch (err) {
    await sbFetch(`report_delivery_queue?${filter}`, { method: 'PATCH', body: JSON.stringify({ status: 'failed', error: `report generation error: ${err.message}`.slice(0, 500) }) });
    await logOpsResult(caseNumber, session.id, 'BLOCKED', 'blocker', `report generation error: ${err.message}`);
    return;
  }
  if (result?.error) {
    await sbFetch(`report_delivery_queue?${filter}`, { method: 'PATCH', body: JSON.stringify({ status: 'failed', error: result.message || result.error }) });
    await logOpsResult(caseNumber, session.id, 'BLOCKED', 'blocker', result.message || result.error);
    return;
  }

  const resendKey = await getVaultSecret('resend_api_key');
  const resendFrom = await getVaultSecret('resend_from_address');
  if (!resendKey || !resendFrom) {
    await sbFetch(`report_delivery_queue?${filter}`, { method: 'PATCH', body: JSON.stringify({ status: 'failed', error: 'resend_api_key/resend_from_address not configured in vault' }) });
    await logOpsResult(caseNumber, session.id, 'BLOCKED', 'blocker', 'resend_api_key/resend_from_address not configured');
    return;
  }

  const cover = result.report?.cover || {};
  const emailRes = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${resendKey}` },
    body: JSON.stringify({
      from: resendFrom,
      to: [email],
      subject: `Your BidDeed.AI SIGNAL$ Property Report — Case ${caseNumber}`,
      text: `Your SIGNAL$ Property Report for case ${caseNumber} (${county} County, FL) is attached.\n\n` +
        `Verdict: ${cover.verdict || 'see attached'}  ·  Investment Grade: ${cover.investment_grade || 'see attached'}\n\n` +
        `This is informational only — not legal, financial, or investment advice. Verify independently and consult a licensed Florida attorney before bidding.`,
      attachments: [{ filename: `biddeed-report-${caseNumber}.pdf`, content: result.pdf_base64 }],
    }),
  });

  if (!emailRes.ok) {
    const errText = await emailRes.text();
    await sbFetch(`report_delivery_queue?${filter}`, { method: 'PATCH', body: JSON.stringify({ status: 'failed', error: `resend send failed: ${errText}`.slice(0, 500) }) });
    await logOpsResult(caseNumber, session.id, 'BLOCKED', 'blocker', `resend send failed: ${errText}`);
    return;
  }

  await sbFetch(`report_delivery_queue?${filter}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'delivered', delivered_at: new Date().toISOString() }),
  });

  await logOpsResult(caseNumber, session.id, 'VERIFIED', 'info', `delivered to ${email}`);
}

export async function handleStripeWebhook(req, res) {
  if (req.method !== 'POST') {
    res.writeHead(405, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Method not allowed' }));
    return;
  }

  const sig = req.headers['stripe-signature'];
  if (!sig) {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Missing stripe-signature' }));
    return;
  }

  const rawBody = await readRawBody(req);

  let event;
  try {
    event = getStripe().webhooks.constructEvent(rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    process.stderr.write(`[stripe/webhook] signature verification failed: ${err.message}\n`);
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Invalid signature' }));
    return;
  }

  try {
    const stripeCustomerId = event.data?.object?.customer || null;
    const customerId = await resolveCustomerId(stripeCustomerId);

    await sbFetch('stripe_webhook_events', {
      method: 'POST',
      body: JSON.stringify({
        event_id: event.id,
        event_type: event.type,
        customer_id: customerId,
        payload: event.data.object,
        processed: true,
        processed_at: new Date().toISOString(),
      }),
    });
  } catch (err) {
    process.stderr.write(`[stripe/webhook] ${event.id} (${event.type}): ${err.message}\n`);
    // Best-effort failure record — response still 200s so Stripe doesn't hammer retries
    // for a Supabase-side issue that a human needs to look at (see `error` column).
    await sbFetch('stripe_webhook_events', {
      method: 'POST',
      body: JSON.stringify({
        event_id: event.id,
        event_type: event.type,
        payload: event.data.object,
        processed: false,
        error: err.message,
      }),
    }).catch(() => {});
  }

  // Additive post-processing — failures here are logged, never affect the
  // 200 response below (Stripe must not see this as a delivery failure/retry).
  if (event.type === 'checkout.session.completed') {
    await processCheckoutCompletion(event.data.object).catch(err => {
      process.stderr.write(`[stripe/webhook] checkout completion post-processing failed for ${event.id}: ${err.message}\n`);
    });
    await processS5OnetimeCompletion(event.data.object).catch(err => {
      process.stderr.write(`[stripe/webhook] s5_onetime completion post-processing failed for ${event.id}: ${err.message}\n`);
    });
  }

  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ received: true }));
}
