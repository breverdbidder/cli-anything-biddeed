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
| **npm `biddeed-mcp`** | Intended stdio distribution channel. **Unpublished** (registry 404). `NPM_TOKEN` absent from repo secrets. | Not required for the HTTP surface to go live. Publish is a separate owner decision. |

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

## 6. CHANGE RULES
Additive by default. New surface, box, service, tunnel, or deploy target ⇒ update §1 in the same commit. A session that cannot find an answer here asks the owner; it does not infer from what happens to be running.
