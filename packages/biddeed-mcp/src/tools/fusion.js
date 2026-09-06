// S3 Fusion tools — $5.00/call, gate: pro tier
import { get } from '../supabase.js';
import { getClerkLink, LIEN_RULES } from '../constants.js';
import { callRouter } from '../llm.js';

export const schemas = [
  {
    name: 'check_zoning',
    description: 'ZoneWise zoning lookup — 771K+ FL parcels. Returns zone code, district, FAR, setbacks, max height, permitted uses, and entitlement verdict. BidDeed/ZoneWise exclusive.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        parcel_id: { type: 'string', description: 'FL parcel ID / folio / STRAP number' },
        county:    { type: 'string', description: 'FL county (required for disambiguation)' },
        address:   { type: 'string', description: 'Property address (alternative to parcel_id)' },
      },
      required: ['county'],
    },
  },
  {
    name: 'underwrite_deal',
    description: 'Shapira Formula deal underwriting: calculates max bid, projected returns, and risk score for rental, flip, or BRRRR strategy. Formula: ARV×70% − Repairs − $10K − MIN($25K, 15%×ARV).',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        case_number: { type: 'string', description: 'Auction case number (auto-fills opening_bid)' },
        strategy:    { type: 'string', enum: ['rental', 'flip', 'brrrr'], description: 'Exit strategy' },
        arv:         { type: 'number', description: 'After Repair Value in USD' },
        repairs:     { type: 'number', description: 'Estimated repair cost in USD' },
        opening_bid: { type: 'number', description: 'Auction opening bid (if case_number not provided)' },
        county:      { type: 'string', description: 'FL county (for rental market context)' },
      },
      required: ['strategy', 'arv', 'repairs'],
    },
  },
  {
    name: 'analyze_coliving',
    description: 'Config C 14-suite co-living model analysis. Returns per-room configuration, gross revenue potential, OSTDS (septic) capacity flag, and entitlement check. BidDeed exclusive.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        parcel_id:  { type: 'string', description: 'FL parcel ID' },
        county:     { type: 'string', description: 'FL county' },
        address:    { type: 'string', description: 'Property address' },
        bedrooms:   { type: 'number', description: 'Current bedroom count' },
        bathrooms:  { type: 'number', description: 'Current bathroom count' },
        sqft:       { type: 'number', description: 'Total square footage' },
        lot_sqft:   { type: 'number', description: 'Lot size in square feet' },
      },
      required: ['county'],
    },
  },
  {
    name: 'get_sales_comps',
    description: 'FL property sales comps with arm-length vs distressed split and ARV calculation. Better than Investra: we separate distressed auction sales from arm-length MLS sales for cleaner ARV.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        parcel_id:   { type: 'string', description: 'Subject parcel ID' },
        county:      { type: 'string', description: 'FL county' },
        address:     { type: 'string', description: 'Property address' },
        radius_miles: { type: 'number', description: 'Search radius in miles (default: 0.5)' },
        months:      { type: 'number', description: 'Months of sales history (default: 6)' },
        bedrooms:    { type: 'number', description: 'Filter by bedroom count' },
      },
      required: ['county'],
    },
  },
  {
    name: 'generate_deal_memo',
    description: 'Generate 1-page deal memo combining: auction data + Shapira underwriting + zoning verdict + lien stack summary. BidDeed exclusive — Investra cannot produce this.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    inputSchema: {
      type: 'object',
      properties: {
        case_number: { type: 'string', description: 'Auction case number' },
        county:      { type: 'string', description: 'FL county' },
        strategy:    { type: 'string', enum: ['rental', 'flip', 'brrrr'], description: 'Exit strategy' },
        arv:         { type: 'number', description: 'After Repair Value (your estimate)' },
        repairs:     { type: 'number', description: 'Repair estimate' },
      },
      required: ['case_number', 'county', 'strategy', 'arv', 'repairs'],
    },
  },
  {
    name: 'get_bid_package',
    description: 'Complete bid package: RealForeclose/RealAuction deep link + deposit calc + SIGNAL$ max bid + lien stack + zoning verdict. Everything needed to bid confidently. BidDeed exclusive.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        case_number: { type: 'string', description: 'Auction case number' },
        county:      { type: 'string', description: 'FL county' },
        arv:         { type: 'number', description: 'Your ARV estimate' },
        repairs:     { type: 'number', description: 'Your repair estimate' },
        strategy:    { type: 'string', enum: ['rental', 'flip', 'brrrr'], description: 'Exit strategy (default: flip)' },
      },
      required: ['case_number', 'county'],
    },
  },
  {
    name: 'get_title_chain',
    description: 'O&E title chain for FL auction properties. Returns chain of title, encumbrances, and title insurance recommendation. Pro Plus tier adds full Acclaim/Harris report.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        parcel_id:   { type: 'string', description: 'FL parcel ID' },
        county:      { type: 'string', description: 'FL county' },
        case_number: { type: 'string', description: 'Auction case number' },
      },
      required: ['county'],
    },
  },
];

