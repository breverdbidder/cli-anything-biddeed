// GET /report/json — issue #18307 (S5 v1.2 interactive HTML report). Unlike
// /report/pdf, this route bypasses handleToolCall entirely (auth-only, no
// billing, no cert-gate re-check) since it's a re-view of an already-paid
// report, not a new sale — see the comment in src/http.js.
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { handleReportJsonRequest } = await import('../src/http.js');

function jsonRes(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function makeReqRes(url) {
  const req = { url, headers: { host: 'mcp.biddeed.ai' } };
  const res = {
    statusCode: null,
    headers: null,
    body: null,
    writeHead(status, headers) { this.statusCode = status; this.headers = headers; },
    end(chunk) { this.body = chunk; },
  };
  return { req, res };
}

const AUCTION_UNLOCATABLE = {
  case_number: '422024CA002330CAAXMX', county: 'marion',
  property_address: null, judgment_amount: 718587.84, plaintiff_max_bid: 718587.84,
  sale_type: 'foreclosure', id: 'mca-2330',
};

test('GET /report/json: valid key + existing mca_id returns 200 with report JSON, no billing/idempotency calls', async () => {
  const original = global.fetch;
  let billingCalled = false;
  let idempotencyCalled = false;
  global.fetch = async (url) => {
    const urlStr = url.toString();
    if (urlStr.includes('/mcp_api_keys')) {
      return jsonRes([{ key_prefix: 'bd_live_test', customer_id: 'cust-json-1', tier: 'pro', is_active: true, expires_at: null, call_count: 0, stripe_customer_id: 'cus_json_1' }]);
    }
    if (urlStr.includes('/multi_county_auctions')) return jsonRes([AUCTION_UNLOCATABLE]);
    if (urlStr.includes('/billing_events')) { billingCalled = true; return jsonRes([{ event_id: 'evt-json-1' }], 201); }
    if (urlStr.includes('/mcp_idempotency_keys')) { idempotencyCalled = true; return jsonRes([]); }
    if (urlStr.includes('/mcp_charge_events')) return jsonRes([{}], 201);
    return jsonRes([]);
  };
  try {
    const { req, res } = makeReqRes('/report/json?mca_id=mca-2330');
    await handleReportJsonRequest(req, res, 'bd_live_test_key');

    assert.equal(res.statusCode, 200);
    assert.equal(res.headers['Content-Type'], 'application/json');
    const payload = JSON.parse(res.body);
    assert.equal(payload.mca_id, 'mca-2330');
    assert.ok(payload.report, 'response must include the report object');
    assert.equal(payload.report.cover.verdict, 'SKIP', 'unlocatable subject report shape must be preserved');
    assert.equal(billingCalled, false, 'viewing a report must never write a billing_events row');
    assert.equal(idempotencyCalled, false, 'viewing a report must never touch the idempotency store');
  } finally {
    global.fetch = original;
  }
});

test('GET /report/json: missing mca_id returns 400', async () => {
  const { req, res } = makeReqRes('/report/json');
  await handleReportJsonRequest(req, res, 'bd_live_test_key');
  assert.equal(res.statusCode, 400);
  assert.equal(JSON.parse(res.body).error, 'mca_id query param is required');
});

test('GET /report/json: invalid API key returns 401', async () => {
  const original = global.fetch;
  global.fetch = async (url) => {
    const urlStr = url.toString();
    if (urlStr.includes('/mcp_api_keys')) return jsonRes([]); // no matching key
    return jsonRes([]);
  };
  try {
    const { req, res } = makeReqRes('/report/json?mca_id=mca-2330');
    await handleReportJsonRequest(req, res, 'bd_live_bogus_key');
    assert.equal(res.statusCode, 401);
  } finally {
    global.fetch = original;
  }
});

test('GET /report/json: auction not found returns 404 with AUCTION_NOT_FOUND', async () => {
  const original = global.fetch;
  global.fetch = async (url) => {
    const urlStr = url.toString();
    if (urlStr.includes('/mcp_api_keys')) {
      return jsonRes([{ key_prefix: 'bd_live_test', customer_id: 'cust-json-2', tier: 'pro', is_active: true, expires_at: null, call_count: 0, stripe_customer_id: 'cus_json_2' }]);
    }
    if (urlStr.includes('/multi_county_auctions')) return jsonRes([]); // not found
    return jsonRes([]);
  };
  try {
    const { req, res } = makeReqRes('/report/json?mca_id=does-not-exist');
    await handleReportJsonRequest(req, res, 'bd_live_test_key');
    assert.equal(res.statusCode, 404);
    assert.equal(JSON.parse(res.body).error, 'AUCTION_NOT_FOUND');
  } finally {
    global.fetch = original;
  }
});
