// GTM-22 S5 REPORT ENGINE — 17-section + SECTION ZW + CMA property
// intelligence report. This is the deliverable of predict_auction_outcome
// (issue #12853): a structured JSON object mirroring HC Agile Insights
// section-for-section, with BidDeed's honesty semantics layered on top.
//
// Honesty rules enforced here (non-negotiable, per the brief):
//   - Hidden max bid renders "Hidden", never $0 and never omitted.
//   - Unenrichable fields render "Pending <reason>", never estimated silently.
//   - An unlocatable property returns SKIP with NO value estimate and the
//     explicit refusal sentence — never a fabricated number.
//   - Quitclaim/sub-$1000 prior sales are labeled "no price signal", never
//     used as a comp.
//   - Every dollar figure carries a `source` field.
import { get as defaultGet } from '../supabase.js';
import { getCountyClearancePriors } from './priors.js';
import { buildZwSection } from './zw-section.js';
import { buildCma, buildDistressedCma } from './cma.js';
import { matchStateParcel } from './parcel-match.js';
import { computeCountyTargetEncoding, buildFeatureVector } from './feature-vector.js';
import { predictEnsemble } from './ensemble-model.js';
import { deriveRedFlags, hasJuniorLienRisk, hasTaxDeedLienRisk, JUNIOR_JUDGMENT_TO_ASSESSED } from './red-flags.js';
import { buildOutcomeSection } from './outcome.js';
import { classify as classifyLienSurvival } from './lien-survival.js';
import { DISCLAIMER_FULL } from '../disclaimer.js';

const NO_ESTIMATE_REFUSAL = "An estimate here would be fabrication; BidDeed declines where HouseCanary would extrapolate.";
const MIN_PRICE_SIGNAL = 1000;

function money(value, source) {
  if (value == null) return { value: null, display: 'Pending — no value on file', source };
  return { value, display: `$${Number(value).toLocaleString()}`, source };
}

