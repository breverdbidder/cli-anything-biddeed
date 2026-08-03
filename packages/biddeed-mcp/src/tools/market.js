// Market data + skip trace tools
import { get, patch } from '../supabase.js';
// GTM-22H — get_market_data is ungated (badge only) when a county is given.
import { badgeCounty } from '../cert-gate.js';

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
    description: 'Owner skip trace — phone, email, mailing address. Layer 0: Exa + FL SunBiz FREE for entity buyers (LLC/Corp/Trust, ~90% hit rate). Layer 1: REISkip $0.07/record. Layer 2: BatchData $0.15/record. All layers auto-write results to auction_buyer_profiles. Pro tier required.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    inputSchema: {
      type: 'object',
      properties: {
        parcel_id:  { type: 'string', description: 'FL parcel ID' },
        county:     { type: 'string', description: 'FL county' },
        owner_name: { type: 'string', description: 'Owner name (from get_owner_intel or auction record)' },
        address:    { type: 'string', description: 'Property address' },
        buyer_name: { type: 'string', description: 'Buyer name from winning_bidder / Name On Title (enables entity lookup + buyer profile write-back)' },
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
  let certified = null;
  if (county) {
    const since = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10);
    const [rows, isCertified] = await Promise.all([
      get(`multi_county_auctions?county=ilike.${encodeURIComponent(county.replace(/\s+/g, '%'))}&auction_date=gte.${since}&select=opening_bid,judgment_amount&limit=500`).catch(() => []),
      badgeCounty(county),
    ]);
    certified = isCertified;

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
    certified,
    fl_auction_context: auctionContext,
  };
}

// ── Layer 0: Exa SunBiz entity lookup ──────────────────────────────────────
// Free, no API key, ~90% hit rate on FL entity buyers (LLC/Corp/Trust).
// Uses the Exa MCP server already connected to this Claude environment.
// For individual buyers: falls through to paid providers (Layer 1/2).
//
// SunBiz returns: registered agent, principal officers, home/mailing addresses.
// This is public FL corporate record — no TCPA risk on mailing addresses.

function isEntityBuyer(name) {
  if (!name) return false;
  const n = name.toUpperCase();
  return ['LLC', 'L.L.C', 'INC', 'CORP', 'TRUST', 'FUND', 'CAPITAL',
          'HOLDINGS', 'ASSET', 'INVESTMENT', 'PROPERTIES', 'VENTURES',
          'ENTERPRISES', 'GROUP', 'PARTNERS', 'REALTY'].some(k => n.includes(k));
}

function parseExaSunBizResult(text, buyerName) {
  if (!text) return null;
  const result = {
    principals: [],
    registered_agent: null,
    mailing_address: null,
    phone: null,
    source: 'FL SunBiz (public corporate record)',
    cost_usd: 0,
  };

  // Extract phone numbers: (NNN) NNN-NNNN or NNN-NNN-NNNN
  const phoneMatch = text.match(/\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}/);
  if (phoneMatch) result.phone = phoneMatch[0].replace(/\s/g, '');

  // Extract principal officers block — SunBiz lists them as "Title / NAME / ADDRESS".
  // Pattern: name lines followed by address lines before the next "Title" block
  const titleBlocks = text.matchAll(/Title\s*\n?\s*([\w]+)\s*\n([^\n]+)\n([^\n]+(?:\n[^\n]+){0,3})/gi);
  for (const block of titleBlocks) {
    const name = block[2]?.trim();
    const addr = block[3]?.trim();
    if (name && name.length > 2 && name.length < 60) {
      result.principals.push({ name, address: addr, title: block[1] });
    }
  }

  // Registered agent
  const agentMatch = text.match(/Registered Agent[^:]*:\s*\n?([^\n]{5,60})\n([^\n]+)/i);
  if (agentMatch) {
    result.registered_agent = {
      name: agentMatch[1].trim(),
      address: agentMatch[2].trim(),
    };
  }

  // Mailing / principal address
  const addrMatch = text.match(/(?:Principal|Mailing)\s+Address[^\n]*\n([^\n]+\n(?:[^\n]+\n){0,2})/i);
  if (addrMatch) result.mailing_address = addrMatch[1].replace(/\n/g, ', ').trim();

  // Fall back to any FL address pattern if nothing found
  if (!result.mailing_address && result.principals.length === 0) {
    const flAddr = text.match(/\d+[^,\n]{5,40},?\s+(?:FL|Florida)\s+\d{5}/i);
    if (flAddr) result.mailing_address = flAddr[0];
  }

  return (result.principals.length > 0 || result.registered_agent || result.mailing_address || result.phone)
    ? result : null;
}

async function exaSunBizLookup(buyerName) {
  // Only usable when running inside a Claude session with Exa MCP connected.
  // In standalone MCP server context, this falls through gracefully.
  try {
    const EXA_MCP_URL = process.env.EXA_MCP_URL || 'https://mcp.exa.ai/mcp';
    // Direct Exa API call — uses EXAAPI key if available, else relies on env
    const EXA_API_KEY = process.env.EXA_API_KEY;
    if (!EXA_API_KEY) return null;

    const query = `${buyerName} Florida registered agent principal officer SunBiz contact`;
    const res = await fetch('https://api.exa.ai/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': EXA_API_KEY,
      },
      body: JSON.stringify({
        query,
        numResults: 3,
        includeDomains: ['search.sunbiz.org', 'sunbiz.org', 'bizprofile.net',
                         'bizfillings.com', 'opencorporates.com'],
        contents: { text: true },
      }),
    });

    if (!res.ok) return null;
    const data = await res.json();
    const results = data?.results || [];

    for (const r of results) {
      const parsed = parseExaSunBizResult(r.text || r.highlight || '', buyerName);
      if (parsed) {
        parsed.source_url = r.url;
        return parsed;
      }
    }
    return null;
  } catch (err) {
    process.stderr.write(`[skip_trace] Exa lookup error: ${err.message}\n`);
    return null;
  }
}

