# Odoo 18 Community — Deed Projects accounting engine (C10, issue #20008)

## What this is

A self-hosted Odoo 18 Community instance (`odoo:18` official Docker image, LGPL-3) is
the accounting engine behind **Deed Projects** — ledger, bills, draws, budget-vs-actual.
Customers never see it and never see the name "Odoo" or its logo anywhere (LGPL-3
requires we keep upstream notices in the code, not that we brand with it). Human-facing
surfaces in Deed Projects call this "Projects."

- Host: existing Hetzner box (`87.99.129.125`), its own Postgres 16 container — never the
  Supabase moat database (`multi_county_auctions`, `insights`, etc. are untouched by
  anything in this PR).
- Public URL (once DNS is live): `books.biddeed.ai`, behind Cloudflare Access
  (Ariel + a Worker service token only).
- Modules: Project, Invoicing (`account`), Purchase, Documents, Analytic — all Community.
  Plus one custom module we wrote, `deed_budget` (see **Licensing** below for why).
- The Worker talks to Odoo server-to-server over JSON-RPC with a scoped API key
  (`src/lib/odoo.js`) — no MCP in the request path.

## Licensing (per the C10 ruling)

- **Rejected:** `pantalytics/odoo-mcp-pro` — its added code is Elastic License 2.0, which
  forbids offering it to third parties as part of a hosted service (exactly what Deed
  Projects is). Nothing from that project is in this PR.
- **MCP, personal use only:** `breverdbidder/mcp-server-odoo` (MPL-2.0 fork of the
  upstream MCP server) is for Ariel's own Claude Desktop/Code access to this Odoo
  instance. It is **not** part of the Worker's request path and is not deployed by this
  PR — the Worker calls Odoo's JSON-RPC API directly (`src/lib/odoo.js`).
  Setting it up (if wanted) is a separate, personal-machine task outside this repo.
- **Odoo Community itself:** LGPL-3, official `odoo:18` image, unmodified. Odoo's own
  copyright/license notices are whatever ship inside that image — we do not strip or
  relicense them.
- **Our own code:** `infra/odoo/addons/deed_budget/` is licensed LGPL-3 (declared in its
  manifest), matching Odoo Community's own license, so it can be redistributed on the
  same terms and never becomes an Elastic-License-style trap.
- **KNOWN GAP, flagged for Ariel — Accounting vs. Invoicing:** since Odoo v17, the full
  "Accounting" app (bank reconciliation dashboards, statements, etc.) is
  **Enterprise-only**; Community ships "Invoicing" (the `account` module, vendor
  bills/customer invoices, journals, chart of accounts — enough for what the three tests
  below need) but not the Enterprise accounting dashboards. `bootstrap.py`/`init_db.sh`
  install `account` (Invoicing), not an Enterprise app — confirm this matches what "C10 —
  ledger, bills, draws, budget-vs-actual" needs before assuming full Accounting-app
  parity. **INFERRED** (Odoo's own edition-gating changes across versions; not verified
  against a live v18 install in this session).
- **KNOWN GAP — Budgets:** Odoo Community has **no Budget app** (`account_budget` moved
  to Enterprise around v13). Rather than depend on it, `deed_budget` is our own tiny
  LGPL-3 module: a `deed.budget.line` model (planned amount per analytic
  account/date-range) computed against actual spend from `account.analytic.line` (the
  Community-available analytic ledger, populated automatically whenever a journal entry
  carries an analytic distribution). This is a deliberate simplification, not a full
  budgeting app — flagged here so it isn't mistaken for Enterprise-equivalent budgeting.

## Architecture

```
                         Cloudflare Access (Ariel + Worker service token)
                                       │
                              books.biddeed.ai (A record → Hetzner)
                                       │
                              ┌────────▼────────┐
                              │  caddy (2-alpine) │  TLS terminates here
                              └────────┬────────┘
                     ┌─────────────────┼──────────────────┐
                     │                 │                  │
              odoo:18 :8069    odoo:18 :8072       odoo-backup (cron,
              (web/JSON-RPC)   (longpolling)         pg_dump → R2 nightly)
                     │                                     │
                     └───────────────┬─────────────────────┘
                                      │
                              odoo-db: postgres:16
                              (own volume, own network,
                               never the Supabase moat DB)
```

Files: `infra/odoo/docker-compose.yml` (4 services: `odoo-db`, `odoo`, `caddy`,
`odoo-backup`), `Caddyfile`, `odoo.conf` (non-secret template — secrets are appended to
a gitignored `odoo.local.conf` at deploy time, see its header comment), `backup.sh`,
`init_db.sh`, `bootstrap.py`, `addons/deed_budget/`.

Deploy mechanism: `.github/workflows/deploy-odoo.yml` (`workflow_dispatch`) — rsyncs
`infra/odoo/` to `/opt/odoo` on the box over SSH, writes a runtime `.env` from GitHub
secrets, brings the stack up, healthchecks it, then attempts Cloudflare DNS + Access
(gracefully skips with instructions if `CF_API_TOKEN` lacks the right scope — see
**Known blocker** below).

## Secrets required before dispatching `deploy-odoo.yml`

None of these exist in this repo's GitHub secrets yet (checked via `gh secret list`,
2026-09-04) — add them first:

| Secret | Purpose |
|---|---|
| `ODOO_DB_PASSWORD` | Postgres password for the `odoo` role |
| `ODOO_DB_NAME` | Odoo database name (e.g. `deedprojects`) |
| `ODOO_MASTER_PASSWORD` | Odoo's `admin_passwd` (DB-manager master password) |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Nightly backup upload. If unset, `backup.sh` logs and skips (no failure) — the brief said "existing R2 creds" but none were found in this repo's secrets; either they live elsewhere or still need creating. |

