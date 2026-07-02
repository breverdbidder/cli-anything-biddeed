import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { captureToolCall, hashDistinctId, flushNow, _debugState, _resetForTest } = await import('../src/posthog.js');

function mockFetch(handler) {
  const original = global.fetch;
  global.fetch = handler;
  return () => { global.fetch = original; };
}

test('hashDistinctId never returns the raw credential', () => {
  const raw = 'bd_live_super_secret_001';
  const hashed = hashDistinctId(raw);
  assert.notEqual(hashed, raw);
  assert.equal(hashed, createHash('sha256').update(raw).digest('hex'));
});

test('captureToolCall flushes a batch to PostHog once the vault key resolves', async (t) => {
  _resetForTest();
  let batchBody = null;
  t.after(mockFetch(async (url, opts) => {
    const urlStr = url.toString();
    if (urlStr.includes('/rpc/get_vault_secret_mcp')) {
      return new Response(JSON.stringify('phc_test_live_key'), { status: 200 });
    }
    if (urlStr.includes('us.i.posthog.com/batch')) {
      batchBody = JSON.parse(opts.body);
      return new Response('{}', { status: 200 });
    }
    throw new Error(`Unmocked fetch: ${urlStr}`);
  }));

  captureToolCall({
    credential: 'bd_live_abc',
    toolName: 'search_auctions',
    tier: 'investor',
    latencyMs: 42,
    county: 'brevard',
    cacheHit: false,
    errorClass: null,
  });
  await flushNow();

  assert.ok(batchBody, 'expected a batch POST to PostHog');
  assert.equal(batchBody.api_key, 'phc_test_live_key');
  assert.equal(batchBody.batch[0].event, 'mcp_tool_call');
  assert.equal(batchBody.batch[0].properties.tool_name, 'search_auctions');
  assert.equal(batchBody.batch[0].properties.tier, 'investor');
  assert.notEqual(batchBody.batch[0].distinct_id, 'bd_live_abc');
});

test('captureToolCall never throws when the vault key is missing (blocked_on_key)', async (t) => {
  _resetForTest();
  t.after(mockFetch(async (url) => {
    const urlStr = url.toString();
    if (urlStr.includes('/rpc/get_vault_secret_mcp')) {
      return new Response('null', { status: 200 });
    }
    throw new Error(`Unexpected call to PostHog while key is missing: ${urlStr}`);
  }));

  assert.doesNotThrow(() => {
    captureToolCall({ credential: 'bd_live_x', toolName: 'browse_deals', tier: 'free', latencyMs: 5 });
  });
  await flushNow();
  assert.equal(_debugState().queueDepth, 0);
});

test('captureToolCall drops events past the queue cap instead of growing unbounded', () => {
  _resetForTest();
  // Never resolves — the queue just fills up without a flush completing.
  const restore = mockFetch(() => new Promise(() => {}));
  try {
    for (let i = 0; i < 600; i++) {
      captureToolCall({ credential: 'bd_live_y', toolName: 'search_auctions', tier: 'free', latencyMs: 1 });
    }
    assert.ok(_debugState().dropped > 0, 'expected overflow drops past MAX_QUEUE');
    assert.ok(_debugState().queueDepth <= 500);
  } finally {
    restore();
  }
});
