// Regression: the existing bd_* API key auth path (5 active keys in production
// as of 2026-07-01) must keep working unchanged after WorkOS OAuth was wired in
// as a parallel path.
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { validateKey } = await import('../src/auth.js');
const { isJwtLike } = await import('../src/oauth.js');

function mockFetch(handler) {
  const original = global.fetch;
  global.fetch = handler;
  return () => { global.fetch = original; };
}

test('validateKey accepts an active bd_ key (unaffected by OAuth wiring)', async (t) => {
  t.after(mockFetch(async (url) => {
    const urlStr = url.toString();
    if (urlStr.includes('/mcp_api_keys')) {
      return new Response(JSON.stringify([{
        key_hash: 'hash-1',
        key_prefix: 'bd_live_rcMeTf',
        customer_id: 'cust-1',
        tier: 'pro',
        is_active: true,
        expires_at: null,
        call_count: 4,
      }]), { status: 200 });
    }
    throw new Error(`Unmocked fetch: ${urlStr}`);
  }));

  const record = await validateKey('bd_live_realkey_regression_001');
  assert.equal(record.tier, 'pro');
  assert.equal(record.customer_id, 'cust-1');
  assert.equal(record.is_active, true);
});

test('validateKey rejects a deactivated bd_ key', async (t) => {
  t.after(mockFetch(async () => new Response(JSON.stringify([{
    key_hash: 'hash-2', key_prefix: 'bd_live_dead', customer_id: 'cust-2',
    tier: 'pro', is_active: false, call_count: 0,
  }]), { status: 200 })));

  await assert.rejects(() => validateKey('bd_live_deadkey_regression_002'), /deactivated/);
});

test('validateKey rejects an unknown bd_ key', async (t) => {
  t.after(mockFetch(async () => new Response('[]', { status: 200 })));

  await assert.rejects(() => validateKey('bd_live_unknown_regression_003'), /Invalid API key/);
});

test('isJwtLike never misclassifies a bd_ key as an OAuth token', () => {
  assert.equal(isJwtLike('bd_live_rcMeTf'), false);
  assert.equal(isJwtLike('bd_live_abc.def.ghi'), false); // bd_ prefix wins even with dots
});
