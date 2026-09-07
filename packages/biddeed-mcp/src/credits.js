// Token/credit wallet billing (ChatGPT/Claude-style), Ariel directive Aug 31
// 2026. Layers alongside the existing fixed tier-gate model in billing.js —
// does NOT replace checkChargeAllowance in this issue; both run. Pricing is
// resolved server-side in mcp_credit_spend (mcp_credit_pricing table) —
// never hardcode a per-tool credit amount here, mirrors the zero-deploy-
// pricing-change pattern used for v_s5_report_template.
//
// Fails CLOSED on infra errors, unlike checkChargeAllowance's fail-open:
// the whole point of a prepaid wallet is that a customer with 0 balance
// must never get a free call just because the RPC round-trip errored. If
// mcp_credit_spend itself is unreachable, block the call and let the
// customer retry — this mirrors evaluateCertGate's fail-closed posture, not
// billing.js's fail-open posture (that guards a monthly *allowance*, not a
// balance that can go negative).
import { rpc } from './supabase.js';

export async function checkAndSpendCredits({ customerRecord, toolName, streamId, mcaId = null }) {
  let result;
  try {
    // connect-only: mcp_credit_spend has no dedup key of its own (dedup for
    // the whole tool call lives in idempotency.js) — retrying it after an
    // ambiguous response-lost failure could double-charge a single logical
    // call, so only retry when we're sure the request never reached Postgres.
    result = await rpc('mcp_credit_spend', {
      p_customer_id: customerRecord.customer_id,
      p_tool_name: toolName,
      p_stream_id: streamId,
      p_mca_id: mcaId,
    }, { retryMode: 'connect-only' });
  } catch (err) {
    process.stderr.write(`[credits] mcp_credit_spend failed for ${toolName}: ${err.message}\n`);
    return {
      ok: false,
      outcome: 'blocked_credits_unavailable',
      message: 'Credit balance could not be verified right now. Retry shortly.',
    };
  }

  if (!result.ok) {
    return {
      ok: false,
      outcome: 'blocked_insufficient_credits',
      message: result.message || 'Insufficient credits. Top up at biddeed.ai/upgrade',
      balance: result.balance,
      cost: result.cost,
    };
  }

  return { ok: true, charged: result.charged, cost: result.cost, balance: result.balance };
}
