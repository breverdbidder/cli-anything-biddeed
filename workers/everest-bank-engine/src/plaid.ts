// DEVIATION from issue #19737 scope ("plaid npm SDK"): the official `plaid` package's
// PlaidApi class is built on axios, whose default transport sets a `cache` option the
// Cloudflare Workers fetch implementation rejects outright -- confirmed live 2026-09-02,
// POST /link/token on the deployed Worker returned HTTP 502 with body
// `{"error":"Unsupported cache mode: default"}` even with `compatibility_flags =
// ["nodejs_compat"]` set. This is a documented axios-on-Workers incompatibility, not a config
// mistake in this Worker. Plaid's API surface is plain JSON-over-HTTPS with no signing beyond
// client_id/secret in the body, so this thin wrapper hits the REST endpoints directly with the
// platform's native `fetch` instead of pulling in axios at all. Method names/shapes below
// mirror the subset of the `plaid` SDK's PlaidApi this Worker needs
// (linkTokenCreate/itemPublicTokenExchange/accountsGet/transactionsSync/
// webhookVerificationKeyGet), each returning `{ data }` like the SDK does, so the rest of this
// codebase (sync.ts, webhookVerify.ts, index.ts) reads identically to how it would against the
// real SDK.

import type { Env } from "./env";

const BASE_URL: Record<string, string> = {
  sandbox: "https://sandbox.plaid.com",
  production: "https://production.plaid.com",
};

class PlaidRestClient {
  private baseUrl: string;
  private clientId: string;
  private secret: string;

  constructor(env: Env) {
    this.baseUrl = BASE_URL[env.PLAID_ENV] ?? BASE_URL.sandbox;
    this.clientId = env.PLAID_CLIENT_ID;
    this.secret = env.PLAID_SECRET;
  }

  private async post<T = any>(path: string, body: Record<string, unknown>): Promise<{ data: T }> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: this.clientId, secret: this.secret, ...body }),
    });
    const data = (await res.json()) as any;
    if (!res.ok) {
      const err: any = new Error(data?.error_message ?? `Plaid ${path} failed (${res.status})`);
      err.plaid = data;
      throw err;
    }
    return { data };
  }

  linkTokenCreate(body: Record<string, unknown>) {
    return this.post("/link/token/create", body);
  }

  itemPublicTokenExchange(body: { public_token: string }) {
    return this.post<{ access_token: string; item_id: string }>("/item/public_token/exchange", body);
  }

  accountsGet(body: { access_token: string }) {
    return this.post<{ accounts: any[] }>("/accounts/get", body);
  }

  transactionsSync(body: { access_token: string; cursor?: string; count?: number }) {
    return this.post<{ added: any[]; modified: any[]; removed: any[]; next_cursor: string; has_more: boolean }>(
      "/transactions/sync",
      body
    );
  }

  webhookVerificationKeyGet(body: { key_id: string }) {
    return this.post<{ key: Record<string, unknown> }>("/webhook_verification_key/get", body);
  }
}

export function plaidClient(env: Env): PlaidRestClient {
  return new PlaidRestClient(env);
}

export interface PlaidProductionStatus {
  checked_at: string;
  http_status: number;
  plaid_error_type: string | null;
  plaid_error_code: string | null;
  plaid_error_message: string | null;
  production_access_state: "PENDING" | "LIVE_OR_CHANGED" | "UNKNOWN";
}

// Issue #19770 step 1: "call /link/token/create against https://production.plaid.com with the
// vault plaid_client_id + the sandbox secret -> expect INVALID_API_KEYS while pending; a
// different error or success means status changed." This always targets production.plaid.com
// directly (not env.PLAID_ENV's base URL) using whatever client_id/secret this Worker currently
// holds -- today that's the sandbox pair, since PLAID_ENV=sandbox. Never returns the client_id or
// secret in the response, only Plaid's own (non-secret) error envelope.
export async function checkPlaidProductionStatus(env: Env): Promise<PlaidProductionStatus> {
  const res = await fetch("https://production.plaid.com/link/token/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: env.PLAID_CLIENT_ID,
      secret: env.PLAID_SECRET,
      user: { client_user_id: "plaid-production-status-check" },
      client_name: "Everest Bank Engine",
      products: ["transactions"],
      country_codes: ["US"],
      language: "en",
    }),
  });
  const data = (await res.json().catch(() => ({}))) as any;
  const errorCode: string | null = data?.error_code ?? null;
  return {
    checked_at: new Date().toISOString(),
    http_status: res.status,
    plaid_error_type: data?.error_type ?? null,
    plaid_error_code: errorCode,
    plaid_error_message: data?.error_message ?? null,
    production_access_state: res.ok ? "LIVE_OR_CHANGED" : errorCode === "INVALID_API_KEYS" ? "PENDING" : "UNKNOWN",
  };
}