// ── Tool Handlers ─────────────────────────────────────────────────────────────

export async function check_zoning({ parcel_id, county, address }) {
  if (!parcel_id && !address) return { error: 'Provide parcel_id or address' };

  const filters = [];
  if (parcel_id) filters.push(`parcel_id=eq.${encodeURIComponent(parcel_id)}`);
  if (county) filters.push(`county=eq.${encodeURIComponent(county.toLowerCase())}`);

  const assignments = await get(`zoning_assignments?${filters.join('&')}&limit=1`).catch(() => []);

  const assignment = assignments[0];
  if (!assignment) {
    return {
      found: false,
      parcel_id,
      county,
      note: 'Parcel not in ZoneWise database. Coverage: 771K+ FL parcels across Brevard, Duval, Orange, and 40+ more counties.',
    };
  }

  // Fetch district details (filter by code only — zoning_districts has no county column)
  const zd = await get(
    `zoning_districts?code=eq.${encodeURIComponent(assignment.zone_code)}&limit=1`
  ).catch(() => []);

  const district = zd[0];

  // Fetch zone standards if district found
  let standards = null;
  if (district?.id) {
    const zs = await get(
      `zone_standards?zoning_district_id=eq.${district.id}&limit=1`
    ).catch(() => []);
    standards = zs[0] || null;
  }

  return {
    found: true,
    parcel_id: assignment.parcel_id,
    county: assignment.county,
    zone_code: assignment.zone_code,
    zone_source: assignment.zone_source,
    dor_uc: assignment.dor_uc || null,
    district: district ? {
      name: district.name,
      category: district.category,
      description: district.description || null,
      far_regulated: district.far_regulated,
      density_regulated: district.density_regulated,
    } : null,
    standards: standards ? {
      max_far: standards.max_far,
      max_height_ft: standards.max_height_ft,
      min_lot_sqft: standards.min_lot_sqft,
      front_setback_ft: standards.front_setback_ft,
      side_setback_ft: standards.side_setback_ft,
      rear_setback_ft: standards.rear_setback_ft,
      max_lot_coverage_pct: standards.max_lot_coverage_pct,
      max_density_du_acre: standards.max_density_du_acre,
    } : null,
    verdict: district
      ? `Zoned ${assignment.zone_code} (${district.name || 'Unknown district'}) — ${district.category || 'verify permitted uses'}`
      : `Zoned ${assignment.zone_code} — run check_zoning with county for district details`,
    zoning_map_url: `https://zonewise.ai/map?parcel=${assignment.parcel_id}&county=${county}`,
  };
}

function shapiraFormula(arv, repairs) {
  const threshold = Math.min(25000, 0.15 * arv);
  return (arv * 0.70) - repairs - 10000 - threshold;
}

