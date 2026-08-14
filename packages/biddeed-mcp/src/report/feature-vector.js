// GTM-22 S5 REPORT ENGINE — feature vector assembly for shapira_models v14.0.
//
// FINDING (2026-07-20, issue #12853): the v14.0 training run (gha:26529179958)
// stored the trained artifact (model.json), the feature NAME list
// (features.json), and metrics — but no feature-engineering SOURCE CODE or
// county-encoding MAP artifact alongside them (storage/shapira-models/v14/...
// contains exactly features.json, metrics.json, model.json — confirmed via
// live storage list). This module is therefore a best-effort RECONSTRUCTION
// of the 21 features from multi_county_auctions columns, not a verified port
// of the original training pipeline. Fields marked INFERRED below are a
// judgment call, not a re-derivation — the report must disclose this in its
// provenance section rather than presenting the probability as exact.
export const FEATURE_NAMES = [
  'judgment_amount_log1p', 'opening_bid_log1p', 'market_value_log1p',
  'assessed_value_log1p', 'prior_sale_price_log1p', 'beds_f', 'baths_f',
  'sqft_f', 'property_age', 'opening_to_market', 'judgment_to_market',
  'years_since_prior_sale', 'has_prior_sale', 'is_foreclosure', 'is_tax_deed',
  'has_homestead', 'owner_is_estate', 'owner_is_entity', 'owner_is_lender',
  'is_diamond', 'county_target_enc',
];

const ENTITY_RE = /\b(LLC|INC|CORP|LP|LLP|TRUST|TRUSTEE|HOLDINGS?|PARTNERS?|CO)\b/i;
const ESTATE_RE = /\b(ESTATE OF|HEIRS OF|DECEASED|SURVIVING)\b/i;
const LENDER_RE = /\b(BANK|MORTGAGE|LENDING|SERVICING|NATIONAL ASSOCIATION|FEDERAL SAVINGS|CREDIT UNION|HOME LOANS?)\b/i;

function log1p(v) {
  const n = Number(v) || 0;
  return Math.log1p(Math.max(0, n));
}

function safeRatio(numer, denom) {
  const d = Number(denom) || 0;
  if (d <= 0) return 0;
  return (Number(numer) || 0) / d;
}

// county_target_enc: the original training pipeline presumably fit a
// per-county mean-target encoding on the training corpus. That fitted map is
// not present in storage. This computes the same statistic LIVE — the
// county's own historical third_party_purchase rate — which is the correct
// formula for a mean-target encoding, but computed on today's (larger,
// still-growing) corpus rather than the exact training-time snapshot. Labeled
// INFERRED in the report, not CONFIRMED.
export async function computeCountyTargetEncoding(county, { get }) {
  const rows = await get(
    `multi_county_auctions?county=eq.${encodeURIComponent(county.toLowerCase())}&winning_bidder=in.("3rd Party","Plaintiff","3rd Party (inferred)","Plaintiff (inferred)")&select=winning_bidder&limit=5000`
  ).catch(() => []);
  if (!rows.length) return { value: 0.42, n: 0, inferred: true }; // corpus-wide fallback prior, disclosed
  const thirdParty = rows.filter(r => r.winning_bidder === '3rd Party' || r.winning_bidder === '3rd Party (inferred)').length;
  return { value: thirdParty / rows.length, n: rows.length, inferred: true };
}

// auction: a multi_county_auctions row. countyEncoding: { value, n, inferred }
// from computeCountyTargetEncoding. auctionYear: reference year for age/years-
// since-sale math (uses auction_date, not wall-clock, so results are
// reproducible for historical rows).
export function buildFeatureVector(auction, countyEncoding) {
  const auctionYear = auction.auction_date ? new Date(auction.auction_date).getUTCFullYear() : new Date().getUTCFullYear();
  const marketValue = auction.market_value || auction.assessed_value || 0;
  const ownerName = auction.owner_name || '';
  const priorSaleYear = auction.prior_sale_date ? new Date(auction.prior_sale_date).getUTCFullYear() : null;

  const vector = {
    judgment_amount_log1p: log1p(auction.judgment_amount),
    opening_bid_log1p: log1p(auction.opening_bid),
    market_value_log1p: log1p(marketValue),
    assessed_value_log1p: log1p(auction.assessed_value),
    prior_sale_price_log1p: log1p(auction.prior_sale_price),
    beds_f: Number(auction.bedrooms ?? auction.beds ?? 0),
    baths_f: Number(auction.bathrooms ?? auction.baths ?? 0),
    sqft_f: Number(auction.living_area_sqft ?? auction.sqft ?? 0),
    property_age: auction.year_built ? Math.max(0, auctionYear - auction.year_built) : 0,
    opening_to_market: safeRatio(auction.opening_bid, marketValue),
    judgment_to_market: safeRatio(auction.judgment_amount, marketValue),
    years_since_prior_sale: priorSaleYear ? Math.max(0, auctionYear - priorSaleYear) : 0,
    has_prior_sale: auction.prior_sale_date ? 1 : 0,
    is_foreclosure: auction.sale_type === 'foreclosure' ? 1 : 0,
    is_tax_deed: auction.sale_type === 'tax_deed' ? 1 : 0,
    has_homestead: auction.homestead_status === 'homestead' ? 1 : 0,
    // INFERRED — owner-name pattern classification, no ground-truth column exists.
    owner_is_estate: ESTATE_RE.test(ownerName) ? 1 : 0,
    owner_is_entity: ENTITY_RE.test(ownerName) ? 1 : 0,
    owner_is_lender: LENDER_RE.test(ownerName) ? 1 : 0,
    // INFERRED — mapped to the data-quality "matched_clean" parity flag as the
    // closest available proxy for a "diamond" (highest-confidence) row; the
    // true definition used at training time is not recoverable from this repo.
    is_diamond: auction.parity_status === 'matched_clean' ? 1 : 0,
    county_target_enc: countyEncoding?.value ?? 0.42,
  };

  return { array: FEATURE_NAMES.map(name => vector[name]), byName: vector, v4Array: V4_FEATURE_NAMES.map(name => vector[name]) };
}

// FIX (issue #19079, Aug 14 2026): the V4 stacked ensemble (Modal +
// xgb_v4.json/lgbm_v4_flat.json, model_version v4.0-20260802-015242) was
// trained on a DIFFERENT, smaller 13-feature set than this file's own
// FEATURE_NAMES (21 features, reconstructed for the retired v14.0 model -
// see file header). Modal correctly rejected the mismatched 21-length
// vector ("feature_vector must be 13 floats"); the JS fallback trees did
// NOT error on it, which is not evidence they were scoring correctly -
// they were almost certainly reading the wrong array positions.
//
// This exact 13-name, exact-order list is the AUTHORITATIVE one - pulled
// directly from shapira_models.features_used for model_version
// v4.0-20260802-015242 (recorded by the training script itself at train
// time, 2026-08-02), not reconstructed or guessed. All 13 names already
// exist as keys on the `vector` object computed above - this only changes
// which 13 (and what order) get sent to the V4 models specifically.
export const V4_FEATURE_NAMES = [
  'judgment_amount_log1p', 'opening_bid_log1p', 'assessed_value_log1p',
  'prior_sale_price_log1p', 'beds_f', 'baths_f', 'sqft_f', 'property_age',
  'opening_to_market', 'judgment_to_market', 'is_foreclosure', 'is_tax_deed',
  'county_target_enc',
];
