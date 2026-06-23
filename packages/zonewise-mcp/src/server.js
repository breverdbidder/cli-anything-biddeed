import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';

import { validateKey, resolveApiKey, assertTier, AuthError } from '../../biddeed-mcp/src/auth.js';
import { recordBilling } from '../../biddeed-mcp/src/billing.js';
import { check_zoning } from '../../biddeed-mcp/src/tools/fusion.js';
import { get } from '../../biddeed-mcp/src/supabase.js';

// ZoneWise-specific tool schemas
const TOOLS = [
  {
    name: 'check_zoning',
    description: 'ZoneWise parcel zoning lookup — 771K+ FL parcels. Returns zone code, district name, FAR, setbacks, max height, and entitlement verdict. Keys start with zw_live_.',
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
    name: 'get_zoning_districts',
    description: 'List all zoning districts for a FL county with standards (FAR, height, lot size, setbacks). Useful for understanding what development is possible in a county.',
    inputSchema: {
      type: 'object',
      properties: {
        county:    { type: 'string', description: 'FL county name' },
        category:  { type: 'string', description: 'Zone category filter (residential/commercial/industrial/agricultural)' },
        limit:     { type: 'number', description: 'Max results (default: 50)' },
      },
      required: ['county'],
    },
  },
  {
    name: 'bulk_check_zoning',
    description: 'Check zoning for up to 50 parcels in a single call. Returns zone codes and categories. Ideal for portfolio analysis.',
    inputSchema: {
      type: 'object',
      properties: {
        parcels: {
          type: 'array',
          items: { type: 'object', properties: { parcel_id: { type: 'string' }, county: { type: 'string' } }, required: ['parcel_id', 'county'] },
          description: 'Array of {parcel_id, county} objects (max 50)',
        },
      },
      required: ['parcels'],
    },
  },
];

async function get_zoning_districts({ county, category, limit = 50 }) {
  const filters = [`county=eq.${encodeURIComponent(county.toLowerCase())}`];
  if (category) filters.push(`category=ilike.${encodeURIComponent(`%${category}%`)}`);

  const rows = await get(
    `zoning_districts?${filters.join('&')}&limit=${Math.min(limit, 100)}&select=code,name,category,far,max_height_ft,min_lot_sqft,county`
  ).catch(() => []);

  return { county, category, count: rows.length, districts: rows };
}

async function bulk_check_zoning({ parcels }) {
  if (!Array.isArray(parcels) || parcels.length > 50) {
    return { error: 'parcels must be an array with 1–50 items' };
  }

  const results = await Promise.all(
    parcels.map(({ parcel_id, county }) =>
      check_zoning({ parcel_id, county }).catch(err => ({ parcel_id, county, error: err.message }))
    )
  );

  return {
    count: results.length,
    found: results.filter(r => r.found).length,
    results,
  };
}

const HANDLERS = {
  check_zoning,
  get_zoning_districts,
  bulk_check_zoning,
};

export function createServer(apiKey) {
  const server = new Server(
    { name: 'zonewise-mcp', version: '1.0.0' },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args = {} } = request.params;

    const handler = HANDLERS[name];
    if (!handler) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: `Unknown tool: ${name}` }) }], isError: true };
    }

    let customerRecord;
    try {
      const key = resolveApiKey(apiKey);
      customerRecord = await validateKey(key);
      assertTier(customerRecord, 's3'); // zoning tools are S3
    } catch (err) {
      if (err instanceof AuthError || err.isAuthError) {
        return {
          content: [{ type: 'text', text: JSON.stringify({ error: err.message, code: 'AUTH_ERROR' }) }],
          isError: true,
        };
      }
      throw err;
    }

    let result;
    let toolError = false;
    try {
      result = await handler(args);
    } catch (err) {
      result = { error: err.message, tool: name };
      toolError = true;
    }

    recordBilling({ toolName: 'check_zoning', customerRecord, params: args, county: args.county });

    return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }], isError: toolError };
  });

  return server;
}

export async function startStdio(apiKey) {
  const server = createServer(apiKey);
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write('[zonewise-mcp] Server started (stdio)\n');
}
