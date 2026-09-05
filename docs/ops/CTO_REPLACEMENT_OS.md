# CTO Replacement OS — corrected for the live 2026-09-05 Cloudflare topology

**Prepared by:** Claude Code, issue #20037 (LAUNCH-C canon repair), 2026-09-05.
**Status:** corrected brief for the Tuesday 2026-09-08 00:01 ET launch. Supersedes
the infra (§2) and stack (§3) sections of the original "CTO Replacement OS" brief
referenced in `docs/ops/LAUNCH_READINESS_T60_2026-09-05.md` §1/§5.
**Provenance note (read before relying on this file):** the original "CTO
Replacement OS" brief exists as a chat artifact and was never committed to this
repo — a repo-wide search on 2026-09-05 (`git log --all`, `grep -ril` for its
distinctive stack items) found no prior copy under any filename. This document
is **not** a verbatim reproduction of that brief. It is reconstructed from the
brief's content as quoted and critiqued in `docs/ops/LAUNCH_READINESS_T60_2026-09-05.md`
§1 ("Brief drift") and §5 ("The CTO stack, corrected") — the only artifact in
this repo that captures what the original brief said. Anything below sourced
from that doc is tagged **INFERRED (from LAUNCH_READINESS quote)**; anything
independently re-verified this session is tagged **VERIFIED**. Do not treat
this file as the original brief's full text — treat it as the corrected
infra/stack sections plus a pointer to the live audit for everything else.

---

## Corrections 2026-09-05

The original brief was written against `BIDDEED_SSOT.md` §1–2 as they stood
before this session, which described a Dell + Cloudflare Tunnel + Hetzner
topology. That topology had already been fully migrated away from by the time
the brief was written (Vercel exit completed 2026-09-05 13:40 UTC). Per
`CC_META_PROMPT.md` §2.3 ("the DoD query itself may be wrong"), the corrections
are called out here rather than silently folded in:

