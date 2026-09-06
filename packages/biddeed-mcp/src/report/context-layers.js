// GTM-22 S5 REPORT ENGINE — SECTIONS 11-14: Context Layers (neighborhood,
// schools, FEMA flood, median income). Issue #20043 item 4.
//
// Two independent public sources, each cached 30 days in
// context_layer_cache(zip, layer, payload, fetched_at) so a report re-run
// for the same ZIP doesn't re-hit the upstream API:
//
//   FEMA  — NFHL public ArcGIS REST (hazards.fema.gov), keyed by lat/lon.
//           No API key required. CONFIRMED reachable (curl probe, 2026-09-06).
//   ACS   — Census ACS 5-year API, keyed by ZCTA. As of 2026-09-06 this
//           endpoint 302s to https://api.census.gov/data/missing_key.html
//           without an API key — the "free, no key" claim in the issue body
//           does not hold in this environment; no CENSUS_API_KEY secret is
//           configured for this repo (confirmed: env + `gh secret list`
//           both empty). Wired end-to-end and ready to activate the moment
//           a key is added — until then it renders Pending with this exact
//           gate, never a fabricated score.
//
// Schools is intentionally NOT implemented here — no free, in-repo source
// exists (per issue scope: "leave Pending... do not add a paid API").
import { get as defaultGet, insert as defaultInsert } from '../supabase.js';

const CACHE_TTL_DAYS = 30;
const FEMA_TIMEOUT_MS = 8000;
const ACS_TIMEOUT_MS = 8000;

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timeout after ${ms}ms`)), ms)),
  ]);
}

async function readCache(zip, layer, { get = defaultGet } = {}) {
  if (!zip) return null;
  const cutoff = new Date(Date.now() - CACHE_TTL_DAYS * 24 * 60 * 60 * 1000).toISOString();
  const rows = await get(
    `context_layer_cache?zip=eq.${encodeURIComponent(zip)}&layer=eq.${layer}` +
    `&fetched_at=gte.${cutoff}&select=payload,fetched_at&order=fetched_at.desc&limit=1`
  ).catch(() => []);
  return rows?.[0]?.payload ?? null;
}

async function writeCache(zip, layer, payload, { insert = defaultInsert } = {}) {
  if (!zip) return;
  // Fire-and-forget: a cache-write failure must never fail the report.
  await insert('context_layer_cache', { zip, layer, payload, fetched_at: new Date().toISOString() }).catch(() => {});
}

// ── FEMA NFHL flood zone by point ───────────────────────────────────────────
async function fetchFemaLive(lat, lon) {
  const url = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query' +
    `?geometry=${lon},${lat}&geometryType=esriGeometryPoint&inSR=4326` +
    `&spatialRel=esriSpatialRelIntersects&outFields=FLD_ZONE,ZONE_SUBTY,STATIC_BFE&f=json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`FEMA NFHL ${res.status}`);
  const data = await res.json();
  if (data.error) throw new Error(`FEMA NFHL error: ${data.error.message || JSON.stringify(data.error)}`);
  const feature = data.features?.[0];
  if (!feature) {
    return { available: true, zone: null, sfha: null, bfe: null, note: 'No NFHL polygon at this point — outside mapped flood study area.', source: 'FEMA NFHL public REST' };
  }
  const zone = feature.attributes.FLD_ZONE || null;
  const sfha = zone != null ? /^A|^V/.test(zone) : null; // A*/V* zones = Special Flood Hazard Area
  const bfe = (feature.attributes.STATIC_BFE != null && feature.attributes.STATIC_BFE > -9000) ? feature.attributes.STATIC_BFE : null;
  return { available: true, zone, sfha, bfe, subtype: feature.attributes.ZONE_SUBTY || null, source: 'FEMA NFHL public REST' };
}

export async function fetchFemaFloodZone(lat, lon, zip, { get = defaultGet, insert = defaultInsert } = {}) {
  if (lat == null || lon == null) {
    return { available: false, reason: 'Pending — FEMA layer not yet wired; subject has no lat/lon on file' };
  }
  const cached = await readCache(zip, 'fema', { get });
  if (cached) return cached;
  try {
    const result = await withTimeout(fetchFemaLive(lat, lon), FEMA_TIMEOUT_MS, 'FEMA NFHL');
    await writeCache(zip, 'fema', result, { insert });
    return result;
  } catch (err) {
    return { available: false, reason: `Pending — FEMA NFHL lookup failed: ${err.message}` };
  }
}

// ── Census ACS 5-year neighborhood scores by ZCTA ───────────────────────────
const ACS_VARS = {
  median_income: 'B19013_001E',
  population: 'B01003_001E',
  poverty_count: 'B17001_002E',
  poverty_universe: 'B17001_001E',
  owner_occupied: 'B25003_002E',
  total_occupied: 'B25003_001E',
  median_rent: 'B25064_001E',
};

async function fetchAcsLive(zip) {
  const apiKey = process.env.CENSUS_API_KEY;
  if (!apiKey) {
    throw new Error('CENSUS_API_KEY not configured — Census ACS API returns HTTP 302 to missing_key.html without one (confirmed 2026-09-06)');
  }
  const vars = Object.values(ACS_VARS).join(',');
  const url = `https://api.census.gov/data/2022/acs/acs5?get=${vars}&for=zip%20code%20tabulation%20area:${zip}&key=${apiKey}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Census ACS ${res.status}`);
  const rows = await res.json();
  const header = rows[0];
  const values = rows[1];
  if (!values) throw new Error('Census ACS returned no row for this ZCTA');
  const byName = Object.fromEntries(header.map((h, i) => [h, values[i]]));
  const povertyRate = Number(byName[ACS_VARS.poverty_universe]) > 0
    ? Number(byName[ACS_VARS.poverty_count]) / Number(byName[ACS_VARS.poverty_universe])
    : null;
  const ownershipRate = Number(byName[ACS_VARS.total_occupied]) > 0
    ? Number(byName[ACS_VARS.owner_occupied]) / Number(byName[ACS_VARS.total_occupied])
    : null;
  return {
    available: true,
    median_income: Number(byName[ACS_VARS.median_income]) || null,
    median_rent: Number(byName[ACS_VARS.median_rent]) || null,
    poverty_rate: povertyRate != null ? Number(povertyRate.toFixed(3)) : null,
    ownership_rate: ownershipRate != null ? Number(ownershipRate.toFixed(3)) : null,
    population: Number(byName[ACS_VARS.population]) || null,
    source: 'Census ACS 5-year 2022, ZCTA',
  };
}

export async function fetchNeighborhoodAcs(zip, { get = defaultGet, insert = defaultInsert } = {}) {
  if (!zip) {
    return { available: false, reason: 'Pending — neighborhood layer not yet wired for this county; no ZIP on file' };
  }
  const cached = await readCache(zip, 'acs', { get });
  if (cached) return cached;
  try {
    const result = await withTimeout(fetchAcsLive(zip), ACS_TIMEOUT_MS, 'Census ACS');
    await writeCache(zip, 'acs', result, { insert });
    return result;
  } catch (err) {
    return { available: false, reason: `Pending — ${err.message}` };
  }
}
