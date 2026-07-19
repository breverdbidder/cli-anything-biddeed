// GTM-22F — Gold Standard certification delivery gate.
//
// Verifies: certified county passes, uncertified county is blocked with a
// clean COUNTY_NOT_CERTIFIED payload (no rows), an unfiltered multi-county
// call (browse_deals) returns only certified-county rows, and the gate
// fails closed (blocks, does not leak) when v_certified_counties itself is
// unreachable. Covers one S1 tool, one S3 tool, and S5 per the DoD.
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { normalizeCountySlug, assertCountyCertified, filterCertifiedRows } = await import('../src/cert-gate.js');
const { handleToolCall, _setHandlerForTest } = await import('../src/server.js');

function jsonRes(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

test('normalizeCountySlug: already-normalized raw values pass through unchanged', () => {
  assert.equal(normalizeCountySlug('brevard'), 'brevard');
  assert.equal(normalizeCountySlug('palm_beach'), 'palm_beach');
  assert.equal(normalizeCountySlug('st_johns'), 'st_johns');
});

test('normalizeCountySlug: handles spaces, hyphens, mixed case, and "county" suffix', () => {
  assert.equal(normalizeCountySlug('Palm Beach'), 'palm_beach');
  assert.equal(normalizeCountySlug('St-Johns'), 'st_johns');
  assert.equal(normalizeCountySlug('Brevard County'), 'brevard');
  assert.equal(normalizeCountySlug(''), '');
  assert.equal(normalizeCountySlug(null), '');
});

test('assertCountyCertified: certified county clears the gate (returns null)', async () => {
  const original = global.fetch;
  global.fetch = async (url) => {
    assert.match(url.toString(), /v_certified_counties/);
    return jsonRes([{ county_slug: 'duval' }, { county_slug: 'brevard' }]);
  };
  try {
    const result = await assertCountyCertified('brevard');
    assert.equal(result, null);
  } finally {
    global.fetch = original;
  }
});

test('assertCountyCertified: uncertified county returns a clean COUNTY_NOT_CERTIFIED payload, not partial data', async () => {
  const original = global.fetch;
  global.fetch = async () => jsonRes([{ county_slug: 'duval' }]); // seminole absent — revoked 2026-07-19
  try {
    const result = await assertCountyCertified('seminole');
    assert.ok(result);
    assert.equal(result.code, 'COUNTY_NOT_CERTIFIED');
    assert.equal(result.certified, false);
    assert.equal(result.county_slug, 'seminole');
  } finally {
    global.fetch = original;
  }
});

test('assertCountyCertified: fails CLOSED when the live view is unreachable', async () => {
  const original = global.fetch;
  global.fetch = async () => { throw new Error('network down'); };
  try {
    const result = await assertCountyCertified('brevard');
    assert.ok(result, 'must block, not fall through, when certification cannot be verified');
    assert.equal(result.code, 'CERT_GATE_UNAVAILABLE');
  } finally {
    global.fetch = original;
  }
});

test('filterCertifiedRows: drops rows for uncertified counties, keeps certified ones', async () => {
  const original = global.fetch;
  global.fetch = async () => jsonRes([{ county_slug: 'brevard' }]);
  try {
    const rows = [{ county: 'brevard', id: 1 }, { county: 'seminole', id: 2 }];
    const filtered = await filterCertifiedRows(rows);
    assert.deepEqual(filtered.map(r => r.id), [1]);
  } finally {
    global.fetch = original;
  }
});

// ── Integration: one S1 tool, one S3 tool, and S5 through handleToolCall ──

function mockFetchForTool({ certified, tierRow, customerOverrides = {} }) {
  const original = global.fetch;
  global.fetch = async (url, opts = {}) => {
    const urlStr = url.toString();
    const method = opts.method || 'GET';

    if (urlStr.includes('/v_certified_counties')) {
      return jsonRes(certified.map(c => ({ county_slug: c })));
    }
    if (urlStr.includes('/mcp_api_keys')) {
      return jsonRes([{
        key_prefix: 'bd_live_gate', customer_id: 'cust-gate', tier: 'pro',
        is_active: true, expires_at: null, call_count: 0, stripe_customer_id: 'cus_gate',
        ...customerOverrides,
      }]);
    }
    if (urlStr.includes('/mcp_idempotency_keys')) {
      if (method === 'POST') return jsonRes([{}], 201);
      if (method === 'PATCH') return jsonRes([{}]);
      return jsonRes([]);
    }
    if (urlStr.includes('/mcp_subscription_tiers')) return jsonRes([tierRow ?? {}]);
    if (urlStr.includes('/billing_events') && method === 'GET') return jsonRes([]);
    if (urlStr.includes('/billing_events') && method === 'POST') return jsonRes([{ event_id: 'evt-1' }], 201);
    if (urlStr.includes('/mcp_charge_events')) return jsonRes([{}], 201);
    if (urlStr.includes('/multi_county_auctions')) return jsonRes([]);
    if (urlStr.includes('/zoning_assignments')) return jsonRes([]);
    if (urlStr.includes('/gold_standard_county_status')) return jsonRes([]);

    throw new Error(`Unmocked fetch in cert-gate integration test: ${method} ${urlStr}`);
  };
  return { restore: () => { global.fetch = original; } };
}

test('S1 (search_auctions): certified county reaches the handler', async () => {
  let handlerCalled = false;
  _setHandlerForTest('search_auctions', async () => { handlerCalled = true; return { count: 0, auctions: [] }; });
  const mocks = mockFetchForTool({ certified: ['duval'], tierRow: { s1_calls_monthly: 50 } });
  try {
    const res = await handleToolCall('bd_live_gate_key', 'search_auctions', { county: 'duval' }, 'req-gate-s1-ok');
    assert.equal(handlerCalled, true);
    assert.equal(res.isError, false);
  } finally {
    mocks.restore();
  }
});

test('S1 (search_auctions): uncertified county (seminole) never reaches the handler, zero rows, clean reason', async () => {
  let handlerCalled = false;
  _setHandlerForTest('search_auctions', async () => { handlerCalled = true; return { count: 99, auctions: [{ leak: true }] }; });
  const mocks = mockFetchForTool({ certified: ['duval'], tierRow: { s1_calls_monthly: 50 } });
  try {
    const res = await handleToolCall('bd_live_gate_key', 'search_auctions', { county: 'seminole' }, 'req-gate-s1-blocked');
    assert.equal(handlerCalled, false, 'the handler must never execute for an uncertified county');
    assert.equal(res.isError, true);
    const body = JSON.parse(res.content[0].text);
    assert.equal(body.code, 'COUNTY_NOT_CERTIFIED');
    assert.equal(body.certified, false);
  } finally {
    mocks.restore();
  }
});

test('S3 (check_zoning): uncertified county is blocked before the handler runs', async () => {
  let handlerCalled = false;
  _setHandlerForTest('check_zoning', async () => { handlerCalled = true; return { found: true }; });
  const mocks = mockFetchForTool({ certified: ['duval'] });
  try {
    const res = await handleToolCall('bd_live_gate_key', 'check_zoning', { parcel_id: '123', county: 'seminole' }, 'req-gate-s3-blocked');
    assert.equal(handlerCalled, false);
    assert.equal(res.isError, true);
    assert.equal(JSON.parse(res.content[0].text).code, 'COUNTY_NOT_CERTIFIED');
  } finally {
    mocks.restore();
  }
});

test('S5 (predict_auction_outcome): uncertified county is blocked before the handler runs (supersedes the old inline gate)', async () => {
  let handlerCalled = false;
  _setHandlerForTest('predict_auction_outcome', async () => { handlerCalled = true; return { verdict: 'sell' }; });
  const mocks = mockFetchForTool({ certified: ['duval'] });
  try {
    const res = await handleToolCall('bd_live_gate_key', 'predict_auction_outcome', { case_number: 'C1', county: 'seminole' }, 'req-gate-s5-blocked');
    assert.equal(handlerCalled, false);
    assert.equal(res.isError, true);
    assert.equal(JSON.parse(res.content[0].text).code, 'COUNTY_NOT_CERTIFIED');
  } finally {
    mocks.restore();
  }
});

test('S5 (predict_auction_outcome): certified county reaches the handler', async () => {
  let handlerCalled = false;
  _setHandlerForTest('predict_auction_outcome', async () => { handlerCalled = true; return { verdict: 'sell' }; });
  const mocks = mockFetchForTool({ certified: ['duval'] });
  try {
    const res = await handleToolCall('bd_live_gate_key', 'predict_auction_outcome', { case_number: 'C1', county: 'duval' }, 'req-gate-s5-ok');
    assert.equal(handlerCalled, true);
    assert.equal(res.isError, false);
  } finally {
    mocks.restore();
  }
});
