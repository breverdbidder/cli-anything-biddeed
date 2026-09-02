// Core /transactions/sync loop, shared by the POST /sync route, the webhook handler, and the
// 6h cron trigger. Cursor is persisted (via bank_engine_apply_sync, which also stamps
// last_synced_at + status='active') ONLY after the whole added/modified/removed page loop for
// this invocation completes without throwing -- a mid-loop failure leaves the previously
// stored cursor untouched so the next run resumes from the same known-good point rather than
// silently dropping a page (issue #19737 scope item 1: "persist cursor only after success").

import type { Env } from "./env";
import { plaidClient } from "./plaid";
import { getVaultSecret, rpc, logFinanceOps } from "./db";

export interface ActiveConnection {
  id: string;
  plaid_item_id: string;
  cursor: string | null;
  entity_code: string;
}

export interface SyncResult {
  connection_id: string;
  plaid_item_id: string;
  added: number;
  modified: number;
  removed: number;
  upserted: number;
  skipped_no_account: number;
  status: "VERIFIED" | "BLOCKED";
  error?: string;
}

// amount_cents convention (documented in README.md + the #19716 migration column comment):
// Plaid's raw `amount` is positive for money LEAVING the account (outflow) and negative for
// money entering it (inflow). We store amount_cents = round(amount * 100) with the SIGN
// UNCHANGED -- never flipped -- so downstream recon rules (track D) have one unambiguous
// convention to read.
function shapeTransaction(t: any) {
  return {
    plaid_account_id: t.account_id,
    plaid_transaction_id: t.transaction_id,
    amount_cents: Math.round(t.amount * 100),
    posted_on: t.date,
    authorized_on: t.authorized_date ?? null,
    pending: t.pending ?? false,
    name: t.name ?? null,
    merchant_name: t.merchant_name ?? null,
    category: Array.isArray(t.category)
      ? t.category
      : t.personal_finance_category?.primary
        ? [t.personal_finance_category.primary]
        : null,
    raw: t,
  };
}

export async function syncConnection(env: Env, connection: ActiveConnection): Promise<SyncResult> {
  const client = plaidClient(env);
  const accessToken = await getVaultSecret(env, `plaid_access_${connection.plaid_item_id}`);
  if (!accessToken) {
    const result: SyncResult = {
      connection_id: connection.id,
      plaid_item_id: connection.plaid_item_id,
      added: 0,
      modified: 0,
      removed: 0,
      upserted: 0,
      skipped_no_account: 0,
      status: "BLOCKED",
      error: "no plaid_access_<item_id> secret in vault for this connection",
    };
    await logFinanceOps(env, connection.entity_code, "bank_engine_sync", "BLOCKED", connection.plaid_item_id, result, "error");
    return result;
  }

  let cursor: string | undefined = connection.cursor ?? undefined;
  let hasMore = true;
  const addedAll: any[] = [];
  const modifiedAll: any[] = [];
  const removedAll: string[] = [];
  let latestCursor = cursor;

  try {
    while (hasMore) {
      const resp = await client.transactionsSync({
        access_token: accessToken,
        cursor,
        count: 500,
      });
      const data = resp.data;
      addedAll.push(...data.added);
      modifiedAll.push(...data.modified);
      removedAll.push(...data.removed.map((r: any) => r.transaction_id));
      hasMore = data.has_more;
      cursor = data.next_cursor;
      latestCursor = data.next_cursor;
    }
  } catch (err: any) {
    const result: SyncResult = {
      connection_id: connection.id,
      plaid_item_id: connection.plaid_item_id,
      added: addedAll.length,
      modified: modifiedAll.length,
      removed: removedAll.length,
      upserted: 0,
      skipped_no_account: 0,
      status: "BLOCKED",
      error: String(err?.response?.data?.error_message ?? err?.message ?? err),
    };
    await logFinanceOps(env, connection.entity_code, "bank_engine_sync", "BLOCKED", connection.plaid_item_id, result, "error");
    return result;
  }

  const upserts = [...addedAll, ...modifiedAll].map(shapeTransaction);

  const applyResult = await rpc<{ upserted: number; skipped_no_account: number; removed: number }>(
    env,
    "bank_engine_apply_sync",
    { p_connection_id: connection.id, p_upserts: upserts, p_removed: removedAll, p_cursor: latestCursor }
  );

  const result: SyncResult = {
    connection_id: connection.id,
    plaid_item_id: connection.plaid_item_id,
    added: addedAll.length,
    modified: modifiedAll.length,
    removed: applyResult.removed,
    upserted: applyResult.upserted,
    skipped_no_account: applyResult.skipped_no_account,
    status: "VERIFIED",
  };
  await logFinanceOps(env, connection.entity_code, "bank_engine_sync", "VERIFIED", connection.plaid_item_id, result, "info");
  return result;
}

export async function syncAllActiveConnections(env: Env): Promise<SyncResult[]> {
  const connections = await rpc<ActiveConnection[]>(env, "bank_engine_list_active_connections", {});
  const results: SyncResult[] = [];
  for (const c of connections) {
    results.push(await syncConnection(env, c));
  }
  return results;
}

export async function syncOneByItemId(env: Env, plaidItemId: string): Promise<SyncResult | null> {
  const connections = await rpc<ActiveConnection[]>(env, "bank_engine_list_active_connections", {});
  const match = connections.find((c) => c.plaid_item_id === plaidItemId);
  if (!match) return null;
  return syncConnection(env, match);
}
