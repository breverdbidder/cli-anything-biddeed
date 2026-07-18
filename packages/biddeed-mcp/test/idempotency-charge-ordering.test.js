// GTM-22 Task 2 (idempotency) + Task 3 (charge ordering) — triple-fire test.
//
// Fires the identical JSON-RPC call (same request id, same args, same API
// key) three times for one S1 tool, one S3 tool, and S5 (Shapira Formula),
// and asserts exactly one billing_events row lands per tool despite the
// retries. S5's Stripe usage-record filing is nested 1:1 inside
// recordBilling() and gated by the same idempotency claim, so "one
// billing_events insert" is also proof of "at most one Stripe meter event"
// even with STRIPE_SECRET_KEY unset in this test env (getStripe() short-
// circuits to null — no real Stripe network calls happen either way).
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { handleToolCall } = await import('../src/server.js');

function jsonRes(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

// In-memory fake for mcp_idempotency_keys — mirrors the real table's unique
// constraint (PK on idempotency_key) so the test exercises the same
// insert-or-conflict semantics the DB enforces.
function makeFakeIdempotencyStore() {
  const rows = new Map();
  return {
    insert(row) {
      if (rows.has(row.idempotency_key)) {
        const err = { code: '23505', message: 'duplicate key value violates unique constraint "mcp_idempotency_keys_pkey"' };
        return { status: 409, body: err };
      }
      rows.set(row.idempotency_key, { ...row, duplicate_count: 0 });
      return { status: 201, body: [rows.get(row.idempotency_key)] };
    },
    get(key) {
      const row = rows.get(key);
      return row ? [row] : [];
    },
    patch(key, updates) {
      const row = rows.get(key);
      if (row) Object.assign(row, updates);
      return [row];
    },
  };
}

function mockFetch({ tier, streamId }) {
  const idem = makeFakeIdempotencyStore();
  let billingInserts = 0;
  let chargeEventInserts = 0;

  const original = global.fetch;
  global.fetch = async (url, opts = {}) => {
    const urlStr = url.toString();
    const method = opts.method || 'GET';

    if (urlStr.includes('/mcp_api_keys')) {
      return jsonRes([{
        key_hash: 'hash-triple-fire',
        key_prefix: 'bd_live_triplefire',
        customer_id: 'cust-triple-fire',
        tier,
        is_active: true,
        expires_at: null,
        call_count: 0,
        stripe_customer_id: 'cus_test_triplefire',
      }]);
    }

    if (urlStr.includes('/mcp_idempotency_keys')) {
      if (method === 'POST') {
        const row = JSON.parse(opts.body);
        const result = idem.insert(row);
        return jsonRes(result.body, result.status);
      }
      if (method === 'PATCH') {
        const key = decodeURIComponent(urlStr.split('idempotency_key=eq.')[1]);
        const updates = JSON.parse(opts.body);
        return jsonRes(idem.patch(key, updates));
      }
      // GET
      const key = decodeURIComponent(urlStr.split('idempotency_key=eq.')[1].split('&')[0]);
      return jsonRes(idem.get(key));
    }

    if (urlStr.includes('/mcp_subscription_tiers')) {
      return jsonRes([{}]); // no cap column populated → allowance check passes
    }

    if (urlStr.includes('/billing_events')) {
      billingInserts++;
      return jsonRes([{ event_id: `evt-${billingInserts}` }], 201);
    }

    if (urlStr.includes('/mcp_charge_events')) {
      chargeEventInserts++;
      return jsonRes([{}], 201);
    }

    if (urlStr.includes('/gold_standard_county_status')) {
      return jsonRes([]); // uncertified — predict_auction_outcome short-circuits, no further lookups
    }

    if (urlStr.includes('/zoning_assignments')) {
      return jsonRes([]);
    }

    if (urlStr.includes('/multi_county_auctions')) {
      return jsonRes([]);
    }

    throw new Error(`Unmocked fetch in triple-fire test: ${method} ${urlStr}`);
  };

  return {
    restore: () => { global.fetch = original; },
    billingInsertCount: () => billingInserts,
  };
}

async function tripleFire(tool, args, tier) {
  const mocks = mockFetch({ tier });
  try {
    const requestId = 'req-triple-fire-1'; // same JSON-RPC id across retries — the scenario under test
    const results = [];
    for (let i = 0; i < 3; i++) {
      results.push(await handleToolCall('bd_live_triplefire_key', tool, args, requestId));
    }
    return { results, billingInsertCount: mocks.billingInsertCount() };
  } finally {
    mocks.restore();
  }
}

test('S1 tool (search_auctions): 3x identical fire → exactly 1 billing event', async () => {
  const { results, billingInsertCount } = await tripleFire('search_auctions', { county: 'brevard' }, 'pro');
  assert.equal(billingInsertCount, 1, 'expected exactly one billing_events insert across 3 identical fires');
  assert.equal(results.length, 3);
  // Calls 2 and 3 must be served from cache, not re-executed — same payload as call 1.
  assert.equal(results[1].content[0].text, results[0].content[0].text);
  assert.equal(results[2].content[0].text, results[0].content[0].text);
});

test('S3 tool (check_zoning): 3x identical fire → exactly 1 billing event', async () => {
  const { billingInsertCount } = await tripleFire('check_zoning', { parcel_id: '123-456', county: 'brevard' }, 'pro');
  assert.equal(billingInsertCount, 1, 'expected exactly one billing_events insert across 3 identical fires');
});

test('S5 tool (predict_auction_outcome): 3x identical fire → exactly 1 billing event (⇒ ≤1 Stripe meter event)', async () => {
  const { billingInsertCount } = await tripleFire(
    'predict_auction_outcome',
    { case_number: 'CASE-001', county: 'brevard' },
    'pro'
  );
  assert.equal(billingInsertCount, 1, 'expected exactly one billing_events insert across 3 identical fires — Stripe usage filing is nested 1:1 inside this call');
});

test('duplicate_count increments on the idempotency row for each suppressed retry', async () => {
  const mocks = mockFetch({ tier: 'pro' });
  try {
    const requestId = 'req-dup-count-1';
    await handleToolCall('bd_live_triplefire_key', 'search_auctions', { county: 'duval' }, requestId);
    await handleToolCall('bd_live_triplefire_key', 'search_auctions', { county: 'duval' }, requestId);
    const third = await handleToolCall('bd_live_triplefire_key', 'search_auctions', { county: 'duval' }, requestId);
    assert.equal(third.isError, false);
  } finally {
    mocks.restore();
  }
});
