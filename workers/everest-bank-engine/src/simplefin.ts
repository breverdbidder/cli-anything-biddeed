// SimpleFIN Bridge connector (issue #19749 Part 2). Protocol: https://www.simplefin.org/protocol.html
//   1. Setup token = base64 of a one-time claim URL.
//   2. POST (empty body) to the claim URL -> plain-text Access URL with Basic Auth credentials
//      embedded in its userinfo component, e.g. https://user:pass@bridge.simplefin.org/simplefin
//   3. GET {access_url}/accounts?start-date=&end-date= (Basic Auth) -> accounts + transactions.
//
// The access URL is the durable credential (no separate refresh/access-token pair like Plaid) --
// it is stored ONLY in vault as `simplefin_access_url`, exactly once, and never printed or
// returned in any response body (issue #19749: "Never print tokens").

import type { Env } from "./env";
import { getVaultSecret, setVaultSecret, rpc, logFinanceOps } from "./db";
import { fallbackTransactionId } from "./importUtils";

const VAULT_KEY = "simplefin_access_url";

export interface ClaimResult {
  status: "VERIFIED" | "BLOCKED";
  claim_url?: string;
  error?: string;
}

export async function claimSetupToken(env: Env, setupToken: string): Promise<ClaimResult> {
  let claimUrl: string;
  try {
    claimUrl = atob(setupToken.trim());
  } catch {
    return { status: "BLOCKED", error: "setup token is not valid base64" };
  }
  if (!/^https?:\/\//i.test(claimUrl)) {
    return { status: "BLOCKED", error: "decoded setup token is not a URL" };
  }

  let res: Response;
  try {
    res = await fetch(claimUrl, { method: "POST" });
  } catch (err: any) {
    return { status: "BLOCKED", error: `claim request failed: ${String(err?.message ?? err)}` };
  }
  if (!res.ok) {
    return { status: "BLOCKED", error: `claim endpoint returned HTTP ${res.status}` };
  }
  const accessUrl = (await res.text()).trim();
  if (!/^https?:\/\/[^:@/]+:[^@]+@/.test(accessUrl)) {
    // Redacted preview only (never the full body -- it may itself be a valid credential in an
    // unexpected shape) to make a live diagnosis possible without printing a secret.
    const preview = accessUrl.length > 24 ? `${accessUrl.slice(0, 12)}...(${accessUrl.length} chars)...${accessUrl.slice(-4)}` : `(${accessUrl.length} chars, too short to preview safely)`;
    return { status: "BLOCKED", error: `claim response was not a Basic-Auth access URL -- got: ${preview}` };
  }

  await setVaultSecret(env, VAULT_KEY, accessUrl, "SimpleFIN Bridge access URL (Basic Auth embedded, issue #19749)");
  return { status: "VERIFIED", claim_url: claimUrl };
}

// The access URL's userinfo IS the Basic Auth credential -- pull it out once into a header
// rather than relying on fetch() to forward URL-embedded credentials (inconsistent across
// runtimes), then strip it from the URL used for the actual request.
function splitAccessUrl(accessUrl: string): { origin: string; headers: Record<string, string> } {
  const u = new URL(accessUrl);
  const authValue = btoa(`${decodeURIComponent(u.username)}:${decodeURIComponent(u.password)}`);
  u.username = "";
  u.password = "";
  return { origin: u.toString().replace(/\/$/, ""), headers: { Authorization: `Basic ${authValue}` } };
}

export interface SimplefinSyncResult {
  status: "VERIFIED" | "BLOCKED" | "SKIPPED";
  accounts?: number;
  upserted?: number;
  skipped_no_account?: number;
  error?: string;
}

// Sign convention (README.md): SimpleFIN's `amount` is positive=deposit/credit,
// negative=withdrawal/debit -- the same human convention as the WF CSV/OFX importer (see
// fileImport.ts), and negated the same way into this Worker's storage convention.
function toAmountCents(rawAmount: string): number {
  const value = Number.parseFloat(rawAmount);
  if (!Number.isFinite(value)) throw new Error(`unrecognized SimpleFIN amount: ${rawAmount}`);
  return -Math.round(value * 100);
}

interface SimplefinAccount {
  id: string;
  name: string;
  currency?: string;
  balance?: string;
  org?: { name?: string };
  transactions?: Array<{ id?: string; posted: number; amount: string; description?: string; pending?: boolean }>;
}

// SimpleFIN's protocol has no top-level "mask" field -- the account's last-4
// is embedded in its name instead, e.g. "BUSINESS CHECKING ...3519 (3519)".
// Previously this hardcoded `mask: null` on every sync, and
// bank_engine_upsert_accounts()'s unconditional `mask = excluded.mask` on
// ON CONFLICT blanked out the mask on every single 6h cron tick (issue
// #19768 finding -- confirmed live on 2026-09-03: all 4 real WF accounts had
// mask=NULL despite being populated at account-creation time). The SQL side
// now also coalesces against the existing value, but this is the actual
// source of a correct mask going forward.
function extractMask(name: string): string | null {
  return name.match(/\((\d{4})\)\s*$/)?.[1] ?? null;
}

