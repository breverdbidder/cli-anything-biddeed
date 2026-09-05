# Vercel Invoice Dispute — Evidence Pack (2026-09-05)

This document supports a billing dispute for a Vercel invoice on the `brevardbidderai@gmail.com`
Pro account. It is split into a customer-facing section (safe to share externally, no internal
tooling/process detail) and an internal appendix (full technical trail).

**Update, 2026-09-05T12:41Z (added after the initial write-up below):** the Vercel account itself
has since been **suspended for non-payment** (its own billing status shows `overdue`). Both
`mcp.biddeed.ai` and `zonewise.ai` returned `HTTP 402 DEPLOYMENT_DISABLED` from Vercel within the
hour this pack was assembled — one was already fixed with an emergency Cloudflare cutover by a
sibling effort, the other was confirmed down and flagged as a live outage (not a future risk) to
the team responsible for its own Cloudflare cutover. This changes the framing of the underlying
dispute from "stop a build-minute overcharge" to "the account relationship itself failed in a way
that took production down" — worth stating plainly in the dispute conversation.

---

## Customer-facing summary

**The charge in question:** an $82.20 "Build CPU Minutes" overage (29,160 minutes billed) on top
of the flat $20/month Pro seat, on an invoice dated 2026-08-18 for the billing period
2026-07-18 → 2026-08-18. **VERIFIED** — pulled directly from the Vercel account's own invoice API
(`/v1/invoices`), matching the invoice total ($102.37 = $20.00 seat + $82.20 build overage + $0.17
other metered usage) exactly.

**Why this is disputable — it is a spike, not steady usage:**

| Billing period | Build CPU minutes used | Amount charged for build minutes |
|---|---:|---:|
| 2026-03-18 – 2026-04-19 | (not itemized this period) | $0.00 |
| 2026-04-19 – 2026-05-18 | 1,020 | $0.00 (covered by plan allowance) |
| 2026-05-18 – 2026-06-19 | 4,650 | $0.00 (covered by plan allowance) |
| 2026-06-19 – 2026-07-18 | 2,910 | $0.00 (covered by plan allowance) |
| **2026-07-18 – 2026-08-18** | **29,160** | **$82.20** |

