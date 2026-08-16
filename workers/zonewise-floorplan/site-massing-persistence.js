/**
 * Site massing persistence — Supabase REST + Storage, same fetch-only
 * pattern as persistence.js (no @supabase/supabase-js SDK, Workers-safe).
 *
 * Requires the same SUPABASE_URL / SUPABASE_SERVICE_KEY bindings as the
 * floorplan tool. Depends on migration 20260816_site_massing_runs_options.sql
 * having been applied (verified live 2026-08-16 — see PR description) and
 * on the `site-dxf` Storage bucket existing (created 2026-08-16, private).
 */

const RUNS_TABLE = "site_massing_runs";
const OPTIONS_TABLE = "site_massing_options";
const DXF_BUCKET = "site-dxf";

function restHeaders(env) {
  return {
    apikey: env.SUPABASE_SERVICE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
    "Content-Type": "application/json",
    Prefer: "return=representation",
  };
}

function requireBindings(env) {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) {
    throw new Error("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY bindings.");
  }
}

/** Creates a new run row. Returns the saved row (with its generated id). */
export async function createRun(env, { parcelId, coNo, zoningSnapshot, parcelBoundaryGeoJSON, createdBy }) {
  requireBindings(env);
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/${RUNS_TABLE}`, {
    method: "POST",
    headers: restHeaders(env),
    body: JSON.stringify([
      {
        parcel_id: parcelId,
        co_no: coNo,
        zoning_snapshot: zoningSnapshot,
        // Verified live 2026-08-16 by direct probe insert: PostgREST/PostGIS
        // on this project accepts a raw GeoJSON object for a `geometry`
        // column insert — no ST_GeomFromGeoJSON RPC wrapper needed. Passing
        // the object as-is here (NOT a JSON.stringify'd string — that would
        // send a text value instead of a geometry-typed JSON object).
        parcel_boundary: parcelBoundaryGeoJSON,
        status: "pending",
        created_by: createdBy ?? null,
      },
    ]),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Supabase insert (${RUNS_TABLE}) failed (${res.status}): ${text}`);
  }
  const rows = await res.json();
  return rows[0];
}

export async function updateRunStatus(env, runId, status) {
  requireBindings(env);
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/${RUNS_TABLE}?id=eq.${runId}`, {
    method: "PATCH",
    headers: restHeaders(env),
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Supabase update (${RUNS_TABLE}) failed (${res.status}): ${text}`);
  }
}

/** Bulk-inserts ranked options for a run. Returns the saved rows (with ids). */
export async function saveOptions(env, runId, options) {
  requireBindings(env);
  if (!options.length) return [];
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/${OPTIONS_TABLE}`, {
    method: "POST",
    headers: restHeaders(env),
    body: JSON.stringify(
      options.map((o) => ({
        run_id: runId,
        option_rank: o.option_rank,
        layout_type: o.layout_type,
        footprints: o.footprints,
        unit_count: o.unit_count,
        gross_floor_area_sqft: o.gross_floor_area_sqft,
        lot_coverage_pct: o.lot_coverage_pct,
        setback_compliant: o.setback_compliant,
        score: o.score,
      }))
    ),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Supabase insert (${OPTIONS_TABLE}) failed (${res.status}): ${text}`);
  }
  return res.json();
}

/** Fetches a run and its options, newest run only (by id, direct lookup). */
export async function getRun(env, runId) {
  requireBindings(env);
  const runRes = await fetch(`${env.SUPABASE_URL}/rest/v1/${RUNS_TABLE}?id=eq.${runId}&limit=1`, {
    headers: restHeaders(env),
  });
  if (!runRes.ok) throw new Error(`Supabase read (${RUNS_TABLE}) failed (${runRes.status}): ${await runRes.text()}`);
  const [run] = await runRes.json();
  if (!run) return null;

  const optRes = await fetch(
    `${env.SUPABASE_URL}/rest/v1/${OPTIONS_TABLE}?run_id=eq.${runId}&order=option_rank.asc`,
    { headers: restHeaders(env) }
  );
  if (!optRes.ok) throw new Error(`Supabase read (${OPTIONS_TABLE}) failed (${optRes.status}): ${await optRes.text()}`);
  const options = await optRes.json();

  return { ...run, options };
}

export async function getOption(env, runId, optionId) {
  requireBindings(env);
  const res = await fetch(
    `${env.SUPABASE_URL}/rest/v1/${OPTIONS_TABLE}?id=eq.${optionId}&run_id=eq.${runId}&limit=1`,
    { headers: restHeaders(env) }
  );
  if (!res.ok) throw new Error(`Supabase read (${OPTIONS_TABLE}) failed (${res.status}): ${await res.text()}`);
  const [row] = await res.json();
  return row ?? null;
}

/**
 * Uploads a generated DXF to Storage at site-dxf/<run_id>/<option_id>.dxf
 * and writes the path back onto the option row. Returns the storage path.
 */
export async function saveDxf(env, runId, optionId, dxfString) {
  requireBindings(env);
  const objectPath = `${runId}/${optionId}.dxf`;

  const uploadRes = await fetch(`${env.SUPABASE_URL}/storage/v1/object/${DXF_BUCKET}/${objectPath}`, {
    method: "POST",
    headers: {
      apikey: env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
      "Content-Type": "application/dxf",
      "x-upsert": "true",
    },
    body: dxfString,
  });
  if (!uploadRes.ok) {
    const text = await uploadRes.text();
    throw new Error(`Storage upload (${DXF_BUCKET}/${objectPath}) failed (${uploadRes.status}): ${text}`);
  }

  const patchRes = await fetch(`${env.SUPABASE_URL}/rest/v1/${OPTIONS_TABLE}?id=eq.${optionId}`, {
    method: "PATCH",
    headers: restHeaders(env),
    body: JSON.stringify({ dxf_path: `${DXF_BUCKET}/${objectPath}` }),
  });
  if (!patchRes.ok) {
    const text = await patchRes.text();
    throw new Error(`Supabase update (${OPTIONS_TABLE}.dxf_path) failed (${patchRes.status}): ${text}`);
  }

  return `${DXF_BUCKET}/${objectPath}`;
}

/** Signed URL (60 min) for a stored DXF, so the caller never needs the service key. */
export async function signDxfUrl(env, objectPath) {
  requireBindings(env);
  const relPath = objectPath.startsWith(`${DXF_BUCKET}/`) ? objectPath.slice(DXF_BUCKET.length + 1) : objectPath;
  const res = await fetch(`${env.SUPABASE_URL}/storage/v1/object/sign/${DXF_BUCKET}/${relPath}`, {
    method: "POST",
    headers: restHeaders(env),
    body: JSON.stringify({ expiresIn: 3600 }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Storage sign (${DXF_BUCKET}/${relPath}) failed (${res.status}): ${text}`);
  }
  const { signedURL } = await res.json();
  return `${env.SUPABASE_URL}/storage/v1${signedURL}`;
}