export async function syncSimplefin(
  env: Env,
  params: { entityCode: string; startDate?: number; endDate?: number }
): Promise<SimplefinSyncResult> {
  const accessUrl = await getVaultSecret(env, VAULT_KEY);
  if (!accessUrl) {
    return { status: "SKIPPED", error: "no simplefin_access_url in vault -- call POST /simplefin/claim first" };
  }

  const { origin, headers } = splitAccessUrl(accessUrl);
  const qs = new URLSearchParams();
  if (params.startDate) qs.set("start-date", String(params.startDate));
  if (params.endDate) qs.set("end-date", String(params.endDate));
  const url = `${origin}/accounts${qs.toString() ? `?${qs.toString()}` : ""}`;

  let res: Response;
  try {
    res = await fetch(url, { headers });
  } catch (err: any) {
    const result: SimplefinSyncResult = { status: "BLOCKED", error: `accounts request failed: ${String(err?.message ?? err)}` };
    await logFinanceOps(env, params.entityCode, "bank_engine_simplefin_sync", "BLOCKED", null, result, "error", "19749");
    return result;
  }
  if (!res.ok) {
    const result: SimplefinSyncResult = { status: "BLOCKED", error: `SimpleFIN /accounts returned HTTP ${res.status}` };
    await logFinanceOps(env, params.entityCode, "bank_engine_simplefin_sync", "BLOCKED", null, result, "error", "19749");
    return result;
  }

  const data = (await res.json()) as { accounts?: SimplefinAccount[]; errors?: unknown[] };
  const accounts = data.accounts ?? [];

  let totalUpserted = 0;
  let totalSkipped = 0;

  for (const account of accounts) {
    const plaidItemId = `simplefin:${account.id}`;
    const plaidAccountId = `simplefin:${account.id}`;

    const connectionId = await rpc<string>(env, "bank_engine_upsert_connection_status", {
      p_plaid_item_id: plaidItemId,
      p_entity_code: params.entityCode,
      p_institution_name: account.org?.name ?? null,
      p_status: "simplefin",
    });

    await rpc<number>(env, "bank_engine_upsert_accounts", {
      p_connection_id: connectionId,
      p_accounts: [
        {
          plaid_account_id: plaidAccountId,
          name: account.name,
          mask: extractMask(account.name),
          subtype: null,
          currency: account.currency ?? null,
          current_balance_cents: account.balance != null ? Math.round(Number.parseFloat(account.balance) * 100) : null,
          available_balance_cents: null,
        },
      ],
    });

    const upserts = await Promise.all(
      (account.transactions ?? []).map(async (t) => {
        const posted = new Date(t.posted * 1000).toISOString().slice(0, 10);
        const description = t.description ?? "";
        const plaidTransactionId = t.id
          ? `simplefin:${t.id}`
          : await fallbackTransactionId(posted, t.amount, description, account.id);
        return {
          plaid_account_id: plaidAccountId,
          plaid_transaction_id: plaidTransactionId,
          amount_cents: toAmountCents(t.amount),
          posted_on: posted,
          authorized_on: null,
          pending: t.pending ?? false,
          name: description || null,
          merchant_name: null,
          category: null,
          raw: { source: "simplefin", ...t },
        };
      })
    );

    if (upserts.length > 0) {
      const applyResult = await rpc<{ upserted: number; skipped_no_account: number }>(
        env,
        "bank_engine_import_transactions",
        { p_connection_id: connectionId, p_upserts: upserts }
      );
      totalUpserted += applyResult.upserted;
      totalSkipped += applyResult.skipped_no_account;
    }
  }

  const result: SimplefinSyncResult = {
    status: "VERIFIED",
    accounts: accounts.length,
    upserted: totalUpserted,
    skipped_no_account: totalSkipped,
  };
  await logFinanceOps(env, params.entityCode, "bank_engine_simplefin_sync", "VERIFIED", null, result, "info", "19749");
  return result;
}

// Cron entry point (wired into the existing 6h `scheduled` trigger alongside Plaid, issue
// #19749: "cron every 6h alongside Plaid sync" -- no new [triggers] cron needed, same tick).
// The cron has no caller to supply entity_code, so it reads back whichever entity_code the most
// recent status='simplefin' connection already used (bank_engine_simplefin_default_entity) --
// see that function's comment in the migration for why this doesn't try to support more than
// one SimpleFIN access URL / entity at a time.
export async function syncSimplefinCron(env: Env): Promise<SimplefinSyncResult> {
  const entityCode = await rpc<string | null>(env, "bank_engine_simplefin_default_entity", {});
  if (!entityCode) {
    return { status: "SKIPPED", error: "no SimpleFIN connections yet -- /simplefin/claim + /simplefin/sync never run" };
  }
  return syncSimplefin(env, { entityCode });
}
