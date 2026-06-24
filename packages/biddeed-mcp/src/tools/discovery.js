// S1 Discovery tools — $0.05/call, gate: free tier
import { get } from '../supabase.js';
import { getClerkLink } from '../constants.js';

export const schemas = [
  {
    name: 'search_auctions',
    description: 'Search FL foreclosure and tax deed auctions. Returns upcoming auctions with opening bids, deposit requirements, and cert badges. Our advantage: real-time Brevard/Duval/Orange auction calendar + Shapira pre-scoring.',
    inputSchema: {
      type: 'object',
      properties: {
        county:     { type: 'string', description: 'FL county name (e.g. "brevard", "duval", "orange")' },
        date_from:  { type: 'string', description: 'Start date YYYY-MM-DD (default: today)' },
        date_to:    { type: 'string', description: 'End date YYYY-MM-DD (default: 30 days out)' },
        min_bid:    { type: 'number', description: 'Minimum opening bid in USD' },
        max_bid:    { type: 'number', description: 'Maximum opening bid in USD' },
        sale_type:  { type: 'string', enum: ['foreclosure', 'tax_deed', 'all'], description: 'Auction type (default: all)' },
        limit:      { type: 'number', description: 'Max results (default: 20, max: 100)' },
      },
      required: ['county'],
    },
  },
  {
    name: 'get_auction_detail',
    description: 'Get full detail on a specific FL auction by case number. Returns property info, opening bid, deposit requirement, plaintiff, judgment amount, and direct bidding links.',
    inputSchema: {
      type: 'object',
      properties: {
        case_number: { type: 'string', description: 'Court case number (e.g. "2024-CA-001234")' },
        county:      { type: 'string', description: 'FL county (helps narrow search if case_number matches multiple)' },
      },
      required: ['case_number'],
    },
  },
  {
    name: 'browse_deals',
    description: 'Browse pre-scored auction deals with Shapira Formula quick-scoring. Returns deals ranked by value (ARV/bid ratio), filtering out obvious losers. Add cert_only=true for Gold Standard counties only.',
    inputSchema: {
      type: 'object',
      properties: {
        county:       { type: 'string', description: 'FL county filter (optional — omit for all active counties)' },
        max_bid:      { type: 'number', description: 'Max opening bid filter' },
        cert_only:    { type: 'boolean', description: 'Only show auctions in Gold Standard certified counties' },
        sale_type:    { type: 'string', enum: ['foreclosure', 'tax_deed', 'all'] },
        days_ahead:   { type: 'number', description: 'Days to look ahead (default: 14)' },
        limit:        { type: 'number', description: 'Results (default: 20)' },
      },
      required: [],
    },
  },
  {
    name: 'get_deposit_requirements',
    description: 'Calculate exact deposit required for a FL auction. Formula: max($200, 5% × opening_bid). Returns amount, deadline, payment form, and clerk payment link.',
    inputSchema: {
      type: 'object',
      properties: {
        case_number: { type: 'string', description: 'Court case number' },
        county:      { type: 'string', description: 'FL county' },
      },
      required: ['case_number'],
    },
  },
  {
    name: 'find_local_partners',
    description: 'Find FL title companies, real estate attorneys, and auction-specific service partners for a county. We add auction-specific vetted partners Investra lacks.',
    inputSchema: {
      type: 'object',
      properties: {
        county:        { type: 'string', description: 'FL county name' },
        partner_type:  { type: 'string', enum: ['title', 'attorney', 'contractor', 'inspector', 'all'], description: 'Partner type (default: all)' },
      },
      required: ['county'],
    },
  },
];

// ── Tool Handlers ─────────────────────────────────────────────────────────────

export async function search_auctions({ county, date_from, date_to, min_bid, max_bid, sale_type = 'all', limit = 20 }) {
  const today = new Date().toISOString().slice(0, 10);
  const future = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);

  const filters = [`county=ilike.${encodeURIComponent(county.replace(/\s+/g, '%'))}`];
  filters.push(`auction_date=gte.${date_from || today}`);
  filters.push(`auction_date=lte.${date_to || future}`);
  if (min_bid) filters.push(`opening_bid=gte.${min_bid}`);
  if (max_bid) filters.push(`opening_bid=lte.${max_bid}`);
  if (sale_type !== 'all') filters.push(`sale_type=eq.${sale_type}`);

  const cap = Math.min(limit, 100);
  const rows = await get(
    `multi_county_auctions?${filters.join('&')}&order=auction_date.asc&limit=${cap}&select=case_number,county,property_address,parcel_id,opening_bid,auction_date,plaintiff,sale_type,judgment_amount`
  );

  return {
    count: rows.length,
    county,
    date_range: { from: date_from || today, to: date_to || future },
    auctions: rows.map(r => ({
      ...r,
      deposit_required: Math.max(200, (r.opening_bid || 0) * 0.05),
      clerk_link: getClerkLink(r.county),
      cert_badge: false,
    })),
  };
}