function hiddenOr(value, source) {
  if (value == null) return { value: null, display: 'Hidden', source };
  return { value, display: `$${Number(value).toLocaleString()}`, source };
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function grade(marginPct, locatable) {
  if (!locatable) return 'D';
  if (marginPct >= 0.40) return 'A';
  if (marginPct >= 0.25) return 'B+';
  if (marginPct >= 0.10) return 'B';
  if (marginPct >= 0) return 'C';
  return 'D';
}

const STALE_SALE_YEARS = 5; // beyond this, a raw sale price is historical context only, not a value anchor

// DUAL-BAND value estimate — separates two fundamentally different quantities:
//
//   CLEARING BAND  (expected auction price)
//     Anchors: county sold/assessed prior · county sold/FJ prior · Layer 1 distressed CMA median
//     → What this property will likely SELL FOR at auction
//
//   MARKET BAND    (retail ARV / exit value)
//     Anchors: prior arm's-length sale · Layer 2 retail CMA median · JV-twin retail indication
//     → What this property is worth on the OPEN MARKET after acquisition
//
// THE SPREAD = THE INVESTMENT THESIS: buying inside the clearing band while
// the market band represents your exit means every dollar below the ceiling
// is day-one equity.
//
// Shapira Max Bid formula uses MARKET BAND midpoint as ARV (not clearing band).
// Layer 1 distressed CMA feeds the clearing band context only.
//
// KNOWN METHODOLOGY NOTE: prior bids averaged a single band blending both —
// which was ambiguous when scoring a realised auction price against the band.
// This split resolves it: the scorecard in §18 now grades clearing vs clearing
// and market vs market independently.
function computeValueEstimate(auction, priors, cma, distressedCma) {
  const clearingAnchors = [];
  const marketAnchors   = [];

  // ── Clearing anchors (county priors + Layer 1) ────────────────────────────
  if (priors && !priors.insufficient && priors.median_sold_to_assessed && auction.assessed_value > 0) {
    clearingAnchors.push({
      key: 'county_clearance_prior',
      value: auction.assessed_value * priors.median_sold_to_assessed,
      source: `county clearance prior (median sold/assessed=${priors.median_sold_to_assessed.toFixed(3)}, n=${priors.n_sold_to_assessed})`,
    });
  }
  if (priors && !priors.insufficient && priors.median_sold_to_judgment && auction.judgment_amount > 0) {
    // Junior-lien guard: the sold/FJ ratio prior is fit on first-mortgage
    // foreclosures. A judgment far below assessed value is junior/HOA scale,
    // and multiplying it by the ratio produces a garbage anchor that drags
    // the whole clearing average ($17,403 x 0.538 = $9,357 on a $457K house
    // — Palm Beach 502025CA005319XXXAMB). Excluded, reason shown, following
    // the same value:null convention as the stale prior-sale exclusion.
    const jToAssessed = auction.assessed_value > 0
      ? auction.judgment_amount / auction.assessed_value : null;
    if (jToAssessed != null && jToAssessed < JUNIOR_JUDGMENT_TO_ASSESSED) {
      clearingAnchors.push({
        key: 'judgment_ratio_prior',
        value: null,
        source: `judgment $${auction.judgment_amount.toLocaleString()} is ${Math.round(jToAssessed * 100)}% of assessed — junior-lien scale, excluded as clearing anchor (sold/FJ prior assumes a first-mortgage judgment)`,
      });
    } else {
      clearingAnchors.push({
        key: 'judgment_ratio_prior',
        value: auction.judgment_amount * priors.median_sold_to_judgment,
        source: `county clearance prior (median sold/FJ=${priors.median_sold_to_judgment.toFixed(3)}, n=${priors.n_sold_to_judgment})`,
      });
    }
  }
  // Layer 1 distressed CMA median (from multi_county_auctions)
  if (distressedCma?.median_distressed_price > 0) {
    clearingAnchors.push({
      key: 'layer1_distressed_cma_median',
      value: distressedCma.median_distressed_price,
      source: `Layer 1 distressed CMA median of ${distressedCma.n_county_outcomes} auction outcomes in ${distressedCma.county} county (${distressedCma.since_year}→)`,
    });
  }
  // Layer 1 implied clearing price for THIS property at county median ratio
  if (distressedCma?.implied_clearing_price_for_subject > 0) {
    clearingAnchors.push({
      key: 'layer1_implied_clearing_for_subject',
      value: distressedCma.implied_clearing_price_for_subject,
      source: `Layer 1 implied: assessed $${(auction.assessed_value||0).toLocaleString()} × clearing ratio ${distressedCma.median_clearing_ratio_sold_to_assessed}`,
    });
  }

  // ── Market anchors (prior sale + Layer 2 retail CMA) ─────────────────────
  const priorSaleYear = auction.prior_sale_date ? new Date(auction.prior_sale_date).getUTCFullYear() : null;
  const auctionYear   = auction.auction_date ? new Date(auction.auction_date).getUTCFullYear() : new Date().getUTCFullYear();
  const yearsSinceSale = priorSaleYear ? auctionYear - priorSaleYear : null;
  const hasPriorSalePriceSignal = auction.prior_sale_price > MIN_PRICE_SIGNAL && auction.prior_sale_date;

  if (hasPriorSalePriceSignal && yearsSinceSale != null && yearsSinceSale <= STALE_SALE_YEARS) {
    marketAnchors.push({
      key: 'prior_arms_length_sale',
      value: auction.prior_sale_price,
      source: `prior arm's-length sale ${auction.prior_sale_date} at $${auction.prior_sale_price.toLocaleString()}`,
    });
  } else if (hasPriorSalePriceSignal) {
    marketAnchors.push({
      key: 'prior_arms_length_sale',
      value: null,
      source: `prior sale ${auction.prior_sale_date} at $${auction.prior_sale_price.toLocaleString()} is ${yearsSinceSale}yr stale — shown in transaction_history, excluded as market anchor (no appreciation model)`,
    });
  } else if (auction.prior_sale_price != null) {
    marketAnchors.push({
      key: 'prior_arms_length_sale',
      value: null,
      source: 'no price signal — prior sale below $1,000/quitclaim-pattern, excluded',
    });
  }

  // Layer 2 retail CMA median
  if (cma?.n >= 3 && cma?.median_sale_price != null) {
    marketAnchors.push({
      key: 'layer2_retail_cma_median',
      value: cma.median_sale_price,
      source: `Layer 2 retail CMA median of ${cma.n} comps (±30% sqft, same zip+DOR-use, sale within 2yr)`,
    });
  }
  // JV-twin retail indication — single comp most comparable by assessed value
  if (cma?.jv_twin?.retail_indication > 0) {
    marketAnchors.push({
      key: 'layer2_jv_twin_retail',
      value: cma.jv_twin.retail_indication,
      source: `Layer 2 JV-twin: ${cma.jv_twin.address} (JV ratio ${cma.jv_twin.jv_ratio}) sold $${cma.jv_twin.retail_indication.toLocaleString()}`,
    });
  }

  // ── Band arithmetic ───────────────────────────────────────────────────────
  const spreadPct = priors?.confidence === 'HIGH' ? 0.06 : priors?.confidence === 'MEDIUM' ? 0.10 : 0.15;

  const usableClearing = clearingAnchors.filter(a => a.value != null).map(a => a.value);
  const clearingMid    = usableClearing.length
    ? Math.round(usableClearing.reduce((a, b) => a + b, 0) / usableClearing.length)
    : null;

  const usableMarket = marketAnchors.filter(a => a.value != null).map(a => a.value);
  const marketMid    = usableMarket.length
    ? Math.round(usableMarket.reduce((a, b) => a + b, 0) / usableMarket.length)
    : null;

  // Legacy midpoint = market band (used by Shapira formula). Clearing band
  // is surfaced separately for the §2-3 display and §18 scorecard.
  const midpoint = marketMid ?? clearingMid;

  return {
    // Legacy fields (backward compat — used by computeShapiraCeiling)
    anchors: [...clearingAnchors, ...marketAnchors],
    midpoint,
    low:  midpoint != null ? Math.round(midpoint * (1 - spreadPct)) : null,
    high: midpoint != null ? Math.round(midpoint * (1 + spreadPct)) : null,
    // Split bands
    clearing_band: {
      anchors:  clearingAnchors,
      midpoint: clearingMid,
      low:      clearingMid != null ? Math.round(clearingMid * (1 - spreadPct)) : null,
      high:     clearingMid != null ? Math.round(clearingMid * (1 + spreadPct)) : null,
      label:    'Expected Auction Clearing Price',
    },
    market_band: {
      anchors:  marketAnchors,
      midpoint: marketMid,
      low:      marketMid != null ? Math.round(marketMid * (1 - spreadPct)) : null,
      high:     marketMid != null ? Math.round(marketMid * (1 + spreadPct)) : null,
      label:    'Retail ARV (Open Market Exit Value)',
    },
  };
}

// Shapira Max Bid ceiling — county+sale_type-specific RL-fit parameters from
// shapira_formula_params (optimal_bid_pct_of_assessed × plaintiff_discount_factor,
// scaled by the XGBoost sell-probability), not a flat closing-cost buffer.
// Falls back to a conservative default only when no row exists for this
// county/sale_type — never silently reuses another county's fit.
//
// property_type is constrained to [this parcel's dor_uc, "ALL"] — without it,
// ORDER BY sample_size DESC can pick an unrelated property-type row whose
// sample happens to be larger than ALL's (confirmed live for duval/tax_deed:
// property_type='001' carries sample_size=1693 vs ALL's 669, so every Duval
// tax-deed report was silently scored with single-family params regardless
// of the subject's actual type).
async function computeShapiraCeiling(auction, county, arv, sellProb, propertyType, { get }) {
  if (arv == null) return { ceiling: null, floor: null, cap: null, source: null };
  const countySlug = String(county).toLowerCase();
  const saleType = auction.sale_type === 'tax_deed' ? 'tax_deed' : 'foreclosure';
  const propertyTypeFilter = [...new Set([propertyType || 'ALL', 'ALL'])].join(',');

  const rows = await get(
    `shapira_formula_params?county=eq.${countySlug}&sale_type=eq.${saleType}&property_type=in.(${propertyTypeFilter})&select=optimal_bid_pct_of_assessed,bid_floor_pct,bid_ceiling_pct,plaintiff_discount_factor,sample_size,model_version&order=sample_size.desc&limit=1`
  ).catch(() => []);
  const row = rows?.[0];
  const p = row
    ? {
        optimal_bid_pct_of_assessed: Number(row.optimal_bid_pct_of_assessed),
        bid_floor_pct: Number(row.bid_floor_pct),
        bid_ceiling_pct: Number(row.bid_ceiling_pct),
        plaintiff_discount_factor: Number(row.plaintiff_discount_factor),
        sample_size: row.sample_size,
        model_version: row.model_version,
      }
    : { optimal_bid_pct_of_assessed: 0.70, bid_floor_pct: 0.50, bid_ceiling_pct: 0.90, plaintiff_discount_factor: 0.85, sample_size: 0, model_version: 'default (no shapira_formula_params row for this county/sale_type)' };

  // sellProb gates the VERDICT (BID vs REVIEW), not the ceiling price.
  // Compressing the dollar ceiling by sellProb produces absurd results when
  // the model assigns low probability — a property can have strong equity
  // but the formula collapses to an unbiddable number. The pre-sale Marion
  // card (Jul 20, ceiling $82K, actual sale $73.5K, CEILING HELD) was correct
  // precisely because it did NOT use sellProb as a ceiling multiplier.
  const ceiling = Math.round(arv * p.optimal_bid_pct_of_assessed * p.plaintiff_discount_factor);
  const floor = Math.round(arv * p.bid_floor_pct);
  const cap = Math.round(arv * p.bid_ceiling_pct);
  const source = `shapira_formula_params: county=${countySlug} sale_type=${saleType} optimal_bid_pct=${p.optimal_bid_pct_of_assessed} plaintiff_discount=${p.plaintiff_discount_factor} sample_size=${p.sample_size} model=${p.model_version}`;
  return { ceiling, floor, cap, source };
}

async function scoreModel(auction, county, deps) {
  const countyEncoding = await computeCountyTargetEncoding(county, deps).catch(() => null);
  const { byName, v4Array } = buildFeatureVector(auction, countyEncoding);
  try {
    // FIX (issue #19079, Aug 14 2026): pass v4Array (the exact 13 features
    // the deployed V4 model was actually trained on), not the full 21-name
    // reconstructed array - see feature-vector.js for the full story.
    const result = await predictEnsemble(v4Array, deps);
    return {
      available: true,
      ...result,
      feature_vector: byName,
      county_target_enc: countyEncoding,
    };
  } catch (err) {
    // FIX (issue #19079, found during code review): this claimed
    // model_version: 'v14.0' on any scoring failure - but v14.0 is
    // explicitly retired elsewhere in this codebase ("DEAD... Never call
    // it", ensemble-model.js). Nothing v14.0-related ever runs; this was a
    // stale placeholder misrepresenting what was attempted.
    return {
      available: false,
      model_version: null,
      probability_third_party_purchase: 'unavailable — V4 ensemble scoring failed (see error)',
      feature_vector: byName,
      error: err.message,
    };
  }
}

export async function buildReport(auction, { get = defaultGet } = {}) {
  const locatable = !!auction.property_address;
  const county = auction.county;

  // Kicked off unawaited so it overlaps with matchStateParcel below in the
  // locatable path — perf fix for the /report/json timeout (issue: buildReport
  // exceeded the caller's 20s budget). Every downstream await in this function
  // is independent of every other once `match`/`parcel` is resolved, so they
  // are run concurrently via Promise.all rather than serially; this changes
  // wall-clock time only — none of these calls read another's result.
  const priorsPromise = getCountyClearancePriors(county, { get, saleType: auction.sale_type || 'foreclosure' });

  if (!locatable) {
    const priors = await priorsPromise;
    const redFlags = deriveRedFlags(auction);
    const lienSurvival = await classifyLienSurvival(
      { case_number: auction.case_number, parcel_id: auction.parcel_id, sale_type: auction.sale_type },
      { get }
    ).catch(() => ({ available: false, reason: 'classification failed', items: [], n_items: 0, statutory_basis: null }));
    return {
      cover: {
        case_number: auction.case_number,
        county,
        verdict: 'SKIP',
        investment_grade: 'D',
        shapira_max_bid: null,
        entry_bid: null,
        locatable: false,
      },
      value_estimate: null,
      refusal: NO_ESTIMATE_REFUSAL,
      county_stats: priors,
      zoning: await buildZwSection(auction, null, { get }),
      cma: { section_key: 'cma', comps: [], note: 'No comps — subject is unlocatable.' },
      red_flags: redFlags,
      auction_outcome: buildOutcomeSection(auction, { ceiling: null, value: null, entryBid: null }),
      lien_survival: lienSurvival,
      composition: await sectionComposition({ locatable: false, lienSurvival }, { get }),
      provenance: buildProvenance(auction, { model: { available: false } }),
      disclaimer: DISCLAIMER_FULL,
    };
  }

  const [priors, match] = await Promise.all([
    priorsPromise,
    matchStateParcel(county, auction.property_address, { get }),
  ]);
  const parcel = match.matched ? match.parcel : null;
  const [zoning, cma, distressedCma, model] = await Promise.all([
    buildZwSection(auction, match, { get }),
    buildCma(parcel, { get }),
    buildDistressedCma(parcel, auction, { get }),
    scoreModel(auction, county, { get }),
  ]);
  const value = computeValueEstimate(auction, priors, cma, distressedCma);
  const sellProb = typeof model.probability_third_party_purchase === 'number' ? model.probability_third_party_purchase : 0.5;
  const shapira = await computeShapiraCeiling(auction, county, value.midpoint, sellProb, parcel?.dor_uc, { get });
  const ceiling = shapira.ceiling;
  // Entry bid preference: opening_bid (rare — usually null in this feed) >
  // plaintiff_max_bid (the plaintiff's disclosed credit-bid floor, when not
  // hidden) > judgment_amount (conservative fallback when no bid figure is
  // on file at all — this is a worst-case ceiling-vs-bid comparison, not a
  // claim that the opening bid literally equals the judgment).
  const isTaxDeed = (auction.sale_type || '').toLowerCase() === 'tax_deed';
  const entryBid = isTaxDeed
    ? (auction.opening_bid || null)
    : (auction.opening_bid || auction.plaintiff_max_bid || auction.judgment_amount || null);
  const entryBidSource = isTaxDeed
    ? (auction.opening_bid ? 'opening_bid (unpaid taxes + certificate interest + fees)' : 'opening_bid (not on file)')
    : (auction.opening_bid ? 'opening_bid' : auction.plaintiff_max_bid ? 'plaintiff_max_bid (disclosed credit-bid floor)' : 'judgment_amount (no opening bid or plaintiff max bid on file — conservative fallback)');
  const redFlags = deriveRedFlags(auction);

  // A completed sale must never present itself as an actionable bid card.
  // The pre-sale verdict is preserved (it is what §18 grades), but the card
  // carries an explicit completed-auction notice.
  const saleCompleted = String(auction.auction_status || '').toLowerCase() === 'completed'
    || auction.tier1_sold_amount != null || auction.sold_amount != null;
  if (saleCompleted) {
    redFlags.push({ code: 'AUCTION_COMPLETED', severity: 'pending',
      text: `This auction has already completed${auction.auction_date ? ` (${auction.auction_date})` : ''}. The verdict on this card is the model pre-sale call, preserved for grading in the SECTION 18 Outcome Scorecard — do not treat it as an actionable bid recommendation.` });
  }

  // hasHiddenCap: foreclosure-only concept. Tax deeds have no plaintiff.
  const hasHiddenCap = !isTaxDeed && auction.plaintiff_max_bid == null;
  const marginPct = (ceiling != null && entryBid) ? (ceiling - entryBid) / entryBid : null;
  const thinMargin = marginPct != null && marginPct >= 0 && marginPct < 0.10;

  // Third-party probability gate: if model says <25% chance a third party wins,
  // plaintiff is almost certainly credit-bidding it back — suppress BID to REVIEW
  const LOW_3P_PROB = typeof sellProb === 'number' && sellProb < 0.25;

  let verdict = 'SKIP';
  if (ceiling != null && entryBid != null) {
    if (ceiling >= entryBid) verdict = (hasHiddenCap || thinMargin) ? 'BID (conditional)' : 'BID';
    else verdict = marginPct > -0.10 ? 'REVIEW' : 'SKIP';
  }
  // Downgrade BID → REVIEW when third-party probability is too low to justify entry
  if (verdict.startsWith('BID') && LOW_3P_PROB) {
    verdict = 'REVIEW';
    const low3pText = isTaxDeed
      ? `Third-party probability ${Math.round(sellProb * 100)}% — model predicts low competitive interest; county or municipality may take back. Monitor; do not plan to win this lot.`
      : `Third-party probability ${Math.round(sellProb * 100)}% — model predicts plaintiff likely to credit-bid. Monitor; do not plan to win this lot.`;
    redFlags.push({ code: 'LOW_3P_PROBABILITY', severity: 'pending', text: low3pText });
  }
  // Downgrade BID → REVIEW when junior/HOA lien risk detected and lien survival unconfirmed
  if (verdict.startsWith('BID') && hasJuniorLienRisk(redFlags)) {
    verdict = 'REVIEW';
  }

  if (thinMargin && verdict.startsWith('BID')) {
    redFlags.push({ code: 'THIN_MARGIN', severity: 'risk', text: `Ceiling-to-entry margin is ${marginPct != null ? Math.round(marginPct * 100) : '?'}% — thin cushion, size accordingly.` });
  }

  const outcome = buildOutcomeSection(auction, { ceiling, value, entryBid });
  if (outcome.flags?.length) redFlags.push(...outcome.flags);

  const lienSurvival = await classifyLienSurvival(
    { case_number: auction.case_number, parcel_id: parcel?.parcel_id || auction.parcel_id, sale_type: auction.sale_type },
    { get }
  ).catch(() => ({ available: false, reason: 'classification failed', items: [], n_items: 0, statutory_basis: null }));

  return {
    cover: {
      case_number: auction.case_number,
      county,
      property_address: auction.property_address,
      verdict,
      investment_grade: grade(marginPct ?? -1, true),
      // Equity at acquisition (day-one, as-is)
      equity_at_entry_bid: (value.market_band?.midpoint != null && entryBid != null)
        ? Math.round(value.market_band.midpoint - entryBid)
        : null,
      equity_at_ceiling: (value.market_band?.midpoint != null && shapira.ceiling != null)
        ? Math.round(value.market_band.midpoint - shapira.ceiling)
        : null,
      shapira_max_bid: { ...money(ceiling, shapira.source), bid_floor: shapira.floor, bid_ceiling: shapira.cap },
      entry_bid: money(entryBid, entryBidSource),
    },
    value_estimate: value.midpoint == null ? null : {
      // Legacy flat band (backward compat)
      low:      value.low,
      high:     value.high,
      midpoint: Math.round(value.midpoint),
      anchors:  value.anchors,
      // Split bands — use these for display and scoring
      clearing_band: value.clearing_band,
      market_band:   value.market_band,
    },
    county_stats: priors,
    transaction_history: {
      prior_sale_date: auction.prior_sale_date || null,
      prior_sale_price: (auction.prior_sale_price > MIN_PRICE_SIGNAL) ? money(auction.prior_sale_price, 'prior_sale_price') : { value: auction.prior_sale_price ?? null, display: auction.prior_sale_price != null ? 'no price signal (sub-$1,000/quitclaim pattern)' : 'Pending — no prior sale on file', source: 'prior_sale_price' },
    },
    // auction.* (owner-observed docket data) wins when present; falls back to
    // the matched fl_parcels row (state cadastral data) rather than rendering
    // Pending when the auction feed simply never carried the field for this
    // county (Marion property-appraiser enrichment gap, SSOT §5). beds/baths
    // stay Pending on the fallback — fl_parcels has no such columns, and
    // guessing them would be fabrication.
    property_record: {
      property_type: auction.property_type || (parcel?.dor_uc ? `DOR use code ${parcel.dor_uc} (fl_parcels)` : 'Pending — not on file'),
      beds: auction.bedrooms ?? 'Pending',
      baths: auction.bathrooms ?? 'Pending',
      living_area_sqft: auction.living_area_sqft ?? (parcel?.tot_lvg_ar != null ? Number(parcel.tot_lvg_ar) : 'Pending'),
      year_built: auction.year_built ?? (parcel?.act_yr_blt ?? 'Pending'),
      lot_size_acres: auction.lot_size ?? (parcel?.lnd_sqfoot != null ? Number((parcel.lnd_sqfoot / 43560).toFixed(3)) : 'Pending'),
      homestead_status: auction.homestead_status || (parcel?.jv_hmstd != null ? (Number(parcel.jv_hmstd) > 0 ? 'homestead (fl_parcels jv_hmstd>0)' : 'non-homestead (fl_parcels jv_hmstd=0)') : 'Pending'),
    },
    auction_listing: isTaxDeed ? {
      // §1 TAX DEED — no plaintiff, no judgment
      case_number:            auction.case_number,
      auction_date:           auction.auction_date,
      assessed_value:         money(auction.assessed_value, 'assessed_value'),
      taxing_authority:       auction.plaintiff || 'Pending — taxing authority not on file',
      unpaid_taxes:           money(auction.opening_bid, 'opening_bid (unpaid taxes + certificate interest + fees)'),
      irs_lien_risk:          'IRS federal tax liens survive FL tax deed sales — independent IRS lien search required (26 U.S.C. § 7425)',
      hoa_lien_risk:          'HOA/COA liens may survive or re-attach (FL FS 720.3085 / 718.116) — confirm outstanding balance',
      statutory_basis:        'FL FS 197.502 / 197.552 / 197.582',
    } : {
      // §1 FORECLOSURE — standard fields
      case_number: auction.case_number,
      auction_date: auction.auction_date,
      plaintiff: auction.plaintiff || 'Pending — not on file',
      judgment_amount: money(auction.judgment_amount, 'judgment_amount'),
      plaintiff_max_bid: hiddenOr(auction.plaintiff_max_bid, auction.plaintiff_max_bid_source || 'plaintiff_max_bid (docket)'),
      assessed_value: money(auction.assessed_value, 'assessed_value'),
    },
    context_layers: {
      ml_model: model,
    },
    zoning,
    cma,
    cma_distressed: distressedCma,
    opinion_of_price_bid_card: {
      entry_bid: entryBid,
      shapira_ceiling: ceiling,
      value_midpoint: value.midpoint,
      verdict,
    },
    judgment: isTaxDeed ? {
      sale_type_note:           'Tax deed sale — no foreclosure judgment.',
      unpaid_taxes:             auction.opening_bid,
      irs_lien_survives:        true,
      hoa_lien_may_survive:     true,
      statutory_extinguishment: 'FL FS 197.552 extinguishes most state/county liens; does NOT extinguish federal liens or HOA liens under FL FS 720/718',
    } : {
      judgment_amount: auction.judgment_amount,
      opening_bid: auction.opening_bid,
      bid_to_judgment_ratio: (auction.opening_bid && auction.judgment_amount) ? Number((auction.opening_bid / auction.judgment_amount).toFixed(3)) : null,
    },
    red_flags: redFlags,
    auction_outcome: outcome,
    lien_survival: lienSurvival,
    composition: await sectionComposition({ locatable: true, lienSurvival }, { get }),
    provenance: buildProvenance(auction, { model }),
    disclaimer: DISCLAIMER_FULL,
  };
}

// Maps to public.biddeed_report_composition's 6 canonical section keys.
// FIX (ship-gate bypass, known bug since Aug 1 — this issue): lien_search,
// lien_survival, and title_search now actually read
// biddeed_report_composition.ship_status before claiming to deliver content
// to a paying customer. auction_intel/zoning/deal_score are UNCHANGED —
// they are not in scope for this gate (see issue: only lien_search/
// title_search/lien_survival are named) and already ship today.
// Any of the three title/lien tiers still ship_status='blocked' renders as
// internal-preview-only — the real classify() output is always computed
// (see report.lien_survival) so it's available for internal QA/tests, but
// it is never surfaced as 'delivered' status to a customer response until a
// human flips ship_status in Supabase.
async function sectionComposition({ locatable, lienSurvival }, { get = defaultGet } = {}) {
  const gateRows = await get(
    'biddeed_report_composition?section_key=in.(lien_search,lien_survival,title_search)&select=section_key,ship_status,disclosure_text'
  ).catch(() => []);
  const gates = Object.fromEntries((gateRows || []).map(r => [r.section_key, r]));

  const isLive = (key) => gates[key]?.ship_status === 'live';

  const lienSearch = isLive('lien_search')
    ? { section_key: 'lien_search', status: 'delivered', disclosure: gates.lien_search.disclosure_text }
    : { section_key: 'lien_search', status: `Pending — Title Tier 1 (lien search) internal-preview-only, not yet shipped to customers (ship_status=${gates.lien_search?.ship_status || 'unknown'})` };

  const titleSearch = isLive('title_search')
    ? { section_key: 'title_search', status: 'delivered', disclosure: gates.title_search.disclosure_text }
    : { section_key: 'title_search', status: `Pending — Title Tier 3 (title search) internal-preview-only, not yet shipped to customers (ship_status=${gates.title_search?.ship_status || 'unknown'})` };

  let lienSurvivalStatus;
  if (!isLive('lien_survival')) {
    lienSurvivalStatus = { section_key: 'lien_survival', status: `Pending — Title Tier 2 (lien survival, Fla. Stat. §197.552/§713.07) internal-preview-only, not yet shipped to customers (ship_status=${gates.lien_survival?.ship_status || 'unknown'})` };
  } else if (!lienSurvival?.available) {
    lienSurvivalStatus = { section_key: 'lien_survival', status: `Pending — insufficient recorded-document coverage for this county (${lienSurvival?.reason || 'no data on file'})` };
  } else {
    lienSurvivalStatus = { section_key: 'lien_survival', status: 'delivered', disclosure: gates.lien_survival.disclosure_text };
  }

  return {
    auction_intel: { section_key: 'auction_intel', status: locatable ? 'delivered' : 'refused (unlocatable subject)' },
    zoning: { section_key: 'zoning', status: 'delivered (see SECTION ZW)' },
    lien_search: lienSearch,
    lien_survival: lienSurvivalStatus,
    title_search: titleSearch,
    deal_score: { section_key: 'deal_score', status: locatable ? 'delivered' : 'refused (unlocatable subject)' },
  };
}

function buildProvenance(auction, { model }) {
  const available = model?.available === true;
  // FIX (issue #19079, Aug 14 2026, found during code review): this used
  // to check model?.ensemble === true, but neither runModal() nor
  // runPureJsV4() in ensemble-model.js ever set an `ensemble` field on
  // their return value - method is 'v4_pkl_modal' or 'v4_pure_js_fallback'
  // instead. That made this branch permanently dead code: every real V4
  // score (Modal or JS fallback) fell through to the wrong disclosure text
  // below, which claims "a single XGBoost v14.0 classifier" ran even when
  // the real V4 stacked ensemble genuinely scored the report. available
  // alone is the correct signal - it's true only when predictEnsemble()
  // actually succeeded via either real path.
  const ensemble = available;
  const isTaxDeed = (auction.sale_type || '').toLowerCase() === 'tax_deed';

  let modelDisclosure;
  if (!available) {
    modelDisclosure = 'Verdict/value-estimate math is a deterministic prior/anchor framework, NOT an ML model. The v14.0 XGBoost artifact was not available at scoring time for this call — no probability is rendered (see context_layers.ml_model).';
  } else if (ensemble) {
    // FIX (issue #19079): disclosure now reflects which path actually ran
    // (model.method), instead of a hardcoded claim that was already wrong
    // before today's fix (referenced "XGBoost v14.0" and "approximated via
    // XGBoost weighting" - neither matches what ensemble-model.js does).
    modelDisclosure = model.method === 'v4_pkl_modal'
      ? `Verdict/value-estimate math is a deterministic prior/anchor framework (county clearance priors + prior sale + judgment ratio), NOT the ML model. This is informational, not the deal verdict driver.

ML Stack: SUMMIT-B V4 Stacked Ensemble (Patent Claim 8), model_version=${model.model_version}. Ran on the primary path: XGBoost + LightGBM + CatBoost base learners, Random Forest meta-learner, native Python inference on Modal (ensemble.pkl). Ensemble AUC: ${model.auc}.`
      : `Verdict/value-estimate math is a deterministic prior/anchor framework (county clearance priors + prior sale + judgment ratio), NOT the ML model. This is informational, not the deal verdict driver.

ML Stack: SUMMIT-B V4 Stacked Ensemble (Patent Claim 8), model_version=${model.model_version}. Modal primary path unavailable for this call - ran on the pure-JS fallback: XGBoost + LightGBM base learners only (CatBoost/RF meta-learner require the Python pickle, not available in this runtime), simple average in place of the meta-learner. AUC ${model.auc} (fallback, vs ${model.auc ? model.auc : '0.9468'} for the full Modal ensemble).`;
  } else {
    modelDisclosure = isTaxDeed
      ? 'Verdict/value-estimate math uses county tax-deed clearance priors + prior sale anchors. Judgment ratio anchor NOT used (tax deed — no FJ). Third-party purchase probability is directional; tax deeds have different buyer dynamics than foreclosures.'
      : 'Verdict/value-estimate math is a deterministic prior/anchor framework (county clearance priors + prior sale + judgment ratio), NOT the ML model. A single XGBoost v14.0 classifier additionally scores third-party-purchase probability as a directional signal in context_layers.ml_model — this is informational, not the deal verdict driver.';
  }

  return {
    section: 17,
    title: 'Provenance & Methodology',
    generated_from: 'multi_county_auctions (live), fl_parcels (live), zoning_assignments (live), shapira_models (Supabase — V4 stacked ensemble when in production, v14.0 XGBoost fallback otherwise)',
    model_disclosure: modelDisclosure,
    certification_disclosure: 'Delivered under Gold Standard certification gating (v_certified_counties) — this report tool is CERT_REQUIRED and will refuse an uncertified county before any charge is made.',
    kpi_coverage: null, // populated by caller once composed against zonewise_kpis (298 total) — see issue report for the disclosed approximation
    generated_at_field: 'stamped by caller at response time (composer.js is deterministic and takes no wall-clock dependency of its own)',
  };
}
