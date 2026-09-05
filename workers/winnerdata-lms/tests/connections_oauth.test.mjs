// Unit tests for the /connections OAuth routes (issue #20033), mocked
// providers -- no real Meta/TikTok/X credentials exist yet (Ariel creates
// the apps after this ships; see issue DoD: "unit-tested with mocked
// providers... report READY FOR CONNECT"). Runs via `node --test` (Node 20,
// same runtime as the deploy workflow) against the actual Worker module --
// Workers modules are plain ES modules and Node 18+ ships global fetch/
// Request/Response/URL/crypto.subtle, so no Miniflare/wrangler-dev harness
// is needed to exercise fetch()/scheduled() directly.
import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/index.js';

const BASE = 'https://lms-test.example.workers.dev';
const TEST_ENV = {
  LMS_AUTH_USER: 'test_admin',
  LMS_AUTH_PASS: 'test_pass_do_not_use_in_prod',
  SUPABASE_URL: 'https://test.supabase.example',
  SUPABASE_SERVICE_KEY: 'test-service-key',
  SUPABASE_ANON_KEY: 'test-anon-key',
  META_APP_ID: 'meta-app-id-test',
  META_APP_SECRET: 'meta-app-secret-test',
  TIKTOK_CLIENT_KEY: 'tiktok-client-key-test',
  TIKTOK_CLIENT_SECRET: 'tiktok-client-secret-test',
  X_API_KEY: 'x-api-key-test',
  X_API_SECRET: 'x-api-secret-test',
};

// --- replicate the Worker's session-cookie signing so tests can mint a
// valid session without exporting internal functions from src/index.js. ---
function base64url(bytes) {
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
async function sign(env, domain, payload) {
  const enc = new TextEncoder();
  const keyDigest = await crypto.subtle.digest('SHA-256', enc.encode(`${env.LMS_AUTH_USER}:${env.LMS_AUTH_PASS}:${domain}`));
  const key = await crypto.subtle.importKey('raw', keyDigest, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sigBuf = await crypto.subtle.sign('HMAC', key, enc.encode(payload));
  return base64url(new Uint8Array(sigBuf));
}
async function validSessionCookie(env) {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  const payload = `${env.LMS_AUTH_USER}|${exp}`;
  const sig = await sign(env, 'lms-session-v1', payload);
  return `lms_session=${base64url(new TextEncoder().encode(payload))}.${sig}`;
}
async function validOAuthStateCookie(env, platform, state, extra) {
  const exp = Math.floor(Date.now() / 1000) + 600;
  const payload = `${platform}|${state}|${exp}|${extra || ''}`;
  const sig = await sign(env, 'lms-oauth-state-v1', payload);
  return `lms_oauth_state=${base64url(new TextEncoder().encode(payload))}.${sig}`;
}

// --- fetch mock: records every call, answers Meta/TikTok/X/Supabase by URL
// pattern. Restored after each test via t.after so tests never leak mocks. ---
function installFetchMock() {
  const calls = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    calls.push({ url: u, opts });

    if (u.includes('/rest/v1/rpc/lms_oauth_vault_write') || u.includes('/rest/v1/rpc/lms_connections_health_upsert')) {
      return new Response(JSON.stringify({ ok: true, action: 'created' }), { status: 200 });
    }
    if (u.includes('graph.facebook.com') && u.includes('oauth/access_token') && u.includes('fb_exchange_token')) {
      return new Response(JSON.stringify({ access_token: 'LONG_LIVED_USER_TOKEN', expires_in: 5184000 }), { status: 200 });
    }
    if (u.includes('graph.facebook.com') && u.includes('oauth/access_token')) {
      return new Response(JSON.stringify({ access_token: 'SHORT_LIVED_USER_TOKEN', expires_in: 3600 }), { status: 200 });
    }
    if (u.includes('graph.facebook.com') && u.includes('/me/accounts')) {
      return new Response(JSON.stringify({ data: [{ id: 'PAGE123', name: 'BidDeed AI', access_token: 'PAGE_ACCESS_TOKEN', instagram_business_account: { id: 'IG456' } }] }), { status: 200 });
    }
    if (u.includes('open.tiktokapis.com/v2/oauth/token')) {
      return new Response(JSON.stringify({ access_token: 'TT_ACCESS', refresh_token: 'TT_REFRESH', open_id: 'TT_OPEN_ID', expires_in: 86400 }), { status: 200 });
    }
    if (u.includes('api.twitter.com/2/oauth2/token')) {
      return new Response(JSON.stringify({ access_token: 'X_ACCESS', refresh_token: 'X_REFRESH' }), { status: 200 });
    }
    throw new Error(`unmocked fetch: ${u}`);
  };
  return { calls, restore: () => { globalThis.fetch = realFetch; } };
}

function rpcCallsNamed(calls, fnName) {
  return calls
    .filter((c) => c.url.includes(`/rest/v1/rpc/${fnName}`))
    .map((c) => JSON.parse(c.opts.body));
}

test('GET /connections/meta/callback with no state cookie fails closed (CSRF), no stack trace', async () => {
  const mock = installFetchMock();
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    const req = new Request(`${BASE}/connections/meta/callback?state=whatever&code=abc123`, {
      headers: { Cookie: cookie },
    });
    const res = await worker.fetch(req, TEST_ENV);
    assert.equal(res.status, 403);
    const text = await res.text();
    assert.match(text, /Invalid or expired/i);
    assert.doesNotMatch(text, /at Object\.|at async|TypeError|ReferenceError/); // no raw stack trace ever shown
    // nothing should have been written to the vault on a rejected CSRF check
    assert.equal(rpcCallsNamed(mock.calls, 'lms_oauth_vault_write').length, 0);
  } finally {
    mock.restore();
  }
});

