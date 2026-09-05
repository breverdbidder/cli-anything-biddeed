// Shared SQLite-backed Durable Object rate-limit counter (#20041, LAUNCH-A2).
//
// Replaces the `caches.default` "counter" from #20035, which is not a real
// counter: Cache API writes are per-colo and non-atomic, so a burst spread
// across colos (or even racing within one colo) is undercounted — confirmed
// live on 2026-09-05 (25 unauth POSTs to mcp.biddeed.ai/api/mcp -> 25x401,
// zero 429). Cloudflare's dedicated Rate Limiting binding was tried first
// per the intent's hard-constraint order and also confirmed non-functional
// on this account (env.RATE_LIMITER.limit() always returns success:true —
// see cloudflare/wrangler.mcp.jsonc and wrangler.toml history, #20035).
//
// A Durable Object gives one strongly-consistent, single-threaded instance
// per (bucket, identity) key regardless of which colo the request lands in
// — the actual correctness property a rate limiter needs. SQLite-backed DOs
// are available on the Workers Free plan (no Durable Objects Paid/Workers
// Paid plan required), unlike the classic KV-backed DO storage class.
//
// Bound identically into both biddeed-mcp-production (cloudflare/mcp-worker.mjs)
// and worker-damp-snowflake-cead (src/worker.js) — each Worker gets its own
// isolated DO namespace, so bucket names only need to be unique within one
// Worker's binding, not globally.
export class RateLimiterCounter {
  constructor(state) {
    this.sql = state.storage.sql;
    this.sql.exec('CREATE TABLE IF NOT EXISTS counters (window_start INTEGER NOT NULL, count INTEGER NOT NULL)');
  }

  async fetch(request) {
    const { limit, windowMs } = await request.json();
    const now = Date.now();
    const rows = [...this.sql.exec('SELECT window_start, count FROM counters LIMIT 1')];
    const row = rows[0];
    let windowStart;
    let count;
    if (!row || now - row.window_start >= windowMs) {
      windowStart = now;
      count = 1;
      this.sql.exec('DELETE FROM counters');
      this.sql.exec('INSERT INTO counters (window_start, count) VALUES (?, ?)', windowStart, count);
    } else {
      windowStart = row.window_start;
      count = row.count + 1;
      this.sql.exec('UPDATE counters SET count = ?', count);
    }
    return Response.json({ allowed: count <= limit, count, windowStart });
  }
}

// Fails OPEN (allowed=true) on any DO error, matching the fail-open behavior
// the caches.default counter had — a limiter outage must never take down
// MCP/chat/checkout traffic.
export async function checkRateLimitDO(env, bindingName, bucket, key, limit, windowMs) {
  try {
    const binding = env[bindingName];
    const id = binding.idFromName(`${bucket}:${key}`);
    const stub = binding.get(id);
    const res = await stub.fetch('https://rate-limit-do.internal/check', {
      method: 'POST',
      body: JSON.stringify({ limit, windowMs }),
    });
    const data = await res.json();
    return !!data.allowed;
  } catch {
    return true;
  }
}
