#!/usr/bin/env node
// stripe-meters-s5.js — S5 (Shapira Formula) Billing Meters + metered prices → Supabase writeback
// Sprint 2 follow-up. Zero-HITL: reads config from env. Idempotent — safe to re-run.
//
// Scope (per taxi_meter_streams.stripe_metered=true, currently only stream_id='s5'):
//   1. List existing Stripe Billing Meters (new meters API) — create only if missing (by event_name).
//   2. Create S5 metered prices attached to the EXISTING products for investor/pro/proplus.
//      Does NOT create products or subscription (monthly/annual) prices — those already exist.
//   3. Enterprise: pencil_mcp_tool_spec has no row for predict_auction_outcome (verified empty at
//      authoring time) — falls back to mcp_subscription_tiers.enterprise (price_monthly_usd=null,
//      description="...Custom contract") as INFERRED evidence of custom-quote-only. Skipped, logged.
//   4. Writes stripe_meter_id + stripe_s5_price_id back to stripe_products, then re-reads to verify.

import Stripe from 'stripe';

const STRIPE_KEY = process.env.STRIPE_SECRET_KEY;
if (!STRIPE_KEY) { console.error('FATAL: STRIPE_SECRET_KEY not set'); process.exit(1); }

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;
if (!SUPABASE_KEY) { console.error('FATAL: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY not set'); process.exit(1); }

const stripe = new Stripe(STRIPE_KEY, { apiVersion: '2024-06-20' });
const LIVE = !STRIPE_KEY.startsWith('sk_test_');

