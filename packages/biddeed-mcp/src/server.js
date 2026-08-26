import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';

import { validateKey, assertTier, resolveApiKey, AuthError } from './auth.js';
import { validateOAuthToken, resolveCustomerFromOAuth, isJwtLike } from './oauth.js';
import { recordBilling, checkChargeAllowance, logChargeOutcome } from './billing.js';
import { computeIdempotencyKey, claimIdempotencyKey, completeIdempotencyKey } from './idempotency.js';
import { captureToolCall } from './posthog.js';
import { logUsage } from './usage-log.js';
import { TOOL_STREAM } from './constants.js';
import { assertCountyCertified, resolveAuctionCounty } from './cert-gate.js';
import { DISCLAIMER_SHORT } from './disclaimer.js';
import { scanInput, scanOutput, logSecurityEvent, UNTRUSTED_DATA_NOTICE } from './security/guardrails.js';

// Tool schemas
import { schemas as discoverySchemas } from './tools/discovery.js';
import { schemas as qualificationSchemas } from './tools/qualification.js';
import { schemas as fusionSchemas } from './tools/fusion.js';
import { schemas as monitoringSchemas } from './tools/monitoring.js';
import { schemas as shapiraSchemas } from './tools/shapira.js';
import { schemas as marketSchemas } from './tools/market.js';
import { schemas as propertySchemas } from './tools/properties.js';
import { schemas as funnelSchemas } from './tools/funnel.js';

// Tool handlers
import * as discovery from './tools/discovery.js';
import * as qualification from './tools/qualification.js';
import * as fusion from './tools/fusion.js';
import * as monitoring from './tools/monitoring.js';
import * as shapira from './tools/shapira.js';
import * as market from './tools/market.js';
import * as properties from './tools/properties.js';
import * as funnel from './tools/funnel.js';

const ALL_SCHEMAS = [
  ...discoverySchemas,
  ...qualificationSchemas,
  ...fusionSchemas,
  ...monitoringSchemas,
  ...shapiraSchemas,
  ...marketSchemas,
  ...propertySchemas,
  ...funnelSchemas,
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
  // Growth Funnel (Sprint 0 — issue #19480)
  run_daily_funnel:             funnel.run_daily_funnel,
  get_top_auction_highlights:   funnel.get_top_auction_highlights,
  generate_funnel_content:      funnel.generate_funnel_content,
};

// GTM-22H — Gold Standard certification gate config, revised down from the
// blanket gate shipped in GTM-22F/c3d956d8. Product rule (Ariel, 2026-07-19):
// GATE where being wrong is legally or financially expensive, BADGE where
// the data is informational. Only decision-grade outputs a customer acts on
// with real money are gated here; S1 Discovery and the rest are ungated and
// stamp `certified` on every row instead (see cert-gate.js badgeRows/
// badgeCounty, wired into discovery.js/properties.js/qualification.js/
// market.js/monitoring.js). Do not add S1 Discovery tools back to this map.
// Strategies:
//   'county'            — args.county is the scoping input, gate directly.
//   'case_optional'      — only gate if args.case_number is present (the
//                          tool also has a pure-computation path with no DB
//                          row involved, e.g. underwrite_deal with no
//                          case_number — nothing county-scoped to gate).
// cert_required = true for exactly these 10 tools in v_tool_billing_resolved
// (GTM-22H Task C) — keep this map and that column in sync.
const CERT_GATE = {
  get_owner_intel:          'county',
  get_lien_stack:           'case_optional',
  check_zoning:             'county',
  underwrite_deal:          'case_optional',
  analyze_coliving:         'county',
  get_sales_comps:          'county',
  generate_deal_memo:       'county',
  get_bid_package:          'county',
  get_title_chain:          'county',
  predict_auction_outcome:  'county',
};

// Resolves the gate outcome for one call. Returns null when the call may
// proceed (nothing to gate, or the resolved county is certified); returns a
// ready-to-serialize error payload otherwise. Runs before checkChargeAllowance
// — never charge a customer for a county we are not going to deliver.
export async function evaluateCertGate(name, args) {
  const strategy = CERT_GATE[name];
  if (!strategy) return null;

  if (strategy === 'county') {
    return assertCountyCertified(args.county);
  }

  if (strategy === 'case_optional') {
    if (!args.case_number) return null;
    const resolved = await resolveAuctionCounty(args.case_number);
    return assertCountyCertified(resolved || args.county);
  }

  return null;
}

// GTM-22 Task 3, Failure B guard — isolated so the "unserializable result"
// path is directly unit-testable (circular refs, BigInt, etc.) without
// needing a real tool handler to produce one.
export function serializeToolResult(result) {
  try {
    return { ok: true, text: JSON.stringify(result, null, 2) };
  } catch {
    return { ok: false, text: null };
  }
}

