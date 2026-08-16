// BidDeed.AI — S5 REPORT ENGINE — DUAL-LAYER CMA
// Patent Claim 7 — two CMA layers are REQUIRED on every report.
//
// LAYER 1 — Distressed Market CMA (OUR MOAT)
//   Source: multi_county_auctions (READ-ONLY, SSOT §3)
//   Answers: What will this property clear for AT AUCTION in this county?
//   Shows investor: clearing ratio, auction-cleared comps, county distressed median
//
// LAYER 2 — Retail ARV CMA (EXIT VALUE)
//   Source: fl_parcels DOR state cadastral (READ-ONLY)
//   Answers: What is this property worth on the OPEN MARKET after auction?
//   Used as: primary ARV input to the Shapira Max Bid formula
//
// THE SPREAD BETWEEN THE TWO IS THE INVESTMENT THESIS.
//   Equity at acquisition = Layer 2 ARV − Winning Bid
//   Max Bid = Shapira formula using Layer 2 ARV as input
//   Layer 1 clears the deal screen; Layer 2 sizes the position.
//
// Never runs without a resolved subject parcel — unlocatable subject yields
// both layers empty with explicit notes, never fabricated numbers.
//
// FIX (issue #19079, Aug 14 2026): Layer 2 previously matched comps on
// zip + DOR-use-code + sqft + sale recency ONLY. Live audit on a real
// Hillsborough property (2470 sqft, 1976-built, assessed $239,342) found
// all 6 "matched" comps were 1985-1996 builds assessed $311K-$381K in the
// same zip — same sqft, completely different quality/vintage tier. Median
// comp price $432,000 fed a Shapira Max Bid of $269,961, which the
// sellability gate correctly rejected as insane vs the real clearing band
// ($148K-$180K, from actual sold-auction priors). Root cause: nothing in
// the comp query checked whether comps were actually comparable in VALUE,
// only in size/location/type. The existing JV-twin logic already applied
// an assessed-value proximity check to pick ONE best comp — this fix
// applies the same discipline to the WHOLE comp set, not just one pick.
// Also adds lot size (lnd_sqfoot, confirmed 100% populated for at least
// Hillsborough) as a second matching dimension, since two homes with
// identical living-area sqft on very different lot sizes are not
// equivalent comps either.
//
// NOTE ON GARAGE DATA (requested Aug 14 2026, investigated and confirmed
// NOT ADDED): has_garage / garage_spaces exist as columns on the separate
// `parcels` table, but are populated on ZERO of 437,371 rows statewide -
// not a Hillsborough gap, never actually collected anywhere in this
// dataset. CORRECTION (same day): that table was initially mislabeled here
// as "ATTOM-sourced" - verified false. 104,551 of ~104,562 rows with a
// source_url are literally internal://fl_parcels+zoning_assignments (i.e.
// this table is 99.99% a reshaped copy of fl_parcels itself, not an
// independent data source); attom_id/clip_id are null on every row. Only
// 11 rows trace to a real external source (county scrapes + FL state GIS).
// No ATTOM license or feed exists anywhere in this pipeline. Filtering or
// displaying on garage_spaces would silently pass everything (100% null)
// while looking like a real signal. Left out deliberately rather than
// faked. Revisit if/when a real garage data source is sourced.

import { get as defaultGet } from '../supabase.js';