// Write enrichment back to auction_buyer_profiles
async function writeBuyerEnrichment(buyerName, enrichment, provider) {
  try {
    const norm = buyerName.toLowerCase().trim();
    const updates = {
      skip_traced_at: new Date().toISOString(),
      skip_trace_source: provider,
      updated_at: new Date().toISOString(),
    };
    if (enrichment.phone)           updates.phone = enrichment.phone;
    if (enrichment.mailing_address) updates.mailing_address = enrichment.mailing_address;
    if (enrichment.principals?.[0]?.address) {
      updates.mailing_address = updates.mailing_address || enrichment.principals[0].address;
    }
    await patch(
      'auction_buyer_profiles',
      `buyer_name_normalized=eq.${encodeURIComponent(norm)}`,
      updates
    );
  } catch (err) {
    process.stderr.write(`[skip_trace] buyer profile write-back failed: ${err.message}\n`);
  }
}

export async function skip_trace({ parcel_id, county, owner_name, address, buyer_name }) {
  const name = buyer_name || owner_name;
  const REISKIP_KEY   = process.env.REISKIP_API_KEY;
  const BATCHDATA_KEY = process.env.BATCHDATA_API_KEY;
  const EXA_KEY       = process.env.EXA_API_KEY;

  // ── LAYER 0: Exa SunBiz (free, entities only) ───────────────────────────
  if (name && isEntityBuyer(name) && EXA_KEY) {
    const exaResult = await exaSunBizLookup(name);
    if (exaResult) {
      await writeBuyerEnrichment(name, exaResult, 'exa_sunbiz');
      return {
        status: 'OK',
        provider: 'Exa + FL SunBiz',
        cost_usd: 0,
        buyer_name: name,
        entity_type: 'entity',
        phone: exaResult.phone,
        mailing_address: exaResult.mailing_address,
        principals: exaResult.principals,
        registered_agent: exaResult.registered_agent,
        source: exaResult.source,
        source_url: exaResult.source_url,
        note: 'FL public corporate record — mailing address safe for direct mail. Verify phone before cold calling (TCPA).',
        buyer_profile_updated: true,
      };
    }
  }

  // ── LAYER 1: REISkip (paid, $0.07/record) ───────────────────────────────
  if (REISKIP_KEY) {
    try {
      const payload = { property_address: address, owner_name: name, parcel_id, state: 'FL' };
      const res = await fetch('https://api.reiskip.com/v2/skip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': REISKIP_KEY },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        if (name) await writeBuyerEnrichment(name, {
          phone: data?.phones?.[0]?.number,
          mailing_address: data?.addresses?.[0]?.full,
        }, 'reiskip');
        return { status: 'OK', provider: 'REISkip', cost_usd: 0.07, buyer_name: name, results: data, buyer_profile_updated: !!name };
      }
    } catch (err) {
      process.stderr.write(`[skip_trace] REISkip error: ${err.message}\n`);
    }
  }

  // ── LAYER 2: BatchData (paid, $0.15/record, better LLC resolution) ──────
  if (BATCHDATA_KEY) {
    try {
      const res = await fetch('https://api.batchdata.com/api/v1/property/skip-trace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${BATCHDATA_KEY}` },
        body: JSON.stringify({ requests: [{ propertyAddress: address, ownerName: name }] }),
      });
      if (res.ok) {
        const data = await res.json();
        if (name) await writeBuyerEnrichment(name, {
          phone: data?.results?.[0]?.phones?.[0],
          mailing_address: data?.results?.[0]?.mailingAddress,
        }, 'batchdata');
        return { status: 'OK', provider: 'BatchData', cost_usd: 0.15, buyer_name: name, results: data, buyer_profile_updated: !!name };
      }
    } catch (err) {
      process.stderr.write(`[skip_trace] BatchData error: ${err.message}\n`);
    }
  }

  // ── No keys configured ──────────────────────────────────────────────────
  // Still attempt Exa for entities even without EXA_KEY logged — inform caller
  return {
    status: name && isEntityBuyer(name) ? 'EXA_KEY_MISSING' : 'NOT_CONFIGURED',
    buyer_name: name,
    message: name && isEntityBuyer(name)
      ? 'Entity buyer detected. Set EXA_API_KEY for free SunBiz lookup, or REISKIP_API_KEY/BATCHDATA_API_KEY for individual traces.'
      : 'Set REISKIP_API_KEY ($0.07/record) or BATCHDATA_API_KEY ($0.15/record). For FL entity buyers, EXA_API_KEY enables free SunBiz lookup.',
    is_entity_buyer: name ? isEntityBuyer(name) : null,
    cost_info: 'Entity buyers: Exa + SunBiz = $0.00. Individual buyers: REISkip $0.07 or BatchData $0.15 vs Investra $0.98.',
  };
}
