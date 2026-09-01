// Unit coverage for credits.js checkAndSpendCredits — mocks the Supabase
// REST RPC endpoint directly (mirrors packages/biddeed-mcp/test/charge-
// ordering.test.js's mockFetch pattern) rather than importing server.js,
// since @modelcontextprotocol/sdk in this environment ships without a
// built dist/ (pre-existing gap, unrelated to this change — see
// packages/biddeed-mcp/src/server.js import chain).
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { checkAndSpendCredits } = await import('../src/credits.js');

function jsonRes(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function mockRpc(response, { throwError = false } = {}) {
  const original = global.fetch;
  const calls = [];
  global.fetch = async (url, opts = {}) => {
    calls.push({ url: url.toString(), body: opts.body ? JSON.parse(opts.body) : null });
    if (throwError) throw new Error('network down');
    return jsonRes(response);
  };
  return { calls, restore: () => { global.fetch = original; } };
}

test('checkAndSpendCredits — sufficient balance charges and returns ok', async () => {
  const mock = mockRpc({ ok: true, charged: true, cost: 75, balance: 425 });
  try {
    const result = await checkAndSpendCredits({
      customerRecord: { customer_id: 'cust-1' },
      toolName: 'get_lien_stack',
      streamId: 's2',
    });
    assert.equal(result.ok, true);
    assert.equal(result.charged, true);
    assert.equal(result.cost, 75);
    assert.equal(result.balance, 425);
    assert.equal(mock.calls.length, 1);
    assert.match(mock.calls[0].url, /\/rpc\/mcp_credit_spend$/);
    assert.deepEqual(mock.calls[0].body, {
      p_customer_id: 'cust-1', p_tool_name: 'get_lien_stack', p_stream_id: 's2', p_mca_id: null,
    });
  } finally {
    mock.restore();
  }
});

test('checkAndSpendCredits — insufficient balance rejects the call (negative test)', async () => {
  const mock = mockRpc({ ok: false, code: 'insufficient_credits', balance: 425, cost: 2500, message: 'Insufficient credits: need 2500, have 425. Top up at biddeed.ai/upgrade' });
  try {
    const result = await checkAndSpendCredits({
      customerRecord: { customer_id: 'cust-1' },
      toolName: 'predict_auction_outcome',
      streamId: 's5',
    });
    assert.equal(result.ok, false);
    assert.equal(result.outcome, 'blocked_insufficient_credits');
    assert.equal(result.balance, 425);
    assert.equal(result.cost, 2500);
    assert.match(result.message, /Insufficient credits/);
  } finally {
    mock.restore();
  }
});

test('checkAndSpendCredits — unpriced tool is a no-op (does not block)', async () => {
  const mock = mockRpc({ ok: true, charged: false, cost: 0 });
  try {
    const result = await checkAndSpendCredits({
      customerRecord: { customer_id: 'cust-1' },
      toolName: 'search_distressed',
      streamId: 's2',
    });
    assert.equal(result.ok, true);
    assert.equal(result.charged, false);
  } finally {
    mock.restore();
  }
});

test('checkAndSpendCredits — fails CLOSED when the RPC is unreachable', async () => {
  const mock = mockRpc(null, { throwError: true });
  try {
    const result = await checkAndSpendCredits({
      customerRecord: { customer_id: 'cust-1' },
      toolName: 'get_lien_stack',
      streamId: 's2',
    });
    assert.equal(result.ok, false, 'an unreachable wallet must block the call, not let it through free');
    assert.equal(result.outcome, 'blocked_credits_unavailable');
  } finally {
    mock.restore();
  }
});
