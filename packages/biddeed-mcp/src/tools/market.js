// Market data + skip trace tools
import { get } from '../supabase.js';

export const schemas = [
  {
    name: 'get_interest_rate',
    description: 'Current US mortgage interest rates from FRED (Federal Reserve). Returns 30-yr fixed, 15-yr fixed, and 10-yr Treasury. Same FRED source as Investra — free tier.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    inputSchema: {
      type: 'object',
      properties: {
        rate_type: {
          type: 'string',
          enum: ['30yr_fixed', '15yr_fixed', '10yr_treasury', 'all'],
          description: 'Rate type (default: all)',
        },
      },
      required: [],
    },
  },
  {
    name: 'get_market_data',
    description: 'National and FL-specific real estate market data: mortgage rates, home price index, vacancy rates. Same FRED source as Investra with FL overlay.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    inputSchema: {
      type: 'object',
      properties: {
        metrics:  { type: 'array', items: { type: 'string' }, description: 'Specific metrics (default: all)' },
        county:   { type: 'string', description: 'FL county for regional overlay' },
      },
      required: [],
    },
  },
  {
    name: 'skip_trace',
    description: 'Owner skip trace — phone, email, additional addresses. Passthrough to REISkip/BatchData at $0.07–$0.15/record (vs Investra $0.98). Pro tier required.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    inputSchema: {
      type: 'object',
      properties: {
        parcel_id:  { type: 'string', description: 'FL parcel ID' },
        county:     { type: 'string', description: 'FL county' },
        owner_name: { type: 'string', description: 'Owner name (from get_owner_intel or auction record)' },
        address:    { type: 'string', description: 'Property address' },
      },
      required: ['county'],
    },
  },
];

const FRED_BASE = 'https://fred.stlouisfed.org/graph/fredgraph.csv';

async function fredLatest(seriesId) {
  try {
    const res = await fetch(`${FRED_BASE}?id=${seriesId}`, {
      headers: { 'User-Agent': 'BidDeed-MCP/1.0' },
    });
    if (!res.ok) return null;
    const csv = await res.text();
    const lines = csv.trim().split('\n').filter(l => l && !l.startsWith('DATE'));
    const last = lines[lines.length - 1]?.split(',');
    if (!last || last.length < 2 || last[1] === '.') return null;
    return { date: last[0], value: parseFloat(last[1]) };
  } catch {
    return null;
  }
}

export async function get_interest_rate({ rate_type = 'all' } = {}) {
  const series = {
    '30yr_fixed':    { id: 'MORTGAGE30US', label: '30-Year Fixed Mortgage Rate', unit: '%' },
    '15yr_fixed':    { id: 'MORTGAGE15US', label: '15-Year Fixed Mortgage Rate', unit: '%' },
    '10yr_treasury': { id: 'DGS10',        label: '10-Year Treasury Yield',       unit: '%' },
  };

  const targets = rate_type === 'all' ? Object.keys(series) : [rate_type].filter(k => series[k]);

  const results = await Promise.all(
    targets.map(async key => {
      const s = series[key];
      const data = await fredLatest(s.id);
      return { key, ...s, ...data, available: !!data };
    })
  );

  return {
    source: 'FRED / Federal Reserve Bank of St. Louis',
    retrieved_at: new Date().toISOString(),
    rates: results,
    fl_context: 'FL investment property: typically rate + 0.5–1.0% for non-owner-occupied. Hard money: 10–14%.',
  };
}

export async function get_market_data({ metrics, county } = {}) {
  const [rates, hpi] = await Promise.all([
    get_interest_rate({ rate_type: 'all' }),
    fredLatest('CSUSHPISA'),  // Case-Shiller US Home Price Index
  ]);

  let auctionContext = null;
  if (county) {
    const since = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10);
    const rows = await get(
      `multi_county_auctions?county=ilike.${encodeURIComponent(county.replace(/\s+/g, '%'))}&auction_date=gte.${since}&select=opening_bid,judgment_amount&limit=500`
    ).catch(() => []);

    if (rows.length) {
      const avgBid = Math.round(rows.reduce((s, r) => s + (r.opening_bid || 0), 0) / rows.length);
      auctionContext = { county, auctions_90d: rows.length, avg_opening_bid: avgBid };
    }
  }

  return {
    source: 'FRED + BidDeed Auction Pipeline',
    retrieved_at: new Date().toISOString(),
    national: {
      mortgage_rates: rates.rates,
      home_price_index: hpi ? { series: 'CSUSHPISA', ...hpi, label: 'Case-Shiller US Home Price Index' } : null,
    },
    fl_auction_context: auctionContext,
  };
}

export async function skip_trace({ parcel_id, county, owner_name, address }) {
  const REISKIP_KEY = process.env.REISKIP_API_KEY;
  const BATCHDATA_KEY = process.env.BATCHDATA_API_KEY;

  if (!REISKIP_KEY && !BATCHDATA_KEY) {
    return {
      status: 'NOT_CONFIGURED',
      message: 'Skip trace requires REISKIP_API_KEY or BATCHDATA_API_KEY. Contact support@biddeed.ai to enable.',
      cost_info: 'BidDeed rate: $0.07–$0.15/record vs Investra $0.98/record (6–14× cheaper)',
      provider_info: {
        reiskip: 'https://www.reiskip.com — $0.07/record with BidDeed volume pricing',
        batchdata: 'https://batchdata.com — $0.15/record, higher hit rate on LLC owners',
      },
    };
  }

  // REISkip integration
  if (REISKIP_KEY) {
    try {
      const payload = { property_address: address, owner_name, parcel_id, state: 'FL' };
      const res = await fetch('https://api.reiskip.com/v2/skip', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': REISKIP_KEY,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        return {
          status: 'OK',
          provider: 'REISkip',
          cost_usd: 0.07,
          results: data,
        };
      }
    } catch (err) {
      process.stderr.write(`[skip_trace] REISkip error: ${err.message}\n`);
    }
  }

  // BatchData fallback
  if (BATCHDATA_KEY) {
    try {
      const res = await fetch('https://api.batchdata.com/api/v1/property/skip-trace', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${BATCHDATA_KEY}`,
        },
        body: JSON.stringify({ requests: [{ propertyAddress: address, ownerName: owner_name }] }),
      });

      if (res.ok) {
        const data = await res.json();
        return {
          status: 'OK',
          provider: 'BatchData',
          cost_usd: 0.15,
          results: data,
        };
      }
    } catch (err) {
      process.stderr.write(`[skip_trace] BatchData error: ${err.message}\n`);
    }
  }

  return {
    status: 'PROVIDER_ERROR',
    message: 'Skip trace providers returned errors. Try again or contact support@biddeed.ai.',
  };
}
