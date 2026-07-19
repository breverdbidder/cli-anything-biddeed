// GTM-22F — Gold Standard certification delivery gate.
//
// Product rule (Ariel, 2026-07-19, issue GTM-22F): a county's auction or
// parcel data must NOT reach an MCP customer unless that county is currently
// certified in v_certified_counties. This is a hard gate, not a quality
// label — it must never be softened into a warning field on the response.
//
// v_certified_counties is read live on every call. It is never cached at
// module scope: certification can be revoked intra-day (hysteresis N=2, see
// #12786) and a stale in-process cache would keep serving a revoked county's
// data until process restart.
//
// Fails CLOSED: if the certification lookup itself errors, no county-scoped
// data is returned. An unverifiable answer is not a green light — the
// alternative (fail open) is exactly the "leaks uncertified data" hazard
// called out in GTM-22F.
import { get } from './supabase.js';

// multi_county_auctions.county is already stored as lower_snake_case
// (verified live, 2026-07-19: all 60 distinct raw values across 2,290
// upcoming rows match this shape with zero variants — e.g. "palm_beach",
// "st_johns", "miami_dade"). This function is kept explicit and exported so
// the mapping is testable and so any future non-conforming raw value (new
// county, scraper regression) degrades safely instead of silently matching
// the wrong slug.
export function normalizeCountySlug(raw) {
  if (!raw) return '';
  return String(raw)
    .trim()
    .toLowerCase()
    .replace(/\bcounty\b/g, '')
    .replace(/[-\s]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

export async function getCertifiedSlugs() {
  const rows = await get('v_certified_counties?select=county_slug');
  return new Set(rows.map(r => r.county_slug));
}

export function notCertifiedResponse(rawCounty) {
  const slug = normalizeCountySlug(rawCounty);
  return {
    error: 'COUNTY_NOT_CERTIFIED',
    code: 'COUNTY_NOT_CERTIFIED',
    county: rawCounty,
    county_slug: slug,
    certified: false,
    message: `${rawCounty} is not currently Gold Standard certified. This county's auction/parcel data is not available via the MCP until certification is granted.`,
    action: 'Call list_certified_counties (free) for the current certified list. Certification status can change daily.',
  };
}

function gateUnavailableResponse(rawCounty) {
  return {
    error: 'CERT_GATE_UNAVAILABLE',
    code: 'CERT_GATE_UNAVAILABLE',
    county: rawCounty,
    certified: false,
    message: 'Certification status could not be verified right now. Failing closed — no county-scoped data returned. Retry shortly.',
  };
}

// Pre-charge gate for a single, already-known county. Returns null when the
// call may proceed; returns a ready-to-serialize error payload otherwise.
// Returns null (no-op) when rawCounty is falsy — callers with no county
// input at all have nothing to gate on here (e.g. underwrite_deal called
// with no case_number).
export async function assertCountyCertified(rawCounty) {
  if (!rawCounty) return null;
  try {
    const certified = await getCertifiedSlugs();
    const slug = normalizeCountySlug(rawCounty);
    if (!certified.has(slug)) return notCertifiedResponse(rawCounty);
    return null;
  } catch (err) {
    process.stderr.write(`[cert-gate] lookup failed for "${rawCounty}": ${err.message}\n`);
    return gateUnavailableResponse(rawCounty);
  }
}

// Row-array filter for tools that can return rows spanning multiple
// counties in one call (e.g. browse_deals / get_market_data with no county
// argument). Fails closed: a lookup error drops to an empty array rather
// than returning unfiltered rows.
export async function filterCertifiedRows(rows, countyField = 'county') {
  if (!rows?.length) return rows || [];
  try {
    const certified = await getCertifiedSlugs();
    return rows.filter(r => certified.has(normalizeCountySlug(r[countyField])));
  } catch (err) {
    process.stderr.write(`[cert-gate] row filter failed: ${err.message}\n`);
    return [];
  }
}

// Resolves the county of a specific auction row, for tools that accept
// case_number without requiring county in their schema (get_auction_detail,
// get_deposit_requirements). Without this, a customer who already has a
// case_number for an uncertified county could bypass the county-argument
// gate entirely.
export async function resolveAuctionCounty(caseNumber) {
  if (!caseNumber) return null;
  const rows = await get(
    `multi_county_auctions?case_number=eq.${encodeURIComponent(caseNumber)}&select=county&limit=1`
  ).catch(() => []);
  return rows[0]?.county || null;
}
