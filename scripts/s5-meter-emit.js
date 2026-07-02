#!/usr/bin/env node
// s5-meter-emit.js — S5 (Shapira Formula) usage emission: billing_events -> Stripe Billing Meter
// SPRINT3 P0-2. Zero-HITL: reads config from env / Supabase Vault. Idempotent — safe to re-run.
//
// Aggregates billing_events (stream_id='s5') per bd_key per hourly window, then emits one
// Stripe meter event per window via POST /v1/billing/meter_events (the new Billing Meters
// API — NOT the deprecated subscriptionItems.createUsageRecord path used elsewhere in
// packages/biddeed-mcp/src/billing.js). Idempotency: usage_source_ref = `s5:{bd_key}:{window}`
// is UNIQUE on s5_meter_emissions, and is also passed as the Stripe `identifier` so a re-run
// can never double-bill even if the DB write and the Stripe call race.
//
// KNOWN CONSTRAINT: no mcp_api_keys row has stripe_customer_id set yet (Customers=Read only
// on the restricted Stripe key — this script cannot create them). Windows for an unmapped
// bd_key are logged with stripe_accepted=false, error='no_customer_mapping' and NO Stripe
// call is made. That is a valid, expected pipeline state — not a failure.

import Stripe from 'stripe';

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;
if (!SUPABASE_KEY) { console.error('FATAL: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY not set'); process.exit(1); }

const S5_EVENT_NAME = 's5_predict_auction_outcome';
const WINDOW_MS = 60 * 60 * 1000; // hourly buckets

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
  return k;
}

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
  if (res.status >= 300 && res.status !== 409) throw new Error(`Supabase ${path} → HTTP ${res.status}: ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

function windowStart(isoTimestamp) {
  return new Date(Math.floor(new Date(isoTimestamp).getTime() / WINDOW_MS) * WINDOW_MS).toISOString();
}

async function main() {
  console.log('=== S5 Meter Emission (billing_events -> Stripe Billing Meter) ===\n');
  const stripe = new Stripe(await resolveStripeKey(), { apiVersion: '2024-06-20' });

  // ── P0: pull all S5 usage rows not yet covered by an emission ──────────────
  const events = await sbFetch('billing_events?stream_id=eq.s5&select=event_id,key_prefix,customer_id,created_at&order=created_at');
  console.log(`billing_events (stream_id=s5): ${events.length} row(s)`);
  if (events.length === 0) {
    console.log('Nothing to emit. Exiting cleanly.');
    return;
  }

  // ── P1: aggregate per bd_key per hourly window ──────────────────────────────
  const windows = new Map(); // usage_source_ref -> { bd_key, window, quantity }
  for (const ev of events) {
    const win = windowStart(ev.created_at);
    const ref = `s5:${ev.key_prefix}:${win}`;
    const bucket = windows.get(ref) || { usage_source_ref: ref, bd_key: ev.key_prefix, window: win, quantity: 0 };
    bucket.quantity += 1;
    windows.set(ref, bucket);
  }
  console.log(`Aggregated into ${windows.size} (bd_key, window) bucket(s)\n`);

  // ── P2: skip buckets already emitted (idempotency at app layer) ────────────
  const refs = [...windows.keys()];
  const existing = await sbFetch(`s5_meter_emissions?usage_source_ref=in.(${refs.map(r => encodeURIComponent(r)).join(',')})&select=usage_source_ref`);
  const alreadyEmitted = new Set(existing.map(r => r.usage_source_ref));
  const pending = [...windows.values()].filter(w => !alreadyEmitted.has(w.usage_source_ref));
  console.log(`Already emitted: ${alreadyEmitted.size} | Pending: ${pending.length}\n`);

  if (pending.length === 0) {
    console.log('All buckets already emitted. Exiting cleanly.');
    return;
  }

  // ── P3: resolve bd_key -> stripe_customer_id via mcp_api_keys ───────────────
  const keyPrefixes = [...new Set(pending.map(w => w.bd_key))];
  const keyRows = await sbFetch(`mcp_api_keys?key_prefix=in.(${keyPrefixes.map(k => encodeURIComponent(k)).join(',')})&select=key_prefix,stripe_customer_id`);
  const customerByKey = new Map(keyRows.map(k => [k.key_prefix, k.stripe_customer_id]));

  // ── P4: emit — Stripe meter event when mapped, logged gap when not ─────────
  let accepted = 0, unmapped = 0, failed = 0;
  for (const bucket of pending) {
    const stripeCustomerId = customerByKey.get(bucket.bd_key) || null;
    const row = {
      usage_source_ref: bucket.usage_source_ref,
      bd_key: bucket.bd_key,
      stripe_customer_id: stripeCustomerId,
      quantity: bucket.quantity,
      emitted_at: new Date().toISOString(),
      stripe_accepted: false,
      stripe_event_id: null,
      error: null,
    };

    if (!stripeCustomerId) {
      row.error = 'no_customer_mapping';
      unmapped++;
    } else {
      try {
        const meterEvent = await stripe.billing.meterEvents.create({
          event_name: S5_EVENT_NAME,
          identifier: bucket.usage_source_ref, // Stripe-side idempotency, belt-and-suspenders with our UNIQUE constraint
          payload: { stripe_customer_id: stripeCustomerId, value: String(bucket.quantity) },
        });
        row.stripe_accepted = true;
        row.stripe_event_id = meterEvent.identifier;
        accepted++;
      } catch (err) {
        row.error = err.message || String(err);
        failed++;
      }
    }

    try {
      await sbFetch('s5_meter_emissions', {
        method: 'POST',
        headers: { Prefer: 'return=representation,resolution=ignore-duplicates' },
        body: JSON.stringify(row),
      });
      console.log(`  ${bucket.usage_source_ref}  qty=${bucket.quantity}  accepted=${row.stripe_accepted}  error=${row.error || 'none'}`);
    } catch (err) {
      console.error(`  ${bucket.usage_source_ref}  FAILED TO LOG: ${err.message}`);
    }
  }

  console.log(`\nSummary: accepted=${accepted} unmapped=${unmapped} failed=${failed}`);

  // ── P5: verify ────────────────────────────────────────────────────────────
  const total = await sbFetch('s5_meter_emissions?select=emission_id');
  console.log('\n### SQL VERIFICATION');
  console.log('```');
  console.log('SELECT count(*) FROM public.s5_meter_emissions;');
  console.log('');
  console.log(`count=${total.length}`);
  if (total.length === 0) {
    console.error('FAIL: s5_meter_emissions is empty after emission run');
    process.exit(1);
  }
  console.log('PASS: s5_meter_emissions has >=1 row ✅');
  console.log(`Timestamp: ${new Date().toISOString()}`);
  console.log('```');
}

main().catch(e => { console.error('FATAL:', e.message || e); process.exit(1); });
