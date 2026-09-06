# BidDeed.AI — Launch Readiness, T-60h
## Live audit + hardening record for the Tuesday 2026-09-08 00:01 ET launch
**Written:** Sat 2026-09-05 15:00 UTC (11:00 EDT / 18:00 IST) · **Audience:** Ariel (decisions §7), Claude Code (execution §6, §8) · **Status:** canonical for the launch window; supersedes §0–§4 of the "CTO Replacement OS" brief where they conflict (see §1).
**Evidence standard:** Honesty Protocol V3. Every number below was observed live in this session (VERIFIED) unless tagged INFERRED or UNKNOWN.

---

## 0. Verdict

The product surface is up and correctly served from Cloudflare (biddeed.ai, mcp.biddeed.ai, zonewise.ai, winnerdataai.com all 200; MCP handshake healthy). **It was not launch-safe at 14:30 UTC today** for two reasons the brief did not know about, both now mitigated with free changes, and two decisions that only Ariel can make (§7).

| # | Finding (VERIFIED live) | Severity | State at 15:00 UTC |
|---|---|---|---|
| 1 | Supabase compute instance **reboots every 10–15 min** (95 restarts/24h, 96 the day before, 48h+; all services restart together — PgBouncer, PostgREST, GoTrue, Postgres) | P0 reliability | Load cut (cron stagger + 2 hot-path caches + anon timeout) — **not yet proven to stop the reboots** (one more at 14:59:58 after the changes). Cause is instance-level (memory, INFERRED); needs Ariel's dashboard/support (§7.5). |
| 2 | Public anon key exposed **434 Protection Partners leads** (contact name / phone / email) via REST + a SECURITY DEFINER view, and could invoke 14 internal dispatch/finance RPCs | P0 security (client PII, B2B data-services agreement) | **Closed.** 401 on all three paths; FF worker re-verified working. |
| 3 | Whole product on **Cloudflare Workers Free**: 100,000 requests/day for the entire account (20 Workers) and 10 ms CPU per request; over the cap = HTTP 1027 "fail closed" for the rest of the UTC day | P0 scale | **Ariel decision** (§7.1) — $5/mo. |
| 4 | `ff.winnerdataai.com/portal` lists all 436 leads with phones **with no login**; `/ff/<uuid>` pages carry full PII | P1 security | **Ariel decision** (§7.2) — Cloudflare Access, 5 min, $0. |
| 5 | Zero edge rate limiting anywhere (30 concurrent unauth POSTs to `/api/mcp` all answered, no 429) | P1 abuse/cost | CC issue #20035 (§6). |
| 6 | Homepage RPC `auctions_summary_ssot()` = 15.2 s mean, 2.9M blocks (~23 GB) read per 10 calls; `/api/coverage` 10.6 s single, timed out at 3 concurrent | P1 scale | **Fixed** — 0.44 s / 1.5 s, served from caches. |
| 7 | `status.biddeed.ai` does not exist; no status page, no public uptime | P2 ops | CC issue #20036 (§6). |
| 8 | Zero-HITL support: Chatwoot Hacker plan cannot post bot replies (403 "API access not enabled"); Deed on biddeed.ai `/chat` already answers | P2 CS | Ariel decision (§7.3) — recommend: drop Chatwoot, `/chat` is the CS surface. |
| 9 | Brief §2 / SSOT §1–2 describe a Dell + Cloudflare Tunnel + Hetzner topology that no longer exists | P2 canon drift | CC issue #20037 (§6). |

**Tuesday DoD (operational, per the brief):** MCP up · billed · rate-limited · queued/cached · monitored · CS answers without a human. Status per item in §8.

---

## 1. Brief drift — what the "CTO Replacement OS" brief got wrong (and why it matters)

The brief was written from SSOT §1–2, which still say *"Customer → mcp.biddeed.ai → Cloudflare Tunnel → local Dell"* and *"Hetzner 87.99.129.125 = CC runner box"*. Both are stale:

