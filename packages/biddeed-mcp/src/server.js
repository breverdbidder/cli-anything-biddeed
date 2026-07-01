import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';

import { validateKey, assertTier, resolveApiKey, AuthError } from './auth.js';
import { validateOAuthToken, resolveCustomerFromOAuth, isJwtLike } from './oauth.js';
import { recordBilling } from './billing.js';
import { TOOL_STREAM } from './constants.js';

// Tool schemas
import { schemas as discoverySchemas } from './tools/discovery.js';
import { schemas as qualificationSchemas } from './tools/qualification.js';
import { schemas as fusionSchemas } from './tools/fusion.js';
import { schemas as monitoringSchemas } from './tools/monitoring.js';
import { schemas as shapiraSchemas } from './tools/shapira.js';
import { schemas as marketSchemas } from './tools/market.js';
import { schemas as propertySchemas } from './tools/properties.js';

// Tool handlers
import * as discovery from './tools/discovery.js';
import * as qualification from './tools/qualification.js';
import * as fusion from './tools/fusion.js';
import * as monitoring from './tools/monitoring.js';
import * as shapira from './tools/shapira.js';
import * as market from './tools/market.js';
import * as properties from './tools/properties.js';

const ALL_SCHEMAS = [
  ...discoverySchemas,
  ...qualificationSchemas,
  ...fusionSchemas,
  ...monitoringSchemas,
  ...shapiraSchemas,
  ...marketSchemas,
  ...propertySchemas,
];

const HANDLERS = {
  // S1 Discovery
  search_auctions:          discovery.search_auctions,
  get_auction_detail:       discovery.get_auction_detail,
  browse_deals:             discovery.browse_deals,
  get_deposit_requirements: discovery.get_deposit_requirements,
  find_local_partners:      discovery.find_local_partners,
  // S2 Qualification
  search_distressed:        qualification.search_distressed,
  get_owner_intel:          qualification.get_owner_intel,
  get_lien_stack:           qualification.get_lien_stack,
  get_rent_estimate:        qualification.get_rent_estimate,
  analyze_market:           qualification.analyze_market,
  get_zip_market_data:      qualification.get_zip_market_data,
  // S3 Fusion
  check_zoning:             fusion.check_zoning,
  underwrite_deal:          fusion.underwrite_deal,
  analyze_coliving:         fusion.analyze_coliving,
  get_sales_comps:          fusion.get_sales_comps,
  generate_deal_memo:       fusion.generate_deal_memo,
  get_bid_package:          fusion.get_bid_package,
  get_title_chain:          fusion.get_title_chain,
  // S4 Monitoring
  watch_auction:            monitoring.watch_auction,
  // S5 Shapira Formula
  predict_auction_outcome:  shapira.predict_auction_outcome,
  // Market data
  get_interest_rate:        market.get_interest_rate,
  get_market_data:          market.get_market_data,
  skip_trace:               market.skip_trace,
  // Properties
  search_properties:        properties.search_properties,
  get_property_detail:      properties.get_property_detail,
};

export function createServer(apiKey) {
  const server = new Server(
    { name: 'biddeed-mcp', version: '1.0.0' },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: ALL_SCHEMAS,
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args = {} } = request.params;

    const handler = HANDLERS[name];
    if (!handler) {
      return { content: [{ type: 'text', text: JSON.stringify({ error: `Unknown tool: ${name}` }) }], isError: true };
    }

    // Auth + tier check — bd_* API key and WorkOS OAuth bearer token are
    // parallel paths; the credential shape (JWT vs opaque bd_ string) decides
    // which validator runs.
    let customerRecord;
    try {
      const credential = resolveApiKey(apiKey);
      customerRecord = isJwtLike(credential)
        ? await resolveCustomerFromOAuth(await validateOAuthToken(credential))
        : await validateKey(credential);
      const streamId = TOOL_STREAM[name] || 's1';
      assertTier(customerRecord, streamId);
    } catch (err) {
      if (err instanceof AuthError || err.isAuthError) {
        return {
          content: [{ type: 'text', text: JSON.stringify({ error: err.message, code: 'AUTH_ERROR' }) }],
          isError: true,
        };
      }
      throw err;
    }

    // Execute tool
    let result;
    let resultSummary = '';
    let toolError = false;

    try {
      result = await handler(args);
      resultSummary = typeof result === 'object'
        ? (result.count !== undefined ? `count=${result.count}` : Object.keys(result).slice(0, 3).join(','))
        : String(result).slice(0, 100);
    } catch (err) {
      result = { error: err.message, tool: name };
      resultSummary = `ERROR: ${err.message.slice(0, 100)}`;
      toolError = true;
    }

    // Record billing (non-blocking, async)
    recordBilling({
      toolName: name,
      customerRecord,
      params: args,
      resultSummary,
      county: args.county || null,
      certStatus: name === 'predict_auction_outcome' ? (result?.cert_status || null) : null,
    });

    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
      isError: toolError,
    };
  });

  return server;
}

// Stdio transport entry point
export async function startStdio(apiKey) {
  const server = createServer(apiKey);
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write('[biddeed-mcp] Server started (stdio)\n');
}