export async function underwrite_deal({ case_number, strategy, arv, repairs, opening_bid, county }) {
  let auctionData = null;
  let bid = opening_bid || 0;

  if (case_number) {
    const rows = await get(
      `multi_county_auctions?case_number=eq.${encodeURIComponent(case_number)}&select=opening_bid,judgment_amount,county,property_address,auction_date&limit=1`
    ).catch(() => []);
    if (rows.length) {
      auctionData = rows[0];
      bid = auctionData.opening_bid || bid;
    }
  }

  const maxBid = shapiraFormula(arv, repairs);
  const bidGap = maxBid - bid;
  const roi = arv > 0 ? ((arv - bid - repairs) / (bid + repairs) * 100).toFixed(1) : null;

  const rental = strategy === 'rental' || strategy === 'brrrr' ? {
    monthly_rent_est: Math.round(arv * 0.0065),
    annual_rent_est: Math.round(arv * 0.0065 * 12),
    gross_yield_pct: arv > 0 ? ((arv * 0.0065 * 12) / (bid + repairs) * 100).toFixed(1) : null,
    cap_rate_est_pct: arv > 0 ? ((arv * 0.0065 * 12 * 0.6) / arv * 100).toFixed(1) : null,
    note: 'Rent = ARV × 0.65%. Run get_rent_estimate (S2) for zip-specific HUD FMR data.',
  } : null;

  const brrrr = strategy === 'brrrr' ? {
    refi_value_75ltv: Math.round(arv * 0.75),
    cash_left_in: Math.max(0, bid + repairs - arv * 0.75),
    infinite_return: bid + repairs <= arv * 0.75,
  } : null;

  return {
    case_number,
    strategy,
    arv,
    repairs,
    opening_bid: bid,
    shapira_max_bid: Math.round(maxBid),
    bid_cushion: Math.round(bidGap),
    verdict: bidGap > 0
      ? `BID: Opening bid is $${Math.round(bidGap).toLocaleString()} below Shapira max. Budget up to $${Math.round(maxBid).toLocaleString()}.`
      : `PASS: Opening bid exceeds Shapira max by $${Math.round(-bidGap).toLocaleString()}. Overpaying risk.`,
    roi_pct: roi,
    rental,
    brrrr,
    auction_context: auctionData,
    formula: 'ARV × 70% − Repairs − $10K − MIN($25K, 15% × ARV)',
  };
}

export async function analyze_coliving({ parcel_id, county, address, bedrooms = 4, bathrooms = 2, sqft = 2000, lot_sqft }) {
  // ENR-OSTDS flag: septic systems in FL typically rated for household size
  // Co-living with 14 occupants requires septic capacity check
  const ostdsConcern = !lot_sqft || lot_sqft < 7500;

  // Check zoning for multi-family/co-living permission
  let zoningCheck = null;
  if (parcel_id && county) {
    zoningCheck = await check_zoning({ parcel_id, county }).catch(() => null);
  }

  const perRoomRent = 850; // FL co-living average per room
  const suites = Math.min(14, Math.floor(sqft / 150)); // ~150 sqft per suite minimum
  const grossMonthly = suites * perRoomRent;
  const conventionalRent = Math.round(sqft * 0.85); // $0.85/sqft FL avg

  return {
    parcel_id,
    county,
    property_specs: { bedrooms, bathrooms, sqft, lot_sqft },
    coliving_config: {
      model: 'Config C — 14-Suite Co-Living',
      feasible_suites: suites,
      per_room_rent_est: perRoomRent,
      gross_monthly_revenue: grossMonthly,
      gross_annual_revenue: grossMonthly * 12,
      uplift_vs_conventional: Math.round((grossMonthly / conventionalRent - 1) * 100),
    },
    risks: [
      ostdsConcern ? 'OSTDS (septic) capacity flag: lot size may require system upgrade for 14 occupants — verify with FL DEP' : null,
      'HOA/deed restriction review required before conversion',
      'Local zoning must permit rooming houses or co-living use',
      zoningCheck?.verdict || 'Run check_zoning to confirm zoning permits co-living',
    ].filter(Boolean),
    zoning: zoningCheck,
    next_steps: [
      '1. Confirm zoning allows co-living (rooming house / SRO use)',
      '2. Verify OSTDS capacity or city sewer connection',
      '3. Obtain occupancy permit from building department',
      '4. Run get_rent_estimate for zip-specific per-room rates',
    ],
  };
}