| Brief / SSOT claim | Live reality (VERIFIED today) | Consequence |
|---|---|---|
| "Dell is production MCP via Cloudflare Tunnel; one tunnel + one box = one crash takes the product down" | `mcp.biddeed.ai` = Cloudflare Worker **`biddeed-mcp-production`** (created 12:18 UTC today, DNS flipped 12:36, `server: cloudflare`, no tunnel). Vercel exit completed 13:40 UTC. | The Dell is not a bottleneck — it is not in the path. The bottleneck is the **Workers Free plan cap** and the **Supabase instance**. |
| "Hetzner = Claude Code runner / dispatch" | GHA-ONLY mandate (Ariel, Sep 2): no external SSH boxes. Dispatch is `cc-runner-ghonly.yml` (workflow 297104962) on `ubuntu-latest`. | Every "install X on a server" line in the brief's §3 stack (Hermes, LiteLLM, Chatwoot self-host, GlitchTip, Grafana/Loki, Redis/BullMQ, Coolify, Uptime Kuma, Infisical, Unleash, PostHog self-host) has **no host to run on** and violates the mandate. See §5 for the $0 / serverless equivalents. |
| "Supabase … Not a secret store" | Correct — but the live risk was the opposite: the **public** key could read client PII (fixed §3). | — |
| "Stripe LIVE, meter S5, 4 products" | Unchanged. S5 PDF generation on the MCP Worker is the known Free-plan CPU-cap risk (10 ms). | Paid purchases can fail under Free (§7.1). |
| "Launch Tuesday = freeze + scale-hardening + CS bot + rate limits" | Agreed. This document is that. | — |

Per SSOT §7, a topology conflict is "a finding to report, not silently resolve" — reported here; the SSOT amendment is CC issue #20037 (§6) so §1–2 get rewritten in a tracked commit.

---

## 2. Verified live state (15:00 UTC, Sat Sep 5)

