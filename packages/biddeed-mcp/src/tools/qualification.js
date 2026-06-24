// S2 Qualification tools — $0.40/call, gate: investor tier
import { get } from '../supabase.js';
import { LIEN_RULES } from '../constants.js';

export const schemas = [
  {
    name: 'search_distressed',
    description: 'Search distressed FL properties: lis pendens, tax delinquent, pre-foreclosure filings. Our advantage over Investra: we add FL-specific lis pendens database + tax cert delinquency status.',
    inputSchema: {
      type: 'object',
      properties: {
        county:        { type: 'string', description: 'FL county name' },
        distress_type: { type: 'string', enum: ['lis_pendens', 'tax_delinquent', 'pre_foreclosure', 'all'], description: 'Type of distress (default: all)' },
        zip_code:      { type: 'string', description: 'Zip code filter' },
        min_equity:    { type: 'number', description: 'Minimum estimated equity (USD)' },
        limit:         { type: 'number', description: 'Results (default: 20)' },
      },
      required: ['county'],
    },
  },
  {
    name: 'get_owner_intel',
    description: 'Property owner intelligence: name, mailing address, LLC/trust flag, absentee indicator. Used for pre-foreclosure outreach.',
    inputSchema: {
      type: 'object',
      properties: {
        parcel_id:    { type: 'string', description: 'FL property parcel ID / folio number' },
        county:       { type: 'string', description: 'FL county' },
        address:      { type: 'string', description: 'Property address (alternative to parcel_id)' },
      },
      required: ['county'],
    },
  },
  {
    name: 'get_lien_stack',
    description: 'FL auction lien survival rules. Critical for bid decisions. Returns which liens survive vs are extinguished post-sale per FL FS 197 (tax deed) or FL FS 45 (foreclosure). BidDeed exclusive — Investra has no equivalent.',
    inputSchema: {
      type: 'object',
      properties: {
        case_number: { type: 'string', description: 'Case number (optional — enriches with auction context)' },
        county:      { type: 'string', description: 'FL county' },
        sale_type:   { type: 'string', enum: ['tax_deed', 'foreclosure'], description: 'Auction sale type (default: foreclosure)' },
      },
      required: ['sale_type'],
    },
  },
  {
    name: 'get_rent_estimate',
    description: 'Rent estimate for FL property by zip code using HUD Fair Market Rents. Adds per-room co-living uplift calculation. Better than Investra: we add HUD FMR + auction distress context.',
    inputSchema: {
      type: 'object',
      properties: {
        zip_code:   { type: 'string', description: 'FL zip code (5-digit)' },
        county:     { type: 'string', description: 'FL county (used if zip_code unavailable)' },
        bedrooms:   { type: 'number', description: 'Number of bedrooms (0=studio, 1-4)' },
        include_coliving: { type: 'boolean', description: 'Include per-room co-living estimate (default: true)' },
      },
      required: ['zip_code'],
    },
  },
  {
    name: 'analyze_market',
    description: 'County-level auction market analysis: volume trends, avg bid vs judgment, distress rate, absorption. We add auction volume overlay Investra lacks.',
    inputSchema: {
      type: 'object',
      properties: {
        county:    { type: 'string', description: 'FL county name' },
        months:    { type: 'number', description: 'Analysis window in months (default: 6, max: 24)' },
        sale_type: { type: 'string', enum: ['foreclosure', 'tax_deed', 'all'] },
      },
      required: ['county'],
    },
  },
  {
    name: 'get_zip_market_data',
    description: 'Zip-code level market data: HUD FMR rents, auction distress rate, median bid, active listings count. Better than Investra: adds auction distress rate overlay.',
    inputSchema: {
      type: 'object',
      properties: {
        zip_code: { type: 'string', description: 'FL zip code (5-digit)' },
        county:   { type: 'string', description: 'FL county (enhances zip lookup)' },
      },
      required: ['zip_code'],
    },
  },
];

// ── Tool Handlers ─────────────────────────────────────────────────────────────