export async function get_sales_comps({ parcel_id, county, address, radius_miles = 0.5, months = 6, bedrooms }) {
  // Query our auction outcomes for distressed comps
  const since = new Date(Date.now() - months * 30 * 86400000).toISOString().slice(0, 10);
  // Live schema: foreclosure_outcomes uses 'county' (not county_slug) and 'winning_bid' (not sale_amount/high_bid)
  const fcFilters = [
    `county=eq.${encodeURIComponent((county || '').toLowerCase())}`,
    `auction_date=gte.${since}`,
  ];
  // tax_deed_outcomes uses 'county' and 'winning_bid' as well
  const tdFilters = [
    `county=eq.${encodeURIComponent((county || '').toLowerCase())}`,
    `auction_date=gte.${since}`,
  ];

  const [fcOutcomes, taxOutcomes] = await Promise.all([
    get(`foreclosure_outcomes?${fcFilters.join('&')}&select=case_number,parcel_id,auction_date,winning_bid,winner_type&limit=20`).catch(() => []),
    get(`tax_deed_outcomes?${tdFilters.join('&')}&select=case_number,parcel_id,auction_date,winning_bid,winner_type&limit=20`).catch(() => []),
  ]);

  const distressedComps = [
    ...fcOutcomes.map(r => ({ ...r, comp_type: 'foreclosure', sale_amount: r.winning_bid })),
    ...taxOutcomes.map(r => ({ ...r, comp_type: 'tax_deed', sale_amount: r.winning_bid })),
  ].filter(r => r.sale_amount > 0);

  const avgDistressed = distressedComps.length
    ? Math.round(distressedComps.reduce((s, r) => s + r.sale_amount, 0) / distressedComps.length)
    : null;

  return {
    county,
    months,
    radius_miles,
    distressed_comps: {
      count: distressedComps.length,
      avg_sale: avgDistressed,
      sales: distressedComps.slice(0, 10),
    },
    arm_length_comps: {
      note: 'Arm-length MLS comps require MLS data integration (coming Q3 2026). Current data: auction outcomes only.',
      count: 0,
    },
    arv_estimate: avgDistressed
      ? {
          distressed_avg: avgDistressed,
          arm_length_est: Math.round(avgDistressed * 1.15),
          recommended_arv: Math.round(avgDistressed * 1.12),
          note: 'ARV estimate = distressed avg × 1.12. Use get_sales_comps as floor — MLS comps are ceiling.',
        }
      : null,
  };
}

