// BidDeed Stripe webhook handler — verifies signature, logs to stripe_webhook_events.
// Exported for the Vercel serverless function at api/stripe/webhook.js
// (biddeed.ai/api/stripe/webhook — the URL registered via scripts/stripe-setup.js).
//
// Idempotent: event_id is the stripe_webhook_events primary key, so Stripe
// retries/re-deliveries upsert rather than duplicate.
import Stripe from 'stripe';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

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
  }

  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ received: true }));
}
