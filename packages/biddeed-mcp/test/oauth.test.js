import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPair, SignJWT, exportJWK } from 'jose';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { validateOAuthToken, resolveCustomerFromOAuth, isJwtLike } = await import('../src/oauth.js');

async function setupKeys() {
  const { publicKey, privateKey } = await generateKeyPair('RS256');
  const jwk = await exportJWK(publicKey);
  jwk.kid = 'test-kid';
  jwk.alg = 'RS256';
  jwk.use = 'sig';
  return { privateKey, jwks: { keys: [jwk] } };
}

function mockFetch(routes) {
  const original = global.fetch;
  global.fetch = async (url, opts) => {
    const urlStr = url.toString();
    const route = routes.find(([matcher]) => matcher.test(urlStr));
    if (!route) throw new Error(`Unmocked fetch: ${urlStr}`);
    return route[1](urlStr, opts);
  };
  return () => { global.fetch = original; };
}

test('isJwtLike distinguishes bd_ keys from OAuth JWTs', () => {
  assert.equal(isJwtLike('bd_live_abc123'), false);
  assert.equal(isJwtLike('bd_live_rcMeTf.notarealsegment'), false); // still bd_-prefixed
  assert.equal(isJwtLike('eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyXzEifQ.sig'), true);
  assert.equal(isJwtLike('not-a-jwt'), false);
});

test('validateOAuthToken accepts a valid WorkOS-signed JWT', async (t) => {
  process.env.WORKOS_API_KEY = 'sk_test_workos';
  process.env.WORKOS_CLIENT_ID = 'client_test_valid';

  const { privateKey, jwks } = await setupKeys();
  t.after(mockFetch([
    [/\/sso\/jwks\//, async () => new Response(JSON.stringify(jwks), { status: 200 })],
  ]));

  const token = await new SignJWT({ email: 'investor@example.com' })
    .setProtectedHeader({ alg: 'RS256', kid: 'test-kid' })
    .setSubject('user_01ABCXYZ')
    .setIssuedAt()
    .setExpirationTime('10m')
    .sign(privateKey);

  const claims = await validateOAuthToken(token);
  assert.equal(claims.sub, 'user_01ABCXYZ');
  assert.equal(claims.email, 'investor@example.com');
});

test('validateOAuthToken rejects an expired JWT', async (t) => {
  process.env.WORKOS_API_KEY = 'sk_test_workos';
  process.env.WORKOS_CLIENT_ID = 'client_test_expired';

  const { privateKey, jwks } = await setupKeys();
  t.after(mockFetch([
    [/\/sso\/jwks\//, async () => new Response(JSON.stringify(jwks), { status: 200 })],
  ]));

  const now = Math.floor(Date.now() / 1000);
  const token = await new SignJWT({})
    .setProtectedHeader({ alg: 'RS256', kid: 'test-kid' })
    .setSubject('user_expired')
    .setIssuedAt(now - 7200)
    .setExpirationTime(now - 3600)
    .sign(privateKey);

  await assert.rejects(() => validateOAuthToken(token), /expired/i);
});

test('validateOAuthToken fails loudly when WORKOS env vars are missing', async () => {
  const savedKey = process.env.WORKOS_API_KEY;
  const savedClient = process.env.WORKOS_CLIENT_ID;
  delete process.env.WORKOS_API_KEY;
  delete process.env.WORKOS_CLIENT_ID;
  try {
    await assert.rejects(
      () => validateOAuthToken('a.b.c'),
      /WORKOS_API_KEY and WORKOS_CLIENT_ID/
    );
  } finally {
    if (savedKey !== undefined) process.env.WORKOS_API_KEY = savedKey;
    if (savedClient !== undefined) process.env.WORKOS_CLIENT_ID = savedClient;
  }
});

test('resolveCustomerFromOAuth inserts a new mcp_customers row on first login (tier=free, stripe_customer_id=NULL)', async (t) => {
  let insertedBody = null;
  t.after(mockFetch([
    [/mcp_customers\?workos_user_id=eq\./, async () => new Response('[]', { status: 200 })],
    [/mcp_customers\?email=eq\./, async () => new Response('[]', { status: 200 })],
    [/\/rest\/v1\/mcp_customers$/, async (_url, opts) => {
      insertedBody = JSON.parse(opts.body);
      return new Response(JSON.stringify([{ ...insertedBody, customer_id: 'new-uuid' }]), { status: 201 });
    }],
  ]));

  const record = await resolveCustomerFromOAuth({ sub: 'user_new', email: 'new@example.com' });

  assert.equal(insertedBody.workos_user_id, 'user_new');
  assert.equal(insertedBody.email, 'new@example.com');
  assert.equal(insertedBody.stripe_customer_id, null);
  assert.equal(insertedBody.tier_id, 'free');
  assert.equal(record.customer_id, 'new-uuid');
  assert.equal(record.tier, 'free');
});

test('resolveCustomerFromOAuth links an existing bd_-key customer by email instead of violating the UNIQUE(email) constraint', async (t) => {
  let patchedFilter = null;
  t.after(mockFetch([
    [/mcp_customers\?workos_user_id=eq\./, async () => new Response('[]', { status: 200 })],
    [/mcp_customers\?email=eq\./, async () => new Response(JSON.stringify([{
      customer_id: 'existing-uuid', email: 'ariel@everestcapitalusa.com', tier_id: 'pro',
      stripe_customer_id: null, active: true,
    }]), { status: 200 })],
    [/\/rest\/v1\/mcp_customers\?customer_id=eq\./, async (url, opts) => {
      patchedFilter = url;
      return new Response(JSON.stringify([{
        customer_id: 'existing-uuid', email: 'ariel@everestcapitalusa.com', tier_id: 'pro',
        stripe_customer_id: null, active: true, workos_user_id: JSON.parse(opts.body).workos_user_id,
      }]), { status: 200 });
    }],
  ]));

  const record = await resolveCustomerFromOAuth({ sub: 'user_ariel', email: 'ariel@everestcapitalusa.com' });

  assert.match(patchedFilter, /customer_id=eq\.existing-uuid/);
  assert.equal(record.customer_id, 'existing-uuid');
  assert.equal(record.tier, 'pro');
});
