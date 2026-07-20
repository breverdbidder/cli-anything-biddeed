// GTM-22 S5 REPORT ENGINE — state-parcel resolver (fl_parcels, READ-ONLY).
//
// FINDING (2026-07-20, issue #12853 Amendment 1): fl_parcels.co_no is NOT a
// single consistent numbering scheme. `public.fl_counties` (the registry
// table) and the alphabetical constant in scripts/consolidation_modal.py
// BOTH claim Marion = co_no 42 — but live fl_parcels rows for real Marion
// cities (Ocala, Dunnellon, Summerfield — confirmed against
// multi_county_auctions addresses) carry co_no=52, while co_no=42 in
// fl_parcels resolves to "Alford" (a Jackson County city). The two registries
// disagree with the ingested data for at least this county. Do not trust
// fl_counties.co_no or DOR_COUNTIES for resolution — per the brief's
// standing instruction, resolve per county via address match + census, never
// assume. CONFIRMED_CO_NO below holds only empirically re-verified values;
// anything else must be re-verified live before use, not guessed from either
// registry.
import { get as defaultGet } from '../supabase.js';

export const CONFIRMED_CO_NO = {
  marion: 52, // live-verified 2026-07-20 against Marion auction addresses (Ocala/Dunnellon/Summerfield)
};

function normalizeStreet(addr) {
  return String(addr || '')
    .toUpperCase()
    .replace(/[.,]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// Splits "14470 SE 91ST TER, SUMMERFIELD, FL, 34491" into street + city.
function splitAddress(fullAddress) {
  const [street, ...rest] = String(fullAddress || '').split(',');
  const city = rest[0]?.trim().toUpperCase().replace(/^-\s*/, '') || null;
  return { street: normalizeStreet(street), city };
}

// Returns { matched, parcel, candidates } — never a silent single guess when
// multiple candidates share a house number (see 91ST AVE vs 91ST TER
// disambiguation found live for fixture 414's neighborhood).
export async function matchStateParcel(county, propertyAddress, { get = defaultGet } = {}) {
  const countySlug = county.toLowerCase();
  const coNo = CONFIRMED_CO_NO[countySlug];
  if (!coNo) {
    return { matched: false, reason: `co_no not empirically confirmed for county "${county}" — refusing to guess from fl_counties/DOR registry (see parcel-match.js header)` };
  }
  const { street, city } = splitAddress(propertyAddress);
  if (!street) {
    return { matched: false, reason: 'no address to match' };
  }

  const rows = await get(
    `fl_parcels?co_no=eq.${coNo}&phy_addr1=eq.${encodeURIComponent(street)}&select=*`
  ).catch(() => []);

  const filtered = city ? rows.filter(r => r.phy_city?.toUpperCase() === city) : rows;
  const candidates = filtered.length ? filtered : rows;

  if (candidates.length === 0) {
    return { matched: false, reason: 'no fl_parcels row matched this address', co_no: coNo };
  }
  if (candidates.length > 1) {
    return { matched: false, reason: 'ambiguous match — multiple fl_parcels rows for this address', candidates, co_no: coNo };
  }
  return { matched: true, parcel: candidates[0], co_no: coNo };
}
