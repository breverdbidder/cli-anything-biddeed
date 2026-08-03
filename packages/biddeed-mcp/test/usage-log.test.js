// GTM-22 SECURITY — logUsage() unit coverage.
//
// Deliberately imports only usage-log.js + posthog.js (not server.js): at
// the time this was written, src/tools/market.js has a pre-existing,
// unrelated module-load syntax error (a regex/comment with literal embedded
// newlines around line 164) that crashes every test importing server.js —
// confirmed present on main before this change too. Importing server.js
// here would make this test fail for a reason that has nothing to do with
// usage logging. Once market.js is fixed, an integration-level assertion
// (handleToolCall → mcp_usage_log insert) should be added alongside the
// existing cert-gate/charge-ordering suites.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { logUsage } = await import('../src/usage-log.js');

function mockFetch(handler) {
  const original = global.fetch;
  global.fetch = handler;
  return () => { global.fetch = original; };
}

test('logUsage POSTs a row to mcp_usage_log with the hashed key, never the raw credential', async (t) => {
  let body = null;
  t.after(mockFetch(async (url, opts) => {
    const urlStr = url.toString();
    if (urlStr.includes('/rest/v1/mcp_usage_log')) {
      body = JSON.parse(opts.body);
      return new Response(JSON.stringify([{ id: 1 }]), { status: 201 });
    }
    throw new Error(`Unmocked fetch: ${urlStr}`);
  }));

  logUsage({
    credential: 'bd_live_super_secret_001',
    customerId: '11111111-1111-1111-1111-111111111111',
    toolName: 'search_auctions',
    county: 'brevard',
    latencyMs: 42,
    success: true,
    tier: 'investor',
  });

  // Fire-and-forget — give the microtask queue a tick to run the insert.
  await new Promise(resolve => setImmediate(resolve));

  assert.ok(body, 'expected a POST to mcp_usage_log');
  assert.equal(body.api_key_hash, createHash('sha256').update('bd_live_super_secret_001').digest('hex'));
  assert.notEqual(body.api_key_hash, 'bd_live_super_secret_001');
  assert.equal(body.customer_id, '11111111-1111-1111-1111-111111111111');
  assert.equal(body.tool_name, 'search_auctions');
  assert.equal(body.county_slug, 'brevard');
  assert.equal(body.ip_address, null);
  assert.equal(body.response_ms, 42);
  assert.equal(body.success, true);
  assert.equal(body.tier_id, 'investor');
});

test('logUsage never throws when the insert fails (fire-and-forget)', async (t) => {
  t.after(mockFetch(async () => new Response('server error', { status: 500 })));

  assert.doesNotThrow(() => {
    logUsage({ credential: 'bd_live_x', toolName: 'browse_deals', success: true });
  });
  await new Promise(resolve => setImmediate(resolve));
});