| Brief assumed | Live evidence (VERIFIED 2026-09-05) | This document answers |
|---|---|---|
| "Dell is production MCP via Cloudflare Tunnel; one tunnel + one box = one crash takes the product down" | `mcp.biddeed.ai` = Cloudflare Worker **`biddeed-mcp-production`** (created 12:18 UTC, DNS flipped 12:36 UTC, `server: cloudflare` header, no tunnel). Re-verified this session with a live authenticated MCP handshake (`initialize` → 200, `tools/list` → 200, 25 tools). | §2 below describes the Worker topology, not the Dell/Tunnel path. The Dell is not a bottleneck — it is not in the path. |
| "Hetzner 87.99.129.125 = Claude Code runner / dispatch box" | GHA-ONLY mandate (Ariel, 2026-09-02): no external SSH boxes. Dispatch is `cc-runner-ghonly.yml` (workflow id 297104962) on GitHub-hosted `ubuntu-latest` runners. | §3 below replaces every "install X on a server" stack item with a $0/GHA-only or Cloudflare-native equivalent — none of them need a host. |
| "Cloudflare Pages serves biddeed.ai" | `biddeed.ai` is served by Cloudflare Worker `worker-damp-snowflake-cead`, not Pages. | §2 below names the actual four production Workers. |
| Implied unlimited/standard Cloudflare Workers capacity for the stack items below | Cloudflare account is on **Workers FREE**: 100,000 requests/day account-wide (~20 Workers share it), 10 ms CPU/request — confirmed live by a rejected deploy (`limits.cpu_ms`, code 100328) and R2 not enabled (code 10042). | §2 and §4 record this as the binding constraint and the one paid decision on the table ($5/mo Workers Paid), not assumed away. |
| `mcp_server_registry` "36 tools" declared count, implicitly treated as current | Authenticated `tools/list` handshake this session: **25 tools**, matching `packages/biddeed-mcp/src/server.js`'s 25-entry `HANDLERS` map and `package.json`'s own "25 tools" description exactly — confirmed **not** a build regression (two prior sessions, `docs/spec/20025.md` and `docs/spec/20030.md`, reached the same conclusion from source alone; the 2026-08-03 CAIQ session's live `/security` page copy already said "25 tools" too). | `mcp_server_registry` corrected `declared_tool_count` 36→25, `is_live=true` (see `BIDDEED_SSOT.md` §7 for the full reconciliation record). |
| Self-hosted stack layer picks (Hermes, LiteLLM, Chatwoot self-host, GlitchTip, Grafana/Loki, Redis/BullMQ, Coolify, Uptime Kuma, Infisical, Unleash, PostHog self-host) — **INFERRED (from LAUNCH_READINESS quote)**, this document never saw the brief's original §3 text directly | None of these have a host to run on under the GHA-ONLY mandate. | §3 below is the $0/already-owned replacement for each layer, as already shipped and verified in `docs/ops/LAUNCH_READINESS_T60_2026-09-05.md` §5. |

---

## 1. Scope of this document

This file carries only the two sections `LAUNCH_READINESS_T60_2026-09-05.md`
identifies as wrong in the original brief — **infrastructure topology** and
**the CTO stack pick list**. For the full launch-readiness audit (security
findings, scale model, Ariel decisions, execution lanes, rollback map), see
`docs/ops/LAUNCH_READINESS_T60_2026-09-05.md`, which is canonical for the
launch window. For the narrative infra inventory and serving model, see
`BIDDEED_SSOT.md` §1–§2 (rewritten in this same issue).

## 2. Infrastructure — corrected topology (VERIFIED 2026-09-05)

| Surface | Served by | Status |
|---|---|---|
| `biddeed.ai` | Cloudflare Worker `worker-damp-snowflake-cead` (this repo, `src/worker.js`) → proxies to Worker `biddeed-web-production` (Next.js/OpenNext) for `/`, `/radar*`, `/_next/*`, `/api/*` | 200, full CSP + HSTS preload |
| `mcp.biddeed.ai` | Cloudflare Worker `biddeed-mcp-production` (this repo, `cloudflare/mcp-worker.mjs` → `packages/biddeed-mcp/src/http.js`) | 401-with-auth-hint unauthenticated; 200 on an authenticated handshake (verified live this session). No HSTS yet — known gap. |
| `zonewise.ai` / `www` | Cloudflare Worker `zonewise-web-production` (`breverdbidder/zonewise-web`, OpenNext, branch `cf-exit`) | 200, edge-cached |
| `winnerdataai.com` | Cloudflare Pages | 200 |
| `lms.winnerdataai.com` | Cloudflare Worker `winnerdata-lms` behind Cloudflare Access | 302 → login (correct) |
| `ff.winnerdataai.com` | Cloudflare Worker `winnerdata-ff` | No authentication as of this writing — known gap, Ariel decision pending (CC #20038) |
| `status.biddeed.ai` | Does not exist yet | CC #20036, not landed as of this document |

Dell and Hetzner are **retired-historical** — not in any serving path. Full
detail and row-by-row evidence: `BIDDEED_SSOT.md` §1.

**Binding constraint:** Cloudflare account is on Workers FREE — 100,000
requests/day shared across every Worker above, 10 ms CPU/request. This is a
known gap (`BIDDEED_SSOT.md` §5), not a plan change; Workers Paid ($5/mo) is
Ariel's decision, tracked in `docs/ops/LAUNCH_READINESS_T60_2026-09-05.md` §7.1.

## 3. The stack, corrected for $0-hosting / GHA-only / Cloudflare + Supabase

Reproduced from `docs/ops/LAUNCH_READINESS_T60_2026-09-05.md` §5 (already
shipped and verified there — not re-implemented by this document):

| Brief layer | Brief pick (INFERRED, no host under GHA-ONLY) | Ship instead (VERIFIED, $0 or already owned) |
|---|---|---|
| Night SRE / operator | Hermes Agent on Hetzner | pg_cron + `db_restart_watch` + `sweep_security_alerts` + Everest Sentinel (GHA) |
| LLM gateway | LiteLLM | Smart Router v5/v6 edge function (Gemini → Haiku/OAuth), already the `/chat/api` path |
| Customer inbox / CS | Chatwoot + n8n RAG | Deed on `/chat` (SSE, 8 languages) — zero-HITL CS surface |
| Tickets / incidents | GitHub Issues | Already correct — GitHub Issues + `agent_ops_log` |
| Errors + uptime | GlitchTip + Uptime Kuma | Workers Logs (built-in) + Upptime on GitHub Actions/Pages (MIT, $0) for `status.biddeed.ai` |
| Metrics | Grafana/Prometheus/Loki | Cloudflare Workers analytics + Supabase Reports + `v_cron_health` / `db_restart_log` |
| Queue | Redis/BullMQ | Supabase idempotency claim + `SKIP LOCKED` work tables today; Cloudflare Queues after Workers Paid |
| Edge | Cloudflare WAF/rate limit | Workers Rate Limiting binding (all plans) — CC #20035 |
| Deploy | GHA + Coolify | GHA → `wrangler deploy` (live for all four production Workers) |
| Secrets | Infisical/Doppler | GH Actions secrets + Worker secrets + Supabase Vault (live) |
| Feature flags | Unleash | Env vars / `unified_context` rows (live) |
| Status page | Gatus/Kuma | Upptime (above) |

Nothing in the right-hand column needs a VM before the Tuesday launch.

## 4. What this document does not cover

Security findings, the Supabase scale model, Ariel's five pending decisions,
the per-issue execution lanes (#20035–#20039), and the rollback map all live
in `docs/ops/LAUNCH_READINESS_T60_2026-09-05.md` and are not duplicated here —
duplicating live-audit numbers into a second document is how they go stale.
This file exists only to correct the brief's topology/stack assumptions in a
form that can be linked from `BIDDEED_SSOT.md` and future briefs.