### 2.1 Edge / serving
| Host | Served by | Status | Notes |
|---|---|---|---|
| biddeed.ai | Worker `worker-damp-snowflake-cead` → proxies `/`, `/radar*`, `/api/*` to Worker `biddeed-web-production` (OpenNext) | 200 | Full CSP (nonce + strict-dynamic), HSTS preload, X-Frame DENY, Permissions-Policy. `/api/health` sha `cfae7c04`. `/auctions` JSON `cache-control: public,max-age=60` but **no `cf-cache-status`** → not edge-cached (every hit reaches Supabase). |
| mcp.biddeed.ai | Worker `biddeed-mcp-production` | 401-with-hint on `/api/mcp` (healthy), `/.well-known/oauth-protected-resource` 200 (WorkOS), `/health` 200 | **No HSTS / security headers** on this host. tools/list requires auth. `mcp_server_registry` says 36 tools; live handshake this morning showed **25** (drift). |
| zonewise.ai / www | Worker `zonewise-web-production` (OpenNext, branch `cf-exit`, PR #113 unmerged) | 200, `cf-cache-status: HIT` on `/` | **No security headers at all** on prerendered `/` (known follow-up from cutover). |
| winnerdataai.com | Cloudflare Pages (mirror-deploy) | 200 | Good headers. |
| lms.winnerdataai.com | Worker `winnerdata-lms` behind Cloudflare Access | 302 → login | Correct. |
| ff.winnerdataai.com | Worker `winnerdata-ff` | **200, no auth** | §7.2. Also reachable at `winnerdata-ff.brevardbidderai.workers.dev`. |
| status.biddeed.ai | — | does not resolve | #20036. |
| mcp.zonewise.ai | — | no DNS (deliberate) | — |

**Cloudflare account plan: Workers FREE** (VERIFIED 12:22 UTC today — deploy rejected `limits.cpu_ms`, code 100328; R2 not enabled, 10042). 20 Workers on the account share one daily quota.

### 2.2 Concurrency probes (from this sandbox, 30 s timeouts)
| Probe | Result |
|---|---|
| `POST /api/mcp` ×30 concurrent, unauth | 30 × 401 in <1 s. **No 429** → no rate limit. |
| `GET biddeed.ai/auctions?county=…` ×30 concurrent | **all 30 timed out at 10 s (0 bytes)** at 14:33 UTC; ×10 at 14:36 → 0.4–0.7 s. INFERRED: the 14:33 burst coincided with an instance reboot. |
| `GET /county/brevard` ×10 concurrent | 14:36: **all 10 = 12.1 s**; 14:56 retest: 1.3–2.8 s (identical URL), 0.3–0.7 s (10 distinct counties). Single = 0.5 s. INFERRED: same-key request coalescing/DB contention; not edge-cached. |
| `GET zonewise.ai/api/coverage` | 10.6 s single; ×3 concurrent → **all timed out at 40 s** (before fix). After fix: 1.5 s single, 0.8–1.9 s ×3. |
| `GET zonewise.ai/` ×10 | 0.2–0.55 s (cache HIT). |

### 2.3 Supabase `mocerqjnksmhcjzxrewo`
| Metric | Value |
|---|---|
| Compute | Large (8 GB) — `shared_buffers` 2 GB, `work_mem` 12 MB, `maintenance_work_mem` 512 MB, `max_connections` 160, `max_parallel_workers` 2 |
| Database size | **64 GB** — `fl_parcels_stage` 15 GB (staging copy, larger than `fl_parcels` 11 GB), `zw_parcels` 12 GB, `fl_parcel_assessments` 6.9 GB, `zw_building_footprints` 4 GB, `zoning_assignments` 2.4 GB, `multi_county_auctions` 1 GB (117,188 rows) |
| Restarts | `db_restart_log`: **95 in last 24 h, 96 in the 24 h before** (4/hour, every hour, 30 h of hourly buckets checked). Postgres logs (24 h): `database system was not properly shut down; automatic recovery` ×58, `was interrupted` ×61, `redo done` ×17. Deaths at ~:04 / :19 / :34 / :49, then 14:49 and **14:59:58 UTC** (after the cron stagger). **Decisive detail:** at 14:59:58 PgBouncer, PostgREST, GoTrue (auth_logs burst) and Postgres all log their boot lines in the same second → this is a **whole-compute-instance restart**, not a Postgres crash. No `terminated by signal` / `out of memory` lines exist because the kill happens above Postgres. INFERRED cause: instance memory exhaustion on the 8 GB Large (Supabase restarts unhealthy instances); cannot be proven from inside the database — needs the Supabase dashboard memory report (§7.5). Side effect VERIFIED: every restart wipes `pg_stat_user_tables` (all counters 0, `last_autovacuum = never` on every big table), so autovacuum thresholds never accumulate → bloat is growing unchecked. |
| Cron | 97 active jobs before changes; **36 jobs started in the same second at 14:30:00** (8 every-minute + */2 + */5 + */10 + */15 + */30 + hourly all align at :00/:15/:30/:45); 754 cron runs/hour; 0 failures/hour. |
| Hot statements (14 min of uptime) | `auctions_summary_ssot()` via PostgREST: 10 calls, **mean 15,176 ms, max 15,252 ms, 2,914,563 shared blocks read**; `multi_county_auctions LIMIT/OFFSET case_number` paging: 10 calls, 3,164 ms mean. |
| Role timeouts | `anon` / `authenticated` / `service_role` `statement_timeout` were **10 min** (Supabase default 3 s / 8 s). |
| GHA scheduled load (last ~13 h, cli-anything-biddeed, 683 workflows) | Everest Sentinel 71 runs (~every 11 min), everest-sentinel-5-repos-deploy 68 (7 failures), Sentinel V2 63, Sync Credentials → Vault 48 (7 failures), Watchdog Stuck CC 42, Gold Standard Tick Watcher 36, centroid-watchdog 33, SUMMIT Verifier 27, Continuous Executor 27, Task Lifecycle 26, ff-send-approved 19, `fl-parcel-centroids-all` 7 runs / **6 failures** (8-way matrix hammering PostgREST, re-armed by centroid-watchdog). |
| Security advisor | 3,426 lints: **2 ERROR** (`winnerdata.v_producer_intake` security_definer view — fixed; `spatial_ref_sys` — accepted PostGIS exception), 208 `anon_security_definer_function_executable`, 214 authenticated, 309 `function_search_path_mutable`, 1,089 pg_graphql anon-exposed tables (GraphQL introspection returned 0 types live → not exploitable), 5 extensions in public, 498 INFO. |

### 2.4 Customers / billing
`mcp_api_keys` 19 · `mcp_customers` 25 · Stripe LIVE (acct `acct_1LPHtN…`), webhook v18 active. Zero confirmed external paying customers as of the last audit on file; the Tuesday launch is the first revenue event under load.

---

## 3. Security — findings, evidence, remediation

### 3.1 Closed in this session (migration `launch_hardening_anon_surface_20260905`, rollback SQL inside)
| Exposure (before) | Proof | Fix | After |
|---|---|---|---|
| `GET /rest/v1/leads` with `Accept-Profile: winnerdata` + public anon key | `206`, `content-range: 0-0/434` | Dropped `ff_worker_anon_*` policies on `winnerdata.leads/binds/ff_responses`; revoked anon table grants. The FF Worker only uses SECURITY DEFINER RPCs owned by `postgres` (`ff_portal_leads`, `ff_get_lead`, `ff_record_bind`, `ff_upsert_response`, `ff_healthz`) which bypass RLS → **no functional change**. | `401` |
| `winnerdata.v_producer_intake` (security_definer, anon SELECT) — contact name/phone/email + buyer mailing address | 408 rows to `set role anon`; 3 rows returned over REST | `security_invoker = true` + revoke anon/authenticated | `401` |
| 14 internal SECURITY DEFINER functions executable by anon/authenticated: `finance.simplefin_sync/_backfill/daily_close/_send_close_alert`, `dispatch_realauction_sweep`, `dispatch_skill_audit`, `dispatch_homeharvest_rental_ingest`, `fl_dor_dispatch_wave`, `cc_redispatch_tick/_reconcile`, `auto_dispatch_awaiting_verification`, `gha_log_agent_tick`, `reconcile_gha_dispatch_log`, `check_secret_rotation_due` | `POST /rest/v1/rpc/reconcile_gha_dispatch_log` → `200` with anon key | `REVOKE EXECUTE … FROM anon, authenticated` (pg_cron runs as `postgres`, unaffected) | `401` |
| anon `statement_timeout = 10min` (public-key DoS) | `pg_roles.rolconfig` | anon 15 s, authenticated 30 s (migration `zoning_coverage_cache_and_anon_timeout_20260905`) | — |

Regression checks after the change: `ff.winnerdataai.com/portal` 200 (436 rows), a real `/ff/<uuid>` 200 with "Producer Call Script", `/healthz` `{"status":"ok","leads":434}`; biddeed.ai `/`, `/auctions`, zonewise.ai `/` all 200.

### 3.2 Open — needs Ariel (§7)
- **FF portal has no authentication** (`/portal`, `/ff/<uuid>`, `/producer-report?user_id=`, `/owner-dashboard?user_id=` — `user_id` is a query-string parameter). Fix = Cloudflare Access application on `ff.winnerdataai.com` (same Access login already used by the LMS + CFO agent), allowed emails `@protectionpartners.net` + Ariel; CC #20038 disables the `workers.dev` route so Access cannot be bypassed.
- Remaining anon-callable SECURITY DEFINER RPCs (~190 in `public`). Most are legitimate public reads (county cards, SSOT counts, chat). The `ff_*` five take `p_org_id` as their only "credential" — #20038 moves the FF Worker to a Worker secret and revokes anon on those five **after** the Worker is redeployed.

### 3.3 Not changed, on record
- 309 `function_search_path_mutable` warnings — hardening backlog, not launch-blocking (`SET search_path` on SECURITY DEFINER functions).
- `graphql_public` USAGE granted to anon — introspection returns 0 types live; leave.
- Unrotated secrets per `secret_rotation_registry` (35 of 37 never rotated as of Aug 3; service_role rotated Aug 12; Clerk secret rotated Sep 3). Not touched — owner-only.
- `fl_parcels_stage` (15 GB) looks like a finished staging copy. **Not dropped** — deleting production data is an Ariel call. Freeing it would take the DB from 64 → 49 GB.

---

## 4. Scale model — "thousands of users, hundreds of paid subscribers"

### 4.1 Cloudflare Workers Free vs Paid (the binding constraint)
Cloudflare's published limits: Free = **100,000 requests/day** and **10 ms CPU per invocation**; over the daily cap → Error 1027 (fail closed) until the next UTC day. Paid = **$5/month minimum, 10 million requests/month included (+$0.30/M), 30 million CPU-ms included (+$0.02/M), 30 s CPU default (max 5 min)**.

What 100k/day means for BidDeed (all 20 Workers share it):
| Traffic | Requests/day (INFERRED, from observed page composition) |
|---|---|
| One biddeed.ai page view (HTML + `/_next/*` assets + `/api/*` calls, mostly served by the Worker, not the CDN cache) | ~15–40 |
| 1,000 visitors × 3 pages | 45,000–120,000 → **cap hit by afternoon** |
| 300 paid MCP subscribers × 50 tool calls/day | 15,000 (each tool call is 1 request, but S5 PDF rendering blows the 10 ms CPU cap → 1102 errors on the **paid** path) |
| Background: LMS, FF, CFO, cron pings, uptime monitors | 5,000–10,000 |

Conclusion: **Free cannot survive launch day if the marketing works.** Paid at $5/mo gives 333k requests/day equivalent and removes the CPU wall on PDF generation. This is the single spend decision on the table (§7.1). Everything else in this document is $0.

### 4.2 Supabase (Large, 8 GB)
Before today's changes the homepage alone cost the DB 15 s and ~2.3 GB of block reads per hit, and the instance was rebooting 4×/hour with **zero external customers**. After: homepage RPC 0.44 s from cache (refreshed every 10 min, `compute_ms` 2,033), coverage API 1.5 s from an hourly cache, anon queries capped at 15 s, cron peak 36 → 13 simultaneous starts, cron runs/hour 754 → ~517.
Capacity headroom (INFERRED): PostgREST is HTTP, so 1,000 concurrent browsers do not map to 1,000 Postgres connections; the pooler + 160 max_connections is adequate **if** the per-request DB work stays in the milliseconds, which is what the caching achieved for the two known hot paths. Unknown remaining hot paths get caught by the 15 s anon cap instead of taking the instance down.
**Rule for the launch window:** no new pg_cron job and no GHA workflow that scans `fl_parcels`/`zw_parcels`/`zoning_assignments` until Wednesday. `fl-parcel-centroids-all` (8-way matrix, 6/7 failed today) is the first to pause (#20039).

### 4.3 MCP
Auth: `bd_live_` API keys / WorkOS OAuth, cert gate before charge, idempotent billing chain (SSOT §2, proven Jul 20). 401 on every unauth path ✔. Missing: rate limit per key and per IP (#20035), tool-count registry sync (25 live vs 36 declared, #20037), HSTS header. Queue: the brief's "Redis + BullMQ required before 1k tenants" has no host; Cloudflare Queues requires Workers Paid — another reason for §7.1. Until then, the Worker's per-request model + Supabase idempotency claim is the queue.

---

## 5. The CTO stack, corrected for the real constraints ($0 hosting, GHA-only, Cloudflare + Supabase)

| Brief layer | Brief pick | Why it cannot ship by Tuesday | Ship instead (all $0 or already owned) |
|---|---|---|---|
| Night SRE / operator | Hermes Agent on Hetzner | No box (GHA-only mandate) | pg_cron + `db_restart_watch` + `sweep_security_alerts` (already live) + Everest Sentinel (GHA). Alerts stay in Claude chat/Cowork + LMS per Ariel's no-external-channels rule. |
| LLM gateway | LiteLLM | Needs a host | Smart Router v5/v6 edge function (Gemini → Haiku/OAuth), already the `/chat/api` path. |
| Customer inbox / CS | Chatwoot + n8n RAG | Hacker plan cannot post bot replies (403); self-host needs Rails+Redis host | **Deed on `/chat`** (SSE, 8 languages) is the zero-HITL CS surface; unresolved → `/chat/lead` email capture (tag `support_escalation`). Chatwoot widget stays down (§7.3). |
| Tickets / incidents | GitHub Issues | ✔ already | GitHub Issues + `agent_ops_log`. |
| Errors + uptime | GlitchTip + Uptime Kuma | Need hosts | Workers Logs (built in) + **Upptime** on GitHub Actions/Pages (MIT, $0, no server) for `status.biddeed.ai` (#20036). |
| Metrics | Grafana/Prometheus/Loki | Need hosts | Cloudflare Workers analytics + Supabase Reports + `v_cron_health` / `db_restart_log` (live). |
| Queue | Redis/BullMQ | No host | Cloudflare Queues after Workers Paid; today: Supabase idempotency claim + `SKIP LOCKED` work tables (pattern already used by the shard missions). |
| Edge | Cloudflare WAF/rate limit | Zone token is DNS-only from chat; Free plan = 1 rate-limit rule | **Rate limiting inside the Workers** (Workers Rate Limiting binding, all plans) — #20035. Ariel can additionally add the one free WAF rule on `mcp.biddeed.ai/api/mcp`. |
| Deploy | GHA + Coolify | Coolify needs a host | GHA → `wrangler deploy` (live for all 4 production Workers). |
| Secrets | Infisical/Doppler | Adds a service | GH Actions secrets + Worker secrets + Supabase Vault (live). |
| Feature flags | Unleash | Adds a host | Env vars / `unified_context` rows (live). |
| Status page | Gatus/Kuma | Hosts | Upptime (above). |

Cut list from the brief stands, plus: Coolify, Hetzner CX, Hermes, LiteLLM, GlitchTip, Kuma, Grafana stack, Redis — **nothing that needs a VM before Wednesday.**

---

## 6. Execution — dispatched to Claude Code (cc-runner 297104962, one lane per issue, intent file per issue)

| Lane | Issue | Scope (DoD is live-observed, Honesty V3) | Owner |
|---|---|---|---|
| A | **#20035 Edge hardening in-Worker** | Rate limiting via Workers Rate Limiting binding: `biddeed-mcp-production` `/api/mcp` per-API-key (120/min) + per-IP unauth (20/min → 429 + `Retry-After`); `worker-damp-snowflake-cead` `/chat/api` 30/min/IP, `/chat/lead` 5/min/IP, `/auctions` 60/min/IP; `biddeed-web-production` `/api/*` 120/min/IP. Edge-cache `/auctions` JSON + `/county/:slug` 60 s via `caches.default` (DoD: `cf-cache-status: HIT` on second hit). Add HSTS/X-Content-Type/Referrer-Policy on `mcp.biddeed.ai` and on zonewise prerendered `/`. Deploy through the existing production workflows only. | CC |
| B | **#20036 Status page** | Upptime repo `breverdbidder/status` (GitHub Actions + Pages), monitors: biddeed.ai `/api/health`, mcp `/.well-known/oauth-protected-resource`, zonewise.ai `/api/stats`, winnerdataai.com, Supabase REST (`rpc/auctions_summary_ssot` anon), `ff.winnerdataai.com/healthz`. CNAME `status.biddeed.ai` (CC token has DNS:Edit on the biddeed.ai zone). 5-min checks. | CC |
| C | **#20037 Canon repair** | Rewrite SSOT §1 inventory + §2 serving model to the verified Cloudflare Workers topology (Vercel exit 2026-09-05, Dell/Hetzner rows retired to a "historical" note), record Workers Free limits as a known gap, sync `mcp_server_registry.tool_count` 36 → live 25 (or fix the server if 25 is the bug — decided by handshake, not by doc), file this document and the corrected brief at `docs/ops/`. | CC |
| D | **#20038 FF Worker lockdown** | `workers_dev = false` for `winnerdata-ff` (only `ff.winnerdataai.com` remains, ready for Access); Worker reads `SUPABASE_KEY` from a Worker secret (service role) instead of the hardcoded anon key; then revoke anon EXECUTE on `ff_portal_leads/ff_get_lead/ff_record_bind/ff_upsert_response/ff_healthz`; `X-Robots-Tag: noindex`. Producer-facing behaviour unchanged (DoD: portal 200 with 436 rows, one FF page renders, anon RPC call → 401). No-send mandate in body. | CC (secret binding step may need Ariel if the deploy workflow lacks the CF token) |
| E | **#20039 DB stampede diet — GHA side** | Cap `fl-parcel-centroids-all` matrix at 2 workers + pause `centroid-watchdog` re-arm until Wed; consolidate the three Sentinel workflows (≈200 runs/day) into one 15-min schedule; move every scheduled workflow that hits PostgREST off `*/15`-aligned crons; report before/after `db_restart_log` counts per hour. No data deletions. | CC |

Chat-side changes already applied (Supabase, tracked as migrations `launch_hardening_anon_surface_20260905`, `auctions_summary_ssot_cache_20260905`, `cron_stagger_launch_hardening_20260905`, `zoning_coverage_cache_and_anon_timeout_20260905`) — each carries verbatim rollback.

---

## 7. Decisions only Ariel can make (with the numbers)

### 7.1 Cloudflare Workers Paid — $5/month (recommend YES, today)
Free: 100,000 requests/day across all 20 Workers, 10 ms CPU/request, fail-closed 1027 at the cap. Paid: 10M requests/month + 30M CPU-ms included, $5 minimum, 30 s CPU. Launch-day math in §4.1: 1,000 visitors ≈ 45k–120k requests. The S5 report PDF ($25 product) renders on the MCP Worker and is the documented Free-plan CPU risk from this morning's cutover. This is the only paid item in this plan; it also unlocks Cloudflare Queues and R2 (ISR cache for zonewise). Where: Cloudflare dashboard → Workers & Pages → Plans. Ariel's credentials only.

### 7.2 Cloudflare Access on `ff.winnerdataai.com` — $0, ~5 minutes (recommend YES, before Tuesday)
436 Protection Partners leads with phone numbers are readable at a URL with no login. Zero Trust → Access → Applications → Self-hosted → `ff.winnerdataai.com` → policy: allow emails ending `@protectionpartners.net` + your address (one-time PIN). Producers keep the same links; they get an email code once per session. CC #20038 removes the `workers.dev` bypass in parallel.

### 7.3 Support channel for launch (recommend: Deed on `/chat`, Chatwoot stays dark)
Chatwoot Hacker cannot reply (API is paid, $19/agent contradicts "never human, never $19 tier"). `/chat` already answers in 8 languages and captures escalations. Decision needed only if you want the Chatwoot widget back on the sites (it is inert/503 today by design).

### 7.5 Supabase instance reboots — 2 minutes of your dashboard, then a support ticket (recommend: today)
The compute instance has rebooted ~96×/day for 2+ days (all services at once). From inside the DB this is invisible; the load reductions applied today may or may not be enough. Two things only your login can do:
1. Dashboard → Reports → Database → **Memory** and **CPU** for the last 48 h. If memory pegs at ~100% before each restart, it is our load (then §7.4 + CC #20039 are the fix, and we re-measure). If memory is flat and the instance still reboots, it is platform-side.
2. Either way, open a Supabase support ticket (included with the paid plan) with this text: *"Project mocerqjnksmhcjzxrewo (Large, us-west-2) has restarted the whole compute instance every 10–15 minutes since at least 2026-09-03 (db_restart_log: 95 restarts in 24 h). Postgres logs show 'database system was not properly shut down' 58× in 24 h with no OOM/signal lines; PgBouncer, PostgREST and GoTrue restart in the same second. Please check the instance's restart reason and memory ceiling."*
Not recommended: the XL upgrade you already declined — not until the memory graph says so.

### 7.4 Optional cleanups you asked about ("clean up something else in Supabase")
`fl_parcels_stage` = 15 GB staging table (vs 11 GB production `fl_parcels`). If it is a finished staging artifact, dropping it takes the DB 64 → 49 GB and shortens crash recovery. Needs your yes — it is production data by definition until you say otherwise.

### 7.6 Odoo C10 — merged as files, not deployed (#20046, 2026-09-06)
Odoo C10: merged as files; going live requires a host (Docker) — not present in the launch stack; owner decision pending.

---

## 8. Tuesday 00:01 ET — operational DoD scorecard

| DoD line (brief §0) | Evidence required | State now |
|---|---|---|
| MCP up | `/.well-known` 200, `/api/mcp` 401-with-hint, authed `tools/list` returns tools; Upptime green 24 h | ✔ up · status page pending (#20036) |
| Billed | Stripe webhook edge fn active, `subscription_events` row on a live test purchase | Webhook v18 active; end-to-end paid test still the one founder action on record |
| Rate-limited | 429 observed on burst; `cf-cache-status: HIT` on `/auctions` | ✖ → #20035 |
| Queued / cached | Homepage RPC < 1 s, coverage < 2 s at 3× concurrency | ✔ (0.44 s / 1.5 s) |
| Monitored | `db_restart_log` < 1/hour for 24 h; status page public; Sentinel alerts land in chat | Restart watch live; reboots continue (§7.5) |
| CS answers without you | `/chat` answers + `/chat/lead` escalation path 200 | ✔ live (Chatwoot dark by decision) |
| Compliance canon intact | No homeowner contact paths; FF/portal B2B only; `insurance exclusivity` untouched | ✔ (no product logic changed) |
| BID/SKIP stays advisory | No auto-bid code path exists | ✔ |

**Launch gate (go/no-go at Mon 21:00 ET):** restarts/hour ≤ 1 for the trailing 24 h · #20035 429s observed · Workers plan decision recorded · FF Access on or explicitly deferred · status page green.

---

## 9. Rollback map
| Change | Rollback |
|---|---|
| Anon surface migration | Verbatim `CREATE POLICY` / `GRANT` statements in the migration header |
| `auctions_summary_ssot` cache | `alter function auctions_summary_ssot() rename to _cached; alter function auctions_summary_compute() rename to auctions_summary_ssot;` and `cron.unschedule('auctions-summary-cache-refresh')` |
| `v_zoning_coverage` cache | `create or replace view v_zoning_coverage as select * from v_zoning_coverage_live;` |
| Cron stagger | Original schedule recorded per line in the migration; `cron.alter_job(jobid, schedule := '<original>')` |
| anon/authenticated timeouts | `alter role anon set statement_timeout = '10min'` (not recommended) |
| Worker changes (#20035/#20038) | `wrangler rollback` / revert commit; deploy workflows unchanged |
