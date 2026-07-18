// GTM-22 Task 2 — idempotency keys on billable tool calls.
//
// Under stateless MCP (HTTP transport has no session state, and stdio
// clients retry on transport-level 5xx/timeout), a retried call must never
// bill twice for one logical request. The DB unique constraint on
// mcp_idempotency_keys.idempotency_key is the enforcement point — this
// module only decides who wins the race, never whether a duplicate is
// allowed through.
import { createHash } from 'crypto';
import { get, insert, patch } from './supabase.js';

const TTL_HOURS = 24;
const POLL_ATTEMPTS = 5;
const POLL_INTERVAL_MS = 200;

export function computeIdempotencyKey({ credential, toolName, requestId, args }) {
  const credentialHash = createHash('sha256').update(credential || '').digest('hex');
  const bodyHash = createHash('sha256').update(JSON.stringify(args ?? {})).digest('hex');
  return createHash('sha256')
    .update(`${credentialHash}:${toolName}:${String(requestId)}:${bodyHash}`)
    .digest('hex');
}

function isUniqueViolation(err) {
  return /23505|duplicate key/i.test(err.message || '');
}

// Claims the key for execution, or reports a duplicate. Returns:
//   { claimed: true }                              — this call owns execution
//   { claimed: false, cached: { response, isError } } — duplicate, serve cached response
//   { claimed: false, cached: null }                — duplicate still in flight after polling
export async function claimIdempotencyKey({ idempotencyKey, customerId, toolName }) {
  const expiresAt = new Date(Date.now() + TTL_HOURS * 60 * 60 * 1000).toISOString();

  try {
    await insert('mcp_idempotency_keys', {
      idempotency_key: idempotencyKey,
      customer_id: customerId,
      tool_name: toolName,
      status: 'pending',
      expires_at: expiresAt,
    });
    return { claimed: true };
  } catch (err) {
    if (!isUniqueViolation(err)) throw err;
  }

  return resolveDuplicate(idempotencyKey);
}

async function resolveDuplicate(idempotencyKey) {
  for (let attempt = 0; attempt < POLL_ATTEMPTS; attempt++) {
    const rows = await get(`mcp_idempotency_keys?idempotency_key=eq.${idempotencyKey}&limit=1`);
    const row = rows[0];

    if (!row || new Date(row.expires_at) < new Date()) {
      // Row vanished (cleaned up) or expired mid-race — treat as a fresh key.
      return { claimed: true };
    }

    if (row.status === 'completed') {
      patch('mcp_idempotency_keys', `idempotency_key=eq.${idempotencyKey}`, {
        duplicate_count: (row.duplicate_count || 0) + 1,
      }).catch(() => {});
      return { claimed: false, cached: { response: row.response_json, isError: row.is_error } };
    }

    if (attempt < POLL_ATTEMPTS - 1) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
  }
  return { claimed: false, cached: null };
}

export async function completeIdempotencyKey({ idempotencyKey, response, isError, billingEventId }) {
  await patch('mcp_idempotency_keys', `idempotency_key=eq.${idempotencyKey}`, {
    status: 'completed',
    response_json: response,
    is_error: !!isError,
    billing_event_id: billingEventId || null,
    completed_at: new Date().toISOString(),
  });
}
