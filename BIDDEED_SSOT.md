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

## 6. CHANGE RULES
Additive by default. New surface, box, service, tunnel, or deploy target ⇒ update §1 in the same commit. A session that cannot find an answer here asks the owner; it does not infer from what happens to be running.

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
