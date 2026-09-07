// Shared retry/backoff wrapper for Supabase calls (issue #20090) — Supabase's
// whole compute stack (Postgres+PgBouncer+PostgREST+GoTrue) bounces together
// every ~10-15min as of Sep 2026, for ~10-30s per bounce. This absorbs that
// window so it never surfaces as a 5xx to a real user, without ever retrying
// an application-level (4xx) error.
//
// Two modes:
//   'full'        — safe for reads and naturally-idempotent writes (PATCH-by-
//                    filter, upsert/on-conflict inserts). Retries on anything
//                    that indicates the request didn't durably complete.
//   'connect-only' — for non-idempotent writes (balance-mutating RPCs like
//                    mcp_credit_grant/mcp_credit_spend) where retrying a
//                    write whose response was merely lost could double-apply
//                    it. Only retries when we're sure nothing reached the
//                    server: the TCP connection itself never opened, or
//                    PostgREST/Postgres rejected the request before running
//                    it (503, or Postgres 57P03 "cannot connect now").
const DEFAULT_ATTEMPTS = 3;
const DEFAULT_BACKOFF_MS = [150, 450, 1200];
const DEFAULT_TIMEOUT_MS = 5000;

const PRE_EXECUTION_NETWORK_CODES = new Set(['ECONNREFUSED', 'ENOTFOUND', 'EAI_AGAIN']);
const MID_STREAM_NETWORK_CODES = new Set(['ECONNRESET', 'EPIPE', 'ETIMEDOUT']);
const PRE_EXECUTION_PG_CODES = new Set(['57P03']); // "the database system is not yet accepting connections"
const AMBIGUOUS_PG_CODES = new Set(['57P01', '57P02', '08000', '08003', '08006']);

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function networkErrorCode(err) {
  return err?.cause?.code || err?.code || null;
}

function isRetryableError(err, mode) {
  if (PRE_EXECUTION_NETWORK_CODES.has(networkErrorCode(err))) return true;
  if (mode !== 'full') return false;
  if (err?.name === 'AbortError') return true; // our own client-side timeout fired
  if (MID_STREAM_NETWORK_CODES.has(networkErrorCode(err))) return true;
  if (err instanceof TypeError && /fetch failed|network/i.test(err.message || '')) return true;
  return false;
}

async function isRetryableResponse(res, mode) {
  if (res.status === 503) return true; // PostgREST couldn't get a DB connection — query never ran
  if (res.status < 500) return false; // never retry 4xx application errors
  try {
    const body = await res.clone().json();
    const code = body?.code;
    if (PRE_EXECUTION_PG_CODES.has(code)) return true;
    if (mode === 'full' && AMBIGUOUS_PG_CODES.has(code)) return true;
  } catch (_) {
    // not JSON, or body already consumed — nothing more to learn from it
  }
  return false;
}

// Wraps a single fetch() call with timeout + retry. Returns the Response
// object exactly as fetch() would — callers keep their existing res.ok /
// res.json() handling unchanged.
export async function fetchWithRetry(url, init = {}, opts = {}) {
  const attempts = opts.attempts ?? DEFAULT_ATTEMPTS;
  const backoffMs = opts.backoffMs ?? DEFAULT_BACKOFF_MS;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const mode = opts.retryMode ?? 'full';

  let lastErr;
  for (let attempt = 0; attempt < attempts; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      clearTimeout(timer);
      if (res.ok || attempt === attempts - 1 || !(await isRetryableResponse(res, mode))) {
        return res;
      }
      await sleep(backoffMs[attempt] ?? backoffMs[backoffMs.length - 1]);
    } catch (err) {
      clearTimeout(timer);
      lastErr = err;
      if (attempt === attempts - 1 || !isRetryableError(err, mode)) throw err;
      await sleep(backoffMs[attempt] ?? backoffMs[backoffMs.length - 1]);
    }
  }
  throw lastErr;
}
