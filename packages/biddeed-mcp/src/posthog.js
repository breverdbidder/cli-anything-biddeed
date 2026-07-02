// PostHog server-side event capture — fire-and-forget, batched.
//
// mcp_tool_call events double as an independent audit stream against
// billing_events (see billing.js) — same tool call, two ledgers. Reconcile
// with:
//   SELECT b.tool_name, count(*) AS billed, count(p.uuid) AS posthog_seen
//   FROM billing_events b
//   LEFT JOIN posthog_events_backfill p  -- PostHog data warehouse export/sync
//     ON p.event = 'mcp_tool_call'
//    AND p.properties->>'tool_name' = b.tool_name
//    AND p.timestamp BETWEEN b.created_at - interval '1 minute' AND b.created_at + interval '1 minute'
//   WHERE b.created_at > now() - interval '1 day'
//   GROUP BY b.tool_name;
// A gap (billed > posthog_seen) means the queue dropped events (overflow) or
// the vault key was missing for that window — both are visible, not silent.
import { createHash } from 'crypto';
import { rpc } from './supabase.js';

const POSTHOG_HOST = 'https://us.i.posthog.com';
const VAULT_SECRET_NAME = 'posthog_project_key';
const MAX_QUEUE = 500;
const FLUSH_BATCH_SIZE = 50;
const FLUSH_INTERVAL_MS = 5000;
const KEY_RECHECK_MS = 10 * 60 * 1000; // re-probe vault periodically so a key added later activates without a restart

let queue = [];
let flushTimer = null;
let projectKey; // undefined = unresolved, null = confirmed missing, string = live phc_ token
let keyCheckedAt = 0;
let dropped = 0;

export function hashDistinctId(credential) {
  return createHash('sha256').update(credential || '').digest('hex');
}

async function resolveProjectKey() {
  const stale = Date.now() - keyCheckedAt > KEY_RECHECK_MS;
  if (projectKey !== undefined && projectKey !== null && !stale) return projectKey;
  if (projectKey === null && !stale) return null;
  try {
    const key = await rpc('get_vault_secret_mcp', { p_name: VAULT_SECRET_NAME });
    projectKey = typeof key === 'string' && key.startsWith('phc_') ? key : null;
  } catch {
    projectKey = null;
  }
  keyCheckedAt = Date.now();
  return projectKey;
}

export function captureToolCall({ credential, toolName, tier, latencyMs, county, cacheHit, errorClass }) {
  if (queue.length >= MAX_QUEUE) {
    dropped++;
    return;
  }
  queue.push({
    event: 'mcp_tool_call',
    distinct_id: hashDistinctId(credential),
    properties: {
      tool_name: toolName,
      tier: tier || null,
      latency_ms: latencyMs,
      county: county || null,
      cache_hit: cacheHit ?? null,
      error_class: errorClass || null,
    },
    timestamp: new Date().toISOString(),
  });
  scheduleFlush();
}

function scheduleFlush() {
  if (queue.length >= FLUSH_BATCH_SIZE) {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
    flush().catch(() => {});
    return;
  }
  if (flushTimer) return;
  flushTimer = setTimeout(() => { flushTimer = null; flush().catch(() => {}); }, FLUSH_INTERVAL_MS);
  if (typeof flushTimer.unref === 'function') flushTimer.unref();
}

async function flush() {
  if (!queue.length) return;
  const key = await resolveProjectKey();
  if (!key) {
    queue = []; // blocked_on_key — never crash, never buffer forever
    return;
  }
  const batch = queue.splice(0, queue.length);
  try {
    await fetch(`${POSTHOG_HOST}/batch/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key, batch }),
    });
  } catch (err) {
    process.stderr.write(`[posthog] flush failed: ${err.message}\n`);
  }
}

// Ops hook — call on graceful shutdown (SIGTERM) to drain the queue instead
// of losing up to FLUSH_INTERVAL_MS of buffered events. Also used by tests.
export function flushNow() {
  if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
  return flush();
}

// Test/ops hooks — not part of the public capture contract
export function _debugState() {
  return { queueDepth: queue.length, dropped, projectKeyResolved: projectKey !== undefined };
}

export function _resetForTest() {
  queue = [];
  if (flushTimer) clearTimeout(flushTimer);
  flushTimer = null;
  projectKey = undefined;
  keyCheckedAt = 0;
  dropped = 0;
}
