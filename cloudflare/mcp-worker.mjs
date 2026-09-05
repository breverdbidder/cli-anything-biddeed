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
// logic in packages/biddeed-mcp/src/**. Fails open on limiter errors so a
// Workers Rate Limiting outage never blocks legitimate MCP traffic.
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
    let debug = 'ok';
    try {
      const bearer = request.headers.get('Authorization')?.match(/^Bearer\s+(.+)$/i)?.[1];
      const limiter = bearer ? env.RATE_LIMITER_KEY : env.RATE_LIMITER_IP;
      const key = bearer ? await sha256Hex(bearer) : request.headers.get('CF-Connecting-IP') || 'unknown';
      if (limiter) {
        const { success } = await limiter.limit({ key });
        debug = `checked:${success}`;
        if (!success) {
          const blocked = await rateLimitedJsonRpcError(request);
          blocked.headers.set('X-RateLimit-Debug', debug);
          return blocked;
        }
      } else {
        debug = 'no-limiter-binding';
      }
    } catch (err) {
      debug = `error:${err && err.message}`;
    }

    const response = await nodeHandler.fetch(request, env, ctx);
    const wrapped = withSecurityHeaders(response);
    wrapped.headers.set('X-RateLimit-Debug', debug);
    return wrapped;
  },
};
