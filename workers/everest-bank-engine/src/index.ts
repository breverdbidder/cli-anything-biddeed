import { Hono } from "hono";
import type { Env } from "./env";
import { isAuthorized } from "./auth";
import { plaidClient } from "./plaid";
import { setVaultSecret, rpc, insertRow, logFinanceOps } from "./db";
import { syncAllActiveConnections, syncOneByItemId } from "./sync";
import { verifyPlaidWebhook } from "./webhookVerify";
import { renderLinkPage } from "./linkPage";
import { renderPrivacyPage } from "./privacyPage";

const app = new Hono<{ Bindings: Env }>();

app.get("/healthz", (c) => c.json({ ok: true, service: "everest-bank-engine", env: c.env.PLAID_ENV }));

// No auth (Plaid production questionnaire addendum, 2026-09-02) -- must be publicly reachable.
app.get("/privacy", (c) => c.html(renderPrivacyPage()));

// /webhook is exempt from the X-CFO-Secret gate (Plaid calls it directly) -- it is
// JWT-verified instead. Every other route requires the shared secret.
app.use("/link/*", async (c, next) => {
  if (!isAuthorized(c.req.raw, c.env.CFO_AGENT_SHARED_SECRET)) {
    return c.json({ error: "unauthorized", hint: "Pass the shared secret as header 'X-CFO-Secret' or ?key=" }, 401);
  }
  await next();
});
app.use("/sync", async (c, next) => {
  if (!isAuthorized(c.req.raw, c.env.CFO_AGENT_SHARED_SECRET)) {
    return c.json({ error: "unauthorized", hint: "Pass the shared secret as header 'X-CFO-Secret' or ?key=" }, 401);
  }
  await next();
});

app.get("/link", (c) => {
  const entityCode = c.req.query("entity_code");
  const key = c.req.query("key") ?? c.req.header("X-CFO-Secret") ?? "";
  if (!entityCode) {
    return c.text("Missing required query param: entity_code (e.g. /link?entity_code=everest_capital&key=...)", 400);
  }
  return c.html(renderLinkPage(entityCode, key));
});

app.post("/link/token", async (c) => {
  const body = await c.req.json<{ entity_code?: string }>().catch(() => ({}) as { entity_code?: string });
  if (!body.entity_code) return c.json({ error: "entity_code required" }, 400);

  const client = plaidClient(c.env);
  try {
    const resp = await client.linkTokenCreate({
      user: { client_user_id: body.entity_code },
      client_name: "Everest Bank Engine",
      products: ["transactions"] as any,
      country_codes: ["US"] as any,
      language: "en",
      webhook: c.env.PLAID_WEBHOOK_URL,
    });
    return c.json({ link_token: resp.data.link_token, expiration: resp.data.expiration });
  } catch (err: any) {
    return c.json({ error: String(err?.response?.data?.error_message ?? err?.message ?? err) }, 502);
  }
});

app.post("/link/exchange", async (c) => {
  const body = await c.req
    .json<{ public_token?: string; entity_code?: string; institution_name?: string | null }>()
    .catch(() => ({}) as any);
  if (!body.public_token || !body.entity_code) {
    return c.json({ error: "public_token and entity_code required" }, 400);
  }

  const client = plaidClient(c.env);
  try {
    const exchange = await client.itemPublicTokenExchange({ public_token: body.public_token });
    const { access_token, item_id } = exchange.data;

    // Access token lives ONLY in vault, never in a table column (issue #19737 scope item 1).
    await setVaultSecret(
      c.env,
      `plaid_access_${item_id}`,
      access_token,
      `Plaid access token for item ${item_id} (entity ${body.entity_code})`
    );

    const connectionId = await rpc<string>(c.env, "bank_engine_upsert_connection", {
      p_plaid_item_id: item_id,
      p_entity_code: body.entity_code,
      p_institution_name: body.institution_name ?? null,
    });

    const accountsResp = await client.accountsGet({ access_token });
    const accounts = accountsResp.data.accounts.map((a) => ({
      plaid_account_id: a.account_id,
      name: a.name,
      mask: a.mask ?? null,
      subtype: a.subtype ?? null,
      currency: a.balances.iso_currency_code ?? null,
      current_balance_cents: a.balances.current != null ? Math.round(a.balances.current * 100) : null,
      available_balance_cents: a.balances.available != null ? Math.round(a.balances.available * 100) : null,
    }));
    const accountsCount = await rpc<number>(c.env, "bank_engine_upsert_accounts", {
      p_connection_id: connectionId,
      p_accounts: accounts,
    });

    await logFinanceOps(
      c.env,
      body.entity_code,
      "bank_engine_link_exchange",
      "VERIFIED",
      item_id,
      { connection_id: connectionId, accounts_count: accountsCount },
      "info"
    );

    return c.json({ connection_id: connectionId, item_id, accounts_count: accountsCount });
  } catch (err: any) {
    const message = String(err?.response?.data?.error_message ?? err?.message ?? err);
    await logFinanceOps(c.env, body.entity_code, "bank_engine_link_exchange", "BLOCKED", null, { error: message }, "error");
    return c.json({ error: message }, 502);
  }
});

app.post("/sync", async (c) => {
  const body = await c.req.json<{ plaid_item_id?: string }>().catch(() => ({}) as any);
  if (body.plaid_item_id) {
    const result = await syncOneByItemId(c.env, body.plaid_item_id);
    if (!result) return c.json({ error: `no active connection for plaid_item_id ${body.plaid_item_id}` }, 404);
    return c.json({ results: [result] });
  }
  const results = await syncAllActiveConnections(c.env);
  return c.json({ results });
});

app.post("/webhook", async (c) => {
  const rawBody = await c.req.text();
  const verification = await verifyPlaidWebhook(c.env, c.req.raw, rawBody);
  if (!verification.ok) {
    return c.json({ error: "webhook verification failed", reason: verification.reason }, 401);
  }

  let payload: { webhook_type?: string; webhook_code?: string; item_id?: string };
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return c.json({ error: "invalid JSON body" }, 400);
  }

  await insertRow(c.env, "agent_ops_log", {
    dispatch_id: "19737",
    task: "bank_engine_webhook_received",
    status: "VERIFIED",
    evidence: payload,
    severity: "info",
  });

  const triggersSync = new Set(["SYNC_UPDATES_AVAILABLE", "DEFAULT_UPDATE", "INITIAL_UPDATE", "HISTORICAL_UPDATE"]);
  if (payload.webhook_type === "TRANSACTIONS" && payload.webhook_code && triggersSync.has(payload.webhook_code) && payload.item_id) {
    const result = await syncOneByItemId(c.env, payload.item_id);
    return c.json({ ok: true, synced: result ?? null });
  }

  return c.json({ ok: true, ignored: true });
});

export default {
  fetch: app.fetch,
  scheduled: async (_event: ScheduledEvent, env: Env, ctx: ExecutionContext) => {
    ctx.waitUntil(
      syncAllActiveConnections(env).then((results) =>
        insertRow(env, "agent_ops_log", {
          dispatch_id: "19737",
          task: "bank_engine_cron_sync",
          status: results.every((r) => r.status === "VERIFIED") ? "VERIFIED" : "PARTIAL",
          evidence: { results },
          severity: results.every((r) => r.status === "VERIFIED") ? "info" : "warn",
        })
      )
    );
  },
};