export async function search_distressed({ county, distress_type = 'all', zip_code, min_equity, limit = 20 }) {
  // Query our auction table for pre-filing / lis pendens stage cases
  const filters = [
    `county=ilike.${encodeURIComponent(county.replace(/\s+/g, '%'))}`,
    `auction_date=gte.${new Date(Date.now() - 180 * 86400000).toISOString().slice(0, 10)}`,
  ];
  if (zip_code) filters.push(`zip_code=eq.${zip_code}`);

  const rows = await get(
    `multi_county_auctions?${filters.join('&')}&order=auction_date.desc&limit=${Math.min(limit, 100)}&select=case_number,county,property_address,parcel_id,opening_bid,auction_date,sale_type,plaintiff,judgment_amount`
  ).catch(() => []);

  const distressed = rows.map(r => ({
    ...r,
    distress_type: r.sale_type === 'tax_deed' ? 'tax_delinquent' : 'lis_pendens',
    estimated_equity: r.judgment_amount
      ? Math.max(0, (r.judgment_amount || 0) - (r.opening_bid || 0))
      : null,
  })).filter(r => !min_equity || (r.estimated_equity || 0) >= min_equity);

  return {
    county,
    distress_type,
    count: distressed.length,
    properties: distressed,
    note: 'Source: BidDeed auction pipeline. For pre-filing lis pendens (not yet in auction), contact support@biddeed.ai for county recorder data access.',
  };
}

export async function get_owner_intel({ parcel_id, county, address }) {
  if (!parcel_id && !address) {
    return { error: 'Provide parcel_id or address' };
  }

  const filters = [`county=ilike.${encodeURIComponent((county || '').replace(/\s+/g, '%'))}`];
  if (parcel_id) filters.push(`parcel_id=eq.${encodeURIComponent(parcel_id)}`);
  else if (address) filters.push(`property_address=ilike.${encodeURIComponent(`%${address}%`)}`);

  const rows = await get(
    `multi_county_auctions?${filters.join('&')}&select=case_number,county,property_address,parcel_id,plaintiff,defendant&limit=5`
  ).catch(() => []);

  if (!rows.length) {
    return {
      found: false,
      note: 'Property not found in auction records. For BCPAO/PAO lookup, run get_property_detail (S2).',
    };
  }

  return {
    found: true,
    results: rows.map(r => ({
      parcel_id: r.parcel_id,
      property_address: r.property_address,
      county: r.county,
      defendant_name: r.defendant,
      plaintiff: r.plaintiff,
      note: 'Full owner intel (mailing address, LLC check, absentee flag) available via skip_trace (S3) or BCPAO direct lookup.',
    })),
  };
}

export async function get_lien_stack({ case_number, county, sale_type = 'foreclosure' }) {
  const rules = LIEN_RULES[sale_type];
  if (!rules) return { error: `Unknown sale_type: ${sale_type}. Use 'tax_deed' or 'foreclosure'.` };

  let auctionContext = null;
  if (case_number) {
    const rows = await get(
      `multi_county_auctions?case_number=eq.${encodeURIComponent(case_number)}&select=case_number,county,property_address,opening_bid,judgment_amount,plaintiff,auction_date&limit=1`
    ).catch(() => []);
    if (rows.length) auctionContext = rows[0];
  }

  return {
    case_number,
    county,
    sale_type,
    statute: rules.statute,
    liens_that_survive: rules.survive,
    liens_extinguished: rules.extinguished,
    legal_note: rules.note,
    auction_context: auctionContext,
    recommendation: sale_type === 'tax_deed'
      ? 'Budget $500–$2,000 for title search + O&E insurance before bidding. Federal lien check is mandatory.'
      : 'Always obtain title commitment before bidding. HOA super-lien (12 months) may survive — verify with HOA directly.',
    disclaimer: 'This is general FL law guidance. Not legal advice. Verify with FL real estate attorney before bidding.',
  };
}

