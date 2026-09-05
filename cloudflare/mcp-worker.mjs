// biddeed-mcp-production — Cloudflare Worker entry (#20025, EXIT VERCEL A)
// Serves mcp.biddeed.ai byte-equivalent to the retired Vercel function.
// Option 1 (preferred, per issue plan): reuse the existing Node http.Server
// from packages/biddeed-mcp/src/http.js unchanged, bound into the Worker
// fetch event via cloudflare:node's httpServerHandler. Zero duplicated
// routing logic between Vercel-era code and the Worker.
import { httpServerHandler } from 'cloudflare:node';
import { startHttp } from '../packages/biddeed-mcp/src/http.js';
import { RateLimiterCounter, checkRateLimitDO } from './rate-limit-do.mjs';

// Re-exported so wrangler can bind the `RATE_LIMIT_DO` Durable Object
// (class_name: "RateLimiterCounter" in wrangler.mcp.jsonc) to this Worker's
// own script.
export { RateLimiterCounter };

const PORT = 8080;

await startHttp(PORT);

const nodeHandler = httpServerHandler({ port: PORT });

// LAUNCH-A2 (#20041) — in-Worker rate limiting + security headers. Wraps the
// unmodified Node http.Server handler above; never touches auth/billing/cert
// logic in packages/biddeed-mcp/src/**.
//
// Cloudflare's dedicated Rate Limiting binding (`ratelimits` config) deploys
// cleanly on this Free-plan account, but env.RATE_LIMITER.limit() always
// returned success:true against live traffic — verified with a temporary
// debug header across 85+ requests (up to 50 concurrent), tried under both
// the legacy `unsafe.bindings type="ratelimit"` and the GA `ratelimits`
// top-level config. Matches an open, unresolved Cloudflare community report
// of the same symptom. The #20035 fallback (`caches.default` as a counter)
// was also proven non-functional live on 2026-09-05 (25 unauth POSTs to
// mcp.biddeed.ai/api/mcp -> 25x401, zero 429) — Cache API writes are
// per-colo and non-atomic. This uses the RATE_LIMIT_DO Durable Object
// instead — one strongly-consistent counter instance per (bucket, identity)
// regardless of colo. SQLite-backed DOs are available on the Workers Free
// plan. See cloudflare/rate-limit-do.mjs.
const WINDOW_MS = 60_000;
const LIMIT_IP = 20;
const LIMIT_KEY = 120;

// Never rate-limit health checks, OAuth discovery, or the Stripe webhook.
const RATE_LIMIT_EXEMPT_PATHS = new Set([
  '/health',
  '/',
  '/.well-known/oauth-protected-resource',
  '/api/stripe/webhook',
]);

function isRateLimitExempt(request) {
  const path = new URL(request.url).pathname;
  return RATE_LIMIT_EXEMPT_PATHS.has(path) || path.startsWith('/.well-known/');
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
      if (!isRateLimitExempt(request)) {
        const bearer = request.headers.get('Authorization')?.match(/^Bearer\s+(.+)$/i)?.[1];
        const allowed = bearer
          ? await checkRateLimitDO(env, 'RATE_LIMIT_DO', 'key', await sha256Hex(bearer), LIMIT_KEY, WINDOW_MS)
          : await checkRateLimitDO(env, 'RATE_LIMIT_DO', 'ip', request.headers.get('CF-Connecting-IP') || 'unknown', LIMIT_IP, WINDOW_MS);
        if (!allowed) return rateLimitedJsonRpcError(request);
      }
    } catch {
      // Never block MCP traffic on a limiter error.
    }

    const response = await nodeHandler.fetch(request, env, ctx);
    return withSecurityHeaders(response);
  },
};
