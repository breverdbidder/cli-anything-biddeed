// Supabase REST client — uses native fetch (Node 18+)
import { fetchWithRetry } from './retry.js';

const SUPABASE_URL = process.env.SUPABASE_URL || process.env.BIDDEED_SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || process.env.BIDDEED_SUPABASE_KEY;

function headers() {
  if (!SUPABASE_URL || !SUPABASE_KEY) throw new Error('SUPABASE_URL and SUPABASE_KEY must be set');
  return {
    apikey: SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
    'Content-Type': 'application/json',
    Prefer: 'return=representation',
  };
}

// GET is always safe to retry — read-only.
export async function get(path) {
  const res = await fetchWithRetry(`${SUPABASE_URL}/rest/v1/${path}`, { headers: headers() });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase GET ${path} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

// retryMode: 'full' (default) is fine for inserts protected by a unique
// constraint/upsert or where a duplicate row is low-blast-radius (audit/log
// tables). Callers writing a non-idempotent, balance-mutating row (credit
// grants/spends) must pass { retryMode: 'connect-only' } — or better, do
// their own check-before-write and skip retry entirely.
export async function insert(table, row, opts = {}) {
  const res = await fetchWithRetry(`${SUPABASE_URL}/rest/v1/${table}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(row),
  }, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase INSERT ${table} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

// PATCH-by-filter is naturally idempotent (re-applying the same update is
// safe), so it always uses full retry mode.
export async function patch(table, filter, updates) {
  const res = await fetchWithRetry(`${SUPABASE_URL}/rest/v1/${table}?${filter}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase PATCH ${table} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

// See insert() above re: retryMode — mcp_credit_grant/mcp_credit_spend must
// pass { retryMode: 'connect-only' } since they mutate a balance with no
// dedup key.
export async function rpc(fn, params = {}, opts = {}) {
  const res = await fetchWithRetry(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(params),
  }, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase RPC ${fn} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

// Fetches a raw object from Supabase Storage (e.g. a trained model artifact).
// Returns the response body as text — callers parse (JSON.parse, etc).
export async function storageGet(bucket, path) {
  const res = await fetchWithRetry(`${SUPABASE_URL}/storage/v1/object/${bucket}/${path}`, { headers: headers() });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase storage GET ${bucket}/${path} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.text();
}

// Uploads a Buffer to Supabase Storage, overwriting any existing object at
// the same path (x-upsert) — callers re-generating the same report/export
// must not 409 on a second run. Retry-safe: x-upsert makes a redelivered
// write a no-op-equivalent overwrite of the same content.
export async function storagePut(bucket, path, buffer, contentType = 'application/octet-stream') {
  const res = await fetchWithRetry(`${SUPABASE_URL}/storage/v1/object/${bucket}/${path}`, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      'Content-Type': contentType,
      'x-upsert': 'true',
    },
    body: buffer,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase storage PUT ${bucket}/${path} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

export default { get, insert, patch, rpc, storageGet, storagePut };