test('GET /connections/meta/callback with mismatched state fails closed (CSRF)', async () => {
  const mock = installFetchMock();
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    const stateCookie = await validOAuthStateCookie(TEST_ENV, 'meta', 'the-real-state');
    const req = new Request(`${BASE}/connections/meta/callback?state=an-attacker-supplied-state&code=abc123`, {
      headers: { Cookie: `${cookie}; ${stateCookie}` },
    });
    const res = await worker.fetch(req, TEST_ENV);
    assert.equal(res.status, 403);
    assert.equal(rpcCallsNamed(mock.calls, 'lms_oauth_vault_write').length, 0);
  } finally {
    mock.restore();
  }
});

test('GET /connections/meta/callback happy path stores exactly the vault secret names the issue names', async () => {
  const mock = installFetchMock();
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    const stateCookie = await validOAuthStateCookie(TEST_ENV, 'meta', 'good-state');
    const req = new Request(`${BASE}/connections/meta/callback?state=good-state&code=real-code`, {
      headers: { Cookie: `${cookie}; ${stateCookie}` },
    });
    const res = await worker.fetch(req, TEST_ENV);
    assert.equal(res.status, 303);
    assert.equal(res.headers.get('Location'), '/connections');

    const writes = rpcCallsNamed(mock.calls, 'lms_oauth_vault_write');
    const names = writes.map((w) => w.p_vault_secret_name).sort();
    assert.deepEqual(names, ['ig_business_account_id', 'meta_page_access_token', 'meta_page_id', 'meta_user_token_expires_at'].sort());
    const byName = Object.fromEntries(writes.map((w) => [w.p_vault_secret_name, w.p_value]));
    assert.equal(byName.meta_page_access_token, 'PAGE_ACCESS_TOKEN');
    assert.equal(byName.meta_page_id, 'PAGE123');
    assert.equal(byName.ig_business_account_id, 'IG456');
    assert.ok(writes.every((w) => w.p_platform === 'meta'));

    const healthWrites = rpcCallsNamed(mock.calls, 'lms_connections_health_upsert');
    assert.ok(healthWrites.some((h) => h.p_platform === 'facebook' && h.p_healthy === true));
    assert.ok(healthWrites.some((h) => h.p_platform === 'instagram' && h.p_healthy === true));
  } finally {
    mock.restore();
  }
});

