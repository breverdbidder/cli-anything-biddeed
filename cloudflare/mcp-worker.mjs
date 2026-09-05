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
// the legacy `unsafe.bindings type="ratelimit"` and the GA `ratelimits`
// top-level config. Matches an open, unresolved Cloudflare community report
// of the same symptom. A per-isolate in-memory counter was tried next and
// also failed live (25 sequential requests, zero throttling) — Cloudflare
// does not give a single client session affinity to one isolate, so state
// never accumulated. A Workers Paid plan change (for Durable Objects) is
// Ariel's call and out of scope here, so this uses `caches.default` (the
// Cache API, colo-shared and already proven live in this same issue via the
// /auctions cf-cache-status: HIT test) as a best-effort shared counter.
// Read-then-write is not atomic, so concurrent requests can under-count —
// acceptable for abuse mitigation, not a hard guarantee.
const WINDOW_MS = 60_000;
const LIMIT_IP = 20;
const LIMIT_KEY = 120;

async function checkRateLimitCache(bucket, key, limit) {
  const cache = caches.default;
  const cacheKey = new Request(`https://rl.internal.biddeed.ai/${bucket}/${encodeURIComponent(key)}`);
  const now = Date.now();
  let count = 1;
  let windowStart = now;
  try {
    const cached = await cache.match(cacheKey);
    if (cached) {
      const data = await cached.json();
      if (data && typeof data.windowStart === 'number' && now - data.windowStart < WINDOW_MS) {
        windowStart = data.windowStart;
        count = (data.count || 0) + 1;
      }
    }
  } catch {
    // treat as a fresh window on any read error
  }
  const allowed = count <= limit;
  try {
    const ttlSeconds = Math.max(1, Math.ceil((windowStart + WINDOW_MS - now) / 1000));
    await cache.put(cacheKey, new Response(JSON.stringify({ count, windowStart }), {
      headers: { 'Content-Type': 'application/json', 'Cache-Control': `max-age=${ttlSeconds}` },
    }));
  } catch {
    // best-effort — a failed write just means the next request re-reads stale/missing state
  }
  return allowed;
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
        ? await checkRateLimitCache('key', await sha256Hex(bearer), LIMIT_KEY)
        : await checkRateLimitCache('ip', request.headers.get('CF-Connecting-IP') || 'unknown', LIMIT_IP);
      if (!allowed) return rateLimitedJsonRpcError(request);
    } catch {
      // Never block MCP traffic on a limiter error.
    }

    const response = await nodeHandler.fetch(request, env, ctx);
    return withSecurityHeaders(response);
  },
};