// ─── Constants ─────────────────────────────────────────────────────────────
const SQFT_TOLERANCE      = 0.30;  // ±30% living-area sqft window for retail comps
const LOT_SQFT_TOLERANCE  = 0.40;  // ±40% lot-size window — lots vary more naturally than living area even among true comps
const JV_TOLERANCE        = 0.35;  // ±35% assessed-value window — NEW: the core fix. Prevents same-sqft/different-quality-tier mismatches (see FIX note above)
const MIN_SALE_PRICE      = 25000; // below this = not an arm's-length sale signal
const MAX_COMPS           = 6;     // max retail comps to surface
const MAX_DISTRESSED_COMPS = 5;    // max auction-cleared comps to surface
const DISTRESSED_SQFT_TOL = 0.40;  // wider tolerance for auction comps (thinner set)
const SINCE_YEAR_DEFAULT  = 2024;  // distressed priors window

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// ─── LAYER 1: Distressed Market CMA ────────────────────────────────────────
// Pulls from multi_county_auctions — completed/sold rows for the same county,
// same zip, same DOR use code (where available), similar sqft, since SINCE_YEAR.
// Returns: county clearing stats + up to MAX_DISTRESSED_COMPS auction-cleared comps.
export async function buildDistressedCma(subjectParcel, auction, {
  get = defaultGet,
  sinceYear = SINCE_YEAR_DEFAULT,
} = {}) {

  const county = (auction?.county || '').toLowerCase();

  if (!subjectParcel || !county) {
    return {
      section_key: 'cma_distressed',
      layer: 1,
      label: 'Auction Market Comps (Distressed) — What similar properties cleared for at auction',
      comps: [],
      note: 'Layer 1 requires a matched subject parcel and county — not available.',
    };
  }

  const sqft     = Number(subjectParcel.tot_lvg_ar) || 0;
  const sqftMin  = sqft > 0 ? Math.round(sqft * (1 - DISTRESSED_SQFT_TOL)) : 0;
  const sqftMax  = sqft > 0 ? Math.round(sqft * (1 + DISTRESSED_SQFT_TOL)) : 999999;
  const zip      = subjectParcel.phy_zipcd || '';
  const dorUc    = subjectParcel.dor_uc || '';

  // Build query — zip and dor_uc are used when available (tighter comps),
  // fall back to county-wide when zip yields < 3 results.
  let rows = [];
  if (zip) {
    rows = await get(
      `multi_county_auctions?county=eq.${encodeURIComponent(county)}` +
      `&tier1_sale_status=eq.SOLD` +
      `&auction_date=gte.${sinceYear}-01-01` +
      `&tier1_sold_amount=gt.${MIN_SALE_PRICE}` +
      (sqft > 0 ? `&living_area_sqft=gte.${sqftMin}&living_area_sqft=lte.${sqftMax}` : '') +
      (zip ? `&property_zip=eq.${encodeURIComponent(zip)}` : '') +
      `&select=case_number,property_address,property_zip,living_area_sqft,assessed_value,judgment_amount,tier1_sold_amount,tier1_buyer_type,auction_date,dor_uc` +
      `&order=auction_date.desc&limit=50`
    ).catch(() => []);
  }

  // Widen to county if zip gave < 3
  if (rows.length < 3) {
    rows = await get(
      `multi_county_auctions?county=eq.${encodeURIComponent(county)}` +
      `&tier1_sale_status=eq.SOLD` +
      `&auction_date=gte.${sinceYear}-01-01` +
      `&tier1_sold_amount=gt.${MIN_SALE_PRICE}` +
      (sqft > 0 ? `&living_area_sqft=gte.${sqftMin}&living_area_sqft=lte.${sqftMax}` : '') +
      `&select=case_number,property_address,property_zip,living_area_sqft,assessed_value,judgment_amount,tier1_sold_amount,tier1_buyer_type,auction_date,dor_uc` +
      `&order=auction_date.desc&limit=100`
    ).catch(() => []);
  }

  // Sort by sqft proximity
  if (sqft > 0) {
    rows.sort((a, b) =>
      Math.abs((a.living_area_sqft || 0) - sqft) -
      Math.abs((b.living_area_sqft || 0) - sqft)
    );
  }
  const top = rows.slice(0, MAX_DISTRESSED_COMPS);

  // County-level clearing stats from this comp set (wider county view)
  const allSoldAmounts   = rows.map(r => Number(r.tier1_sold_amount)).filter(v => v > 0);
  const allClearingRatios = rows
    .filter(r => r.assessed_value > 0 && r.tier1_sold_amount > 0)
    .map(r => Number(r.tier1_sold_amount) / Number(r.assessed_value));
  const allJudgmentRatios = rows
    .filter(r => r.judgment_amount > 0 && r.tier1_sold_amount > 0)
    .map(r => Number(r.tier1_sold_amount) / Number(r.judgment_amount));

  const medianClearingRatio  = median(allClearingRatios);
  const medianJudgmentRatio  = median(allJudgmentRatios);
  const medianDistressedPrice = median(allSoldAmounts);

  // Derived: what would THIS property clear at the county median ratio?
  const impliedClearingPrice = medianClearingRatio && subjectParcel.jv > 0
    ? Math.round(Number(subjectParcel.jv) * medianClearingRatio)
    : null;

  return {
    section_key: 'cma_distressed',
    layer: 1,
    label: 'Auction Market Comps (Distressed) — What similar properties cleared for at auction',
    county,
    n_county_outcomes: rows.length,
    n_comps_shown: top.length,
    since_year: sinceYear,
    median_clearing_ratio_sold_to_assessed: medianClearingRatio
      ? Number(medianClearingRatio.toFixed(3))
      : null,
    median_judgment_ratio_sold_to_judgment: medianJudgmentRatio
      ? Number(medianJudgmentRatio.toFixed(3))
      : null,
    median_distressed_price: medianDistressedPrice
      ? Math.round(medianDistressedPrice)
      : null,
    implied_clearing_price_for_subject: impliedClearingPrice,
    comps: top.map(r => ({
      address:         r.property_address,
      zip:             r.property_zip,
      sqft:            r.living_area_sqft,
      assessed_value:  r.assessed_value,
      judgment_amount: r.judgment_amount,
      sold_amount:     Number(r.tier1_sold_amount),
      auction_date:    r.auction_date,
      buyer_type:      r.tier1_buyer_type || 'unknown',
      clearing_pct_of_assessed: r.assessed_value > 0
        ? Number((Number(r.tier1_sold_amount) / Number(r.assessed_value) * 100).toFixed(1))
        : null,
    })),
    note: top.length === 0
      ? `No distressed comps found in ${county} county (${sinceYear}→). Layer 1 clearing ratio unavailable — Shapira formula falls back to county-level priors.`
      : null,
  };
}

