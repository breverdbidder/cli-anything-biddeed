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
| `GET /import?key=<secret>` | none (page itself, same pattern as `GET /link`) | Minimal upload form — account dropdown (from `public.bank_engine_import_account_options()`, real `simplefin`/`manual` accounts only, each labeled with its live coverage/gap), file picker. |
| `POST /import?entity_code=&mask=&account_label=` | `X-CFO-Secret` / `?key=` | Imports a Wells Fargo CSV or QFX/OFX file (multipart `file` field or raw body), then runs the daily-close pipeline (categorize/post/recon) and returns the fresh coverage snapshot. See "Bank file importer" below. |
| `POST /plaid/production-status` | `X-CFO-Secret` | Issue #19770 step 1 — probes `production.plaid.com/link/token/create` with this Worker's current `PLAID_CLIENT_ID`/`PLAID_SECRET` to check whether Plaid production access has been granted. Never returns the client_id/secret, only Plaid's error envelope. |
| `POST /simplefin/claim` | `X-CFO-Secret` | One-time: exchanges a SimpleFIN setup token for an access URL, stored in vault. |
| `POST /simplefin/sync` | `X-CFO-Secret` | Pulls accounts + transactions from the stored SimpleFIN access URL for one `entity_code`. |
| `GET /healthz` | none | Liveness probe. |
| `GET /privacy` | none | Renders §9 of `docs/security/EVEREST_INFOSEC_POLICY.md` as plain HTML (Plaid production questionnaire, 2026-09-02 addendum). Linked from the `/link` page footer. |

Cron trigger (`wrangler.toml` `[triggers]`) runs every 6h and syncs every `status='active'`
connection (Plaid only), plus one SimpleFIN sync using whichever `entity_code` the most recent
`status='simplefin'` connection used (no-op/`SKIPPED` until `/simplefin/claim` has run once).

## Bank file importer (issue #19749 Part 1)

`POST /import` accepts a Wells Fargo CSV export (no header row: `Date,Amount,*,*,Description`)
or a QFX/OFX file (1.x SGML or 2.x XML, `<STMTTRN>` blocks), auto-detected from the filename
extension or file content (`src/ofxImport.ts::looksLikeOfx`). Query params: `entity_code`
(required), `mask` (required, last 4 of the account), `account_label` (optional, defaults to
`WF Checking <mask>`). Body is either `multipart/form-data` with a `file` field, or the raw file
bytes with any content-type.

Writes go to the same `finance.bank_connections`/`bank_accounts`/`bank_transactions` tables as
Plaid, via **new, file/SimpleFIN-specific RPCs** (`bank_engine_upsert_connection_status`,
`bank_engine_import_transactions` — see
`supabase/migrations/20260902m_bank_file_simplefin_rpc.sql`), not `bank_engine_apply_sync`
(#19737's Plaid RPC forces `status='active'`, which would put a file-imported connection into
the Plaid cron's sweep and produce a spurious `BLOCKED` result every 6h since it has no Plaid
access token in vault). `bank_connections.plaid_item_id = 'file:'||mask`,
`bank_accounts.plaid_account_id = 'file:'||mask`, `institution_name='Wells Fargo'`,
`status='manual'`. Idempotency key: OFX `FITID` when present, else
`sha256(date|amount|description|mask)` — re-importing the same file is a no-op re-upsert
(`on conflict (plaid_transaction_id) do update`), not a duplicate insert.

**Post-import pipeline (issue #19770)**: on a successful import, `POST /import` also calls
`public.bank_engine_run_daily_close('2026-01-01')` (reuses #19765's existing categorize/post/
recon/balance-check pipeline rather than re-implementing it) and reads back
`finance.v_data_coverage` — both are returned in the response body as
`daily_close_summary`/`coverage`, and both are best-effort (a failure there is reported inline,
not treated as a failed import — the rows were already safely upserted by that point).

## SimpleFIN Bridge connector (issue #19749 Part 2)

Protocol: [simplefin.org/protocol.html](https://www.simplefin.org/protocol.html). `POST
/simplefin/claim` takes `{"setup_token": "<base64>"}`, decodes it to a claim URL, `POST`s that
URL (empty body) to get a Basic-Auth Access URL, and stores it **only** in vault as
`simplefin_access_url` (`public.ecu_set_vault_secret`) — never in a table column, never returned
in a response body. `POST /simplefin/sync` takes `{"entity_code": "..."}` (+ optional
`start_date`/`end_date` Unix timestamps), reads the access URL back out of vault, and calls `GET
{access_url}/accounts`. Each returned account becomes its own `bank_connections` row
(`plaid_item_id='simplefin:'||account.id`, `status='simplefin'`) — unlike Plaid, where one item
covers many accounts, SimpleFIN's protocol doc models one access URL as covering an arbitrary
set of accounts with no single parent "item" concept, so each account is its own connection row.

**Real activation is pending Ariel's own setup token** (issue non-goal: "real activation waits
for Ariel's token"). This session tested `/simplefin/claim` + `/simplefin/sync` code paths
against SimpleFIN's own published demo setup token from the protocol page
(`aHR0cHM6Ly9icmlkZ2Uuc2ltcGxlZmluLm9yZy9zaW1wbGVmaW4vY2xhaW0vZGVtbw==`, decodes to
`https://bridge.simplefin.org/simplefin/claim/demo`) — see `docs/spec/19749.md` for the exact
live result (Cloudflare bot-challenge blocked the claim request; the code path itself is
implemented per spec but the live demo round-trip is `UNTESTED`, flagged explicitly rather than
claimed).

## Amount sign convention

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
`ecu_set_vault_secret`/`vault_secret`. Issue #19749 added four more in the same style
(`bank_engine_upsert_connection_status`, `bank_engine_import_transactions`,
`bank_engine_list_entities`, `bank_engine_simplefin_default_entity` — see
`supabase/migrations/20260902m_bank_file_simplefin_rpc.sql`) for the file importer and SimpleFIN
connector, which deliberately do NOT reuse `bank_engine_upsert_connection`/`bank_engine_apply_sync`
(those hardcode `status='active'`, which would put a file/SimpleFIN connection into the
Plaid-only cron sweep).

## Amount sign convention

`finance.bank_transactions.amount_cents` = `round(plaid_amount * 100)`, **sign unchanged**:

- **Positive** = money **leaving** the account (an outflow/expense from the account holder's
  perspective) — this is Plaid's own convention, not Everest's.
- **Negative** = money **entering** the account (an inflow/deposit).

The full original Plaid transaction object is preserved untouched in the `raw` jsonb column.
Track D (recon) reads `amount_cents` directly with this convention — do not flip the sign
anywhere in this pipeline.

**File import (CSV/QFX/OFX) and SimpleFIN both use the opposite raw convention** —
negative=debit/positive=credit (WF CSV's own stated convention; OFX `TRNAMT` per the OFX spec;
SimpleFIN `amount` per its protocol doc: "positive numbers indicate money being deposited"). Both
`fileImport.ts::toAmountCents` and `simplefin.ts::toAmountCents` negate the raw value exactly
once, at the single point where each source's parsed transaction is shaped into the
`bank_engine_import_transactions` upsert shape, so `finance.bank_transactions.amount_cents`
means the same thing (Plaid's positive-outflow convention) regardless of which of the three
ingestion paths wrote a given row.

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
