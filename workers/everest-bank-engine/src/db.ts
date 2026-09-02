// All Supabase access goes through PostgREST (REST + RPC) as service_role, never a direct
// Postgres connection -- SUPABASE_DB_PASSWORD / psql confirmed dead this session (matching
// decision_log 169/205/287). service_role has no USAGE on the `finance` schema (confirmed
// live, see supabase/migrations/20260902i_bank_engine_rpc.sql), so every finance.bank_* write
// goes through the bank_engine_* SECURITY DEFINER RPCs in `public` created by that migration.
//
// CREDENTIAL HANDLING (CLAUDE.md, permanent): this module reads/writes vault secrets via the
// sanctioned public.vault_secret / public.ecu_set_vault_secret RPCs only. A fetched secret
// value is held in memory only long enough to forward it to Plaid or to the vault write RPC --
// it is never logged, never echoed, never returned in an HTTP response body.

import type { Env } from "./env";

function restHeaders(env: Env, extra?: Record<string, string>): Record<string, string> {
  return {
    apikey: env.SUPABASE_SERVICE_ROLE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    "Content-Type": "application/json",
    ...extra,
  };
}

export async function rpc<T = unknown>(env: Env, fn: string, args: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: "POST",
    headers: restHeaders(env),
    body: JSON.stringify(args),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`rpc ${fn} failed: ${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

export async function insertRow(env: Env, table: string, row: Record<string, unknown>): Promise<void> {
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/${table}`, {
    method: "POST",
    headers: restHeaders(env, { Prefer: "return=minimal" }),
    body: JSON.stringify(row),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`insert ${table} failed: ${res.status} ${text}`);
  }
}

export async function getVaultSecret(env: Env, name: string): Promise<string | null> {
  const value = await rpc<string | null>(env, "vault_secret", { p_name: name });
  return value ?? null;
}

export async function setVaultSecret(env: Env, name: string, value: string, description?: string): Promise<void> {
  await rpc(env, "ecu_set_vault_secret", { p_name: name, p_value: value, p_description: description ?? null });
}

export async function logFinanceOps(
  env: Env,
  entity: string,
  task: string,
  status: "VERIFIED" | "PARTIAL" | "BLOCKED" | "UNTESTED",
  sourceEventId: string | null,
  evidence: object,
  severity: "info" | "warn" | "error" = "info"
): Promise<void> {
  await insertRow(env, "finance_ops_log", {
    dispatch_id: "19737",
    entity,
    task,
    status,
    source_event_id: sourceEventId,
    evidence,
    severity,
  });
}