test('GET /connections/meta/connect redirects to Facebook with a state param and sets a state cookie, no config -> fails closed', async () => {
  const mock = installFetchMock();
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    const req = new Request(`${BASE}/connections/meta/connect`, { headers: { Cookie: cookie } });
    const res = await worker.fetch(req, TEST_ENV);
    assert.equal(res.status, 303);
    const location = new URL(res.headers.get('Location'));
    assert.equal(location.hostname, 'www.facebook.com');
    assert.ok(location.searchParams.get('state'));
    assert.ok(res.headers.get('Set-Cookie').includes('lms_oauth_state='));

    const envNoConfig = { ...TEST_ENV, META_APP_ID: undefined };
    const res2 = await worker.fetch(new Request(`${BASE}/connections/meta/connect`, { headers: { Cookie: cookie } }), envNoConfig);
    assert.equal(res2.status, 400);
    const text2 = await res2.text();
    assert.match(text2, /not configured/i);
    assert.match(text2, /META_APP_ID/);
  } finally {
    mock.restore();
  }
});

test('GET /connections/tiktok/callback happy path stores tiktok_* vault secrets', async () => {
  const mock = installFetchMock();
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    const stateCookie = await validOAuthStateCookie(TEST_ENV, 'tiktok', 'tt-state');
    const req = new Request(`${BASE}/connections/tiktok/callback?state=tt-state&code=tt-code`, {
      headers: { Cookie: `${cookie}; ${stateCookie}` },
    });
    const res = await worker.fetch(req, TEST_ENV);
    assert.equal(res.status, 303);

    const writes = rpcCallsNamed(mock.calls, 'lms_oauth_vault_write');
    const byName = Object.fromEntries(writes.map((w) => [w.p_vault_secret_name, w.p_value]));
    assert.equal(byName.tiktok_access_token, 'TT_ACCESS');
    assert.equal(byName.tiktok_refresh_token, 'TT_REFRESH');
    assert.equal(byName.tiktok_open_id, 'TT_OPEN_ID');
    assert.ok(byName.tiktok_token_expires_at);

    const healthWrites = rpcCallsNamed(mock.calls, 'lms_connections_health_upsert');
    const tiktokHealth = healthWrites.find((h) => h.p_platform === 'tiktok');
    assert.equal(tiktokHealth.p_healthy, true);
    assert.match(tiktokHealth.p_detail, /audit pending/i);
  } finally {
    mock.restore();
  }
});

test('GET /connections/tiktok/callback with no state cookie fails closed (CSRF)', async () => {
  const mock = installFetchMock();
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    const req = new Request(`${BASE}/connections/tiktok/callback?state=whatever&code=abc`, { headers: { Cookie: cookie } });
    const res = await worker.fetch(req, TEST_ENV);
    assert.equal(res.status, 403);
    assert.equal(rpcCallsNamed(mock.calls, 'lms_oauth_vault_write').length, 0);
  } finally {
    mock.restore();
  }
});

test('GET /connections/x/callback happy path (PKCE) stores x_* vault secrets and sends the code_verifier', async () => {
  const mock = installFetchMock();
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    const stateCookie = await validOAuthStateCookie(TEST_ENV, 'x', 'x-state', 'the-code-verifier');
    const req = new Request(`${BASE}/connections/x/callback?state=x-state&code=x-code`, {
      headers: { Cookie: `${cookie}; ${stateCookie}` },
    });
    const res = await worker.fetch(req, TEST_ENV);
    assert.equal(res.status, 303);

    const tokenCall = mock.calls.find((c) => c.url.includes('api.twitter.com/2/oauth2/token'));
    assert.ok(tokenCall, 'expected a token exchange call to X');
    const sentBody = new URLSearchParams(tokenCall.opts.body);
    assert.equal(sentBody.get('code_verifier'), 'the-code-verifier');
    assert.match(tokenCall.opts.headers.Authorization, /^Basic /);

    const writes = rpcCallsNamed(mock.calls, 'lms_oauth_vault_write');
    const byName = Object.fromEntries(writes.map((w) => [w.p_vault_secret_name, w.p_value]));
    assert.equal(byName.x_access_token, 'X_ACCESS');
    assert.equal(byName.x_refresh_token, 'X_REFRESH');
  } finally {
    mock.restore();
  }
});

