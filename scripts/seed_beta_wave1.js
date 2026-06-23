#!/usr/bin/env node
// Seed wave1_brevard_duval beta invites + API keys
// Usage: node scripts/seed_beta_wave1.js
// Prints API keys to stdout — save securely, never commit.
import { createHash, randomBytes, randomUUID } from 'crypto';

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_KEY) {
  console.error('SUPABASE_SERVICE_ROLE_KEY required');
  process.exit(1);
}

const headers = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
  'Content-Type': 'application/json',
  Prefer: 'return=representation',
};

function hashKey(k) {
  return createHash('sha256').update(k).digest('hex');
}

function genApiKey(prefix) {
  const rand = randomBytes(24).toString('base64url').slice(0, 32);
  return `${prefix}_${rand}`;
}

function genInviteCode() {
  return 'BD-' + randomBytes(6).toString('hex').toUpperCase();
}

async function supabasePost(path, body) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method: 'POST',
    headers: { ...headers, Prefer: 'resolution=ignore-duplicates,return=representation' },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}: ${text.slice(0, 400)}`);
  return JSON.parse(text);
}

const WAVE1 = [
  { name: 'Ariel Shapira',     email: 'ariel@everestcapitalusa.com', investor_type: 'founder',   notes: 'Founder — full access, all counties' },
  { name: 'Mariam Shapira',    email: 'mariam@property360.com',       investor_type: 'broker',    notes: 'Property360 — broker integration testing' },
  { name: 'Beta Investor 3',   email: 'beta3@biddeed.ai',             investor_type: 'investor',  notes: 'Wave 1 — Brevard focus' },
  { name: 'Beta Investor 4',   email: 'beta4@biddeed.ai',             investor_type: 'investor',  notes: 'Wave 1 — Duval focus' },
  { name: 'Beta Investor 5',   email: 'beta5@biddeed.ai',             investor_type: 'investor',  notes: 'Wave 1 — multi-county' },
];

const results = [];

for (const beta of WAVE1) {
  const customerId = randomUUID();
  const apiKey = genApiKey('bd_live');
  const keyHash = hashKey(apiKey);
  const keyPrefix = apiKey.slice(0, 16);
  const inviteCode = genInviteCode();

  // Insert into beta_invites
  try {
    await supabasePost('beta_invites', {
      customer_id: customerId,
      name: beta.name,
      email: beta.email,
      invite_code: inviteCode,
      cohort: 'wave1_brevard_duval',
      cohort_id: 'wave1_brevard_duval',
      counties_active: ['brevard', 'duval'],
      tier: 'pro',
      api_key_prefix: keyPrefix,
      investor_type: beta.investor_type,
      source: 'ariel_direct_network',
      status: 'invited',
      notes: beta.notes,
      invite_sent_at: new Date().toISOString(),
    });
    console.log(`✓ beta_invites: ${beta.email}`);
  } catch (e) {
    if (e.message.includes('duplicate') || e.message.includes('unique') || e.message.includes('conflict')) {
      console.log(`[skip] beta_invites ${beta.email} already exists`);
    } else {
      console.error(`[warn] beta_invites ${beta.email}: ${e.message}`);
    }
  }

  // Insert API key
  try {
    await supabasePost('mcp_api_keys', {
      customer_id: customerId,
      key_hash: keyHash,
      key_prefix: keyPrefix,
      server: 'biddeed',
      tier: 'pro',
      product: 'biddeed',
      active: true,
      is_active: true,
      rate_limit_hr: 500,
      daily_s1_limit: 200,
    });
    console.log(`✓ mcp_api_keys: ${keyPrefix}...`);
  } catch (e) {
    if (e.message.includes('duplicate') || e.message.includes('unique') || e.message.includes('conflict')) {
      console.log(`[skip] mcp_api_keys ${keyPrefix} already exists`);
    } else {
      console.error(`[warn] mcp_api_keys ${keyPrefix}: ${e.message}`);
    }
  }

  results.push({ ...beta, customer_id: customerId, api_key: apiKey, invite_code: inviteCode, key_prefix: keyPrefix });
}

console.log('\n=== WAVE 1 BETA API KEYS (save securely — printed ONCE) ===');
for (const r of results) {
  console.log(`\n${r.name}`);
  console.log(`  Email:       ${r.email}`);
  console.log(`  Customer ID: ${r.customer_id}`);
  console.log(`  API Key:     ${r.api_key}`);
  console.log(`  Invite Code: ${r.invite_code}`);
  console.log(`  Install:     npx biddeed-mcp`);
  console.log(`  Env:         BIDDEED_API_KEY=${r.api_key}`);
}
console.log('\n=== END — Share keys only via secure channel ===');
