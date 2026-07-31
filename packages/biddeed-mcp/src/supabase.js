// Supabase REST client — uses native fetch (Node 18+)
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

export async function get(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { headers: headers() });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase GET ${path} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

export async function insert(table, row) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(row),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase INSERT ${table} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

export async function patch(table, filter, updates) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?${filter}`, {
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

export async function rpc(fn, params = {}) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase RPC ${fn} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

// Fetches a raw object from Supabase Storage (e.g. a trained model artifact).
// Returns the response body as text — callers parse (JSON.parse, etc).
export async function storageGet(bucket, path) {
  const res = await fetch(`${SUPABASE_URL}/storage/v1/object/${bucket}/${path}`, { headers: headers() });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Supabase storage GET ${bucket}/${path} → ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.text();
}

// Uploads a Buffer to Supabase Storage, overwriting any existing object at
// the same path (x-upsert) — callers re-generating the same report/export
// must not 409 on a second run.
export async function storagePut(bucket, path, buffer, contentType = 'application/octet-stream') {
  const res = await fetch(`${SUPABASE_URL}/storage/v1/object/${bucket}/${path}`, {
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
