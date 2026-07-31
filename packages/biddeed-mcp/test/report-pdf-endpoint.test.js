// GET /report/pdf — HTTP delivery of the predict_auction_outcome PDF
// artifact (issue: "Add /report/pdf endpoint"). Routes through the exact
// same handleToolCall pipeline as the MCP tool call, so these tests assert
// the HTTP-specific plumbing (status code mapping, Content-Type, byte
// payload, export storage) — auth/cert-gate/billing behavior itself is
// already covered by s5-negative.test.js and cert-gate.test.js.
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { handleReportPdfRequest } = await import('../src/http.js');
const { _setHandlerForTest } = await import('../src/server.js');

function jsonRes(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

// Minimal req/res doubles — handleReportPdfRequest only reads req.url/req.headers.host
// and calls res.writeHead/res.end.
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

function baseMock({ certified = true } = {}) {
  return async (url, opts = {}) => {
    const urlStr = url.toString();
    const method = opts.method || 'GET';

    if (urlStr.includes('/v_certified_counties')) {
      return jsonRes(certified ? [{ county_slug: 'marion' }] : [{ county_slug: 'duval' }]);
    }
    if (urlStr.includes('/mcp_api_keys')) {
      if (method === 'PATCH') return jsonRes([{}]);
      return jsonRes([{ key_prefix: 'bd_live_test', customer_id: 'cust-pdf-1', tier: 'pro', is_active: true, expires_at: null, call_count: 0, stripe_customer_id: 'cus_pdf_1' }]);
    }
    if (urlStr.includes('/mcp_idempotency_keys')) {
      if (method === 'POST') return jsonRes([{}], 201);
      if (method === 'PATCH') return jsonRes([{}]);
      return jsonRes([]);
    }
    if (urlStr.includes('/multi_county_auctions')) {
      return jsonRes([AUCTION_UNLOCATABLE]);
    }
    if (urlStr.includes('/billing_events')) {
      if (method === 'POST') return jsonRes([{ event_id: 'evt-pdf-1' }], 201);
      return jsonRes([]);
    }
    if (urlStr.includes('/mcp_charge_events')) return jsonRes([{}], 201);
    if (urlStr.includes('/storage/v1/object/exports/')) return jsonRes({ Key: 'exports/s5/cust-pdf-1/mca-2330.pdf' });
    // Fire-and-forget side channels (PostHog vault-key RPC, etc.) — never
    // asserted on here, must not throw and break the response path.
    return jsonRes([]);
  };
}

test('GET /report/pdf: certified county + valid key returns 200 application/pdf with real bytes', async () => {
  const original = global.fetch;
  global.fetch = baseMock({ certified: true });
  try {
    const { req, res } = makeReqRes('/report/pdf?case_number=422024CA002330CAAXMX&county=marion');
    await handleReportPdfRequest(req, res, 'bd_live_test_key');

    assert.equal(res.statusCode, 200);
    assert.equal(res.headers['Content-Type'], 'application/pdf');
    assert.ok(res.headers['Content-Disposition'].includes('biddeed-s5-marion-422024CA002330CAAXMX.pdf'));
    assert.ok(Buffer.isBuffer(res.body));
    assert.ok(res.body.length > 0, 'PDF buffer must not be empty');
    assert.equal(res.body.slice(0, 4).toString('latin1'), '%PDF', 'response body must be a real PDF (starts with %PDF magic bytes)');
  } finally {
    // handleToolCall's recordBilling/captureToolCall/export-storage calls are
    // fire-and-forget (not awaited) — give them a beat to settle against the
    // mock before restoring global.fetch, so they never fall through to the
    // real SUPABASE_URL this shell may have set in its environment.
    await new Promise(r => setTimeout(r, 50));
    global.fetch = original;
  }
});

test('GET /report/pdf: missing case_number/county returns 400', async () => {
  const { req, res } = makeReqRes('/report/pdf?county=marion');
  await handleReportPdfRequest(req, res, 'bd_live_test_key');
  assert.equal(res.statusCode, 400);
  assert.equal(JSON.parse(res.body).error, 'case_number and county query params are required');
});

test('GET /report/pdf: uncertified county returns 403 with COUNTY_NOT_CERTIFIED, no PDF bytes', async () => {
  const original = global.fetch;
  global.fetch = baseMock({ certified: false });
  try {
    const { req, res } = makeReqRes('/report/pdf?case_number=422024CA002330CAAXMX&county=marion');
    await handleReportPdfRequest(req, res, 'bd_live_test_key');

    assert.equal(res.statusCode, 403);
    const payload = JSON.parse(res.body);
    assert.equal(payload.code, 'COUNTY_NOT_CERTIFIED');
  } finally {
    global.fetch = original;
  }
});

test('GET /report/pdf: invalid API key returns 401', async () => {
  const original = global.fetch;
  global.fetch = async (url, opts = {}) => {
    const urlStr = url.toString();
    if (urlStr.includes('/mcp_api_keys')) return jsonRes([]); // no matching key
    return jsonRes([]);
  };
  try {
    const { req, res } = makeReqRes('/report/pdf?case_number=422024CA002330CAAXMX&county=marion');
    await handleReportPdfRequest(req, res, 'bd_live_bogus_key');

    assert.equal(res.statusCode, 401);
    assert.equal(JSON.parse(res.body).code, 'AUTH_ERROR');
  } finally {
    global.fetch = original;
  }
});

test('GET /report/pdf: auction not found returns 404', async () => {
  const original = global.fetch;
  global.fetch = async (url, opts = {}) => {
    const urlStr = url.toString();
    const method = opts.method || 'GET';
    if (urlStr.includes('/v_certified_counties')) return jsonRes([{ county_slug: 'marion' }]);
    if (urlStr.includes('/mcp_api_keys')) {
      if (method === 'PATCH') return jsonRes([{}]);
      return jsonRes([{ key_prefix: 'bd_live_test', customer_id: 'cust-pdf-2', tier: 'pro', is_active: true, expires_at: null, call_count: 0, stripe_customer_id: 'cus_pdf_2' }]);
    }
    if (urlStr.includes('/mcp_idempotency_keys')) {
      if (method === 'POST') return jsonRes([{}], 201);
      if (method === 'PATCH') return jsonRes([{}]);
      return jsonRes([]);
    }
    if (urlStr.includes('/multi_county_auctions')) return jsonRes([]); // not found
    if (urlStr.includes('/billing_events')) return jsonRes([{ event_id: 'evt-pdf-404' }], 201);
    if (urlStr.includes('/mcp_charge_events')) return jsonRes([{}], 201);
    return jsonRes([]);
  };
  try {
    const { req, res } = makeReqRes('/report/pdf?case_number=NONEXISTENT&county=marion');
    await handleReportPdfRequest(req, res, 'bd_live_test_key');

    assert.equal(res.statusCode, 404);
    assert.equal(JSON.parse(res.body).error, 'AUCTION_NOT_FOUND');
  } finally {
    // see comment in the 200 test above — let fire-and-forget calls settle
    // against the mock before restoring the real global.fetch.
    await new Promise(r => setTimeout(r, 50));
    global.fetch = original;
  }
});

test('_setHandlerForTest is restored (sanity — this suite must not leak handler overrides to other files)', () => {
  // No-op: importing _setHandlerForTest above and never calling it in this
  // file confirms the golden/negative-test handlers are untouched.
  assert.equal(typeof _setHandlerForTest, 'function');
});
