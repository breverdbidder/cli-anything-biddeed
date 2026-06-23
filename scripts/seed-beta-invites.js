#!/usr/bin/env node
// seed-beta-invites.js — Insert wave1_brevard_duval beta cohort + generate API keys
// Zero-HITL. Run via mcp-build-deploy.yml P4 step or manually.
// Outputs: bd_live_* API keys printed to stdout for Ariel to distribute.

import { createHash, randomBytes } from 'crypto';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('FATAL: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required');
  process.exit(1);
}

const HEADERS = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
  'Content-Type': 'application/json',
  Prefer: 'return=representation',
};

async function supabasePost(path, body) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method: 'POST',
    headers: HEADERS,
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}: ${text.slice(0, 300)}`);
  return JSON.parse(text);
}

async function supabaseGet(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { headers: HEADERS });
  const text = await res.text();
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}: ${text.slice(0, 300)}`);
  return JSON.parse(text);
}

function generateKey(prefix = 'bd_live_') {
  return prefix + randomBytes(24).toString('base64url');
}

function hashKey(key) {
  return createHash('sha256').update(key).digest('hex');
}

function generateCustomerId() {
  return 'bd_cust_' + randomBytes(8).toString('hex');
}

function generateInviteCode(county) {
  return county.toUpperCase().slice(0, 7) + '-' + randomBytes(3).toString('hex').toUpperCase() + '-' + randomBytes(3).toString('hex').toUpperCase();
}

// Wave 1 beta cohort — Ariel's direct network (placeholder names, update before seeding)
const WAVE1_COHORT = [
  {
    name: 'Beta Tester 1',
    email: 'beta1@biddeed.ai',
    counties_active: ['brevard', 'duval'],
    tier: 'pro',
    notes: 'Wave 1 — Brevard investor',
  },
  {
    name: 'Beta Tester 2',
    email: 'beta2@biddeed.ai',
    counties_active: ['brevard'],
    tier: 'investor',
    notes: 'Wave 1 — Brevard tax deed specialist',
  },
  {
    name: 'Beta Tester 3',
    email: 'beta3@biddeed.ai',
    counties_active: ['duval'],
    tier: 'pro',
    notes: 'Wave 1 — Duval foreclosure investor',
  },
  {
    name: 'Beta Tester 4',
    email: 'beta4@biddeed.ai',
    counties_active: ['brevard', 'duval', 'orange'],
    tier: 'proplus',
    notes: 'Wave 1 — Multi-county investor',
  },
  {
    name: 'Beta Tester 5',
    email: 'beta5@biddeed.ai',
    counties_active: ['brevard'],
    tier: 'pro',
    notes: 'Wave 1 — Broker / Property360 referral',
  },
];

async function main() {
  console.log('=== BidDeed Beta Invites Seed (wave1_brevard_duval) ===\n');

  const results = [];

  for (const member of WAVE1_COHORT) {
    const customerId = generateCustomerId();
    const apiKey = generateKey('bd_live_');
    const inviteCode = generateInviteCode(member.counties_active[0] || 'biddeed');

    // Check if already exists
    const existing = await supabaseGet(
      `beta_invites?email=eq.${encodeURIComponent(member.email)}&limit=1`
    ).catch(() => []);

    if (existing.length) {
      console.log(`SKIP: ${member.email} — already in beta_invites`);
      continue;
    }

    // Insert beta_invite
    await supabasePost('beta_invites', {
      customer_id: customerId,
      name: member.name,
      email: member.email,
      invite_code: inviteCode,
      cohort: 'wave1_brevard_duval',
      counties_active: member.counties_active,
      tier: member.tier,
      api_key_prefix: apiKey.slice(0, 14),
      notes: member.notes,
    });

    // Insert API key (hashed)
    await supabasePost('mcp_api_keys', {
      key_hash: hashKey(apiKey),
      key_prefix: apiKey.slice(0, 14),
      customer_id: customerId,
      tier: member.tier,
      product: 'biddeed',
      rate_limit_hr: member.tier === 'investor' ? 100 : 500,
      daily_s1_limit: member.tier === 'free' ? 50 : 9999,
      is_active: true,
    });

    results.push({ ...member, customerId, apiKey, inviteCode });
    console.log(`✅ ${member.email} — ${member.tier} — ${inviteCode}`);
  }

  if (!results.length) {
    console.log('\nAll 5 beta members already seeded.');
    return;
  }

  console.log('\n=== API KEYS (distribute to beta members — store securely) ===');
  console.log('');
  for (const r of results) {
    console.log(`${r.name} <${r.email}>`);
    console.log(`  Tier:       ${r.tier}`);
    console.log(`  Counties:   ${r.counties_active.join(', ')}`);
    console.log(`  API Key:    ${r.apiKey}`);
    console.log(`  Invite:     ${r.inviteCode}`);
    console.log(`  Install:    npx biddeed-mcp (set BIDDEED_API_KEY=${r.apiKey})`);
    console.log('');
  }

  console.log('=== CLAUDE CONFIG SNIPPET (send to each beta member) ===');
  console.log(JSON.stringify({
    mcpServers: {
      biddeed: {
        command: 'npx',
        args: ['-y', 'biddeed-mcp'],
        env: { BIDDEED_API_KEY: '<their_key_above>' },
      },
    },
  }, null, 2));

  // Verify
  console.log('\n### SQL VERIFICATION');
  console.log('```');
  console.log(`SELECT email, tier, invite_code, api_key_prefix FROM beta_invites WHERE cohort = 'wave1_brevard_duval' ORDER BY invited_at;`);
  console.log('');
  const rows = await supabaseGet(
    `beta_invites?cohort=eq.wave1_brevard_duval&select=email,tier,invite_code,api_key_prefix&order=invited_at`
  );
  rows.forEach(r => console.log(JSON.stringify(r)));
  console.log(`\nTotal: ${rows.length} beta invites seeded ✅`);
  console.log('```');
}

main().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
