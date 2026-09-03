// POST /import orchestration (issue #19749 Part 1): parse a WF CSV or QFX/OFX file, shape into
// the same upsert shape #19737's Plaid sync uses, and write via the new file/SimpleFIN-only
// bank_engine_upsert_connection_status / bank_engine_import_transactions RPCs (see
// supabase/migrations/20260902m_bank_file_simplefin_rpc.sql) -- never bank_engine_apply_sync,
// which forces status='active' and would put this connection in the Plaid cron's sweep.

import type { Env } from "./env";
import { rpc, logFinanceOps } from "./db";
import { parseWfCsv } from "./csvImport";
import { parseOfx, looksLikeOfx } from "./ofxImport";
import { fallbackTransactionId, type ParsedTxn } from "./importUtils";

export interface FileImportResult {
  connection_id: string;
  format: "csv" | "ofx";
  parsed: number;
  upserted: number;
  skipped_no_account: number;
  status: "VERIFIED" | "BLOCKED";
  error?: string;
  // Issue #19770 scope item 3: "After import, automatically run categorize -> post ->
  // finance.recon_run(null,'2026-01-01') and show the new coverage." daily_close_summary is
  // whatever public.bank_engine_run_daily_close() returns (categorize/post/recon/balance-check,
  // #19765's existing pipeline reused here rather than re-implemented); coverage is the fresh
  // finance.v_data_coverage snapshot taken right after. Both are best-effort: a failure here
  // does not flip the import itself to BLOCKED (the file WAS imported; the pipeline step is
  // reported separately so a partial failure is visible, not silently retried as a full import).
  daily_close_summary?: unknown;
  coverage?: unknown;
}

// Sign convention -- the single point of negation for this pipeline (documented in README.md).
// WF CSV and OFX/QFX both use "negative = debit / positive = credit" (the source file's own,
// human-intuitive convention). This Worker's storage convention
// (finance.bank_transactions.amount_cents, set by #19737's Plaid sync) is Plaid's RAW
// convention instead -- positive = outflow, negative = inflow, the opposite sign. Negate once
// here so every downstream reader (recon, dashboards) sees one convention regardless of source.
function toAmountCents(rawAmount: string): number {
  const value = Number.parseFloat(rawAmount);
  if (!Number.isFinite(value)) throw new Error(`unrecognized amount: ${rawAmount}`);
  return -Math.round(value * 100);
}

async function shapeTransaction(t: ParsedTxn, plaidAccountId: string, mask: string) {
  const plaidTransactionId = t.fitId ?? (await fallbackTransactionId(t.date, t.rawAmount, t.description, mask));
  return {
    plaid_account_id: plaidAccountId,
    plaid_transaction_id: plaidTransactionId,
    amount_cents: toAmountCents(t.rawAmount),
    posted_on: t.date,
    authorized_on: null,
    pending: false,
    name: t.description || null,
    merchant_name: null,
    category: null,
    raw: { source: "file_import", ...t },
  };
}

export async function importFile(
  env: Env,
  params: { entityCode: string; accountLabel: string; mask: string; text: string; filename?: string }
): Promise<FileImportResult> {
  const format: "csv" | "ofx" = looksLikeOfx(params.text, params.filename) ? "ofx" : "csv";

  let parsedRaw: ParsedTxn[];
  try {
    parsedRaw = format === "ofx" ? parseOfx(params.text) : parseWfCsv(params.text);
  } catch (err: any) {
    return {
      connection_id: "",
      format,
      parsed: 0,
      upserted: 0,
      skipped_no_account: 0,
      status: "BLOCKED",
      error: `parse failed: ${String(err?.message ?? err)}`,
    };
  }

  if (parsedRaw.length === 0) {
    return {
      connection_id: "",
      format,
      parsed: 0,
      upserted: 0,
      skipped_no_account: 0,
      status: "BLOCKED",
      error: "no transactions parsed from file",
    };
  }

  const plaidItemId = `file:${params.mask}`;
  const plaidAccountId = `file:${params.mask}`;

  const connectionId = await rpc<string>(env, "bank_engine_upsert_connection_status", {
    p_plaid_item_id: plaidItemId,
    p_entity_code: params.entityCode,
    p_institution_name: "Wells Fargo",
    p_status: "manual",
  });

  await rpc<number>(env, "bank_engine_upsert_accounts", {
    p_connection_id: connectionId,
    p_accounts: [
      {
        plaid_account_id: plaidAccountId,
        name: params.accountLabel,
        mask: params.mask,
        subtype: null,
        currency: "USD",
        current_balance_cents: null,
        available_balance_cents: null,
      },
    ],
  });

  const upserts = await Promise.all(parsedRaw.map((t) => shapeTransaction(t, plaidAccountId, params.mask)));

  const applyResult = await rpc<{ upserted: number; skipped_no_account: number }>(
    env,
    "bank_engine_import_transactions",
    { p_connection_id: connectionId, p_upserts: upserts }
  );

  const result: FileImportResult = {
    connection_id: connectionId,
    format,
    parsed: parsedRaw.length,
    upserted: applyResult.upserted,
    skipped_no_account: applyResult.skipped_no_account,
    status: "VERIFIED",
  };

  // Issue #19770 scope item 3 -- reuses #19765's existing daily_close pipeline (sync/categorize/
  // post/recon/balance-check) rather than re-implementing categorize->post->recon_run by hand.
  // Best-effort: caught separately so a pipeline hiccup doesn't relabel a successful import as
  // BLOCKED -- the rows are already safely upserted at this point.
  try {
    result.daily_close_summary = await rpc(env, "bank_engine_run_daily_close", { p_from: "2026-01-01" });
  } catch (err: any) {
    result.daily_close_summary = { error: String(err?.message ?? err) };
  }
  try {
    result.coverage = await rpc(env, "bank_engine_data_coverage", {});
  } catch (err: any) {
    result.coverage = { error: String(err?.message ?? err) };
  }

  await logFinanceOps(env, params.entityCode, "bank_engine_file_import", "VERIFIED", plaidItemId, result, "info", "19749");
  return result;
}
