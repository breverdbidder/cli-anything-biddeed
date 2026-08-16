# BIDDEED.AI — ARCHITECTURE SINGLE SOURCE OF TRUTH (SSOT v1)

**Status:** canonical. Where any brief, doc, comment, or session memory conflicts
with this file, this file wins. **Any commit that changes infrastructure must
update this file in the same commit.**
**Owner:** Ariel Shapira. **Authored:** 2026-07-20 by the AI Architect, ratified by owner.
**Companion:** `CC_META_PROMPT.md` (process contract). Read both before any brief.

Written because on 2026-07-20 one session deployed the MCP product service onto
the CC runner box, and a later session — lacking any written inventory — treated
that same box as a possible intrusion. Neither would have happened if this file
had existed.

---

## 1. INFRASTRUCTURE INVENTORY

| Component | What it is | What it is NOT |
|---|---|---|
| **Local Dell** | The biddeed.ai MCP **product serving machine**. Runs the MCP HTTP server from this repo on open-source infrastructure, exposed as `mcp.biddeed.ai` via Cloudflare Tunnel (`cloudflared`). See `docs/DELL_MCP_RUNBOOK.md`. | Not a dev toy. This is production. |
| **Hetzner `87.99.129.125`** | The **CC runner / dispatch box**, set up March 2026 at owner direction as the permanent Claude Code home. | **NOT a product surface.** The MCP HTTP service formerly on `:3031` is legacy (deployed 2026-06-26 in error, refreshed 2026-07-20 in error, stopped 2026-07-20). Never deploy product services here. Never cite `:3031` as a live endpoint. |
| **Cloudflare Pages** | Serves `biddeed.ai` (marketing/site). | `biddeed.ai/api/mcp` does **NOT** serve MCP — it returns site HTML. Do not "fix" it to; the MCP surface is `mcp.biddeed.ai`. |
| **Supabase `mocerqjnksmhcjzxrewo`** | Data plane: auctions, billing, cert system, dispatch guard, ops log. | Not a place for secrets in row data. |
| **GitHub Actions** | Dispatch (`cc-runner-ghonly.yml` id 297104962), crons, deploys. Guard table `public.cc_redispatch_guard` + reconciler drive the loop; a brief without a guard row has no retry and no DoD enforcement. | `mcp-vercel-deploy.yml` is dead: no Vercel project exists for biddeed (verified 2026-07-20); Vercel secrets absent. Do not chase it. |
| **Stripe** | LIVE mode only: 4 products, 2 payment links, S5 meter. No test-mode path exists (known gap). | Not yet carrying real customer traffic. |
| **npm `biddeed-mcp`** | Intended stdio distribution channel. **Unpublished** (registry 404). `NPM_TOKEN` absent from repo secrets. | Not required for the HTTP surface to go live. Publish is a separate owner decision; canonical endpoint and npm name are registered in mcp_server_registry. |
| **`zonewise-floorplan` Worker** (`workers/zonewise-floorplan/` in this repo, deployed via `.github/workflows/deploy-zonewise-floorplan.yml` → `zonewise-floorplan.brevardbidderai.workers.dev`) | Two ZoneWise tools sharing one Worker: (1) `/floorplan/*` — interior room-layout compiler (ArchLang wrapper). (2) `/site-massing/*` — generative parcel-level footprint/unit-placement solver + DXF export (added 2026-08-16, Algoma-parity issue). Routes: `POST /site-massing/generate`, `GET /site-massing/:run_id`, `GET /site-massing/:run_id/options/:option_id/dxf`. Reads `zw_parcels` (boundary + zoning_code) and `zoning_districts`/`zone_standards` (setbacks/coverage/density — NOT `zw_zoning`, which has zero Brevard rows and null setbacks everywhere, contrary to that issue's original spec text). Writes `public.site_massing_runs` / `public.site_massing_options` (RLS on, no anon policy) and Storage bucket `site-dxf` (private). Proxied from zonewise-web at `/api/floorplan/*` and `/api/site-massing/*` (`app/api/.../[...path]/route.ts` — NOT a next.config rewrite, Vercel serves zonewise.ai directly so the Worker's own `routes` entry can never fire). | `/site-massing/*` is NOT an extension of an "ArchLang DXF path" — no such path ever existed (ArchLang only produces SVG reliably; PDF is confirmed broken under Workers, see `worker.js`'s `handleCompilePdf` comment). The DXF exporter (`site-dxf.js`) is new, built directly on `dxf-writer`. Parcel→zoning-district jurisdiction resolution is a **known-honest v1 gap**: `zw_parcels.zoning_jurisdiction` is unpopulated fleet-wide, and the same zoning code (e.g. Brevard's `RU-1-11`) is reused with different standards across up to 10 municipalities — resolution falls back through `site_city` match → "Unincorporated `<county>`", tagged in `zoning_snapshot.jurisdiction_resolution_method`, never presented as authoritative without that tag. |

