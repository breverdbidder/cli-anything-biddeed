#!/usr/bin/env node
// gtm22g-stripe-live-audit.js — GTM-22G Task A: LIVE mode Stripe configuration audit.
// READ-ONLY. Never calls create/update/delete on any Stripe resource. Never logs the
// Stripe key or any webhook signing secret — only mode (live/test) and pass/fail facts.
// Vault-first key resolution, same pattern as scripts/stripe-meters-s5.js /
// scripts/s5-meter-emit.js — must run inside the GHA runner (cc-runner-ghonly.yml or a
// dedicated workflow_dispatch), never from an interactive chat session.

import Stripe from 'stripe';

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;
if (!SUPABASE_KEY) { console.error('FATAL: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY not set'); process.exit(1); }

async function resolveStripeKey() {
  const envKey = process.env.STRIPE_SECRET_KEY;
  if (envKey && /^(sk|rk)_(live|test)_/.test(envKey)) return envKey;
  console.log('STRIPE_SECRET_KEY env missing/invalid — using Supabase Vault (SSOT)');
  const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/vault_secret`, {
    method: 'POST',
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ p_name: 'stripe_secret_key' }),
  });
  if (!r.ok) { console.error('FATAL: vault_secret RPC failed', r.status); process.exit(1); }
  const k = await r.json();
  if (!k || !/^(sk|rk)_(live|test)_/.test(k)) { console.error('FATAL: no valid Stripe key in env or vault'); process.exit(1); }
  // Mask immediately so it can never leak via a later accidental echo of process state.
  console.log(`::add-mask::${k}`);
  return k;
}

async function sbFetch(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
  });
  if (!res.ok) throw new Error(`Supabase ${path} -> HTTP ${res.status}`);
  return res.json();
}

async function main() {
  const key = await resolveStripeKey();
  const LIVE = !key.startsWith('sk_test_');
  const stripe = new Stripe(key, { apiVersion: '2024-06-20' });
  console.log(`=== GTM-22G Task A: Stripe config audit (mode=${LIVE ? 'LIVE' : 'TEST'}) — READ-ONLY ===\n`);

  let failures = 0;

  // ── 1. stripe_products -> Stripe products/prices, active + resolvable ──────
  console.log('--- 1. stripe_products cross-check ---');
  const dbProducts = await sbFetch('stripe_products?select=tier_id,product_id,stripe_price_id_monthly,stripe_price_id_annual,stripe_s5_price_id,stripe_meter_id,live_mode&order=tier_id');
  for (const row of dbProducts) {
    console.log(`\n  tier=${row.tier_id} live_mode=${row.live_mode}`);
    if (!row.product_id) { console.log('    product_id: NULL (enterprise custom contract — expected)'); continue; }
    try {
      const prod = await stripe.products.retrieve(row.product_id);
      console.log(`    product ${row.product_id}: active=${prod.active}`);
      if (!prod.active) { console.log('    FLAG: product exists but is INACTIVE'); failures++; }
    } catch (e) {
      console.log(`    FLAG: product ${row.product_id} NOT RESOLVABLE (${e.message})`);
      failures++;
    }
    for (const [label, priceId] of [
      ['monthly', row.stripe_price_id_monthly],
      ['annual', row.stripe_price_id_annual],
      ['s5', row.stripe_s5_price_id],
    ]) {
      if (!priceId) { console.log(`    price(${label}): NULL`); continue; }
      try {
        const price = await stripe.prices.retrieve(priceId);
        console.log(`    price(${label}) ${priceId}: active=${price.active} unit_amount=${price.unit_amount ?? 'n/a'} meter=${price.recurring?.meter || 'none'}`);
        if (!price.active) { console.log(`    FLAG: price(${label}) exists but is INACTIVE`); failures++; }
      } catch (e) {
        console.log(`    FLAG: price(${label}) ${priceId} NOT RESOLVABLE (${e.message})`);
        failures++;
      }
    }
  }

  // ── 2. Billing meter ────────────────────────────────────────────────────────
  console.log('\n--- 2. Billing meter (s5_predict_auction_outcome) ---');
  const meters = (await stripe.billing.meters.list({ limit: 100 })).data;
  const s5Meter = meters.find(m => m.event_name === 's5_predict_auction_outcome');
  if (!s5Meter) {
    console.log('  FLAG: no billing meter with event_name=s5_predict_auction_outcome found in this mode');
    failures++;
  } else {
    console.log(`  meter ${s5Meter.id}: status=${s5Meter.status} event_name=${s5Meter.event_name}`);
    if (s5Meter.status !== 'active') { console.log('  FLAG: meter exists but status != active'); failures++; }
  }
  const dbMeterIds = [...new Set(dbProducts.map(r => r.stripe_meter_id).filter(Boolean))];
  console.log(`  DB stripe_meter_id values referenced (investor/pro/proplus): ${dbMeterIds.join(', ') || 'none'}`);
  if (s5Meter && dbMeterIds.length && !dbMeterIds.every(id => id === s5Meter.id)) {
    console.log('  FLAG: DB stripe_meter_id does not match live meter id');
    failures++;
  }

  // ── 3. Webhook endpoints (presence/config only, never the signing secret) ──
  console.log('\n--- 3. Webhook endpoints ---');
  let webhooks = [];
  try {
    webhooks = (await stripe.webhookEndpoints.list({ limit: 100 })).data;
    if (webhooks.length === 0) {
      console.log('  FLAG: zero webhook endpoints registered in this mode');
      failures++;
    }
    for (const wh of webhooks) {
      console.log(`  ${wh.id}: url=${wh.url} status=${wh.status} events=${wh.enabled_events.join(',')}`);
    }
  } catch (e) {
    console.log(`  FLAG: could not list webhook endpoints — ${e.message}`);
    failures++;
  }
  console.log('  NOTE: Stripe never returns the signing secret via list/retrieve — cannot confirm it matches STRIPE_WEBHOOK_SECRET from here.');
  console.log('  NOTE: STRIPE_WEBHOOK_SECRET is not present in this repo\'s GitHub Actions secrets (verified separately via `gh secret list`) and webhook.js has no vault fallback for it.');

  // ── 4. Tier allowances vs advertised pricing ────────────────────────────────
  console.log('\n--- 4. mcp_subscription_tiers pricing ---');
  const tiers = await sbFetch('mcp_subscription_tiers?select=tier_id,price_monthly_usd&order=tier_id');
  tiers.forEach(t => console.log(`  ${t.tier_id}: $${t.price_monthly_usd ?? 'custom'}/mo`));

  console.log('\n### SQL VERIFICATION');
  console.log('```');
  console.log(`Stripe mode: ${LIVE ? 'LIVE' : 'TEST'}`);
  console.log(`Products checked: ${dbProducts.filter(r => r.product_id).length}`);
  console.log(`Webhook endpoints found: ${webhooks.length}`);
  console.log(`Billing meter found: ${!!s5Meter}`);
  console.log(`Flags raised: ${failures}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);
  console.log('```');

  if (failures > 0) process.exitCode = 1;
}

main().catch(e => { console.error('FATAL:', e.message || e); process.exit(1); });
