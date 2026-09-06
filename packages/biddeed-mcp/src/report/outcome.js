// GTM-22 S5 REPORT ENGINE — SECTION 18: Auction Outcome & Prediction Scorecard.
//
// The closing half of the $25 report. A pre-sale report states a Shapira Max
// Bid and a value band; this section states what the room actually did, and
// scores the call against it. Buyers of a pre-sale report are re-issued the
// report once this section can be populated.
//
// Honesty rules (same contract as the rest of the engine):
//   - An uncaptured outcome renders "Pending — <named reason>", never $0,
//     never omitted, and never inferred from the opening bid.
//   - The scorecard grades the report's OWN prior call. A ceiling that was
//     exceeded is reported as a correct walk-away, not hidden as a miss.
//   - Buyer type is only stated when a source captured it. The v14.0 model
//     targets third-party purchase; scoring that target against an unknown
//     buyer type would be circular, so it is withheld rather than guessed.
//   - No field here is model-generated. Every figure traces to a captured
//     source row with its source named.

const PENDING_REASON =
  'outcome not captured — the post-sale result loop has not written sold_amount/winning_bidder for this auction';

// Terminal statuses where no sale occurred by design (the auction was
// resolved without a bid, not merely "not yet captured"). Rendering these as
// "Pending — outcome not captured" implies the post-sale loop simply hasn't
// run yet, which is false and misleading — the outcome IS known, it's just
// not a sale. Vocabulary sourced from tier1_sale_status values already
// written by the harvest pipeline (see scripts/shard9_run651_b_outcomes.py,
// scripts/gold_standard_miami_dade_20260902_c_null_parity_triage.py).
const TERMINAL_NO_SALE_STATUSES = new Set([
  'CANCELED', 'CANCELLED', 'CANCELED_PER_ORDER', 'CANCELED_PER_BANKRUPTCY',
  'DISMISSED', 'JUDGMENT_VACATED', 'REDEEMED', 'WITHDRAWN',
]);

function resolveTerminalNoSale(auction) {
  const status = (auction.tier1_sale_status || '').toUpperCase();
  return TERMINAL_NO_SALE_STATUSES.has(status) ? status : null;
}

function money(value, source) {
  if (value == null) return { value: null, display: 'Pending — not captured', source };
  return { value, display: `$${Number(value).toLocaleString()}`, source };
}

function pct(n) {
  return n == null ? null : Number((n * 100).toFixed(1));
}

// Resolve the sale price from the most authoritative source available.
// tier1_* is platform-verified; sold_amount is the general scrape lane.
function resolveSale(auction) {
  if (auction.tier1_sold_amount != null) {
    return {
      amount: Number(auction.tier1_sold_amount),
      source: `tier1 verified${auction.tier1_verified_at ? ` ${auction.tier1_verified_at}` : ''}`,
      authoritative: true,
    };
  }
  if (auction.sold_amount != null) {
    return {
      amount: Number(auction.sold_amount),
      source: auction.sold_amount_source || 'sold_amount (scrape lane)',
      authoritative: false,
    };
  }
  return { amount: null, source: null, authoritative: false };
}

function resolveBuyerType(auction) {
  const raw = auction.tier1_buyer_type || null;
  if (raw) return { value: raw, source: 'tier1_buyer_type', display: raw };
  if (auction.winning_bidder) {
    return {
      value: null,
      source: auction.winning_bidder_source || 'winning_bidder',
      display: `Winner recorded (${auction.winning_bidder}) — buyer type not classified`,
    };
  }
  return { value: null, source: null, display: 'Pending — buyer type not captured' };
}

/**
 * Grades the pre-sale call against the realised sale.
 *
 * ceiling_call semantics — both outcomes are legitimate and are reported
 * plainly:
 *   sale <= ceiling  -> "ceiling held": a bidder disciplined to the Shapira
 *                       Max Bid could have taken the property at or under it.
 *   sale >  ceiling  -> "walked correctly": the lot cleared above our ceiling,
 *                       so the report's instruction to walk away prevented an
 *                       overpay. Not a miss.
 */
