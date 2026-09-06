// Issue #20043 item 4 — sections 11-14 context layers (neighborhood, FEMA,
// schools, median income). FEMA NFHL is public/keyless and wired live.
// Census ACS requires CENSUS_API_KEY, which is not configured in this repo
// as of 2026-09-06 (confirmed: the endpoint 302s to missing_key.html without
// one) — it must render Pending with that exact gate, never fabricate a
// score.
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

test('ACS: no CENSUS_API_KEY configured renders Pending with the exact gate, never a fabricated score', async () => {
  delete process.env.CENSUS_API_KEY;
  const result = await fetchNeighborhoodAcs('32901', { get: async () => [], insert: async () => {} });
  assert.equal(result.available, false);
  assert.match(result.reason, /CENSUS_API_KEY not configured/);
});

test('ACS: no zip on file renders Pending without attempting a fetch', async () => {
  const result = await fetchNeighborhoodAcs(null, { get: async () => [] });
  assert.equal(result.available, false);
  assert.match(result.reason, /Pending/);
});
