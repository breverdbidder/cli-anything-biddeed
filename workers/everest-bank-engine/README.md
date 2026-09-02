# everest-bank-engine

CFO v1 Issue C (CP4), issue [#19737](https://github.com/breverdbidder/cli-anything-biddeed/issues/19737).
Cloudflare Worker (Hono + TypeScript) that connects Plaid Link and `/transactions/sync` into
`finance.bank_connections` / `finance.bank_accounts` / `finance.bank_transactions`. **Sandbox
first** — `PLAID_ENV=sandbox` today; going to production is a one-secret swap
(`PLAID_ENV` + `PLAID_SECRET`), zero code change.

## Routes

| Route | Auth | Purpose |
|---|---|---|
| `GET /link?entity_code=<code>&key=<secret>` | `X-CFO-Secret` / `?key=` | Minimal HTML page that loads Plaid Link JS and drives the link flow. |
| `POST /link/token` | `X-CFO-Secret` | Creates a Plaid Link token (`products=[transactions]`, `country_codes=[US]`). |
| `POST /link/exchange` | `X-CFO-Secret` | Exchanges a `public_token` for an `access_token`, stores it in vault, inserts `finance.bank_connections` + `finance.bank_accounts`. |
| `POST /sync` | `X-CFO-Secret` | Runs `/transactions/sync` for one connection (`{plaid_item_id}`) or all active connections. |
| `POST /webhook` | Plaid JWT (`Plaid-Verification` header) — **not** `X-CFO-Secret` | Plaid webhook receiver. `SYNC_UPDATES_AVAILABLE`/`DEFAULT_UPDATE`/etc. trigger a sync for that item. |
| `GET /healthz` | none | Liveness probe. |
| `GET /privacy` | none | Renders §9 of `docs/security/EVEREST_INFOSEC_POLICY.md` as plain HTML (Plaid production questionnaire, 2026-09-02 addendum). Linked from the `/link` page footer. |

Cron trigger (`wrangler.toml` `[triggers]`) runs every 6h and syncs every `status='active'`
connection.

## Auth

Same single access-key gate as `everest-cfo-agent` (`X-CFO-Secret` header, byte-for-byte port
of that Worker's `auth.ts`) — see `src/auth.ts`. **Known gap**: GitHub Actions secrets are
write-only and no sanctioned vault accessor covers a name outside the
`cli_anything_*`/`everest_*_pat` allow-list (CLAUDE.md CREDENTIAL HANDLING), so this repo's
`CFO_AGENT_SHARED_SECRET` is a freshly generated value, not a copy of the one already set on
`everest-cfo-agent`. The two Workers do not yet share one literal key — Ariel needs to align
them manually (paste the same value into both repos' secrets) if cross-Worker calls are ever
needed. Until then, each Worker's own `X-CFO-Secret` gate is independently correct.

## Where the access token lives

`access_token` is **never** written to a table column. It is stored in Supabase Vault as
`plaid_access_<item_id>` via the sanctioned `public.ecu_set_vault_secret` RPC (service_role
only), and read back via `public.vault_secret`. `finance.bank_connections` stores only
`plaid_item_id`, never the token.

## Why writes go through `public.bank_engine_*` RPCs, not direct table inserts

`service_role` has no `USAGE` grant on the `finance` schema (confirmed live 2026-09-02 —
`cfo_agent_ro` is the only role with `finance` schema access, and it is read-only per #19716).
Since this Worker talks to Supabase over PostgREST as `service_role` (no direct Postgres
connection is possible — `SUPABASE_DB_PASSWORD`/psql is confirmed dead, decision_log
169/205/287), every write into `finance.bank_*` goes through a `SECURITY DEFINER` wrapper
function in `public` (`bank_engine_upsert_connection`, `bank_engine_upsert_accounts`,
`bank_engine_apply_sync`, `bank_engine_list_active_connections` — see
`supabase/migrations/20260902i_bank_engine_rpc.sql`), the same pattern already used by
`ecu_set_vault_secret`/`vault_secret`.

## Amount sign convention

`finance.bank_transactions.amount_cents` = `round(plaid_amount * 100)`, **sign unchanged**:

- **Positive** = money **leaving** the account (an outflow/expense from the account holder's
  perspective) — this is Plaid's own convention, not Everest's.
- **Negative** = money **entering** the account (an inflow/deposit).

The full original Plaid transaction object is preserved untouched in the `raw` jsonb column.
Track D (recon) reads `amount_cents` directly with this convention — do not flip the sign
anywhere in this pipeline.

## Deviation: no `plaid` npm SDK

The issue named the official `plaid` npm package. Its `PlaidApi` class is built on axios, whose
default transport sets a `cache` fetch option the Cloudflare Workers runtime rejects outright —
confirmed live 2026-09-02: `POST /link/token` on the deployed Worker returned HTTP 502
`{"error":"Unsupported cache mode: default"}` even with `compatibility_flags = ["nodejs_compat"]`
set. This is a documented axios-on-Workers incompatibility, not a misconfiguration. `src/plaid.ts`
instead hits Plaid's plain JSON-over-HTTPS REST endpoints directly with the platform's native
`fetch`, exposing the same method names/shapes (`linkTokenCreate`, `itemPublicTokenExchange`,
`accountsGet`, `transactionsSync`, `webhookVerificationKeyGet`) the SDK would, so the rest of the
codebase is unaffected. `plaid` is not a dependency in `package.json`.

## Deploy

`.github/workflows/deploy-bank-engine.yml`, triggered on push to `workers/everest-bank-engine/**`.
Uses this repo's actual working Cloudflare secret names, `CF_API_TOKEN` / `CF_ACCOUNT_ID` — the
issue body named `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` (the `everest-cfo-agent` repo's
convention), but those names do not exist as secrets on `cli-anything-biddeed` (confirmed via
`gh secret list`); every other Workers deploy workflow already live in this repo
(`deploy-winnerdata-ff.yml`, `deploy-winnerdata-lms.yml`, `deploy-ensemble-worker.yml`, etc.)
uses `CF_API_TOKEN`/`CF_ACCOUNT_ID` instead, so this workflow follows the repo's actual working
convention rather than the issue's stated one (CC_META_PROMPT §2.3: a brief's own detail can be
wrong — use the corrected version and log it, don't silently guess or block).
