// GTM-22 S5 REPORT ENGINE — CMA (comparable sales), per issue #12853
// Amendment 2. Fed from public.fl_parcels (READ-ONLY): same co_no + zip +
// dor_uc, sqft within ±30%, recent arm's-length sale. Never runs without a
// resolved subject parcel — an unlocatable subject yields no comps table.
import { get as defaultGet } from '../supabase.js';

const SQFT_TOLERANCE = 0.30;
const MIN_SALE_PRICE = 25000;
const MAX_COMPS = 6;

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export async function buildCma(subjectParcel, { get = defaultGet, referenceYear = new Date().getUTCFullYear() } = {}) {
  if (!subjectParcel) {
    return { section_key: 'cma', comps: [], note: 'Comparable sales require a matched subject parcel; none available for an unlocatable property.' };
  }

  const sqft = subjectParcel.tot_lvg_ar || 0;
  const sqftMin = Math.round(sqft * (1 - SQFT_TOLERANCE));
  const sqftMax = Math.round(sqft * (1 + SQFT_TOLERANCE));
  const sinceYear = referenceYear - 2;

  const rows = await get(
    `fl_parcels?co_no=eq.${subjectParcel.co_no}&phy_zipcd=eq.${encodeURIComponent(subjectParcel.phy_zipcd || '')}&dor_uc=eq.${encodeURIComponent(subjectParcel.dor_uc)}&sale_yr1=gte.${sinceYear}&sale_prc1=gte.${MIN_SALE_PRICE}&tot_lvg_ar=gte.${sqftMin}&tot_lvg_ar=lte.${sqftMax}&parcel_id=neq.${encodeURIComponent(subjectParcel.parcel_id)}&select=parcel_id,phy_addr1,tot_lvg_ar,act_yr_blt,sale_prc1,sale_yr1,jv&limit=100`
  ).catch(() => []);

  const withDelta = rows.map(r => ({ ...r, sqft_delta: Math.abs((r.tot_lvg_ar || 0) - sqft) }));
  withDelta.sort((a, b) => a.sqft_delta - b.sqft_delta);
  const top = withDelta.slice(0, MAX_COMPS);

  const psfs = top.map(r => r.tot_lvg_ar > 0 ? r.sale_prc1 / r.tot_lvg_ar : null).filter(v => v != null);
  const prices = top.map(r => r.sale_prc1);
  const medianPrice = median(prices);
  const range = prices.length ? { min: Math.min(...prices), max: Math.max(...prices) } : null;
  const dispersion = (range && medianPrice) ? (range.max - range.min) / medianPrice : null;
  const dispersionFlag = dispersion == null ? null : dispersion > 0.5 ? 'HIGH' : dispersion > 0.25 ? 'MEDIUM' : 'LOW';

  // ±25% band — the brief's own fixture example (414: "JV-twin 0.80×JV")
  // is a 20% divergence, so "approximately equal" is read generously here.
  const jvTwin = subjectParcel.jv > 0
    ? top.find(r => r.jv > 0 && Math.abs(r.jv - subjectParcel.jv) / subjectParcel.jv < 0.25) || null
    : null;

  return {
    section_key: 'cma',
    comps: top.map(r => ({
      address: r.phy_addr1,
      sqft: r.tot_lvg_ar,
      year_built: r.act_yr_blt,
      sale_price: r.sale_prc1,
      sale_year: r.sale_yr1,
      price_per_sqft: r.tot_lvg_ar > 0 ? Number((r.sale_prc1 / r.tot_lvg_ar).toFixed(2)) : null,
    })),
    n: top.length,
    median_sale_price: medianPrice,
    range,
    dispersion_flag: dispersionFlag,
    jv_twin: jvTwin ? { address: jvTwin.phy_addr1, jv_ratio: Number((jvTwin.jv / subjectParcel.jv).toFixed(2)) } : null,
    note: top.length === 0 ? `No comps found within ±${Math.round(SQFT_TOLERANCE * 100)}% sqft / same zip+DOR-use in the last 2 years.` : null,
  };
}
