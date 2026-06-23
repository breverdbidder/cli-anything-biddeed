#!/usr/bin/env node
// stripe-setup.js — Create BidDeed Stripe products, prices, webhook; update Supabase
// Zero-HITL: reads all config from env. Run via stripe-setup.yml GHA workflow.

const Stripe = require('stripe');
const fs = require('fs');

const STRIPE_KEY = process.env.STRIPE_SECRET_KEY;
if (!STRIPE_KEY) { console.error('FATAL: STRIPE_SECRET_KEY not set'); process.exit(1); }

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;
const SUPABASE_ACCESS_TOKEN = process.env.SUPABASE_ACCESS_TOKEN;
const PROJECT_REF = 'mocerqjnksmhcjzxrewo';

if (!SUPABASE_URL || !SUPABASE_KEY) { console.error('FATAL: SUPABASE_URL or SUPABASE_KEY not set'); process.exit(1); }

const stripe = Stripe(STRIPE_KEY, { apiVersion: '2024-06-20' });
const LIVE = !STRIPE_KEY.startsWith('sk_test_');

const PRODUCTS = [
  { tier: 'investor',   name: 'BidDeed Investor',  desc: 'Foreclosure intelligence — Investor tier',              monthly: 9900,  annual: 99000,  s5: false },
  { tier: 'pro',        name: 'BidDeed Pro',        desc: 'Foreclosure intelligence — Pro tier',                   monthly: 19900, annual: 199000, s5: true  },
  { tier: 'proplus',    name: 'BidDeed Pro Plus',   desc: 'Foreclosure intelligence — Pro Plus tier',              monthly: 29900, annual: 299000, s5: true  },
  { tier: 'enterprise', name: 'BidDeed Enterprise', desc: 'Foreclosure intelligence — Enterprise (custom pricing)', monthly: null,  annual: null,   s5: true  },
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

const CREATE_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS stripe_products (
  id                      BIGSERIAL PRIMARY KEY,
  tier_id                 TEXT NOT NULL UNIQUE,
  name                    TEXT NOT NULL,
  product_id              TEXT NOT NULL DEFAULT 'PENDING',
  stripe_price_id_monthly TEXT,
  stripe_price_id_annual  TEXT,
  stripe_s5_price_id      TEXT,
  live_mode               BOOLEAN NOT NULL DEFAULT FALSE,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stripe_products_tier ON stripe_products(tier_id);
INSERT INTO stripe_products (tier_id, name) VALUES
  ('investor','BidDeed Investor'),('pro','BidDeed Pro'),
  ('proplus','BidDeed Pro Plus'),('enterprise','BidDeed Enterprise')
ON CONFLICT (tier_id) DO NOTHING;
`;

async function sbFetch(path, opts = {}) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...opts,
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
      ...(opts.headers || {}),
    },
  });
  const text = await res.text();
  return { status: res.status, body: text };
}

async function ensureTable() {
  // Check if table exists
  const { status } = await sbFetch('stripe_products?limit=1');
  if (status === 200) { console.log('  stripe_products already exists ✅'); return; }

  console.log(`  Table missing (HTTP ${status}) — creating via Management API`);
  if (!SUPABASE_ACCESS_TOKEN) {
    console.error('  FATAL: SUPABASE_ACCESS_TOKEN not set, cannot create table');
    process.exit(1);
  }

  const res = await fetch(`https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${SUPABASE_ACCESS_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: CREATE_TABLE_SQL }),
  });
  const body = await res.text();
  if (!res.ok) {
    console.error(`  Management API error (HTTP ${res.status}): ${body}`);
    process.exit(1);
  }
  console.log(`  Management API HTTP ${res.status}: ${body.slice(0, 200)}`);

  // Re-verify
  const { status: s2 } = await sbFetch('stripe_products?limit=1');
  if (s2 !== 200) { console.error(`  Table still not accessible (HTTP ${s2})`); process.exit(1); }
  console.log('  stripe_products created ✅');
}