`CF_API_TOKEN` / `CF_ACCOUNT_ID` already exist (used by other workflows), but
`deploy-paperclip.yml`'s own comments and `workers/everest-bank-engine/wrangler.toml`
both record that this token has historically lacked `Zone:DNS:Edit` /
`Access:Edit` scope for `biddeed.ai` — **CONFIRMED via repo history, not re-tested this
session**. `deploy-odoo.yml`'s DNS/Access steps are `continue-on-error: true` and print
the manual fallback (`books.biddeed.ai A 87.99.129.125`, proxied) if that's still true.

## What did NOT run in this session, and why (Honesty Protocol)

This dispatch executed inside `.github/workflows/cc-runner-ghonly.yml` — a lane titled
**"CC Runner — GHA-only (no Hetzner)"**. The issue's own **RULES** section also caps the
deliverable at **"PR only."** Both point the same direction, so this session:

- **Did not** SSH into the Hetzner box (no `docker ps` inventory, no `docker compose up`).
- **Did not** create the `books.biddeed.ai` DNS record or Cloudflare Access app.
- **Did not** run `init_db.sh` or `bootstrap.py` against a live instance.
- **Did not** run the three evaluation tests below against real output.

Everything above is **UNTESTED** — files exist and are internally consistent (Python/XML
syntax-checked, YAML-parsed, field names for `project.project.account_id` and
`account.analytic.line` verified against the actual Odoo 18 source on GitHub — see
inline comments), but none of it has run against a live Odoo instance. Marking this
`VERIFIED` or `SHIPPED` would violate the SHIP GATE and Honesty Protocol. The reviewed,
correct way to get live evidence is: merge this PR, add the secrets above, dispatch
`deploy-odoo.yml` with `run_db_init: true`, run `bootstrap.py`, then run the three tests
below and paste real output into a follow-up comment on issue #20008 (or a new session
dispatched through a Hetzner-capable lane, if this repo has one).

## The three evaluation tests (methodology — results pending live deploy)

### Test A — project → budget → bill → draw → report in ≤5 RPC calls

```
1. execute_kw project.project create        (deed_budget auto-creates the linked
                                              account.analytic.account in this same call)
2. execute_kw deed.budget.line create        (planned_amount, date_from, date_to)
3. execute_kw account.move create            (move_type=in_invoice, line analytic_distribution
                                              -> the project's analytic account)
4. execute_kw account.move action_post       (posts the bill — "the draw"; this is what
                                              generates the account.analytic.line actuals)
5. execute_kw deed.budget.line search_read   (planned_amount, actual_amount, variance_amount)
```
`src/lib/odoo.js` exposes calls 1–3 as `createProjectWithAnalytic` / `addBudgetLine` /
`addVendorBill` (call 3 posts by default). **Status: UNTESTED** — design verified against
Odoo 18 source (`project.project.account_id`, `account.analytic.line.account_id/amount/date`
all confirmed via github.com/odoo/odoo @ 18.0), not run live.

### Test B — two customers as two companies cannot see each other (negative test)

Plan: `bootstrap.py`'s worker user gets `multi_company` off (single default company);
create two `res.company` records (one per test customer, deleted after the drill — no
real customer data used); as the Worker's API key, `search_read` on `project.project`
scoped with `context={'allowed_company_ids': [company_a.id]}` should return zero rows
for a project created under `company_b`. Odoo's multi-company record rules are the
platform mechanism being tested, not custom code. **Status: UNTESTED**.

### Test C — resource use on the box + cost at 100 customers

Plan: `docker stats --no-stream` + `df -h` on the box, ~10 min after `docker compose up
-d`, before and after `init_db.sh`. **Status: UNTESTED** — no numbers are stated here
because none were measured; do not treat the "2 workers / postgres:16" sizing in
`docker-compose.yml` as a validated capacity number. Rough, labeled **INFERRED** (from
Odoo's own sizing docs, not this box): a 2-worker single-tenant-Postgres Odoo instance
is commonly quoted at ~1-2GB RAM baseline; 100 companies in one DB (not 100 separate
DBs) is a normal Odoo multi-company pattern and shouldn't multiply resource use
linearly, but this needs the real Test C measurement to confirm, not an estimate.

## Backup / restore drill

- **Backup:** `odoo-backup` service runs `backup.sh` nightly at 03:00 (box-local) via
  cron: `pg_dump -Fc` the Odoo DB, upload to `r2://$R2_BUCKET/odoo-backups/`, prune
  objects older than 30 days. Skips (not fails) if R2 secrets are unset.
- **Restore drill (run after first successful backup, not yet performed):**
  1. `aws --endpoint-url https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com s3 cp s3://$R2_BUCKET/odoo-backups/<file> /tmp/restore.dump`
  2. `docker compose exec -T odoo-db pg_restore -U $ODOO_DB_USER -d $ODOO_DB_NAME --clean --if-exists < /tmp/restore.dump`
  3. `docker compose restart odoo`
  4. Confirm login + one known project/budget line round-trips.
  **Status: UNTESTED** — documented procedure, not yet executed against a real backup.

## Worker integration status

`src/lib/odoo.js` is written and syntax-checked (`node --check`) but **deliberately not
wired into `src/worker.js`'s existing `/chat/api/projects*` routes yet** — `src/worker.js`
is a single ~10k-line file serving live production traffic for `biddeed.ai`, and wiring a
call to an Odoo instance that isn't deployed/reachable would risk breaking that route for
real users. Wire it in a follow-up PR once `ODOO_URL`/`ODOO_LOGIN`/`ODOO_API_KEY` are
confirmed reachable from a live `deploy-odoo.yml` run.
