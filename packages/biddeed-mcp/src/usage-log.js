// Per-tool-call usage log for behavioural anomaly detection (GTM-22 SECURITY,
// 2026-08-03) — feeds public.detect_usage_anomalies() (pg_cron, */30min).
// Fire-and-forget, same shape as billing.js logChargeOutcome: never awaited
// by the caller, never allowed to affect the tool response or its latency.
//
// ip_address is not threaded through here — the MCP SDK's CallToolRequestSchema
// handler (server.js) never receives the raw HTTP request, only requestId, so
// it is logged as null. Wiring it would mean threading `req` through auth/
// cert-gate/billing/idempotency, which is out of scope for this change.
import { insert } from './supabase.js';
import { hashDistinctId } from './posthog.js';

export function logUsage({ credential, customerId, toolName, county, latencyMs, success, tier }) {
  insert('mcp_usage_log', {
    api_key_hash: hashDistinctId(credential),
    customer_id: customerId || null,
    tool_name: toolName,
    county_slug: county || null,
    ip_address: null,
    response_ms: latencyMs,
    success,
    tier_id: tier || null,
  }).catch(err => {
    process.stderr.write(`[usage-log] ${toolName}: ${err.message}\n`);
  });
}