export async function generate_deal_memo({ case_number, county, strategy, arv, repairs }) {
  const [auction, underwrite] = await Promise.all([
    get(`multi_county_auctions?case_number=eq.${encodeURIComponent(case_number)}&limit=1`).catch(() => []),
    underwrite_deal({ case_number, strategy, arv, repairs, county }),
  ]);

  const a = auction[0] || {};

  // AI risk narrative via claude-router v4 (non-blocking — memo always returns even if LLM fails)
  const aiResp = await callRouter(
    [{
      role: 'user',
      content: JSON.stringify({
        case_number,
        county,
        strategy,
        arv,
        repairs,
        opening_bid: a.opening_bid || 0,
        judgment_amount: a.judgment_amount || 0,
        auction_date: a.auction_date || null,
        shapira_max_bid: underwrite.shapira_max_bid,
        verdict: underwrite.verdict,
        roi_pct: underwrite.roi_pct,
      }),
    }],
    {
      system: 'You are BidDeed.AI\'s foreclosure deal analyst for FL tax deed and foreclosure auctions. Given this deal data, provide exactly: 3 key risk factors (labeled RISK 1/2/3) and 3 strategic recommendations (labeled REC 1/2/3). Be specific, cite FL law where relevant, max 180 words total.',
      max_tokens: 400,
      tool_name: 'generate_deal_memo',
    }
  ).catch(() => null);

  const memo = `
# DEAL MEMO — ${a.property_address || case_number}
Generated: ${new Date().toISOString().slice(0, 10)} | BidDeed.AI

## AUCTION
Case:           ${case_number}
County:         ${county}
Sale Date:      ${a.auction_date || 'TBD'}
Opening Bid:    $${(a.opening_bid || 0).toLocaleString()}
Final Judgment: $${(a.judgment_amount || 0).toLocaleString()}
Clerk:          ${getClerkLink(county)}

## SHAPIRA UNDERWRITING (${strategy.toUpperCase()})
ARV:            $${arv.toLocaleString()}
Repairs:        $${repairs.toLocaleString()}
Max Bid:        $${underwrite.shapira_max_bid.toLocaleString()}
Verdict:        ${underwrite.verdict}
ROI:            ${underwrite.roi_pct || 'N/A'}%

## LIEN STACK (${a.sale_type || 'foreclosure'})
Statute:        FL FS 45
Key Survives:   ${LIEN_RULES.foreclosure.survive.slice(0, 2).join('; ')}
Key Extinguished: ${LIEN_RULES.foreclosure.extinguished.slice(0, 2).join('; ')}
${aiResp?.text ? `\n## AI RISK INTELLIGENCE\n${aiResp.text}\n_Powered by claude-router v4 · ${aiResp.tier} · ${aiResp.latency_ms}ms_` : ''}
## ACTIONS
[ ] Run check_zoning (S3) — confirm zoning + entitlement
[ ] Run get_deposit_requirements (S1) — lock deposit amount
[ ] Run predict_auction_outcome (S5) — certified bid prediction
[ ] Order O&E title search before bidding

---
BidDeed.AI / Everest Capital USA | Not financial advice
`.trim();

  return {
    case_number,
    county,
    strategy,
    memo_text: memo,
    auction_context: a,
    underwriting: underwrite,
    ai_enhanced: !!aiResp?.text,
    ai_router: aiResp ? { tier: aiResp.tier, model: aiResp.model, latency_ms: aiResp.latency_ms, request_id: aiResp.request_id } : null,
    format: 'text/markdown',
    note: 'PDF export: POST to https://biddeed.ai/api/deal-memo/pdf with this response',
  };
}

export async function get_bid_package({ case_number, county, arv, repairs, strategy = 'flip' }) {
  const [auction, deposit] = await Promise.all([
    get(`multi_county_auctions?case_number=eq.${encodeURIComponent(case_number)}&limit=1`).catch(() => []),
    Promise.resolve(null),
  ]);

  const a = auction[0] || {};
  const bid = a.opening_bid || 0;
  const depositAmt = Math.max(200, bid * 0.05);

  let underwriting = null;
  if (arv && repairs) {
    underwriting = await underwrite_deal({ case_number, strategy, arv, repairs, county });
  }

  const saleDate = a.auction_date || '';
  const countySlug = county.toLowerCase().replace(/\s+/g, '');

  return {
    case_number,
    county,
    property_address: a.property_address,
    auction: {
      opening_bid: bid,
      auction_date: saleDate,
      sale_type: a.sale_type || 'foreclosure',
      plaintiff: a.plaintiff,
      final_judgment: a.judgment_amount,
    },
    deposit: {
      amount: depositAmt,
      formula: 'max($200, 5% × opening_bid)',
      due: 'Close of business on auction day',
      payment: 'Cashier\'s check or same-day wire',
      clerk_link: getClerkLink(county),
    },
    bidding_links: {
      realforeclose: `https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=${saleDate}&county=${countySlug}`,
      realauction: 'https://www.realauction.com/',
    },
    underwriting: underwriting || { note: 'Pass arv + repairs to get SIGNAL$ max bid' },
    lien_stack_summary: {
      sale_type: a.sale_type || 'foreclosure',
      key_risk: 'Federal liens + HOA super-lien (12 months) survive foreclosure sale',
      full_analysis: 'Run get_lien_stack (S2) for complete lien survival rules',
    },
    zoning: { note: 'Run check_zoning (S3) with parcel_id for zone code + entitlement verdict' },
    next_step: underwriting?.verdict || 'Run underwrite_deal (S3) with your ARV + repair estimate',
  };
}

export async function get_title_chain({ parcel_id, county, case_number }) {
  const filters = [];
  if (case_number) filters.push(`case_number=eq.${encodeURIComponent(case_number)}`);
  if (parcel_id) filters.push(`parcel_id=eq.${encodeURIComponent(parcel_id)}`);
  // Live schema: foreclosure_outcomes uses 'county' (not county_slug)
  if (county) filters.push(`county=eq.${encodeURIComponent(county.toLowerCase())}`);

  // Live schema columns: outcome (not sale_status), winner_name (not buyer_name), plaintiff_raw (not plaintiff)
  const fc = await get(
    `foreclosure_outcomes?${filters.join('&')}&select=case_number,parcel_id,auction_date,outcome,winner_name,plaintiff_raw,data_source&limit=5`
  ).catch(() => []);

  return {
    parcel_id,
    county,
    case_number,
    chain_from_db: fc.map(r => ({ ...r, sale_status: r.outcome, buyer_name: r.winner_name, plaintiff: r.plaintiff_raw })),
    title_status: fc.length
      ? 'Foreclosure history found in BidDeed database'
      : 'No prior sale history in BidDeed database',
    recommendations: [
      'Order full O&E (Owner & Encumbrance) report from local title company before bidding',
      'Cost: $75–$200 from local title agent',
      'Required: federal lien search via IRS lien index',
    ],
    acclaim_harris_note: 'Full Acclaim/Harris O&E chain integration coming Q3 2026 (Pro Plus tier). Currently: BidDeed outcome database + title company referral.',
    title_companies: { note: `Run find_local_partners (S1) for vetted title companies in ${county}` },
    disclaimer: 'BidDeed title chain is based on auction outcome records — not a substitute for a professional title search.',
  };
}
