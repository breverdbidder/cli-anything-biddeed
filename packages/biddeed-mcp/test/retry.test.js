// Issue #20090 — retry/backoff wrapper unit coverage. Uses a mocked global
// fetch (same pattern as usage-log.test.js) with short backoff/timeout
// overrides so the suite runs fast; the production defaults (150/450/1200ms
// backoff, 5s timeout) are exercised separately by the live smoke test.
import { test } from 'node:test';
import assert from 'node:assert/strict';

const { fetchWithRetry } = await import('../src/retry.js');

function mockFetch(handler) {
  const original = global.fetch;
  global.fetch = handler;
  return () => { global.fetch = original; };
}

const FAST = { backoffMs: [1, 1, 1], timeoutMs: 200 };

test('retries a connection-refused network error and succeeds on the 2nd attempt', async (t) => {
  let calls = 0;
  t.after(mockFetch(async () => {
    calls++;
    if (calls === 1) {
      const err = new TypeError('fetch failed');
      err.cause = { code: 'ECONNREFUSED' };
      throw err;
    }
    return new Response('ok', { status: 200 });
  }));

  const res = await fetchWithRetry('https://x.test/rest/v1/foo', {}, FAST);
  assert.equal(res.status, 200);
  assert.equal(calls, 2);
});

test('retries a PostgREST 503 and succeeds once Postgres is back', async (t) => {
  let calls = 0;
  t.after(mockFetch(async () => {
    calls++;
    if (calls < 3) return new Response('service unavailable', { status: 503 });
    return new Response('ok', { status: 200 });
  }));

  const res = await fetchWithRetry('https://x.test/rest/v1/foo', {}, FAST);
  assert.equal(res.status, 200);
  assert.equal(calls, 3);
});

test('never retries a 4xx application error', async (t) => {
  let calls = 0;
  t.after(mockFetch(async () => {
    calls++;
    return new Response(JSON.stringify({ message: 'not found' }), { status: 404 });
  }));

  const res = await fetchWithRetry('https://x.test/rest/v1/foo', {}, FAST);
  assert.equal(res.status, 404);
  assert.equal(calls, 1);
});

test('gives up after the configured attempt count and surfaces the last error', async (t) => {
  let calls = 0;
  t.after(mockFetch(async () => {
    calls++;
    const err = new TypeError('fetch failed');
    err.cause = { code: 'ECONNREFUSED' };
    throw err;
  }));

  await assert.rejects(() => fetchWithRetry('https://x.test/rest/v1/foo', {}, { ...FAST, attempts: 3 }));
  assert.equal(calls, 3);
});

test('connect-only mode retries a pre-execution ECONNREFUSED', async (t) => {
  let calls = 0;
  t.after(mockFetch(async () => {
    calls++;
    if (calls === 1) {
      const err = new TypeError('fetch failed');
      err.cause = { code: 'ECONNREFUSED' };
      throw err;
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  }));

  const res = await fetchWithRetry('https://x.test/rest/v1/rpc/mcp_credit_grant', {}, { ...FAST, retryMode: 'connect-only' });
  assert.equal(res.status, 200);
  assert.equal(calls, 2);
});

test('connect-only mode does NOT retry an ambiguous mid-stream reset (could be a lost response to an already-applied write)', async (t) => {
  let calls = 0;
  t.after(mockFetch(async () => {
    calls++;
    const err = new TypeError('fetch failed');
    err.cause = { code: 'ECONNRESET' };
    throw err;
  }));

  await assert.rejects(() => fetchWithRetry('https://x.test/rest/v1/rpc/mcp_credit_grant', {}, { ...FAST, retryMode: 'connect-only' }));
  assert.equal(calls, 1);
});

test('connect-only mode DOES retry a 503 (PostgREST rejected before the RPC ever ran)', async (t) => {
  let calls = 0;
  t.after(mockFetch(async () => {
    calls++;
    if (calls === 1) return new Response('service unavailable', { status: 503 });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  }));

  const res = await fetchWithRetry('https://x.test/rest/v1/rpc/mcp_credit_grant', {}, { ...FAST, retryMode: 'connect-only' });
  assert.equal(res.status, 200);
  assert.equal(calls, 2);
});

test('connect-only mode does NOT retry our own client-side timeout (AbortError) — the write may already be mid-flight', async (t) => {
  let calls = 0;
  t.after(mockFetch(async (url, init) => {
    calls++;
    return new Promise((resolve, reject) => {
      init.signal.addEventListener('abort', () => {
        const err = new Error('The operation was aborted');
        err.name = 'AbortError';
        reject(err);
      });
    });
  }));

  await assert.rejects(() => fetchWithRetry('https://x.test/rest/v1/rpc/mcp_credit_grant', {}, { backoffMs: [1], timeoutMs: 20, retryMode: 'connect-only' }));
  assert.equal(calls, 1);
});

test('retries a Cloudflare 521 (edge cannot reach the Supabase origin at all) with an HTML body, in both modes', async (t) => {
  let calls = 0;
  t.after(mockFetch(async () => {
    calls++;
    if (calls === 1) return new Response('<html>521 Web server is down</html>', { status: 521, headers: { 'Content-Type': 'text/html' } });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  }));

  const res = await fetchWithRetry('https://x.test/rest/v1/rpc/mcp_credit_grant', {}, { ...FAST, retryMode: 'connect-only' });
  assert.equal(res.status, 200);
  assert.equal(calls, 2);
});

test('full mode DOES retry our own client-side timeout (AbortError) for a plain read', async (t) => {
  let calls = 0;
  t.after(mockFetch(async (url, init) => {
    calls++;
    if (calls === 1) {
      return new Promise((_, reject) => {
        init.signal.addEventListener('abort', () => {
          const err = new Error('The operation was aborted');
          err.name = 'AbortError';
          reject(err);
        });
      });
    }
    return new Response(JSON.stringify([{ id: 1 }]), { status: 200 });
  }));

  const res = await fetchWithRetry('https://x.test/rest/v1/foo', {}, { backoffMs: [1, 1], timeoutMs: 20 });
  assert.equal(res.status, 200);
  assert.equal(calls, 2);
});