## 2. SERVING MODEL (the one answer to "where does the MCP run")

Customer → `mcp.biddeed.ai` → Cloudflare Tunnel → **local Dell** → MCP HTTP server (this repo, `main`) → Supabase.
Auth: API key / OAuth per `src/server.js`. Billing chain: `handleToolCall` → idempotency claim → cert gate → allowance → execute → `recordBilling` → `billing_events` → hourly `s5-meter-emit` → Stripe meters.
**Proven end-to-end 2026-07-20** (first verified traffic: idempotency +1-not-+2, `mcp_charge_events` outcome=charged, `last_used_at` updated, tier-gate refusal left billing unchanged).

## 3. PROTECTED OBJECTS (read freely, write only when a brief names them)
`gold_standard_*`, `insights`, `taxi_meter_*`, `multi_county_auctions`. Ops outcomes go to `public.agent_ops_log`; auction/anomaly data to `public.insights`. `gold_standard_scoreboard` is untrustworthy — never cite as proof.

## 4. CERTIFICATION
`gold_standard_certify()` with N=3 strike hysteresis, persisted `revocation_reason` + `last_evaluated_run`, warn-before-revoke (GTM-22H, 2026-07-19). Cert gates S5 (`predict_auction_outcome`, $25). A county with empty enrichment data will and should fail cert — fix the data, not the gate.

## 5. KNOWN GAPS (open, owner-visible)
- Marion (and non-Brevard generally): property-appraiser enrichment absent; FJ was mis-mapped into `opening_bid`; `plaintiff_max_bid` not captured. In flight: issue #12851.
- No Stripe test mode; no live customer subscriptions yet.
- `NPM_TOKEN` absent — npm channel dark (owner decision).
- A GitHub PAT was exposed in plaintext in a March 2026 session — rotation recommended (owner-only).
- Issue #12745 (GTM-22 parent) parked in `needs_dod`.
- **Secret rotation (2026-08-03 audit):** 35 of 37 tracked secrets have never
  had a rotation date recorded (`public.secret_rotation_registry`). Weekly
  Telegram reminder now live (`secret-rotation-check` cron, Mondays 09:00 UTC)
  but nothing has actually been rotated yet except Cloudflare's deploy token
  and the gh-aw Anthropic API key (both 2026-07-28). `service_role_key` and
  `anthropic_oauth_bearer` in particular are still unrotated. See
  `docs/security/vault-audit-2026-08-03.md`.
- **No Supabase network restriction is possible today without a tradeoff**:
  Vercel egress IPs are dynamic/unpublished unless the $100/mo Static IPs
  add-on is purchased (not provisioned, purchase forbidden by this audit's
  scope); GitHub Actions' published IP range (7,297 CIDRs) is too broad to be
  a meaningful allowlist. Project remains fully open (`0.0.0.0/0`). See
  `docs/security/ip-allowlist-research.md`.
- **Vault secret access is not audited**: no `vault_access_log`, no `pgaudit`
  extension. Platform limitation, not a config gap — cannot verify who reads
  `vault.decrypted_secrets` and when. See CREDENTIAL HANDLING section of
  `CLAUDE.md` for the `get_vault_secret_mcp()` open finding this compounds.
- `cc-login-telegram.yml` and `claude-login-telegram.yml` (OAuth-refresh-
  adjacent) both last ran 2026-04-03 (4 months stale as of 2026-08-03);
  `claude-login-telegram.yml` failing on its last 3 observed runs. Not
  investigated further — out of scope for the 2026-08-03 security audit,
  flagged as a finding.
