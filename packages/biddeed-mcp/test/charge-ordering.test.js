// GTM-22 Task 3 — charge/execute ordering.
//
// Failure A (free data leak): charge/allowance check must clear BEFORE the
// tool executes. Failure B (billing for nothing): the response must be
// confirmed serializable BEFORE billing commits.
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { handleToolCall, serializeToolResult, _setHandlerForTest } = await import('../src/server.js');

function jsonRes(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function mockFetch(routes) {
  const original = global.fetch;
  let billingInserts = 0;
  let chargeOutcomes = [];

  global.fetch = async (url, opts = {}) => {
    const urlStr = url.toString();
    const method = opts.method || 'GET';

    if (urlStr.includes('/mcp_api_keys')) return jsonRes([routes.customer]);

    if (urlStr.includes('/mcp_idempotency_keys')) {
      if (method === 'POST') return jsonRes([{}], 201); // always claims — each test uses a fresh requestId
      if (method === 'PATCH') return jsonRes([{}]);
      return jsonRes([]);
    }

    if (urlStr.includes('/mcp_subscription_tiers')) {
      return jsonRes([routes.tierRow ?? {}]);
    }

    if (urlStr.includes('/billing_events') && method === 'GET') {
      // Monthly-usage count for the allowance check
      return jsonRes(routes.usageRows ?? []);
    }

    if (urlStr.includes('/billing_events') && method === 'POST') {
      billingInserts++;
      return jsonRes([{ event_id: `evt-${billingInserts}` }], 201);
    }

    if (urlStr.includes('/mcp_charge_events')) {
      const body = JSON.parse(opts.body);
      chargeOutcomes.push(body.outcome);
      return jsonRes([{}], 201);
    }

    throw new Error(`Unmocked fetch in charge-ordering test: ${method} ${urlStr}`);
  };

  return {
    restore: () => { global.fetch = original; },
    billingInsertCount: () => billingInserts,
    chargeOutcomes: () => chargeOutcomes,
  };
}

test('serializeToolResult: happy path returns the JSON text', () => {
  const r = serializeToolResult({ count: 3 });
  assert.equal(r.ok, true);
  assert.equal(JSON.parse(r.text).count, 3);
});

test('serializeToolResult: circular reference is caught, not thrown (Failure B guard)', () => {
  const circular = {};
  circular.self = circular;
  const r = serializeToolResult(circular);
  assert.equal(r.ok, false);
  assert.equal(r.text, null);
});

test('Failure A — S1 allowance exhausted blocks execution before the handler runs, zero charge', async () => {
  let handlerCalled = false;
  _setHandlerForTest('search_auctions', async () => { handlerCalled = true; return { count: 0, auctions: [] }; });

  const mocks = mockFetch({
    customer: {
      key_prefix: 'bd_live_a1', customer_id: 'cust-a1', tier: 'free',
      is_active: true, expires_at: null, call_count: 0,
    },
    tierRow: { s1_calls_monthly: 50 },
    usageRows: Array.from({ length: 50 }, (_, i) => ({ event_id: `used-${i}` })), // at the cap
  });

  try {
    const res = await handleToolCall('bd_live_a1_key', 'search_auctions', { county: 'brevard' }, 'req-failA-1');
    assert.equal(handlerCalled, false, 'tool must not execute once the allowance check fails');
    assert.equal(res.isError, true);
    const body = JSON.parse(res.content[0].text);
    assert.equal(body.code, 'PAYMENT_REQUIRED');
    assert.equal(mocks.billingInsertCount(), 0, 'a blocked call must never bill');
    assert.deepEqual(mocks.chargeOutcomes(), ['blocked_allowance']);
  } finally {
    mocks.restore();
  }
});

test('Failure A — S5 without a Stripe customer on file blocks execution before the handler runs', async () => {
  let handlerCalled = false;
  _setHandlerForTest('predict_auction_outcome', async () => { handlerCalled = true; return { verdict: 'sell' }; });

  const mocks = mockFetch({
    customer: {
      key_prefix: 'bd_live_a2', customer_id: 'cust-a2', tier: 'pro',
      is_active: true, expires_at: null, call_count: 0, stripe_customer_id: null,
    },
  });

  try {
    const res = await handleToolCall('bd_live_a2_key', 'predict_auction_outcome', { case_number: 'C1', county: 'brevard' }, 'req-failA-2');
    assert.equal(handlerCalled, false, 'tool must not execute without a Stripe customer for a Stripe-metered stream');
    assert.equal(res.isError, true);
    const body = JSON.parse(res.content[0].text);
    assert.equal(body.code, 'PAYMENT_REQUIRED');
    assert.match(body.error, /Shapira Formula/);
    assert.equal(mocks.billingInsertCount(), 0);
    assert.deepEqual(mocks.chargeOutcomes(), ['blocked_stripe']);
  } finally {
    mocks.restore();
  }
});

test('Failure A — allowance not yet exhausted clears the gate and the handler executes', async () => {
  let handlerCalled = false;
  _setHandlerForTest('search_auctions', async () => { handlerCalled = true; return { count: 0, auctions: [] }; });

  const mocks = mockFetch({
    customer: {
      key_prefix: 'bd_live_a3', customer_id: 'cust-a3', tier: 'free',
      is_active: true, expires_at: null, call_count: 0,
    },
    tierRow: { s1_calls_monthly: 50 },
    usageRows: Array.from({ length: 10 }, (_, i) => ({ event_id: `used-${i}` })), // well under cap
  });

  try {
    const res = await handleToolCall('bd_live_a3_key', 'search_auctions', { county: 'brevard' }, 'req-failA-3');
    assert.equal(handlerCalled, true);
    assert.equal(res.isError, false);
    assert.equal(mocks.billingInsertCount(), 1);
    assert.deepEqual(mocks.chargeOutcomes(), ['charged']);
  } finally {
    mocks.restore();
  }
});

test('Failure B — unserializable tool result never bills and returns a clean error', async () => {
  const circular = {};
  circular.self = circular;
  _setHandlerForTest('search_auctions', async () => circular);

  const mocks = mockFetch({
    customer: {
      key_prefix: 'bd_live_b1', customer_id: 'cust-b1', tier: 'free',
      is_active: true, expires_at: null, call_count: 0,
    },
    tierRow: { s1_calls_monthly: 50 },
    usageRows: [],
  });

  try {
    const res = await handleToolCall('bd_live_b1_key', 'search_auctions', { county: 'brevard' }, 'req-failB-1');
    assert.equal(res.isError, true);
    const body = JSON.parse(res.content[0].text);
    assert.match(body.error, /serialization/i);
    assert.equal(mocks.billingInsertCount(), 0, 'an unserializable result must never bill — record-then-commit, not record-then-hope');
    assert.deepEqual(mocks.chargeOutcomes(), ['serialization_error']);
  } finally {
    mocks.restore();
  }
});
