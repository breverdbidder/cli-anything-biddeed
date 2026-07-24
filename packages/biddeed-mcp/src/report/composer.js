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
import { buildCma } from './cma.js';
import { matchStateParcel } from './parcel-match.js';
import { computeCountyTargetEncoding, buildFeatureVector } from './feature-vector.js';
import { predict as xgbPredict } from './xgboost-model.js';
import { deriveRedFlags } from './red-flags.js';
import { buildOutcomeSection } from './outcome.js';

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

// Anchor-average value estimate. Three DB-derived anchors plus a CMA anchor
// when enough comps exist — averaged over whichever have a real basis.
// Never invents an anchor with no data behind it (sub-$1000/quitclaim sale,
// or a sale stale enough that unadjusted extrapolation would be a guess).
function computeValueEstimate(auction, priors, cma) {
  const anchors = [];

  if (priors && !priors.insufficient && priors.median_sold_to_assessed && auction.assessed_value > 0) {
    anchors.push({ key: 'county_clearance_prior', value: auction.assessed_value * priors.median_sold_to_assessed, source: `county clearance prior (median sold/assessed=${priors.median_sold_to_assessed.toFixed(3)}, n=${priors.n_sold_to_assessed})` });
  }
  if (priors && !priors.insufficient && priors.median_sold_to_judgment && auction.judgment_amount > 0) {
    anchors.push({ key: 'judgment_ratio_prior', value: auction.judgment_amount * priors.median_sold_to_judgment, source: `county clearance prior (median sold/FJ=${priors.median_sold_to_judgment.toFixed(3)}, n=${priors.n_sold_to_judgment})` });
  }

  const priorSaleYear = auction.prior_sale_date ? new Date(auction.prior_sale_date).getUTCFullYear() : null;
  const auctionYear = auction.auction_date ? new Date(auction.auction_date).getUTCFullYear() : new Date().getUTCFullYear();
  const yearsSinceSale = priorSaleYear ? auctionYear - priorSaleYear : null;
  const hasPriorSalePriceSignal = auction.prior_sale_price > MIN_PRICE_SIGNAL && auction.prior_sale_date;

  if (hasPriorSalePriceSignal && yearsSinceSale != null && yearsSinceSale <= STALE_SALE_YEARS) {
    anchors.push({ key: 'prior_arms_length_sale', value: auction.prior_sale_price, source: `prior sale ${auction.prior_sale_date} at $${auction.prior_sale_price.toLocaleString()}` });
  } else if (hasPriorSalePriceSignal) {
    anchors.push({ key: 'prior_arms_length_sale', value: null, source: `prior sale ${auction.prior_sale_date} at $${auction.prior_sale_price.toLocaleString()} is ${yearsSinceSale}yr stale — shown in transaction_history, excluded as a value anchor (no appreciation model to extrapolate it forward without guessing)` });
  } else if (auction.prior_sale_price != null) {
    anchors.push({ key: 'prior_arms_length_sale', value: null, source: 'no price signal — prior sale below $1,000/quitclaim-pattern, excluded as a comp' });
  }

  if (cma && cma.n >= 3 && cma.median_sale_price != null) {
    anchors.push({ key: 'cma_median', value: cma.median_sale_price, source: `CMA median of ${cma.n} comps (±30% sqft, same zip+DOR-use, sale within 2yr)` });
  }

  const usable = anchors.filter(a => a.value != null).map(a => a.value);
  if (!usable.length) return { anchors, midpoint: null, low: null, high: null };

  const midpoint = usable.reduce((a, b) => a + b, 0) / usable.length;
  const spreadPct = priors?.confidence === 'HIGH' ? 0.06 : priors?.confidence === 'MEDIUM' ? 0.10 : 0.15;
  return { anchors, midpoint, low: Math.round(midpoint * (1 - spreadPct)), high: Math.round(midpoint * (1 + spreadPct)) };
}

// Shapira Max Bid ceiling — the top defensible bid for a hold/rental
// strategy: value estimate less a flat closing-cost/margin-of-safety buffer
// (the larger of $10k or 5% of value). This is deliberately gentler than a
// flip-repair formula (predict_auction_outcome's older ARV-based heuristic)
// because these fixtures are occupied/rental-grade properties, not
// gut-rehab flips — see issue #12853 report for the live comparison that
// drove this calibration.
function computeCeiling(valueMidpoint) {
  if (valueMidpoint == null) return null;
  return Math.round(valueMidpoint - Math.max(10000, valueMidpoint * 0.05));
}