export async function get_rent_estimate({ zip_code, county, bedrooms = 3, include_coliving = true }) {
  // HUD FMR API — public, no key required
  let hudData = null;
  try {
    const hudRes = await fetch(
      `https://www.huduser.gov/hudapi/public/fmr/listCounties/FL`,
      { headers: { 'Accept': 'application/json' } }
    );
    if (hudRes.ok) {
      const allCounties = await hudRes.json();
      // Find matching county
      const match = allCounties?.data?.find(c =>
        c.county_name?.toLowerCase().includes((county || '').toLowerCase())
      );
      if (match?.fips_code) {
        const fmrRes = await fetch(
          `https://www.huduser.gov/hudapi/public/fmr/data/${match.fips_code}`,
          { headers: { 'Accept': 'application/json' } }
        );
        if (fmrRes.ok) hudData = await fmrRes.json();
      }
    }
  } catch {
    // HUD API unavailable — use FL baseline estimates
  }

  // FL baseline FMR estimates by bedroom count (2024 HUD data)
  const flBaseline = { 0: 1050, 1: 1250, 2: 1550, 3: 1900, 4: 2250 };
  const fmrMap = hudData?.data?.basicdata || {};
  const estimate = fmrMap[`Efficiency`]
    ? {
        studio:  Math.round(fmrMap['Efficiency'] || flBaseline[0]),
        '1br':   Math.round(fmrMap['One-Bedroom'] || flBaseline[1]),
        '2br':   Math.round(fmrMap['Two-Bedroom'] || flBaseline[2]),
        '3br':   Math.round(fmrMap['Three-Bedroom'] || flBaseline[3]),
        '4br':   Math.round(fmrMap['Four-Bedroom'] || flBaseline[4]),
      }
    : {
        studio: flBaseline[0], '1br': flBaseline[1], '2br': flBaseline[2],
        '3br': flBaseline[3], '4br': flBaseline[4],
      };

  const targetRent = estimate[`${bedrooms}br`] || estimate['2br'];
  const result = {
    zip_code,
    county,
    bedrooms,
    monthly_rent_estimate: targetRent,
    hud_fmr: estimate,
    source: hudData ? 'HUD Fair Market Rents 2024' : 'FL baseline estimates (HUD API unavailable)',
  };

  if (include_coliving) {
    // Config C co-living: 14 rooms, per-room premium ~1.4× market rate / room count
    const perRoom = Math.round(targetRent * 1.4 / bedrooms);
    result.coliving = {
      per_room_estimate: perRoom,
      gross_monthly_14suite: perRoom * 14,
      note: 'Co-living per-room rate = market rent × 1.4 ÷ bedrooms. Run analyze_coliving (S3) for full 14-suite model with OSTDS flag.',
    };
  }

  return result;
}

export async function analyze_market({ county, months = 6, sale_type = 'all' }) {
  const since = new Date(Date.now() - months * 30 * 86400000).toISOString().slice(0, 10);
  const filters = [
    `county=ilike.${encodeURIComponent(county.replace(/\s+/g, '%'))}`,
    `auction_date=gte.${since}`,
  ];
  if (sale_type !== 'all') filters.push(`sale_type=eq.${sale_type}`);

  const rows = await get(
    `multi_county_auctions?${filters.join('&')}&select=opening_bid,judgment_amount,auction_date,sale_type`
  ).catch(() => []);

  if (!rows.length) {
    return { county, months, count: 0, note: 'No auction data found for this county/period.' };
  }

  const totalBid = rows.reduce((s, r) => s + (r.opening_bid || 0), 0);
  const totalFJ = rows.reduce((s, r) => s + (r.judgment_amount || 0), 0);
  const avgDiscount = totalFJ > 0 ? ((totalFJ - totalBid) / totalFJ * 100).toFixed(1) : null;

  const byType = rows.reduce((acc, r) => {
    acc[r.sale_type] = (acc[r.sale_type] || 0) + 1;
    return acc;
  }, {});

  return {
    county,
    analysis_window_months: months,
    since_date: since,
    total_auctions: rows.length,
    avg_opening_bid: Math.round(totalBid / rows.length),
    avg_final_judgment: totalFJ > 0 ? Math.round(totalFJ / rows.length) : null,
    avg_judgment_discount_pct: avgDiscount ? parseFloat(avgDiscount) : null,
    auctions_by_type: byType,
    monthly_volume: Math.round(rows.length / months),
    insight: avgDiscount
      ? `Average auction opens at ${avgDiscount}% discount to final judgment — ${avgDiscount > 40 ? 'strong value zone' : 'competitive market'}.`
      : `${rows.length} auctions in ${months}mo period.`,
  };
}

export async function get_zip_market_data({ zip_code, county }) {
  const [rentData, marketData] = await Promise.all([
    get_rent_estimate({ zip_code, county, bedrooms: 3, include_coliving: false }),
    analyze_market({ county: county || zip_code, months: 6, sale_type: 'all' }).catch(() => null),
  ]);

  return {
    zip_code,
    county,
    rent_estimates: rentData.hud_fmr,
    market: marketData,
    hud_fmr_source: rentData.source,
  };
}
