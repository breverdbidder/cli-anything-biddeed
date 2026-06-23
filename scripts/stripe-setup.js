#!/usr/bin/env node
// stripe-setup.js — Create BidDeed Stripe products, prices, webhook; update Supabase
// Zero-HITL: reads all config from env. Run via stripe-setup.yml GHA workflow.

const Stripe = require('stripe');

const STRIPE_KEY = process.env.STRIPE_SECRET_KEY;
if (!STRIPE_KEY) { console.error('FATAL: STRIPE_SECRET_KEY not set'); process.exit(1); }

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;
if (!SUPABASE_URL || !SUPABASE_KEY) { console.error('FATAL: SUPABASE_URL or SUPABASE_KEY not set'); process.exit(1); }

const stripe = Stripe(STRIPE_KEY, { apiVersion: '2024-06-20' });
const LIVE = !STRIPE_KEY.startsWith('sk_test_');

const PRODUCTS = [
  { tier: 'investor',   name: 'BidDeed Investor',   desc: 'Foreclosure intelligence — Investor tier',    monthly: 9900,  annual: 99000,  s5: false },
  { tier: 'pro',        name: 'BidDeed Pro',         desc: 'Foreclosure intelligence — Pro tier',         monthly: 19900, annual: 199000, s5: true  },
  { tier: 'proplus',    name: 'BidDeed Pro Plus',    desc: 'Foreclosure intelligence — Pro Plus tier',    monthly: 29900, annual: 299000, s5: true  },
  { tier: 'enterprise', name: 'BidDeed Enterprise',  desc: 'Foreclosure intelligence — Enterprise (custom pricing)', monthly: null,  annual: null,   s5: true  },
];

const S5_BASE = {
  unit_amount: 2500,
  currency: 'usd',
  recurring: { interval: 'month', usage_type: 'metered', aggregate_usage: 'sum' },
  metadata: { stream_id: 's5', tool: 'predict_auction_outcome' },
};

const WEBHOOK_EVENTS = [
  'checkout.session.completed',
  'invoice.paid',
  'invoice.payment_failed',
  'customer.subscription.deleted',
  'customer.subscription.updated',
  'customer.subscription.created',
];

async function supabasePatch(path, body) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method: 'PATCH',
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
    },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  return { status: res.status, body: text };
}

async function supabaseGet(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
  });
  return res.json();
}

async function main() {
  console.log(`=== BidDeed Stripe Setup (live_mode=${LIVE}) ===\n`);

  const results = [];

  for (const p of PRODUCTS) {
    console.log(`--- ${p.name} ---`);

    const product = await stripe.products.create({
      name: p.name,
      description: p.desc,
      metadata: { tier: p.tier, app: 'biddeed' },
    });
    console.log(`  product_id:    ${product.id}`);

    let monthlyPriceId = null, annualPriceId = null, s5PriceId = null;

    if (p.monthly !== null) {
      const mp = await stripe.prices.create({
        product: product.id,
        unit_amount: p.monthly,
        currency: 'usd',
        recurring: { interval: 'month' },
        metadata: { tier: p.tier, interval_label: 'monthly' },
      });
      monthlyPriceId = mp.id;
      console.log(`  monthly:       ${mp.id}  ($${p.monthly / 100}/mo)`);
    }

    if (p.annual !== null) {
      const ap = await stripe.prices.create({
        product: product.id,
        unit_amount: p.annual,
        currency: 'usd',
        recurring: { interval: 'year' },
        metadata: { tier: p.tier, interval_label: 'annual' },
      });
      annualPriceId = ap.id;
      console.log(`  annual:        ${ap.id}  ($${p.annual / 100}/yr)`);
    }

    if (p.s5) {
      const s5 = await stripe.prices.create({
        product: product.id,
        ...S5_BASE,
        metadata: { ...S5_BASE.metadata, tier: p.tier },
      });
      s5PriceId = s5.id;
      console.log(`  s5_metered:    ${s5.id}  ($25/call)`);
    }

    results.push({ tier: p.tier, product_id: product.id, monthlyPriceId, annualPriceId, s5PriceId });
  }

  // Create webhook
  console.log('\n--- Webhook ---');
  const wh = await stripe.webhookEndpoints.create({
    url: 'https://biddeed.ai/api/stripe/webhook',
    enabled_events: WEBHOOK_EVENTS,
    metadata: { app: 'biddeed', env: LIVE ? 'live' : 'test' },
  });
  console.log(`  webhook_id:    ${wh.id}`);
  console.log(`  webhook_url:   ${wh.url}`);
  // Output for gh secret set in workflow step
  console.log(`\nSTRIPE_WEBHOOK_SECRET=${wh.secret}`);
  // Also write to /tmp for the workflow to capture
  require('fs').writeFileSync('/tmp/stripe_webhook_secret', wh.secret);

  // Update Supabase
  console.log('\n--- Supabase stripe_products ---');
  for (const r of results) {
    const patch = {
      product_id: r.product_id,
      stripe_price_id_monthly: r.monthlyPriceId,
      stripe_price_id_annual: r.annualPriceId,
      stripe_s5_price_id: r.s5PriceId,
      live_mode: LIVE,
    };
    const { status, body } = await supabasePatch(`stripe_products?tier_id=eq.${r.tier}`, patch);
    console.log(`  tier=${r.tier}: HTTP ${status}`);
    if (status >= 300) console.log(`    response: ${body.slice(0, 200)}`);
  }

  // Verify
  console.log('\n--- Verification ---');
  const rows = await supabaseGet('stripe_products?select=tier_id,product_id,stripe_price_id_monthly,stripe_price_id_annual,stripe_s5_price_id,live_mode&order=tier_id');
  console.log('\n### SQL VERIFICATION');
  console.log('```');
  console.log('SELECT tier_id, product_id, stripe_price_id_monthly, stripe_s5_price_id FROM stripe_products ORDER BY tier_id;');
  console.log('');
  if (Array.isArray(rows)) {
    rows.forEach(r => console.log(JSON.stringify(r)));
    const pending = rows.filter(r => r.product_id === 'PENDING' || !r.product_id);
    if (pending.length > 0) {
      console.error(`\nFAIL: ${pending.length} rows still have PENDING product_id`);
      process.exit(1);
    }
    console.log('\nAll 4 rows have real prod_xxx IDs ✅');
  } else {
    console.error('Unexpected response:', rows);
    process.exit(1);
  }
  console.log('```');
}

main().catch(e => { console.error('FATAL:', e.message || e); process.exit(1); });