const HOMEHARVEST_SQFT_TOLERANCE = 0.30; // same window as the fl_parcels retail comp match

// ─── LAYER 2b: Realtor.com (HomeHarvest) retail comps fallback ─────────────
// Interim/bootstrap comps source (Ariel, Aug 16 2026) until revenue supports
// a licensed API (RentCast or similar) -- see scripts/homeharvest_ingest.py.
// Only consulted when fl_parcels (the DOR-recorded sale history) has NO
// comps for this subject -- fl_parcels sale history is often thin/stale;
// this fills that gap with closed MLS-adjacent sales instead of leaving the
// section on "Pending". Never merged silently with fl_parcels comps --
// comp_source on the returned object always says which one actually ran.
async function fetchHomeHarvestSaleComps(subjectParcel, { get }) {
  const zip = subjectParcel.phy_zipcd || '';
  if (!zip) return [];

  const sqft = Number(subjectParcel.tot_lvg_ar) || 0;
  const sqftMin = sqft > 0 ? Math.round(sqft * (1 - HOMEHARVEST_SQFT_TOLERANCE)) : 0;
  const sqftMax = sqft > 0 ? Math.round(sqft * (1 + HOMEHARVEST_SQFT_TOLERANCE)) : 999999;

  const rows = await get(
    `sale_listings?zip_code=eq.${encodeURIComponent(zip)}` +
    `&source=eq.homeharvest_realtor_com` +
    `&sold_price=gte.${MIN_SALE_PRICE}` +
    (sqft > 0 ? `&square_footage=gte.${sqftMin}&square_footage=lte.${sqftMax}` : '') +
    `&select=formatted_address,square_footage,lot_size,year_built,sold_price,listed_date,honesty_marker` +
    `&order=listed_date.desc&limit=${MAX_COMPS}`
  ).catch(() => []);

  return rows;
}