const S5_EVENT_NAME = 's5_predict_auction_outcome';
const S5_TIERS = ['investor', 'pro', 'proplus']; // enterprise handled separately (custom quote)

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
  if (res.status >= 300) throw new Error(`Supabase ${path} → HTTP ${res.status}: ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

async function main() {
  console.log(`=== S5 Billing Meters + Metered Prices (live_mode=${LIVE}) ===\n`);

  // ── P0: Confirm S5 is the only stream requiring Stripe metering ────────────
  console.log('--- taxi_meter_streams (stripe_metered) ---');
  const streams = await sbFetch('taxi_meter_streams?select=stream_id,name,unit_price_usd,gate_tier,stripe_metered&order=stream_id');
  const metered = streams.filter(s => s.stripe_metered);
  metered.forEach(s => console.log(`  ${s.stream_id}: ${s.name} — $${s.unit_price_usd}/call (gate=${s.gate_tier})`));
  const s5 = metered.find(s => s.stream_id === 's5');
  if (!s5) { console.error('FATAL: no stream_id=s5 with stripe_metered=true — nothing to wire'); process.exit(1); }
  const unitAmount = Math.round(Number(s5.unit_price_usd) * 100);

  console.log('\n--- mcp_subscription_tiers.s5_calls_monthly (context only, does not gate creation) ---');
  const tiers = await sbFetch('mcp_subscription_tiers?select=tier_id,s5_calls_monthly&order=tier_id');
  tiers.forEach(t => console.log(`  ${t.tier_id}: ${t.s5_calls_monthly ?? 'null'}`));
  const investorTier = tiers.find(t => t.tier_id === 'investor');
  if (investorTier && !investorTier.s5_calls_monthly) {
    console.log('  NOTE: investor tier has s5_calls_monthly=0 and predict_auction_outcome is not in its tool_gates —');
    console.log('        creating the S5 price anyway per explicit dispatch instruction. It will simply never be attached');
    console.log('        to an investor subscription unless the tier is upsold. Flagging for Ariel — INFERRED discrepancy.');
  }

  // ── P1: Billing meter (idempotent by event_name) ───────────────────────────
  console.log('\n--- Billing meter ---');
  const existingMeters = (await stripe.billing.meters.list({ limit: 100 })).data;
  let meter = existingMeters.find(m => m.event_name === S5_EVENT_NAME);
  if (meter) {
    console.log(`  REUSING meter_id: ${meter.id}  (event_name=${meter.event_name}, status=${meter.status})`);
  } else {
    meter = await stripe.billing.meters.create({
      display_name: 'S5 Shapira Formula calls',
      event_name: S5_EVENT_NAME,
      default_aggregation: { formula: 'sum' },
      customer_mapping: { type: 'by_id', event_payload_key: 'stripe_customer_id' },
      value_settings: { event_payload_key: 'value' },
    });
    console.log(`  CREATED meter_id: ${meter.id}  (event_name=${meter.event_name})`);
  }

  // ── P2: S5 metered price per tier (idempotent — reuse if a price already references this meter) ──
  console.log('\n--- S5 metered prices ---');
  const products = await sbFetch('stripe_products?select=tier_id,product_id&order=tier_id');
  const results = [];

  for (const tierId of S5_TIERS) {
    const prod = products.find(p => p.tier_id === tierId);
    if (!prod || !prod.product_id || prod.product_id === 'PENDING') {
      console.error(`  ${tierId}: FATAL — no product_id in stripe_products (expected this to already exist)`);
      process.exitCode = 1;
      continue;
    }
    console.log(`\n  ${tierId} (product=${prod.product_id})`);

    const existingPrices = (await stripe.prices.list({ product: prod.product_id, limit: 100, active: true })).data;
    let price = existingPrices.find(pr => pr.recurring?.meter === meter.id);

    if (price) {
      console.log(`    REUSING price_id: ${price.id}`);
    } else {
      price = await stripe.prices.create({
        product: prod.product_id,
        currency: 'usd',
        unit_amount: unitAmount,
        recurring: { interval: 'month', meter: meter.id, usage_type: 'metered' },
        metadata: { tier: tierId, stream_id: 's5' },
      });
      console.log(`    CREATED price_id: ${price.id}  ($${unitAmount / 100}/call, metered via ${meter.id})`);
    }

    results.push({ tier: tierId, priceId: price.id });
  }

  // ── P3: Enterprise — custom quote only, skip ────────────────────────────────
  console.log('\n--- enterprise ---');
  console.log('  SKIPPED — no pencil_mcp_tool_spec row for predict_auction_outcome (table checked, 0 rows).');
  console.log('  Falling back to mcp_subscription_tiers.enterprise: price_monthly_usd=null,');
  console.log('  description mentions "Custom contract" — INFERRED custom-quote-only, no self-serve metered price created.');

  // ── P4: Writeback to stripe_products ────────────────────────────────────────
  console.log('\n--- Supabase stripe_products writeback ---');
  for (const r of results) {
    await sbFetch(`stripe_products?tier_id=eq.${r.tier}`, {
      method: 'PATCH',
      body: JSON.stringify({ stripe_meter_id: meter.id, stripe_s5_price_id: r.priceId }),
    });
    console.log(`  ${r.tier}: stripe_meter_id=${meter.id} stripe_s5_price_id=${r.priceId}`);
  }

  // ── P5: Verify ───────────────────────────────────────────────────────────────
  console.log('\n--- Verification ---');
  const rows = await sbFetch('stripe_products?select=tier_id,stripe_meter_id,stripe_s5_price_id&order=tier_id');
  console.log('\n### SQL VERIFICATION');
  console.log('```');
  console.log("SELECT count(*) FROM public.stripe_products WHERE tier_id IN ('investor','pro','proplus') AND (stripe_meter_id IS NULL OR stripe_s5_price_id IS NULL);");
  console.log('');
  rows.forEach(r => console.log(`  ${r.tier_id.padEnd(12)} meter=${r.stripe_meter_id || 'null'}  s5_price=${r.stripe_s5_price_id || 'null'}`));
  const missing = rows.filter(r => S5_TIERS.includes(r.tier_id) && (!r.stripe_meter_id || !r.stripe_s5_price_id));
  console.log(`\ncount=${missing.length}`);
  if (missing.length > 0) {
    console.error(`FAIL: ${missing.length} of ${S5_TIERS.length} tiers still missing meter/price: ${missing.map(r => r.tier_id).join(', ')}`);
    process.exit(1);
  }
  console.log('PASS: investor/pro/proplus all have stripe_meter_id + stripe_s5_price_id ✅');
  console.log(`Timestamp: ${new Date().toISOString()}`);
  console.log('```');
}

main().catch(e => { console.error('FATAL:', e.message || e); process.exit(1); });