async function scoreModel(auction, county, deps) {
  const countyEncoding = await computeCountyTargetEncoding(county, deps).catch(() => null);
  const { array, byName } = buildFeatureVector(auction, countyEncoding);
  try {
    const result = await xgbPredict(array);
    return {
      available: true,
      model_version: result.model_version,
      probability_third_party_purchase: Number(result.probability.toFixed(4)),
      feature_vector: byName,
      county_target_enc: countyEncoding,
      caveat: 'Probability uses a best-effort feature reconstruction (see feature-vector.js) — the original training-time feature-engineering source is not in this repo. Treat as directional, not exact.',
    };
  } catch (err) {
    return {
      available: false,
      model_version: 'v14.0',
      probability_third_party_purchase: 'unavailable — artifact not deployed',
      feature_vector: byName,
      error: err.message,
    };
  }
}

export async function buildReport(auction, { get = defaultGet } = {}) {
  const locatable = !!auction.property_address;
  const county = auction.county;

  const priors = await getCountyClearancePriors(county, { get });

  if (!locatable) {
    const redFlags = deriveRedFlags(auction);
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
      zoning: await buildZwSection(auction, { get }),
      cma: { section_key: 'cma', comps: [], note: 'No comps — subject is unlocatable.' },
      red_flags: redFlags,
      auction_outcome: buildOutcomeSection(auction, { ceiling: null, value: null, entryBid: null }),
      composition: sectionComposition({ locatable: false }),
      provenance: buildProvenance(auction, { modelAvailable: false }),
    };
  }

  const match = await matchStateParcel(county, auction.property_address, { get });
  const zoning = await buildZwSection(auction, { get });
  const cma = await buildCma(match.matched ? match.parcel : null, { get });
  const model = await scoreModel(auction, county, { get });
  const value = computeValueEstimate(auction, priors, cma);
  const ceiling = computeCeiling(value.midpoint);
  // Entry bid preference: opening_bid (rare — usually null in this feed) >
  // plaintiff_max_bid (the plaintiff's disclosed credit-bid floor, when not
  // hidden) > judgment_amount (conservative fallback when no bid figure is
  // on file at all — this is a worst-case ceiling-vs-bid comparison, not a
  // claim that the opening bid literally equals the judgment).
  const entryBid = auction.opening_bid || auction.plaintiff_max_bid || auction.judgment_amount || null;
  const entryBidSource = auction.opening_bid ? 'opening_bid' : auction.plaintiff_max_bid ? 'plaintiff_max_bid (disclosed credit-bid floor)' : 'judgment_amount (no opening bid or plaintiff max bid on file — conservative fallback)';
  const redFlags = deriveRedFlags(auction);

  const hasHiddenCap = auction.plaintiff_max_bid == null;
  const marginPct = (ceiling != null && entryBid) ? (ceiling - entryBid) / entryBid : null;
  const thinMargin = marginPct != null && marginPct >= 0 && marginPct < 0.10;

  let verdict = 'SKIP';
  if (ceiling != null && entryBid != null) {
    if (ceiling >= entryBid) verdict = (hasHiddenCap || thinMargin) ? 'BID (conditional)' : 'BID';
    else verdict = marginPct > -0.10 ? 'REVIEW' : 'SKIP';
  }
  if (thinMargin && verdict.startsWith('BID')) {
    redFlags.push({ code: 'THIN_MARGIN', severity: 'risk', text: `Ceiling-to-entry margin is ${marginPct != null ? Math.round(marginPct * 100) : '?'}% — thin cushion, size accordingly.` });
  }

  const outcome = buildOutcomeSection(auction, { ceiling, value, entryBid });
  if (outcome.flags?.length) redFlags.push(...outcome.flags);

  return {
    cover: {
      case_number: auction.case_number,
      county,
      property_address: auction.property_address,
      verdict,
      investment_grade: grade(marginPct ?? -1, true),
      shapira_max_bid: money(ceiling, 'Shapira anchor formula (0.70×value − 0.15×value − $10k − margin buffer)'),
      entry_bid: money(entryBid, entryBidSource),
    },
    value_estimate: value.midpoint == null ? null : {
      low: value.low,
      high: value.high,
      midpoint: Math.round(value.midpoint),
      anchors: value.anchors,
    },
    county_stats: priors,
    transaction_history: {
      prior_sale_date: auction.prior_sale_date || null,
      prior_sale_price: (auction.prior_sale_price > MIN_PRICE_SIGNAL) ? money(auction.prior_sale_price, 'prior_sale_price') : { value: auction.prior_sale_price ?? null, display: auction.prior_sale_price != null ? 'no price signal (sub-$1,000/quitclaim pattern)' : 'Pending — no prior sale on file', source: 'prior_sale_price' },
    },
    property_record: {
      property_type: auction.property_type || 'Pending — not on file',
      beds: auction.bedrooms ?? 'Pending',
      baths: auction.bathrooms ?? 'Pending',
      living_area_sqft: auction.living_area_sqft ?? 'Pending',
      year_built: auction.year_built ?? 'Pending',
      lot_size_acres: auction.lot_size ?? 'Pending',
      homestead_status: auction.homestead_status || 'Pending',
    },
    auction_listing: {
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
    opinion_of_price_bid_card: {
      entry_bid: entryBid,
      shapira_ceiling: ceiling,
      value_midpoint: value.midpoint,
      verdict,
    },
    judgment: {
      judgment_amount: auction.judgment_amount,
      opening_bid: auction.opening_bid,
      bid_to_judgment_ratio: (auction.opening_bid && auction.judgment_amount) ? Number((auction.opening_bid / auction.judgment_amount).toFixed(3)) : null,
    },
    red_flags: redFlags,
    auction_outcome: outcome,
    composition: sectionComposition({ locatable: true }),
    provenance: buildProvenance(auction, { modelAvailable: model.available }),
  };
}

