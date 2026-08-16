/**
 * Supabase reads that assemble solver inputs for /site-massing/generate:
 * the parcel itself (zw_parcels) and its zone's dimensional standards
 * (zoning_districts + zone_standards). Same fetch-only REST pattern as
 * persistence.js — no SDK, Workers-safe.
 *
 * JURISDICTION RESOLUTION — HONEST LIMITATION (v1):
 *   zw_parcels has no reliable per-parcel jurisdiction foreign key
 *   (`zoning_jurisdiction` is unpopulated on every row checked live
 *   2026-08-16). The SAME zoning code (e.g. "RU-1-11") is reused, with
 *   different standards, across multiple Brevard municipalities that copied
 *   the county's original code names into their own Municode ordinances —
 *   confirmed live: RU-1-11 alone resolves to 10 different
 *   zoning_districts rows across 10 different Brevard jurisdictions.
 *   This module resolves jurisdiction with a best-effort fallback chain and
 *   labels which branch was used in `resolution_method` — it never silently
 *   presents a guessed jurisdiction as authoritative:
 *     1. site_city match against jurisdictions.name (same county)
 *     2. fallback to "Unincorporated <County>"
 *   A caller needing a hard jurisdiction guarantee should treat
 *   resolution_method !== "site_city_match" as lower-confidence and cross-
 *   check against the county GIS zoning layer directly — that spatial
 *   jurisdiction-boundary lookup is out of scope for this v1 (it belongs to
 *   the county-conquest zoning pipeline, not this Worker).
 */

function headers(env) {
  return {
    apikey: env.SUPABASE_SERVICE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
    "Content-Type": "application/json",
  };
}

function requireBindings(env) {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) {
    throw new Error("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY bindings.");
  }
}

/** Looks up a parcel by pin_clean + co_no in zw_parcels. Returns null if not found. */
export async function fetchParcelForMassing(env, { parcelId, coNo }) {
  requireBindings(env);
  const url = `${env.SUPABASE_URL}/rest/v1/zw_parcels?pin_clean=eq.${encodeURIComponent(parcelId)}&co_no=eq.${coNo}&geom=not.is.null&limit=1`;
  const res = await fetch(url, { headers: headers(env) });
  if (!res.ok) throw new Error(`zw_parcels read failed (${res.status}): ${await res.text()}`);
  const [row] = await res.json();
  return row ?? null;
}

async function findZoningDistrict(env, jurisdictionId, zoningCode) {
  const url = `${env.SUPABASE_URL}/rest/v1/zoning_districts?jurisdiction_id=eq.${jurisdictionId}&code=eq.${encodeURIComponent(zoningCode)}&limit=1`;
  const res = await fetch(url, { headers: headers(env) });
  if (!res.ok) throw new Error(`zoning_districts read failed (${res.status}): ${await res.text()}`);
  const [row] = await res.json();
  return row ?? null;
}

async function findJurisdictionByName(env, county, name) {
  const url = `${env.SUPABASE_URL}/rest/v1/jurisdictions?county=ilike.${encodeURIComponent(county)}&name=ilike.${encodeURIComponent(name)}&limit=1`;
  const res = await fetch(url, { headers: headers(env) });
  if (!res.ok) throw new Error(`jurisdictions read failed (${res.status}): ${await res.text()}`);
  const [row] = await res.json();
  return row ?? null;
}

/**
 * @returns {{ standards: object, zoningDistrict: object, jurisdiction: object,
 *   resolutionMethod: "site_city_match" | "unincorporated_fallback" } | null}
 *   null means the zoning code could not be matched to ANY jurisdiction's
 *   district table in this county — caller must not guess standards.
 */
export async function resolveZoneStandards(env, { county, zoningCode, siteCity }) {
  requireBindings(env);
  if (!zoningCode) return null;

  const attempts = [];
  if (siteCity) attempts.push({ name: siteCity, method: "site_city_match" });
  attempts.push({ name: `Unincorporated ${county}`, method: "unincorporated_fallback" });
  attempts.push({ name: `Unincorporated ${county} County`, method: "unincorporated_fallback" });

  for (const attempt of attempts) {
    const jurisdiction = await findJurisdictionByName(env, county, attempt.name);
    if (!jurisdiction) continue;
    const zoningDistrict = await findZoningDistrict(env, jurisdiction.id, zoningCode);
    if (!zoningDistrict) continue;

    const stdRes = await fetch(
      `${env.SUPABASE_URL}/rest/v1/zone_standards?zoning_district_id=eq.${zoningDistrict.id}&limit=1`,
      { headers: headers(env) }
    );
    if (!stdRes.ok) throw new Error(`zone_standards read failed (${stdRes.status}): ${await stdRes.text()}`);
    const [standards] = await stdRes.json();
    if (!standards) continue;

    return { standards, zoningDistrict, jurisdiction, resolutionMethod: attempt.method };
  }
  return null;
}