async function main() {
  console.log(`=== BidDeed Stripe Setup (live_mode=${LIVE}) ===\n`);

  // P0: Ensure table exists
  console.log('--- stripe_products table ---');
  await ensureTable();

  const results = [];

  // P1: Create products + prices
  for (const p of PRODUCTS) {
    console.log(`\n--- ${p.name} ---`);

    const product = await stripe.products.create({
      name: p.name,
      description: p.desc,
      metadata: { tier: p.tier, app: 'biddeed' },
    });
    console.log(`  product_id:  ${product.id}`);

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
      console.log(`  monthly:     ${mp.id}  ($${p.monthly / 100}/mo)`);
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
      console.log(`  annual:      ${ap.id}  ($${p.annual / 100}/yr)`);
    }

    if (p.s5) {
      const s5 = await stripe.prices.create({
        product: product.id,
        ...S5_BASE,
        metadata: { ...S5_BASE.metadata, tier: p.tier },
      });
      s5PriceId = s5.id;
      console.log(`  s5_metered:  ${s5.id}  ($25/call, metered)`);
    }

    results.push({ tier: p.tier, product_id: product.id, monthlyPriceId, annualPriceId, s5PriceId });
  }

  // P2: Create webhook
  console.log('\n--- Webhook ---');
  const wh = await stripe.webhookEndpoints.create({
    url: 'https://biddeed.ai/api/stripe/webhook',
    enabled_events: WEBHOOK_EVENTS,
    metadata: { app: 'biddeed', env: LIVE ? 'live' : 'test' },
  });
  console.log(`  webhook_id:  ${wh.id}`);
  console.log(`  webhook_url: ${wh.url}`);
  console.log(`\nSTRIPE_WEBHOOK_SECRET=${wh.secret}`);
  fs.writeFileSync('/tmp/stripe_webhook_secret', wh.secret);

  // P3: Update Supabase
  console.log('\n--- Supabase stripe_products ---');
  for (const r of results) {
    const { status, body } = await sbFetch(`stripe_products?tier_id=eq.${r.tier}`, {
      method: 'PATCH',
      body: JSON.stringify({
        product_id: r.product_id,
        stripe_price_id_monthly: r.monthlyPriceId,
        stripe_price_id_annual: r.annualPriceId,
        stripe_s5_price_id: r.s5PriceId,
        live_mode: LIVE,
      }),
    });
    console.log(`  tier=${r.tier}: HTTP ${status}${status >= 300 ? ' ' + body.slice(0, 100) : ''}`);
    if (status >= 300) process.exitCode = 1;
  }

  // P4: Verify
  console.log('\n--- Verification ---');
  const { status: vs, body: vb } = await sbFetch(
    'stripe_products?select=tier_id,product_id,stripe_price_id_monthly,stripe_price_id_annual,stripe_s5_price_id,live_mode&order=tier_id'
  );
  console.log('\n### SQL VERIFICATION');
  console.log('```');
  console.log('SELECT tier_id, product_id, stripe_price_id_monthly, stripe_s5_price_id FROM stripe_products ORDER BY tier_id;');
  console.log('');
  const rows = JSON.parse(vb);
  if (!Array.isArray(rows)) { console.error('Unexpected response:', vb); process.exit(1); }
  rows.forEach(r => console.log(
    `  ${r.tier_id.padEnd(12)} prod=${r.product_id}  monthly=${r.stripe_price_id_monthly || 'null'}  s5=${r.stripe_s5_price_id || 'null'}`
  ));
  const pending = rows.filter(r => r.product_id === 'PENDING' || !r.product_id);
  if (pending.length > 0) {
    console.error(`\nFAIL: ${pending.length} tiers still PENDING: ${pending.map(r => r.tier_id).join(', ')}`);
    process.exit(1);
  }
  console.log('\nPASS: All 4 tiers have real prod_xxx IDs ✅');
  console.log(`Timestamp: ${new Date().toISOString()}`);
  console.log('```');

  // Summary
  console.log('\n=== SUMMARY ===');
  results.forEach(r => console.log(
    `${r.tier.padEnd(12)} prod=${r.product_id}  monthly=${r.monthlyPriceId || '-'}  annual=${r.annualPriceId || '-'}  s5=${r.s5PriceId || '-'}`
  ));
  console.log(`webhook:      ${wh.id}  (${wh.url})`);
}

main().catch(e => { console.error('FATAL:', e.message || e); process.exit(1); });