function scorePrediction({ sale, ceiling, valueLow, valueHigh, valueMidpoint, entryBid, terminalNoSale }) {
  if (sale == null) {
    return {
      available: false,
      note: terminalNoSale
        ? `Scorecard withheld — no sale occurred (tier1_sale_status=${terminalNoSale}); nothing to grade the pre-sale call against.`
        : `Scorecard withheld — ${PENDING_REASON}.`,
    };
  }

  const card = { available: true };

  if (ceiling != null) {
    const held = sale <= ceiling;
    card.ceiling_call = {
      shapira_max_bid: ceiling,
      sale,
      verdict: held ? 'ceiling held' : 'walked correctly',
      headroom: held ? ceiling - sale : null,
      overshoot: held ? null : sale - ceiling,
      text: held
        ? `Sale cleared at $${sale.toLocaleString()}, $${(ceiling - sale).toLocaleString()} under the $${ceiling.toLocaleString()} Shapira Max Bid — a bidder holding to the ceiling wins this lot.`
        : `Sale cleared at $${sale.toLocaleString()}, $${(sale - ceiling).toLocaleString()} above the $${ceiling.toLocaleString()} Shapira Max Bid — the report's walk-away instruction prevented an overpay of that amount.`,
    };
  }

  if (valueLow != null && valueHigh != null) {
    const within = sale >= valueLow && sale <= valueHigh;
    card.value_band_call = {
      band: [valueLow, valueHigh],
      sale,
      verdict: within ? 'within band' : sale < valueLow ? 'below band' : 'above band',
      error_vs_midpoint_pct: valueMidpoint ? pct((sale - valueMidpoint) / valueMidpoint) : null,
    };
  }

  if (entryBid != null && entryBid > 0) {
    card.clearing_multiple = Number((sale / entryBid).toFixed(3));
  }

  return card;
}

export function buildOutcomeSection(auction, { ceiling = null, value = null, entryBid = null } = {}) {
  const today = new Date().toISOString().slice(0, 10);
  const auctionDate = auction.auction_date || null;
  const isPast = auctionDate != null && auctionDate < today;

  const sale = resolveSale(auction);
  const buyer = resolveBuyerType(auction);
  const terminalNoSale = resolveTerminalNoSale(auction);

  const captured = sale.amount != null;
  let status;
  if (!auctionDate) status = 'Pending — no auction date on file';
  else if (!isPast) status = `Scheduled — sale has not yet occurred (${auctionDate})`;
  else if (captured) status = 'Captured';
  else if (terminalNoSale) status = `Canceled — no sale occurred (tier1_sale_status=${terminalNoSale})`;
  else status = `Pending — ${PENDING_REASON}`;

  // A past-dated auction still flagged 'upcoming' is a pipeline defect, not a
  // property fact. Surface it rather than letting the stale status imply the
  // sale never happened.
  const staleStatusFlag = (isPast && auction.auction_status === 'upcoming')
    ? {
        code: 'STALE_AUCTION_STATUS',
        severity: 'risk',
        text: `Row still carries auction_status='upcoming' although the sale date (${auctionDate}) has passed — the post-sale result loop did not reconcile this auction. Treat any downstream county clearance prior built from this county as incomplete.`,
      }
    : null;

  return {
    section: 18,
    section_key: 'auction_outcome',
    title: 'Auction Outcome & Prediction Scorecard',
    status,
    outcome_captured: captured,
    auction_date: auctionDate,
    auction_status_field: auction.auction_status ?? null,
    sale_price: money(sale.amount, sale.source),
    sale_price_authoritative: sale.authoritative,
    sale_result_date: auction.sale_result_date ?? null,
    winning_bidder: auction.winning_bidder ?? null,
    buyer_type: buyer,
    tier1_sale_status: auction.tier1_sale_status ?? null,
    terminal_no_sale: terminalNoSale,
    scorecard: scorePrediction({
      sale: sale.amount,
      ceiling,
      valueLow: value?.low ?? null,
      valueHigh: value?.high ?? null,
      valueMidpoint: value?.midpoint ?? null,
      entryBid,
      terminalNoSale,
    }),
    model_target_note:
      buyer.value == null
        ? 'The v14.0 classifier targets third-party purchase. Buyer type is not captured for this lot, so the model target cannot be scored — withheld rather than inferred.'
        : `Buyer type captured as "${buyer.value}" — this lot is a usable training label for the third-party-purchase target.`,
    reissue_policy:
      'Buyers of the pre-sale edition of this report are re-issued the report with this section populated once the outcome is captured. No additional charge.',
    flags: staleStatusFlag ? [staleStatusFlag] : [],
  };
}