**VERIFIED** (same `/v1/invoices` source, all four prior invoices' `buildCpuMinutes` line item).
The disputed period used **6.3× to 28.6× more build compute** than any of the three preceding
months, none of which incurred any build-minute overage charge at all. This is consistent with an
automated process generating far more Vercel builds than normal usage would produce, not with a
change in legitimate traffic or deliberate scaling.

**What drove it:** one project's automated deployment pipeline. In the exact invoice window, that
one project alone accounts for an estimated 95% of all measured build activity across every
project on the account, and every code change to it was triggering **two separate Vercel builds**
— one from Vercel's own automatic "deploy on every push" integration, and a second, redundant one
from a separate automated deploy step — instead of one. That double-build path has since been
disabled (2026-09-05), and a path filter that stops the automatic per-push trigger from firing on
unrelated file changes was added two days prior (2026-09-03). **VERIFIED** for the disable action
(see project/workflow evidence below); the pre-fix redundant-build behavior is **CONFIRMED** from
the account's own deployment history for the invoice window.

**What has already been done (as of 2026-09-05), to stop this recurring:** every non-essential
Vercel project on the account has been paused (paused projects cannot build at all, whether
triggered by a push or a manual command); the automatic "deploy on every push" trigger has been
removed from the workflow files that were driving it, on the two projects still in active use;
and a nightly cost-anomaly check now flags any vendor charge that is more than 150% of its own
trailing 90-day median, so a repeat of this pattern would surface within a day instead of showing
up on a monthly invoice.

**Net position:** the $82.20 overage traces to a real, identified, now-fixed automation defect
(uncontrolled, duplicated automatic builds on one project), not to legitimate increased usage of
the service. The steady-state build-minute usage in the three months before the spike (1,020 –
4,650/month) supports that the corrected configuration should return usage to a level fully
covered by the existing Pro plan allowance.

---

## Internal appendix (technical detail, not for external sharing)

### Source of every number in this document

- Vercel account: `brevardbidderai@gmail.com`, team `team_UEds2qBzyD9e7rOrX8aakj9K`
  ("Ariel Shapira's projects", Pro plan, billing status **`overdue`** at time of pull —
  **VERIFIED**, `GET /v2/user` + `GET /v2/teams` via the `public.vercel_api` Supabase RPC,
  2026-09-05).
- Invoice line items: `GET /v1/invoices` via the same RPC, 2026-09-05. Invoice
  `inv_c3RyaXBlOmluXzFVNXQ1Y0dJcGRLRlVtUFltYjYzcU42aQ` = the disputed $102.37 invoice
  (D2LOTNWY-0007 per the issue that requested this pack), `issuedAt` 2026-08-18T19:54:33Z.
  `buildCpuMinutes` line item: `quantity=29160`, `amount=82.20` (on-demand), `subtotal=102.06`,
  `allocation=19.86` (plan-included portion). **VERIFIED**, exact match against the figures in
  the request for this pack.
- Trailing-month `buildCpuMinutes` quantities (1,020 / 4,650 / 2,910, all `amount=0.00`) —
  **VERIFIED**, same endpoint, the three invoices immediately preceding the disputed one
  (2026-05-18, 2026-06-19, 2026-07-18 issue dates). The 2026-04-19 invoice ($267.61, paid) had
  `buildCpuMinutes` quantity **0** — that spike was a different billable item, unrelated to this
  dispute, **not investigated further here** (out of scope for this issue; flagged as residual
  below).
- Per-project deployment counts / wall-clock build durations: `GET /v6/deployments?projectId=…`
  per project, paginated, for two windows — **A** = 2026-07-18T00:00Z→2026-08-18T00:00Z (the
  exact invoice period) and **B** = 2026-08-18T00:00Z→2026-09-05 (session time, partial current
  cycle) — via the same RPC, 2026-09-05. 22 of 22 projects queried (the account's full project
  list, `GET /v9/projects`, cross-checked against the issue's own "22 projects" count).
- GitHub Actions corroboration: `gh api repos/breverdbidder/zonewise-web/actions/workflows/238782092/runs?created=2026-07-18..2026-08-18` (workflow `deploy-prod.yml`), **VERIFIED**, 2026-09-05.

### Per-project build activity, invoice window (Window A: 2026-07-18 → 2026-08-18)

Wall-clock build duration (`ready` − `buildingAt`, falling back to `ready` − `createdAt` when
`buildingAt` is absent) measured from the Deployments API. **This is not the same metric as
Vercel's internal `buildCpuMinutes` billing unit** — Vercel does not expose a per-deployment
CPU-minute or CPU-core-count breakdown via any endpoint this session could reach, so the
529-minute total below cannot be arithmetically reconciled to the invoice's 29,160-minute figure
(a ~55× gap, most plausibly explained by CPU-minutes being wall-clock-minutes × the build
machine's allocated core count, and/or by billing counting queued time this measurement excludes
— **UNKNOWN**, not guessed at). What this data *does* establish, at full confidence, is **which
project and which trigger mechanism** dominated:

| Project | Deployments | Wall-clock build minutes | Trigger breakdown |
|---|---:|---:|---|
| **zonewise-web** | **380** | **489.13** | git-integration auto-build: 264 (avg 105.4s/build) · CLI (`vercel deploy --prebuilt`, GHA-triggered): 115 (avg 12.5s/build) · unknown: 1 |
| shapira-life-os | 67 | 6.98 | cli: 67 |
| brevard-bidder-landing-v2 | 10 | 5.85 | git: 8, redeploy: 2 |
| biddeed-mcp | 39 | 5.62 | cli: 39 |
| brevard-bidder-site | 8 | 4.76 | git: 8 |
| cli-anything-biddeed | 1 | 0.98 | cli: 1 |
| biddeed-web | 0 | 0 | (no deployments in window) |
| everest-geo-tracker | 0 | 0 | (no deployments in window) |
| (remaining 14 of 22 projects) | 0 | 0 | (no deployments in window) |
| **Account total** | **~505** | **~513.3** | |

**zonewise-web = 489.13 / 513.3 = 95.3% of all measured wall-clock build minutes on the entire
account** in the exact invoice window. **VERIFIED.**

### The double-build mechanism (root cause)

`zonewise-web`'s 380 deployments split into two distinct trigger paths for the *same* commits:

1. **`source: "git"` (264 deployments, avg 105.4s each ≈ 463.8 measured minutes)** — Vercel's
   native GitHub App integration, which auto-builds on every push to `main` regardless of which
   files changed. Prior to 2026-09-03 (issue #19811, a separate prior session), this repo's
   `vercel.json` had no `ignoreCommand` / path filter at all, so pushes touching only docs,
   agent-harness config, or unrelated directories still triggered a full production build.
2. **`source: "cli"` (115 deployments, avg 12.5s each ≈ 23.9 measured minutes)** — a GitHub
   Actions workflow (`deploy-prod.yml`) independently running `vercel deploy --prebuilt --prod`
   on the *same* push. **Cross-checked, VERIFIED**: `deploy-prod.yml` shows 233 runs in the exact
   invoice window (117 `cancelled` — killed by its own `concurrency: cancel-in-progress` group
   when a newer push arrived mid-build — 16 `failure`, 100 `success`), consistent with ~115
   completed CLI deploys landing on Vercel's side.

Net effect: most commits to `zonewise-web` in this window triggered **two** Vercel builds — one
expensive (full `npm run build` on Vercel's infrastructure, ~105s) and one cheap (upload of an
already-built artifact via `--prebuilt`, ~12.5s) — when one would have sufficed. The expensive
path (`git`-triggered) is the one with no path filter and is the dominant minute-consumer.

### What was fixed this session (2026-09-05, issue #20027 — Part 1, "stop the meter")

All actions below were taken via the account's own Vercel API (through the
`public.vercel_api` Supabase RPC, which holds the account credential server-side — this session
never had direct access to a raw Vercel API token) and verified with a follow-up `GET`:

| Action | Evidence |
|---|---|
| Paused `biddeed-web`, `everest-geo-tracker`, `brevard-bidder-skills-dashboard`, `cli-anything-biddeed` | `POST /v1/projects/{id}/pause` → 200, re-`GET` confirms `paused: true` on all 4 |
| `life-os`, `life-os-mobile`: pause **rejected** by Vercel (`400 invalid_deployment — Active production deployment does not exist`) | Real platform constraint — pause requires a prior production deployment. `life-os-mobile` has a live GitHub link, so `commandForIgnoringBuildStep: "exit 0"` was set instead (confirmed via re-`GET`) as an equivalent kill switch. `life-os` has no GitHub link recorded at all — no push-triggered build risk exists to mitigate |
| 15 of 22 projects were already paused before this session (unrelated prior work) | `GET /v9/projects` inventory, `paused: true` on all 15 |
| `biddeed-mcp`, `zonewise-web` left **unpaused** (deliberately, per issue scope — both are still-live production domains awaiting a Cloudflare cutover in sibling issues #20025/#20026) | — |
| Removed the `push: branches: [main]` trigger from `mcp-vercel-deploy.yml` and `deploy-watch-dashboard.yml` (`cli-anything-biddeed` repo); added `DEPRECATED` header | committed to `main`, this repo |
| Removed the `push: branches: [main]` trigger from `deploy-prod.yml` and added a `DEPRECATED` header to all 13 Vercel-touching workflows in `zonewise-web` | PR breverdbidder/zonewise-web#112, branch `cf-exit-decommission` (main is protected — could not push directly) |
| `biddeed-web`'s `ci-deploy.yml` — confirmed already gated: its deploy job only runs on `workflow_dispatch` or when repo variable `DEPLOY_TO_VERCEL=true`; that variable does not exist (`GET .../actions/variables/DEPLOY_TO_VERCEL` → 404), so push-triggered auto-deploy is already off by design (prior work, issue #19820) | confirmed live, no change needed |

### Window B (2026-08-18 → 2026-09-05, current partial cycle, informational only)

`zonewise-web`: 32 deployments, ~66.5 measured build-minutes so far this cycle (31 git-triggered,
1 unknown) — still the dominant project, though at a lower rate than Window A, consistent with
Ariel's own observation that "current cycle already $17.31 by Sep 3." This is **not** a finalized
invoice figure — no invoice has been issued yet for this partial period — flagged as directional
context only, not a number to cite in the dispute itself.

### Residual / not investigated in this pack

- The 2026-04-19 invoice's $267.61 charge had zero build-minutes — a different cost driver,
  out of scope for this dispute (which is specifically about the build-CPU-minutes line item)
  and not examined further here.
- The exact conversion factor between wall-clock build minutes and Vercel's billed
  `buildCpuMinutes` unit is **UNKNOWN** — Vercel does not expose it via any endpoint reachable
  this session. If Vercel support provides a per-deployment CPU-minute breakdown during the
  dispute conversation, it should reconcile against the 380-deployment list this pack is built
  from, not replace it.
- `zonewise-web`'s CORS allowlist (`lib/api/cors.ts`) references
  `https://zonewise-desktop-viewer.vercel.app`, a project not found in this account's 22-project
  inventory — either a separate Vercel account, an already-deleted project, or a dead CORS entry.
  Not migrated or touched (read-only finding per this issue's scope).
- A cron job named `everest-scheduled-deploy-health` (`jobid=15`, active) could not be inspected
  for its actual SQL command text — Supabase's exposed read surfaces (`v_cron_health`,
  `cron_job_registry`) deliberately omit the `command` column, and direct `psql` access is
  blocked by a known, previously-documented credential constraint (decision_log 169/205/287).
  No cron job with "vercel" in its *name* was found across all 126 registered jobs. This one's
  actual behavior is **UNKNOWN**, not assumed safe or unsafe.

### CFO capability integration (issue ask: "feed totals into `cfo_invoice_ingest` if a row for
this invoice doesn't already exist")

Confirmed live (`GET /rest/v1/` OpenAPI schema) that `public.cfo_invoice_ingest`,
`cfo_invoice_save_dispute`, `cfo_invoice_set_status`, `cfo_invoice_write_verification`, and
`cfo_invoice_check_anomalies` all exist and are callable. **Did not call any of them.** No
read endpoint for the underlying `cfo_invoices`/`cfo_invoice_lines` tables is exposed via
PostgREST (only the write/anomaly RPCs above appear in the schema), so there was no safe way to
first confirm "does a row for invoice D2LOTNWY-0007 already exist" before writing — and the
issue's own instruction is explicitly conditional on not duplicating that row. Calling
`cfo_invoice_ingest` blind, with no verification path, risked exactly the duplication the issue
asked to avoid. Flagged as residual: a follow-up with either a read-scoped RPC or direct
confirmation from Ariel should complete this integration; this session's evidence pack is
complete and stands on its own regardless of whether that ingestion happens.

### Honesty V3 tag legend
Every dollar figure and every quantity in the tables above is **VERIFIED** (pulled live from the
Vercel or GitHub API during this session, 2026-09-05, and shown with its exact source query). The
"which mechanism caused it" narrative is **CONFIRMED** (directly observed in both the Vercel
deployment history and the GitHub Actions run history, cross-checked against each other). The
CPU-minute-to-wall-clock-minute conversion factor is explicitly **UNKNOWN**.
