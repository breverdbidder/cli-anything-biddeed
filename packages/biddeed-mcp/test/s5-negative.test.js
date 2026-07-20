// GTM-22 S5 REPORT ENGINE — negative tests, issue #12853 DoD.
//
// NEGATIVE TEST 1: an uncertified county is refused through the real gate
// path in server.js (not a re-implementation of the gate) — zero billing
// events written, handler never called.
// NEGATIVE TEST 2 & 3 live in s5-report-golden.test.js (hidden cap renders
// "Hidden" with no "$0"; unlocatable subject has no estimate + the exact
// refusal sentence) — reproduced here at the handleToolCall level too, so
// the negative behavior is proven through the real dispatch path, not just
// the composer unit.
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { handleToolCall, _setHandlerForTest } = await import('../src/server.js');

function jsonRes(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

test('NEGATIVE TEST 1: predict_auction_outcome for an uncertified county is refused before billing — billing_events count unchanged', async () => {
  let handlerCalled = false;
  let billingPostCount = 0;
  _setHandlerForTest('predict_auction_outcome', async () => { handlerCalled = true; return { report: 'should never be reached' }; });

  const original = global.fetch;
  global.fetch = async (url, opts = {}) => {
    const urlStr = url.toString();
    const method = opts.method || 'GET';
    if (urlStr.includes('/v_certified_counties')) return jsonRes([{ county_slug: 'duval' }]); // marion absent
    if (urlStr.includes('/mcp_api_keys')) return jsonRes([{ key_prefix: 'bd_live_neg', customer_id: 'cust-neg', tier: 'pro', is_active: true, expires_at: null, call_count: 0, stripe_customer_id: 'cus_neg' }]);
    if (urlStr.includes('/mcp_idempotency_keys')) {
      if (method === 'POST') return jsonRes([{}], 201);
      if (method === 'PATCH') return jsonRes([{}]);
      return jsonRes([]);
    }
    if (urlStr.includes('/billing_events')) {
      if (method === 'POST') { billingPostCount += 1; return jsonRes([{ event_id: 'evt-neg' }], 201); }
      return jsonRes([]);
    }
    if (urlStr.includes('/mcp_charge_events')) return jsonRes([{}], 201);
    throw new Error(`Unmocked fetch in negative test: ${method} ${urlStr}`);
  };

  try {
    const before = billingPostCount;
    const res = await handleToolCall('bd_live_neg_key', 'predict_auction_outcome', { case_number: '422021CA000414CAAXXX', county: 'marion' }, 'req-neg-1');
    const after = billingPostCount;

    assert.equal(handlerCalled, false, 'the report engine must never run for an uncertified county');
    assert.equal(res.isError, true);
    assert.equal(JSON.parse(res.content[0].text).code, 'COUNTY_NOT_CERTIFIED');
    assert.equal(before, 0);
    assert.equal(after, 0, 'billing_events POST count must be unchanged (0 before, 0 after) — no charge for a refused call');
  } finally {
    global.fetch = original;
  }
});
