// biddeed-mcp-production — Cloudflare Worker entry (#20025, EXIT VERCEL A)
// Serves mcp.biddeed.ai byte-equivalent to the retired Vercel function.
// Option 1 (preferred, per issue plan): reuse the existing Node http.Server
// from packages/biddeed-mcp/src/http.js unchanged, bound into the Worker
// fetch event via cloudflare:node's httpServerHandler. Zero duplicated
// routing logic between Vercel-era code and the Worker.
import { httpServerHandler } from 'cloudflare:node';
import { startHttp } from '../packages/biddeed-mcp/src/http.js';

const PORT = 8080;

await startHttp(PORT);

const nodeHandler = httpServerHandler({ port: PORT });

// LAUNCH-A (#20035) — in-Worker rate limiting + security headers. Wraps the
// unmodified Node http.Server handler above; never touches auth/billing/cert
// logic in packages/biddeed-mcp/src/**.
//
// Cloudflare's dedicated Rate Limiting binding (`ratelimits` config) deploys
// cleanly on this Free-plan account, but env.RATE_LIMITER.limit() always
// returned success:true against live traffic — verified with a temporary
// debug header across 85+ requests (up to 50 concurrent), tried under both
// the legacy `unsafe.bindings type="ratelimit"` and the GA `ratelimits` top-
// level config. Matches an open, unresolved Cloudflare community report of
// the same symptom. A Workers Paid plan change is Ariel's call and out of
// scope here, so this uses a per-isolate fixed-window counter instead. It is
// weaker than the binding (resets on cold start, not shared across colos)
// but it is the only mechanism that actually enforces on this account today.
const RATE_WINDOWS = new Map(); // "ip"|"key" -> { count, windowStart }
const WINDOW_MS = 60_000;
const LIMIT_IP = 20;
const LIMIT_KEY = 120;

function checkRateLimitLocal(bucket, key, limit) {
  const now = Date.now();
  const mapKey = `${bucket}:${key}`;
  const entry = RATE_WINDOWS.get(mapKey);
  if (!entry || now - entry.windowStart >= WINDOW_MS) {
    RATE_WINDOWS.set(mapKey, { count: 1, windowStart: now });
    if (RATE_WINDOWS.size > 10000) {
      for (const [k, v] of RATE_WINDOWS) {
        if (now - v.windowStart >= WINDOW_MS) RATE_WINDOWS.delete(k);
      }
    }
    return true;
  }
  if (entry.count >= limit) return false;
  entry.count += 1;
  return true;
}

const SECURITY_HEADERS = {
  'Strict-Transport-Security': 'max-age=63072000; includeSubDomains',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
};

function withSecurityHeaders(response) {
  const headers = new Headers(response.headers);
  for (const [key, value] of Object.entries(SECURITY_HEADERS)) headers.set(key, value);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

async function sha256Hex(input) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function rateLimitedJsonRpcError(request) {
  let id = null;
  try {
    if (request.method === 'POST') {
      const body = await request.clone().json();
      id = body?.id ?? null;
    }
  } catch {
    // no/invalid JSON body — id stays null
  }
  return new Response(
    JSON.stringify({ jsonrpc: '2.0', id, error: { code: -32000, message: 'Rate limit exceeded' } }),
    { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '60', ...SECURITY_HEADERS } }
  );
}

export default {
  async fetch(request, env, ctx) {
    try {
      const bearer = request.headers.get('Authorization')?.match(/^Bearer\s+(.+)$/i)?.[1];
      const allowed = bearer
        ? checkRateLimitLocal('key', await sha256Hex(bearer), LIMIT_KEY)
        : checkRateLimitLocal('ip', request.headers.get('CF-Connecting-IP') || 'unknown', LIMIT_IP);
      if (!allowed) return rateLimitedJsonRpcError(request);
    } catch {
      // Never block MCP traffic on a limiter error.
    }

    const response = await nodeHandler.fetch(request, env, ctx);
    return withSecurityHeaders(response);
  },
};
