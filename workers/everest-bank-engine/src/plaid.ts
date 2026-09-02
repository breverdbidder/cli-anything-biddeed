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
