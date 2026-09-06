// Issue #20043 item 4 / #20044 item 1 — sections 11-14 context layers
// (neighborhood, FEMA, schools, median income). FEMA NFHL is public/keyless
// and wired live. Census ACS is called keyless whenever CENSUS_API_KEY is
// unset (never hard-gated) — any failure (missing-key redirect, rate-limit,
// 5xx, parse error) renders the generic "Pending — Census API unavailable
// at generation time", never a fabricated score, and is never cached so the
// next report generation retries automatically.
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { fetchFemaFloodZone, fetchNeighborhoodAcs } = await import('../src/report/context-layers.js');

test('FEMA: no lat/lon on file renders Pending with a named gate', async () => {
  const result = await fetchFemaFloodZone(null, null, '32901', { get: async () => [] });
  assert.equal(result.available, false);
  assert.match(result.reason, /Pending/);
});

test('FEMA: cache hit short-circuits the live fetch', async () => {
  const cachedPayload = { available: true, zone: 'AE', sfha: true, bfe: 12, source: 'FEMA NFHL public REST' };
  const get = async (path) => {
    assert.match(path, /context_layer_cache/);
    assert.match(path, /layer=eq\.fema/);
    return [{ payload: cachedPayload, fetched_at: new Date().toISOString() }];
  };
  const result = await fetchFemaFloodZone(28.09, -80.66, '32901', { get });
  assert.deepEqual(result, cachedPayload);
});

test('ACS: no CENSUS_API_KEY configured still attempts a keyless call, and a missing-key redirect renders the generic Pending message, never a fabricated score', async () => {
  delete process.env.CENSUS_API_KEY;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.doesNotMatch(url, /[?&]key=/); // no key= param when CENSUS_API_KEY is unset
    return {
      ok: true,
      url: 'https://api.census.gov/data/missing_key.html',
      headers: new Map([['x-datawebapi-keyerror', '1']]),
      json: async () => { throw new Error('not json'); },
    };
  };
  try {
    const result = await fetchNeighborhoodAcs('32901', { get: async () => [], insert: async () => {} });
    assert.equal(result.available, false);
    assert.equal(result.reason, 'Pending — Census API unavailable at generation time');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('ACS: CENSUS_API_KEY configured includes key= param and a successful call is delivered (never fabricated when it fails)', async () => {
  process.env.CENSUS_API_KEY = 'test-key-123';
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.match(url, /[?&]key=test-key-123/);
    return {
      ok: true,
      url,
      headers: new Map(),
      json: async () => [
        ['B19013_001E', 'B01003_001E', 'B17001_002E', 'B17001_001E', 'B25003_002E', 'B25003_001E', 'B25064_001E', 'zip code tabulation area'],
        ['65000', '12000', '900', '11000', '4000', '4800', '1450', '32901'],
      ],
    };
  };
  try {
    const result = await fetchNeighborhoodAcs('32901', { get: async () => [], insert: async () => {} });
    assert.equal(result.available, true);
    assert.equal(result.median_income, 65000);
  } finally {
    globalThis.fetch = originalFetch;
    delete process.env.CENSUS_API_KEY;
  }
});

test('ACS: no zip on file renders Pending without attempting a fetch', async () => {
  const result = await fetchNeighborhoodAcs(null, { get: async () => [] });
  assert.equal(result.available, false);
  assert.match(result.reason, /Pending/);
});