// ─── LAYER 2: Retail ARV CMA ────────────────────────────────────────────────
// Source: fl_parcels (DOR state cadastral, READ-ONLY).
// Answers: What is this property worth on the OPEN MARKET?
// This is the ARV that feeds the Shapira Max Bid formula.
export async function buildCma(subjectParcel, {
  get = defaultGet,
  referenceYear = new Date().getUTCFullYear(),
} = {}) {

  if (!subjectParcel) {
    return {
      section_key: 'cma',
      layer: 2,
      label: 'Retail Market Comps (Open Market ARV) — Exit value after acquisition',
      comps: [],
      note: 'Layer 2 requires a matched subject parcel — not available for unlocatable property.',
    };
  }

  const sqft    = subjectParcel.tot_lvg_ar || 0;
  const sqftMin = Math.round(sqft * (1 - SQFT_TOLERANCE));
  const sqftMax = Math.round(sqft * (1 + SQFT_TOLERANCE));
  const sinceYear = referenceYear - 2;

  // NEW (issue #19079): assessed-value (jv) proximity band. This is the core
  // fix — without it, comps matched only on sqft+zip+type can be a
  // completely different quality/vintage tier (see file header FIX note).
  // Guarded: if the subject has no jv on file, skip this filter rather than
  // producing an impossible range.
  const subjectJv = Number(subjectParcel.jv) || 0;
  const jvMin = subjectJv > 0 ? Math.round(subjectJv * (1 - JV_TOLERANCE)) : null;
  const jvMax = subjectJv > 0 ? Math.round(subjectJv * (1 + JV_TOLERANCE)) : null;

  // NEW (issue #19079): lot size (lnd_sqfoot) proximity band, same guard pattern.
  const subjectLot = Number(subjectParcel.lnd_sqfoot) || 0;
  const lotMin = subjectLot > 0 ? Math.round(subjectLot * (1 - LOT_SQFT_TOLERANCE)) : null;
  const lotMax = subjectLot > 0 ? Math.round(subjectLot * (1 + LOT_SQFT_TOLERANCE)) : null;

  const rows = await get(
    `fl_parcels?co_no=eq.${subjectParcel.co_no}` +
    `&phy_zipcd=eq.${encodeURIComponent(subjectParcel.phy_zipcd || '')}` +
    `&dor_uc=eq.${encodeURIComponent(subjectParcel.dor_uc)}` +
    `&sale_yr1=gte.${sinceYear}` +
    `&sale_prc1=gte.${MIN_SALE_PRICE}` +
    `&tot_lvg_ar=gte.${sqftMin}&tot_lvg_ar=lte.${sqftMax}` +
    (jvMin != null ? `&jv=gte.${jvMin}&jv=lte.${jvMax}` : '') +
    (lotMin != null ? `&lnd_sqfoot=gte.${lotMin}&lnd_sqfoot=lte.${lotMax}` : '') +
    `&parcel_id=neq.${encodeURIComponent(subjectParcel.parcel_id)}` +
    `&select=parcel_id,phy_addr1,tot_lvg_ar,act_yr_blt,sale_prc1,sale_yr1,jv,lnd_sqfoot` +
    `&limit=100`
  ).catch(() => []);

  // Fallback: if the jv+lot band is too tight for this market (thin comp
  // pool), widen by dropping jv/lot filters rather than silently returning
  // zero comps — but flag it in the note so the report is honest about
  // which criteria actually applied.
  let usedFallback = false;
  let finalRows = rows;
  if (rows.length < 3 && (jvMin != null || lotMin != null)) {
    usedFallback = true;
    finalRows = await get(
      `fl_parcels?co_no=eq.${subjectParcel.co_no}` +
      `&phy_zipcd=eq.${encodeURIComponent(subjectParcel.phy_zipcd || '')}` +
      `&dor_uc=eq.${encodeURIComponent(subjectParcel.dor_uc)}` +
      `&sale_yr1=gte.${sinceYear}` +
      `&sale_prc1=gte.${MIN_SALE_PRICE}` +
      `&tot_lvg_ar=gte.${sqftMin}&tot_lvg_ar=lte.${sqftMax}` +
      `&parcel_id=neq.${encodeURIComponent(subjectParcel.parcel_id)}` +
      `&select=parcel_id,phy_addr1,tot_lvg_ar,act_yr_blt,sale_prc1,sale_yr1,jv,lnd_sqfoot` +
      `&limit=100`
    ).catch(() => []);
  }

  const withDelta = finalRows.map(r => ({
    ...r,
    sqft_delta: Math.abs((r.tot_lvg_ar || 0) - sqft),
  }));
  withDelta.sort((a, b) => a.sqft_delta - b.sqft_delta);
  const top = withDelta.slice(0, MAX_COMPS);

  const prices      = top.map(r => r.sale_prc1);
  const medianPrice = median(prices);
  const range       = prices.length ? { min: Math.min(...prices), max: Math.max(...prices) } : null;
  const dispersion  = (range && medianPrice) ? (range.max - range.min) / medianPrice : null;
  const dispersionFlag = dispersion == null ? null
    : dispersion > 0.5 ? 'HIGH'
    : dispersion > 0.25 ? 'MEDIUM'
    : 'LOW';

  // JV-twin: comp with assessed value within ±25% of subject's — the most
  // reliable retail indication for this exact quality tier. Kept even with
  // the new whole-set jv filter above (JV_TOLERANCE=0.35) since this picks
  // the SINGLE tightest match within that already-filtered set.
  const jvTwin = subjectParcel.jv > 0
    ? top.find(r =>
        r.jv > 0 &&
        Math.abs(r.jv - subjectParcel.jv) / subjectParcel.jv < 0.25
      ) || null
    : null;

  // fl_parcels (DOR-recorded sale history) has nothing for this subject --
  // fall back to Realtor.com (HomeHarvest) closed-sale comps before giving
  // up and reporting Pending. This is a distinct, honestly-labeled comp
  // source, not a merge with the DOR-sourced comps above.
  if (top.length === 0) {
    const hhRows = await fetchHomeHarvestSaleComps(subjectParcel, { get });
    if (hhRows.length > 0) {
      const hhPrices = hhRows.map(r => Number(r.sold_price)).filter(v => v > 0);
      const hhMedian = median(hhPrices);
      const hhRange  = hhPrices.length ? { min: Math.min(...hhPrices), max: Math.max(...hhPrices) } : null;
      return {
        section_key: 'cma',
        layer: 2,
        comp_source: 'homeharvest_realtor_com',
        label: 'Retail Market Comps (Open Market ARV) — Realtor.com closed sales — Exit value after acquisition',
        comps: hhRows.map(r => ({
          address: r.formatted_address,
          sqft: r.square_footage,
          lot_sqft: r.lot_size ?? null,
          year_built: r.year_built,
          sale_price: Number(r.sold_price),
          sale_date: r.listed_date,
          price_per_sqft: r.square_footage > 0
            ? Number((Number(r.sold_price) / r.square_footage).toFixed(2))
            : null,
          honesty_marker: r.honesty_marker,
        })),
        n: hhRows.length,
        median_sale_price: hhMedian,
        range: hhRange,
        match_criteria: { sqft_tolerance_pct: Math.round(HOMEHARVEST_SQFT_TOLERANCE * 100), zip_match: true },
        jv_twin: null,
        note: 'No DOR-recorded sale comps for this parcel — showing Realtor.com closed-sale comps instead (scraped, not MLS/Zillow/Redfin-licensed data; interim source pending a licensed comps API).',
      };
    }
  }

  return {
    section_key: 'cma',
    layer: 2,
    comp_source: 'fl_parcels_dor',
    label: 'Retail Market Comps (Open Market ARV) — Exit value after acquisition',
    comps: top.map(r => ({
      address:       r.phy_addr1,
      sqft:          r.tot_lvg_ar,
      lot_sqft:      r.lnd_sqfoot ?? null,
      year_built:    r.act_yr_blt,
      assessed_value: r.jv ?? null,
      sale_price:    r.sale_prc1,
      sale_year:     r.sale_yr1,
      price_per_sqft: r.tot_lvg_ar > 0
        ? Number((r.sale_prc1 / r.tot_lvg_ar).toFixed(2))
        : null,
    })),
    n: top.length,
    median_sale_price: medianPrice,
    range,
    dispersion_flag: dispersionFlag,
    match_criteria: {
      sqft_tolerance_pct: Math.round(SQFT_TOLERANCE * 100),
      jv_tolerance_pct: jvMin != null ? Math.round(JV_TOLERANCE * 100) : null,
      lot_tolerance_pct: lotMin != null ? Math.round(LOT_SQFT_TOLERANCE * 100) : null,
      jv_and_lot_filters_applied: !usedFallback && (jvMin != null || lotMin != null),
    },
    jv_twin: jvTwin
      ? {
          address:  jvTwin.phy_addr1,
          jv_ratio: Number((jvTwin.jv / subjectParcel.jv).toFixed(2)),
          sale_price: jvTwin.sale_prc1,
          retail_indication: jvTwin.sale_prc1,
        }
      : null,
    note: top.length === 0
      ? `No retail comps found within ±${Math.round(SQFT_TOLERANCE * 100)}% sqft / same zip+DOR-use in the last 2 years, and no Realtor.com closed-sale comps available for this zip either.`
      : usedFallback
      ? `Assessed-value/lot-size match criteria too tight for this market (thin comp pool) — widened to sqft+zip+type only. Comps shown may span a wider value tier than the subject; treat median with more caution.`
      : null,
  };
}