test('GET /connections/x/callback missing PKCE verifier in cookie fails closed', async () => {
  const mock = installFetchMock();
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    // state cookie present but with an empty `extra` (code_verifier) field
    const stateCookie = await validOAuthStateCookie(TEST_ENV, 'x', 'x-state', '');
    const req = new Request(`${BASE}/connections/x/callback?state=x-state&code=x-code`, {
      headers: { Cookie: `${cookie}; ${stateCookie}` },
    });
    const res = await worker.fetch(req, TEST_ENV);
    assert.equal(res.status, 403);
    assert.equal(rpcCallsNamed(mock.calls, 'lms_oauth_vault_write').length, 0);
  } finally {
    mock.restore();
  }
});

test('GET /connections requires a session (redirects to /login when unauthenticated)', async () => {
  const mock = installFetchMock();
  try {
    const res = await worker.fetch(new Request(`${BASE}/connections`), TEST_ENV);
    assert.equal(res.status, 302);
    assert.match(res.headers.get('Location'), /\/login$/);
  } finally {
    mock.restore();
  }
});

test('GET /connections renders all six tiles with real (mocked) status data', async () => {
  const mock = installFetchMock();
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    if (u.includes('/rest/v1/rpc/lms_connections_status')) {
      return new Response(JSON.stringify({
        social: [
          { platform: 'facebook', healthy: false, detail: "NOT_CONFIGURED -- missing vault secret(s) ['facebook_page_access_token']", checked_at: '2026-09-05T00:00:00Z' },
          { platform: 'instagram', healthy: false, detail: "NOT_CONFIGURED -- missing vault secret(s) ['instagram_access_token']", checked_at: '2026-09-05T00:00:00Z' },
          { platform: 'tiktok', healthy: false, detail: "NOT_CONFIGURED -- missing vault secret(s) ['tiktok_access_token']", checked_at: '2026-09-05T00:00:00Z' },
          { platform: 'x', healthy: false, detail: "NOT_CONFIGURED -- missing vault secret(s) ['x_access_token']", checked_at: '2026-09-05T00:00:00Z' },
          { platform: 'typefully', healthy: false, detail: 'NOT_CONFIGURED -- TYPEFULLY_API_KEY not set', checked_at: '2026-09-05T00:00:00Z' },
          { platform: 'linkedin_company', healthy: false, detail: 'NOT_CONFIGURED', checked_at: '2026-09-05T00:00:00Z' },
        ],
        youtube: { ok: true, checked_at: '2026-09-04T15:37:45Z', error: null },
      }), { status: 200 });
    }
    return realFetch(url, opts);
  };
  try {
    const cookie = await validSessionCookie(TEST_ENV);
    const res = await worker.fetch(new Request(`${BASE}/connections`, { headers: { Cookie: cookie } }), TEST_ENV);
    assert.equal(res.status, 200);
    const html = await res.text();
    for (const label of ['YouTube', 'Instagram Business', 'Facebook Page', 'TikTok', 'X (Twitter)', 'Typefully', 'LinkedIn Company Page']) {
      assert.ok(html.includes(label), `expected tile "${label}" in rendered HTML`);
    }
    assert.match(html, /conn-status-connected/); // YouTube tile
    assert.match(html, /conn-status-not-configured/); // the rest
  } finally {
    mock.restore();
  }
});