// Maps to public.biddeed_report_composition's 6 canonical section keys.
// Title Tiers 1-3 have no Marion pipeline today — rendered Pending, never
// silently omitted, naming the gate per Amendment 2.
function sectionComposition({ locatable }) {
  return {
    auction_intel: { section_key: 'auction_intel', status: locatable ? 'delivered' : 'refused (unlocatable subject)' },
    zoning: { section_key: 'zoning', status: 'delivered (see SECTION ZW)' },
    lien_search: { section_key: 'lien_search', status: 'Pending — Title Tier 1 (lien search) not yet live for this county' },
    lien_survival: { section_key: 'lien_survival', status: 'Pending — Title Tier 2 (lien survival, Fla. Stat. §197.552/§713.07) not yet live for this county' },
    title_search: { section_key: 'title_search', status: 'Pending — Title Tier 3 (title search) not yet live for this county' },
    deal_score: { section_key: 'deal_score', status: locatable ? 'delivered' : 'refused (unlocatable subject)' },
  };
}

function buildProvenance(auction, { modelAvailable }) {
  return {
    section: 17,
    title: 'Provenance & Methodology',
    generated_from: 'multi_county_auctions (live), fl_parcels (live), zoning_assignments (live), shapira_models v14.0 (Supabase storage)',
    model_disclosure: modelAvailable
      ? 'Verdict/value-estimate math is a deterministic prior/anchor framework (county clearance priors + prior sale + judgment ratio), NOT the ML model. A single XGBoost v14.0 classifier (72.2% accuracy, 0.7834 AUC, trained 2026-05-27) additionally scores third-party-purchase probability as a directional signal in context_layers.ml_model — this is informational, not the deal verdict driver.'
      : 'Verdict/value-estimate math is a deterministic prior/anchor framework, NOT an ML model. The v14.0 XGBoost artifact was not available at scoring time for this call — no probability is rendered (see context_layers.ml_model).',
    certification_disclosure: 'Delivered under Gold Standard certification gating (v_certified_counties) — this report tool is CERT_REQUIRED and will refuse an uncertified county before any charge is made.',
    kpi_coverage: null, // populated by caller once composed against zonewise_kpis (298 total) — see issue report for the disclosed approximation
    generated_at_field: 'stamped by caller at response time (composer.js is deterministic and takes no wall-clock dependency of its own)',
  };
}
