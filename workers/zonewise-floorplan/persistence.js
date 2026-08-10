/**
 * ZoneWise floor plan persistence — Supabase REST client.
 * ---------------------------------------------------------------------------
 * Uses the Supabase REST API directly (fetch, no @supabase/supabase-js SDK)
 * so this stays dependency-free and Workers-safe — same reasoning as
 * keeping the compiler path zero-dependency. The SDK works fine in Workers
 * too; this is a deliberate minimalism choice, not a compatibility one.
 *
 * Requires two bindings on the Worker (set via `wrangler secret put` — do
 * NOT hardcode these, see the [[stated]] note in memory about hardcoded
 * secrets in Supabase vault on other ZoneWise services):
 *   SUPABASE_URL            e.g. https://mocerqjnksmhcjzxrewo.supabase.co
 *   SUPABASE_SERVICE_KEY     service_role key (server-side only — never
 *                            ship this to the frontend)
 *
 * Depends on migration_floor_plans.sql having been applied. Not applied
 * automatically by this module — that's a confirm-first action.
 */

const TABLE = "floor_plans";

function headers(env) {
  return {
    apikey: env.SUPABASE_SERVICE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
    "Content-Type": "application/json",
    Prefer: "return=representation",
  };
}

/**
 * Save a new version of a plan. Marks it `is_current`, and un-marks the
 * previous current version for the same (parcel_id, plan_name) — two
 * requests, not a transaction (Supabase's REST API doesn't expose
 * multi-statement transactions directly). A crash between them leaves two
 * `is_current` rows rather than corrupting data; `getCurrentPlan` below
 * defensively orders by version desc + limit 1 to tolerate that.
 */
export async function savePlanVersion(env, { parcelId, planName = "default", source, svg, summary, zoningResult, compilerWarnings, createdBy }) {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) {
    throw new Error("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY bindings.");
  }

  const current = await getCurrentPlan(env, parcelId, planName);
  const nextVersion = current ? current.version + 1 : 1;

  if (current) {
    await fetch(`${env.SUPABASE_URL}/rest/v1/${TABLE}?id=eq.${current.id}`, {
      method: "PATCH",
      headers: headers(env),
      body: JSON.stringify({ is_current: false }),
    });
  }

  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/${TABLE}`, {
    method: "POST",
    headers: headers(env),
    body: JSON.stringify([
      {
        parcel_id: parcelId,
        plan_name: planName,
        version: nextVersion,
        is_current: true,
        source,
        svg: svg ?? null,
        summary: summary ?? null,
        zoning_result: zoningResult ?? null,
        compiler_warnings: compilerWarnings ?? null,
        created_by: createdBy ?? null,
      },
    ]),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Supabase insert failed (${res.status}): ${text}`);
  }
  const rows = await res.json();
  return rows[0];
}

/** Latest version of a plan, or null if none exists. */
export async function getCurrentPlan(env, parcelId, planName = "default") {
  const url = `${env.SUPABASE_URL}/rest/v1/${TABLE}?parcel_id=eq.${encodeURIComponent(parcelId)}&plan_name=eq.${encodeURIComponent(planName)}&order=version.desc&limit=1`;
  const res = await fetch(url, { headers: headers(env) });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Supabase read failed (${res.status}): ${text}`);
  }
  const rows = await res.json();
  return rows[0] ?? null;
}

/** Full version history for a plan, newest first. */
export async function getPlanHistory(env, parcelId, planName = "default") {
  const url = `${env.SUPABASE_URL}/rest/v1/${TABLE}?parcel_id=eq.${encodeURIComponent(parcelId)}&plan_name=eq.${encodeURIComponent(planName)}&order=version.desc`;
  const res = await fetch(url, { headers: headers(env) });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Supabase read failed (${res.status}): ${text}`);
  }
  return res.json();
}

/** All current (latest) plans for a parcel — a parcel may have more than one named plan. */
export async function getParcelPlans(env, parcelId) {
  const url = `${env.SUPABASE_URL}/rest/v1/${TABLE}?parcel_id=eq.${encodeURIComponent(parcelId)}&is_current=eq.true`;
  const res = await fetch(url, { headers: headers(env) });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Supabase read failed (${res.status}): ${text}`);
  }
  return res.json();
}
