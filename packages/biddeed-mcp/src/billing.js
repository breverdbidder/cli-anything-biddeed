import { insert, get } from './supabase.js';
import { TOOL_STREAM, STREAM_PRICE } from './constants.js';

// Streams with a monthly-allowance column on mcp_subscription_tiers. s4 is
// subscription (price $0), s6/s7 have no monthly cap column — nothing to
// gate for those.
const ALLOWANCE_STREAMS = new Set(['s1', 's2', 's3', 's5']);

let stripeClient = null;

async function getStripe() {
  if (stripeClient) return stripeClient;
  if (!process.env.STRIPE_SECRET_KEY) return null;
  try {
    const { default: Stripe } = await import('stripe');
    stripeClient = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2024-06-20' });
    return stripeClient;
  } catch {
    return null;
  }
}

// Failure A guard — do not execute a billable tool unless the charge/
// allowance check clears first. S1-S3 are metered internally against the
// customer's tier monthly allowance (mcp_subscription_tiers); S5 requires a
// Stripe customer on file (actual usage-record filing happens in
// recordBilling — a missing price/subscription-item there is a pricing
// config gap, not a customer-side gate). Fails open on infra errors: an
// allowance-check outage must not turn into a hard outage for paying
// customers — the caller logs the failure for follow-up.
export async function checkChargeAllowance({ customerRecord, toolName, streamId }) {
  const unitPrice = STREAM_PRICE[streamId] ?? 0;
  if (unitPrice === 0) return { ok: true }; // no per-call charge to gate (S4 subscription)

  if (streamId === 's5') {
    if (!customerRecord.stripe_customer_id) {
      return {
        ok: false,
        outcome: 'blocked_stripe',
        message: 'Shapira Formula requires an active paid subscription with billing on file. Upgrade at biddeed.ai/upgrade',
      };
    }
    return { ok: true };
  }

  if (!ALLOWANCE_STREAMS.has(streamId)) return { ok: true };

  const tierRows = await get(
    `mcp_subscription_tiers?tier_id=eq.${encodeURIComponent(customerRecord.tier)}&select=${streamId}_calls_monthly`
  );
  const limit = tierRows[0]?.[`${streamId}_calls_monthly`];
  if (limit === null || limit === undefined) return { ok: true }; // unlimited for this tier

  const now = new Date();
  const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)).toISOString();
  const usageRows = await get(
    `billing_events?customer_id=eq.${customerRecord.customer_id}&stream_id=eq.${streamId}&created_at=gte.${monthStart}&select=event_id`
  );

  if (usageRows.length >= limit) {
    return {
      ok: false,
      outcome: 'blocked_allowance',
      message: `Monthly ${streamId.toUpperCase()} allowance (${limit} calls) reached for ${customerRecord.tier} tier. Upgrade at biddeed.ai/upgrade`,
    };
  }
  return { ok: true };
}

// One row per charge decision — feeds v_mcp_charge_failure_rate_15m
// (Sentinel alerts at >2% over a rolling 15 min window). Non-blocking.
export function logChargeOutcome({ customerId, toolName, streamId, outcome }) {
  insert('mcp_charge_events', {
    customer_id: customerId || null,
    tool_name: toolName,
    stream_id: streamId || null,
    outcome,
  }).catch(err => {
    process.stderr.write(`[charge-events] ${toolName}: ${err.message}\n`);
  });
}

export async function recordBilling({
  toolName,
  customerRecord,
  params = {},
  resultSummary = '',
  county = null,
  certStatus = null,
  modelVersion = null,
}) {
  const streamId = TOOL_STREAM[toolName] || 's1';
  const unitPrice = STREAM_PRICE[streamId] ?? 0;

  // Strip PII before storing params
  const safeParams = Object.fromEntries(
    Object.entries(params).filter(([k]) => !['ssn', 'dob', 'tax_id', 'password'].includes(k))
  );

  let stripeUsageRecordId = null;
  const needsStripeMetering = streamId === 's5' && !!customerRecord.stripe_customer_id;
  if (needsStripeMetering) {
    stripeUsageRecordId = await fileStripeS5Usage(customerRecord).catch(() => null);
  }

  // Settle immediately for non-metered streams; for S5+Stripe, settled only when usage record filed
  const settled = !needsStripeMetering || stripeUsageRecordId !== null;

  const event = {
    tool_name: toolName,
    stream_id: streamId,
    customer_id: customerRecord.customer_id,
    key_prefix: customerRecord.key_prefix,
    unit_price_usd: unitPrice,
    billed_amount: unitPrice,
    settled,
    settled_at: settled ? new Date().toISOString() : null,
    cert_status: certStatus,
    model_version: modelVersion,
    county: county || params.county || null,
    params: safeParams,
    result_summary: String(resultSummary || '').slice(0, 500),
    stripe_usage_record_id: stripeUsageRecordId,
    stripe_meter_id: stripeUsageRecordId,
  };

  // Caller invokes this without awaiting (fire-and-forget w.r.t. the tool
  // response) — billing must never block or fail the client's response. The
  // returned event_id lets the caller link mcp_idempotency_keys.billing_event_id.
  try {
    const rows = await insert('billing_events', event);
    return rows?.[0]?.event_id || null;
  } catch (err) {
    process.stderr.write(`[billing] ${toolName}: ${err.message}\n`);
    return null;
  }
}

async function fileStripeS5Usage(customerRecord) {
  const stripe = await getStripe();
  if (!stripe) return null;

  const products = await get(
    `stripe_products?tier_id=eq.${encodeURIComponent(customerRecord.tier)}&select=stripe_s5_price_id&limit=1`
  );
  const priceId = products[0]?.stripe_s5_price_id;
  if (!priceId) return null;

  const subs = await stripe.subscriptions.list({
    customer: customerRecord.stripe_customer_id,
    status: 'active',
    limit: 5,
  });

  for (const sub of subs.data) {
    const item = sub.items.data.find(i => i.price.id === priceId);
    if (item) {
      const record = await stripe.subscriptionItems.createUsageRecord(item.id, {
        quantity: 1,
        action: 'increment',
        timestamp: Math.floor(Date.now() / 1000),
      });
      return record.id;
    }
  }

  return null;
}