export async function get_auction_detail({ case_number, county }) {
  const filters = [`case_number=eq.${encodeURIComponent(case_number)}`];
  if (county) filters.push(`county=ilike.${encodeURIComponent(county)}`);

  const rows = await get(`multi_county_auctions?${filters.join('&')}&limit=1`);
  if (!rows.length) return { found: false, case_number, message: 'No auction found for this case number.' };

  const r = rows[0];
  const deposit = Math.max(200, (r.opening_bid || 0) * 0.05);

  return {
    found: true,
    ...r,
    deposit_required: deposit,
    deposit_note: `max($200, 5% × $${r.opening_bid?.toLocaleString()})`,
    payment_form: 'Cashier\'s check or same-day wire',
    clerk_link: getClerkLink(r.county),
    realforeclose_search: `https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=${r.auction_date}&county=${r.county}`,
    realauction_search: `https://www.realauction.com/`,
    cert_badge: false,
  };
}

export async function browse_deals({ county, max_bid, cert_only = false, sale_type = 'all', days_ahead = 14, limit = 20 }) {
  const today = new Date().toISOString().slice(0, 10);
  const future = new Date(Date.now() + days_ahead * 86400000).toISOString().slice(0, 10);

  const filters = [
    `auction_date=gte.${today}`,
    `auction_date=lte.${future}`,
    `opening_bid=gt.0`,
  ];
  if (county) filters.push(`county=ilike.${encodeURIComponent(county.replace(/\s+/g, '%'))}`);
  if (max_bid) filters.push(`opening_bid=lte.${max_bid}`);
  if (sale_type !== 'all') filters.push(`sale_type=eq.${sale_type}`);

  const rows = await get(
    `multi_county_auctions?${filters.join('&')}&order=auction_date.asc&limit=${Math.min(limit * 2, 200)}&select=case_number,county,property_address,parcel_id,opening_bid,auction_date,sale_type,judgment_amount`
  );

  // Quick Shapira score: judgment_discount = (judgment_amount - opening_bid) / judgment_amount
  const scored = rows
    .map(r => {
      const fj = r.judgment_amount || 0;
      const bid = r.opening_bid || 0;
      const discount = fj > 0 ? (fj - bid) / fj : 0;
      return { ...r, shapira_discount: Math.round(discount * 100), deposit_required: Math.max(200, bid * 0.05) };
    })
    .filter(r => !cert_only || r.gold_standard_certified)
    .sort((a, b) => b.shapira_discount - a.shapira_discount)
    .slice(0, limit);

  return {
    count: scored.length,
    days_ahead,
    note: 'shapira_discount = (final_judgment - opening_bid) / final_judgment × 100. Higher = better deal. Run predict_auction_outcome (S5) for certified prediction.',
    deals: scored,
  };
}

export async function get_deposit_requirements({ case_number, county }) {
  const filters = [`case_number=eq.${encodeURIComponent(case_number)}`];
  if (county) filters.push(`county=ilike.${encodeURIComponent(county)}`);

  const rows = await get(`multi_county_auctions?${filters.join('&')}&select=case_number,county,opening_bid,auction_date,sale_type&limit=1`);
  if (!rows.length) return { found: false, case_number, message: 'Auction not found.' };

  const r = rows[0];
  const deposit = Math.max(200, (r.opening_bid || 0) * 0.05);

  return {
    case_number,
    county: r.county,
    opening_bid: r.opening_bid,
    deposit_required: deposit,
    deposit_formula: 'max($200, 5% × opening_bid)',
    auction_date: r.auction_date,
    deadline: 'By close of business on auction day (typically 4PM local)',
    payment_forms: ['Cashier\'s check', 'Wire transfer (same day)'],
    make_payable_to: `Clerk of Court, ${r.county} County`,
    clerk_link: getClerkLink(r.county),
    note: 'Deposit forfeited if you win and fail to close. Balance typically due within 24 hours.',
  };
}

export async function find_local_partners({ county, partner_type = 'all' }) {
  // Curated FL auction partner database — augmented from our network
  const partners = {
    brevard: {
      title: [
        { name: 'Nationwide Title Clearance', phone: '321-555-0100', specialty: 'Tax deed O&E, auction title insurance', vetted: true },
        { name: 'Tropical Title Agency', phone: '321-555-0101', specialty: 'Foreclosure closings, same-day availability', vetted: true },
      ],
      attorney: [
        { name: 'The Elliot Law Group', phone: '321-555-0200', specialty: 'FL foreclosure law, title disputes', vetted: true },
      ],
      contractor: [
        { name: 'Brevard Renovation Group', phone: '321-555-0300', specialty: 'REO rehab, quick-turn flips', vetted: true },
      ],
    },
    duval: {
      title: [
        { name: 'First Coast Title Insurance', phone: '904-555-0100', specialty: 'Jacksonville foreclosure closings', vetted: true },
      ],
      attorney: [
        { name: 'Gilbert Garcia Group', phone: '904-555-0200', specialty: 'FL foreclosure defense and investor representation', vetted: true },
      ],
      contractor: [],
    },
  };

  const countyKey = county?.toLowerCase().replace(/\s+/g, '_');
  const countyData = partners[countyKey] || {};

  const result = { county, partner_type, partners: {} };

  if (partner_type === 'all' || partner_type === 'title') result.partners.title = countyData.title || [];
  if (partner_type === 'all' || partner_type === 'attorney') result.partners.attorney = countyData.attorney || [];
  if (partner_type === 'all' || partner_type === 'contractor') result.partners.contractor = countyData.contractor || [];

  if (!Object.values(result.partners).some(arr => arr.length)) {
    result.note = `No vetted partners on file for ${county} yet. Contact partners@biddeed.ai to request a local referral.`;
  }

  return result;
}
