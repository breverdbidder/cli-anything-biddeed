import { insert, get } from './supabase.js';
import { TOOL_STREAM, STREAM_PRICE } from './constants.js';

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

export async function recordBilling({
  toolName,
  customerRecord,
  params = {},
  resultSummary = '',
  county = null,
  certStatus = null,
}) {
  const streamId = TOOL_STREAM[toolName] || 's1';
  const unitPrice = STREAM_PRICE[streamId] ?? 0;

  // Strip PII before storing params
  const safeParams = Object.fromEntries(
    Object.entries(params).filter(([k]) => !['ssn', 'dob', 'tax_id', 'password'].includes(k))
  );

  let stripeUsageRecordId = null;
  if (streamId === 's5' && customerRecord.stripe_customer_id) {
    stripeUsageRecordId = await fileStripeS5Usage(customerRecord).catch(() => null);
  }

  const event = {
    tool_name: toolName,
    stream_id: streamId,
    customer_id: customerRecord.customer_id,
    key_prefix: customerRecord.key_prefix,
    unit_price_usd: unitPrice,
    billed_amount: unitPrice,
    settled: false,
    cert_status: certStatus,
    county: county || params.county || null,
    params: safeParams,
    result_summary: String(resultSummary || '').slice(0, 500),
    stripe_usage_record_id: stripeUsageRecordId,
  };

  // Non-blocking — billing failure must never block tool response
  insert('billing_events', event).catch(err => {
    process.stderr.write(`[billing] ${toolName}: ${err.message}\n`);
  });
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
