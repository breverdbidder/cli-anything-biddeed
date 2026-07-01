// WorkOS AuthKit OAuth — resource-server token validation.
// biddeed-mcp NEVER issues tokens; it only verifies tokens WorkOS AuthKit issued
// (OAuth 2.1 + PKCE happens entirely client<->WorkOS). Mirrors the verification
// approach used by WorkOS's own workos-node SDK (UserManagement#isValidJwt):
// JWKS fetched from https://api.workos.com/sso/jwks/{client_id}, signature +
// standard exp/nbf checked via `jose`. WorkOS access tokens do not populate the
// `aud` claim by default, so audience is intentionally not asserted here.
import { jwtVerify, createRemoteJWKSet } from 'jose';
import { get, insert, patch } from './supabase.js';
import { AuthError } from './auth.js';

const WORKOS_BASE_URL = 'https://api.workos.com';

let jwksCache = null; // { clientId, jwks }

function requireWorkosEnv() {
  const apiKey = process.env.WORKOS_API_KEY;
  const clientId = process.env.WORKOS_CLIENT_ID;
  if (!apiKey || !clientId) {
    throw new AuthError(
      'WORKOS_API_KEY and WORKOS_CLIENT_ID must both be set to accept OAuth bearer tokens — set them in GitHub Secrets, or use a bd_ API key instead.'
    );
  }
  return { apiKey, clientId };
}

function getJwks(clientId) {
  if (!jwksCache || jwksCache.clientId !== clientId) {
    jwksCache = {
      clientId,
      jwks: createRemoteJWKSet(new URL(`${WORKOS_BASE_URL}/sso/jwks/${clientId}`)),
    };
  }
  return jwksCache.jwks;
}

// Bearer tokens issued by WorkOS AuthKit are JWTs (header.payload.signature).
// bd_* API keys are opaque strings with no dots — this distinguishes the two
// parallel auth paths without needing a prefix on the OAuth side.
export function isJwtLike(token) {
  return typeof token === 'string' && token.split('.').length === 3 && !token.startsWith('bd_');
}

export async function validateOAuthToken(token) {
  if (!token) throw new AuthError('OAuth bearer token required');
  const { clientId } = requireWorkosEnv();
  const jwks = getJwks(clientId);

  let payload;
  try {
    ({ payload } = await jwtVerify(token, jwks));
  } catch (err) {
    if (err?.code === 'ERR_JWT_EXPIRED') {
      throw new AuthError('OAuth token expired — re-authenticate via WorkOS AuthKit');
    }
    throw new AuthError(`Invalid OAuth token: ${err.message}`);
  }

  if (!payload.sub) throw new AuthError('OAuth token missing sub claim');
  return payload;
}

// Upsert on first login: look up by workos_user_id, fall back to email (links
// an OAuth login to a pre-existing bd_*-key customer row), else insert fresh.
// stripe_customer_id is intentionally left NULL here — Sprint 3 links it.
export async function resolveCustomerFromOAuth(claims) {
  const workosUserId = claims.sub;

  const byWorkosId = await get(`mcp_customers?workos_user_id=eq.${encodeURIComponent(workosUserId)}&limit=1`);
  if (byWorkosId.length) return toCustomerRecord(byWorkosId[0]);

  const email = claims.email || (await fetchWorkosUserEmail(workosUserId));

  const byEmail = await get(`mcp_customers?email=eq.${encodeURIComponent(email)}&limit=1`);
  if (byEmail.length) {
    const linked = await patch(
      'mcp_customers',
      `customer_id=eq.${byEmail[0].customer_id}`,
      { workos_user_id: workosUserId }
    );
    return toCustomerRecord(linked[0] || { ...byEmail[0], workos_user_id: workosUserId });
  }

  const created = await insert('mcp_customers', {
    workos_user_id: workosUserId,
    email,
    customer_type: 'human',
    tier_id: 'free',
    stripe_customer_id: null,
  });
  return toCustomerRecord(created[0]);
}

async function fetchWorkosUserEmail(userId) {
  const { apiKey } = requireWorkosEnv();
  const res = await fetch(`${WORKOS_BASE_URL}/user_management/users/${userId}`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new AuthError(`WorkOS user lookup failed for ${userId}: ${res.status}: ${body.slice(0, 200)}`);
  }
  const user = await res.json();
  return user.email;
}

// Shape matches what auth.js#assertTier / billing.js#recordBilling expect from
// the bd_* key path (customer_id, tier, is_active) — see mcp_api_keys rows.
function toCustomerRecord(row) {
  return {
    customer_id: row.customer_id,
    key_prefix: 'oauth',
    tier: row.tier_id,
    is_active: row.active !== false,
    stripe_customer_id: row.stripe_customer_id ?? null,
    call_count: 0,
  };
}