- **`pipeline.tier1_card_raw` and 3 sibling `pipeline.*` tables had no GRANT
  for `service_role`/`anon`/`authenticated`** (only `postgres` — a config gap,
  not RLS), so `v_brevard_td_sold_cma` 403'd for every PostgREST caller even
  though the view itself was exposed. Fixed 2026-08-16 (issue #19146 session):
  `GRANT USAGE ON SCHEMA pipeline` + `GRANT SELECT` on `tier1_card_raw`,
  `brevard_account_parcel`, `brevard_realtdm_cases`, `brevard_trtax_deeds` to
  those three roles, via the Management API SQL endpoint (`api.supabase.com`,
  not direct psql — see CREDENTIAL HANDLING's `SUPABASE_DB_PASSWORD`
  constraint in `CLAUDE.md`, which does not apply to this HTTPS-based path).
  **Separately, the view's own join is broken**: `pipeline.brevard_account_parcel.parcel_id`
  uses a different tokenization than `fl_parcels.parcel_id` for the same
  parcel (e.g. `20-34-09-00-6` vs `20 3404-00-1`), so the join to `fl_parcels`
  never matches and `median_comp`/`n_comps` are NULL for all 2,504 rows in the
  view today — verified via direct query, not fixed here (owned by whatever
  pipeline populates `brevard_account_parcel`, out of scope for a UI-wiring
  session). Any future work reading this view should re-check row coverage
  before assuming the GRANT fix alone makes it usable.
- **Site Massing CAD/DXF export shipped in `breverdbidder/zonewise-web`
  (2026-08-16, issue #19144, superseding #19143)**: `MassingEngine.tsx`'s
  `computeEnvelope()` (idealized-rectangle-only) now has a sibling solver,
  `lib/development-analysis/site-massing-solver.ts`, that walks the real
  parcel boundary polygon and ranks up to 5 candidate footprints per lot
  orientation, each validated against the true (non-rectangular) boundary.
  New DXF export, `lib/development-analysis/site-dxf.js`, via new deps
  `dxf-writer` + `proj4` — **no ArchLang/existing DXF writer was found
  anywhere in this repo** despite #19143/#19144's spec assuming one existed
  (the floorplan tool only exports PDF client-side); this is the first DXF
  dependency in zonewise-web. Reprojects EPSG:4326 → FL State Plane
  (EPSG:2236/2237/2238, verified against epsg.io, not guessed) by county
  name. New API routes `/api/massing/run` (persistence) and `/api/massing/dxf`
  (export), both added to the public route matcher (no login gate, matching
  `/massing` itself). Tables `site_massing_runs`/`site_massing_options`
  already existed live pre-commit (created directly against the DB by the
  superseded #19143 dispatch, no migration file had been committed) — this
  shipped a `create table if not exists` migration
  (`supabase/migrations/20260816_site_massing_runs.sql` in zonewise-web) to
  make that schema reproducible; zero rows existed at the time, so nothing
  needed reconciling. **Open finding, not resolved by this commit:** a
  different, apparently still-active CC session
  (`site_massing_runs.created_by = 'cc-session-test'`) wrote a run to these
  same tables at `2026-08-16T08:47:28Z` — **after** the 08:27 UTC comment on
  #19143 told that dispatch to stop — using a materially different schema
  convention (footprint vertices pre-projected to state-plane feet at
  write time rather than lng/lat, a richer `zoning_snapshot` sourced from
  `zone_standards`, and populated `dxf_path` values implying DXF files are
  being written to storage). That row was left untouched (no evidence it is
  wrong, just evidence of a second writer). Needs owner attention: confirm
  whether #19143's dispatch is still running and should be stopped, and
  whether its design should supersede or be merged with this one before
  either is treated as final.

## 6. CHANGE RULES
Additive by default. New surface, box, service, tunnel, or deploy target ⇒ update §1 in the same commit. A session that cannot find an answer here asks the owner; it does not infer from what happens to be running.

## 6.1 SECURITY EVIDENCE PACK
Investor/enterprise due-diligence security documentation lives at
`docs/security/SECURITY_EVIDENCE_PACK.md` (index), with `INCIDENT_RESPONSE_PLAN.md`,
`VENDOR_SUB_PROCESSOR_LIST.md`, `EXTERNAL_SCAN_SUMMARY.md` alongside it and
`docs/legal/DATA_RETENTION_POLICY.md` (live at `biddeed.ai/data-retention`).
Public summary at `biddeed.ai/security`. Built 2026-08-03; that session's scan
found `mcp.biddeed.ai` serving Vercel response headers, which conflicts with
§1's "no Vercel project exists for biddeed" — flagged there as unresolved,
not corrected in §1 without a dedicated verification session.

## 6.2 ENTERPRISE TRUST PORTAL (CAIQ / AI-CAIQ)
Self-serve vendor-security-review documentation, added 2026-08-03:
`docs/security/CAIQ-v4.1-BidDeed-Completed.md` (CSA-domain self-assessment),
`docs/security/AI-CAIQ-v1.1-BidDeed-Completed.md` (AI-specific self-assessment),
`docs/security/SECURITY_QUESTIONNAIRE_ANSWERS.md` (50-question lookup bank),
`docs/security/SAFEBASE_SETUP_GUIDE.md` (manual setup steps for Ariel).
Both CAIQ/AI-CAIQ docs open with a "Corrections from the originating brief"
table — several capabilities an earlier brief assumed (LlamaFirewall/LLM
Guard, a completed OWASP ZAP scan, Garak, a `mcp_usage_log` table, confirmed
MFA, an executing secret-rotation cadence) did not match live evidence
gathered the same session and are answered honestly (NO/PARTIAL), not as
the brief assumed. Do not restate those as YES elsewhere without re-verifying.
`trust.biddeed.ai` (SafeBase) is **not live** — portal signup requires
Ariel's browser session (§ SAFEBASE_SETUP_GUIDE.md); `biddeed.ai/security`
links the docs above directly in the meantime and says so explicitly.

## 6.3 INTERNAL EMAIL REGISTRY

| Address | Purpose | From identity | Consumers |
|---|---|---|---|
| `activate@biddeed.ai` | Customer-facing activation emails only. | `resend_from_address` (vault) | B2C trial/activation flow — **not touched by the 2026-08-03 alerts work.** |
| `alerts@biddeed.ai` | Internal ops alerts only (security P0/P1, secret rotation reminders). Added 2026-08-03. | `alerts_from_email` (vault) → `brevardbidderai@gmail.com` (`alerts_to_email`, vault) | `sweep_security_alerts()` (P0/P1 security events, cron `*/15`), `check_secret_rotation_due()` (cron Mon 09:00 UTC). **Not yet wired:** PostHog Worker-error relay (blocked on issue #17634/#17631, see §5) and weekly control-test report emailing (blocked — `scripts/generate_control_report.py` and `weekly-control-tests.yml` do not exist yet; that pipeline is issue #17584's scope, not built here). |

Both `sweep_security_alerts()` and `check_secret_rotation_due()` send email via a direct
`net.http_post` to Resend from inside the SECURITY DEFINER function (same pattern as the
existing Telegram sends) — the Resend key never leaves Postgres. Email is best-effort:
`IF v_resend_key IS NOT NULL AND v_to_email IS NOT NULL` guards each send, so a missing
vault entry silently skips email without blocking the Telegram leg (or vice versa).

---

## 7. MACHINE SSOT (Supabase) — this file defers to it for inventory

The queryable inventory layer lives in Supabase and is cron-verified; this file is the
narrative/topology layer. For component lists, counts, and facts, query — do not restate here:

- `ssot_registry_projects` / `ssot_registry_components` — projects and their 635 cataloged components.
- `ssot_facts` — verified operating facts with `source_sql` and `verified_at`; trust these over any number in a doc.
- `mcp_server_registry` — canonical MCP endpoint (`https://mcp.biddeed.ai/api/mcp`), npm package, declared tool count. `is_live` flips true only on an observed MCP handshake, never on a deploy claim.
- `v_ssot_master` and related views — rollups; per CC_META_PROMPT §2.2, cross-check any rollup against base tables before citing it as proof.

Precedence: for INVENTORY AND COUNTS, Supabase wins over this file. For TOPOLOGY AND
SERVING MODEL (§1–2), this file wins. A conflict between the two is a finding to report,
not a thing to silently resolve.