// Test-only hook — lets integration tests substitute a tool handler (e.g. to
// force an unserializable result or a specific error) without touching the
// real tool implementations. Mirrors the _resetForTest convention in
// posthog.js. Never called from the production request path.
export function _setHandlerForTest(name, fn) {
  HANDLERS[name] = fn;
}

// Core call-tool logic, factored out of the SDK request handler so it can be
// exercised directly in tests (in particular the idempotency triple-fire
// test — GTM-22 Task 2/3). apiKey is the raw credential (bd_* key or OAuth
// bearer token); requestId is the JSON-RPC request id from the transport.
export async function handleToolCall(apiKey, name, args = {}, requestId) {
  const handler = HANDLERS[name];
  if (!handler) {
    return { content: [{ type: 'text', text: JSON.stringify({ error: `Unknown tool: ${name}` }) }], isError: true };
  }

  // Auth + tier check — bd_* API key and WorkOS OAuth bearer token are
  // parallel paths; the credential shape (JWT vs opaque bd_ string) decides
  // which validator runs.
  let customerRecord;
  let credential;
  const streamId = TOOL_STREAM[name] || 's1';
  try {
    credential = resolveApiKey(apiKey);
    customerRecord = isJwtLike(credential)
      ? await resolveCustomerFromOAuth(await validateOAuthToken(credential))
      : await validateKey(credential);
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

  // Prompt-injection guard — scans caller-supplied args before anything is
  // claimed/charged. Untrusted county-scraped text mostly re-enters via tool
  // *results* (see the output scan below), but caller args are scanned too
  // since nothing stops a client from passing injection-styled text directly.
  const inputScan = scanInput(args);
  if (!inputScan.safe) {
    logSecurityEvent('prompt_injection_blocked', `tool=${name} reason=${inputScan.reason}`, 'blocker');
    return {
      content: [{ type: 'text', text: JSON.stringify({ error: 'Request rejected: unsafe input detected', code: 'INPUT_REJECTED' }) }],
      isError: true,
    };
  }

  // GTM-22 Task 2 — idempotency. Derived from API key + tool + JSON-RPC id +
  // request body, so a client retry (same id, same body) after a 5xx never
  // bills or re-executes twice. Fails open on infra errors: an idempotency-
  // store outage must not block legitimate calls, only lose the dedup guarantee
  // for that one call.
  const idempotencyKey = computeIdempotencyKey({ credential, toolName: name, requestId, args });
  let claim;
  try {
    claim = await claimIdempotencyKey({ idempotencyKey, customerId: customerRecord.customer_id, toolName: name });
  } catch (err) {
    process.stderr.write(`[idempotency] ${name}: ${err.message}\n`);
    claim = { claimed: true };
  }

  if (!claim.claimed) {
    if (claim.cached) {
      return {
        content: [{ type: 'text', text: JSON.stringify(claim.cached.response, null, 2) }],
        isError: claim.cached.isError,
      };
    }
    return {
      content: [{ type: 'text', text: JSON.stringify({ error: 'Duplicate request already in flight — retry shortly', code: 'DUPLICATE_IN_FLIGHT' }) }],
      isError: true,
    };
  }

  // GTM-22F — Gold Standard certification gate. Must run before the charge
  // decision (Failure A pattern): never charge a customer for a county we
  // are not going to deliver. Fails closed inside evaluateCertGate/cert-gate.js.
  const gateResult = await evaluateCertGate(name, args);
  if (gateResult) {
    logChargeOutcome({ customerId: customerRecord.customer_id, toolName: name, streamId, outcome: 'blocked_cert_gate' });
    completeIdempotencyKey({ idempotencyKey, response: gateResult, isError: true }).catch(() => {});
    return {
      content: [{ type: 'text', text: JSON.stringify(gateResult) }],
      isError: true,
    };
  }

  // GTM-22 Task 3, Failure A — do not execute a billable tool unless the
  // charge/allowance check clears first (free data leak otherwise).
  let allowance;
  try {
    allowance = await checkChargeAllowance({ customerRecord, toolName: name, streamId });
  } catch (err) {
    process.stderr.write(`[billing] allowance check failed open for ${name}: ${err.message}\n`);
    allowance = { ok: true };
  }

  if (!allowance.ok) {
    logChargeOutcome({ customerId: customerRecord.customer_id, toolName: name, streamId, outcome: allowance.outcome });
    const errorResponse = { error: allowance.message, code: 'PAYMENT_REQUIRED' };
    completeIdempotencyKey({ idempotencyKey, response: errorResponse, isError: true }).catch(() => {});
    return {
      content: [{ type: 'text', text: JSON.stringify(errorResponse) }],
      isError: true,
    };
  }

  // Execute tool
  let result;
  let resultSummary = '';
  let toolError = false;
  let errorClass = null;
  const startedAt = Date.now();

  try {
    result = await handler(args);
    resultSummary = typeof result === 'object'
      ? (result.count !== undefined ? `count=${result.count}` : Object.keys(result).slice(0, 3).join(','))
      : String(result).slice(0, 100);
  } catch (err) {
    result = { error: err.message, tool: name };
    resultSummary = `ERROR: ${err.message.slice(0, 100)}`;
    toolError = true;
    errorClass = err.name || err.constructor?.name || 'Error';
  }
  const latencyMs = Date.now() - startedAt;

  // Secret-leak guard — scraped county documents or an upstream error string
  // could in principle echo back a credential; never let that reach the
  // caller or get cached for idempotent replay.
  const outputScan = scanOutput(result);
  if (!outputScan.safe) {
    logSecurityEvent('secret_leak_blocked', `tool=${name}`, 'blocker');
    result = { error: 'Response withheld: output failed security scan', tool: name };
    toolError = true;
  }

  // UPL/legal disclaimer — every tool response payload carries it, success
  // or tool-level error. Mutating `result` here (rather than the `response`
  // envelope below) means the disclaimer also rides along into whatever
  // gets cached for idempotent replay (completeIdempotencyKey below).
  if (result && typeof result === 'object' && !Array.isArray(result)) {
    result = { ...result, disclaimer: DISCLAIMER_SHORT, security_notice: UNTRUSTED_DATA_NOTICE };
  }

  // GTM-22 Task 3, Failure B — build and validate the wire payload BEFORE
  // charging. Billing for a response that fails to serialize is billing for
  // nothing the customer ever received. Record-then-commit, not
  // record-then-hope: nothing below this point is allowed to charge if this throws.
  const serialized = serializeToolResult(result);
  if (!serialized.ok) {
    logChargeOutcome({ customerId: customerRecord.customer_id, toolName: name, streamId, outcome: 'serialization_error' });
    const errorResponse = { error: 'Internal serialization error', tool: name };
    completeIdempotencyKey({ idempotencyKey, response: errorResponse, isError: true }).catch(() => {});
    return { content: [{ type: 'text', text: JSON.stringify(errorResponse) }], isError: true };
  }

  const response = {
    content: [{ type: 'text', text: serialized.text }],
    isError: toolError,
  };

  // Billing + idempotency completion fire only now that the response is
  // confirmed serializable — non-blocking w.r.t. the return below, but never
  // before this point.
  recordBilling({
    toolName: name,
    customerRecord,
    params: args,
    resultSummary,
    county: args.county || null,
    certStatus: name === 'predict_auction_outcome' ? (result?.cert_status || null) : null,
    modelVersion: name === 'predict_auction_outcome' ? (result?.model_version || null) : null,
  }).then((billingEventId) => {
    completeIdempotencyKey({ idempotencyKey, response: result, isError: toolError, billingEventId }).catch(() => {});
  }).catch((err) => {
    process.stderr.write(`[billing] ${name}: ${err.message}\n`);
    completeIdempotencyKey({ idempotencyKey, response: result, isError: toolError }).catch(() => {});
  });

  logChargeOutcome({
    customerId: customerRecord.customer_id,
    toolName: name,
    streamId,
    outcome: toolError ? 'tool_error' : 'charged',
  });

  // PostHog usage event — independent audit ledger alongside billing_events
  // (see posthog.js header comment for the reconciliation query). Queued +
  // batched; never awaited, never allowed to affect the tool response.
  captureToolCall({
    credential,
    toolName: name,
    tier: customerRecord.tier,
    latencyMs,
    county: args.county || null,
    cacheHit: result?.cache_hit ?? null,
    errorClass,
  });

  // GTM-22 SECURITY — anomaly-detection usage log. Non-blocking, mirrors the
  // captureToolCall hook above (see usage-log.js header for the ip_address
  // deviation).
  logUsage({
    credential,
    customerId: customerRecord.customer_id,
    toolName: name,
    county: args.county || null,
    latencyMs,
    success: !toolError,
    tier: customerRecord.tier,
  });

  return response;
}

export function createServer(apiKey) {
  const server = new Server(
    { name: 'biddeed-mcp', version: '1.0.0' },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: ALL_SCHEMAS,
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request, extra) => {
    const { name, arguments: args = {} } = request.params;
    return handleToolCall(apiKey, name, args, extra?.requestId);
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
